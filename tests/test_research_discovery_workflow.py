import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from collections import Counter


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

try:  # Task 5 TDD: keep the pre-implementation suite as an assertion failure.
    import research_discovery_review as review_module  # noqa: E402
except ModuleNotFoundError:
    review_module = None

try:  # Task 6 TDD: keep the pre-implementation suite as an assertion failure.
    import research_discovery_route as route_module  # noqa: E402
except ModuleNotFoundError:
    route_module = None


CREATED_AT = "2026-07-14T00:00:00+00:00"
EVENT_REF = "human-request-2026-07-14"
ETH_APPROVAL_PATH = (
    "research/governance/approvals/"
    "eth-cross-pair-generalization-v1-approval.json"
)


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


class CommitOperationalErrorConnection:
    def __init__(self, connection: sqlite3.Connection, mode: str):
        self.connection = connection
        self.mode = mode
        self.commit_calls = 0

    def execute(self, sql, parameters=()):
        return self.connection.execute(sql, parameters)

    def commit(self):
        self.commit_calls += 1
        if self.mode == "transient" and self.commit_calls == 1:
            raise sqlite3.OperationalError("database is locked")
        if self.mode == "persistent":
            raise sqlite3.OperationalError("database is locked")
        if self.mode == "nonlock":
            raise sqlite3.OperationalError("injected disk I/O error")
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
            "research/discovery/schemas/research-critique.schema.json",
            "research/discovery/schemas/research-shortlist.schema.json",
            "research/discovery/schemas/research-direction-approval.schema.json",
            "research/discovery/schemas/research-direction-handoff.schema.json",
            "research/discovery/policy/ranking-policy.yaml",
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
            ETH_APPROVAL_PATH,
            "research/runtime/freqtrade-runtime.yaml",
        }
        for relative in self.allowed_paths:
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture: {relative}\n", encoding="utf-8")

        write_json(
            self.repo / ETH_APPROVAL_PATH,
            {
                "schema_version": "cross-pair-generalization-human-approval-v1",
                "approval_status": "approved",
                "approver_type": "human_user",
                "scope": {"pair": "ETH/USDT:USDT"},
            },
        )

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
                "evidence": [ETH_APPROVAL_PATH],
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
                    "agent_visibility": None,
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
        result = trigger_module._expected_result(trigger, self.repo)
        temp_run_root = Path(str(result["researcher_inbox"])).parent
        if temp_run_root.is_dir():
            shutil.rmtree(temp_run_root)
        for parent in (temp_run_root.parent, temp_run_root.parent.parent):
            try:
                parent.rmdir()
            except (FileNotFoundError, OSError):
                pass

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
        result = trigger_module._expected_result(trigger, self.repo)
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

    def _review_api(self):
        self.assertIsNotNone(
            review_module,
            "Task 5 review ingestion module must exist",
        )
        return review_module

    def _route_api(self):
        self.assertIsNotNone(
            route_module,
            "Task 6 direction routing module must exist",
        )
        return route_module

    def _prepare_route_run(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        critiques, _ = self._ingest_fixture_critiques(result, ideas)
        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        return result, ideas, critiques, shortlist

    def _approved_direction_request(self) -> dict[str, object]:
        return json.loads(
            (
                ROOT
                / "tests/fixtures/research-discovery/"
                "human-direction-approved-rank-1.json"
            ).read_text(encoding="utf-8")
        )

    def _prepare_review_run(self) -> dict[str, object]:
        return prepare_run(self.repo, self._trigger(), self.registry)

    def _write_review_drafts(
        self,
        kind: str,
        inbox: Path,
        *,
        ideas: list[dict[str, object]] | None = None,
        transform=None,
    ) -> list[dict[str, object]]:
        inbox.mkdir(parents=True, exist_ok=True)
        for path in inbox.iterdir():
            if path.is_file():
                path.unlink()
        source = ROOT / "tests/fixtures/research-discovery" / kind
        payloads: list[dict[str, object]] = []
        idea_by_id = {
            str(item["idea_id"]): item for item in (ideas or [])
        }
        for index, path in enumerate(sorted(source.glob("*.json"))):
            payload = json.loads(path.read_text(encoding="utf-8"))
            if kind == "ideas":
                payload["research_state_fingerprint"] = self.state[
                    "state_fingerprint"
                ]
            else:
                idea = idea_by_id[str(payload["idea_id"])]
                payload["idea_semantic_fingerprint"] = idea[
                    "semantic_fingerprint"
                ]
            if transform is not None:
                transform(index, payload)
            write_json(inbox / path.name, payload)
            payloads.append(payload)
        return payloads

    def _ingest_fixture_ideas(
        self,
        transform=None,
    ) -> tuple[dict[str, object], list[dict[str, object]], Path]:
        api = self._review_api()
        result = self._prepare_review_run()
        inbox = Path(str(result["researcher_inbox"]))
        self._write_review_drafts("ideas", inbox, transform=transform)
        ideas = api.ingest_ideas(
            self.repo, str(result["run_id"]), inbox, self.registry
        )
        return result, ideas, inbox

    def _ingest_fixture_critiques(
        self,
        result: dict[str, object],
        ideas: list[dict[str, object]],
        transform=None,
    ) -> tuple[list[dict[str, object]], Path]:
        api = self._review_api()
        inbox = Path(str(result["researcher_inbox"])).parent / "critic"
        self._write_review_drafts(
            "critiques",
            inbox,
            ideas=ideas,
            transform=transform,
        )
        critiques = api.ingest_critiques(
            self.repo, str(result["run_id"]), inbox, self.registry
        )
        return critiques, inbox

    def _revision_draft(
        self, idea: dict[str, object]
    ) -> dict[str, object]:
        payload = copy.deepcopy(idea)
        payload.pop("semantic_fingerprint", None)
        payload["idea_version"] = 2
        payload["falsifiable_hypothesis"] = (
            str(payload["falsifiable_hypothesis"]) + " Revision 2."
        )
        return payload

    def _stored_critique(
        self, run_id: str, idea_id: str
    ) -> dict[str, object]:
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            row = connection.execute(
                "SELECT payload_json FROM research_discovery_critiques "
                "WHERE run_id=? AND idea_key LIKE ? ORDER BY rowid DESC LIMIT 1",
                (run_id, f"{run_id}:{idea_id}:v%"),
            ).fetchone()
        self.assertIsNotNone(row)
        return json.loads(row[0])

    def _replace_stored_critique(
        self, result: dict[str, object], payload: dict[str, object]
    ) -> dict[str, object]:
        updated = copy.deepcopy(payload)
        updated.pop("critic_fingerprint", None)
        updated["critic_fingerprint"] = review_module.artifact_fingerprint(
            updated, "critic_fingerprint"
        )
        payload_json = json.dumps(updated, ensure_ascii=False, sort_keys=True)
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "UPDATE research_discovery_critiques SET verdict=?, "
                "critic_fingerprint=?, payload_json=? WHERE critique_id=?",
                (
                    updated["verdict"],
                    updated["critic_fingerprint"],
                    payload_json,
                    updated["critique_id"],
                ),
            )
            connection.commit()
        write_json(
            self.repo
            / str(result["run_path"])
            / "critiques"
            / f"{updated['critique_id']}.json",
            updated,
        )
        return updated

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
        result = trigger_module._expected_result(trigger, self.repo)
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
        result = trigger_module._expected_result(trigger, self.repo)
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
                        "_open_registry_with_retry",
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
            "_open_registry_with_retry",
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
        with mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            side_effect=AssertionError("registry opened despite pre-existing final"),
        ):
            with self.assertRaises(DiscoveryError) as final_conflict:
                prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(final_conflict.exception.reason_code, "run_path_conflict")
        self.assertEqual(list(final_run.iterdir()), [])
        self.assertFalse(self.registry.exists())

        existing_registry = self.registry.with_name("existing-empty.sqlite")
        with contextlib.closing(open_director_registry(existing_registry)):
            pass
        with self.assertRaises(DiscoveryError) as orphan_conflict:
            prepare_run(self.repo, trigger, existing_registry)
        self.assertEqual(
            orphan_conflict.exception.reason_code, "run_path_conflict"
        )
        self.assertEqual(list(final_run.iterdir()), [])
        self._assert_discovery_registry_empty(existing_registry)

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
                        "_open_registry_with_retry",
                        side_effect=lambda path, _deadline, selected=fault: FaultConnection(
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

    def test_e_helper_failures_preserve_cleanup_ownership(self):
        trigger = self._trigger()
        original_reparse_check = trigger_module._assert_no_reparse_components

        def fail_staging_validation(root, target, reason_code):
            if ".staging-" in Path(target).name:
                raise DiscoveryError(
                    "run_reparse_forbidden", "injected staging validation failure"
                )
            return original_reparse_check(root, target, reason_code)

        staging_registry = self.registry.with_name("staging-helper-fault.sqlite")
        with mock.patch.object(
            trigger_module,
            "_assert_no_reparse_components",
            side_effect=fail_staging_validation,
        ):
            with self.assertRaises(DiscoveryError) as staging_failure:
                prepare_run(self.repo, trigger, staging_registry)
        self.assertEqual(
            staging_failure.exception.reason_code, "run_reparse_forbidden"
        )
        self._assert_no_new_run_residue(trigger, staging_registry)

        _, _, inbox = self._run_locations(trigger)
        self.addCleanup(lambda: shutil.rmtree(inbox.parent, ignore_errors=True))
        original_directory_check = trigger_module._require_plain_directory

        def fail_temp_run_root(path, reason_code):
            if Path(path) == inbox.parent and os.path.lexists(path):
                raise DiscoveryError(
                    "temp_reparse_forbidden", "injected TEMP mkdir validation failure"
                )
            return original_directory_check(path, reason_code)

        temp_registry = self.registry.with_name("temp-helper-fault.sqlite")
        with mock.patch.object(
            trigger_module,
            "_require_plain_directory",
            side_effect=fail_temp_run_root,
        ):
            with self.assertRaises(DiscoveryError) as temp_failure:
                prepare_run(self.repo, trigger, temp_registry)
        self.assertEqual(
            temp_failure.exception.reason_code, "temp_reparse_forbidden"
        )
        self.assertFalse(os.path.lexists(inbox.parent))
        self._assert_no_new_run_residue(trigger, temp_registry)

    def test_e_cleanup_failures_are_aggregated_and_auditable(self):
        trigger = self._trigger()
        _, final_run, _ = self._run_locations(trigger)

        def fault_connection(registry: Path):
            return FaultConnection(open_director_registry(registry), "insert")

        rmtree_registry = self.registry.with_name("cleanup-rmtree.sqlite")
        with mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            side_effect=lambda _path, _deadline: fault_connection(rmtree_registry),
        ), mock.patch.object(
            trigger_module.shutil,
            "rmtree",
            side_effect=OSError("injected rmtree cleanup failure"),
        ):
            with self.assertRaises(DiscoveryError) as rmtree_failure:
                prepare_run(self.repo, trigger, rmtree_registry)
        self.assertEqual(
            rmtree_failure.exception.reason_code, "rollback_cleanup_failed"
        )
        self.assertIn("OperationalError", str(rmtree_failure.exception))
        self.assertIn("injected insert failure", str(rmtree_failure.exception))
        self.assertIn("injected rmtree cleanup failure", str(rmtree_failure.exception))
        self.assertTrue(os.path.lexists(final_run))
        shutil.rmtree(final_run)

        unlink_registry = self.registry.with_name("cleanup-unlink.sqlite")
        original_is_reparse = trigger_module._is_reparse_point
        original_unlink = Path.unlink

        def report_final_as_reparse(path):
            if Path(path) == final_run and os.path.lexists(path):
                return True
            return original_is_reparse(Path(path))

        def fail_final_unlink(path, *args, **kwargs):
            if Path(path) == final_run:
                raise OSError("injected unlink cleanup failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            side_effect=lambda _path, _deadline: fault_connection(unlink_registry),
        ), mock.patch.object(
            trigger_module,
            "_is_reparse_point",
            side_effect=report_final_as_reparse,
        ), mock.patch.object(
            Path,
            "unlink",
            autospec=True,
            side_effect=fail_final_unlink,
        ):
            with self.assertRaises(DiscoveryError) as unlink_failure:
                prepare_run(self.repo, trigger, unlink_registry)
        self.assertEqual(
            unlink_failure.exception.reason_code, "rollback_cleanup_failed"
        )
        self.assertIn("injected unlink cleanup failure", str(unlink_failure.exception))
        self.assertTrue(os.path.lexists(final_run))
        shutil.rmtree(final_run)

        class RollbackFaultConnection(FaultConnection):
            def rollback(self):
                raise OSError("injected rollback failure")

        rollback_registry = self.registry.with_name("cleanup-rollback.sqlite")
        with mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            side_effect=lambda _path, _deadline: RollbackFaultConnection(
                open_director_registry(rollback_registry), "insert"
            ),
        ):
            with self.assertRaises(DiscoveryError) as rollback_failure:
                prepare_run(self.repo, trigger, rollback_registry)
        self.assertEqual(
            rollback_failure.exception.reason_code, "rollback_cleanup_failed"
        )
        self.assertIn("injected rollback failure", str(rollback_failure.exception))
        self.assertFalse(os.path.lexists(final_run))

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
            "trigger_fingerprint": "8" * 64,
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
                try:
                    with self.assertRaises(DiscoveryError) as conflict:
                        prepare_run(self.repo, trigger, self.registry)
                    self.assertEqual(
                        conflict.exception.reason_code, "registry_run_conflict"
                    )
                finally:
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

        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "UPDATE research_discovery_runs SET payload_json=?",
                ("{malformed",),
            )
            connection.commit()
        try:
            with self.assertRaises(DiscoveryError) as malformed_payload:
                prepare_run(self.repo, trigger, self.registry)
            self.assertEqual(
                malformed_payload.exception.reason_code,
                "registry_run_conflict",
            )
        finally:
            with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                connection.execute(
                    "UPDATE research_discovery_runs SET payload_json=?",
                    (original["payload_json"],),
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

    def test_d_registry_or_query_rejects_two_matching_rows(self):
        trigger = self._trigger()
        result = prepare_run(self.repo, trigger, self.registry)
        alternate_fingerprint = "8" * 64
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "UPDATE research_discovery_runs SET trigger_fingerprint=? ",
                (alternate_fingerprint,),
            )
            connection.execute(
                "INSERT INTO research_discovery_runs("
                "run_id, trigger_fingerprint, status, state_fingerprint, "
                "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "discovery-run-fingerprint-alias",
                    trigger["trigger_fingerprint"],
                    result["status"],
                    trigger["research_state_fingerprint"],
                    json.dumps(result, sort_keys=True),
                    trigger["created_at"],
                ),
            )
            connection.commit()

        with self.assertRaises(DiscoveryError) as conflict:
            prepare_run(self.repo, trigger, self.registry)
        self.assertEqual(conflict.exception.reason_code, "registry_run_conflict")

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

    def test_g_registry_retry_has_deadline_and_only_retries_lock_errors(self):
        self.assertLessEqual(
            trigger_module.REGISTRY_RETRY_DEADLINE_SECONDS,
            3.0,
        )
        locked_registry = self.registry.with_name("persistently-locked.sqlite")
        with contextlib.closing(open_director_registry(locked_registry)):
            pass
        holder = sqlite3.connect(locked_registry, timeout=0)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            started = trigger_module.time.monotonic()
            with self.assertRaises(DiscoveryError) as locked:
                trigger_module._open_registry_with_retry(
                    locked_registry,
                    started + trigger_module.REGISTRY_RETRY_DEADLINE_SECONDS,
                )
            elapsed = trigger_module.time.monotonic() - started
        finally:
            holder.rollback()
            holder.close()
        self.assertEqual(locked.exception.reason_code, "registry_locked")
        self.assertLess(elapsed, 3.0)

        non_lock = sqlite3.OperationalError("injected disk I/O error")
        with mock.patch.object(
            trigger_module,
            "_open_registry_once",
            side_effect=non_lock,
        ) as opener:
            with self.assertRaisesRegex(
                sqlite3.OperationalError, "injected disk I/O error"
            ):
                trigger_module._open_registry_with_retry(
                    self.registry.with_name("non-lock.sqlite"),
                    trigger_module.time.monotonic()
                    + trigger_module.REGISTRY_RETRY_DEADLINE_SECONDS,
                )
        self.assertEqual(opener.call_count, 1)

    def test_h_transaction_begin_uses_the_shared_registry_deadline(self):
        trigger = create_trigger(
            "manual_request",
            f"{EVENT_REF}-transaction-lock",
            self.state,
            self.constitution,
            self.source_policy,
            CREATED_AT,
        )
        registry = self.registry.with_name("transaction-lock.sqlite")
        _, _, inbox = self._run_locations(trigger)
        self.addCleanup(
            lambda: shutil.rmtree(inbox.parent, ignore_errors=True)
        )
        real_open = trigger_module._open_registry_with_retry
        holders: list[sqlite3.Connection] = []

        def open_then_lock(path, *args):
            connection = real_open(path, *args)
            time_budget_consumption = 0.12
            trigger_module.time.sleep(time_budget_consumption)
            holder = sqlite3.connect(path, timeout=0)
            holder.execute("BEGIN EXCLUSIVE")
            holders.append(holder)
            return connection

        started = trigger_module.time.monotonic()
        try:
            with mock.patch.object(
                trigger_module,
                "REGISTRY_RETRY_DEADLINE_SECONDS",
                0.30,
            ), mock.patch.object(
                trigger_module,
                "_open_registry_with_retry",
                side_effect=open_then_lock,
            ):
                with self.assertRaises(DiscoveryError) as locked:
                    prepare_run(self.repo, trigger, registry)
            elapsed = trigger_module.time.monotonic() - started
        finally:
            for holder in holders:
                holder.rollback()
                holder.close()
        self.assertEqual(locked.exception.reason_code, "registry_locked")
        self.assertLess(elapsed, 0.45)
        self._assert_no_new_run_residue(trigger, registry)

    def test_h_commit_lock_retries_share_deadline_and_cleanup(self):
        def run_case(mode: str):
            trigger = create_trigger(
                "manual_request",
                f"{EVENT_REF}-commit-{mode}",
                self.state,
                self.constitution,
                self.source_policy,
                CREATED_AT,
            )
            registry = self.registry.with_name(f"commit-{mode}.sqlite")
            connection = CommitOperationalErrorConnection(
                open_director_registry(registry), mode
            )
            _, final_run, inbox = self._run_locations(trigger)
            self.addCleanup(
                lambda path=inbox.parent: shutil.rmtree(
                    path, ignore_errors=True
                )
            )
            return trigger, registry, connection, final_run, inbox

        trigger, registry, transient, final_run, transient_inbox = run_case(
            "transient"
        )
        with mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            return_value=transient,
        ):
            result = prepare_run(self.repo, trigger, registry)
        self.assertEqual(transient.commit_calls, 2)
        self.assertTrue((final_run / "trigger.json").is_file())
        with contextlib.closing(sqlite3.connect(registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_runs"
                ).fetchone()[0],
                1,
            )
        self.assertEqual(result["run_id"], final_run.name)
        shutil.rmtree(final_run)
        shutil.rmtree(transient_inbox.parent)

        trigger, registry, persistent, _, _ = run_case("persistent")
        started = trigger_module.time.monotonic()
        with mock.patch.object(
            trigger_module,
            "REGISTRY_RETRY_DEADLINE_SECONDS",
            0.25,
        ), mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            return_value=persistent,
        ):
            with self.assertRaises(DiscoveryError) as locked:
                prepare_run(self.repo, trigger, registry)
        elapsed = trigger_module.time.monotonic() - started
        self.assertEqual(locked.exception.reason_code, "registry_locked")
        self.assertLess(elapsed, 0.45)
        self.assertGreater(persistent.commit_calls, 1)
        self._assert_no_new_run_residue(trigger, registry)

        trigger, registry, nonlock, _, _ = run_case("nonlock")
        with mock.patch.object(
            trigger_module,
            "_open_registry_with_retry",
            return_value=nonlock,
        ):
            with self.assertRaisesRegex(
                sqlite3.OperationalError, "injected disk I/O error"
            ):
                prepare_run(self.repo, trigger, registry)
        self.assertEqual(nonlock.commit_calls, 1)
        self._assert_no_new_run_residue(trigger, registry)

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
            / trigger_module._repo_identity_namespace(self.repo)
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

    def test_f_public_renderer_is_canonical_and_has_zero_write_side_effects(self):
        trigger = self._trigger()
        result, final_run, inbox = self._run_locations(trigger)
        packet = render_researcher_packet(
            self.repo,
            Path(result["run_path"]),
            trigger,
            inbox,
        )
        self.assertIn(trigger["trigger_fingerprint"], packet)
        self.assertFalse(os.path.lexists(final_run))
        self.assertFalse(os.path.lexists(inbox.parent))
        self.assertFalse(self.registry.exists())

        for invalid_run_path in (
            Path("research/discovery/runs/manual-render"),
            Path("research/discovery/runs/discovery-run-0000000000000000"),
        ):
            with self.subTest(run_path=invalid_run_path.as_posix()):
                with self.assertRaises(DiscoveryError) as invalid:
                    render_researcher_packet(
                        self.repo,
                        invalid_run_path,
                        trigger,
                        inbox,
                    )
                self.assertEqual(invalid.exception.reason_code, "run_path_invalid")

        final_run.mkdir(parents=True)
        packet_path = final_run / "researcher-task.md"
        symlink_target = self.repo / "packet-target.md"
        symlink_target.write_text("untrusted packet\n", encoding="utf-8")
        actual_symlink = False
        try:
            os.symlink(symlink_target, packet_path)
            actual_symlink = True
        except OSError:
            packet_path.write_text("untrusted packet\n", encoding="utf-8")

        original_is_reparse = trigger_module._is_reparse_point

        def packet_is_reparse(path):
            if Path(path) == packet_path:
                return True
            return original_is_reparse(Path(path))

        reparse_context = (
            contextlib.nullcontext()
            if actual_symlink
            else mock.patch.object(
                trigger_module,
                "_is_reparse_point",
                side_effect=packet_is_reparse,
            )
        )
        with reparse_context:
            with self.assertRaises(DiscoveryError) as packet_conflict:
                render_researcher_packet(
                    self.repo,
                    Path(result["run_path"]),
                    trigger,
                    inbox,
                )
        self.assertEqual(
            packet_conflict.exception.reason_code, "run_artifact_conflict"
        )
        self.assertFalse(os.path.lexists(inbox.parent))

    def test_dataset_sources_require_scope_approval_and_development_visibility(self):
        def packet_for(
            state: dict[str, object], event_ref: str
        ) -> tuple[dict[str, object], str]:
            self._reseal_state(state)
            write_json(
                self.repo / "research/director/current-research-state.json",
                state,
            )
            trigger = create_trigger(
                "manual_request",
                event_ref,
                state,
                self.constitution,
                self.source_policy,
                CREATED_AT,
            )
            result = trigger_module._expected_result(trigger, self.repo)
            return (
                trigger,
                trigger_module._researcher_packet_text(
                    self.repo,
                    Path(result["run_path"]),
                    trigger,
                    Path(result["researcher_inbox"]),
                ),
            )

        valid = copy.deepcopy(self.state)
        valid_trigger, packet = packet_for(valid, "dataset-auth-valid")
        self.assertIn("futures-dev-btc/manifest.yaml", packet)
        self.assertIn("futures-dev-eth/manifest.yaml", packet)
        self.assertNotIn("futures-validation-btc/manifest.yaml", packet)

        approval_path = self.repo / ETH_APPROVAL_PATH
        original_approval = approval_path.read_text(encoding="utf-8")
        approval_path.write_text(
            '{"approval_status":"rejected","scope":{"pair":"SOL/USDT:USDT"}}\n',
            encoding="utf-8",
        )
        try:
            tampered_trigger, tampered_packet = packet_for(
                copy.deepcopy(self.state), "dataset-auth-valid"
            )
        finally:
            approval_path.write_text(original_approval, encoding="utf-8")
        self.assertEqual(
            tampered_trigger["trigger_fingerprint"],
            valid_trigger["trigger_fingerprint"],
        )
        self.assertEqual(tampered_packet, packet)

        cases = []

        controlled_eth = copy.deepcopy(self.state)
        controlled_eth["datasets"][1]["agent_visibility"] = "controlled"
        cases.append(("additional pair controlled", controlled_eth, "futures-dev-eth"))

        unsealed_eth = copy.deepcopy(self.state)
        unsealed_eth["datasets"][1]["sealed"] = False
        cases.append(("additional pair unsealed", unsealed_eth, "futures-dev-eth"))

        baseline_not_full = copy.deepcopy(self.state)
        baseline_not_full["datasets"][0]["agent_visibility"] = None
        cases.append(("baseline pair not full", baseline_not_full, "futures-dev-btc"))

        no_four_hour = copy.deepcopy(self.state)
        no_four_hour["datasets"][1]["timeframes"] = ["1h"]
        cases.append(("additional pair missing 4h", no_four_hour, "futures-dev-eth"))

        unapproved_pair = copy.deepcopy(self.state)
        unapproved_pair["allowed_research_scope"][
            "human_approved_additional_pairs"
        ] = ["ETH/USDT:USDT", "SOL/USDT:USDT"]
        sol_path = "research/data/snapshots/futures-dev-sol/manifest.yaml"
        sol_source = self.repo / sol_path
        sol_source.parent.mkdir(parents=True, exist_ok=True)
        sol_source.write_text("fixture: sol\n", encoding="utf-8")
        sol_approval = (
            "research/governance/approvals/sol-human-approval.json"
        )
        write_json(
            self.repo / sol_approval,
            {
                "schema_version": "cross-pair-generalization-human-approval-v1",
                "approval_status": "approved",
                "approver_type": "human_user",
                "scope": {"pair": "SOL/USDT:USDT"},
            },
        )
        unapproved_pair["allowed_research_scope"]["evidence"].append(
            sol_approval
        )
        unapproved_pair["datasets"].append(
            {
                "dataset_id": "futures-dev-sol",
                "intended_use": "development",
                "agent_visibility": None,
                "pairs": ["SOL/USDT:USDT"],
                "timeframes": ["1h", "4h"],
                "path": sol_path,
                "sealed": True,
            }
        )
        for index, (label, state, forbidden_source) in enumerate(cases):
            with self.subTest(case=label):
                _, packet = packet_for(state, f"dataset-auth-{index}")
                self.assertNotIn(forbidden_source, packet)
                self.assertNotIn("futures-validation-btc", packet)

        with self.assertRaises(DiscoveryError) as sol_scope:
            packet_for(unapproved_pair, "dataset-auth-sol-self-approval")
        self.assertEqual(sol_scope.exception.reason_code, "state_structure_invalid")

        no_additional_pair = copy.deepcopy(self.state)
        no_additional_pair["allowed_research_scope"][
            "human_approved_additional_pairs"
        ] = []
        with self.assertRaises(DiscoveryError) as additional_missing:
            packet_for(no_additional_pair, "dataset-auth-no-additional-pair")
        self.assertEqual(
            additional_missing.exception.reason_code,
            "state_structure_invalid",
        )

        missing_evidence = copy.deepcopy(self.state)
        missing_evidence["allowed_research_scope"]["evidence"] = []
        with self.assertRaises(DiscoveryError) as evidence_missing:
            packet_for(missing_evidence, "dataset-auth-missing-evidence")
        self.assertEqual(
            evidence_missing.exception.reason_code,
            "state_structure_invalid",
        )

        approval_path.unlink()
        try:
            with self.assertRaises(DiscoveryError) as approval_missing:
                packet_for(
                    copy.deepcopy(self.state),
                    "dataset-auth-missing-approval-file",
                )
        finally:
            approval_path.write_text(original_approval, encoding="utf-8")
        self.assertEqual(approval_missing.exception.reason_code, "source_missing")

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

    def test_review_ingests_six_families_critiques_and_top_three_idempotently(self):
        api = self._review_api()
        result, ideas, ideas_inbox = self._ingest_fixture_ideas()

        self.assertEqual(len(ideas), 6)
        self.assertEqual(
            max(Counter(item["strategy_family"] for item in ideas).values()),
            1,
        )
        idea_paths = sorted(
            (self.repo / result["run_path"] / "ideas").glob("*.json")
        )
        idea_hashes = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in idea_paths
        }
        replay_drafts = self._write_review_drafts("ideas", ideas_inbox)
        for path in sorted(ideas_inbox.glob("*.json"))[1:]:
            path.unlink()
        with self.assertRaises(DiscoveryError) as incomplete_replay:
            api.ingest_ideas(
                self.repo,
                str(result["run_id"]),
                ideas_inbox,
                self.registry,
            )
        self.assertEqual(
            incomplete_replay.exception.reason_code,
            "idea_id_set_mismatch",
        )
        self.assertEqual(len(replay_drafts), 6)
        self._write_review_drafts("ideas", ideas_inbox)
        self.assertEqual(
            api.ingest_ideas(
                self.repo,
                str(result["run_id"]),
                ideas_inbox,
                self.registry,
            ),
            ideas,
        )

        critic_packet = api.render_critic_packet(
            self.repo, str(result["run_id"])
        )
        self.assertIn("Do not edit", critic_packet)
        self.assertIn("system TEMP", critic_packet)
        critiques, critiques_inbox = self._ingest_fixture_critiques(
            result, ideas
        )
        self.assertEqual(
            {item["idea_id"] for item in critiques},
            {item["idea_id"] for item in ideas},
        )
        self.assertEqual(
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critiques_inbox,
                self.registry,
            ),
            critiques,
        )
        self.assertEqual(
            idea_hashes,
            {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in idea_paths
            },
        )

        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        self.assertLessEqual(len(shortlist["ranked_ideas"]), 3)
        self.assertGreaterEqual(len(shortlist["ranked_ideas"]), 1)
        self.assertFalse(
            "profit" in shortlist["recommendation_reason_zh"].lower()
        )
        self.assertEqual(
            api.build_shortlist(
                self.repo, str(result["run_id"]), self.registry
            ),
            shortlist,
        )

        markdown, html = api.render_human_review_zh(
            self.repo, str(result["run_id"]), self.registry
        )
        disclaimer = (
            "批准研究方向不代表盈利判断，也不授权创建 Candidate 或执行 Campaign。"
        )
        self.assertTrue(markdown.endswith(disclaimer))
        self.assertIn(disclaimer, html)
        self.assertIn('lang="zh-CN"', html)
        self.assertIn('data-markdown-source="human-review.zh-CN.md"', html)
        self.assertIn('<link rel="icon" href="data:,">', html)
        self.assertIn("table, .sources { break-inside:avoid; }", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("<script", html.lower())
        for label in (
            "研究问题",
            "当前理由",
            "机制",
            "最强反证",
            "数据准备度",
            "最小测试",
            "成本",
            "停止条件",
            "Critic 结论",
            "评分",
            "不确定性",
            "来源溯源",
        ):
            self.assertIn(label, markdown)
            self.assertIn(label, html)

        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_ideas"
                ).fetchone()[0],
                6,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_critiques"
                ).fetchone()[0],
                6,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_shortlists"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT event_type FROM research_discovery_events "
                    "ORDER BY rowid DESC LIMIT 1"
                ).fetchone()[0],
                "completed",
            )

    def test_review_rejects_idea_count_family_cap_and_schema_drift_atomically(self):
        api = self._review_api()
        result = self._prepare_review_run()
        inbox = Path(str(result["researcher_inbox"]))
        payloads = self._write_review_drafts("ideas", inbox)

        for count in (5, 11):
            with self.subTest(count=count):
                for path in inbox.glob("*.json"):
                    path.unlink()
                expanded = [copy.deepcopy(item) for item in payloads]
                while len(expanded) < count:
                    extra = copy.deepcopy(payloads[len(expanded) % len(payloads)])
                    extra["idea_id"] = f"extra-{len(expanded)}"
                    extra["strategy_family"] = f"extra_family_{len(expanded)}"
                    expanded.append(extra)
                for index, payload in enumerate(expanded[:count]):
                    write_json(inbox / f"idea-{index:02d}.json", payload)
                with self.assertRaises(DiscoveryError) as raised:
                    api.ingest_ideas(
                        self.repo,
                        str(result["run_id"]),
                        inbox,
                        self.registry,
                    )
                self.assertEqual(
                    raised.exception.reason_code, "idea_count_out_of_bounds"
                )

        def same_family(index, payload):
            if index < 3:
                payload["strategy_family"] = "crowded_family"

        self._write_review_drafts("ideas", inbox, transform=same_family)
        with self.assertRaises(DiscoveryError) as family:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            family.exception.reason_code, "strategy_family_cap_exceeded"
        )

        for mutation in ("extra", "missing"):
            def schema_drift(index, payload, mutation=mutation):
                if index == 0 and mutation == "extra":
                    payload["unexpected"] = True
                if index == 0 and mutation == "missing":
                    payload.pop("title")

            self._write_review_drafts("ideas", inbox, transform=schema_drift)
            with self.subTest(mutation=mutation), self.assertRaises(
                DiscoveryError
            ) as schema_error:
                api.ingest_ideas(
                    self.repo,
                    str(result["run_id"]),
                    inbox,
                    self.registry,
                )
            self.assertEqual(
                schema_error.exception.reason_code,
                "artifact_validation_failed",
            )

        self.assertFalse(
            (self.repo / result["run_path"] / "ideas").exists()
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_ideas"
                ).fetchone()[0],
                0,
            )

    def test_review_reuses_class_a_fixed_scope_and_data_readiness_guards(self):
        api = self._review_api()
        result = self._prepare_review_run()
        inbox = Path(str(result["researcher_inbox"]))

        def class_c_only(index, payload):
            if index == 0:
                payload["source_refs"] = [
                    {
                        "source_class": "C",
                        "canonical_url": "offline:public-strategy-note",
                        "publisher_type": "public_strategy_repository",
                        "retrieved_at": CREATED_AT,
                        "claim": "Unverified public strategy claim",
                        "content_fingerprint": "a" * 64,
                        "staleness_assessment": "unknown",
                        "licensing_constraints": "metadata only",
                    }
                ]

        def forbidden_source(index, payload):
            if index == 0:
                payload["source_refs"] = [
                    {
                        "source_class": "A",
                        "path": "research/data/snapshots/futures-validation-btc/manifest.yaml",
                        "claim": "Forbidden Validation evidence",
                    }
                ]

        def fixed_scope_drift(index, payload):
            if index == 0:
                payload["fixed_scope_confirmation"]["validation_access"] = True

        def unapproved_dataset(index, payload):
            if index == 0:
                payload["required_datasets"] = ["holdout-private"]

        cases = (
            ("class_c_only", class_c_only),
            ("source_not_allowlisted", forbidden_source),
            ("validation_forbidden", fixed_scope_drift),
            ("data_readiness_invalid", unapproved_dataset),
        )
        for expected_reason, transform in cases:
            self._write_review_drafts("ideas", inbox, transform=transform)
            with self.subTest(expected_reason=expected_reason), self.assertRaises(
                DiscoveryError
            ) as raised:
                api.ingest_ideas(
                    self.repo,
                    str(result["run_id"]),
                    inbox,
                    self.registry,
                )
            self.assertEqual(raised.exception.reason_code, expected_reason)

        policy_path = self.repo / "research/discovery/policy/ranking-policy.yaml"
        policy = json.loads(
            json.dumps(
                review_module._ranking_policy(self.repo),
                ensure_ascii=False,
            )
        )
        policy["weights"]["expected_information_gain"] = 0.31
        write_json(policy_path, policy)
        self._write_review_drafts("ideas", inbox)
        with self.assertRaises(DiscoveryError) as policy_error:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            policy_error.exception.reason_code, "ranking_policy_invalid"
        )

        self.assertFalse(
            (self.repo / result["run_path"] / "ideas").exists()
        )

    def test_review_rejects_modified_ideas_and_bad_critique_id_sets(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        ideas_root = self.repo / result["run_path"] / "ideas"
        first_path = sorted(ideas_root.glob("*.json"))[0]
        original_bytes = first_path.read_bytes()
        tampered = json.loads(original_bytes)
        tampered["title"] = "Critic attempted edit"
        write_json(first_path, tampered)
        critic_inbox = Path(str(result["researcher_inbox"])).parent / "critic"
        self._write_review_drafts("critiques", critic_inbox, ideas=ideas)
        with self.assertRaises(DiscoveryError) as modified:
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critic_inbox,
                self.registry,
            )
        self.assertEqual(
            modified.exception.reason_code, "idea_artifact_conflict"
        )
        first_path.write_bytes(original_bytes)

        self._write_review_drafts("critiques", critic_inbox, ideas=ideas)
        sorted(critic_inbox.glob("*.json"))[0].unlink()
        with self.assertRaises(DiscoveryError) as missing:
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critic_inbox,
                self.registry,
            )
        self.assertEqual(
            missing.exception.reason_code, "critique_id_set_mismatch"
        )

        payloads = self._write_review_drafts(
            "critiques", critic_inbox, ideas=ideas
        )
        extra = copy.deepcopy(payloads[0])
        extra["critique_id"] = "critique-extra"
        extra["idea_id"] = "extra-idea"
        write_json(critic_inbox / "extra.json", extra)
        with self.assertRaises(DiscoveryError) as extra_error:
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critic_inbox,
                self.registry,
            )
        self.assertEqual(
            extra_error.exception.reason_code, "critique_id_set_mismatch"
        )

        payloads = self._write_review_drafts(
            "critiques", critic_inbox, ideas=ideas
        )
        duplicate = copy.deepcopy(payloads[1])
        duplicate["critique_id"] = "critique-duplicate"
        duplicate["idea_id"] = payloads[0]["idea_id"]
        duplicate["idea_semantic_fingerprint"] = payloads[0][
            "idea_semantic_fingerprint"
        ]
        write_json(critic_inbox / "duplicate.json", duplicate)
        with self.assertRaises(DiscoveryError) as duplicate_error:
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critic_inbox,
                self.registry,
            )
        self.assertEqual(
            duplicate_error.exception.reason_code, "critique_idea_duplicate"
        )

        def wrong_binding(index, payload):
            if index == 0:
                payload["idea_semantic_fingerprint"] = "f" * 64

        self._write_review_drafts(
            "critiques",
            critic_inbox,
            ideas=ideas,
            transform=wrong_binding,
        )
        with self.assertRaises(DiscoveryError) as binding:
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critic_inbox,
                self.registry,
            )
        self.assertEqual(
            binding.exception.reason_code, "critic_binding_mismatch"
        )
        for mutation in ("extra", "missing"):
            def schema_drift(index, payload, mutation=mutation):
                if index == 0 and mutation == "extra":
                    payload["unexpected"] = True
                if index == 0 and mutation == "missing":
                    payload.pop("ranking_inputs")

            self._write_review_drafts(
                "critiques",
                critic_inbox,
                ideas=ideas,
                transform=schema_drift,
            )
            with self.subTest(mutation=mutation), self.assertRaises(
                DiscoveryError
            ) as schema_error:
                api.ingest_critiques(
                    self.repo,
                    str(result["run_id"]),
                    critic_inbox,
                    self.registry,
                )
            self.assertEqual(
                schema_error.exception.reason_code,
                "artifact_validation_failed",
            )
        self.assertFalse(
            (self.repo / result["run_path"] / "critiques").exists()
        )

    def test_review_allows_only_one_critic_requested_revision(self):
        api = self._review_api()
        result, ideas, ideas_inbox = self._ingest_fixture_ideas()
        revised_id = str(ideas[0]["idea_id"])

        def request_revision(index, payload):
            if payload["idea_id"] == revised_id:
                payload["verdict"] = "revise"

        self._ingest_fixture_critiques(result, ideas, request_revision)
        original = json.loads(
            sorted(
                (
                    ROOT
                    / "tests/fixtures/research-discovery/ideas"
                ).glob("*.json")
            )[0].read_text(encoding="utf-8")
        )
        fixture_by_id = {}
        for path in (
            ROOT / "tests/fixtures/research-discovery/ideas"
        ).glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            fixture_by_id[str(payload["idea_id"])] = payload
        original = fixture_by_id[revised_id]
        original["research_state_fingerprint"] = self.state["state_fingerprint"]
        original["idea_version"] = 2
        original["falsifiable_hypothesis"] += " Revision 2."
        for path in ideas_inbox.glob("*.json"):
            path.unlink()
        write_json(ideas_inbox / "revision-v2.json", original)
        revised = api.ingest_ideas(
            self.repo,
            str(result["run_id"]),
            ideas_inbox,
            self.registry,
        )
        self.assertEqual(len(revised), 1)
        self.assertEqual(revised[0]["idea_version"], 2)

        version_three = copy.deepcopy(original)
        version_three["idea_version"] = 3
        version_three["falsifiable_hypothesis"] += " Revision 3."
        for path in ideas_inbox.glob("*.json"):
            path.unlink()
        write_json(ideas_inbox / "revision-v3.json", version_three)
        with self.assertRaises(DiscoveryError) as exhausted:
            api.ingest_ideas(
                self.repo,
                str(result["run_id"]),
                ideas_inbox,
                self.registry,
            )
        self.assertEqual(
            exhausted.exception.reason_code, "revision_limit_exceeded"
        )

    def test_review_reject_verdict_is_excluded_from_shortlist(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        rejected_id = str(ideas[0]["idea_id"])

        def reject_one(index, payload):
            if payload["idea_id"] == rejected_id:
                payload["verdict"] = "reject"

        self._ingest_fixture_critiques(result, ideas, reject_one)
        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        self.assertNotIn(
            rejected_id,
            {item["idea_id"] for item in shortlist["ranked_ideas"]},
        )

    def test_review_low_scores_complete_as_no_research_recommended(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()

        def below_threshold(index, payload):
            payload["verdict"] = "pass"
            payload["ranking_inputs"] = {
                key: 0.1 for key in payload["ranking_inputs"]
            }

        self._ingest_fixture_critiques(result, ideas, below_threshold)
        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        self.assertEqual(shortlist["ranked_ideas"], [])
        self.assertIsNone(shortlist["recommended_idea_id"])
        self.assertEqual(
            shortlist["recommendation"], "no_research_recommended"
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            completed = connection.execute(
                "SELECT payload_json FROM research_discovery_events "
                "WHERE run_id=? AND event_type='completed'",
                (result["run_id"],),
            ).fetchone()
        self.assertIsNotNone(completed)
        self.assertEqual(
            json.loads(completed[0])["recommendation"],
            "no_research_recommended",
        )

    def test_review_html_escapes_artifact_text_and_stays_offline(self):
        api = self._review_api()

        def hostile_text(index, payload):
            if payload["idea_id"] == "trend-persistence-filter":
                payload["title"] = '<img src=x onerror="alert(1)">'
                payload["known_limitations"] = ["<script>alert(2)</script>"]

        result, ideas, _ = self._ingest_fixture_ideas(hostile_text)
        self._ingest_fixture_critiques(result, ideas)
        api.build_shortlist(self.repo, str(result["run_id"]), self.registry)
        _, html = api.render_human_review_zh(
            self.repo, str(result["run_id"]), self.registry
        )
        self.assertNotIn('<img src=x onerror="alert(1)">', html)
        self.assertNotIn("<script>alert(2)</script>", html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("<img ", html.lower())

    def test_review_same_version_conflict_preserves_immutable_rows_and_files(self):
        api = self._review_api()
        result, ideas, inbox = self._ingest_fixture_ideas()
        ideas_root = self.repo / result["run_path"] / "ideas"
        before = {
            path.name: path.read_bytes() for path in ideas_root.glob("*.json")
        }

        def conflicting_title(index, payload):
            if index == 0:
                payload["title"] = "Conflicting immutable version"

        self._write_review_drafts("ideas", inbox, transform=conflicting_title)
        with self.assertRaises(DiscoveryError) as conflict:
            api.ingest_ideas(
                self.repo,
                str(result["run_id"]),
                inbox,
                self.registry,
            )
        self.assertEqual(
            conflict.exception.reason_code, "immutable_artifact_conflict"
        )
        self.assertEqual(
            before,
            {path.name: path.read_bytes() for path in ideas_root.glob("*.json")},
        )
        self.assertFalse(
            any(
                path.name.startswith(".review-staging-")
                for path in (self.repo / result["run_path"]).iterdir()
            )
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_ideas"
                ).fetchone()[0],
                len(ideas),
            )

    def test_review_lifecycle_uses_latest_rowid_and_blocks_pending_revision(self):
        api = self._review_api()
        result, ideas, ideas_inbox = self._ingest_fixture_ideas()
        revised_id = str(ideas[0]["idea_id"])

        def request_revision(index, payload):
            if payload["idea_id"] == revised_id:
                payload["verdict"] = "revise"

        self._ingest_fixture_critiques(result, ideas, request_revision)
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "UPDATE research_discovery_events SET created_at=? "
                "WHERE run_id=? AND event_type='ideas_ingested'",
                ("9999-12-31T23:59:59+00:00", result["run_id"]),
            )
            connection.commit()
            events = connection.execute(
                "SELECT event_type FROM research_discovery_events "
                "WHERE run_id=? ORDER BY rowid",
                (result["run_id"],),
            ).fetchall()
        self.assertEqual(
            [row[0] for row in events],
            ["ideas_ingested", "critiques_ingested"],
        )

        with self.assertRaises(DiscoveryError) as pending:
            api.build_shortlist(self.repo, str(result["run_id"]), self.registry)
        self.assertEqual(pending.exception.reason_code, "revision_pending")
        self.assertFalse(
            (self.repo / str(result["run_path"]) / "shortlist.json").exists()
        )

        for path in ideas_inbox.glob("*.json"):
            path.unlink()
        write_json(
            ideas_inbox / "revision-v2.json",
            self._revision_draft(ideas[0]),
        )
        revised = api.ingest_ideas(
            self.repo, str(result["run_id"]), ideas_inbox, self.registry
        )[0]
        with self.assertRaises(DiscoveryError) as awaiting_critic:
            api.build_shortlist(self.repo, str(result["run_id"]), self.registry)
        self.assertEqual(
            awaiting_critic.exception.reason_code, "lifecycle_order_invalid"
        )

        latest = [revised if item["idea_id"] == revised_id else item for item in ideas]

        def revised_critique(index, payload):
            if payload["idea_id"] == revised_id:
                payload["critique_id"] += "-v2"
                payload["verdict"] = "pass"

        self._ingest_fixture_critiques(result, latest, revised_critique)
        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        self.assertEqual(shortlist["recommendation"], "research_recommended")

        for path in ideas_inbox.glob("*.json"):
            path.unlink()
        write_json(ideas_inbox / "invalid-after-completed.json", {})
        with self.assertRaises(DiscoveryError) as closed_idea:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), ideas_inbox, self.registry
            )
        self.assertEqual(closed_idea.exception.reason_code, "run_completed")

        critic_inbox = Path(str(result["researcher_inbox"])).parent / "critic"
        for path in critic_inbox.glob("*.json"):
            path.unlink()
        write_json(critic_inbox / "invalid-after-completed.json", {})
        with self.assertRaises(DiscoveryError) as closed_critic:
            api.ingest_critiques(
                self.repo, str(result["run_id"]), critic_inbox, self.registry
            )
        self.assertEqual(closed_critic.exception.reason_code, "run_completed")

    def test_review_rebinds_stored_critique_for_ranking_and_rendering(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        self._ingest_fixture_critiques(result, ideas)
        target_id = str(ideas[0]["idea_id"])
        original = self._stored_critique(str(result["run_id"]), target_id)
        tampered = copy.deepcopy(original)
        tampered["idea_semantic_fingerprint"] = "f" * 64
        self._replace_stored_critique(result, tampered)

        with self.assertRaises(DiscoveryError) as ranking:
            api.build_shortlist(self.repo, str(result["run_id"]), self.registry)
        self.assertEqual(ranking.exception.reason_code, "critic_binding_mismatch")

        self._replace_stored_critique(result, original)
        api.build_shortlist(self.repo, str(result["run_id"]), self.registry)
        wrong_id = copy.deepcopy(original)
        wrong_id["idea_id"] = str(ideas[1]["idea_id"])
        self._replace_stored_critique(result, wrong_id)
        with self.assertRaises(DiscoveryError) as rendering:
            api.render_human_review_zh(
                self.repo, str(result["run_id"]), self.registry
            )
        self.assertEqual(rendering.exception.reason_code, "critic_binding_mismatch")

    def test_revision_authorization_revalidates_full_critique_binding(self):
        api = self._review_api()
        result, ideas, inbox = self._ingest_fixture_ideas()
        revised_id = str(ideas[0]["idea_id"])

        def request_revision(index, payload):
            if payload["idea_id"] == revised_id:
                payload["verdict"] = "revise"

        self._ingest_fixture_critiques(result, ideas, request_revision)
        stored = self._stored_critique(str(result["run_id"]), revised_id)
        stored["source_verification"]["highest_class"] = "B"
        self._replace_stored_critique(result, stored)
        for path in inbox.glob("*.json"):
            path.unlink()
        write_json(inbox / "revision-v2.json", self._revision_draft(ideas[0]))

        with self.assertRaises(DiscoveryError) as invalid_authorization:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            invalid_authorization.exception.reason_code, "critic_source_mismatch"
        )

    def test_stored_critique_pass_gating_is_rechecked(self):
        api = self._review_api()

        def needs_data(index, payload):
            if payload["idea_id"] == "trend-persistence-filter":
                payload["data_readiness"] = "data_readiness_required"

        result, ideas, _ = self._ingest_fixture_ideas(needs_data)
        target_id = "trend-persistence-filter"

        def cannot_pass(index, payload):
            if payload["idea_id"] == target_id:
                payload["verdict"] = "revise"

        self._ingest_fixture_critiques(result, ideas, cannot_pass)
        stored = self._stored_critique(str(result["run_id"]), target_id)
        stored["verdict"] = "pass"
        self._replace_stored_critique(result, stored)
        with self.assertRaises(DiscoveryError) as pass_gate:
            api.build_shortlist(self.repo, str(result["run_id"]), self.registry)
        self.assertEqual(pass_gate.exception.reason_code, "critic_pass_forbidden")

    def test_publish_race_is_fail_if_exists_and_preserves_concurrent_file(self):
        api = self._review_api()
        result = self._prepare_review_run()
        inbox = Path(str(result["researcher_inbox"]))
        self._write_review_drafts("ideas", inbox)
        concurrent_bytes = b'{"owner":"concurrent"}\n'
        raced_destination: list[Path] = []
        original_link = os.link

        def create_destination_then_link(source, destination, *args, **kwargs):
            target = Path(destination)
            if not raced_destination:
                target.write_bytes(concurrent_bytes)
                raced_destination.append(target)
            return original_link(source, destination, *args, **kwargs)

        with mock.patch.object(
            review_module.os,
            "link",
            side_effect=create_destination_then_link,
            create=True,
        ), self.assertRaises(DiscoveryError) as race:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(race.exception.reason_code, "immutable_artifact_conflict")
        self.assertEqual(raced_destination[0].read_bytes(), concurrent_bytes)
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_ideas"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_events"
                ).fetchone()[0],
                0,
            )

    def test_staging_cleanup_failure_rolls_back_and_retry_is_not_blocked(self):
        api = self._review_api()
        result = self._prepare_review_run()
        inbox = Path(str(result["researcher_inbox"]))
        drafts = self._write_review_drafts("ideas", inbox)
        original_rmtree = shutil.rmtree
        calls = 0

        def fail_once(path, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("injected staging cleanup failure")
            return original_rmtree(path, *args, **kwargs)

        with mock.patch.object(
            review_module.shutil, "rmtree", side_effect=fail_once
        ), self.assertRaises(DiscoveryError) as cleanup:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            cleanup.exception.reason_code, "artifact_staging_cleanup_failed"
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_ideas"
                ).fetchone()[0],
                0,
            )
        self.assertFalse((self.repo / str(result["run_path"]) / "ideas").exists())
        self.assertEqual(
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            ),
            [api._validate_idea_payload(api._canonical_run_context(
                self.repo, str(result["run_id"]), self.registry
            ), item) for item in drafts],
        )

    def test_temp_inbox_is_namespaced_by_canonical_repo_identity(self):
        first = self._prepare_review_run()
        first_inbox = Path(str(first["researcher_inbox"]))
        write_json(first_inbox / "owned-by-first-repo.json", {"owner": "first"})

        second_repo = Path(self.temporary_directory.name) / "repo-copy"
        shutil.copytree(self.repo, second_repo)
        shutil.rmtree(second_repo / str(first["run_path"]))
        second_registry = Path(self.temporary_directory.name) / "second.sqlite"
        second = prepare_run(second_repo, self._trigger(), second_registry)
        second_inbox = Path(str(second["researcher_inbox"]))
        self.addCleanup(
            lambda: shutil.rmtree(second_inbox.parents[1], ignore_errors=True)
        )

        self.assertEqual(first["run_id"], second["run_id"])
        self.assertNotEqual(first_inbox, second_inbox)
        self.assertEqual(list(second_inbox.iterdir()), [])

    def test_revision_v2_response_loss_retry_requires_exact_event_batch(self):
        api = self._review_api()
        result, ideas, inbox = self._ingest_fixture_ideas()
        revised_id = str(ideas[0]["idea_id"])

        def request_revision(index, payload):
            if payload["idea_id"] == revised_id:
                payload["verdict"] = "revise"

        self._ingest_fixture_critiques(result, ideas, request_revision)
        revision = self._revision_draft(ideas[0])
        for path in inbox.glob("*.json"):
            path.unlink()
        write_json(inbox / "revision-v2.json", revision)
        first_response = api.ingest_ideas(
            self.repo, str(result["run_id"]), inbox, self.registry
        )

        run_root = self.repo / str(result["run_path"])

        def persistent_state():
            with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                registry = {
                    table: connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in (
                        "research_discovery_ideas",
                        "research_discovery_critiques",
                        "research_discovery_shortlists",
                        "research_discovery_events",
                    )
                }
                registry["events"] = connection.execute(
                    "SELECT rowid, event_type, payload_json "
                    "FROM research_discovery_events WHERE run_id=? ORDER BY rowid",
                    (result["run_id"],),
                ).fetchall()
            files = {
                path.relative_to(run_root).as_posix(): path.read_bytes()
                for path in run_root.rglob("*")
                if path.is_file()
            }
            return registry, files

        after_first = persistent_state()
        original_publish = api._publish_batch
        guard_observations = []

        def require_transaction_guard(*args, **kwargs):
            transaction_guard = kwargs.get("transaction_guard")

            if transaction_guard is not None:
                def observed_guard(connection):
                    guard_observations.append(
                        (str(args[4]), connection.in_transaction)
                    )
                    return transaction_guard(connection)

                kwargs["transaction_guard"] = observed_guard
            return original_publish(*args, **kwargs)

        with mock.patch.object(
            api, "_publish_batch", side_effect=require_transaction_guard
        ):
            retry_response = api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(retry_response, first_response)
        self.assertEqual(persistent_state(), after_first)
        self.assertEqual(guard_observations, [("ideas_ingested", True)])

        changed = copy.deepcopy(revision)
        changed["falsifiable_hypothesis"] += " Conflicting retry."
        write_json(inbox / "revision-v2.json", changed)
        with self.assertRaises(DiscoveryError) as changed_retry:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            changed_retry.exception.reason_code, "revision_replay_mismatch"
        )
        self.assertEqual(persistent_state(), after_first)

        write_json(inbox / "revision-v2.json", revision)
        extra = copy.deepcopy(ideas[1])
        extra.pop("semantic_fingerprint", None)
        write_json(inbox / "extra-v1.json", extra)
        with self.assertRaises(DiscoveryError) as extra_retry:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            extra_retry.exception.reason_code, "revision_replay_mismatch"
        )
        self.assertEqual(persistent_state(), after_first)

        for path in inbox.glob("*.json"):
            path.unlink()
        with self.assertRaises(DiscoveryError) as missing_retry:
            api.ingest_ideas(
                self.repo, str(result["run_id"]), inbox, self.registry
            )
        self.assertEqual(
            missing_retry.exception.reason_code, "revision_batch_empty"
        )
        self.assertEqual(persistent_state(), after_first)

    def test_transaction_guard_rejects_critique_replay_completed_after_preflight(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        _, critic_inbox = self._ingest_fixture_critiques(result, ideas)
        run_root = self.repo / str(result["run_path"])
        original_publish = api._publish_batch
        interleaved = False
        state_after_completion = []
        guard_observations = []

        def persistent_state():
            with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                rows = {
                    table: connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in (
                        "research_discovery_ideas",
                        "research_discovery_critiques",
                        "research_discovery_shortlists",
                        "research_discovery_events",
                    )
                }
                rows["events"] = connection.execute(
                    "SELECT rowid, event_type, payload_json "
                    "FROM research_discovery_events WHERE run_id=? ORDER BY rowid",
                    (result["run_id"],),
                ).fetchall()
            files = {
                path.relative_to(run_root).as_posix(): path.read_bytes()
                for path in run_root.rglob("*")
                if path.is_file()
            }
            return rows, files

        def complete_between_preflight_and_begin(*args, **kwargs):
            nonlocal interleaved
            event_type = str(args[4])
            transaction_guard = kwargs.get("transaction_guard")

            if event_type == "critiques_ingested" and not interleaved:
                interleaved = True
                api.build_shortlist(
                    self.repo, str(result["run_id"]), self.registry
                )
                state_after_completion.append(persistent_state())

            if transaction_guard is not None:
                def observed_guard(connection):
                    guard_observations.append(
                        (event_type, connection.in_transaction)
                    )
                    return transaction_guard(connection)

                kwargs["transaction_guard"] = observed_guard
            return original_publish(*args, **kwargs)

        with mock.patch.object(
            api,
            "_publish_batch",
            side_effect=complete_between_preflight_and_begin,
        ), self.assertRaises(DiscoveryError) as replay:
            api.ingest_critiques(
                self.repo,
                str(result["run_id"]),
                critic_inbox,
                self.registry,
            )
        self.assertEqual(replay.exception.reason_code, "run_completed")
        self.assertEqual(len(state_after_completion), 1)
        self.assertEqual(persistent_state(), state_after_completion[0])
        self.assertEqual(
            guard_observations,
            [("completed", True), ("critiques_ingested", True)],
        )

    def test_exact_critic_replay_rechecks_idea_integrity_before_early_return(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        _, critic_inbox = self._ingest_fixture_critiques(result, ideas)
        run_root = self.repo / str(result["run_path"])
        idea_path = (
            run_root
            / "ideas"
            / f"{ideas[0]['idea_id']}-v{ideas[0]['idea_version']}.json"
        )
        original_idea_bytes = idea_path.read_bytes()
        begin_reached = threading.Event()
        allow_begin = threading.Event()
        replay_thread_open_count = 0
        original_open = api.open_director_registry
        replay_results = []
        replay_errors = []

        def persistent_state():
            with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                registry = {
                    table: connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in (
                        "research_discovery_ideas",
                        "research_discovery_critiques",
                        "research_discovery_shortlists",
                        "research_discovery_events",
                    )
                }
                registry["events"] = connection.execute(
                    "SELECT rowid, event_type, payload_json "
                    "FROM research_discovery_events WHERE run_id=? ORDER BY rowid",
                    (result["run_id"],),
                ).fetchall()
            critique_files = {
                path.name: path.read_bytes()
                for path in (run_root / "critiques").glob("*.json")
            }
            return registry, critique_files

        state_before_replay = persistent_state()

        class PauseBeforeBegin:
            def __init__(self, connection):
                self.connection = connection

            def execute(self, sql, parameters=()):
                if " ".join(sql.split()) == "BEGIN IMMEDIATE":
                    begin_reached.set()
                    if not allow_begin.wait(timeout=10):
                        raise TimeoutError("critic replay synchronization timed out")
                return self.connection.execute(sql, parameters)

            def __getattr__(self, name):
                return getattr(self.connection, name)

        def open_with_replay_paused(path):
            nonlocal replay_thread_open_count
            connection = original_open(path)
            if threading.current_thread() is replay_thread:
                replay_thread_open_count += 1
            if (
                threading.current_thread() is replay_thread
                and replay_thread_open_count == 3
            ):
                return PauseBeforeBegin(connection)
            return connection

        def replay_critiques():
            try:
                replay_results.append(
                    api.ingest_critiques(
                        self.repo,
                        str(result["run_id"]),
                        critic_inbox,
                        self.registry,
                    )
                )
            except Exception as exc:
                replay_errors.append(exc)

        with mock.patch.object(
            api,
            "open_director_registry",
            side_effect=open_with_replay_paused,
        ):
            replay_thread = threading.Thread(
                target=replay_critiques, daemon=True
            )
            replay_thread.start()
            self.assertTrue(begin_reached.wait(timeout=10))
            idea_path.write_bytes(original_idea_bytes + b"\n")
            allow_begin.set()
            replay_thread.join(timeout=10)

        self.assertFalse(replay_thread.is_alive())
        self.assertEqual(replay_results, [])
        self.assertEqual(len(replay_errors), 1)
        self.assertIsInstance(replay_errors[0], DiscoveryError)
        self.assertEqual(
            replay_errors[0].reason_code, "idea_artifact_changed"
        )
        self.assertEqual(persistent_state(), state_before_replay)
        self.assertEqual(idea_path.read_bytes(), original_idea_bytes + b"\n")
        self.assertEqual(
            [
                path.name
                for path in run_root.parent.iterdir()
                if path.name.startswith(".review-staging-")
            ],
            [],
        )

    def test_concurrent_identical_build_replays_after_stale_destination_preflight(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        self._ingest_fixture_critiques(result, ideas)
        run_root = self.repo / str(result["run_path"])
        begin_reached = threading.Event()
        allow_begin = threading.Event()
        first_thread_open_count = 0
        original_open = api.open_director_registry
        a_results = []
        a_errors = []

        class PauseBeforeBegin:
            def __init__(self, connection):
                self.connection = connection

            def execute(self, sql, parameters=()):
                if " ".join(sql.split()) == "BEGIN IMMEDIATE":
                    begin_reached.set()
                    if not allow_begin.wait(timeout=10):
                        raise TimeoutError("build replay synchronization timed out")
                return self.connection.execute(sql, parameters)

            def __getattr__(self, name):
                return getattr(self.connection, name)

        def open_with_first_build_paused(path):
            nonlocal first_thread_open_count
            connection = original_open(path)
            if threading.current_thread() is first:
                first_thread_open_count += 1
            if (
                threading.current_thread() is first
                and first_thread_open_count == 2
            ):
                return PauseBeforeBegin(connection)
            return connection

        def build_first():
            try:
                a_results.append(
                    api.build_shortlist(
                        self.repo, str(result["run_id"]), self.registry
                    )
                )
            except Exception as exc:
                a_errors.append(exc)

        with mock.patch.object(
            api,
            "open_director_registry",
            side_effect=open_with_first_build_paused,
        ):
            first = threading.Thread(target=build_first, daemon=True)
            first.start()
            self.assertTrue(begin_reached.wait(timeout=10))
            try:
                second_result = api.build_shortlist(
                    self.repo, str(result["run_id"]), self.registry
                )
            finally:
                allow_begin.set()
                first.join(timeout=10)

        self.assertFalse(first.is_alive())
        self.assertEqual(a_errors, [])
        self.assertEqual(len(a_results), 1)
        self.assertEqual(
            a_results[0]["shortlist_fingerprint"],
            second_result["shortlist_fingerprint"],
        )

        shortlist_path = run_root / "shortlist.json"
        self.assertEqual(
            json.loads(shortlist_path.read_text(encoding="utf-8")),
            second_result,
        )
        self.assertEqual(
            [path.name for path in run_root.glob("shortlist.json")],
            ["shortlist.json"],
        )
        self.assertEqual(
            [
                path.name
                for path in run_root.parent.iterdir()
                if path.name.startswith(".review-staging-")
            ],
            [],
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.row_factory = sqlite3.Row
            shortlist_rows = connection.execute(
                "SELECT shortlist_fingerprint, payload_json "
                "FROM research_discovery_shortlists WHERE run_id=?",
                (result["run_id"],),
            ).fetchall()
            completed_rows = connection.execute(
                "SELECT payload_json FROM research_discovery_events "
                "WHERE run_id=? AND event_type='completed'",
                (result["run_id"],),
            ).fetchall()
        self.assertEqual(len(shortlist_rows), 1)
        self.assertEqual(len(completed_rows), 1)
        self.assertEqual(
            shortlist_rows[0]["shortlist_fingerprint"],
            second_result["shortlist_fingerprint"],
        )
        self.assertEqual(
            json.loads(shortlist_rows[0]["payload_json"]), second_result
        )
        self.assertEqual(
            json.loads(completed_rows[0]["payload_json"])[
                "shortlist_fingerprint"
            ],
            second_result["shortlist_fingerprint"],
        )

    def test_completed_artifacts_without_exact_event_fail_closed(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        self._ingest_fixture_critiques(result, ideas)
        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        shortlist_path = self.repo / str(result["run_path"]) / "shortlist.json"
        original_bytes = shortlist_path.read_bytes()
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "DELETE FROM research_discovery_events "
                "WHERE run_id=? AND event_type='completed'",
                (result["run_id"],),
            )
            connection.commit()

        with self.assertRaises(DiscoveryError) as missing_event:
            api.build_shortlist(
                self.repo, str(result["run_id"]), self.registry
            )
        self.assertEqual(
            missing_event.exception.reason_code, "registry_artifact_conflict"
        )
        self.assertEqual(shortlist_path.read_bytes(), original_bytes)
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_shortlists "
                    "WHERE run_id=? AND shortlist_fingerprint=?",
                    (result["run_id"], shortlist["shortlist_fingerprint"]),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_events "
                    "WHERE run_id=? AND event_type='completed'",
                    (result["run_id"],),
                ).fetchone()[0],
                0,
            )

    def test_review_happy_path_freezes_scores_threshold_order_and_html_reason(self):
        api = self._review_api()
        result, ideas, _ = self._ingest_fixture_ideas()
        critiques, _ = self._ingest_fixture_critiques(result, ideas)
        policy = api._ranking_policy(self.repo)
        scores = {
            str(idea["idea_id"]): f"{api.score_idea(idea, {
                str(item['idea_id']): item for item in critiques
            }[str(idea['idea_id'])], policy):.6f}"
            for idea in ideas
        }
        self.assertEqual(
            scores,
            {
                "breakout-compression-release": "0.698000",
                "market-structure-range-location": "0.477500",
                "mean-reversion-liquidity-reset": "0.783000",
                "regime-switching-transition-risk": "0.606000",
                "trend-persistence-filter": "0.832000",
                "volatility-transition-asymmetry": "0.759500",
            },
        )
        self.assertEqual(policy["shortlist_threshold"], 0.55)
        self.assertEqual(
            policy["tie_breakers"],
            ["lower_risk", "lower_cost", "semantic_fingerprint"],
        )
        shortlist = api.build_shortlist(
            self.repo, str(result["run_id"]), self.registry
        )
        self.assertEqual(
            [item["idea_id"] for item in shortlist["ranked_ideas"]],
            [
                "trend-persistence-filter",
                "mean-reversion-liquidity-reset",
                "volatility-transition-asymmetry",
            ],
        )
        markdown, html = api.render_human_review_zh(
            self.repo, str(result["run_id"]), self.registry
        )
        reason = str(shortlist["recommendation_reason_zh"])
        self.assertIn(reason, markdown)
        self.assertIn(reason, html)

    def test_route_approval_and_nonexecuting_handoff_are_exactly_replayable(self):
        api = self._route_api()
        result, ideas, critiques, shortlist = self._prepare_route_run()
        run_id = str(result["run_id"])
        request = self._approved_direction_request()

        approval = api.record_direction_decision(
            self.repo,
            run_id,
            request,
            self.state,
            self.constitution,
            self.registry,
            decided_at="2026-07-14T00:10:00+00:00",
        )
        self.assertEqual(approval["decision"], "approved_for_director_handoff")
        self.assertEqual(approval["selected_idea_id"], shortlist["ranked_ideas"][0]["idea_id"])
        self.assertEqual(
            approval["selected_idea_fingerprint"],
            shortlist["ranked_ideas"][0]["idea_fingerprint"],
        )
        self.assertEqual(
            api.record_direction_decision(
                self.repo,
                run_id,
                request,
                self.state,
                self.constitution,
                self.registry,
                decided_at="2026-07-14T00:10:00+00:00",
            ),
            approval,
        )

        handoff = api.create_handoff(
            self.repo,
            run_id,
            self.state,
            self.constitution,
            self.registry,
        )
        self.assertFalse(handoff["execution_authorized"])
        self.assertEqual(
            handoff["idea_fingerprint"], approval["selected_idea_fingerprint"]
        )
        self.assertEqual(
            api.create_handoff(
                self.repo,
                run_id,
                self.state,
                self.constitution,
                self.registry,
            ),
            handoff,
        )
        selected_id = str(approval["selected_idea_id"])
        selected_idea = {str(item["idea_id"]): item for item in ideas}[selected_id]
        selected_critique = {
            str(item["idea_id"]): item for item in critiques
        }[selected_id]
        self.assertEqual(handoff["research_question"], selected_idea["falsifiable_hypothesis"])
        self.assertEqual(handoff["critique_fingerprint"], selected_critique["critic_fingerprint"])
        run_root = self.repo / str(result["run_path"])
        self.assertEqual(json.loads((run_root / "approval.json").read_text(encoding="utf-8")), approval)
        self.assertEqual(json.loads((run_root / "handoff.json").read_text(encoding="utf-8")), handoff)
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_approvals WHERE run_id=?",
                    (run_id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_handoffs WHERE run_id=?",
                    (run_id,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT event_type FROM research_discovery_events WHERE run_id=? "
                    "ORDER BY rowid DESC LIMIT 2",
                    (run_id,),
                ).fetchall(),
                [("handed_to_director",), ("human_direction_decision",)],
            )

    def test_route_request_is_human_only_and_cannot_inject_governed_fields(self):
        api = self._route_api()
        result, _, _, _ = self._prepare_route_run()
        run_id = str(result["run_id"])
        cases = (
            ({**self._approved_direction_request(), "reviewer_type": "researcher"}, "reviewer_not_human"),
            ({**self._approved_direction_request(), "selected_rank": 0}, "selected_rank_invalid"),
            ({**self._approved_direction_request(), "selected_rank": 4}, "selected_rank_invalid"),
            ({key: value for key, value in self._approved_direction_request().items() if key != "selected_rank"}, "selected_rank_invalid"),
            ({**self._approved_direction_request(), "selected_rank": [1, 2]}, "selected_rank_invalid"),
            ({**self._approved_direction_request(), "approval_fingerprint": "0" * 64}, "decision_request_fields_invalid"),
            ({**self._approved_direction_request(), "execution_authorized": True}, "decision_request_fields_invalid"),
            ({**self._approved_direction_request(), "research_question": "override"}, "decision_request_fields_invalid"),
        )
        for request, reason in cases:
            with self.subTest(reason=reason, request=request):
                with self.assertRaises(DiscoveryError) as rejected:
                    api.record_direction_decision(
                        self.repo,
                        run_id,
                        request,
                        self.state,
                        self.constitution,
                        self.registry,
                    )
                self.assertEqual(rejected.exception.reason_code, reason)
        run_root = self.repo / str(result["run_path"])
        self.assertFalse((run_root / "approval.json").exists())
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_approvals"
                ).fetchone()[0],
                0,
            )

    def test_route_rejected_and_deferred_decisions_have_null_selection_and_no_handoff(self):
        for decision in ("rejected", "deferred"):
            with self.subTest(decision=decision):
                self.tearDown()
                self.setUp()
                api = self._route_api()
                result, _, _, _ = self._prepare_route_run()
                run_id = str(result["run_id"])
                request = {
                    "decision": decision,
                    "selected_rank": None,
                    "reviewer_type": "human_user",
                    "decision_reason_zh": "本轮暂不进入正式准备",
                }
                approval = api.record_direction_decision(
                    self.repo,
                    run_id,
                    request,
                    self.state,
                    self.constitution,
                    self.registry,
                )
                self.assertIsNone(approval["selected_idea_id"])
                self.assertIsNone(approval["selected_idea_fingerprint"])
                self.assertIsNone(approval["selected_critique_fingerprint"])
                with self.assertRaises(DiscoveryError) as blocked:
                    api.create_handoff(
                        self.repo,
                        run_id,
                        self.state,
                        self.constitution,
                        self.registry,
                    )
                self.assertEqual(blocked.exception.reason_code, "direction_not_approved")
                self.assertFalse(
                    (self.repo / str(result["run_path"]) / "handoff.json").exists()
                )

    def test_route_revalidates_state_constitution_shortlist_idea_and_critique(self):
        api = self._route_api()
        mutations = (
            ("state", "research_state_conflict"),
            ("constitution", "constitution_fingerprint_conflict"),
            ("shortlist", "shortlist_artifact_conflict"),
            ("idea", "idea_artifact_conflict"),
            ("critique", "critique_artifact_conflict"),
        )
        for target, reason in mutations:
            with self.subTest(target=target):
                self.tearDown()
                self.setUp()
                result, _, _, shortlist = self._prepare_route_run()
                run_id = str(result["run_id"])
                state = copy.deepcopy(self.state)
                constitution = copy.deepcopy(self.constitution)
                run_root = self.repo / str(result["run_path"])
                if target == "state":
                    state["datasets"][0]["pairs"].append("SOL/USDT:USDT")
                    self._reseal_state(state)
                elif target == "constitution":
                    constitution["approved_version"] = 2
                elif target == "shortlist":
                    payload = json.loads((run_root / "shortlist.json").read_text(encoding="utf-8"))
                    payload["recommendation_reason_zh"] += "篡改"
                    write_json(run_root / "shortlist.json", payload)
                else:
                    selected = shortlist["ranked_ideas"][0]
                    if target == "idea":
                        path = next((run_root / "ideas").glob(f"{selected['idea_id']}-v*.json"))
                        payload = json.loads(path.read_text(encoding="utf-8"))
                        payload["falsifiable_hypothesis"] += " tampered"
                    else:
                        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                            row = connection.execute(
                                "SELECT payload_json FROM research_discovery_critiques "
                                "WHERE critic_fingerprint=?",
                                (selected["critique_fingerprint"],),
                            ).fetchone()
                        payload = json.loads(row[0])
                        path = run_root / "critiques" / f"{payload['critique_id']}.json"
                        payload["strongest_counterevidence"] += " tampered"
                    write_json(path, payload)
                with self.assertRaises(DiscoveryError) as stale:
                    api.record_direction_decision(
                        self.repo,
                        run_id,
                        self._approved_direction_request(),
                        state,
                        constitution,
                        self.registry,
                    )
                self.assertEqual(stale.exception.reason_code, reason)
                self.assertFalse((run_root / "approval.json").exists())

    def test_route_conflicting_second_approval_and_broken_replay_fail_closed(self):
        api = self._route_api()
        result, _, _, _ = self._prepare_route_run()
        run_id = str(result["run_id"])
        first = api.record_direction_decision(
            self.repo,
            run_id,
            self._approved_direction_request(),
            self.state,
            self.constitution,
            self.registry,
            decided_at="2026-07-14T00:10:00+00:00",
        )
        conflicting = {**self._approved_direction_request(), "selected_rank": 2}
        with self.assertRaises(DiscoveryError) as conflict:
            api.record_direction_decision(
                self.repo,
                run_id,
                conflicting,
                self.state,
                self.constitution,
                self.registry,
                decided_at="2026-07-14T00:11:00+00:00",
            )
        self.assertEqual(conflict.exception.reason_code, "direction_decision_conflict")
        run_root = self.repo / str(result["run_path"])
        (run_root / "approval.json").unlink()
        with self.assertRaises(DiscoveryError) as broken:
            api.record_direction_decision(
                self.repo,
                run_id,
                self._approved_direction_request(),
                self.state,
                self.constitution,
                self.registry,
                decided_at=str(first["decided_at"]),
            )
        self.assertEqual(broken.exception.reason_code, "registry_artifact_conflict")

    def test_route_rejects_rogue_artifacts_and_unsafe_run_paths(self):
        api = self._route_api()
        result, _, _, _ = self._prepare_route_run()
        run_id = str(result["run_id"])
        run_root = self.repo / str(result["run_path"])
        (run_root / "rogue.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(DiscoveryError) as rogue:
            api.record_direction_decision(
                self.repo,
                run_id,
                self._approved_direction_request(),
                self.state,
                self.constitution,
                self.registry,
            )
        self.assertEqual(rogue.exception.reason_code, "run_artifact_conflict")
        with self.assertRaises(DiscoveryError) as traversal:
            api.record_direction_decision(
                self.repo,
                "../" + run_id,
                self._approved_direction_request(),
                self.state,
                self.constitution,
                self.registry,
            )
        self.assertEqual(traversal.exception.reason_code, "run_path_invalid")

    def test_route_publish_failure_rolls_back_file_row_and_event(self):
        api = self._route_api()
        result, _, _, _ = self._prepare_route_run()
        run_id = str(result["run_id"])
        original = route_module.os.link

        def fail_link(source, destination):
            if Path(destination).name == "approval.json":
                raise OSError("injected approval publish failure")
            return original(source, destination)

        with mock.patch.object(route_module.os, "link", side_effect=fail_link):
            with self.assertRaises(DiscoveryError) as failed:
                api.record_direction_decision(
                    self.repo,
                    run_id,
                    self._approved_direction_request(),
                    self.state,
                    self.constitution,
                    self.registry,
                )
        self.assertEqual(failed.exception.reason_code, "artifact_publish_failed")
        run_root = self.repo / str(result["run_path"])
        self.assertFalse((run_root / "approval.json").exists())
        self.assertEqual(list(run_root.parent.glob(".route-staging-*")), [])
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM research_discovery_approvals").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_events WHERE event_type='human_direction_decision'"
                ).fetchone()[0],
                0,
            )

    def test_route_transaction_rechecks_selected_artifacts_after_preflight(self):
        api = self._route_api()
        result, _, _, shortlist = self._prepare_route_run()
        run_id = str(result["run_id"])
        run_root = self.repo / str(result["run_path"])
        selected_id = str(shortlist["ranked_ideas"][0]["idea_id"])
        idea_path = next((run_root / "ideas").glob(f"{selected_id}-v*.json"))
        original_publish = review_module._publish_batch
        interleaved = False

        def mutate_after_preflight(*args, **kwargs):
            nonlocal interleaved
            if not interleaved:
                interleaved = True
                payload = json.loads(idea_path.read_text(encoding="utf-8"))
                payload["falsifiable_hypothesis"] += " tampered after route preflight"
                write_json(idea_path, payload)
            return original_publish(*args, **kwargs)

        with mock.patch.object(
            route_module.review_support,
            "_publish_batch",
            side_effect=mutate_after_preflight,
        ):
            with self.assertRaises(DiscoveryError) as changed:
                api.record_direction_decision(
                    self.repo,
                    run_id,
                    self._approved_direction_request(),
                    self.state,
                    self.constitution,
                    self.registry,
                )
        self.assertEqual(changed.exception.reason_code, "idea_artifact_conflict")
        self.assertFalse((run_root / "approval.json").exists())
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM research_discovery_approvals").fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM research_discovery_events WHERE event_type='human_direction_decision'"
                ).fetchone()[0],
                0,
            )

    def test_route_rejects_self_consistent_approval_for_another_run(self):
        api = self._route_api()
        result, _, _, _ = self._prepare_route_run()
        run_id = str(result["run_id"])
        approval = api.record_direction_decision(
            self.repo,
            run_id,
            self._approved_direction_request(),
            self.state,
            self.constitution,
            self.registry,
            decided_at="2026-07-14T00:10:00+00:00",
        )
        altered = copy.deepcopy(approval)
        altered["discovery_run_id"] = "discovery-run-ffffffffffffffff"
        altered["approval_fingerprint"] = route_module.artifact_fingerprint(
            altered, "approval_fingerprint"
        )
        run_root = self.repo / str(result["run_path"])
        write_json(run_root / "approval.json", altered)
        approval_json = json.dumps(altered, ensure_ascii=False, sort_keys=True)
        event_payload = route_module._approval_event(altered)
        event_json = json.dumps(event_payload, ensure_ascii=False, sort_keys=True)
        event_id = route_module._event_id(
            run_id, "human_direction_decision", event_payload
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "UPDATE research_discovery_approvals SET approval_fingerprint=?, payload_json=? "
                "WHERE run_id=?",
                (altered["approval_fingerprint"], approval_json, run_id),
            )
            connection.execute(
                "UPDATE research_discovery_events SET event_id=?, payload_json=? "
                "WHERE run_id=? AND event_type='human_direction_decision'",
                (event_id, event_json, run_id),
            )
            connection.commit()
        with self.assertRaises(DiscoveryError) as wrong_run:
            api.create_handoff(
                self.repo,
                run_id,
                self.state,
                self.constitution,
                self.registry,
            )
        self.assertEqual(wrong_run.exception.reason_code, "approval_binding_conflict")
        self.assertFalse((run_root / "handoff.json").exists())

    def test_route_missing_decision_event_blocks_handoff_without_repair(self):
        api = self._route_api()
        result, _, _, _ = self._prepare_route_run()
        run_id = str(result["run_id"])
        api.record_direction_decision(
            self.repo,
            run_id,
            self._approved_direction_request(),
            self.state,
            self.constitution,
            self.registry,
        )
        with contextlib.closing(sqlite3.connect(self.registry)) as connection:
            connection.execute(
                "DELETE FROM research_discovery_events "
                "WHERE run_id=? AND event_type='human_direction_decision'",
                (run_id,),
            )
            connection.commit()
        with self.assertRaises(DiscoveryError) as missing_event:
            api.create_handoff(
                self.repo,
                run_id,
                self.state,
                self.constitution,
                self.registry,
            )
        self.assertEqual(missing_event.exception.reason_code, "registry_event_conflict")
        self.assertFalse(
            (self.repo / str(result["run_path"]) / "handoff.json").exists()
        )

    def test_route_reparse_destination_and_cleanup_failure_leave_no_decision(self):
        for fault in ("reparse", "cleanup"):
            with self.subTest(fault=fault):
                self.tearDown()
                self.setUp()
                api = self._route_api()
                result, _, _, _ = self._prepare_route_run()
                run_id = str(result["run_id"])
                run_root = self.repo / str(result["run_path"])
                if fault == "reparse":
                    original_reparse = route_module.trigger_support._is_reparse_point

                    def mark_approval(path):
                        return Path(path).name == "approval.json" or original_reparse(path)

                    patcher = mock.patch.object(
                        route_module.trigger_support,
                        "_is_reparse_point",
                        side_effect=mark_approval,
                    )
                    expected = "run_reparse_forbidden"
                else:
                    original_rmtree = route_module.review_support.shutil.rmtree
                    failed_once = False

                    def fail_first_staging_cleanup(path, *args, **kwargs):
                        nonlocal failed_once
                        if (
                            not failed_once
                            and Path(path).name.startswith(f".review-staging-{run_id}-")
                        ):
                            failed_once = True
                            raise OSError("injected route staging cleanup failure")
                        return original_rmtree(path, *args, **kwargs)

                    patcher = mock.patch.object(
                        route_module.review_support.shutil,
                        "rmtree",
                        side_effect=fail_first_staging_cleanup,
                    )
                    expected = "artifact_staging_cleanup_failed"
                with patcher:
                    with self.assertRaises(DiscoveryError) as failed:
                        api.record_direction_decision(
                            self.repo,
                            run_id,
                            self._approved_direction_request(),
                            self.state,
                            self.constitution,
                            self.registry,
                        )
                self.assertEqual(failed.exception.reason_code, expected)
                self.assertFalse((run_root / "approval.json").exists())
                self.assertEqual(
                    list(run_root.parent.glob(f".review-staging-{run_id}-*")), []
                )
                with contextlib.closing(sqlite3.connect(self.registry)) as connection:
                    self.assertEqual(
                        connection.execute(
                            "SELECT COUNT(*) FROM research_discovery_approvals"
                        ).fetchone()[0],
                        0,
                    )
                    self.assertEqual(
                        connection.execute(
                            "SELECT COUNT(*) FROM research_discovery_events "
                            "WHERE event_type='human_direction_decision'"
                        ).fetchone()[0],
                        0,
                    )


if __name__ == "__main__":
    unittest.main()
