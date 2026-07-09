import importlib
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
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


class RegimeAwareV1131LooseRangeWatchShadowTest(unittest.TestCase):
    def test_loose_range_long_enabled_when_gate_passes(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_loose_range_row()])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[0, "enter_short"], 0)
        self.assertEqual(result.loc[0, "enter_tag"], "v1131_loose_range_watch_long")
        self.assertEqual(result.loc[0, "v1131_loose_range_gate"], "enabled_loose_range_watch_long")

    def test_loose_range_threshold_is_less_strict_than_v1130_range(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_loose_range_row(high=101.0, low=100.0, close=100.6)])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(strategy.shadow_min_15m_range, 0.008)

    def test_taker_sell_pressure_blocks_loose_range(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_loose_range_row()])

        with _alpha_patch(_alpha_samples("takerSellPressure")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "v1131_loose_range_gate"], "blocked_taker_sell_pressure")

    def test_alpha_short_block_blocks_loose_range(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_loose_range_row()])

        with _alpha_patch(_alpha_samples("shortCrowding")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "v1131_loose_range_gate"], "blocked_alpha_short")

    def test_missing_columns_fail_closed(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_loose_range_row()]).drop(columns=["volume_mean"])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "ETH/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertTrue(result.loc[0, "v1131_loose_range_gate"].startswith("blocked_missing_columns:"))

    def test_non_allowlisted_pair_blocks_entry(self):
        strategy = _strategy()
        dataframe = pd.DataFrame([_loose_range_row()])

        with _alpha_patch(_alpha_samples("")):
            result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "v1131_loose_range_gate"], "blocked_pair_not_allowlisted")

    def test_custom_stake_caps_only_v1131_long(self):
        strategy = _strategy()

        v1131_stake = strategy.custom_stake_amount(
            "ETH/USDT:USDT",
            datetime.now(timezone.utc),
            100.0,
            2000.0,
            50.0,
            1000.0,
            1.0,
            "v1131_loose_range_watch_long",
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

        self.assertEqual(v1131_stake, 250)
        self.assertEqual(parent_stake, 1000)

    def test_custom_exit_only_handles_v1131_tag(self):
        strategy = _strategy()
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(pd.DataFrame([_loose_range_row(rsi=50.0)]))

        v1131_exit = strategy.custom_exit(
            "ETH/USDT:USDT",
            _Trade(enter_tag="v1131_loose_range_watch_long", open_date_utc=now - timedelta(minutes=125)),
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

        self.assertEqual(v1131_exit, "v1131_loose_range_time_exit")
        self.assertNotIn(parent_exit, {"v1131_loose_range_take_profit", "v1131_loose_range_rsi_exit", "v1131_loose_range_time_exit"})


def _strategy():
    module_name = "RegimeAwareV1131LooseRangeWatchShadow"
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"{module_name} strategy module should exist"
    module = importlib.import_module(module_name)
    return getattr(module, module_name)({})


def _loose_range_row(**overrides):
    row = {
        "date": pd.Timestamp("2026-07-09T00:00:00Z"),
        "open": 100.0,
        "high": 101.4,
        "low": 100.2,
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
        "sampled_at": "2026-07-09T00:00:00Z",
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
