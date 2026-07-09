# Candidate Search Summary: 2026-07-09 V11.30 15m+4h First Pass

## Summary

This is an offline, read-only candidate-search harness output. It aggregates existing reports only.

Conclusion:

```text
first_pass_top_candidate_v1130_loose_range_watch
```

This report does not run a backtest, does not modify strategy/config files, and does not claim V11.30 can replace V10.8.2.

## Data Gate

| item | status |
|---|---|
| run id | `2026-07-09-v1130-15m-4h-first-pass` |
| generated at | `2026-07-09T03:25:39.575Z` |
| 15m OHLCV | `ready` |
| 4h OHLCV | `ready` |
| 1h OHLCV | `excluded_stale` |
| backtest run | `false` |
| strategy modified | `false` |
| bot config modified | `false` |
| server operation | `false` |

## Candidate Matrix

| rank | candidate | score | samples | net bps | positive rate | data status | note |
|---:|---|---:|---:|---:|---:|---|---|
| 1 | `v1130_loose_range_watch` | 51.64 | 23 | 20.15 | 0.7391 | `ready_15m_4h_1h_excluded_stale` | Loose-range watch replay: 4-candle mean 20.15 bps, 8-candle mean 34.13 bps; not an order-capable proof. |
| 2 | `crash_rebound_continuation` | 49.45 | 15 | 21.5559 | 0.6667 | `ready_15m_4h_1h_excluded_stale` | Best high-volatility replay ranking; V11.30 live path confirms order-capable behavior but early live quality is insufficient. |
| 3 | `ranging_short_volatility_fade` | 47.94 | 1214 | 7.3426 | 0.5817 | `historical_only_latest_window_not_included` | Large 30d OHLCV-derived sample, but alpha state is missing and this is not a Freqtrade backtest or execution report. |
| 4 | `blowoff_short_fade` | 32.71 | 1075 | -18.653 | 0.4009 | `ready_15m_4h_1h_excluded_stale` | Large replay sample but negative fee-adjusted mean; keep as risk/control family, not first implementation target. |
| 5 | `selloff_continuation_short` | 29.46 | 122 | -19.9735 | 0.3361 | `ready_15m_4h_1h_excluded_stale` | Enough replay samples, but 4-candle fee-adjusted mean is negative in existing evidence. |

## Blocking Gaps

- Recent `1h` futures OHLCV remains stale and is excluded from this pass.
- Profit factor, max drawdown, exit reason distribution, and live execution quality are unavailable for most offline candidates.
- V11.30 live sample remains insufficient and must not be used for replacement conclusions.
- Ranging-short alpha state is missing in historical OHLCV-derived evidence.

## Recommended Next Task

```text
Task 108: Candidate Search First-Pass Review And Implementation Target Decision
```
