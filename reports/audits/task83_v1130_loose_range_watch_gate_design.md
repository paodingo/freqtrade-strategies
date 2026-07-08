# Task 83: V11.30 Loose-Range Watch Gate Design

## Summary

Designed a V11.30 loose-range watch gate for telemetry and alerts only. This
task does not modify the live strategy, bot config, dashboard, or server.

Conclusion:

- keep the current live entry gate unchanged;
- add a separate watch-only gate concept with `range >= 0.008`;
- do not set `enter_long`;
- do not place orders;
- use the watch gate to measure opportunity frequency and forward behavior
  before any live threshold change.

## Evidence Basis

Task 79 sensitivity:

| scenario | candidates | enabled |
|---|---:|---:|
| baseline | 11 | 9 |
| `range_0_008` | 29 | 23 |
| combined looser | 46 | 34 |

Task 81 close-to-close proxy:

| horizon | samples | mean bps | win rate |
|---|---:|---:|---:|
| 1 candle | 23 | -1.88 | 0.3913 |
| 4 candles | 23 | 20.15 | 0.7391 |
| 8 candles | 23 | 34.13 | 0.5652 |

Interpretation:

- `range >= 0.008` is promising enough for watch telemetry;
- it is not proven enough for live trading behavior.

## Watch Gate Definition

Proposed watch-only gate:

```text
v1130_loose_range_watch
```

Candidate conditions:

- pair is in V11.30 allowed universe;
- `15m_return > 0.004`;
- `15m_range >= 0.008`;
- `35 <= rsi <= 62`;
- `volume > volume_mean * 0.8`;
- `volume > 0`;
- alpha short block is false;
- `takerSellPressure` is false.

Strict live gate remains:

```text
v1130_crash_rebound_long
```

with:

```text
15m_range >= 0.012
```

## Watch-Only Behavior

The watch gate must not:

- set `enter_long = 1`;
- set live `enter_tag`;
- alter stake sizing;
- alter exit logic;
- alter protections;
- alter bot config;
- trigger orders.

It may:

- record telemetry rows;
- emit generated JSON/Markdown reports;
- optionally emit dashboard labels after a separate dashboard task;
- count watch-only opportunities and forward outcomes.

## Suggested Telemetry Fields

Per row:

- `pair`;
- `candle_time`;
- `watch_gate`;
- `strict_gate`;
- `return_ratio`;
- `range_ratio`;
- `rsi`;
- `volume_ratio`;
- `alpha_flags`;
- `failed_live_conditions`;
- `watch_enabled`;
- `strict_enabled`;
- forward returns for `1`, `4`, and `8` candles when available.

## Promotion Rules

Do not promote `range >= 0.008` to live entry unless a later task proves:

1. offline replay/backtest survives fees, funding, slippage assumptions;
2. concentration by pair/time window is acceptable;
3. live observation records multiple watch events without operational errors;
4. risk guard behavior remains acceptable;
5. user explicitly approves a strategy change task.

## Risks

- Lower range can admit noisier candles.
- Positive proxy returns may vanish after fees/slippage.
- Small sample size: only `23` enabled examples in Task 81.
- Watch events could cluster in one regime.

## Non-Actions

This task did not:

- modify strategy code;
- modify bot configs;
- modify dashboard code;
- start, stop, or restart bots;
- read secrets;
- run backtests;
- write SQLite.

## Recommended Next Task

Proceed with:

```text
Task 84: V11.30 loose-range offline replay/backtest plan
```
