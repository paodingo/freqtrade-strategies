from __future__ import annotations

import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_ranging_short_temporal_campaign as temporal
import run_router_extraction_semantic_equivalence_campaign as comparator
import windows_execution_paths as execution_paths


class TemporalCandidateIdentityPropagationTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(temporal, "load_identity_propagation_contract"))
        self.assertTrue(hasattr(temporal, "role_identity_contract"))
        self.contract = temporal.load_identity_propagation_contract(ROOT)

    def runtime_run(self, role: str, repetition: str, pid: int) -> dict:
        if role == "baseline":
            role_contract = self.contract["role_identities"]["baseline"]
            strategy_class = role_contract["strategy_class"]
            source_path = role_contract["source_path"]
            source_sha256 = role_contract["source_sha256"]
            extras = {}
        else:
            role_contract = self.contract["role_identities"]["candidate"]
            strategy_class = role_contract["candidate_class"]
            source_path = role_contract["candidate_path"]
            source_sha256 = role_contract["candidate_source_sha256"]
            extras = {
                "candidate_manifest_sha256": role_contract["candidate_manifest_sha256"],
                "candidate_experiment_id": role_contract["experiment_id"],
                "approved_ablation_unit": role_contract["approved_ablation_unit"],
            }
        projection = {
            "schema_version": "runtime_identity_projection_v1",
            "role": role,
            "strategy_class": strategy_class,
            "module_name": strategy_class,
            "module_path": str((ROOT / source_path).resolve()),
            "source_path": source_path,
            "source_sha256": source_sha256,
            "dependency_path": "strategies/regime_aware_base.py",
            "dependency_sha256": temporal.branch.BASE_SHA256,
            "pid": pid,
            "execution_run_id": f"s01-{role}-{repetition}",
            "runtime_versions": {"python": "3.12.13", "freqtrade": "2025.8", "ccxt": "4.5.64"},
            "experiment_id": 1,
            "identity_propagation_contract_fingerprint": self.contract["contract_fingerprint"],
            **extras,
        }
        return {
            "role": role,
            "repetition": repetition,
            "runtime_identity_projection": projection,
            "pid": pid,
        }

    def test_frozen_candidate_identity_is_injected_into_short_execution_manifest_input(self):
        identity = temporal.short_execution_identity(
            ROOT, "ranging-short-ablation-s01", "candidate", "A"
        )
        expected = self.contract["role_identities"]["candidate"]
        self.assertEqual(identity["runtime_identity_contract"], expected)
        self.assertEqual(
            set(expected),
            {
                "role",
                "candidate_class",
                "candidate_path",
                "candidate_source_sha256",
                "candidate_manifest_path",
                "candidate_manifest_sha256",
                "experiment_id",
                "approved_ablation_unit",
                "identity_propagation_contract_fingerprint",
            },
        )

    def test_bound_attempt_manifest_preserves_the_role_identity_contract(self):
        full_identity = temporal.short_execution_identity(
            ROOT, "ranging-short-ablation-s01", "candidate", "A", "a" * 16
        )
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            namespace = repo / "n"
            namespace.mkdir()
            for name in ("raw.json", "normalized.json", "runner.json"):
                (namespace / name).write_text("{}\n", encoding="utf-8")
            plan = {
                "namespace": "n",
                "execution_id": "a" * 16,
                "execution_short_id": "b" * 10,
                "alias_registry": "aliases.json",
                "aliases": {
                    "campaign_alias": "rtv2",
                    "attempt_alias": "a3",
                    "slice_alias": "s01",
                    "role_alias": "c",
                    "repetition_alias": "a",
                },
                "path_budget": {
                    "relative_outputs": {
                        "raw_result": "raw.json",
                        "normalized_trades": "normalized.json",
                        "runner_report": "runner.json",
                    }
                },
            }
            manifest = execution_paths.build_execution_manifest(
                repo, plan, full_identity
            )
        self.assertIn("runtime_identity_contract", manifest)
        self.assertEqual(
            manifest["runtime_identity_contract"],
            self.contract["role_identities"]["candidate"],
        )

    def test_candidate_identity_missing_fields_fail_before_worker_launch(self):
        self.assertTrue(hasattr(temporal, "validate_identity_propagation_contract"))
        for field in (
            "candidate_class",
            "candidate_path",
            "candidate_source_sha256",
            "candidate_manifest_path",
            "candidate_manifest_sha256",
            "experiment_id",
            "approved_ablation_unit",
        ):
            with self.subTest(field=field):
                broken = json.loads(json.dumps(self.contract))
                broken["role_identities"]["candidate"].pop(field)
                with self.assertRaisesRegex(temporal.TemporalExecutionInvalid, "candidate_identity_contract_missing"):
                    temporal.validate_identity_propagation_contract(ROOT, broken)

    def test_missing_contract_blocks_before_backtest_process_launch(self):
        with (
            mock.patch.object(
                temporal,
                "load_identity_propagation_contract",
                side_effect=temporal.TemporalExecutionInvalid(
                    "candidate_identity_contract_missing"
                ),
            ),
            mock.patch.object(temporal.subprocess, "run") as process_run,
        ):
            with self.assertRaisesRegex(
                temporal.TemporalExecutionInvalid,
                "candidate_identity_contract_missing",
            ):
                temporal.run_fresh(
                    ROOT, "ranging-short-ablation-s01", "candidate", "A"
                )
        process_run.assert_not_called()

    def test_baseline_uses_an_independent_identity_contract(self):
        baseline = self.contract["role_identities"]["baseline"]
        self.assertEqual(set(baseline), {
            "role",
            "strategy_class",
            "source_path",
            "source_sha256",
            "identity_propagation_contract_fingerprint",
        })
        result = comparator.audit_runtime_identity(
            self.runtime_run("baseline", "A", 101),
            self.runtime_run("baseline", "B", 102),
            "baseline",
            baseline,
        )
        self.assertTrue(result["passed"])

    def test_candidate_run_a_and_b_match_the_same_frozen_identity(self):
        expected = self.contract["role_identities"]["candidate"]
        result = comparator.audit_runtime_identity(
            self.runtime_run("candidate", "A", 201),
            self.runtime_run("candidate", "B", 202),
            "candidate",
            expected,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["expected_identity"], expected)

    def test_correct_temporal_candidate_does_not_use_router_default(self):
        original_source = comparator.CANDIDATE_SOURCE
        original_sha = comparator.CANDIDATE_SHA256
        try:
            comparator.CANDIDATE_SOURCE = "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"
            comparator.CANDIDATE_SHA256 = "bee68e27b345a93a1fe8481275e365829c986f700d2719fdd10ffd907e1dffa1"
            result = comparator.audit_runtime_identity(
                self.runtime_run("candidate", "A", 301),
                self.runtime_run("candidate", "B", 302),
                "candidate",
                self.contract["role_identities"]["candidate"],
            )
        finally:
            comparator.CANDIDATE_SOURCE = original_source
            comparator.CANDIDATE_SHA256 = original_sha
        self.assertTrue(result["passed"])

    def test_wrong_candidate_is_still_rejected(self):
        run_a = self.runtime_run("candidate", "A", 401)
        run_b = self.runtime_run("candidate", "B", 402)
        run_b["runtime_identity_projection"]["source_sha256"] = "0" * 64
        with self.assertRaises(comparator.RuntimeIdentityFailure) as caught:
            comparator.audit_runtime_identity(
                run_a,
                run_b,
                "candidate",
                self.contract["role_identities"]["candidate"],
            )
        self.assertEqual(caught.exception.reason_code, "runtime_candidate_identity_mismatch")

    def test_missing_parent_contract_is_rejected_deterministically(self):
        with self.assertRaises(comparator.RuntimeIdentityFailure) as caught:
            comparator.audit_runtime_identity(
                self.runtime_run("candidate", "A", 501),
                self.runtime_run("candidate", "B", 502),
                "candidate",
                {},
            )
        self.assertEqual(caught.exception.reason_code, "candidate_identity_contract_missing")

    def test_identity_authority_does_not_read_historical_attempt_or_registry(self):
        source = inspect.getsource(temporal.load_identity_propagation_contract)
        self.assertNotIn("REGISTRY", source)
        self.assertNotIn("campaign-stopped", source)
        self.assertNotIn("ATTEMPT", source)
        self.assertEqual(
            self.contract["identity_authority"],
            ["compiled_campaign_frozen_inputs", "candidate_manifest", "current_source_files"],
        )

    def test_campaign_candidate_and_attempt_three_stop_are_immutable_inputs(self):
        protected = self.contract["protected_input_sha256"]
        for relative, expected in protected.items():
            self.assertTrue(
                temporal.checkout_stable_text_sha256_matches(ROOT / relative, expected)
            )
        stop_paths = (
            "research/analysis/ranging-short-temporal-review-v1/"
            "campaign-stopped-attempt-3.json",
            "research/director/compiled/"
            "ranging-short-branch-decision-review-v1-temporal-v2/execution/"
            "campaign-stopped-attempt-3.json",
            "reports/audits/ranging-short-temporal-review-v1/"
            "campaign-stopped-attempt-3.json",
        )
        for relative in stop_paths:
            self.assertTrue(
                temporal.checkout_stable_text_sha256_matches(
                    ROOT / relative,
                    "734e9a6d46122daa201798c92108c56a6048ee8d39f318972e217f8c124d2b71",
                )
            )
        stopped = json.loads((ROOT / stop_paths[0]).read_text(encoding="utf-8"))
        self.assertEqual(stopped["status"], "temporal_ablation_execution_invalid")
        self.assertEqual(stopped["completed_backtest_calls"], 4)
        self.assertEqual(stopped["research_verdict"], "not_evaluated")

    def test_root_cause_amendment_preserves_attempt_three_and_records_implementation_error(self):
        relative_paths = (
            "research/analysis/ranging-short-temporal-review-v1/"
            "campaign-stopped-attempt-3-root-cause-amendment.json",
            "research/director/compiled/"
            "ranging-short-branch-decision-review-v1-temporal-v2/execution/"
            "campaign-stopped-attempt-3-root-cause-amendment.json",
            "reports/audits/ranging-short-temporal-review-v1/"
            "campaign-stopped-attempt-3-root-cause-amendment.json",
        )
        amendments = [
            json.loads((ROOT / relative).read_text(encoding="utf-8"))
            for relative in relative_paths
        ]
        self.assertTrue(all(item == amendments[0] for item in amendments[1:]))
        amendment = amendments[0]
        self.assertEqual(amendment["root_cause"]["class"], "implementation_error")
        self.assertEqual(
            amendment["root_cause"]["reason"],
            "frozen_candidate_identity_not_propagated_to_parent_comparator",
        )
        self.assertEqual(
            amendment["original_attempt_preserved"],
            {
                "status": "temporal_ablation_execution_invalid",
                "reason": "runtime_candidate_identity_mismatch",
                "completed_backtests": 4,
                "research_verdict": "not_evaluated",
                "max_retries": 0,
                "attempt_tree_file_count": 81,
                "attempt_tree_bytes": 1576530,
                "attempt_tree_sha256": "c279c499b904f53d19372367e867363ecdb6034bf3bb8dcf473d022aa50a7f05",
            },
        )
        self.assertEqual(amendment["backtests_run_during_fix"], 0)
        self.assertFalse(amendment["campaign_fingerprint_changed"])


if __name__ == "__main__":
    unittest.main()
