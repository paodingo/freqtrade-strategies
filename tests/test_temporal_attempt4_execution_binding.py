from __future__ import annotations

import sys
import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_ranging_short_temporal_campaign as temporal  # noqa: E402
import run_router_extraction_semantic_equivalence_campaign as harness  # noqa: E402
import windows_execution_paths as execution_paths  # noqa: E402


ATTEMPT_ID = "temporal-ablation-execution-attempt-4"


class TemporalAttempt4ExecutionBindingTest(unittest.TestCase):
    def test_runner_selects_the_independently_approved_attempt_four(self):
        self.assertEqual(temporal.ATTEMPT_ID, ATTEMPT_ID)

    def test_attempt_four_uses_a4_without_mutating_the_frozen_path_contract(self):
        contract = execution_paths.load_contract(ROOT)
        self.assertEqual(
            contract["contract_fingerprint"],
            "b7d580480bf828117461e18dc34dd592726839f862655eed1e6ea443b12e21d6",
        )
        self.assertNotIn(ATTEMPT_ID, contract["aliases"]["attempt"])
        plan = temporal.plan_short_execution(
            ROOT, "ranging-short-ablation-s01", "baseline", "A"
        )["plan"]
        self.assertEqual(plan["aliases"]["attempt_alias"], "a4")
        self.assertRegex(plan["namespace"], r"^\.runs/rtv2/a4/s01/b/a/[0-9a-f]{10}$")

    def test_attempt_four_workers_use_the_short_namespace_factory(self):
        temporal.configure_harness(ROOT, "ranging-short-ablation-s01")
        self.assertIsNotNone(harness.SHORT_NAMESPACE_FACTORY)
        self.assertEqual(harness.CONTAMINATED_ROOTS, ())

    def test_attempt_four_approval_binds_all_frozen_contracts_and_zero_access(self):
        self.assertEqual(
            temporal.ATTEMPT_REQUEST_PATH.name,
            "ranging-short-branch-decision-review-v1-temporal-attempt-4-request.json",
        )
        self.assertEqual(
            temporal.ATTEMPT_APPROVAL_PATH.name,
            "ranging-short-branch-decision-review-v1-temporal-attempt-4-approval.json",
        )
        request = json.loads(
            (ROOT / temporal.ATTEMPT_REQUEST_PATH).read_text(encoding="utf-8")
        )
        approval = json.loads(
            (ROOT / temporal.ATTEMPT_APPROVAL_PATH).read_text(encoding="utf-8")
        )
        self.assertEqual(request["execution_attempt_id"], ATTEMPT_ID)
        self.assertEqual(approval["execution_attempt_id"], ATTEMPT_ID)
        self.assertEqual(approval["approval_status"], "approved")
        self.assertTrue(approval["execution_authorized"])
        self.assertEqual(approval["short_namespace_alias"], "a4")
        self.assertEqual(
            approval["candidate_identity_contract_fingerprint"],
            "fb620845db264886845ace8d00a139fa6d407c8fa29046e43d95f59e2b1d8c97",
        )
        self.assertEqual(
            approval["path_budget_contract_fingerprint"],
            "b7d580480bf828117461e18dc34dd592726839f862655eed1e6ea443b12e21d6",
        )
        self.assertEqual(
            approval["data_access"],
            {
                "development_only": True,
                "validation": "forbidden",
                "holdout": "forbidden",
            },
        )
        self.assertEqual(approval["budget"]["max_retries"], 0)
        self.assertTrue(
            temporal.checkout_stable_text_sha256_matches(
                ROOT / temporal.ATTEMPT_REQUEST_PATH, approval["request_sha256"]
            )
        )

    def test_attempt_four_plan_contains_16_unique_a4_namespaces(self):
        plans = [
            temporal.plan_short_execution(ROOT, slice_id, role, repetition)["plan"]
            for slice_id in temporal.SLICE_IDS
            for role in ("baseline", "candidate")
            for repetition in ("A", "B")
        ]
        self.assertEqual(len(plans), 16)
        self.assertEqual(len({plan["namespace"] for plan in plans}), 16)
        self.assertTrue(
            all(plan["aliases"]["attempt_alias"] == "a4" for plan in plans)
        )
        self.assertTrue(
            all(
                plan["path_budget"]["worst_absolute_path_chars"] <= 220
                for plan in plans
            )
        )
        self.assertTrue(
            all(not plan["namespace"].startswith(".runs/rtv2/a3/") for plan in plans)
        )

    def test_zero_backtest_preflight_validates_attempt_four_authority(self):
        checks = temporal.validate_authority(ROOT)
        self.assertTrue(checks["attempt_four_authorization"])
        self.assertTrue(checks["attempt_four_request_preserved"])
        self.assertTrue(checks["candidate_identity_propagation_contract"])
        self.assertTrue(checks["sealed_access_zero"])

    def test_completed_attempt_four_report_records_execution_contracts(self):
        result_path = (
            ROOT
            / "research/analysis/ranging-short-temporal-review-v1/"
            "temporal-contribution-result.json"
        )
        if not result_path.is_file():
            self.skipTest("Attempt 4 has not executed in this worktree")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertIn("path_budget_contract_fingerprint", result)
        self.assertIn("candidate_identity_contract_fingerprint", result)
        self.assertIn("historical_execution_results_read", result)
        self.assertEqual(
            result["path_budget_contract_fingerprint"],
            "b7d580480bf828117461e18dc34dd592726839f862655eed1e6ea443b12e21d6",
        )
        self.assertEqual(
            result["candidate_identity_contract_fingerprint"],
            "fb620845db264886845ace8d00a139fa6d407c8fa29046e43d95f59e2b1d8c97",
        )
        self.assertFalse(result["historical_execution_results_read"])


if __name__ == "__main__":
    unittest.main()
