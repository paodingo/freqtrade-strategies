from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_ranging_short_router_context_attribution as attribution  # noqa: E402
from research_director_common import load_document, sha256_file  # noqa: E402


class RouterVoteTopologyTests(unittest.TestCase):
    def test_existing_router_thresholds_map_to_categorical_topologies(self):
        unanimous = attribution._vote_topology(
            pd.Series(
                {
                    "adx_4h": 19.0,
                    "bb_width_4h": 0.8,
                    "bb_width_mean_4h": 1.0,
                    "atr_4h": 0.9,
                    "atr_mean_4h": 1.0,
                }
            )
        )
        mixed = attribution._vote_topology(
            pd.Series(
                {
                    "adx_4h": 19.0,
                    "bb_width_4h": 1.2,
                    "bb_width_mean_4h": 1.0,
                    "atr_4h": 0.9,
                    "atr_mean_4h": 1.0,
                }
            )
        )
        grey = attribution._vote_topology(
            pd.Series(
                {
                    "adx_4h": 22.0,
                    "bb_width_4h": 0.8,
                    "bb_width_mean_4h": 1.0,
                    "atr_4h": 1.2,
                    "atr_mean_4h": 1.0,
                }
            )
        )
        self.assertEqual(attribution._topology_id(unanimous), "R-R-R")
        self.assertEqual(attribution._topology_id(mixed), "R-T-R")
        self.assertEqual(attribution._topology_id(grey), "G-R-T")


class RouterContextAttributionArtifactTests(unittest.TestCase):
    def test_read_only_authority_forbids_all_mutation_and_sealed_access(self):
        checks = attribution.validate_authority(ROOT)
        self.assertTrue(all(checks.values()))
        approval = load_document(ROOT / attribution.APPROVAL_PATH)
        authority = approval["authority"]
        for field in (
            "create_candidate",
            "run_backtest",
            "search_thresholds",
            "change_router",
            "change_formal_strategy",
            "access_validation",
            "access_holdout",
            "automatic_followup_execution",
        ):
            self.assertFalse(authority[field])

    def test_all_twelve_signals_share_unanimous_ranging_topology(self):
        result = load_document(ROOT / attribution.ATTRIBUTION_PATH)
        self.assertEqual(result["pre_gate_signal_count"], 12)
        self.assertEqual(result["topology_count"], 1)
        self.assertEqual(result["topology_counts"], {"R-R-R": 12})
        self.assertTrue(result["all_signals_share_one_topology"])
        self.assertTrue(result["all_signals_have_current_raw_ranging_support"])
        self.assertEqual(result["carry_context_signal_count"], 0)
        self.assertTrue(all(row["topology_id"] == "R-R-R" for row in result["rows"]))
        self.assertEqual(result["backtest_calls"], 0)
        self.assertEqual(result["validation_accesses"], 0)
        self.assertEqual(result["holdout_accesses"], 0)
        self.assertFalse(result["method"]["continuous_threshold_search"])
        self.assertFalse(result["method"]["outcome_metrics_read"])

    def test_no_context_is_admissible_without_reopening_whole_branch(self):
        decision = load_document(ROOT / attribution.DECISION_PATH)
        self.assertEqual(
            decision["decision"],
            "no_admissible_router_context_under_current_contract",
        )
        self.assertEqual(decision["admissible_context_count"], 0)
        self.assertIsNone(decision["selected_context"])
        self.assertEqual(
            decision["context_partition"],
            {
                "carry_without_current_raw_signal": 0,
                "current_raw_unanimous_ranging": 12,
                "current_raw_mixed_ranging_majority": 0,
                "pre_gate_total": 12,
                "partition_complete": True,
            },
        )
        by_id = {
            item["context_id"]: item for item in decision["contexts_evaluated"]
        }
        self.assertEqual(
            by_id["ranging_state_without_current_range_signal"]["pre_gate_coverage"],
            0,
        )
        self.assertEqual(
            by_id["unanimous_current_ranging_votes"]["pre_gate_coverage"], 12
        )
        self.assertEqual(
            by_id["unanimous_current_ranging_votes"]["rejection_reason"],
            "observed_whole_branch_equivalence",
        )
        self.assertFalse(decision["new_candidate_authorized"])
        self.assertFalse(decision["backtest_authorized"])
        self.assertFalse(decision["threshold_search_authorized"])

    def test_packet_binds_attribution_and_decision_files(self):
        packet = load_document(ROOT / attribution.PACKET_PATH)
        self.assertEqual(
            packet["attribution_sha256"],
            sha256_file(ROOT / attribution.ATTRIBUTION_PATH),
        )
        self.assertEqual(
            packet["decision_sha256"],
            sha256_file(ROOT / attribution.DECISION_PATH),
        )
        self.assertEqual(packet["candidate_created"], False)
        self.assertEqual(packet["backtest_calls"], 0)
        self.assertEqual(packet["validation_accesses"], 0)
        self.assertEqual(packet["holdout_accesses"], 0)

    def test_state_and_registry_record_read_only_completion(self):
        decision = load_document(ROOT / attribution.DECISION_PATH)
        state = load_document(ROOT / "research/director/current-research-state.json")
        current = state["ranging_short_router_context_attribution"]
        self.assertEqual(current["decision"], decision["decision"])
        self.assertEqual(
            current["decision_fingerprint"], decision["decision_fingerprint"]
        )
        self.assertEqual(current["candidate_created"], False)
        self.assertEqual(current["backtest_calls"], 0)
        registry = load_document(ROOT / attribution.REGISTRY_EXPORT_PATH)
        runs = [
            row
            for row in registry["tables"]["research_campaign_runs"]
            if row["run_id"] == attribution.AUDIT_ID
        ]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["status"], "completed_read_only")
        self.assertEqual(runs[0]["campaign_executed"], 0)
        self.assertEqual(runs[0]["candidate_created"], 0)
        self.assertEqual(runs[0]["validation_accesses"], 0)
        self.assertEqual(runs[0]["holdout_accesses"], 0)

    def test_attribution_replay_is_deterministic(self):
        expected = load_document(ROOT / attribution.ATTRIBUTION_PATH)
        actual = attribution.build_attribution(ROOT)
        self.assertEqual(actual, expected)

    def test_report_is_chinese_and_offline(self):
        report = (ROOT / attribution.REPORT_PATH).read_text(encoding="utf-8")
        self.assertIn("只读归因报告", report)
        self.assertIn("R-R-R", report)
        self.assertIn("不存在可采纳的新 context", report)
        self.assertNotRegex(report, r"https?://|<script")

    def test_no_new_candidate_or_result_namespace_exists(self):
        self.assertFalse(
            (ROOT / "research/candidates/ranging-short-router-context-attribution-v1").exists()
        )
        self.assertFalse(
            (ROOT / "research/results/ranging-short-router-context-attribution-v1").exists()
        )

    def test_source_does_not_reference_sealed_dataset_paths(self):
        source = (
            ROOT / "scripts/build_ranging_short_router_context_attribution.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("futures-validation-", source)
        self.assertNotIn("research/data/holdout", source)


if __name__ == "__main__":
    unittest.main()
