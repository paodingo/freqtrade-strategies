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


class RegimeAwareV64Test(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("RegimeAwareV64")
        self.assertIsNotNone(spec, "RegimeAwareV64 strategy module should exist")
        module = importlib.import_module("RegimeAwareV64")
        self.strategy_cls = module.RegimeAwareV64

    def test_position_adjustment_uses_more_aggressive_v64_risk_budget(self):
        strategy = self.strategy_cls({})

        self.assertTrue(strategy.position_adjustment_enable)
        self.assertEqual(strategy.max_entry_position_adjustment, 2)
        self.assertEqual(strategy.initial_stake_amount, 2500)
        self.assertEqual(strategy.add_stake_amount, 1500)
        self.assertEqual(strategy.max_total_stake_amount, 5000)
        self.assertEqual(strategy.min_scale_in_profit, 0.008)
        self.assertEqual(strategy.min_scale_in_minutes, 30)
        self.assertEqual(strategy.old_position_stake_floor, 2000)
        self.assertEqual(strategy.max_scale_in_account_loss_pct, 0.025)
        self.assertEqual(strategy.max_scale_in_atr_pct, 0.04)

    def test_custom_stake_amount_starts_with_v64_initial_stake(self):
        strategy = self.strategy_cls({})

        stake = strategy.custom_stake_amount(
            "BTC/USDT:USDT",
            datetime.now(timezone.utc),
            100.0,
            9999.0,
            10.0,
            9999.0,
            1.0,
            None,
            "short",
        )

        self.assertEqual(stake, 2500)

    def test_adjust_trade_position_signature_matches_freqtrade_interface(self):
        expected = list(inspect.signature(IStrategy.adjust_trade_position).parameters)
        actual = list(inspect.signature(self.strategy_cls.adjust_trade_position).parameters)

        self.assertEqual(expected, actual[: len(expected)])

    def test_adds_larger_stake_to_winning_short_when_trend_signal_continues(self):
        strategy = self.strategy_cls({})
        strategy.wallets = _Wallets(total=10000, available=4000)
        strategy.dp = _DataProvider(_signal_df(enter_short=1))

        stake = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=2500, stop_loss_abs=104.0),
            datetime.now(timezone.utc),
            100.0,
            0.012,
            10.0,
            9999.0,
            100.0,
            100.0,
            0.012,
            0.0,
        )

        self.assertEqual(stake, (1500, "v64_scale_in_1"))

    def test_scale_in_stake_is_still_capped_by_account_loss_budget(self):
        strategy = self.strategy_cls({})
        strategy.max_total_stake_amount = 10000
        strategy.wallets = _Wallets(total=10000, available=5000)
        strategy.dp = _DataProvider(_signal_df(enter_short=1))

        stake = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=5500, stop_loss_abs=104.0),
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

        self.assertEqual(stake, (750, "v64_scale_in_1"))

    def test_does_not_add_when_v64_account_loss_budget_is_spent(self):
        strategy = self.strategy_cls({})
        strategy.max_total_stake_amount = 10000
        strategy.wallets = _Wallets(total=10000, available=5000)
        strategy.dp = _DataProvider(_signal_df(enter_short=1))

        stake = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=6250, stop_loss_abs=104.0),
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

    def test_allows_higher_volatility_than_v63_but_still_has_a_cap(self):
        strategy = self.strategy_cls({})
        strategy.wallets = _Wallets(total=10000, available=4000)
        strategy.dp = _DataProvider(_signal_df(enter_short=1, atr=3.5))

        allowed = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=2500, stop_loss_abs=104.0),
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

        strategy.dp = _DataProvider(_signal_df(enter_short=1, atr=4.5))
        blocked = strategy.adjust_trade_position(
            _Trade(is_short=True, entries=1, stake_amount=2500, stop_loss_abs=104.0),
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

        self.assertEqual(allowed, (1500, "v64_scale_in_1"))
        self.assertIsNone(blocked)


class _DataProvider:
    def __init__(self, dataframe):
        self.dataframe = dataframe

    def get_analyzed_dataframe(self, pair, timeframe):
        return self.dataframe, None


class _Wallets:
    def __init__(self, *, total, available):
        self.total = total
        self.available = available

    def get_total_stake_amount(self):
        return self.total

    def get_available_stake_amount(self):
        return self.available


class _Trade:
    def __init__(
        self,
        *,
        is_short,
        entries,
        stake_amount,
        stop_loss_abs=None,
        liquidation_price=None,
        date_last_filled_utc=None,
    ):
        self.pair = "BTC/USDT:USDT"
        self.is_short = is_short
        self.nr_of_successful_entries = entries
        self.stake_amount = stake_amount
        self.stop_loss_abs = stop_loss_abs
        self.liquidation_price = liquidation_price
        self.date_last_filled_utc = date_last_filled_utc


def _signal_df(*, enter_short=0, enter_long=0, close=100, atr=1.0):
    return pd.DataFrame([
        {
            "enter_short": enter_short,
            "enter_long": enter_long,
            "close": close,
            "atr": atr,
        }
    ])


if __name__ == "__main__":
    unittest.main()
