import importlib
import importlib.util
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))

from regime_detector import RegimeDetector


class RegimeAwareV66AlphaFamilyTest(unittest.TestCase):
    def test_v661_filters_weak_trending_short_entries(self):
        strategy_cls = _strategy_cls("RegimeAwareV661AlphaRisk")
        strategy = strategy_cls({})
        dataframe = pd.DataFrame([
            _trending_short_row(adx_4h=27, minus_di_4h=28, plus_di_4h=24),
            _trending_short_row(adx_4h=38, minus_di_4h=38, plus_di_4h=24),
        ])

        with patch("RegimeAwareV66AlphaRisk.load_alpha_risk_samples", return_value=_empty_alpha_samples()):
            result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_short"], 0)
        self.assertEqual(result.loc[1, "enter_short"], 1)
        self.assertEqual(result.loc[1, "enter_tag"], "trending_short")

    def test_v661_exits_losing_short_on_fast_bounce(self):
        strategy_cls = _strategy_cls("RegimeAwareV661AlphaRisk")
        strategy = strategy_cls({})
        now = datetime.now(timezone.utc)
        strategy.dp = _DataProvider(_last_candle(
            close=103,
            ema21=100,
            ema55=101,
            rsi=57,
            alpha_risk_flags="takerBuyPressure",
        ))

        exit_reason = strategy.custom_exit(
            "BTC/USDT:USDT",
            _Trade(enter_tag="trending_short", open_date_utc=now - timedelta(minutes=45), is_short=True),
            now,
            103.0,
            -0.006,
        )

        self.assertEqual(exit_reason, "v661_short_bounce_exit")

    def test_v662_uses_higher_capital_ceiling(self):
        strategy_cls = _strategy_cls("RegimeAwareV662AlphaRisk")
        strategy = strategy_cls({})

        self.assertEqual(strategy.initial_stake_amount, 3000)
        self.assertEqual(strategy.add_stake_amount, 1500)
        self.assertEqual(strategy.max_total_stake_amount, 6000)
        self.assertEqual(strategy.max_scale_in_account_loss_pct, 0.03)

    def test_v67_requires_clean_alpha_for_trending_shorts_when_available(self):
        strategy_cls = _strategy_cls("RegimeAwareV67AlphaRisk")
        strategy = strategy_cls({})
        dataframe = pd.DataFrame([
            _trending_short_row(date=pd.Timestamp("2026-06-10T00:00:00Z")),
            _trending_short_row(date=pd.Timestamp("2026-06-10T00:15:00Z")),
        ])

        with patch("RegimeAwareV66AlphaRisk.load_alpha_risk_samples", return_value=pd.DataFrame([
            {
                "sampled_at": "2026-06-10T00:00:00Z",
                "risk_level": "neutral",
                "risk_score": 2,
                "risk_flags": "",
            },
            {
                "sampled_at": "2026-06-10T00:15:00Z",
                "risk_level": "good",
                "risk_score": 0,
                "risk_flags": "",
            },
        ])):
            result = strategy.populate_entry_trend(dataframe, {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result.loc[0, "enter_short"], 0)
        self.assertEqual(result.loc[1, "enter_short"], 1)


def _strategy_cls(module_name):
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"{module_name} strategy module should exist"
    module = importlib.import_module(module_name)
    return getattr(module, module_name)


def _trending_short_row(**overrides):
    row = {
        "date": pd.Timestamp("2026-06-10T00:00:00Z"),
        "regime_4h": RegimeDetector.TRENDING,
        "trend_4h_up": False,
        "trend_4h_down": True,
        "close": 98.0,
        "close_4h": 96.0,
        "ema21": 100.0,
        "ema55": 102.0,
        "ema200": 105.0,
        "ema21_4h": 98.0,
        "ema55_4h": 104.0,
        "adx_4h": 38.0,
        "plus_di_4h": 24.0,
        "minus_di_4h": 38.0,
        "pullback_ema_long": False,
        "bb_breakout_long": False,
        "rsi_recovery": False,
        "pullback_ema_short": True,
        "bb_breakout_short": False,
        "rsi_exhaustion": False,
        "bb_percent": 0.42,
        "rsi": 47.0,
        "volume": 100.0,
        "volume_mean": 100.0,
        "range_position_24h": 0.5,
        "range_position_48h": 0.5,
        "range_width_24h": 0.03,
        "range_width_48h": 0.05,
        "bb_width_4h": 0.04,
        "bb_width_mean_4h": 0.08,
        "alpha_risk_level": None,
        "alpha_risk_score": None,
        "alpha_risk_flags": "",
    }
    row.update(overrides)
    return row


def _last_candle(**overrides):
    row = _trending_short_row()
    row.update({
        "enter_long": 0,
        "enter_short": 0,
        "bb_upper": 110,
        "bb_middle": 100,
        "bb_lower": 90,
    })
    row.update(overrides)
    return pd.DataFrame([row])


def _empty_alpha_samples():
    return pd.DataFrame(columns=["sampled_at", "risk_level", "risk_score", "risk_flags"])


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
