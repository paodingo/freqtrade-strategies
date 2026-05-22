# Regime-Aware Strategy Design

## Overview

A single freqtrade strategy that automatically detects market regime (trending vs ranging) and switches between trend-following and mean-reversion logic. Targets BTC/ETH spot, long only.

## Constraints

- Platform: freqtrade
- Market: BTC/ETH spot
- Risk: medium (single stop 7%, max drawdown ~20%)
- Timeframe: multi-timeframe (4h for regime detection, 1h for entries)
- Deployment: openclaw/harmes

---

## Architecture: Three-Layer Design

```
Layer 1 — Regime Detection (4h)
  Inputs: ADX, Bollinger Band width, ATR percentile
  Output: TRENDING or RANGING (with hysteresis)

Layer 2 — Trading Logic
  Trending mode  → trend-following entries + trailing stop exits
  Ranging mode   → mean-reversion entries + target-based exits

Layer 3 — Unified Risk Layer
  ATR dynamic stop-loss, max drawdown circuit breaker,
  position sizing, max concurrent positions
```

Key rules:
- Regime switches require 3 consecutive 4h candles (12h) of agreement before switching
- When ambiguous, default to RANGING (safer)
- Only one mode trades at a time

---

## Layer 1: Regime Detection

Three indicators on 4h timeframe, majority vote:

| Indicator | TRENDING signal | RANGING signal |
|-----------|----------------|----------------|
| ADX | > 25 | < 20 |
| BB width / mean ratio | > 1.0 (expanding) | < 1.0 (contracting) |
| ATR percentile (50-period) | > 50th | < 50th |

Voting:
- 3/3 TRENDING → switch to Trending mode
- 3/3 RANGING → switch to Ranging mode
- 2:1 or ADX 20-25 → maintain current mode (hysteresis)

---

## Layer 2A: Trending Mode

### Entry (4h direction filter + 1h pullback entry)

**Step 1 — 4h confirms uptrend:**
- EMA21 > EMA55 (bullish alignment)
- Price > EMA55
- ADX > 25 AND +DI > -DI

**Step 2 — 1h pullback entry (any ONE of):**
- Pullback to EMA21 (±1%) with lower wick / hammer candle
- BB width contraction to 20-period low, then volume breakout above upper band
- RSI recovery from < 40 back to > 45

Both steps must be satisfied simultaneously.

### Exit
- **Primary**: ATR trailing stop — once profit > 2×ATR, trail stop at 1.5×ATR behind price
- **Secondary**: 4h EMA21 crosses below EMA55 (trend reversal, close all)
- **Hard stop**: Price breaks below entry candle low

### No DCA
One entry, one exit. Ride the trend.

---

## Layer 2B: Ranging Mode

### Entry (price hits "cheap zone")

All 3 conditions must be met:

| Condition | Threshold |
|-----------|-----------|
| BB position | bb_percent < 0.15 |
| RSI | < 35 |
| Volume | volume > volume_mean × 0.8 |

Safety filters:
- Price must be > EMA200 × 0.92 (filter out trending breakdowns)
- BB not expanding rapidly: bb_width < bb_width_mean × 1.3

### Exit (scaled take-profit)

- **Target 1**: Price returns to BB middle → sell 60%
- **Target 2**: Price touches BB upper OR RSI > 65 → sell remaining 40%
- **Time stop**: 48 hours without hitting any target → market sell all

### Hard stop
- 5% below entry price
- OR price < EMA200 × 0.90

---

## Layer 3: Risk Management

### Stop-loss hierarchy
| Layer | Trigger | Action |
|-------|---------|--------|
| Dynamic trailing | ATR-based (differs per mode) | Normal exit |
| Hard stop | Single trade loss > 7% | Unconditional exit |
| Circuit breaker | 3 consecutive losses in 24h | Halt trading for 24h |

### Position sizing
- 15-25% of total capital per trade
- Max 2 concurrent positions (BTC + ETH)
- Trending and ranging share the same position pool

### Capital allocation
- Signal-driven, not fixed allocation
- Both modes produce signals → trending takes priority
- No signals → stay in cash

---

## Files to Create

| File | Purpose |
|------|---------|
| `strategies/RegimeAware.py` | Main strategy class |
| `strategies/indicators.py` | Indicator calculations (regime detection, BB, ATR, etc.) |
| `strategies/risk.py` | Stop-loss and position sizing logic |

---

## Acceptance Criteria

1. Strategy loads successfully in freqtrade
2. Backtest on BTC/USDT 2024-2026 shows net profit improvement over old SmartTrend (-6.1%)
3. Regime detection correctly identifies trending vs ranging periods visually on chart
4. Circuit breaker triggers after 3 consecutive losses
5. No single trade exceeds 7% loss in backtest
