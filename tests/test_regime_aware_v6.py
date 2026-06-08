import importlib
import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

from freqtrade.strategy.interface import IStrategy

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))


class RegimeAwareV6Test(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec("RegimeAwareV6")
        self.assertIsNotNone(spec, "RegimeAwareV6 strategy module should exist")
        module = importlib.import_module("RegimeAwareV6")
        self.strategy_cls = module.RegimeAwareV6

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


class _Trade:
    def __init__(self, *, is_short):
        self.is_short = is_short


if __name__ == "__main__":
    unittest.main()
