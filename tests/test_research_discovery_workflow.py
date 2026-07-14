import contextlib
import copy
import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import fingerprint, open_director_registry  # noqa: E402
from research_discovery_common import DiscoveryError  # noqa: E402
import research_discovery_trigger as trigger_module  # noqa: E402
from research_discovery_trigger import (  # noqa: E402
    create_trigger,
    main,
    prepare_run,
    render_researcher_packet,
)


CREATED_AT = "2026-07-14T00:00:00+00:00"
EVENT_REF = "human-request-2026-07-14"


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class FaultConnection:
    def __init__(self, connection: sqlite3.Connection, fault: str):
        self.connection = connection
        self.fault = fault

    def execute(self, sql, parameters=()):
        normalized = " ".join(sql.split())
        if self.fault == "insert" and normalized.startswith(
            "INSERT INTO research_discovery_runs"
        ):
            raise sqlite3.OperationalError("injected insert failure")
        return self.connection.execute(sql, parameters)

    def commit(self):
        if self.fault == "commit":
            raise OSError("injected commit failure")
        return self.connection.commit()

    def rollback(self):
        return self.connection.rollback()

    def close(self):
        return self.connection.close()


class ResearchDiscoveryWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repo = Path(self.temporary_directory.name) / "repo"
        self.registry = Path(self.temporary_directory.name) / "director-registry.sqlite"

        required_files = (
            "research/discovery/schemas/research-trigger.schema.json",
            "research/discovery/schemas/research-idea.schema.json",
            "research/discovery/prompts/researcher.md",
            "research/discovery/prompts/critic.md",
        )
        for relative in required_files:
            destination = self.repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)

        self.allowed_paths = {
            "research/data/snapshots/futures-dev-btc/manifest.yaml",
            "research/data/snapshots/futures-dev-eth/manifest.yaml",
            "research/evidence/temporal-comparison.json",
            "research/runtime/freqtrade-runtime.yaml",
        }
        for relative in self.allowed_paths:
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture: {relative}\n", encoding="utf-8")

        validation_path = (
            self.repo
            / "research/data/snapshots/futures-validation-btc/manifest.yaml"
        )
        validation_path.parent.mkdir(parents=True, exist_ok=True)
        validation_path.write_text("fixture: validation\n", encoding="utf-8")

        self.state = {
            "schema_version": "current-research-state-v1",
            "generated_at": CREATED_AT,
            "state_conflicts": [],
            "allowed_research_scope": {
                "approved_market": "Binance USD-M Futures",
                "baseline_pair": "BTC/USDT:USDT",
                "baseline_timeframe": "1h",
                "campaign_compilation_only": True,
                "human_approved_additional_pairs": ["ETH/USDT:USDT"],
                "candidate_creation": False,
                "evidence": [],
                "ranging_short_evidence_reuse": "approved_research_only",
                "read_only_analysis": True,
                "strategy_mutation": False,
            },
            "datasets": [
                {
                    "dataset_id": "futures-dev-btc",
                    "intended_use": "development",
                    "agent_visibility": "full",
                    "pairs": ["BTC/USDT:USDT"],
                    "timeframes": ["1h", "4h"],
                    "path": "research/data/snapshots/futures-dev-btc/manifest.yaml",
                    "sealed": True,
                },
                {
                    "dataset_id": "futures-dev-eth",
                    "intended_use": "development_descriptive_cross_pair_generalization_only",
                    "agent_visibility": "full",
                    "pairs": ["ETH/USDT:USDT"],
                    "timeframes": ["1h", "4h"],
                    "path": "research/data/snapshots/futures-dev-eth/manifest.yaml",
                    "sealed": True,
                },
                {
                    "dataset_id": "futures-validation-btc",
                    "intended_use": "validation",
                    "agent_visibility": "controlled",
                    "pairs": ["BTC/USDT:USDT"],
                    "timeframes": ["1h", "4h"],
                    "path": "research/data/snapshots/futures-validation-btc/manifest.yaml",
                    "sealed": True,
                },
            ],
            "runtime_contracts": [
                {
                    "claim": "Approved immutable runtime",
                    "exists": True,
                    "path": "research/runtime/freqtrade-runtime.yaml",
                }
            ],
            "unresolved_research_questions": [
                {
                    "question_id": "temporal-generalization",
                    "question": "Which mechanism remains unresolved?",
                    "evidence": [
                        "research/evidence/temporal-comparison.json",
                        "reports/Validation/validation-result.json",
                    ],
                }
            ],
            "formal_strategy": {
                "name": "RegimeAwareV6",
                "path": "strategies/RegimeAwareV6.py",
            },
        }
        self._reseal_state(self.state)
        self.constitution = {
            "schema_version": "research-constitution-v1",
            "constitution_id": "research-director-governance-v1",
            "status": "approved",
            "approval_status": "approved",
            "approver_type": "human_user",
            "approved_at": "2026-07-12T07:14:16Z",
            "approved_version": 1,
            "approval_hash_authority": "research/governance/approvals/research-constitution-v1-approval.json",
            "approved_version_immutable": True,
            "amendment_requires_new_version_hash_and_human_approval": True,
            "agent_mutable": False,
        }
        self.source_policy = {
            "schema_version": "research-source-policy-v1",
            "classes": {
                "A": [
                    "repository_frozen_data",
                    "completed_research_artifact",
                    "research_registry",
                    "branch_closure",
                    "approved_governance",
                    "official_exchange_documentation",
                ],
                "B": [
                    "peer_reviewed_paper",
                    "reputable_preprint",
                    "textbook",
                    "institutional_research_report",
                ],
                "C": [
                    "public_strategy_repository",
                    "blog",
                    "forum",
                    "social_media",
                    "video",
                    "ranking",
                    "commercial_claim",
                ],
            },
            "pass_requirement": "at_least_one_A_or_B",
            "class_c_only_result": "reject",
            "external_required_fields": [
                "canonical_url",
                "source_class",
                "publisher_type",
                "retrieved_at",
                "claim",
                "content_fingerprint",
                "staleness_assessment",
                "licensing_constraints",
            ],
            "forbidden_inputs": [
                "validation_result",
                "holdout",
                "private_api",
                "secret",
                "live_account",
                "unapproved_dataset",
            ],
            "store_full_copyrighted_source": False,
        }
        self._write_bound_contracts()

    def tearDown(self):
        trigger = create_trigger(
            event_type="manual_request",
            event_ref=EVENT_REF,
            state=self.state,
            constitution=self.constitution,
            source_policy=self.source_policy,
            created_at=CREATED_AT,
        )
        run_id = f"discovery-run-{trigger['trigger_fingerprint'][:16]}"
        temp_run_root = (
            Path(tempfile.gettempdir()) / "freqtrade-research-discovery" / run_id
        )
        if temp_run_root.is_dir():
            shutil.rmtree(temp_run_root)

    def _write_bound_contracts(self) -> None:
        write_json(
            self.repo / "research/director/current-research-state.json", self.state
        )
        write_json(
            self.repo / "research/governance/research-constitution.yaml",
            self.constitution,
        )
        write_json(
            self.repo / "research/discovery/policy/source-policy.yaml",
            self.source_policy,
        )

    @staticmethod
    def _reseal_state(state: dict[str, object]) -> None:
        state.pop("state_fingerprint", None)
        state.pop("snapshot_id", None)
        state["state_fingerprint"] = fingerprint(
            {
                key: value
                for key, value in state.items()
                if key not in {"generated_at", "state_fingerprint", "snapshot_id"}
            }
        )
        state["snapshot_id"] = f"research-state-{state['state_fingerprint'][:16]}"

    def _trigger(self) -> dict[str, object]:
        return create_trigger(
            event_type="manual_request",
            event_ref=EVENT_REF,
            state=self.state,
            constitution=self.constitution,
            source_policy=self.source_policy,
            created_at=CREATED_AT,
        )

    def _run_locations(
        self, trigger: dict[str, object]
    ) -> tuple[dict[str, object], Path, Path]:
        result = trigger_module._expected_result(trigger)
        return (
            result,
            self.repo / result["run_path"],
            Path(result["researcher_inbox"]),
        )

    def _assert_discovery_registry_empty(self, registry: Path) -> None:
        if not registry.exists():
            return
        with contextlib.closing(sqlite3.connect(registry)) as connection:
            for table in (
                "research_discovery_runs",
                "research_discovery_ideas",
                "research_discovery_critiques",
                "research_discovery_shortlists",
                "research_discovery_approvals",
                "research_discovery_handoffs",
                "research_discovery_events",
            ):
                self.assertEqual(
                    connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0],
                    0,
                    table,
                )

    def _assert_no_new_run_residue(
        self,
        trigger: dict[str, object],
        registry: Path,
        *,
        preexisting_inbox: bool = False,
    ) -> None:
        _, final_run, inbox = self._run_locations(trigger)
        self.assertFalse(os.path.lexists(final_run), final_run)
        runs_root = final_run.parent
        if runs_root.exists():
            self.assertEqual(list(runs_root.iterdir()), [])
        if preexisting_inbox:
            self.assertTrue(inbox.is_dir())
            self.assertEqual(list(inbox.iterdir()), [])
        else:
            self.assertFalse(os.path.lexists(inbox.parent))
        self._assert_discovery_registry_empty(registry)

    def _cli_command(
        self,
        registry: Path,
        *,
        event_type: str = "manual_request",
        event_ref: str = EVENT_REF,
        state: str = "research/director/current-research-state.json",
    ) -> list[str]:
        return [
            sys.executable,
            "-B",
            str(ROOT / "scripts/research_discovery_trigger.py"),
            "--event-type",
            event_type,
            "--event-ref",
            event_ref,
            "--state",
            state,
            "--constitution",
            "research/governance/research-constitution.yaml",
            "--source-policy",
            "research/discovery/policy/source-policy.yaml",
            "--director-registry",
            str(registry),
            "--repo-root",
            str(self.repo),
        ]

    def _run_cli_process(
        self, registry: Path, **kwargs
    ) -> tuple[int, int, str, str]:
        process = subprocess.Popen(
            self._cli_command(registry, **kwargs),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        stdout, stderr = process.communicate(timeout=30)
        return process.pid, process.returncode, stdout, stderr

    def _assert_cli_error(
        self,
        returncode: int,
        stdout: str,
        stderr: str,
        expected_reason: str,
    ) -> None:
        self.assertEqual(returncode, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(len(stderr.strip().splitlines()), 1)
        payload = json.loads(stderr)
        self.assertEqual(
            set(payload), {"status", "reason_code", "detail"}
        )
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["reason_code"], expected_reason)
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("TOP-SECRET-MARKER", stderr)

    def test_a_create_trigger_recomputes_state_and_validates_structure(self):
        self.assertEqual(self._trigger()["research_state_fingerprint"], self.state["state_fingerprint"])

        content_tamper = copy.deepcopy(self.state)
        content_tamper["datasets"][0]["pairs"].append("SOL/USDT:USDT")
        with self.assertRaises(DiscoveryError) as fingerprint_conflict:
            create_trigger(
                "manual_request",
                EVENT_REF,
                content_tamper,
                self.constitution,
                self.source_policy,
                CREATED_AT,
            )
        self.assertEqual(
            fingerprint_conflict.exception.reason_code,
            "state_fingerprint_conflict",
        )

        wrong_schema = copy.deepcopy(self.state)
        wrong_schema["schema_version"] = "current-research-state-v2"
        self._reseal_state(wrong_schema)
        with self.assertRaises(DiscoveryError) as schema_invalid:
            create_trigger(
                "manual_request",
                EVENT_REF,
                wrong_schema,
                self.constitution,
                self.source_policy,
                CREATED_AT,
            )
        self.assertEqual(schema_invalid.exception.reason_code, "state_schema_invalid")

        wrong_snapshot = copy.deepcopy(self.state)
        wrong_snapshot["snapshot_id"] = "research-state-deadbeefdeadbeef"
        with self.assertRaises(DiscoveryError) as snapshot_conflict:
            create_trigger(
                "manual_request",
                EVENT_REF,
                wrong_snapshot,
                self.constitution,
                self.source_policy,
                CREATED_AT,
            )
        self.assertEqual(
            snapshot_conflict.exception.reason_code, "state_snapshot_conflict"
        )

        malformed_scope = copy.deepcopy(self.state)
        del malformed_scope["allowed_research_scope"]["strategy_mutation"]
        self._reseal_state(malformed_scope)
        with self.assertRaises(DiscoveryError) as structure_invalid:
            create_trigger(
                "manual_request",
                EVENT_REF,
                malformed_scope,
                self.constitution,
                self.source_policy,
                CREATED_AT,
            )
        self.assertEqual(
            structure_invalid.exception.reason_code, "state_structure_invalid"
        )

    def test_a_prepare_rejects_state_content_tamper_before_side_effects(self):
        trigger = self._trigger()
        mutations = {
            "datasets": lambda state: state["datasets"][0].update(
                {"dataset_id": "tampered-dataset"}
            ),
            "evidence": lambda state: state["unresolved_research_questions"][0][
                "evidence"
            ].append("research/evidence/other.json"),
            "scope": lambda state: state["allowed_research_scope"].update(
                {"read_only_analysis": False}
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                tampered = copy.deepcopy(self.state)
                mutate(tampered)
                write_json(
                    self.repo / "research/director/current-research-state.json",
                    tampered,
                )
                registry = self.registry.with_name(f"state-{label}.sqlite")
                with self.assertRaises(DiscoveryError) as raised:
                    prepare_run(self.repo, trigger, registry)
                self.assertEqual(
                    raised.exception.reason_code, "state_fingerprint_conflict"
                )
                self.assertFalse(registry.exists())
                self.assertFalse((self.repo / "research/discovery/runs").exists())
                self._write_bound_contracts()

    def test_a_constitution_and_source_policy_structures_are_frozen(self):
        invalid_constitution = copy.deepcopy(self.constitution)
        del invalid_constitution["approved_version_immutable"]
        with self.assertRaises(DiscoveryError) as constitution_invalid:
            create_trigger(
                "manual_request",
                EVENT_REF,
                self.state,
                invalid_constitution,
                self.source_policy,
                CREATED_AT,
            )
        self.assertEqual(
            constitution_invalid.exception.reason_code, "constitution_invalid"
        )

        policy_tampers = []
        wrong_class = copy.deepcopy(self.source_policy)
        wrong_class["classes"]["A"].append("unapproved_authority")
        policy_tampers.append(wrong_class)
        missing_forbidden = copy.deepcopy(self.source_policy)
        missing_forbidden["forbidden_inputs"].remove("validation_result")
        policy_tampers.append(missing_forbidden)
        copyright_relaxed = copy.deepcopy(self.source_policy)
        copyright_relaxed["store_full_copyrighted_source"] = True
        policy_tampers.append(copyright_relaxed)

        for policy in policy_tampers:
            with self.subTest(policy=policy):
                with self.assertRaises(DiscoveryError) as policy_invalid:
                    create_trigger(
                        "manual_request",
                        EVENT_REF,
                        self.state,
                        self.constitution,
                        policy,
                        CREATED_AT,
                    )
                self.assertEqual(
                    policy_invalid.exception.reason_code, "source_policy_invalid"
                )

        trigger = self._trigger()
        same_version_tamper = copy.deepcopy(self.source_policy)
        same_version_tamper["pass_requirement"] = "class_a_only"
        write_json(
            self.repo / "research/discovery/policy/source-policy.yaml",
            same_version_tamper,
        )
        with self.assertRaises(DiscoveryError) as bound_policy_invalid:
            prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(
            bound_policy_invalid.exception.reason_code, "source_policy_invalid"
        )
        self.assertFalse(self.registry.exists())

    def test_a_trigger_fingerprint_commits_policy_and_forbidden_inputs(self):
        first = self._trigger()
        later = create_trigger(
            "manual_request",
            EVENT_REF,
            self.state,
            self.constitution,
            self.source_policy,
            "2026-07-14T01:00:00+00:00",
        )
        self.assertEqual(
            first["trigger_fingerprint"], later["trigger_fingerprint"]
        )

        same_version_tamper = copy.deepcopy(self.source_policy)
        same_version_tamper["store_full_copyrighted_source"] = True
        self.assertNotEqual(
            trigger_module._trigger_fingerprint(first, same_version_tamper),
            first["trigger_fingerprint"],
        )
        forbidden_parts = trigger_module._forbidden_path_parts(self.source_policy)
        self.assertTrue(
            {"validation", "holdout", "private", "secret", "live", "unapproved"}
            .issubset(forbidden_parts)
        )

    def test_b_reparse_helper_detects_symlink_and_windows_attribute(self):
        regular = self.repo / "research/evidence/temporal-comparison.json"
        self.assertFalse(trigger_module._is_reparse_point(regular))

        symlink_stat = mock.Mock()
        symlink_stat.st_mode = stat.S_IFLNK
        symlink_stat.st_file_attributes = 0
        with mock.patch.object(Path, "lstat", return_value=symlink_stat):
            self.assertTrue(trigger_module._is_reparse_point(regular))

        windows_reparse_stat = mock.Mock()
        windows_reparse_stat.st_mode = stat.S_IFREG
        windows_reparse_stat.st_file_attributes = getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
        )
        with mock.patch.object(Path, "lstat", return_value=windows_reparse_stat):
            self.assertTrue(trigger_module._is_reparse_point(regular))

    def test_b_source_gate_rejects_reparse_and_resolved_forbidden_aliases(self):
        relative_alias = "research/evidence/alias.json"
        alias = self.repo / relative_alias
        alias.write_text("alias placeholder\n", encoding="utf-8")
        forbidden_parts = trigger_module._forbidden_path_parts(self.source_policy)
        alias_lexical = Path(os.path.abspath(alias))

        with mock.patch.object(
            trigger_module,
            "_is_reparse_point",
            side_effect=lambda path: Path(os.path.abspath(path)) == alias_lexical,
        ):
            with self.assertRaises(DiscoveryError) as mocked_reparse:
                trigger_module._safe_repo_source(
                    self.repo, relative_alias, forbidden_parts
                )
        self.assertEqual(
            mocked_reparse.exception.reason_code, "source_reparse_forbidden"
        )

        alias.unlink()
        validation_target = self.repo / "reports/Validation/result.json"
        validation_target.parent.mkdir(parents=True, exist_ok=True)
        validation_target.write_text("validation result\n", encoding="utf-8")
        symlink_created = False
        try:
            os.symlink(validation_target, alias)
            symlink_created = True
        except OSError:
            pass
        if symlink_created:
            try:
                with self.assertRaises(DiscoveryError) as actual_reparse:
                    trigger_module._safe_repo_source(
                        self.repo, relative_alias, forbidden_parts
                    )
                self.assertEqual(
                    actual_reparse.exception.reason_code,
                    "source_reparse_forbidden",
                )
                with mock.patch.object(
                    trigger_module, "_assert_no_reparse_components"
                ):
                    with self.assertRaises(DiscoveryError) as resolved_forbidden:
                        trigger_module._safe_repo_source(
                            self.repo, relative_alias, forbidden_parts
                        )
                self.assertEqual(
                    resolved_forbidden.exception.reason_code, "source_forbidden"
                )
            finally:
                alias.unlink()

    def test_b_governed_runs_rejects_reparse_components(self):
        trigger = self._trigger()
        result = trigger_module._expected_result(trigger)
        run_path = Path(result["run_path"])
        inbox = Path(result["researcher_inbox"])
        runs_root = self.repo / "research/discovery/runs"
        runs_root.parent.mkdir(parents=True, exist_ok=True)
        runs_lexical = Path(os.path.abspath(runs_root))

        with mock.patch.object(
            trigger_module,
            "_is_reparse_point",
            side_effect=lambda path: Path(os.path.abspath(path)) == runs_lexical,
        ):
            with self.assertRaises(DiscoveryError) as mocked_reparse:
                trigger_module._validate_run_paths(
                    self.repo, run_path, inbox
                )
        self.assertEqual(
            mocked_reparse.exception.reason_code, "run_reparse_forbidden"
        )

        outside = Path(self.temporary_directory.name) / "outside-runs"
        outside.mkdir()
        symlink_created = False
        try:
            os.symlink(outside, runs_root, target_is_directory=True)
            symlink_created = True
        except OSError:
            pass
        if symlink_created:
            try:
                with self.assertRaises(DiscoveryError) as actual_reparse:
                    trigger_module._validate_run_paths(
                        self.repo, run_path, inbox
                    )
                self.assertEqual(
                    actual_reparse.exception.reason_code, "run_reparse_forbidden"
                )
            finally:
                runs_root.unlink()

    def test_b_temp_inbox_rejects_reparse_components(self):
        trigger = self._trigger()
        result = trigger_module._expected_result(trigger)
        run_path = Path(result["run_path"])
        inbox = Path(result["researcher_inbox"])
        controlled_run_root = inbox.parent
        controlled_run_lexical = Path(os.path.abspath(controlled_run_root))

        with mock.patch.object(
            trigger_module,
            "_is_reparse_point",
            side_effect=lambda path: Path(os.path.abspath(path))
            == controlled_run_lexical,
        ):
            with self.assertRaises(DiscoveryError) as mocked_reparse:
                trigger_module._validate_run_paths(
                    self.repo, run_path, inbox
                )
        self.assertEqual(
            mocked_reparse.exception.reason_code, "temp_reparse_forbidden"
        )

        controlled_run_root.parent.mkdir(parents=True, exist_ok=True)
        outside = Path(self.temporary_directory.name) / "outside-inbox"
        outside.mkdir()
        symlink_created = False
        try:
            os.symlink(outside, controlled_run_root, target_is_directory=True)
            symlink_created = True
        except OSError:
            pass
        if symlink_created:
            try:
                with self.assertRaises(DiscoveryError) as actual_reparse:
                    trigger_module._validate_run_paths(
                        self.repo, run_path, inbox
                    )
                self.assertEqual(
                    actual_reparse.exception.reason_code, "temp_reparse_forbidden"
                )
            finally:
                controlled_run_root.unlink()

    def test_c_prompt_and_schema_preflight_fail_before_registry_or_directories(self):
        trigger = self._trigger()
        prompt_path = self.repo / "research/discovery/prompts/researcher.md"
        idea_schema_path = (
            self.repo / "research/discovery/schemas/research-idea.schema.json"
        )
        original_prompt = prompt_path.read_text(encoding="utf-8")
        original_schema = idea_schema_path.read_text(encoding="utf-8")

        cases = []
        cases.append(
            (
                "researcher_prompt_missing",
                lambda: prompt_path.unlink(),
                lambda: prompt_path.write_text(original_prompt, encoding="utf-8"),
            )
        )
        cases.append(
            (
                "researcher_prompt_invalid",
                lambda: prompt_path.write_text(
                    original_prompt.replace(
                        "Do not download a market dataset.",
                        "A market dataset may be downloaded.",
                    ),
                    encoding="utf-8",
                ),
                lambda: prompt_path.write_text(original_prompt, encoding="utf-8"),
            )
        )
        cases.append(
            (
                "idea_schema_missing",
                lambda: idea_schema_path.unlink(),
                lambda: idea_schema_path.write_text(
                    original_schema, encoding="utf-8"
                ),
            )
        )

        tampered_schema = json.loads(original_schema)
        tampered_schema["properties"]["schema_version"]["const"] = (
            "research-idea-v999"
        )
        cases.append(
            (
                "idea_schema_invalid",
                lambda: write_json(idea_schema_path, tampered_schema),
                lambda: idea_schema_path.write_text(
                    original_schema, encoding="utf-8"
                ),
            )
        )

        for reason_code, mutate, restore in cases:
            with self.subTest(reason_code=reason_code):
                mutate()
                try:
                    with mock.patch.object(
                        trigger_module,
                        "open_director_registry",
                        side_effect=AssertionError("registry opened before preflight"),
                    ):
                        with self.assertRaises(DiscoveryError) as raised:
                            prepare_run(self.repo, trigger, self.registry)
                    self.assertEqual(raised.exception.reason_code, reason_code)
                    self.assertFalse(self.registry.exists())
                    self._assert_no_new_run_residue(trigger, self.registry)
                finally:
                    restore()

    def test_c_missing_source_preflight_does_not_open_registry_or_create_paths(self):
        trigger = self._trigger()
        (self.repo / "research/evidence/temporal-comparison.json").unlink()
        with mock.patch.object(
            trigger_module,
            "open_director_registry",
            side_effect=AssertionError("registry opened before preflight"),
        ):
            with self.assertRaises(DiscoveryError) as raised:
                prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(raised.exception.reason_code, "source_missing")
        self.assertFalse(self.registry.exists())
        self._assert_no_new_run_residue(trigger, self.registry)

    def test_c_new_run_rejects_preexisting_final_or_nonempty_temp_inbox(self):
        trigger = self._trigger()
        _, final_run, inbox = self._run_locations(trigger)
        final_run.mkdir(parents=True)
        with self.assertRaises(DiscoveryError) as final_conflict:
            prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(final_conflict.exception.reason_code, "run_path_conflict")
        self.assertEqual(list(final_run.iterdir()), [])
        self._assert_discovery_registry_empty(self.registry)

        final_run.rmdir()
        inbox.mkdir(parents=True)
        untrusted = inbox / "untrusted.json"
        untrusted.write_text('{"untrusted":true}\n', encoding="utf-8")
        second_registry = self.registry.with_name("nonempty-inbox.sqlite")
        with self.assertRaises(DiscoveryError) as inbox_conflict:
            prepare_run(self.repo, trigger, second_registry)
        self.assertEqual(
            inbox_conflict.exception.reason_code, "temp_inbox_not_empty"
        )
        self.assertTrue(untrusted.is_file())
        self.assertFalse(second_registry.exists())

    def test_c_existing_run_requires_exact_artifacts_and_empty_inbox(self):
        trigger = self._trigger()
        result = prepare_run(self.repo, trigger, self.registry)
        run_path = self.repo / result["run_path"]
        inbox = Path(result["researcher_inbox"])

        rogue = run_path / "rogue.json"
        rogue.write_text('{"rogue":true}\n', encoding="utf-8")
        with self.assertRaises(DiscoveryError) as rogue_conflict:
            prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(
            rogue_conflict.exception.reason_code, "run_artifact_conflict"
        )
        self.assertTrue(rogue.is_file())
        rogue.unlink()

        untrusted = inbox / "untrusted.json"
        untrusted.write_text('{"untrusted":true}\n', encoding="utf-8")
        with self.assertRaises(DiscoveryError) as inbox_conflict:
            prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(
            inbox_conflict.exception.reason_code, "temp_inbox_not_empty"
        )
        self.assertTrue(untrusted.is_file())
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_runs"
                ).fetchone()[0],
                1,
            )

    def test_c_faults_rollback_registry_and_remove_only_new_paths(self):
        faults = ("packet", "rename", "insert", "commit")
        for fault in faults:
            with self.subTest(fault=fault):
                trigger = create_trigger(
                    "manual_request",
                    f"{EVENT_REF}-{fault}",
                    self.state,
                    self.constitution,
                    self.source_policy,
                    CREATED_AT,
                )
                registry = self.registry.with_name(f"fault-{fault}.sqlite")
                _, _, inbox = self._run_locations(trigger)
                self.addCleanup(
                    lambda path=inbox.parent: shutil.rmtree(
                        path, ignore_errors=True
                    )
                )
                preexisting_inbox = fault == "commit"
                if preexisting_inbox:
                    inbox.mkdir(parents=True)

                packet_patch = contextlib.nullcontext()
                publish_patch = contextlib.nullcontext()
                registry_patch = contextlib.nullcontext()
                expected_exception: type[BaseException]
                expected_message: str
                if fault == "packet":
                    packet_patch = mock.patch.object(
                        trigger_module,
                        "_write_packet_file",
                        side_effect=OSError("injected packet write failure"),
                    )
                    expected_exception = OSError
                    expected_message = "injected packet write failure"
                elif fault == "rename":
                    publish_patch = mock.patch.object(
                        trigger_module,
                        "_publish_run_directory",
                        side_effect=OSError("injected rename failure"),
                    )
                    expected_exception = OSError
                    expected_message = "injected rename failure"
                else:
                    registry_patch = mock.patch.object(
                        trigger_module,
                        "open_director_registry",
                        side_effect=lambda path, selected=fault: FaultConnection(
                            open_director_registry(path), selected
                        ),
                    )
                    expected_exception = (
                        sqlite3.OperationalError if fault == "insert" else OSError
                    )
                    expected_message = f"injected {fault} failure"

                with packet_patch, publish_patch, registry_patch:
                    with self.assertRaisesRegex(
                        expected_exception, expected_message
                    ):
                        prepare_run(self.repo, trigger, registry)

                self._assert_no_new_run_residue(
                    trigger,
                    registry,
                    preexisting_inbox=preexisting_inbox,
                )

    def test_d_existing_registry_row_and_artifacts_must_match_completely(self):
        trigger = self._trigger()
        result = prepare_run(self.repo, trigger, self.registry)
        stored_trigger = json.loads(
            (self.repo / result["run_path"] / "trigger.json").read_text(
                encoding="utf-8"
            )
        )

        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.row_factory = sqlite3.Row
            original = dict(
                connection.execute(
                    "SELECT run_id, trigger_fingerprint, status, state_fingerprint, "
                    "payload_json, created_at FROM research_discovery_runs"
                ).fetchone()
            )

        mutations = {
            "run_id": "discovery-run-conflicting",
            "status": "completed",
            "state_fingerprint": "9" * 64,
            "payload_json": json.dumps({**result, "status": "completed"}),
            "created_at": "2026-07-14T02:00:00+00:00",
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                    connection.execute(
                        f'UPDATE research_discovery_runs SET "{field}"=?',
                        (value,),
                    )
                    connection.commit()
                with self.assertRaises(DiscoveryError) as conflict:
                    prepare_run(self.repo, trigger, self.registry)
                self.assertEqual(
                    conflict.exception.reason_code, "registry_run_conflict"
                )
                with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                    connection.execute(
                        "UPDATE research_discovery_runs SET "
                        "run_id=?, trigger_fingerprint=?, status=?, state_fingerprint=?, "
                        "payload_json=?, created_at=?",
                        tuple(original[key] for key in (
                            "run_id",
                            "trigger_fingerprint",
                            "status",
                            "state_fingerprint",
                            "payload_json",
                            "created_at",
                        )),
                    )
                    connection.commit()

        later_trigger = create_trigger(
            "manual_request",
            EVENT_REF,
            self.state,
            self.constitution,
            self.source_policy,
            "2026-07-14T03:00:00+00:00",
        )
        self.assertEqual(prepare_run(self.repo, later_trigger, self.registry), result)
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            row = connection.execute(
                "SELECT created_at, COUNT(*) FROM research_discovery_runs"
            ).fetchone()
        self.assertEqual(row, (stored_trigger["created_at"], 1))

    def test_d_two_independent_processes_replay_idempotently(self):
        expected_python = ROOT / ".venv-freqtrade/Scripts/python.exe"
        self.assertEqual(
            Path(sys.executable).resolve(), expected_python.resolve()
        )
        first = self._run_cli_process(self.registry)
        second = self._run_cli_process(self.registry)
        self.assertNotEqual(first[0], second[0])
        for _, returncode, _, stderr in (first, second):
            self.assertEqual(returncode, 0, stderr)
            self.assertEqual(stderr, "")
        first_payload = json.loads(first[2])
        second_payload = json.loads(second[2])
        self.assertEqual(first_payload, second_payload)
        self.addCleanup(
            lambda path=Path(first_payload["run_id"]): shutil.rmtree(
                Path(tempfile.gettempdir())
                / "freqtrade-research-discovery"
                / path,
                ignore_errors=True,
            )
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_runs"
                ).fetchone()[0],
                1,
            )

    def test_d_concurrent_processes_create_one_atomic_run(self):
        event_ref = f"{EVENT_REF}-concurrent"
        command = self._cli_command(self.registry, event_ref=event_ref)
        processes = [
            subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            for _ in range(2)
        ]
        results = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            results.append((process.pid, process.returncode, stdout, stderr))
        self.assertNotEqual(results[0][0], results[1][0])
        for _, returncode, _, stderr in results:
            self.assertEqual(returncode, 0, stderr)
            self.assertEqual(stderr, "")
        payloads = [json.loads(item[2]) for item in results]
        self.assertEqual(payloads[0], payloads[1])

        run_id = payloads[0]["run_id"]
        self.addCleanup(
            lambda: shutil.rmtree(
                Path(tempfile.gettempdir())
                / "freqtrade-research-discovery"
                / run_id,
                ignore_errors=True,
            )
        )
        runs_root = self.repo / "research/discovery/runs"
        self.assertEqual([path.name for path in runs_root.iterdir()], [run_id])
        self.assertFalse(
            any(".staging-" in path.name for path in runs_root.iterdir())
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_runs"
                ).fetchone()[0],
                1,
            )
            for table in (
                "research_discovery_ideas",
                "research_discovery_critiques",
                "research_discovery_shortlists",
                "research_discovery_approvals",
                "research_discovery_handoffs",
                "research_discovery_events",
            ):
                self.assertEqual(
                    connection.execute(
                        f'SELECT COUNT(*) FROM "{table}"'
                    ).fetchone()[0],
                    0,
                )

    def test_d_cli_failures_are_single_line_sanitized_json(self):
        unsupported = self._run_cli_process(
            self.registry.with_name("unsupported.sqlite"),
            event_type="timer",
        )
        self._assert_cli_error(
            unsupported[1], unsupported[2], unsupported[3], "unsupported_trigger"
        )

        missing = self._run_cli_process(
            self.registry.with_name("missing.sqlite"),
            state="research/director/secret-state.json",
        )
        self._assert_cli_error(
            missing[1], missing[2], missing[3], "input_load_failed"
        )
        self.assertNotIn("secret", missing[3].lower())

        tampered = copy.deepcopy(self.state)
        tampered["TOP-SECRET-MARKER"] = "must not leak"
        tampered_path = self.repo / "research/director/tampered-state.json"
        write_json(tampered_path, tampered)
        tamper = self._run_cli_process(
            self.registry.with_name("tampered.sqlite"),
            state="research/director/tampered-state.json",
        )
        self._assert_cli_error(
            tamper[1], tamper[2], tamper[3], "state_fingerprint_conflict"
        )

    def test_create_trigger_is_deterministic_and_fail_closed(self):
        trigger = self._trigger()
        self.assertEqual(trigger["schema_version"], "research-trigger-v1")
        self.assertEqual(len(trigger["trigger_fingerprint"]), 64)
        self.assertEqual(trigger, self._trigger())

        with self.assertRaises(DiscoveryError) as unsupported:
            create_trigger(
                event_type="timer",
                event_ref=EVENT_REF,
                state=self.state,
                constitution=self.constitution,
                source_policy=self.source_policy,
                created_at=CREATED_AT,
            )
        self.assertEqual(unsupported.exception.reason_code, "unsupported_trigger")

        conflicted = {**self.state, "state_conflicts": ["registry_mismatch"]}
        with self.assertRaises(DiscoveryError) as conflict:
            create_trigger(
                event_type="manual_request",
                event_ref=EVENT_REF,
                state=conflicted,
                constitution=self.constitution,
                source_policy=self.source_policy,
                created_at=CREATED_AT,
            )
        self.assertEqual(conflict.exception.reason_code, "state_conflict")

    def test_prepare_run_is_idempotent_and_has_zero_agent_side_effects(self):
        trigger = self._trigger()
        first = prepare_run(self.repo, trigger, self.registry)
        run_path = self.repo / first["run_path"]
        trigger_bytes = (run_path / "trigger.json").read_bytes()
        packet_bytes = (run_path / "researcher-task.md").read_bytes()

        second = prepare_run(self.repo, trigger, self.registry)
        later_trigger = create_trigger(
            event_type="manual_request",
            event_ref=EVENT_REF,
            state=self.state,
            constitution=self.constitution,
            source_policy=self.source_policy,
            created_at="2026-07-14T00:05:00+00:00",
        )
        self.assertEqual(
            later_trigger["trigger_fingerprint"], trigger["trigger_fingerprint"]
        )
        third = prepare_run(self.repo, later_trigger, self.registry)

        self.assertEqual(first, second)
        self.assertEqual(first, third)
        self.assertEqual(first["run_id"], second["run_id"])
        self.assertTrue((run_path / "trigger.json").is_file())
        self.assertTrue((run_path / "researcher-task.md").is_file())
        self.assertEqual((run_path / "trigger.json").read_bytes(), trigger_bytes)
        self.assertEqual((run_path / "researcher-task.md").read_bytes(), packet_bytes)
        self.assertEqual(
            sorted(path.name for path in run_path.iterdir()),
            ["researcher-task.md", "trigger.json"],
        )
        self.assertEqual(
            len(list((self.repo / "research/discovery/runs").iterdir())), 1
        )

        expected_inbox = (
            Path(tempfile.gettempdir())
            / "freqtrade-research-discovery"
            / first["run_id"]
            / "researcher"
        ).resolve()
        actual_inbox = Path(first["researcher_inbox"]).resolve()
        self.assertEqual(actual_inbox, expected_inbox)
        self.assertFalse(actual_inbox.is_relative_to(self.repo.resolve()))
        self.assertTrue(actual_inbox.is_dir())
        self.assertEqual(list(actual_inbox.iterdir()), [])

        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_runs"
                ).fetchone()[0],
                1,
            )
            for table in (
                "research_discovery_ideas",
                "research_discovery_critiques",
                "research_discovery_shortlists",
                "research_discovery_approvals",
                "research_discovery_handoffs",
                "research_discovery_events",
            ):
                self.assertEqual(
                    connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                    0,
                    table,
                )

    def test_packet_lists_only_allowed_sources_and_fixed_boundaries(self):
        trigger = self._trigger()
        result = prepare_run(self.repo, trigger, self.registry)
        packet = (
            self.repo / result["run_path"] / "researcher-task.md"
        ).read_text(encoding="utf-8")

        for relative in sorted(self.allowed_paths):
            self.assertIn(f"`{relative}`", packet)
        self.assertIn("`research/director/current-research-state.json`", packet)
        self.assertIn("`research/governance/research-constitution.yaml`", packet)
        self.assertIn("`research/discovery/policy/source-policy.yaml`", packet)
        self.assertIn("`research/discovery/schemas/research-idea.schema.json`", packet)
        self.assertIn(str(Path(result["researcher_inbox"]).resolve()), packet)
        self.assertIn(trigger["research_state_fingerprint"], packet)
        self.assertIn(trigger["constitution_fingerprint"], packet)
        self.assertIn(trigger["trigger_fingerprint"], packet)
        self.assertIn("Binance USD-M Futures", packet)
        self.assertIn("isolated margin", packet)
        self.assertIn("`1h` primary", packet)
        self.assertIn("`4h` informative", packet)
        self.assertIn("Do not download market data", packet)
        self.assertIn("data readiness", packet)

        for forbidden in (
            "futures-validation-btc",
            "reports/Validation/validation-result.json",
            "strategies/RegimeAwareV6.py",
        ):
            self.assertNotIn(forbidden, packet)
        for boundary in (
            "Validation",
            "Holdout",
            "secrets",
            "private APIs",
            "live accounts",
            "strategy mutation",
            "Candidate",
            "execution",
        ):
            self.assertIn(boundary, packet)

        manual_inbox = (
            Path(tempfile.gettempdir())
            / "freqtrade-research-discovery"
            / "manual-render"
            / "researcher"
        )
        self.addCleanup(lambda: shutil.rmtree(manual_inbox.parent, ignore_errors=True))
        rendered = render_researcher_packet(
            self.repo,
            Path("research/discovery/runs/manual-render"),
            trigger,
            manual_inbox,
        )
        self.assertEqual(
            rendered,
            (
                self.repo
                / "research/discovery/runs/manual-render/researcher-task.md"
            ).read_text(encoding="utf-8"),
        )

    def test_prepare_run_rejects_stale_conflicting_missing_and_tampered_inputs(self):
        cases: list[tuple[str, str, object]] = []

        stale_state = copy.deepcopy(self.state)
        stale_state["unresolved_research_questions"][0]["question"] = (
            "Which changed mechanism remains unresolved?"
        )
        self._reseal_state(stale_state)
        cases.append(("stale_trigger", "state", stale_state))

        conflicting_constitution = copy.deepcopy(self.constitution)
        conflicting_constitution["approved_version"] = 2
        cases.append(
            ("constitution_conflict", "constitution", conflicting_constitution)
        )

        conflicting_policy = copy.deepcopy(self.source_policy)
        conflicting_policy["schema_version"] = "research-source-policy-v2"
        cases.append(("source_policy_conflict", "source_policy", conflicting_policy))

        for expected_reason, target, replacement in cases:
            with self.subTest(reason=expected_reason):
                self._write_bound_contracts()
                path = {
                    "state": self.repo
                    / "research/director/current-research-state.json",
                    "constitution": self.repo
                    / "research/governance/research-constitution.yaml",
                    "source_policy": self.repo
                    / "research/discovery/policy/source-policy.yaml",
                }[target]
                write_json(path, replacement)
                case_registry = self.registry.with_name(f"{expected_reason}.sqlite")
                with self.assertRaises(DiscoveryError) as raised:
                    prepare_run(self.repo, self._trigger(), case_registry)
                self.assertEqual(raised.exception.reason_code, expected_reason)
                self.assertFalse(
                    (self.repo / "research/discovery/runs").exists(),
                    expected_reason,
                )
                self.assertFalse(case_registry.exists(), expected_reason)

        self._write_bound_contracts()
        missing_state = self.repo / "research/director/current-research-state.json"
        missing_state.unlink()
        with self.assertRaises(DiscoveryError) as missing:
            prepare_run(self.repo, self._trigger(), self.registry)
        self.assertEqual(missing.exception.reason_code, "state_missing")
        self.assertFalse(self.registry.exists())

        self._write_bound_contracts()
        tampered = self._trigger()
        tampered["event_ref"] = "tampered"
        with self.assertRaises(DiscoveryError) as artifact:
            prepare_run(self.repo, tampered, self.registry)
        self.assertEqual(
            artifact.exception.reason_code, "trigger_fingerprint_conflict"
        )
        self.assertFalse(self.registry.exists())

    def test_prepare_run_fails_before_writes_when_allowlisted_source_is_missing(self):
        (self.repo / "research/evidence/temporal-comparison.json").unlink()

        with self.assertRaises(DiscoveryError) as raised:
            prepare_run(self.repo, self._trigger(), self.registry)

        self.assertEqual(raised.exception.reason_code, "source_missing")
        self.assertFalse(self.registry.exists())
        self.assertFalse((self.repo / "research/discovery/runs").exists())

    def test_cli_prints_only_the_public_run_fields(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(
                [
                    "--event-type",
                    "manual_request",
                    "--event-ref",
                    EVENT_REF,
                    "--state",
                    "research/director/current-research-state.json",
                    "--constitution",
                    "research/governance/research-constitution.yaml",
                    "--source-policy",
                    "research/discovery/policy/source-policy.yaml",
                    "--director-registry",
                    str(self.registry),
                    "--repo-root",
                    str(self.repo),
                ]
            )

        self.assertEqual(result, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(
            set(payload),
            {"run_id", "run_path", "status", "trigger_fingerprint"},
        )

    def test_prompt_contracts_are_provider_neutral_and_non_executing(self):
        researcher = (
            self.repo / "research/discovery/prompts/researcher.md"
        ).read_text(encoding="utf-8")
        critic = (self.repo / "research/discovery/prompts/critic.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Generate 6-10 distinct `research-idea-v1`", researcher)
        self.assertIn("at most two ideas per `strategy_family`", researcher)
        self.assertIn("Do not download a market dataset", researcher)
        self.assertIn("Do not promise return, win rate, or profitability", researcher)
        self.assertIn("`research-critique-v1`", critic)
        self.assertIn("`pass`, `revise`, or `reject`", critic)
        self.assertIn("A Class C-only idea cannot pass", critic)
        self.assertIn("data_readiness_required", critic)
        self.assertNotIn("OPENAI_API_KEY", researcher + critic)
        self.assertNotIn("ANTHROPIC_API_KEY", researcher + critic)
        self.assertNotIn("api.openai.com", researcher + critic)


if __name__ == "__main__":
    unittest.main()
