import importlib
import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))

from regime_detector import RegimeDetector


class RegimeAwareV65Test(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("RegimeAwareV65")
        self.assertIsNotNone(spec, "RegimeAwareV65 strategy module should exist")
        module = importlib.import_module("RegimeAwareV65")
        self.strategy_cls = module.RegimeAwareV65

    def test_v65_is_more_aggressive_15m_ranging_strategy(self):
        strategy = self.strategy_cls({})

        self.assertEqual(strategy.timeframe, "15m")
        self.assertTrue(strategy.enable_ranging_entries)
        self.assertEqual(strategy.minimal_roi, {"0": 0.008, "30": 0.005, "120": 0.002})
        self.assertEqual(strategy.stoploss, -0.025)
        self.assertEqual(strategy.initial_stake_amount, 3000)
        self.assertEqual(strategy.add_stake_amount, 1500)
        self.assertEqual(strategy.max_total_stake_amount, 6500)
        self.assertEqual(strategy.min_scale_in_profit, 0.004)
        self.assertEqual(strategy.min_scale_in_minutes, 15)
        self.assertEqual(strategy.max_scale_in_account_loss_pct, 0.035)
        self.assertEqual(strategy.max_scale_in_atr_pct, 0.05)

    def test_ranging_entries_are_less_restricted_by_ema200(self):
        strategy = self.strategy_cls({})
        dataframe = pd.DataFrame([
            _entry_row(bb_percent=0.18, rsi=38, close=95, ema200=100),
            _entry_row(bb_percent=0.82, rsi=62, close=105, ema200=100),
        ])

        result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[0, "enter_tag"], "ranging_long")
        self.assertEqual(result.loc[1, "enter_short"], 1)
        self.assertEqual(result.loc[1, "enter_tag"], "ranging_short")

    def test_ranging_trade_times_out_after_six_hours(self):
        strategy = self.strategy_cls({})
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(pd.DataFrame([{
            "bb_upper": 110,
            "bb_middle": 100,
            "bb_lower": 90,
            "rsi": 50,
        }]))

        exit_reason = strategy.custom_exit(
            "BTC/USDT:USDT",
            _Trade(enter_tag="ranging_long", open_date_utc=now - timedelta(hours=7)),
            now,
            96.0,
            -0.002,
        )

        self.assertEqual(exit_reason, "v65_ranging_time_stop")

    def test_short_exits_when_v65_long_signal_appears(self):
        strategy = self.strategy_cls({})
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(_signal_df(enter_long=1))

        exit_reason = strategy.custom_exit(
            "BTC/USDT:USDT",
            _Trade(enter_tag="ranging_short", open_date_utc=now - timedelta(hours=1), is_short=True),
            now,
            100.0,
            -0.003,
        )

        self.assertEqual(exit_reason, "v65_reverse_long_signal_exit")

    def test_long_exits_when_v65_short_signal_appears(self):
        strategy = self.strategy_cls({})
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(_signal_df(enter_short=1))

        exit_reason = strategy.custom_exit(
            "BTC/USDT:USDT",
            _Trade(enter_tag="ranging_long", open_date_utc=now - timedelta(hours=1), is_short=False),
            now,
            100.0,
            -0.003,
        )

        self.assertEqual(exit_reason, "v65_reverse_short_signal_exit")


def _entry_row(*, bb_percent, rsi, close, ema200):
    return {
        "regime_4h": RegimeDetector.RANGING,
        "trend_4h_up": False,
        "trend_4h_down": False,
        "close": close,
        "ema200": ema200,
        "pullback_ema_long": False,
        "bb_breakout_long": False,
        "rsi_recovery": False,
        "pullback_ema_short": False,
        "bb_breakout_short": False,
        "rsi_exhaustion": False,
        "bb_percent": bb_percent,
        "rsi": rsi,
        "volume": 100,
        "volume_mean": 100,
    }


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


def _signal_df(*, enter_short=0, enter_long=0):
    return pd.DataFrame([{
        "enter_short": enter_short,
        "enter_long": enter_long,
        "bb_upper": 110,
        "bb_middle": 100,
        "bb_lower": 90,
        "rsi": 50,
    }])


if __name__ == "__main__":
    unittest.main()
