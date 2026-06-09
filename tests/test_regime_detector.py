import numpy as np
import pandas as pd
import unittest

from strategies.regime_detector import RegimeDetector


def make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80):
    """Helper to create a single-row 4h dataframe with indicator values."""
    return pd.DataFrame([{
        "adx": adx,
        "bb_width": bb_width,
        "bb_width_mean": bb_width_mean,
        "atr": atr,
        "atr_mean": atr_mean,
        "open": 50000, "high": 51000, "low": 49000, "close": 50500, "volume": 1000,
    }])


class RegimeDetectorTest(unittest.TestCase):
    def test_detect_all_trending_votes(self):
        d = RegimeDetector(confirmation_candles=3)
        row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)

        for _ in range(3):
            result = d.detect(row)
        self.assertEqual(result, RegimeDetector.TRENDING)

    def test_detect_all_ranging_votes(self):
        d = RegimeDetector(confirmation_candles=3)
        row = make_4h_df(adx=15, bb_width=0.02, bb_width_mean=0.04, atr=50, atr_mean=80)

        for _ in range(3):
            result = d.detect(row)
        self.assertEqual(result, RegimeDetector.RANGING)

    def test_detect_ambiguous_maintains_current(self):
        d = RegimeDetector(confirmation_candles=3)
        trending_row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
        ambiguous_row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=50, atr_mean=80)

        for _ in range(3):
            d.detect(trending_row)
        self.assertTrue(d.is_trending())

        d.detect(ambiguous_row)
        self.assertTrue(d.is_trending())

    def test_default_is_ranging(self):
        d = RegimeDetector()
        self.assertTrue(d.is_ranging())
        self.assertFalse(d.is_trending())

    def test_reset(self):
        d = RegimeDetector(confirmation_candles=3)
        row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
        for _ in range(3):
            d.detect(row)
        self.assertTrue(d.is_trending())

        d.reset()
        self.assertTrue(d.is_ranging())
        self.assertFalse(d.is_trending())

    def test_hysteresis_needs_confirmation(self):
        d = RegimeDetector(confirmation_candles=3)
        self.assertTrue(d.is_ranging())

        row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
        d.detect(row)
        self.assertTrue(d.is_ranging())

    def test_adx_grey_zone_votes_none(self):
        d = RegimeDetector(confirmation_candles=3)
        ranging_row = make_4h_df(adx=15, bb_width=0.02, bb_width_mean=0.04, atr=50, atr_mean=80)
        for _ in range(3):
            d.detect(ranging_row)
        self.assertTrue(d.is_ranging())

        grey_row = make_4h_df(adx=22, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
        for _ in range(5):
            d.detect(grey_row)
        self.assertTrue(d.is_ranging())


if __name__ == "__main__":
    unittest.main()
