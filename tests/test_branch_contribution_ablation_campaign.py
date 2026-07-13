from __future__ import annotations

import importlib
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_branch_contribution_ablation_campaign as campaign


class BranchContributionAblationCampaignTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        campaign.configure_harness()
        campaign.harness.load_strategy = campaign.load_strategy
        campaign.harness.signal_mask = campaign.signal_mask
        campaign.harness.backtest_campaign = campaign.backtest_campaign

    def test_authority_and_ast_allowlist_pass(self):
        checks = campaign.validate_authority(ROOT)
        self.assertTrue(all(checks.values()))
        self.assertEqual(campaign.validate_candidate_ast(ROOT)["final_zero_gates"], 1)

    def test_only_one_candidate_exists_for_campaign(self):
        candidates = list((ROOT / "research/candidates/branch-contribution-ablation-v1").rglob("*.py"))
        self.assertEqual([path.relative_to(ROOT).as_posix() for path in candidates], [campaign.CANDIDATE_SOURCE])

    def test_gate_preserves_tag_and_other_short_branch(self):
        strategy_class, _, _ = campaign.load_strategy(ROOT, "candidate")
        parent = strategy_class.__mro__[1]
        frame = pd.DataFrame({"enter_short": [1, 1, 0], "enter_tag": ["ranging_short", "trending_short", None], "enter_long": [0, 0, 1]})
        with mock.patch.object(parent, "populate_entry_trend", return_value=frame.copy()):
            result = strategy_class({}).populate_entry_trend(frame.copy(), {"pair": "BTC/USDT:USDT"})
        self.assertEqual(result["enter_short"].tolist(), [0, 1, 0])
        self.assertEqual(result["enter_long"].tolist(), [0, 0, 1])
        self.assertEqual(result["enter_tag"].tolist(), ["ranging_short", "trending_short", None])
        self.assertEqual(result["research_ranging_short_entry_pre_gate"].tolist(), [1, 0, 0])

    def test_budget_and_forbidden_data_are_frozen(self):
        approval = json.loads((ROOT / campaign.APPROVAL).read_text(encoding="utf-8"))
        self.assertEqual(approval["budget"], {"max_candidates": 1, "max_backtest_calls": 8, "max_wall_clock_minutes": 120})
        self.assertEqual((approval["data_access"]["validation"], approval["data_access"]["holdout"]), ("forbidden", "forbidden"))
        self.assertEqual(approval["data_access"]["temporal_slices"], "forbidden")

    def test_attempt_2_is_independent_and_cannot_create_candidate_or_retry(self):
        approval = json.loads((ROOT / campaign.ATTEMPT_APPROVAL).read_text(encoding="utf-8"))
        authorization = json.loads((ROOT / campaign.ATTEMPT_AUTHORIZATION).read_text(encoding="utf-8"))
        self.assertEqual(approval["execution_attempt_id"], "ablation-execution-attempt-2")
        self.assertTrue(approval["independent_human_job_attempt"])
        self.assertFalse(approval["automatic_retry"])
        self.assertFalse(approval["candidate_creation_allowed"])
        self.assertEqual(approval["budget"], {"max_backtest_calls": 8, "max_wall_clock_minutes": 120, "max_retries": 0})
        self.assertEqual((approval["validation_accesses"], approval["holdout_accesses"]), (0, 0))
        self.assertEqual(authorization["candidate_source_sha256"], campaign.CANDIDATE_SHA256)
        self.assertEqual(authorization["single_variable_diff_allowlist"], campaign.ALLOWED_DIFF)
        self.assertEqual(campaign.ATTEMPT_ID, "ablation-execution-attempt-2")
        self.assertNotEqual(campaign.RESULT_ROOT.as_posix(), "research/results/branch-contribution-ablation-v1/ranging-short-entry/execution-attempt-1")

    def test_deterministic_classification_taxonomy(self):
        def result(direction, signals=2, removed=1):
            return {"contribution_direction": direction, "signals": {"baseline_pre_gate": signals}, "trades": {"removed": removed, "added_or_shifted": 0}}
        self.assertEqual(campaign.classify({"btc": result("branch_negative"), "eth": result("branch_negative")}), "branch_negative_contributor")
        self.assertEqual(campaign.classify({"btc": result("branch_positive"), "eth": result("branch_positive")}), "branch_positive_contributor")
        self.assertEqual(campaign.classify({"btc": result("branch_negative"), "eth": result("branch_positive")}), "branch_mixed_regime_dependent")
        self.assertEqual(campaign.classify({"btc": result("neutral", removed=0), "eth": result("neutral", removed=0)}), "branch_redundant")
        self.assertEqual(campaign.classify({"btc": result("neutral", signals=0), "eth": result("neutral")}), "branch_contribution_inconclusive")

    def test_next_proposal_stays_pending(self):
        proposal = campaign.next_proposal("branch_negative_contributor", {"btc": {}, "eth": {}})
        self.assertEqual(proposal["risk_class"], "medium")
        self.assertEqual(proposal["status"], "pending_human_review")
        self.assertFalse(proposal["proposed_method"]["execute_automatically"])
        self.assertEqual(len(proposal["semantic_fingerprint"]), 64)

    def test_stopped_attempt_is_not_a_research_verdict(self):
        stopped = json.loads((ROOT / "research/analysis/branch-contribution-ablation-v1/campaign-stopped.json").read_text(encoding="utf-8"))
        self.assertEqual(stopped["status"], "ablation_execution_invalid")
        self.assertEqual(stopped["research_verdict"], "not_evaluated")
        self.assertFalse(stopped["backtest_engine_started"])
        self.assertEqual(stopped["completed_backtest_calls"], 0)
        self.assertFalse(stopped["retry_policy"]["automatic_retry_permitted"])
        self.assertIsNone(stopped["contribution_classification"])


if __name__ == "__main__":
    unittest.main()
