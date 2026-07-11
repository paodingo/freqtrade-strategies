import json
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_strategy_signal_reachability as stage3d2a
from research_control import load_simple_yaml


class Stage3D2ASignalReachabilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / stage3d2a.FINAL_JSON).exists():
            stage3d2a.run_analysis(ROOT)
        cls.final = json.loads((ROOT / stage3d2a.FINAL_JSON).read_text(encoding="utf-8"))
        cls.graph = json.loads((ROOT / stage3d2a.GRAPH_PATH).read_text(encoding="utf-8"))
        cls.coverage = json.loads((ROOT / stage3d2a.COVERAGE_PATH).read_text(encoding="utf-8"))
        cls.branch = json.loads((ROOT / stage3d2a.BRANCH_PATH).read_text(encoding="utf-8"))
        cls.explanations = json.loads((ROOT / stage3d2a.EXPLANATION_PATH).read_text(encoding="utf-8"))
        cls.thresholds = json.loads((ROOT / stage3d2a.THRESHOLD_PATH).read_text(encoding="utf-8"))
        cls.blockers = json.loads((ROOT / stage3d2a.BLOCKER_PATH).read_text(encoding="utf-8"))
        cls.counterfactual = json.loads((ROOT / stage3d2a.COUNTERFACTUAL_PATH).read_text(encoding="utf-8"))
        cls.proposal = load_simple_yaml(ROOT / stage3d2a.PROPOSAL_PATH)

    def test_instrumentation_reference_keeps_trade_hash_equal(self):
        self.assertFalse(self.final["instrumentation_semantic_drift"])
        baseline = self.final["baseline_reference"]
        self.assertEqual(baseline["baseline_trade_hash"], baseline["candidate_trade_hash"])
        self.assertEqual(baseline["total_trades"], 27)

    def test_condition_graph_extraction_and_and_or_relations(self):
        groups = {item["group_id"]: item for item in self.graph["signal_groups"]}

        self.assertGreater(len(self.graph["ast_extracted_expressions"]), 0)
        self.assertIn("trending_long_entry", groups)
        self.assertIn("trending_long_trigger_any", groups["trending_long_entry"]["conditions"])
        self.assertIn(" AND ", groups["ranging_short_entry"]["logic"])

    def test_condition_coverage_counts(self):
        condition = self.coverage["conditions"]["rshort_rsi_gt_60"]

        self.assertGreater(condition["true_count"], 0)
        self.assertGreater(condition["false_count"], 0)
        self.assertIn("null_count", condition)
        self.assertGreater(condition["single_blocker_count"], 0)

    def test_branch_activation_reports_all_entry_branches(self):
        branches = self.branch["branches"]

        for branch in ["trending_long_entry", "trending_short_entry", "ranging_long_entry", "ranging_short_entry"]:
            self.assertIn(branch, branches)
            self.assertIn("regime_active_candles", branches[branch])
            self.assertIn("final_formed_trade_count", branches[branch])

    def test_threshold_crossing_and_conditional_distribution(self):
        details = self.thresholds["variables"]["ranging_short_setup.rsi_min"]

        self.assertIn("conditional_on_other_setup_conditions", details)
        self.assertIn("55", details["tested_value_crossings"])
        self.assertGreater(details["tested_value_crossings"]["55"]["all_candles_crossing_count"], 0)
        self.assertIn("conditional_crossing_by_group", details["tested_value_crossings"]["55"])

    def test_counterfactual_does_not_execute_backtest_or_profit_selection(self):
        values = self.counterfactual["variables"]["ranging_short_setup.rsi_min"]["candidate_values"]

        self.assertGreater(len(values), 0)
        self.assertTrue(all(item["backtest_executed"] is False for item in values))
        self.assertTrue(all(item["profit_metrics_used"] is False for item in values))
        self.assertGreater(max(item["final_signal_mask_changed_candles"] for item in values), 0)

    def test_stage3d1_each_experiment_has_explanation(self):
        explanations = self.explanations["experiments"]

        self.assertEqual(len(explanations), 10)
        self.assertTrue(all(item["changed_trade_behavior"] is False for item in explanations))
        self.assertTrue(any(item["reason_code"] == "threshold_crossed_but_other_conditions_still_block" for item in explanations))
        self.assertTrue(any(item["reason_code"] == "signal_mask_changed_but_no_trade_behavior_change" for item in explanations))

    def test_multi_condition_blocker_detection(self):
        group = self.blockers["groups"]["ranging_long_entry"]

        self.assertGreater(group["two_condition_blocker_candles"] + group["three_plus_condition_blocker_candles"], 0)
        self.assertGreater(len(group["most_common_blocker_combinations"]), 0)

    def test_proposal_pending_human_review_and_no_high_risk_variables(self):
        variables = {item["variable_id"] for item in self.proposal["proposed_variables"]}

        self.assertEqual(self.proposal["status"], "pending_human_review")
        self.assertNotIn("can_short", variables)
        self.assertNotIn("timeframe", variables)
        self.assertNotIn("stoploss", variables)

    def test_proposal_does_not_use_performance_metrics(self):
        forbidden = set(self.proposal["forbidden_selection_basis"])

        self.assertIn("return", forbidden)
        self.assertIn("profit_factor", forbidden)
        self.assertIn("drawdown", forbidden)
        self.assertNotIn("return", self.proposal["selection_basis"])

    def test_no_candidate_generation_or_forbidden_actions(self):
        forbidden = self.final["forbidden_actions"]

        self.assertFalse(forbidden["candidate_created"])
        self.assertFalse(forbidden["candidate_backtest_run"])
        self.assertFalse(forbidden["validation_accessed"])
        self.assertFalse(forbidden["holdout_accessed"])
        self.assertFalse(forbidden["hyperopt_run"])
        self.assertFalse((ROOT / "research/candidates/stage3d2a-signal-reachability").exists())

    def test_formal_strategy_integrity(self):
        stage3d2a.assert_integrity(ROOT)

    def test_synthetic_single_blocker_count(self):
        df = pd.DataFrame({"a": [True, False, False], "b": [True, True, False]})
        specs = {
            "a": stage3d2a.ConditionSpec("a", "a", "synthetic", 1, "long", "entry", lambda d: d["a"], ("a",)),
            "b": stage3d2a.ConditionSpec("b", "b", "synthetic", 1, "long", "entry", lambda d: d["b"], ("b",)),
        }
        groups = {"g": stage3d2a.SignalGroup("g", "enter_long", "long", "synthetic", ("a", "b"), "enter_long")}
        coverage = stage3d2a.condition_coverage(df, specs, groups)

        self.assertEqual(coverage["conditions"]["a"]["single_blocker_by_group"]["g"], 1)
        self.assertEqual(coverage["conditions"]["b"]["single_blocker_by_group"]["g"], 0)

    def test_synthetic_threshold_no_crossing_is_low_reach(self):
        values = pd.Series([0.1, 0.2, 0.3])
        old_mask = stage3d2a.threshold_mask(values, "<", 0.5)
        new_mask = stage3d2a.threshold_mask(values, "<", 0.6)

        self.assertEqual(int((old_mask ^ new_mask).sum()), 0)


if __name__ == "__main__":
    unittest.main()
