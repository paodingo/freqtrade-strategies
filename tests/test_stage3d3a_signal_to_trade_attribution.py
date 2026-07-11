from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import analyze_signal_to_trade_attribution as s


class Stage3D3ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.deltas = json.loads((ROOT / s.DELTAS_PATH).read_text(encoding="utf-8"))
        cls.timelines = json.loads((ROOT / s.TIMELINES_PATH).read_text(encoding="utf-8"))
        cls.summary = json.loads((ROOT / s.SUMMARY_JSON).read_text(encoding="utf-8"))
        cls.final = json.loads((ROOT / s.FINAL_JSON).read_text(encoding="utf-8"))
        cls.contract = s.load_simple_yaml(ROOT / s.CONTRACT_PATH)
        cls.proposal = s.load_simple_yaml(ROOT / s.PROPOSAL_PATH)

    def test_01_signal_delta_extraction(self):
        self.assertEqual(self.deltas["count"], 25)
        self.assertTrue(all(row["prediction_correspondence"]["matched"] for row in self.deltas["deltas"]))

    def test_02_entry_exit_classification(self):
        self.assertEqual(self.summary["entry_count"], 25)
        self.assertEqual(self.summary["exit_count"], 0)

    def test_03_existing_position_attribution(self):
        primary, _, stage, _ = s.choose_blockers({"existing_same_direction_position": True})
        self.assertEqual((primary, stage), ("existing_same_direction_position", "position_state_checked"))

    def test_04_position_stacking_disabled(self):
        primary, _, _, _ = s.choose_blockers({"position_stacking_disabled": True})
        self.assertEqual(primary, "position_stacking_disabled")

    def test_05_long_short_collision(self):
        self.assertEqual(s.choose_blockers({"long_short_entry_collision": True})[0], "long_short_entry_collision")

    def test_06_entry_exit_collision(self):
        self.assertEqual(s.choose_blockers({"entry_exit_collision": True})[0], "entry_exit_collision")

    def test_07_duplicate_entry(self):
        self.assertEqual(s.choose_blockers({"duplicate_entry_signal": True})[0], "duplicate_entry_signal")

    def test_08_max_open_trades(self):
        self.assertEqual(s.choose_blockers({"max_open_trades_reached": True})[0], "max_open_trades_reached")

    def test_09_wallet_stake_rejection(self):
        self.assertEqual(s.choose_blockers({"insufficient_available_balance": True})[0], "insufficient_available_balance")
        self.assertEqual(s.choose_blockers({"stake_below_minimum": True})[0], "stake_below_minimum")

    def test_10_pair_lock_protection(self):
        self.assertEqual(s.choose_blockers({"pair_locked": True})[0], "pair_locked")
        self.assertEqual(s.choose_blockers({"protection_blocked": True})[0], "protection_blocked")

    def test_11_no_next_candle(self):
        self.assertEqual(s.choose_blockers({"no_next_candle_for_execution": True})[0], "no_next_candle_for_execution")

    def test_12_trade_already_closed(self):
        self.assertEqual(s.choose_blockers({"trade_already_closed": True})[0], "trade_already_closed")

    def test_13_roi_preemption(self):
        self.assertEqual(s.choose_blockers({"roi_exit_preempted_signal": True})[0], "roi_exit_preempted_signal")

    def test_14_stoploss_preemption(self):
        self.assertEqual(s.choose_blockers({"stoploss_preempted_signal": True})[0], "stoploss_preempted_signal")

    def test_15_duplicate_exit(self):
        self.assertEqual(s.choose_blockers({"duplicate_exit_signal": True})[0], "duplicate_exit_signal")

    def test_16_primary_priority(self):
        primary, secondary, stage, _ = s.choose_blockers({"candidate_dependency_module_cache_shadowed": True, "existing_same_direction_position": True, "max_open_trades_reached": True})
        self.assertEqual(primary, "candidate_dependency_module_cache_shadowed")
        self.assertEqual(stage, "signal_candidate")
        self.assertIn("existing_same_direction_position", secondary)

    def test_17_secondary_blockers(self):
        _, secondary, _, _ = s.choose_blockers({"existing_same_direction_position": True, "position_stacking_disabled": True})
        self.assertEqual(secondary, ["position_stacking_disabled"])

    def test_18_unresolved_evidence(self):
        self.assertEqual(s.choose_blockers({})[0], "unresolved_insufficient_instrumentation")

    def test_19_instrumentation_hash_preserved(self):
        self.assertTrue(self.final["instrumentation_trade_hash_preserved"])
        self.assertFalse(self.final["instrumentation_replay_executed"])

    def test_20_freqtrade_contract(self):
        self.assertEqual(self.contract["runtime"]["freqtrade"], "2025.8")
        self.assertEqual(self.contract["contract_sha256"], s.self_hash(self.contract, "contract_sha256"))

    def test_21_site_packages_unchanged(self):
        self.assertTrue(self.final["site_packages_unchanged"])
        self.assertFalse(self.contract["site_packages_modified"])

    def test_22_proposal_pending_review(self):
        self.assertEqual(self.proposal["status"], "pending_human_review")
        self.assertEqual(self.proposal["proposal_sha256"], s.self_hash(self.proposal, "proposal_sha256"))

    def test_23_no_candidate_created(self):
        self.assertFalse(self.final["forbidden_actions"]["candidate_created"])
        self.assertFalse(self.proposal["executable_candidate_queue_created"])

    def test_24_no_hyperopt(self):
        self.assertFalse(self.final["forbidden_actions"]["hyperopt_run"])

    def test_25_no_validation_or_holdout(self):
        self.assertFalse(self.final["forbidden_actions"]["validation_accessed"])
        self.assertFalse(self.final["forbidden_actions"]["holdout_accessed"])

    def test_26_complete_attribution_and_baseline_guard(self):
        self.assertTrue(self.final["all_deltas_attributed"])
        self.assertEqual(self.summary["unresolved_count"], 0)
        self.assertTrue((ROOT / "docs/quality/test-baseline.yaml").exists())


if __name__ == "__main__":
    unittest.main()
