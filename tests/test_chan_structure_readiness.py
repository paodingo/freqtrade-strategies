import json
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_chan_structure_readiness as audit  # noqa: E402


def synthetic_long_structure() -> pd.DataFrame:
    closes = [10, 12, 14, 11, 8, 10, 12, 16, 14, 13, 14, 16, 17]
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.2 for value in closes],
            "low": [value - 0.2 for value in closes],
            "close": closes,
            "volume": [100.0] * len(closes),
        }
    )


class ChanStructureReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit.build_report(ROOT)
        audit.write_report(cls.report, ROOT)

    def test_pivot_is_emitted_on_confirmation_candle_not_backdated(self):
        frame = synthetic_long_structure()
        bottoms = [item for item in audit.confirmed_pivots(frame) if item["kind"] == "bottom"]
        pivot = next(item for item in bottoms if item["pivot_index"] == 4)

        self.assertEqual(pivot["confirmation_index"], 6)
        self.assertEqual(pivot["confirmation_time"], frame.iloc[6]["date"])
        self.assertGreater(pivot["confirmation_index"], pivot["pivot_index"])

    def test_long_sequence_requires_break_then_confirmed_higher_low(self):
        sequences = audit.structure_sequences(synthetic_long_structure())
        signals = sequences["long_unique_signals"]

        self.assertGreaterEqual(len(signals), 1)
        signal = next(item for item in signals if item["initial_pivot_index"] == 4)
        self.assertEqual(signal["breakout_index"], 7)
        self.assertEqual(signal["signal_confirmation_index"], 11)
        self.assertGreater(signal["retest_price"], signal["initial_price"])

    def test_prefix_recomputation_proves_no_future_signal_rewrite(self):
        frame = synthetic_long_structure()
        result = audit.prefix_causality_audit(frame)

        self.assertTrue(result["all_checks_passed"])
        self.assertFalse(result["pivot_backdating_used"])
        self.assertTrue(all(item["match"] for item in result["checks"]))

    def test_only_development_sources_are_loaded(self):
        for pair in self.report["pairs"].values():
            for source in pair["source_files"]:
                self.assertTrue(source["hash_verified"])
                self.assertNotIn("validation", source["path"].lower())
                self.assertNotIn("stage3e1-s04", source["path"].lower())

        self.assertEqual(self.report["safety"]["validation_accesses"], 0)
        self.assertEqual(self.report["safety"]["holdout_accesses"], 0)

    def test_common_window_has_btc_and_eth_hourly_data(self):
        pairs = self.report["pairs"]

        self.assertEqual(set(pairs), {"BTC/USDT:USDT", "ETH/USDT:USDT"})
        self.assertEqual(
            pairs["BTC/USDT:USDT"]["metrics"]["candles"],
            pairs["ETH/USDT:USDT"]["metrics"]["candles"],
        )
        self.assertGreater(pairs["BTC/USDT:USDT"]["metrics"]["candles"], 4000)
        self.assertEqual(pairs["BTC/USDT:USDT"]["data_quality"]["non_hourly_gaps"], 0)
        self.assertEqual(pairs["ETH/USDT:USDT"]["data_quality"]["non_hourly_gaps"], 0)

    def test_readiness_gate_is_derived_from_frozen_counts(self):
        minimum = self.report["policy"]["minimum_signals_per_side_per_pair"]
        pair_results = self.report["readiness_gate"]["pair_results"]
        for pair, details in self.report["pairs"].items():
            metrics = details["metrics"]
            gate = pair_results[pair]
            self.assertEqual(
                gate["long_coverage_pass"],
                metrics["long_higher_low_retest_signals"] >= minimum,
            )
            self.assertEqual(
                gate["short_coverage_pass"],
                metrics["short_lower_high_retest_signals"] >= minimum,
            )
            self.assertEqual(gate["causality_pass"], details["causality_audit"]["all_checks_passed"])

    def test_audit_does_not_authorize_candidate_or_backtest(self):
        safety = self.report["safety"]

        self.assertFalse(safety["strategy_modified"])
        self.assertFalse(safety["candidate_created"])
        self.assertFalse(safety["backtest_run"])
        self.assertFalse(safety["profit_metrics_used"])
        self.assertFalse(safety["live_or_dry_run_bot_touched"])

    def test_generated_json_matches_report(self):
        persisted = json.loads((ROOT / audit.OUTPUT_JSON).read_text(encoding="utf-8"))

        self.assertEqual(persisted["verdict"], self.report["verdict"])
        self.assertEqual(persisted["readiness_gate"], self.report["readiness_gate"])

    def test_guard_surface_is_exact_not_a_directory_wildcard(self):
        guard = (ROOT / "scripts/guard_harness_diff.js").read_text(encoding="utf-8")
        exact_paths = (
            "scripts/analyze_chan_structure_readiness.py",
            "tests/test_chan_structure_readiness.py",
            "research/analysis/chan-structure-readiness-v1/event-coverage-report.json",
            "research/analysis/chan-structure-readiness-v1/event-coverage-report.md",
        )
        for path in exact_paths:
            self.assertIn(f'{{ path: "{path}" }}', guard)
        self.assertNotIn(
            '{ prefix: "research/analysis/chan-structure-readiness-v1/" }',
            guard,
        )


if __name__ == "__main__":
    unittest.main()
