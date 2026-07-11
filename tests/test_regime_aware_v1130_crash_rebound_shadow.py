import hashlib
import json
import importlib
import importlib.util
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
REPO_ROOT = Path(__file__).resolve().parents[1]
FORMAL_TELEMETRY_PATHS = (
    REPO_ROOT / "reports" / "v1130_observation" / "v1130_final_decision_telemetry.json",
    REPO_ROOT / "reports" / "v1130_observation" / "v1130_final_decision_telemetry.md",
)
sys.path.insert(0, str(STRATEGY_PATH))


def _install_freqtrade_test_stubs():
    if "freqtrade.strategy" in sys.modules:
        return

    freqtrade = types.ModuleType("freqtrade")
    strategy = types.ModuleType("freqtrade.strategy")
    strategy_interface = types.ModuleType("freqtrade.strategy.interface")
    persistence = types.ModuleType("freqtrade.persistence")
    enums = types.ModuleType("freqtrade.enums")
    talib = types.ModuleType("talib")
    talib_abstract = types.ModuleType("talib.abstract")

    class IStrategy:
        def __init__(self, config=None):
            self.config = config or {}
            self.dp = None
            self.wallets = None

    class Trade:
        pass

    class CandleType:
        FUTURES = "futures"

    def merge_informative_pair(dataframe, informative, timeframe, informative_timeframe, ffill=True):
        return dataframe

    strategy.IStrategy = IStrategy
    strategy.merge_informative_pair = merge_informative_pair
    strategy_interface.IStrategy = IStrategy
    persistence.Trade = Trade
    enums.CandleType = CandleType

    sys.modules["freqtrade"] = freqtrade
    sys.modules["freqtrade.strategy"] = strategy
    sys.modules["freqtrade.strategy.interface"] = strategy_interface
    sys.modules["freqtrade.persistence"] = persistence
    sys.modules["freqtrade.enums"] = enums
    sys.modules["talib"] = talib
    sys.modules["talib.abstract"] = talib_abstract


_install_freqtrade_test_stubs()


class RegimeAwareV1130CrashReboundShadowTest(unittest.TestCase):
    def setUp(self):
        self.formal_telemetry_hashes = {
            path: _sha256(path)
            for path in FORMAL_TELEMETRY_PATHS
        }
        self.telemetry_directory = tempfile.TemporaryDirectory(
            prefix=f"v1130-{self._testMethodName}-",
        )
        self.addCleanup(self.telemetry_directory.cleanup)
        telemetry_root = Path(self.telemetry_directory.name)
        self.telemetry_json = telemetry_root / "v1130_final_decision_telemetry.json"
        self.telemetry_md = telemetry_root / "v1130_final_decision_telemetry.md"
        self.telemetry_environment = patch.dict(os.environ, {
            "V1130_FINAL_DECISION_TELEMETRY_DISABLE": "0",
            "V1130_FINAL_DECISION_TELEMETRY_JSON": str(self.telemetry_json),
            "V1130_FINAL_DECISION_TELEMETRY_MD": str(self.telemetry_md),
        }, clear=False)
        self.telemetry_environment.start()
        self.addCleanup(self.telemetry_environment.stop)
        self.addCleanup(self._assert_formal_telemetry_unchanged)

    def _assert_formal_telemetry_unchanged(self):
        self.assertEqual(
            self.formal_telemetry_hashes,
            {path: _sha256(path) for path in FORMAL_TELEMETRY_PATHS},
        )

    def test_crash_rebound_long_enabled_when_gate_passes(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[0, "enter_short"], 0)
        self.assertEqual(result.loc[0, "enter_tag"], "v1130_crash_rebound_long")
        self.assertEqual(result.loc[0, "v1130_crash_rebound_gate"], "enabled_crash_rebound_long")

    def test_long_crowding_does_not_hard_block_crash_rebound(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])

        with _alpha_patch(_alpha_samples("topTraderAccountLongCrowding")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[0, "enter_tag"], "v1130_crash_rebound_long")
        self.assertTrue(result.loc[0, "alpha_filter_block_long"])
        self.assertFalse(result.loc[0, "alpha_filter_block_short"])

    def test_taker_sell_pressure_blocks_crash_rebound(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])

        with _alpha_patch(_alpha_samples("takerSellPressure")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "v1130_crash_rebound_gate"], "blocked_taker_sell_pressure")

    def test_alpha_short_block_blocks_crash_rebound(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])

        with _alpha_patch(_alpha_samples("shortCrowding")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "v1130_crash_rebound_gate"], "blocked_alpha_short")

    def test_missing_columns_fail_closed(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])
        dataframe = dataframe.drop(columns=["volume_mean"])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertTrue(result.loc[0, "v1130_crash_rebound_gate"].startswith("blocked_missing_columns:"))

    def test_non_allowlisted_pair_blocks_entry(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "v1130_crash_rebound_gate"], "blocked_pair_not_allowlisted")

    def test_custom_stake_caps_only_v1130_long(self):
        strategy = _strategy()

        v1130_stake = strategy.custom_stake_amount(
            "ETH/USDT:USDT",
            datetime.now(timezone.utc),
            100.0,
            2000.0,
            50.0,
            1000.0,
            1.0,
            "v1130_crash_rebound_long",
            "long",
        )
        parent_stake = strategy.custom_stake_amount(
            "ETH/USDT:USDT",
            datetime.now(timezone.utc),
            100.0,
            2000.0,
            50.0,
            1000.0,
            1.0,
            "trending_long",
            "long",
        )

        self.assertEqual(v1130_stake, 250)
        self.assertEqual(parent_stake, 1000)

    def test_custom_exit_only_handles_v1130_tag(self):
        strategy = _strategy()
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(pd.DataFrame([_crash_rebound_row(rsi=50.0)]))

        v1130_exit = strategy.custom_exit(
            "ETH/USDT:USDT",
            _Trade(enter_tag="v1130_crash_rebound_long", open_date_utc=now - timedelta(minutes=125)),
            now,
            100.0,
            0.002,
        )
        parent_exit = strategy.custom_exit(
            "ETH/USDT:USDT",
            _Trade(enter_tag="trending_long", open_date_utc=now - timedelta(minutes=125)),
            now,
            100.0,
            0.002,
        )

        self.assertEqual(v1130_exit, "v1130_rebound_time_exit")
        self.assertNotIn(parent_exit, {"v1130_rebound_take_profit", "v1130_rebound_rsi_exit", "v1130_rebound_time_exit"})

    def test_final_decision_telemetry_does_not_change_entry_decision(self):
        disabled_strategy = _strategy()
        enabled_strategy = _strategy()
        dataframe = pd.DataFrame([
            _crash_rebound_row(open=100.0, close=100.1),
            _crash_rebound_row(close=100.6),
            _crash_rebound_row(close=100.7),
        ])

        with _alpha_patch(_alpha_samples("")):
            with patch.dict(os.environ, {"V1130_FINAL_DECISION_TELEMETRY_DISABLE": "1"}, clear=False):
                disabled = disabled_strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})
        with _alpha_patch(_alpha_samples("")):
            enabled = enabled_strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        pd.testing.assert_series_equal(disabled["enter_long"], enabled["enter_long"])
        pd.testing.assert_series_equal(disabled["enter_tag"], enabled["enter_tag"])
        pd.testing.assert_series_equal(disabled["v1130_crash_rebound_gate"], enabled["v1130_crash_rebound_gate"])
        self.assertTrue(self.telemetry_json.exists())
        self.assertTrue(self.telemetry_md.exists())

        telemetry = json.loads(self.telemetry_json.read_text(encoding="utf-8"))
        self.assertEqual(telemetry["safety_verdict"], "telemetry_only_no_behavior_change")
        self.assertEqual(telemetry["metadata"]["latest_updated_pair"], "ETH/USDT:USDT")
        self.assertIn("ETH/USDT:USDT", telemetry["pairs"])
        self.assertGreaterEqual(telemetry["summary"]["enabled_rows"], 1)
        latest = telemetry["pairs"]["ETH/USDT:USDT"]["latest_rows"][-1]
        self.assertEqual(latest["pair"], {"state": "observed", "value": "ETH/USDT:USDT"})
        self.assertIn("taker_sell_pressure", latest)

    def test_repository_telemetry_hashes_stay_unchanged(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_crash_rebound_row()])

        with _alpha_patch(_alpha_samples("")):
            strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertTrue(self.telemetry_json.exists())
        self.assertTrue(self.telemetry_md.exists())
        self._assert_formal_telemetry_unchanged()

    def test_independent_temporary_outputs_do_not_overwrite_each_other(self):
        outputs = []
        for suffix in ("first", "second"):
            with tempfile.TemporaryDirectory(prefix=f"v1130-isolation-{suffix}-") as tmpdir:
                json_path = Path(tmpdir) / "telemetry.json"
                md_path = Path(tmpdir) / "telemetry.md"
                with patch.dict(os.environ, {
                    "V1130_FINAL_DECISION_TELEMETRY_JSON": str(json_path),
                    "V1130_FINAL_DECISION_TELEMETRY_MD": str(md_path),
                }, clear=False):
                    with _alpha_patch(_alpha_samples("")):
                        _strategy().populate_entry_trend(
                            pd.DataFrame([_crash_rebound_row()]),
                            {"pair": "ETH/USDT:USDT"},
                        )
                outputs.append((json.loads(json_path.read_text(encoding="utf-8")), md_path.read_text(encoding="utf-8")))

        self.assertEqual(outputs[0][0]["summary"], outputs[1][0]["summary"])
        self.assertIn("V11.30 Final Decision Telemetry", outputs[0][1])
        self.assertIn("V11.30 Final Decision Telemetry", outputs[1][1])
        self._assert_formal_telemetry_unchanged()

    def test_synthetic_test_failure_does_not_pollute_repository_telemetry(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic test failure"):
            with _alpha_patch(_alpha_samples("")):
                _strategy().populate_entry_trend(
                    pd.DataFrame([_crash_rebound_row()]),
                    {"pair": "ETH/USDT:USDT"},
                )
            raise RuntimeError("synthetic test failure")

        self.assertTrue(self.telemetry_json.exists())
        self.assertTrue(self.telemetry_md.exists())
        self._assert_formal_telemetry_unchanged()


def _strategy():
    module_name = "RegimeAwareV1130CrashReboundShadow"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"{module_name} strategy module should exist"
    module = importlib.import_module(module_name)
    return getattr(module, module_name)({})


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _crash_rebound_row(**overrides):
    row = {
        "date": pd.Timestamp("2026-07-08T00:00:00Z"),
        "open": 100.0,
        "high": 102.0,
        "low": 99.5,
        "close": 100.6,
        "volume": 100.0,
        "volume_mean": 100.0,
        "rsi": 45.0,
        "regime_4h": "ranging",
        "trend_4h_up": False,
        "trend_4h_down": False,
        "close_4h": 100.0,
        "ema21": 100.0,
        "ema55": 100.0,
        "ema200": 100.0,
        "ema21_4h": 100.0,
        "ema55_4h": 100.0,
        "adx_4h": 20.0,
        "plus_di_4h": 20.0,
        "minus_di_4h": 20.0,
        "pullback_ema_long": False,
        "bb_breakout_long": False,
        "rsi_recovery": False,
        "pullback_ema_short": False,
        "bb_breakout_short": False,
        "rsi_exhaustion": False,
        "bb_percent": 0.5,
        "range_position_24h": 0.5,
        "range_position_48h": 0.5,
        "range_width_24h": 0.03,
        "range_width_48h": 0.05,
        "bb_width_4h": 0.04,
        "bb_width_mean_4h": 0.08,
    }
    row.update(overrides)
    return row


def _alpha_samples(flags):
    return pd.DataFrame([{
        "sampled_at": "2026-07-08T00:00:00Z",
        "risk_level": "good",
        "risk_score": 5,
        "risk_flags": flags,
    }])


def _alpha_patch(samples):
    return patch("RegimeAwareV66AlphaRisk.load_alpha_risk_samples", return_value=samples)


class _DataProvider:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def get_analyzed_dataframe(self, pair, timeframe):
        return self.dataframe, None


class _Trade:
    def __init__(self, *, enter_tag, open_date_utc, is_short=False):
        self.enter_tag = enter_tag
        self.open_date_utc = open_date_utc
        self.is_short = is_short


if __name__ == "__main__":
    unittest.main()
