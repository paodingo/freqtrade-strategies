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


class RegimeAwareV66Test(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("RegimeAwareV66")
        self.assertIsNotNone(spec, "RegimeAwareV66 strategy module should exist")
        module = importlib.import_module("RegimeAwareV66")
        self.strategy_cls = module.RegimeAwareV66

    def test_v66_is_selective_range_trader(self):
        strategy = self.strategy_cls({})

        self.assertEqual(strategy.timeframe, "15m")
        self.assertTrue(strategy.enable_ranging_entries)
        self.assertEqual(strategy.initial_stake_amount, 2500)
        self.assertEqual(strategy.add_stake_amount, 1000)
        self.assertEqual(strategy.max_total_stake_amount, 4500)
        self.assertEqual(strategy.max_entry_position_adjustment, 1)
        self.assertEqual(strategy.min_scale_in_minutes, 30)
        self.assertEqual(strategy.max_scale_in_account_loss_pct, 0.025)
        self.assertEqual(strategy.max_scale_in_atr_pct, 0.035)

    def test_does_not_open_ranging_trade_in_box_middle(self):
        strategy = self.strategy_cls({})
        dataframe = pd.DataFrame([
            _entry_row(
                bb_percent=0.84,
                rsi=63,
                range_position_24h=0.52,
                range_position_48h=0.51,
            ),
            _entry_row(
                bb_percent=0.16,
                rsi=38,
                range_position_24h=0.48,
                range_position_48h=0.49,
            ),
        ])

        result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_short"], 0)
        self.assertEqual(result.loc[1, "enter_long"], 0)

    def test_opens_short_only_near_upper_range_edge(self):
        strategy = self.strategy_cls({})
        dataframe = pd.DataFrame([
            _entry_row(bb_percent=0.86, rsi=62, range_position_24h=0.78, range_position_48h=0.76)
        ])

        result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_short"], 1)
        self.assertEqual(result.loc[0, "enter_tag"], "v66_ranging_short_edge")

    def test_opens_long_only_near_lower_range_edge(self):
        strategy = self.strategy_cls({})
        dataframe = pd.DataFrame([
            _entry_row(bb_percent=0.14, rsi=39, range_position_24h=0.22, range_position_48h=0.24)
        ])

        result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[0, "enter_tag"], "v66_ranging_long_edge")

    def test_losing_trend_trade_exits_when_market_downgrades_to_range(self):
        strategy = self.strategy_cls({})
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(_last_candle(regime_4h=RegimeDetector.RANGING))

        exit_reason = strategy.custom_exit(
            "BTC/USDT:USDT",
            _Trade(enter_tag="trending_short", open_date_utc=now - timedelta(hours=4), is_short=True),
            now,
            100.0,
            -0.006,
        )

        self.assertEqual(exit_reason, "v66_trend_invalidated_by_range")

    def test_ranging_short_takes_profit_when_price_returns_to_box_middle(self):
        strategy = self.strategy_cls({})
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(_last_candle(range_position_24h=0.52))

        exit_reason = strategy.custom_exit(
            "BTC/USDT:USDT",
            _Trade(enter_tag="v66_ranging_short_edge", open_date_utc=now - timedelta(hours=1), is_short=True),
            now,
            100.0,
            0.003,
        )

        self.assertEqual(exit_reason, "v66_ranging_midbox_take_profit")


def _entry_row(*, bb_percent, rsi, range_position_24h, range_position_48h):
    return {
        "regime_4h": RegimeDetector.RANGING,
        "adx_4h": 34,
        "bb_width_4h": 0.05,
        "bb_width_mean_4h": 0.10,
        "trend_4h_up": False,
        "trend_4h_down": False,
        "close": 100,
        "ema200": 100,
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
        "range_position_24h": range_position_24h,
        "range_position_48h": range_position_48h,
        "range_width_24h": 0.03,
        "range_width_48h": 0.05,
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


def _last_candle(*, regime_4h=RegimeDetector.RANGING, range_position_24h=0.50):
    return pd.DataFrame([{
        "regime_4h": regime_4h,
        "enter_short": 0,
        "enter_long": 0,
        "bb_upper": 110,
        "bb_middle": 100,
        "bb_lower": 90,
        "rsi": 50,
        "range_position_24h": range_position_24h,
    }])


if __name__ == "__main__":
    unittest.main()
