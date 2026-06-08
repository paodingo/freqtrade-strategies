import importlib
import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

import pandas as pd
from freqtrade.strategy.interface import IStrategy

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))

from regime_detector import RegimeDetector


class RegimeAwareV61Test(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("RegimeAwareV61")
        self.assertIsNotNone(spec, "RegimeAwareV61 strategy module should exist")
        module = importlib.import_module("RegimeAwareV61")
        self.strategy_cls = module.RegimeAwareV61

    def test_price_callback_signatures_match_freqtrade_interface(self):
        for callback in ("custom_entry_price", "custom_exit_price"):
            with self.subTest(callback=callback):
                expected = list(
                    inspect.signature(getattr(IStrategy, callback)).parameters
                )
                actual = list(
                    inspect.signature(getattr(self.strategy_cls, callback)).parameters
                )
                self.assertEqual(expected, actual[: len(expected)])

    def test_ranging_setups_do_not_open_entries(self):
        strategy = self.strategy_cls({})
        dataframe = pd.DataFrame(
            [
                self._entry_row(
                    regime=RegimeDetector.RANGING,
                    ranging_long_setup=True,
                    close=110,
                    ema200=100,
                ),
                self._entry_row(
                    regime=RegimeDetector.RANGING,
                    ranging_short_setup=True,
                    close=90,
                    ema200=100,
                ),
            ]
        )

        result = strategy.populate_entry_trend(
            dataframe, {"pair": "BTC/USDT:USDT"}
        )

        self.assertFalse((result.get("enter_long", 0) == 1).any())
        self.assertFalse((result.get("enter_short", 0) == 1).any())

    def test_builtin_protections_are_enabled(self):
        strategy = self.strategy_cls({})
        methods = {protection["method"] for protection in strategy.protections}

        self.assertIn("CooldownPeriod", methods)
        self.assertIn("StoplossGuard", methods)
        self.assertIn("MaxDrawdown", methods)

    def test_slippage_price_callbacks_are_side_aware(self):
        strategy = self.strategy_cls({})

        self.assertAlmostEqual(
            strategy.custom_entry_price(
                "BTC/USDT:USDT", None, None, 100.0, "trending_long", "long"
            ),
            100.03,
        )
        self.assertAlmostEqual(
            strategy.custom_entry_price(
                "BTC/USDT:USDT", None, None, 100.0, "trending_short", "short"
            ),
            99.97,
        )
        self.assertAlmostEqual(
            strategy.custom_exit_price(
                "BTC/USDT:USDT", _Trade(is_short=False), None, 100.0, 0.01, "roi"
            ),
            99.97,
        )
        self.assertAlmostEqual(
            strategy.custom_exit_price(
                "BTC/USDT:USDT", _Trade(is_short=True), None, 100.0, 0.01, "roi"
            ),
            100.03,
        )

    @staticmethod
    def _entry_row(
        *,
        regime,
        ranging_long_setup=False,
        ranging_short_setup=False,
        close=100,
        ema200=100,
    ):
        return {
            "regime_4h": regime,
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
            "ranging_long_setup": ranging_long_setup,
            "ranging_short_setup": ranging_short_setup,
            "volume": 1,
        }


class _Trade:
    def __init__(self, *, is_short):
        self.is_short = is_short


if __name__ == "__main__":
    unittest.main()
