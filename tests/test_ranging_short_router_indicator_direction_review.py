import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_ranging_short_router_indicator_direction_review as review
from research_director_common import load_document, sha256_file


class RouterIndicatorDirectionReviewTest(unittest.TestCase):
    def test_authority_is_human_approved_and_zero_execution(self):
        checks = review.validate_authority(ROOT)
        self.assertTrue(all(checks.values()))
        approval = load_document(ROOT / review.APPROVAL_PATH)
        authority = approval["authority"]
        self.assertFalse(authority["read_outcome_metrics"])
        self.assertFalse(authority["create_candidate"])
        self.assertFalse(authority["run_backtest"])
        self.assertFalse(authority["search_thresholds"])
        self.assertFalse(authority["access_validation"])
        self.assertFalse(authority["access_holdout"])

    def test_contract_uses_completed_candles_and_no_numeric_cutoff(self):
        contract = load_document(ROOT / review.CONTRACT_PATH)
        self.assertEqual(
            contract["clock_semantics"]["required_relation"],
            "informative_available_at <= signal_decision_at",
        )
        self.assertEqual(contract["inputs"]["order"], ["adx", "bb_width", "atr"])
        self.assertEqual(contract["categorization"]["U"], "current > previous")
        self.assertEqual(contract["categorization"]["D"], "current < previous")
        self.assertIsNone(contract["categorization"]["epsilon"])
        self.assertIsNone(contract["categorization"]["continuous_cutoff"])
        self.assertEqual(
            contract["future_single_variable_gate"]["blocked_topology"],
            "U-U-U",
        )
        self.assertFalse(
            contract["future_single_variable_gate"]["outcome_metrics_used"]
        )

    def test_all_twelve_rows_are_lag_safe(self):
        audit = load_document(ROOT / review.ALIGNMENT_PATH)
        self.assertEqual(audit["row_count"], 12)
        self.assertTrue(audit["all_rows_lag_safe"])
        self.assertEqual(audit["lookahead_violation_count"], 0)
        self.assertEqual(audit["violations"], [])
        self.assertFalse(audit["raw_development_data_hydrated"])
        self.assertTrue(audit["raw_replay_required_before_candidate_creation"])
        for row in audit["rows"]:
            self.assertTrue(all(row["checks"].values()))

    def test_direction_is_a_nonredundant_three_way_partition(self):
        audit = load_document(ROOT / review.PARTITION_PATH)
        self.assertEqual(audit["current_router_level_counts"], {"R-R-R": 12})
        self.assertEqual(
            audit["direction_topology_counts"],
            {"D-D-D": 2, "U-U-D": 5, "U-U-U": 5},
        )
        self.assertEqual(audit["current_router_level_entropy_bits"], 0.0)
        self.assertGreater(audit["direction_topology_entropy_bits"], 1.4)
        self.assertTrue(audit["strict_partition_refinement"])
        self.assertTrue(audit["all_categories_meet_minimum_coverage_two"])
        self.assertFalse(audit["whole_branch_equivalent"])
        gate = audit["future_gate_preflight"]
        self.assertEqual(gate["blocked_pre_gate_signals"], 5)
        self.assertEqual(gate["retained_pre_gate_signals"], 7)
        self.assertTrue(gate["both_sides_nonzero"])

    def test_closed_threshold_and_duplicate_mechanisms_stay_closed(self):
        audit = load_document(ROOT / review.REDUNDANCY_PATH)
        self.assertEqual(
            audit["redundancy_decision"],
            "nonredundant_temporal_derivative_of_existing_router_inputs",
        )
        self.assertEqual(audit["closure_conflict_count"], 0)
        checks = audit["closure_checks"]
        self.assertFalse(checks["changes_closed_numeric_threshold"])
        self.assertFalse(checks["reopens_adjacent_threshold_search"])
        self.assertFalse(checks["uses_duplicate_signal_lifecycle"])
        self.assertFalse(checks["uses_time_slice_identity"])
        self.assertFalse(audit["outcome_metrics_read"])

    def test_candidate_feasibility_is_conditional_not_authorization(self):
        decision = load_document(ROOT / review.DECISION_PATH)
        self.assertEqual(
            decision["decision"],
            "conditionally_eligible_for_single_variable_candidate_preparation",
        )
        self.assertTrue(decision["structural_contract_valid"])
        self.assertEqual(
            decision["recommended_future_gate"]["gate_id"],
            "block_unanimous_router_indicator_expansion",
        )
        self.assertEqual(
            decision["recommended_future_gate"]["blocked_pre_gate_signals"], 5
        )
        self.assertEqual(
            decision["recommended_future_gate"]["retained_pre_gate_signals"], 7
        )
        self.assertFalse(decision["candidate_creation_authorized_now"])
        self.assertFalse(decision["backtest_authorized_now"])
        self.assertEqual(decision["next_proposal_status"], "pending_human_review")

    def test_next_proposal_requires_raw_replay_and_forbids_backtest(self):
        proposal = load_document(ROOT / review.NEXT_PROPOSAL_PATH)
        self.assertEqual(proposal["status"], "pending_human_review")
        self.assertEqual(proposal["approval_route"], "human_approval_required")
        self.assertEqual(proposal["execution_budget"]["candidate_creations"], 1)
        self.assertEqual(proposal["execution_budget"]["coverage_preflights"], 1)
        self.assertEqual(proposal["execution_budget"]["backtest_calls"], 0)
        self.assertIn("backtest", proposal["forbidden_scope"])
        self.assertIn("exact raw development data unavailable", proposal["fail_closed_conditions"])
        self.assertFalse(proposal["automatic_execution"])

    def test_packet_hashes_state_and_registry_are_bound(self):
        packet = load_document(ROOT / review.PACKET_PATH)
        mapping = {
            "contract": review.CONTRACT_PATH,
            "alignment": review.ALIGNMENT_PATH,
            "partition": review.PARTITION_PATH,
            "redundancy": review.REDUNDANCY_PATH,
            "decision": review.DECISION_PATH,
            "next_proposal": review.NEXT_PROPOSAL_PATH,
        }
        for key, path in mapping.items():
            self.assertEqual(packet["artifacts"][key]["sha256"], sha256_file(ROOT / path))
        state = load_document(ROOT / review.STATE_PATH)
        current = state["ranging_short_router_indicator_direction_review"]
        self.assertEqual(current["status"], "completed_read_only")
        self.assertFalse(current["candidate_created"])
        registry = load_document(ROOT / review.REGISTRY_EXPORT_PATH)
        rows = [
            row
            for row in registry["tables"]["research_campaign_runs"]
            if row["run_id"] == review.REVIEW_ID
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["campaign_executed"], 0)
        self.assertEqual(rows[0]["candidate_created"], 0)

    def test_replay_is_deterministic_and_report_is_chinese(self):
        result = review.run(ROOT, write=False)
        self.assertEqual(result["contract"], load_document(ROOT / review.CONTRACT_PATH))
        self.assertEqual(result["alignment"], load_document(ROOT / review.ALIGNMENT_PATH))
        self.assertEqual(result["partition"], load_document(ROOT / review.PARTITION_PATH))
        self.assertEqual(result["decision"], load_document(ROOT / review.DECISION_PATH))
        report = (ROOT / review.REPORT_PATH).read_text(encoding="utf-8")
        self.assertIn("router 指标方向契约审计", report)
        self.assertIn("阻止 5 个 pre-gate 信号并保留 7 个", report)
        self.assertIn("没有读取收益结果", report)

    def test_no_candidate_result_or_validation_namespace_is_created(self):
        self.assertFalse((ROOT / "research/candidates" / review.REVIEW_ID).exists())
        self.assertFalse((ROOT / "research/results" / review.REVIEW_ID).exists())
        source = (
            ROOT / "scripts/build_ranging_short_router_indicator_direction_review.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("futures-validation-", source)
        self.assertNotIn("research/data/holdout", source)


if __name__ == "__main__":
    unittest.main()
