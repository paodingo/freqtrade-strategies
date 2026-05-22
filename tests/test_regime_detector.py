import pandas as pd
import numpy as np
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


def test_detect_all_trending_votes():
    """All 3 votes trending -> should switch to trending after confirmation."""
    d = RegimeDetector(confirmation_candles=3)
    row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)

    for _ in range(3):
        result = d.detect(row)
    assert result == RegimeDetector.TRENDING


def test_detect_all_ranging_votes():
    """All 3 votes ranging -> should switch to ranging after confirmation."""
    d = RegimeDetector(confirmation_candles=3)
    row = make_4h_df(adx=15, bb_width=0.02, bb_width_mean=0.04, atr=50, atr_mean=80)

    for _ in range(3):
        result = d.detect(row)
    assert result == RegimeDetector.RANGING


def test_detect_ambiguous_maintains_current():
    """2:1 vote -> should maintain current regime."""
    d = RegimeDetector(confirmation_candles=3)
    trending_row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
    ambiguous_row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=50, atr_mean=80)

    # First establish trending
    for _ in range(3):
        d.detect(trending_row)
    assert d.is_trending()

    # Then send ambiguous (ATR vote is ranging)
    d.detect(ambiguous_row)
    assert d.is_trending()  # Should maintain trending


def test_default_is_ranging():
    d = RegimeDetector()
    assert d.is_ranging()
    assert not d.is_trending()


def test_reset():
    d = RegimeDetector(confirmation_candles=3)
    row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
    for _ in range(3):
        d.detect(row)
    assert d.is_trending()

    d.reset()
    assert d.is_ranging()
    assert not d.is_trending()


def test_hysteresis_needs_confirmation():
    """One trending row should not switch from ranging to trending."""
    d = RegimeDetector(confirmation_candles=3)
    assert d.is_ranging()

    row = make_4h_df(adx=30, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
    d.detect(row)
    assert d.is_ranging()  # Only 1 confirmation, not enough


def test_adx_grey_zone_votes_none():
    """ADX between 20-25 should not vote -> 2 votes is ambiguous."""
    d = RegimeDetector(confirmation_candles=3)
    # First establish ranging
    ranging_row = make_4h_df(adx=15, bb_width=0.02, bb_width_mean=0.04, atr=50, atr_mean=80)
    for _ in range(3):
        d.detect(ranging_row)
    assert d.is_ranging()

    # ADX=22 (grey zone), BB trending, ATR trending -> 2/3 = ambiguous
    grey_row = make_4h_df(adx=22, bb_width=0.05, bb_width_mean=0.03, atr=100, atr_mean=80)
    for _ in range(5):
        d.detect(grey_row)
    assert d.is_ranging()  # Still ranging, ambiguous maintained
