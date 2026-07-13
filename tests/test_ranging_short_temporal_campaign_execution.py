from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_ranging_short_temporal_campaign as campaign


class RangingShortTemporalCampaignExecutionTest(unittest.TestCase):
    def test_attempt_two_uses_an_independent_empty_namespace(self):
        self.assertTrue(hasattr(campaign, "ensure_attempt_namespace_empty"))
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            original = (
                repo
                / campaign.RESULT_ROOT
                / "ranging-short-ablation-s01"
                / "temporal-branch-contribution-review-v1"
            )
            original.mkdir(parents=True)
            campaign.ensure_attempt_namespace_empty(repo)

            current = (
                repo
                / campaign.RESULT_ROOT
                / "ranging-short-ablation-s02"
                / campaign.ATTEMPT_ID
            )
            current.mkdir(parents=True)
            with self.assertRaisesRegex(campaign.TemporalExecutionInvalid, "attempt_output_namespace_not_empty"):
                campaign.ensure_attempt_namespace_empty(repo)

    def test_attempt_two_human_authorization_matches_frozen_authority(self):
        self.assertEqual(campaign.ATTEMPT_ID, "temporal-ablation-execution-attempt-2")
        approval = json.loads((ROOT / campaign.ATTEMPT_APPROVAL_PATH).read_text(encoding="utf-8"))
        self.assertEqual(approval["execution_attempt_id"], campaign.ATTEMPT_ID)
        self.assertEqual(approval["campaign_fingerprint"], campaign.CAMPAIGN_FINGERPRINT)
        self.assertEqual(
            approval["runtime_asset_manifest_fingerprint"],
            "fa9bb13132dad44344e91d262c5fd38473e2cbed7a930e72f677eb7a0ce11f64",
        )
        self.assertTrue(approval["execution_authorized"])
        self.assertEqual(approval["budget"], {
            "max_backtest_calls": 16,
            "max_wall_clock_minutes": 240,
            "max_retries": 0,
        })
        self.assertEqual(approval["data_access"], {
            "development_only": True,
            "validation": "forbidden",
            "holdout": "forbidden",
        })

    def test_attempt_two_has_independent_registry_identity(self):
        self.assertTrue(hasattr(campaign, "RUN_ID"))
        self.assertEqual(campaign.RUN_ID, "ranging-short-temporal-review-v1-attempt-2")
        self.assertNotEqual(campaign.ATTEMPT_APPROVAL_PATH, campaign.APPROVAL_PATH)
        stopped = json.loads(
            (ROOT / "research/analysis/ranging-short-temporal-review-v1/campaign-stopped.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(stopped["execution_attempt_id"], campaign.ORIGINAL_ATTEMPT_ID)
        self.assertEqual(stopped["status"], "temporal_ablation_execution_invalid")

    def test_human_approval_matches_frozen_authority(self):
        approval = json.loads((ROOT / campaign.APPROVAL_PATH).read_text(encoding="utf-8"))
        authorization = json.loads((ROOT / campaign.AUTHORIZATION_PATH).read_text(encoding="utf-8"))
        self.assertTrue(approval["execution_authorized"])
        self.assertEqual(approval["compiled_campaign_fingerprint"], campaign.CAMPAIGN_FINGERPRINT)
        self.assertEqual(approval["slice_policy_fingerprint"], campaign.SLICE_POLICY_FINGERPRINT)
        self.assertEqual(authorization["approved_compiled_fingerprint"], campaign.CAMPAIGN_FINGERPRINT)
        self.assertEqual(authorization["approved_slice_policy_fingerprint"], campaign.SLICE_POLICY_FINGERPRINT)
        self.assertFalse(authorization["candidate_creation_allowed"])
        self.assertEqual((authorization["validation_accesses_authorized"], authorization["holdout_accesses_authorized"]), (0, 0))

    def test_frozen_queue_is_exactly_four_by_four(self):
        queue = json.loads((ROOT / campaign.QUEUE_PATH).read_text(encoding="utf-8"))
        self.assertEqual(len(queue), 16)
        expected = [
            (f"ranging-short-ablation-s0{number}", role, repetition)
            for number in range(1, 5)
            for role in ("baseline", "candidate")
            for repetition in ("RUN-A", "RUN-B")
        ]
        self.assertEqual([(item["slice_id"], item["role"], item["repetition"]) for item in queue], expected)
        self.assertTrue(all(item["cache"] == "none" and item["network_access"] == "forbidden" for item in queue))
        self.assertTrue(all(item["validation_accesses"] == item["holdout_accesses"] == 0 for item in queue))

    def test_slice_policy_has_exact_non_overlapping_boundaries(self):
        policy = campaign.load_document(ROOT / campaign.SLICE_POLICY_PATH)
        slices = policy["slices"]
        self.assertEqual([item["evaluation_1h_candle_count"] for item in slices], [1250] * 4)
        self.assertEqual([item["evaluation_start"] for item in slices], [
            "2024-02-03T08:00:00Z",
            "2024-03-26T10:00:00Z",
            "2024-05-17T12:00:00Z",
            "2024-07-08T14:00:00Z",
        ])
        self.assertEqual([item["evaluation_end_exclusive"] for item in slices], [
            "2024-03-26T10:00:00Z",
            "2024-05-17T12:00:00Z",
            "2024-07-08T14:00:00Z",
            "2024-08-29T16:00:00Z",
        ])
        self.assertTrue(all(left["evaluation_end_exclusive"] == right["evaluation_start"] for left, right in zip(slices, slices[1:])))
        self.assertEqual(policy["slice_policy_fingerprint"], campaign.SLICE_POLICY_FINGERPRINT)

    def test_backtest_campaign_uses_exact_slice_timerange(self):
        fixed = campaign.backtest_campaign("ranging-short-ablation-s01", "baseline")["fixed_backtest"]
        self.assertEqual(fixed["timerange"], "1706947200-1711447200")
        self.assertEqual(fixed["pairs"], ["BTC/USDT:USDT"])
        self.assertEqual(fixed["timeframe"], "1h")
        self.assertEqual(fixed["fee"], "0.0004")
        self.assertEqual(fixed["dataset_id"], campaign.DATASET_ID)

    def test_execution_preflight_requires_repo_local_runtime_asset(self):
        self.assertEqual(
            campaign.LOCAL_LEVERAGE_TIER_PATH.as_posix(),
            ".venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json",
        )
        self.assertNotEqual(
            ROOT / campaign.LOCAL_LEVERAGE_TIER_PATH,
            campaign._runtime_root() / campaign.LOCAL_LEVERAGE_TIER_PATH,
        )

    def test_slice_classification_is_deterministic_and_risk_aware(self):
        baseline = {"max_drawdown_abs": 100.0}
        negative = {"total_return_abs": 10.0, "profit_factor": 0.1, "max_drawdown_abs": -2.0, "max_drawdown_ratio": -0.001}
        positive = {"total_return_abs": -10.0, "profit_factor": -0.1, "max_drawdown_abs": 2.0, "max_drawdown_ratio": 0.001}
        conflicted = {"total_return_abs": 10.0, "profit_factor": 0.1, "max_drawdown_abs": 20.0, "max_drawdown_ratio": 0.01}
        self.assertEqual(campaign.classify_slice(2, 1, 0, baseline, negative), "branch_negative_contributor")
        self.assertEqual(campaign.classify_slice(2, 1, 0, baseline, positive), "branch_positive_contributor")
        self.assertEqual(campaign.classify_slice(2, 1, 0, baseline, conflicted), "branch_mixed_regime_dependent")
        self.assertEqual(campaign.classify_slice(0, 0, 0, baseline, negative), "branch_contribution_inconclusive")
        self.assertEqual(campaign.classify_slice(2, 0, 0, baseline, negative), "branch_redundant")

    def test_temporal_consistency_requires_three_slices_and_no_reverse_risk(self):
        def item(label: str, dd: float = -1.0):
            return {"classification": label, "candidate_minus_baseline": {"max_drawdown_abs": dd, "max_drawdown_ratio": -0.001}, "baseline_metrics": {"max_drawdown_abs": 100.0}}
        negative = {f"s{i}": item("branch_negative_contributor") for i in range(4)}
        self.assertEqual(campaign.classify_temporal(negative), "branch_negative_contributor_temporally_consistent")
        negative["s4"] = item("branch_positive_contributor")
        self.assertEqual(campaign.classify_temporal(negative), "branch_mixed_temporal_dependency")
        reverse = {f"s{i}": item("branch_negative_contributor") for i in range(4)}
        reverse["s4"] = item("branch_mixed_regime_dependent", 10.0)
        self.assertEqual(campaign.classify_temporal(reverse), "branch_contribution_temporally_inconclusive")

    def test_next_validation_proposal_stays_pending_and_unexecuted(self):
        proposal = campaign.next_proposal("branch_negative_contributor_temporally_consistent", ["evidence.json"])
        self.assertEqual(proposal["proposal_id"], "ranging-short-btc-validation-authorization-review-v1")
        self.assertEqual(proposal["risk_class"], "high")
        self.assertEqual(proposal["status"], "pending_human_review")
        self.assertFalse(proposal["proposed_method"]["execute_automatically"])
        self.assertEqual(proposal["data_scope"]["max_validation_accesses_requested"], 1)
        self.assertEqual(len(proposal["semantic_fingerprint"]), 64)

    def test_stopped_attempt_has_no_research_verdict_or_retry(self):
        stopped = json.loads(
            (ROOT / "research/analysis/ranging-short-temporal-review-v1/campaign-stopped.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(stopped["status"], "temporal_ablation_execution_invalid")
        self.assertEqual(stopped["reason_code"], "runtime_execution_asset_missing")
        self.assertEqual((stopped["attempted_backtest_calls"], stopped["completed_backtest_calls"]), (1, 0))
        self.assertEqual(stopped["remaining_backtest_calls_not_started"], 15)
        self.assertEqual(stopped["research_verdict"], "not_evaluated")
        self.assertIsNone(stopped["temporal_classification"])
        self.assertFalse(stopped["retry_policy"]["automatic_retry_permitted"])
        self.assertFalse(stopped["retry_policy"]["retry_performed"])
        self.assertEqual((stopped["validation_accesses"], stopped["holdout_accesses"]), (0, 0))

    def test_registry_preserves_stopped_attempt_without_result_claim(self):
        registry = json.loads((ROOT / campaign.REGISTRY_EXPORT_PATH).read_text(encoding="utf-8"))
        rows = registry["tables"]["research_campaign_runs"]
        row = next(item for item in rows if item["run_id"] == "ranging-short-temporal-review-v1-stopped")
        self.assertEqual(row["status"], "stopped")
        self.assertEqual(row["result_code"], "runtime_execution_asset_missing")
        self.assertEqual((row["validation_accesses"], row["holdout_accesses"]), (0, 0))
        self.assertEqual(row["strategy_modified"], 0)


if __name__ == "__main__":
    unittest.main()
