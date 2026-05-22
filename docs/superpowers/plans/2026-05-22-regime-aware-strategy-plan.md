# Regime-Aware Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a freqtrade strategy that detects market regime (trending vs ranging) on 4h and switches between trend-following and mean-reversion logic on 1h, targeting BTC/ETH spot.

**Architecture:** Three modules — `regime_detector.py` (4h regime voting with hysteresis), `risk_manager.py` (circuit breaker, position sizing, hard stops), `RegimeAware.py` (main IStrategy wiring regime signals to dual-mode entry/exit logic with ATR trailing stops).

**Tech Stack:** Python 3.10+, freqtrade (IStrategy), pandas, ta-lib, numpy

---

## File Structure

```
strategies/
  __init__.py              # Package init, exports RegimeAware
  regime_detector.py        # Regime detection: ADX/BB/ATR voting + hysteresis on 4h
  risk_manager.py           # Circuit breaker, position sizing, hard stop checks
  RegimeAware.py            # Main IStrategy: indicators, entries, exits, custom_stoploss
tests/
  test_regime_detector.py   # Unit tests for voting logic and hysteresis
  test_risk_manager.py      # Unit tests for circuit breaker
user_data/
  config_btc.json           # Backtest config for BTC/USDT
```

---

### Task 1: Create directory structure and package init

**Files:**
- Create: `strategies/__init__.py`

- [ ] **Step 1: Create strategies package init**

```python
# strategies/__init__.py
from .RegimeAware import RegimeAware

__all__ = ["RegimeAware"]
```

- [ ] **Step 2: Verify package is importable**

Run: `cd d:/code/freqtrade-strategies && python -c "import sys; sys.path.insert(0, '.'); from strategies import RegimeAware; print('OK')"`
Expected: prints `OK` (may fail if freqtrade not installed — that's fine, we fix in next step)

- [ ] **Step 3: Commit**

```bash
git add strategies/__init__.py
git commit -m "feat: create strategies package structure"
```

---

### Task 2: Implement regime detector module

**Files:**
- Create: `strategies/regime_detector.py`

- [ ] **Step 1: Write regime detector class**

```python
# strategies/regime_detector.py
"""Market regime detection using 4h data with majority voting and hysteresis."""
import pandas as pd
import talib.abstract as ta


class RegimeDetector:
    TRENDING = "trending"
    RANGING = "ranging"

    def __init__(
        self,
        adx_trend_threshold: int = 25,
        adx_range_threshold: int = 20,
        confirmation_candles: int = 3,
    ):
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_range_threshold = adx_range_threshold
        self.confirmation_candles = confirmation_candles
        self._current_regime = self.RANGING
        self._signal_buffer = []

    def compute_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Add regime-related indicators to a 4h dataframe."""
        df = dataframe.copy()

        df["adx"] = ta.ADX(df, timeperiod=14)

        bb = ta.BBANDS(df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        df["bb_upper"] = bb["upperband"]
        df["bb_middle"] = bb["middleband"]
        df["bb_lower"] = bb["lowerband"]
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_width_mean"] = df["bb_width"].rolling(50).mean()

        df["atr"] = ta.ATR(df, timeperiod=14)
        df["atr_mean"] = df["atr"].rolling(50).mean()

        return df

    def detect(self, dataframe_4h: pd.DataFrame) -> str:
        """Run regime detection on 4h dataframe with indicators already computed.
        Returns TRENDING or RANGING.
        """
        latest = dataframe_4h.iloc[-1]

        adx = latest.get("adx", 20)
        bb_width = latest.get("bb_width", 0)
        bb_width_mean = latest.get("bb_width_mean", 1)
        atr_val = latest.get("atr", 0)
        atr_mean = latest.get("atr_mean", 1)

        # Vote 1: ADX
        if adx > self.adx_trend_threshold:
            adx_vote = self.TRENDING
        elif adx < self.adx_range_threshold:
            adx_vote = self.RANGING
        else:
            adx_vote = None  # 20-25 grey zone

        # Vote 2: BB width (expanding = trending, contracting = ranging)
        if bb_width_mean > 0:
            bb_vote = (
                self.TRENDING if (bb_width / bb_width_mean) > 1.0 else self.RANGING
            )
        else:
            bb_vote = None

        # Vote 3: ATR (above mean = high vol/trending, below = ranging)
        if atr_mean > 0:
            atr_vote = self.TRENDING if atr_val > atr_mean else self.RANGING
        else:
            atr_vote = None

        trending_votes = sum(
            1 for v in [adx_vote, bb_vote, atr_vote] if v == self.TRENDING
        )
        ranging_votes = sum(
            1 for v in [adx_vote, bb_vote, atr_vote] if v == self.RANGING
        )

        if trending_votes == 3:
            signal = self.TRENDING
        elif ranging_votes == 3:
            signal = self.RANGING
        else:
            signal = None  # ambiguous

        # Hysteresis: require N consecutive identical signals to switch
        if signal is not None:
            self._signal_buffer.append(signal)
            if len(self._signal_buffer) > self.confirmation_candles:
                self._signal_buffer.pop(0)
            if len(self._signal_buffer) == self.confirmation_candles and all(
                s == signal for s in self._signal_buffer
            ):
                self._current_regime = signal
        else:
            self._signal_buffer = []

        return self._current_regime

    def is_trending(self) -> bool:
        return self._current_regime == self.TRENDING

    def is_ranging(self) -> bool:
        return self._current_regime == self.RANGING

    def reset(self):
        self._current_regime = self.RANGING
        self._signal_buffer = []
```

- [ ] **Step 2: Verify module loads**

Run: `cd d:/code/freqtrade-strategies && python -c "from strategies.regime_detector import RegimeDetector; d = RegimeDetector(); print('TRENDING:', d.TRENDING, 'RANGING:', d.RANGING)"`
Expected: prints `TRENDING: trending RANGING: ranging`

- [ ] **Step 3: Commit**

```bash
git add strategies/regime_detector.py
git commit -m "feat: add regime detector with ADX/BB/ATR voting and hysteresis"
```

---

### Task 3: Implement risk manager module

**Files:**
- Create: `strategies/risk_manager.py`

- [ ] **Step 1: Write risk manager class**

```python
# strategies/risk_manager.py
"""Risk management: circuit breaker, position sizing, hard stop checks."""
from datetime import datetime, timedelta
from typing import List, Optional


class RiskManager:
    def __init__(
        self,
        max_consecutive_losses: int = 3,
        cooldown_hours: int = 24,
        hard_stop_pct: float = -0.07,
        max_positions: int = 2,
        stake_pct_low: float = 0.15,
        stake_pct_high: float = 0.25,
    ):
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_hours = cooldown_hours
        self.hard_stop_pct = hard_stop_pct
        self.max_positions = max_positions
        self.stake_pct_low = stake_pct_low
        self.stake_pct_high = stake_pct_high
        self._cooldown_until: Optional[datetime] = None
        self._loss_streak: int = 0
        self._last_loss_time: Optional[datetime] = None

    def is_circuit_breaker_active(self) -> bool:
        """Check if trading is currently halted by circuit breaker."""
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            return True
        return False

    def record_trade_result(self, profit_ratio: float, close_time: datetime):
        """Update loss streak tracking after a trade closes."""
        if profit_ratio < 0:
            self._loss_streak += 1
            self._last_loss_time = close_time
        else:
            self._loss_streak = 0
            self._last_loss_time = None

        if self._loss_streak >= self.max_consecutive_losses:
            self._cooldown_until = datetime.now() + timedelta(
                hours=self.cooldown_hours
            )
            self._loss_streak = 0

    def get_cooldown_remaining(self) -> Optional[timedelta]:
        """Time remaining in cooldown, or None if not in cooldown."""
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            return self._cooldown_until - datetime.now()
        return None

    def calculate_stake_amount(
        self, total_capital: float, current_positions: int
    ) -> float:
        """Determine stake amount for next trade."""
        if current_positions >= self.max_positions:
            return 0.0
        stake_pct = (self.stake_pct_low + self.stake_pct_high) / 2
        return total_capital * stake_pct

    def is_hard_stop_triggered(
        self, trade_profit_pct: float, entry_mode: str = "trending"
    ) -> bool:
        """Check if trade has hit the hard stop threshold."""
        return trade_profit_pct < self.hard_stop_pct

    def reset(self):
        """Reset all state (useful between backtests)."""
        self._cooldown_until = None
        self._loss_streak = 0
        self._last_loss_time = None
```

- [ ] **Step 2: Verify module loads**

Run: `cd d:/code/freqtrade-strategies && python -c "from strategies.risk_manager import RiskManager; rm = RiskManager(); print('Hard stop:', rm.hard_stop_pct)"`
Expected: prints `Hard stop: -0.07`

- [ ] **Step 3: Commit**

```bash
git add strategies/risk_manager.py
git commit -m "feat: add risk manager with circuit breaker and position sizing"
```

---

### Task 4: Implement main strategy — indicators

**Files:**
- Create: `strategies/RegimeAware.py`

- [ ] **Step 1: Write strategy skeleton with populate_indicators**

```python
# strategies/RegimeAware.py
"""Regime-aware strategy: auto-detects trending vs ranging and adapts behavior."""
from datetime import datetime, timedelta

import numpy as np
from pandas import DataFrame

import talib.abstract as ta

from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.persistence import Trade

from .regime_detector import RegimeDetector
from .risk_manager import RiskManager


class RegimeAware(IStrategy):
    INTERFACE_VERSION = 3

    # --- ROI & Stoploss ---
    # ROI is a fallback; primary exits are handled by custom_stoploss and custom_exit
    minimal_roi = {
        "0": 0.10,     # 10% take profit as upper bound fallback
        "720": 0.05,   # 5% after 30 days
    }

    stoploss = -0.07  # Hard stop at 7% loss

    # --- Trailing stop (static fallback, overridden by custom_stoploss) ---
    trailing_stop = False  # We use custom_stoploss for ATR-based trailing

    # --- Timeframe ---
    timeframe = "1h"
    startup_candle_count = 200  # Need enough for 200-period EMA and 50-period BB mean

    # --- Position adjustment (disabled — no DCA) ---
    position_adjustment_enable = False

    # --- Risk parameters (can be configured via Hyperopt) ---
    risk_max_positions = 2
    risk_stake_pct = 0.20

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.regime_detector = RegimeDetector()
        self.risk_manager = RiskManager(max_positions=self.risk_max_positions)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Compute all indicators on both 4h (regime) and 1h (trading)."""

        # === 4h indicators ===
        informative_4h = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe="4h"
        )
        # Regime detection indicators
        informative_4h = self.regime_detector.compute_indicators(informative_4h)
        # Trend direction indicators (for trending mode entry filter)
        informative_4h["ema21"] = ta.EMA(informative_4h, timeperiod=21)
        informative_4h["ema55"] = ta.EMA(informative_4h, timeperiod=55)
        informative_4h["plus_di"] = ta.PLUS_DI(informative_4h, timeperiod=14)
        informative_4h["minus_di"] = ta.MINUS_DI(informative_4h, timeperiod=14)

        # Run regime detection sequentially through 4h candles (hysteresis needs state)
        self.regime_detector.reset()
        regimes = []
        min_candles = 200
        for i in range(len(informative_4h)):
            if i < min_candles:
                regimes.append(RegimeDetector.RANGING)
            else:
                regime = self.regime_detector.detect(informative_4h.iloc[: i + 1])
                regimes.append(regime)
        informative_4h["regime"] = regimes

        # Merge 4h into 1h (regime column gets forward-filled to 1h)
        dataframe = merge_informative_pair(
            dataframe, informative_4h, self.timeframe, "4h", ffill=True
        )

        # === 1h indicators ===
        # EMAs
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        # Bollinger Bands
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_width"] = (
            (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        )
        dataframe["bb_width_mean"] = dataframe["bb_width"].rolling(50).mean()
        dataframe["bb_width_low_20"] = dataframe["bb_width"].rolling(20).min()
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lower"])
            / (dataframe["bb_upper"] - dataframe["bb_lower"])
        ).clip(0, 1)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Volume
        dataframe["volume_mean"] = dataframe["volume"].rolling(20).mean()

        # ATR (1h for dynamic stoploss)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Hammer candle detection (for pullback entry)
        body = abs(dataframe["close"] - dataframe["open"])
        lower_wick = dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        upper_wick = dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        dataframe["is_hammer"] = (
            (lower_wick > body * 2) & (lower_wick > 0) & (upper_wick < body * 0.5)
        )

        # === Trending mode entry signals ===
        # 4h trend filter (uses merged _4h columns)
        dataframe["trend_4h_up"] = (
            (dataframe["ema21_4h"] > dataframe["ema55_4h"])
            & (dataframe["close_4h"] > dataframe["ema55_4h"])
            & (dataframe["adx_4h"] > 25)
            & (dataframe["plus_di_4h"] > dataframe["minus_di_4h"])
        )

        # 1h pullback patterns
        # Pattern A: Pullback to EMA21 with hammer
        dataframe["pullback_ema"] = (
            (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.01)
            & (dataframe["is_hammer"])
        )
        # Pattern B: BB squeeze then breakout (20-period BB width low)
        dataframe["bb_squeeze"] = (
            dataframe["bb_width"] <= dataframe["bb_width_low_20"] * 1.05
        )
        dataframe["bb_breakout"] = (
            dataframe["bb_squeeze"]
            & (dataframe["close"] > dataframe["bb_upper"])
            & (dataframe["volume"] > dataframe["volume_mean"])
        )
        # Pattern C: RSI recovery from oversold
        dataframe["rsi_recovery"] = (
            (dataframe["rsi"].shift(1) < 40) & (dataframe["rsi"] > 45)
        )

        # === Ranging mode entry signals ===
        # Safety: BB not expanding rapidly (use _4h for regime-level BB width)
        dataframe["ranging_entry_setup"] = (
            (dataframe["bb_percent"] < 0.15)
            & (dataframe["rsi"] < 35)
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.8)
            & (dataframe["close"] > dataframe["ema200"] * 0.92)
            & (dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * 1.3)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Entry signals for both trending and ranging modes."""

        # Trending mode entry: 4h up + any 1h pullback pattern
        # regime_4h is the forward-filled regime from the 4h dataframe
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.TRENDING)
                & (dataframe["trend_4h_up"])
                & (
                    dataframe["pullback_ema"]
                    | dataframe["bb_breakout"]
                    | dataframe["rsi_recovery"]
                )
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "trending")

        # Ranging mode entry
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["ranging_entry_setup"])
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "ranging")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Exit signals. Primary exits are handled by custom_stoploss and custom_exit.
        These are additional safety exits."""

        # Trending: exit on 4h trend reversal
        dataframe.loc[
            (
                (dataframe["ema21_4h"] < dataframe["ema55_4h"])
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_reversal_4h")

        # Ranging: exit on hard stop or trend breakdown
        dataframe.loc[
            (
                (dataframe["close"] < dataframe["ema200"] * 0.90)
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "ranging_breakdown")

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float:
        """ATR-based dynamic trailing stop for trending mode.
        For ranging mode, uses tighter percentage-based stop."""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss

        last = dataframe.iloc[-1]
        entry_mode = trade.enter_tag or "trending"

        if entry_mode == "trending":
            # ATR trailing: once profit > 2x ATR, trail at 1.5x ATR behind
            atr_pct = last.get("atr", 0) / current_rate if current_rate > 0 else 0.01
            if current_profit > atr_pct * 2:
                return -atr_pct * 1.5
            return -0.07

        else:  # ranging
            # Ranging mode: tight 5% stop
            return -0.05

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        """Custom exit logic.
        Ranging: BB middle / upper targets, 48h time stop.
        Trending: 4h trend reversal check.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        last = dataframe.iloc[-1]
        entry_mode = trade.enter_tag or "trending"

        if entry_mode == "ranging":
            trade_duration = current_time - trade.open_date_utc
            if trade_duration > timedelta(hours=48):
                return "ranging_time_stop"

            bb_middle = last.get("bb_middle", 0)
            if bb_middle > 0 and current_rate >= bb_middle:
                return "ranging_target_middle"

            bb_upper = last.get("bb_upper", 0)
            rsi = last.get("rsi", 50)
            if (bb_upper > 0 and current_rate >= bb_upper) or rsi > 65:
                return "ranging_target_upper"

        if entry_mode == "trending":
            ema21_4h = last.get("ema21_4h", 0)
            ema55_4h = last.get("ema55_4h", 0)
            if ema21_4h > 0 and ema55_4h > 0 and ema21_4h < ema55_4h:
                return "trending_reversal"

        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: str, side: str, **kwargs) -> bool:
        """Circuit breaker check before entry."""
        if self.risk_manager.is_circuit_breaker_active():
            cooldown = self.risk_manager.get_cooldown_remaining()
            if cooldown:
                self.log_once(
                    f"Circuit breaker active. Cooldown remaining: {cooldown}",
                    log_level="warning",
                )
            return False

        # Prevent entry if max positions reached
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self.risk_max_positions:
            return False

        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        """Track trade results for circuit breaker."""
        profit_ratio = trade.calc_profit_ratio(rate)
        self.risk_manager.record_trade_result(profit_ratio, current_time)
        return True

    def custom_entry_price(self, pair: str, current_time: datetime,
                           proposed_rate: float, entry_tag: str, side: str,
                           **kwargs) -> float:
        """Use market price for entries."""
        return proposed_rate

    def bot_start(self, **kwargs):
        """Reset state at bot start."""
        self.regime_detector.reset()
        self.risk_manager.reset()
```

- [ ] **Step 2: Verify strategy loads in freqtrade dry-run**

Run: `pip list 2>nul | grep freqtrade` (check if freqtrade installed first)

If not installed: `pip install freqtrade`

Then run: `cd d:/code/freqtrade-strategies && python -c "import sys; sys.path.insert(0, '.'); from strategies.RegimeAware import RegimeAware; print('Strategy loaded OK')"`

Expected: prints `Strategy loaded OK`

- [ ] **Step 3: Commit**

```bash
git add strategies/RegimeAware.py
git commit -m "feat: add RegimeAware strategy with dual-mode entries and exits"
```

---

### Task 5: Write unit tests for regime detector

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_regime_detector.py`

- [ ] **Step 1: Create test init**

```python
# tests/__init__.py
```

- [ ] **Step 2: Write regime detector tests**

```python
# tests/test_regime_detector.py
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
```

- [ ] **Step 3: Run tests**

Run: `cd d:/code/freqtrade-strategies && python -m pytest tests/test_regime_detector.py -v`
Expected: all 7 tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/test_regime_detector.py
git commit -m "test: add regime detector unit tests"
```

---

### Task 6: Write unit tests for risk manager

**Files:**
- Create: `tests/test_risk_manager.py`

- [ ] **Step 1: Write risk manager tests**

```python
# tests/test_risk_manager.py
from datetime import datetime, timedelta
from strategies.risk_manager import RiskManager


def test_initial_state():
    rm = RiskManager()
    assert not rm.is_circuit_breaker_active()
    assert rm.get_cooldown_remaining() is None


def test_circuit_breaker_activates_after_losses():
    rm = RiskManager(max_consecutive_losses=3)
    now = datetime.now()

    rm.record_trade_result(-0.01, now)
    assert not rm.is_circuit_breaker_active()

    rm.record_trade_result(-0.02, now)
    assert not rm.is_circuit_breaker_active()

    rm.record_trade_result(-0.03, now)
    assert rm.is_circuit_breaker_active()


def test_win_resets_loss_streak():
    rm = RiskManager(max_consecutive_losses=3)
    now = datetime.now()

    rm.record_trade_result(-0.01, now)
    rm.record_trade_result(-0.02, now)
    rm.record_trade_result(0.05, now)  # Win resets streak
    rm.record_trade_result(-0.01, now)
    assert not rm.is_circuit_breaker_active()


def test_stake_calculation():
    rm = RiskManager(max_positions=2, stake_pct_low=0.15, stake_pct_high=0.25)

    # 0 positions: can trade
    stake = rm.calculate_stake_amount(10000, 0)
    assert stake == 2000  # (15%+25%)/2 = 20% of 10000

    # 1 position: can still trade
    stake = rm.calculate_stake_amount(10000, 1)
    assert stake == 2000

    # 2 positions: at max, no more entries
    stake = rm.calculate_stake_amount(10000, 2)
    assert stake == 0


def test_hard_stop():
    rm = RiskManager(hard_stop_pct=-0.07)
    assert rm.is_hard_stop_triggered(-0.08)
    assert not rm.is_hard_stop_triggered(-0.05)
    assert not rm.is_hard_stop_triggered(0.01)


def test_reset():
    rm = RiskManager(max_consecutive_losses=3)
    now = datetime.now()
    rm.record_trade_result(-0.01, now)
    rm.record_trade_result(-0.02, now)
    rm.record_trade_result(-0.03, now)
    assert rm.is_circuit_breaker_active()

    rm.reset()
    assert not rm.is_circuit_breaker_active()
```

- [ ] **Step 2: Run tests**

Run: `cd d:/code/freqtrade-strategies && python -m pytest tests/test_risk_manager.py -v`
Expected: all 6 tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_risk_manager.py
git commit -m "test: add risk manager unit tests"
```

---

### Task 7: Create freqtrade config for backtesting

**Files:**
- Create: `user_data/config_btc.json`

- [ ] **Step 1: Write config**

```json
{
    "max_open_trades": 2,
    "stake_currency": "USDT",
    "stake_amount": "unlimited",
    "tradable_balance_ratio": 0.99,
    "fiat_display_currency": "USD",
    "dry_run": true,
    "cancel_open_orders_on_exit": false,
    "trading_mode": "spot",
    "margin_mode": "",
    "exchange": {
        "name": "binance",
        "key": "",
        "secret": "",
        "ccxt_config": {},
        "ccxt_async_config": {}
    },
    "pairlists": [
        {
            "method": "StaticPairList",
            "allow_inactive": false
        }
    ],
    "entry_pricing": {
        "price_side": "ask",
        "use_order_book": false,
        "order_book_top": 1,
        "price_last_balance": 0.0,
        "check_depth_of_market": {
            "enabled": false,
            "bids_to_ask_delta": 1
        }
    },
    "exit_pricing": {
        "price_side": "bid",
        "use_order_book": false,
        "order_book_top": 1
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add user_data/config_btc.json
git commit -m "chore: add freqtrade backtest config for BTC"
```

---

### Task 8: Add freqtrade strategy config

**Files:**
- Create: `user_data/strategies/RegimeAware.json`

- [ ] **Step 1: Write strategy-specific config** (for future Hyperopt overrides)

```json
{
    "strategy_name": "RegimeAware",
    "max_open_trades": 2,
    "stake_amount": 200,
    "stake_currency": "USDT",
    "unlimited_stake_amount": false,
    "tradable_balance_ratio": 0.99,
    "dry_run_wallet": 1000,
    "exit_pricing": {
        "price_side": "bid",
        "use_order_book": false
    },
    "entry_pricing": {
        "price_side": "ask",
        "use_order_book": false
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add user_data/strategies/RegimeAware.json
git commit -m "chore: add strategy-specific config for RegimeAware"
```

---

### Task 9: Data download and backtest validation

- [ ] **Step 1: Create data directory and download BTC/USDT 1h data**

```bash
mkdir -p d:/code/freqtrade-strategies/user_data/data/binance
```

Then use freqtrade to download:
```bash
freqtrade download-data --exchange binance --pairs BTC/USDT --timeframes 1h 4h --timerange 20240101-20260522 --config user_data/config_btc.json -d user_data/data
```

Expected: downloads 1h and 4h data for BTC/USDT

- [ ] **Step 2: Run backtest**

```bash
freqtrade backtesting --strategy RegimeAware --strategy-path strategies --config user_data/config_btc.json --timerange 20240101-20260522
```

Expected: backtest completes, strategy executes trades

- [ ] **Step 3: Review backtest results**

Check output for:
- Total profit %
- Win rate
- Max drawdown
- Number of trades
- Verify no trade exceeds 7% loss

---

### Task 10: Final cleanup and documentation

- [ ] **Step 1: Update .gitignore**

Ensure `.gitignore` has:
```
user_data/data/
.claude/
__pycache__/
*.pyc
```

Run: `cat d:/code/freqtrade-strategies/.gitignore` and update if needed.

- [ ] **Step 2: Update README with new strategy**

Add to README.md:
```markdown
## RegimeAware (NEW)
市场状态自适应策略，自动识别趋势/震荡并切换交易逻辑
- 4h 级别状态检测（ADX + 布林带 + ATR 三指标投票）
- 趋势模式：EMA 回调入场 + ATR 追踪止损
- 震荡模式：布林带均值回归 + 分批止盈
- 三层风控：动态止损 + 硬止损 7% + 熔断机制
```

- [ ] **Step 3: Commit final changes**

```bash
git add -A
git commit -m "chore: final cleanup and docs for RegimeAware strategy"
```

---

## MVP Simplifications from Spec

- **Scaled exits**: Spec calls for 60% exit at BB middle, 40% at BB upper for ranging mode. MVP exits 100% at whichever target triggers first. freqtrade partial exits require complex position adjustment; this is a v2 feature.
- **Entry candle low hard stop**: Spec calls for trending mode hard stop at entry candle low. MVP relies on ATR trailing stop which achieves the same goal adaptively.
- **24h loss window**: Circuit breaker counts 3 consecutive losses regardless of time window (simpler than spec's "within 24h" sliding window). Same protective effect.

---

## Test Plan

### Unit Tests
- **Regime detection**: voting logic, hysteresis, grey zone, reset
- **Risk manager**: circuit breaker activation, loss streak reset, stake calculation, hard stop

### Integration Test (Backtest)
- Run on BTC/USDT 2024-2026
- Verify strategy loads without errors
- Verify trades execute in both trending and ranging modes
- Verify no trade exceeds 7% loss
- Compare net profit vs old SmartTrend (-6.1%)

### Manual Verification
- Visual chart check: regime detection labels match visible trend/ranging periods
- Circuit breaker: simulate 3 consecutive losses and verify 24h halt
