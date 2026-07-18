import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_ranging_short_structural_observable_discovery as discovery
from research_director_common import load_document, sha256_file


class RangingShortStructuralObservableDiscoveryTest(unittest.TestCase):
    def test_authority_is_read_only_and_bound_to_prior_closure(self):
        checks = discovery.validate_authority(ROOT)
        self.assertTrue(all(checks.values()))
        approval = load_document(ROOT / discovery.APPROVAL_PATH)
        authority = approval["authority"]
        self.assertFalse(authority["create_candidate"])
        self.assertFalse(authority["run_backtest"])
        self.assertFalse(authority["search_thresholds"])
        self.assertFalse(authority["access_validation"])
        self.assertFalse(authority["access_holdout"])

    def test_coverage_forms_natural_non_outcome_partitions(self):
        coverage = load_document(ROOT / discovery.COVERAGE_PATH)
        self.assertEqual(coverage["pre_gate_signal_count"], 12)
        self.assertEqual(
            coverage["coverage_counts"]["router_indicator_direction_topology"],
            {"D-D-D": 2, "U-U-D": 5, "U-U-U": 5},
        )
        self.assertEqual(
            coverage["coverage_counts"]["funding_sign"],
            {"negative": 1, "positive": 11},
        )
        self.assertEqual(
            coverage["coverage_counts"]["completed_mark_futures_basis_sign"],
            {"negative": 10, "positive": 2},
        )
        self.assertEqual(
            coverage["coverage_counts"]["router_transition_state"],
            {"persisted_R-R-R": 12},
        )
        self.assertFalse(coverage["method"]["outcome_metrics_read"])
        self.assertFalse(coverage["method"]["continuous_threshold_search"])
        self.assertEqual(coverage["backtest_calls"], 0)
        self.assertEqual(coverage["validation_accesses"], 0)
        self.assertEqual(coverage["holdout_accesses"], 0)

    def test_inventory_ranks_direction_topology_first(self):
        inventory = load_document(ROOT / discovery.INVENTORY_PATH)
        ranked = inventory["eligible_observables"]
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertEqual(
            ranked[0]["observable_id"],
            "router_indicator_direction_topology",
        )
        self.assertEqual(ranked[0]["score_total"], 19)
        self.assertFalse(ranked[0]["whole_branch_equivalent"])
        self.assertFalse(ranked[0]["continuous_cutoff_required"])
        self.assertFalse(inventory["ranking_rubric"]["outcome_metrics_used"])
        rejected = {
            item["observable_id"]: item
            for item in inventory["rejected_or_deferred_observables"]
        }
        self.assertEqual(
            rejected["duplicate_signal_episode_phase"]["selection_status"],
            "rejected_closed_mechanism_not_reopened",
        )
        self.assertEqual(
            rejected["alpha_taker_open_interest_orderbook"]["selection_status"],
            "blocked_missing_committed_history",
        )

    def test_decision_and_next_proposal_preserve_zero_execution_budget(self):
        decision = load_document(ROOT / discovery.DECISION_PATH)
        proposal = load_document(ROOT / discovery.PROPOSAL_PATH)
        self.assertEqual(
            decision["decision"],
            "prioritize_router_indicator_direction_contract_review",
        )
        self.assertEqual(decision["next_proposal_status"], "pending_human_review")
        self.assertFalse(decision["new_candidate_authorized"])
        self.assertFalse(decision["backtest_authorized"])
        self.assertEqual(proposal["status"], "pending_human_review")
        self.assertEqual(proposal["approval_route"], "human_approval_required")
        self.assertTrue(all(value == 0 for value in proposal["execution_budget"].values()))
        self.assertIn("outcome_metric_read", proposal["forbidden_scope"])
        self.assertIn("continuous_threshold_search", proposal["forbidden_scope"])

    def test_packet_binds_all_material_outputs(self):
        packet = load_document(ROOT / discovery.PACKET_PATH)
        for key, path in (
            ("coverage_sha256", discovery.COVERAGE_PATH),
            ("inventory_sha256", discovery.INVENTORY_PATH),
            ("decision_sha256", discovery.DECISION_PATH),
            ("next_proposal_sha256", discovery.PROPOSAL_PATH),
        ):
            self.assertEqual(packet[key], sha256_file(ROOT / path))
        self.assertEqual(packet["candidate_created"], False)
        self.assertEqual(packet["backtest_calls"], 0)
        self.assertEqual(packet["validation_accesses"], 0)
        self.assertEqual(packet["holdout_accesses"], 0)

    def test_state_and_registry_record_read_only_completion(self):
        state = load_document(ROOT / discovery.STATE_PATH)
        current = state["ranging_short_structural_observable_discovery"]
        self.assertEqual(current["status"], "completed_read_only")
        self.assertEqual(
            current["selected_observable_id"],
            "router_indicator_direction_topology",
        )
        self.assertEqual(current["candidate_created"], False)
        self.assertEqual(current["backtest_calls"], 0)
        registry = load_document(ROOT / discovery.REGISTRY_EXPORT_PATH)
        rows = [
            row
            for row in registry["tables"]["research_campaign_runs"]
            if row["run_id"] == discovery.AUDIT_ID
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "completed_read_only")
        self.assertEqual(rows[0]["campaign_executed"], 0)
        self.assertEqual(rows[0]["candidate_created"], 0)
        self.assertEqual(rows[0]["validation_accesses"], 0)
        self.assertEqual(rows[0]["holdout_accesses"], 0)

    def test_replay_is_deterministic(self):
        expected_coverage = load_document(ROOT / discovery.COVERAGE_PATH)
        actual_coverage = discovery.build_coverage(ROOT)
        self.assertEqual(actual_coverage, expected_coverage)
        expected_inventory = load_document(ROOT / discovery.INVENTORY_PATH)
        self.assertEqual(discovery.build_inventory(actual_coverage), expected_inventory)

    def test_report_is_chinese_and_no_candidate_namespace_exists(self):
        report = (ROOT / discovery.REPORT_PATH).read_text(encoding="utf-8")
        self.assertIn("结构观测量 Discovery 报告", report)
        self.assertIn("D-D-D=2", report)
        self.assertIn("不创建 Candidate、不回测", report)
        self.assertNotRegex(report, r"https?://|<script")
        self.assertFalse(
            (
                ROOT
                / "research/candidates/ranging-short-structural-observable-discovery-v1"
            ).exists()
        )
        self.assertFalse(
            (
                ROOT
                / "research/results/ranging-short-structural-observable-discovery-v1"
            ).exists()
        )

    def test_source_does_not_reference_validation_or_holdout_data(self):
        source = (
            ROOT / "scripts/build_ranging_short_structural_observable_discovery.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("futures-validation-", source)
        self.assertNotIn("research/data/holdout", source)


if __name__ == "__main__":
    unittest.main()
