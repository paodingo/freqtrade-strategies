import importlib
import importlib.util
import inspect
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from freqtrade.strategy.interface import IStrategy

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))


class RegimeAwareV62Test(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("RegimeAwareV62")
        self.assertIsNotNone(spec, "RegimeAwareV62 strategy module should exist")
        module = importlib.import_module("RegimeAwareV62")
        self.strategy_cls = module.RegimeAwareV62

    def test_position_adjustment_is_enabled_with_two_additions(self):
        strategy = self.strategy_cls({})

        self.assertTrue(strategy.position_adjustment_enable)
        self.assertEqual(strategy.max_entry_position_adjustment, 2)
        self.assertEqual(strategy.initial_stake_amount, 1500)
        self.assertEqual(strategy.add_stake_amount, 1000)
        self.assertEqual(strategy.max_total_stake_amount, 3500)

    def test_adjust_trade_position_signature_matches_freqtrade_interface(self):
        expected = list(inspect.signature(IStrategy.adjust_trade_position).parameters)
        actual = list(inspect.signature(self.strategy_cls.adjust_trade_position).parameters)

        self.assertEqual(expected, actual[: len(expected)])

    def test_custom_stake_amount_starts_with_smaller_first_entry(self):
        strategy = self.strategy_cls({})

        stake = strategy.custom_stake_amount(
            "BTC/USDT:USDT",
            datetime.now(timezone.utc),
            100.0,
            2500.0,
            10.0,
            9999.0,
            1.0,
            "trending_short",
            "short",
        )

        self.assertEqual(stake, 1500)

    def test_adds_to_winning_short_when_trend_signal_continues(self):
        strategy = self.strategy_cls({})
        strategy.dp = _DataProvider(
            pd.DataFrame([{"enter_short": 1, "enter_long": 0, "close": 100}])
        )

        stake = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=1500),
            datetime.now(timezone.utc),
            100.0,
            0.018,
            10.0,
            9999.0,
            100.0,
            100.0,
            0.018,
            0.0,
        )

        self.assertEqual(stake, (1000, "v62_scale_in_1"))

    def test_does_not_add_to_old_small_position(self):
        strategy = self.strategy_cls({})
        strategy.dp = _DataProvider(
            pd.DataFrame([{"enter_short": 1, "enter_long": 0, "close": 100}])
        )

        stake = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=190),
            datetime.now(timezone.utc),
            100.0,
            0.05,
            10.0,
            9999.0,
            100.0,
            100.0,
            0.05,
            0.0,
        )

        self.assertIsNone(stake)

    def test_does_not_add_when_same_direction_signal_is_missing(self):
        strategy = self.strategy_cls({})
        strategy.dp = _DataProvider(
            pd.DataFrame([{"enter_short": 0, "enter_long": 1, "close": 100}])
        )

        stake = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=1500),
            datetime.now(timezone.utc),
            100.0,
            0.05,
            10.0,
            9999.0,
            100.0,
            100.0,
            0.05,
            0.0,
        )

        self.assertIsNone(stake)


class _DataProvider:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def get_analyzed_dataframe(self, pair, timeframe):
        return self.dataframe, None


class _Trade:
    def __init__(self, *, is_short, entries, stake_amount):
        self.pair = "BTC/USDT:USDT"
        self.is_short = is_short
        self.nr_of_successful_entries = entries
        self.stake_amount = stake_amount


if __name__ == "__main__":
    unittest.main()
