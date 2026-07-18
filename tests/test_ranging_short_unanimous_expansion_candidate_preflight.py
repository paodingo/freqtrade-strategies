import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_ranging_short_unanimous_expansion_candidate_preflight as preflight
from research_director_common import load_document, sha256_file


class UnanimousExpansionCandidatePreflightTest(unittest.TestCase):
    def test_human_authority_allows_one_candidate_and_zero_backtests(self):
        approval = load_document(ROOT / preflight.APPROVAL_PATH)
        authority = approval["authority"]
        self.assertEqual(approval["approval_status"], "approved")
        self.assertEqual(approval["approver_type"], "human_user")
        self.assertTrue(authority["create_candidate"])
        self.assertEqual(authority["maximum_candidates"], 1)
        self.assertEqual(authority["maximum_coverage_preflights"], 1)
        self.assertFalse(authority["run_backtest"])
        self.assertFalse(authority["read_outcome_metrics"])
        self.assertFalse(authority["search_thresholds"])
        self.assertFalse(authority["access_validation"])
        self.assertFalse(authority["access_holdout"])

    def test_candidate_is_hash_bound_and_single_variable(self):
        approval = load_document(ROOT / preflight.APPROVAL_PATH)
        binding = approval["candidate_binding"]
        manifest = load_document(ROOT / binding["manifest_path"])
        self.assertEqual(manifest["candidate_count"], 1)
        self.assertEqual(manifest["gate"]["blocked_topology"], "U-U-U")
        self.assertFalse(manifest["implementation_contract"]["continuous_thresholds"])
        self.assertFalse(manifest["implementation_contract"]["outcome_metrics_used"])
        self.assertEqual(sha256_file(ROOT / binding["source_path"]), binding["source_sha256"])
        self.assertEqual(sha256_file(ROOT / binding["manifest_path"]), binding["manifest_sha256"])

    def test_exact_development_rehydration_is_recorded(self):
        audit = load_document(ROOT / preflight.REHYDRATION_PATH)
        self.assertTrue(audit["passed"])
        self.assertFalse(audit["network_accessed"])
        self.assertEqual(audit["validation_accesses"], 0)
        self.assertEqual(audit["holdout_accesses"], 0)
        self.assertEqual(len(audit["files"]), 4)
        self.assertTrue(all(item["passed"] for item in audit["files"]))
        self.assertEqual(
            {item["file_id"]: item["actual"]["rows"] for item in audit["files"]},
            {"1h-futures": 5800, "4h-futures": 1450, "8h-mark": 725, "8h-funding_rate": 725},
        )

    def test_coverage_preflight_replays_exact_partition_and_gate(self):
        result = load_document(ROOT / preflight.PREFLIGHT_PATH)
        self.assertTrue(result["gate"]["passed"])
        self.assertTrue(all(result["gate"]["checks"].values()))
        self.assertEqual(result["direction_counts"], {"D-D-D": 2, "U-U-D": 5, "U-U-U": 5})
        self.assertEqual(result["totals"]["pre_gate_signals"], 12)
        self.assertEqual(result["totals"]["blocked_signals"], 5)
        self.assertEqual(result["totals"]["candidate_remaining_signals"], 7)
        self.assertEqual(result["alignment_violation_count"], 0)
        self.assertEqual(len(result["rows"]), 12)
        for row in result["rows"]:
            self.assertTrue(all(row["checks"].values()))
            self.assertEqual(row["blocked"], row["topology"] == "U-U-U")

    def test_execution_boundaries_and_next_proposal(self):
        result = load_document(ROOT / preflight.PREFLIGHT_PATH)
        execution = result["execution"]
        self.assertEqual(execution["backtest_calls"], 0)
        self.assertFalse(execution["outcome_metrics_read"])
        self.assertFalse(execution["threshold_search_run"])
        self.assertFalse(execution["formal_strategy_modified"])
        proposal = load_document(ROOT / preflight.NEXT_PROPOSAL_PATH)
        self.assertEqual(proposal["status"], "pending_human_review")
        self.assertEqual(proposal["execution_budget"]["candidate_creations"], 0)
        self.assertEqual(proposal["execution_budget"]["backtest_calls"], 8)
        self.assertIn("validation", proposal["forbidden_scope"])
        self.assertIn("holdout", proposal["forbidden_scope"])

    def test_state_and_registry_record_completion(self):
        state = load_document(ROOT / preflight.STATE_PATH)
        current = state["ranging_short_router_unanimous_expansion_candidate_preparation"]
        self.assertEqual(current["status"], "completed_candidate_frozen")
        self.assertEqual(current["candidate_count"], 1)
        self.assertEqual(current["backtest_calls"], 0)
        registry = load_document(ROOT / preflight.REGISTRY_EXPORT_PATH)
        rows = [
            row
            for row in registry["tables"]["research_campaign_runs"]
            if row["run_id"] == f"{preflight.PROPOSAL_ID}-coverage-preflight-1"
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["candidate_created"], 1)
        self.assertEqual(rows[0]["strategy_modified"], 0)
        self.assertEqual(rows[0]["validation_accesses"], 0)
        self.assertEqual(rows[0]["holdout_accesses"], 0)

    def test_report_is_chinese(self):
        report = (ROOT / preflight.REPORT_PATH).read_text(encoding="utf-8")
        self.assertIn("U-U-U Candidate 准备报告", report)
        self.assertIn("阻止 `U-U-U` 的 5 个信号并保留 7 个", report)
        self.assertIn("没有运行回测", report)


if __name__ == "__main__":
    unittest.main()
