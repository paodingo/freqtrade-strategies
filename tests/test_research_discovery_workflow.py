import contextlib
import copy
import io
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import fingerprint, open_director_registry  # noqa: E402
from research_discovery_common import DiscoveryError  # noqa: E402
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
            "state_conflicts": [],
            "allowed_research_scope": {
                "approved_market": "Binance USD-M Futures",
                "baseline_pair": "BTC/USDT:USDT",
                "baseline_timeframe": "1h",
                "human_approved_additional_pairs": ["ETH/USDT:USDT"],
                "candidate_creation": False,
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
                },
                {
                    "dataset_id": "futures-dev-eth",
                    "intended_use": "development_descriptive_cross_pair_generalization_only",
                    "agent_visibility": "full",
                    "pairs": ["ETH/USDT:USDT"],
                    "timeframes": ["1h", "4h"],
                    "path": "research/data/snapshots/futures-dev-eth/manifest.yaml",
                },
                {
                    "dataset_id": "futures-validation-btc",
                    "intended_use": "validation",
                    "agent_visibility": "controlled",
                    "pairs": ["BTC/USDT:USDT"],
                    "timeframes": ["1h", "4h"],
                    "path": "research/data/snapshots/futures-validation-btc/manifest.yaml",
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
        self.state["state_fingerprint"] = fingerprint(self.state)
        self.constitution = {
            "schema_version": "research-constitution-v1",
            "constitution_id": "research-director-governance-v1",
            "status": "approved",
            "approval_status": "approved",
            "approved_version": 1,
        }
        self.source_policy = {
            "schema_version": "research-source-policy-v1",
            "forbidden_inputs": [
                "validation_result",
                "holdout",
                "private_api",
                "secret",
                "live_account",
                "unapproved_dataset",
            ],
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

    def _trigger(self) -> dict[str, object]:
        return create_trigger(
            event_type="manual_request",
            event_ref=EVENT_REF,
            state=self.state,
            constitution=self.constitution,
            source_policy=self.source_policy,
            created_at=CREATED_AT,
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
        stale_state["state_fingerprint"] = "9" * 64
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
