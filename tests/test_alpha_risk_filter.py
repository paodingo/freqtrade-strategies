from pathlib import Path
import sys
import unittest

import pandas as pd

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))

from alpha_risk_filter import apply_alpha_filter


class AlphaRiskFilterTest(unittest.TestCase):
    def test_level_mode_blocks_warning_entries_in_both_directions(self):
        dataframe = pd.DataFrame(
            [
                _row("2026-06-10T00:00:00Z", enter_long=1),
                _row("2026-06-10T00:15:00Z", enter_short=1),
                _row("2026-06-10T00:30:00Z", enter_long=1),
            ]
        )
        samples = pd.DataFrame(
            [
                _sample("2026-06-10T00:00:00Z", "neutral", 26, ["longCrowding"]),
                _sample("2026-06-10T00:15:00Z", "warning", 42, ["takerSellPressure"]),
            ]
        )

        result = apply_alpha_filter(dataframe, samples, mode="level")

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[1, "enter_short"], 0)
        self.assertEqual(result.loc[2, "enter_long"], 0)
        self.assertEqual(result.loc[2, "alpha_filter_block_long"], True)

    def test_directional_mode_blocks_only_hostile_side(self):
        dataframe = pd.DataFrame(
            [
                _row("2026-06-10T00:00:00Z", enter_long=1, enter_short=1),
                _row("2026-06-10T00:15:00Z", enter_long=1, enter_short=1),
            ]
        )
        samples = pd.DataFrame(
            [
                _sample("2026-06-10T00:00:00Z", "warning", 42, ["longCrowding"]),
                _sample("2026-06-10T00:15:00Z", "warning", 42, ["takerSellPressure"]),
            ]
        )

        result = apply_alpha_filter(dataframe, samples, mode="directional")

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[0, "enter_short"], 1)
        self.assertEqual(result.loc[1, "enter_long"], 1)
        self.assertEqual(result.loc[1, "enter_short"], 0)

    def test_filter_handles_freqtrade_millisecond_datetime_precision(self):
        dataframe = pd.DataFrame(
            [
                _row(pd.Timestamp("2026-06-10T00:00:00Z").as_unit("ms"), enter_short=1),
            ]
        )
        samples = pd.DataFrame(
            [
                _sample("2026-06-10T00:00:00.000000Z", "warning", 42, ["takerSellPressure"]),
            ]
        )

        result = apply_alpha_filter(dataframe, samples, mode="directional")

        self.assertEqual(result.loc[0, "enter_short"], 0)


def _row(date, *, enter_long=0, enter_short=0):
    return {
        "date": date,
        "enter_long": enter_long,
        "enter_short": enter_short,
        "enter_tag": "test_entry",
    }


def _sample(sampled_at, level, score, flags):
    return {
        "sampled_at": sampled_at,
        "risk_level": level,
        "risk_score": score,
        "risk_flags": ",".join(flags),
    }


if __name__ == "__main__":
    unittest.main()
