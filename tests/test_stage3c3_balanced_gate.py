import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_stage3c3_evaluation as stage3c3
import evaluate_research_candidate as evaluator


def metric(value, direction="higher"):
    return {"normalized_value": value, "direction": direction}


def vector(
    trade_hash="base",
    trades=None,
    total=24,
    long_count=8,
    short_count=16,
    closed=24,
    active_weeks=9,
    windows=7,
    total_return=0.0,
    profit_factor=1.0,
    max_drawdown=0.10,
):
    trades = trades if trades is not None else [{"id": trade_hash}]
    return {
        "metrics": {
            "total_trades": metric(total),
            "long_trades": metric(long_count),
            "short_trades": metric(short_count),
            "closed_trades": metric(closed),
            "active_weeks": metric(active_weeks),
            "rolling_window_28d_step_7d": metric({"complete_window_count": windows}),
            "total_profit_ratio": metric(total_return),
            "profit_factor": metric(profit_factor),
            "max_drawdown_percentage": metric(max_drawdown, "lower"),
        },
        "normalized_trade_hash": trade_hash,
        "normalized_trade_count": len(trades),
        "normalized_trades": trades,
    }


class Stage3C3BalancedGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = stage3c3.approved_policy(ROOT, "2026-07-11T00:00:00+00:00")

    def decision(self, baseline, candidate):
        comparison = evaluator.compare_vectors(baseline, candidate)
        return evaluator.gate_decision(self.policy, baseline, candidate, comparison)

    def test_policy_approval_status_hash_and_scope(self):
        policy = self.policy

        self.assertEqual(policy["policy_id"], "balanced-research-gate-v1")
        self.assertEqual(policy["policy_approval_status"], "approved")
        self.assertEqual(policy["approver_type"], "human_user")
        self.assertEqual(policy["approval_scope"], "current_single_pair_futures_v2")
        self.assertEqual(policy["policy_sha256"], evaluator.canonical_policy_hash(policy))
        self.assertEqual(policy["development_dataset_id"], stage3c3.DEV_DATASET_ID)
        self.assertEqual(policy["validation_dataset_id"], stage3c3.VAL_DATASET_ID)
        self.assertFalse(policy["champion_promotion_allowed"])
        self.assertFalse(policy["qualified_challenger_allowed"])
        self.assertFalse(policy["holdout_access_allowed"])
        self.assertFalse(policy["live_trading_allowed"])

    def test_development_coverage_gate(self):
        decision = self.decision(vector(), vector(trade_hash="cand", total=10, long_count=4, short_count=6, closed=10, active_weeks=4, windows=3))

        self.assertEqual(decision["final_decision"], "development_inconclusive_insufficient_coverage")

    def test_behavior_unchanged_gate(self):
        baseline = vector(trade_hash="same", trades=[{"id": 1}])
        candidate = vector(trade_hash="same", trades=[{"id": 1}])

        decision = self.decision(baseline, candidate)

        self.assertEqual(decision["final_decision"], "development_inconclusive_behavior_unchanged")
        self.assertFalse(decision["rule_outputs"]["behavior_materiality"]["behavior_changed"])

    def test_material_improvement_any_gate_can_make_bias_pending(self):
        baseline = vector(total_return=0.0, profit_factor=1.0, max_drawdown=0.10)
        candidate = vector(trade_hash="cand", trades=[{"id": 2}], total_return=0.02, profit_factor=1.20, max_drawdown=0.07)

        decision = self.decision(baseline, candidate)

        self.assertEqual(decision["final_decision"], "development_eligible_bias_pending")
        self.assertTrue(any(decision["rule_outputs"]["development_material_improvement_any"].values()))

    def test_no_material_degradation_gate(self):
        baseline = vector(total_return=0.0, profit_factor=1.0, max_drawdown=0.10)
        candidate = vector(trade_hash="cand", trades=[{"id": 2}], total_return=-0.02, profit_factor=0.80, max_drawdown=0.40)

        decision = self.decision(baseline, candidate)

        self.assertEqual(decision["final_decision"], "development_ineligible_risk_degradation")

    def test_directional_coverage_gate(self):
        baseline = vector(long_count=12, short_count=12)
        candidate = vector(trade_hash="cand", trades=[{"id": 2}], long_count=19, short_count=5, total_return=0.02, profit_factor=1.2, max_drawdown=0.08)

        decision = self.decision(baseline, candidate)

        self.assertFalse(decision["rule_outputs"]["directional_coverage"]["passed"])
        self.assertEqual(decision["final_decision"], "development_ineligible_risk_degradation")

    def test_missing_metric_policy(self):
        baseline = vector()
        candidate = vector(trade_hash="cand", trades=[{"id": 2}], profit_factor=None)

        decision = self.decision(baseline, candidate)

        self.assertEqual(decision["final_decision"], "development_integrity_failed")
        self.assertIn("development_integrity_failed_metric_missing", decision["reasons"])

    def test_tie_policy_is_inconclusive(self):
        decision = self.decision(vector(trade_hash="same"), vector(trade_hash="same"))

        self.assertEqual(decision["final_decision"], "development_inconclusive_behavior_unchanged")

    def test_validation_coverage_absolute_relative_and_tie_gates(self):
        insufficient = stage3c3.evaluate_validation_gate(self.policy, {}, {"total_trades": 1}, {})
        self.assertEqual(insufficient["status"], "validation_inconclusive_insufficient_coverage")

        candidate = {
            "total_trades": 12,
            "long_trades": 5,
            "short_trades": 7,
            "closed_trades": 12,
            "active_weeks": 6,
            "complete_rolling_windows": 3,
            "total_return": 0.02,
            "profit_factor": 1.10,
            "max_drawdown_percentage": 10.0,
            "positive_rolling_window_ratio": 0.67,
        }
        comparison = {
            "total_return_delta_percentage_points": 1.0,
            "profit_factor_delta": 0.01,
            "max_drawdown_delta_percentage_points": 0.5,
            "worst_window_delta_percentage_points": -0.5,
        }
        passed = stage3c3.evaluate_validation_gate(self.policy, {}, candidate, comparison)
        self.assertEqual(passed["status"], "validation_passed_provisional")

        tie = stage3c3.evaluate_validation_gate(self.policy, {}, candidate, {key: 0 for key in comparison})
        self.assertEqual(tie["status"], "validation_inconclusive_tie")

    def test_validation_access_once_and_bias_pending_blocks_validation(self):
        candidate = evaluator.validate_candidate(ROOT, stage3c3.CANDIDATE_MANIFEST)
        with tempfile.TemporaryDirectory() as tmp:
            first = evaluator.maybe_authorize_validation(Path(tmp), self.policy, "p" * 64, candidate, {}, "validation_evaluator", "development_eligible")
            second = evaluator.maybe_authorize_validation(Path(tmp), self.policy, "p" * 64, candidate, {}, "validation_evaluator", "development_eligible")
            blocked = evaluator.maybe_authorize_validation(Path(tmp), self.policy, "q" * 64, candidate, {}, "validation_evaluator", "development_eligible_bias_pending")

        self.assertEqual(first["authorization_result"], "authorized")
        self.assertEqual(second["reason_code"], "validation_budget_exhausted")
        self.assertEqual(blocked["reason_code"], "development_not_eligible")

    def test_limited_disclosure_withholds_validation_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "limited.json"
            result = {
                "development_status": "development_inconclusive_behavior_unchanged",
                "gate_decision": {"rule_outputs": {"development_coverage": {"passed": True}}},
                "candidate_metrics": {
                    "metrics": {
                        "total_trades": metric(27),
                        "long_trades": metric(7),
                        "short_trades": metric(20),
                        "total_profit_ratio": metric(-0.003),
                        "max_drawdown_percentage": metric(0.02, "lower"),
                        "profit_factor": metric(0.95),
                    }
                },
            }
            payload = stage3c3.write_limited_validation_disclosure(path, result)

        self.assertIn("complete_validation_trade_list", payload["withheld"])
        self.assertNotIn("normalized_trades", json.dumps(payload))

    def test_lookahead_recursive_and_cost_gates(self):
        lookahead_ok = stage3c3.evaluate_lookahead_gate({"biased_entries": 0, "biased_exits": 0, "biased_indicators": 0}, self.policy)
        lookahead_bad = stage3c3.evaluate_lookahead_gate({"biased_entries": 1}, self.policy)
        lookahead_inconclusive = stage3c3.evaluate_lookahead_gate({"signal_coverage": "insufficient"}, self.policy)
        recursive_ok = stage3c3.evaluate_recursive_gate({"max_signal_critical_indicator_variance_percent": 0.5, "changed_entry_signals": 0, "changed_exit_signals": 0}, self.policy)
        recursive_bad = stage3c3.evaluate_recursive_gate({"max_signal_critical_indicator_variance_percent": 1.5, "changed_entry_signals": 0, "changed_exit_signals": 0}, self.policy)
        cost = stage3c3.evaluate_cost_gate(
            {
                "fee_125": {"candidate_total_return": 0.01, "candidate_profit_factor": 1.01},
                "fee_150": {"candidate_total_return": 0.0, "baseline_total_return": -0.01, "candidate_max_drawdown_percentage": 20.0},
            },
            self.policy,
        )

        self.assertTrue(lookahead_ok["passed"])
        self.assertEqual(lookahead_bad["status"], "bias_validation_failed_lookahead")
        self.assertEqual(lookahead_inconclusive["status"], "bias_validation_inconclusive_lookahead_coverage")
        self.assertTrue(recursive_ok["passed"])
        self.assertEqual(recursive_bad["status"], "bias_validation_failed_recursive")
        self.assertTrue(cost["passed"])
        self.assertFalse(cost["synthetic_slippage_used"])
        self.assertTrue(cost["historical_funding_required"])

    def test_current_behavior_unchanged_candidate_does_not_access_validation(self):
        baseline = vector(trade_hash="same", trades=[{"id": 1}])
        candidate = vector(trade_hash="same", trades=[{"id": 1}])
        decision = self.decision(baseline, candidate)

        self.assertEqual(decision["final_decision"], "development_inconclusive_behavior_unchanged")
        self.assertEqual(decision["cost_stress"], "not_required_until_behavior_changed")

    def test_forbidden_surfaces_remain_disabled(self):
        policy = self.policy

        self.assertFalse(policy["champion_promotion_allowed"])
        self.assertFalse(policy["qualified_challenger_allowed"])
        self.assertFalse(policy["holdout_access_allowed"])
        self.assertFalse(policy["hyperopt_allowed"])
        self.assertFalse(policy["strategy_mutation_allowed"])
        self.assertFalse(policy["new_candidate_generation_allowed"])

    def test_stage3c3_registry_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "registry.db")
            try:
                stage3c3.init_stage3c3_registry(conn)
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                conn.close()

        self.assertIn("stage3c3_events", tables)


if __name__ == "__main__":
    unittest.main()
