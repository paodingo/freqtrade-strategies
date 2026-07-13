from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_temporal_generalization_profile as s
from research_control import load_simple_yaml
from run_experiment import sha256_file
from portable_baseline_support import active as portable_active, fixture_json


def fake_slice(total: int = 10, result: float = 0.01, regime: str = "range_low_volatility", consistent: bool = True, long: int = 5, short: int = 5, drawdown: float = 0.02):
    metrics = {
        "coverage": {"total_trades": total, "long_trades": long, "short_trades": short},
        "return": {"total_return": result},
        "risk": {"max_drawdown_percentage": drawdown},
        "risk_adjusted": {"profit_factor": 1.1},
    }
    return {"run_a": {"metrics": metrics}, "reproducibility": {"consistent": consistent}, "market_profile": {"dominant_market_regime": regime}}


class Stage3E1TemporalGeneralizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_simple_yaml(ROOT / s.POLICY_PATH)
        cls.slices = load_simple_yaml(ROOT / s.SLICES_PATH)
        cls.final = fixture_json("stage3e1-semantic-summary.json") if portable_active() else json.loads((ROOT / s.FINAL_JSON).read_text(encoding="utf-8"))

    def test_01_slice_plan_frozen_before_backtest(self):
        self.assertTrue(self.policy["frozen_before_first_backtest"])
        self.assertTrue(self.slices["frozen_before_first_backtest"])
        self.assertEqual(self.slices["status"], "frozen")

    def test_02_slice_lengths_are_equal(self):
        self.assertEqual({row["evaluation_candles_1h"] for row in self.slices["slices"]}, {s.SLICE_HOURS})

    def test_03_formal_intervals_do_not_overlap(self):
        rows = self.slices["slices"]
        self.assertTrue(all(row["evaluation_end_exclusive"] <= rows[index + 1]["evaluation_start"] for index, row in enumerate(rows[:-1])))

    def test_04_warmup_is_excluded(self):
        self.assertFalse(self.policy["warmup_in_evaluation_metrics"])
        self.assertTrue(all(row["warmup_start"] < row["evaluation_start"] for row in self.slices["slices"]))

    def test_05_selection_does_not_use_strategy_results(self):
        self.assertFalse(self.policy["selection_uses_strategy_results"])
        self.assertFalse(self.policy["selection_uses_return_or_risk_metrics"])

    def test_06_acceptance_fixture_is_excluded(self):
        self.assertFalse(self.policy["acceptance_fixture_allowed"])
        self.assertFalse(self.final["governance"]["acceptance_fixture_used"])

    def test_07_profiles_are_strategy_independent(self):
        for row in self.slices["slices"]:
            profile = self.final["profiles"][row["slice_id"]] if portable_active() else json.loads((ROOT / s.PROFILE_ROOT / f"{row['slice_id']}-market-profile.json").read_text(encoding="utf-8"))
            self.assertTrue(profile["strategy_independent"])
            self.assertFalse(profile["uses_strategy_results"])

    def test_08_each_slice_uses_independent_processes(self):
        pids = [run["process_id"] for row in self.final["results"] for run in (row["run_a"], row["run_b"])]
        self.assertEqual(len(pids), len(set(pids)))

    def test_09_run_a_and_run_b_pids_differ(self):
        self.assertTrue(all(row["run_a"]["process_id"] != row["run_b"]["process_id"] for row in self.final["results"]))

    def test_10_no_cross_slice_module_cache(self):
        for row in self.final["results"]:
            for run in (row["run_a"], row["run_b"]):
                identity = run["identity"] if portable_active() else json.loads((ROOT / run["runtime_identity"]).read_text(encoding="utf-8"))
                self.assertEqual(identity["candidate_modules"], [])
                self.assertEqual(identity["related_sys_modules"], ["RegimeAwareV6", "regime_aware_base", "regime_detector", "risk_manager"])

    def test_11_normalized_trade_hash_is_reproducible(self):
        self.assertTrue(all(row["run_a"]["normalized_trade_hash"] == row["run_b"]["normalized_trade_hash"] for row in self.final["results"]))

    def test_12_null_metric_is_not_zero_filled(self):
        missing = {}
        self.assertIsNone(s.nullable(None, "not_available", missing))
        self.assertIn("not_available", missing)

    def test_13_weekly_and_rolling_metrics_exist(self):
        for row in self.final["results"]:
            stability = row["run_a"]["metrics"]["internal_stability"]
            self.assertIn("weekly_returns", stability)
            self.assertIn("rolling_28_day_returns", stability)

    def test_14_regime_level_metrics_exist(self):
        self.assertTrue(all("regime_results" in row["run_a"]["metrics"]["internal_stability"] for row in self.final["results"]))

    def test_15_temporally_consistent_classifier(self):
        verdict, _ = s.classify_temporal_profile([fake_slice() for _ in range(4)])
        self.assertEqual(verdict, "temporally_consistent")

    def test_16_regime_dependent_classifier(self):
        rows = [fake_slice(result=0.01, regime="range") for _ in range(2)] + [fake_slice(result=0.05, regime="trend") for _ in range(2)]
        verdict, _ = s.classify_temporal_profile(rows)
        self.assertEqual(verdict, "regime_dependent")

    def test_17_temporally_fragile_classifier(self):
        rows = [fake_slice(result=value) for value in (0.10, -0.01, -0.01, 0.02)]
        verdict, _ = s.classify_temporal_profile(rows)
        self.assertEqual(verdict, "temporally_fragile")

    def test_18_coverage_insufficient_classifier(self):
        rows = [fake_slice(total=value) for value in (2, 3, 10, 10)]
        verdict, _ = s.classify_temporal_profile(rows)
        self.assertEqual(verdict, "coverage_insufficient")

    def test_19_execution_inconsistent_classifier(self):
        rows = [fake_slice() for _ in range(4)]
        rows[2]["reproducibility"]["consistent"] = False
        verdict, _ = s.classify_temporal_profile(rows)
        self.assertEqual(verdict, "execution_inconsistent")

    def test_20_all_slices_are_retained(self):
        self.assertEqual(len(self.final["results"]), len(self.slices["slices"]))

    def test_21_strategy_is_unmodified(self):
        self.assertEqual(sha256_file(ROOT / s.STRATEGY).lower(), s.BASE_STRATEGY_SHA256)
        self.assertFalse(self.final["governance"]["strategy_modified"])

    def test_22_no_candidate_created(self):
        self.assertFalse(self.final["governance"]["candidate_created"])
        self.assertFalse(any((ROOT / "research/candidates").glob("stage3e1*")))

    def test_23_no_parameter_search_or_hyperopt(self):
        self.assertFalse(self.final["governance"]["parameter_search_run"])
        self.assertFalse(self.final["governance"]["hyperopt_run"])

    def test_24_no_holdout_access(self):
        self.assertFalse(self.final["governance"]["holdout_accessed"])

    def test_25_no_next_campaign_started(self):
        self.assertFalse(self.final["governance"]["next_campaign_started"])

    def test_26_snapshots_are_sealed_and_non_tuning(self):
        for row in self.slices["slices"]:
            manifest = self.final["snapshots"][row["dataset_id"]] if portable_active() else load_simple_yaml(ROOT / s.SNAPSHOT_ROOT / row["dataset_id"] / "manifest.yaml")
            self.assertTrue(manifest["sealed"])
            self.assertFalse(manifest["suitable_for_candidate_tuning"])
            self.assertEqual(manifest["evaluation_range"]["main_1h_candles"], s.SLICE_HOURS)


if __name__ == "__main__":
    unittest.main()
