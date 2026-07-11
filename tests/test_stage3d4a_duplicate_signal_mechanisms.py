from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_duplicate_signal_mechanisms as s
from run_experiment import sha256_file


class Stage3D4ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.timeline = json.loads((ROOT / s.TIMELINES_PATH).read_text(encoding="utf-8"))
        cls.reentry = json.loads((ROOT / s.REENTRY_PATH).read_text(encoding="utf-8"))
        cls.mechanisms = json.loads((ROOT / s.MECHANISMS_PATH).read_text(encoding="utf-8"))["options"]
        cls.final = json.loads((ROOT / s.FINAL_JSON).read_text(encoding="utf-8"))
        cls.proposal = s.load_simple_yaml(ROOT / s.PROPOSAL_PATH)

    def option(self, mechanism_id): return next(row for row in self.mechanisms if row["mechanism_id"] == mechanism_id)

    def test_01_duplicate_signal_timeline(self):
        self.assertEqual(self.timeline["count"], 12)
        self.assertTrue(all(row["position_id"] for row in self.timeline["timelines"]))

    def test_02_signal_distance_entry_exit(self):
        self.assertTrue(all(row["signal_distance_from_entry_candles"] >= 0 and row["signal_distance_to_exit_candles"] > 0 for row in self.timeline["timelines"]))

    def test_03_signal_persistence_after_exit(self):
        primary, _ = s.classify_lifecycle(20, True, False, False)
        self.assertEqual(primary, "signal_persisted_after_exit")

    def test_04_signal_expiration_before_flat(self):
        self.assertTrue(all(row["primary_classification"] == "signal_expired_before_flat" for row in self.timeline["timelines"]))

    def test_05_signal_reappeared_after_flat(self):
        self.assertEqual(sum(row["first_reappearance_after_exit"] is not None for row in self.timeline["timelines"]), 2)

    def test_06_setup_confirmation_classification(self):
        _, secondary = s.classify_lifecycle(5, False, False, False)
        self.assertIn("same_setup_confirmation_during_position", secondary)

    def test_07_first_trigger_extraction(self):
        text = (ROOT / s.FIRST_TRIGGER_MD).read_text(encoding="utf-8")
        self.assertIn("earliest executable current signal", text)
        self.assertIn("no false-to-true edge requirement", text)

    def test_08_same_candle_setup_arbitration(self):
        self.assertEqual(self.final["first_trigger_conflict_count"], 0)
        self.assertEqual(self.final["setup_shadowing_count"], 0)

    def test_09_reentry_opportunity(self):
        self.assertEqual(self.final["real_missed_reentry_opportunity_count"], 0)
        self.assertTrue(all(not row["missed_flat_state_opportunity"] for row in self.reentry["opportunities"]))

    def test_10_no_future_price_use(self):
        self.assertFalse(self.reentry["future_price_used"]); self.assertFalse(self.reentry["hypothetical_profit_calculated"])
        self.assertTrue(all(not row["future_price_evaluation_used"] for row in self.timeline["timelines"]))

    def test_11_position_stacking_blocked(self): self.assertFalse(self.final["forbidden_actions"]["position_stacking_enabled"])
    def test_12_position_adjustment_blocked(self): self.assertFalse(self.final["forbidden_actions"]["position_adjustment_enabled"])

    def test_13_mechanism_risk_classification(self):
        self.assertEqual(self.option("D_signal_persistence_until_flat")["risk_level"], "high")
        self.assertEqual(self.option("F_position_stacking_adjustment")["risk_level"], "critical")

    def test_14_no_mechanism_warranted(self): self.assertEqual(self.final["recommendation"], "no_mechanism_change_warranted")
    def test_15_first_trigger_proposal(self): self.assertFalse(self.option("C_first_valid_trigger_selection")["recommended_for_next_stage"])
    def test_16_rearm_proposal(self): self.assertFalse(self.option("E_rearm_after_flat")["recommended_for_next_stage"])
    def test_17_persistence_high_risk(self): self.assertTrue(self.option("D_signal_persistence_until_flat")["lookahead_risk"])

    def test_18_proposal_preserves_historical_pending_state_after_approval(self):
        self.assertEqual(self.final["proposal_status"], "pending_human_review")
        self.assertEqual(self.proposal["status"], "approved_no_change")
        self.assertEqual(self.proposal["preapproval_proposal_sha256"], self.final["proposal_sha256"])
        self.assertEqual(self.proposal["proposal_sha256"], s.self_hash(self.proposal, "proposal_sha256"))

    def test_19_no_candidate_created(self): self.assertFalse(self.final["forbidden_actions"]["candidate_created"])
    def test_20_no_backtest_search(self): self.assertFalse(self.final["forbidden_actions"]["candidate_backtest_run"])

    def test_21_no_validation_holdout(self):
        self.assertFalse(self.final["forbidden_actions"]["validation_accessed"]); self.assertFalse(self.final["forbidden_actions"]["holdout_accessed"])

    def test_22_no_hyperopt(self): self.assertFalse(self.final["forbidden_actions"]["hyperopt_run"])

    def test_23_official_strategy_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py").upper(), s.BASE_STRATEGY_SHA256)

    def test_24_baseline_guard(self):
        self.assertTrue((ROOT / "docs/quality/test-baseline.yaml").exists())
        self.assertTrue(self.final["single_threshold_search_closed"])


if __name__ == "__main__": unittest.main()
