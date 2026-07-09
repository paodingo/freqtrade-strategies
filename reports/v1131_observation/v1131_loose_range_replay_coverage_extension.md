# V11.31 Loose-Range Replay Coverage Extension

## Summary

This report extends the V11.31 loose-range replay review using committed,
read-only evidence only.

Decision:

```text
coverage_extension_does_not_clear_backtest_gate
```

The expanded evidence does not authorize immediate backtest or deployment.

## Sources

- `reports/v1131_observation/v1131_loose_range_replay_report.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/v1130_observation/v1130_gate_telemetry_report.json`
- `reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json`

## Coverage Layers

| layer | state | candidates | enabled | sample status | interpretation |
|---|---|---:|---:|---|---|
| `alpha_screened_replay` | `observed` | 29 | 23 | `thin` | Closest existing proxy for V11.31 because it includes observed taker-sell blocker evidence. |
| `ohlcv_watch_only` | `observed` | 29 | 29 | `thin` | Wider OHLCV-only coverage; alpha/taker/protection filters remain unknown. |
| `strict_crash_rebound_gate` | `observed` | 9 | 9 | `thin` | Stricter V11.30 crash-rebound reference, not the V11.31 loose-range implementation target. |
| `sensitivity_combined_looser` | `derived` | 46 | 34 | `sufficient_initial` | Sensitivity-only evidence; not V11.31 exact thresholds and not authorized for strategy change. |

## Concentration

Alpha-screened enabled by pair:

| pair | enabled |
|---|---:|
| `ETH/USDT:USDT` | 3 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 6 |
| `LINK/USDT:USDT` | 3 |
| `XRP/USDT:USDT` | 2 |
| `BCH/USDT:USDT` | 6 |

OHLCV watch enabled by pair:

| pair | enabled |
|---|---:|
| `ETH/USDT:USDT` | 4 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 5 |
| `LINK/USDT:USDT` | 4 |
| `XRP/USDT:USDT` | 3 |
| `BCH/USDT:USDT` | 10 |

OHLCV watch enabled by day:

| day | enabled |
|---|---:|
| `2026-07-06` | 12 |
| `2026-07-07` | 12 |
| `2026-07-08` | 5 |

## Return Evidence

| metric | value |
|---|---:|
| alpha-screened fee-adjusted 4-candle mean bps | 10.15 |
| alpha-screened fee-adjusted 8-candle mean bps | 24.13 |
| candidate-search top net return bps | 20.15 |

## Gate Decision

| item | value |
|---|---|
| alpha-screened replay gate pass | `false` |
| OHLCV watch-only gate pass | `false` |
| can reconsider backtest | `false` |
| can deploy shadow | `false` |
| can evaluate replacement | `false` |
| reason | Alpha-screened replay remains at 23 enabled samples and OHLCV-only watch coverage reaches only 29 with alpha/taker/protection unknown. |

## Blocking Gaps

- `alpha_screened_enabled_samples_below_30`
- `ohlcv_watch_only_samples_do_not_prove_final_strategy_entry`
- `alpha_taker_protection_unknown_for_wider_watch_layer`
- `no_lifecycle_exit_distribution`
- `no_fill_slippage_funding_latency_model`
- `no_drawdown_path`
- `no_same_window_live_trade_quality_comparison`

## What This Cannot Conclude

- Does not prove V11.31 is profitable.
- Does not prove V11.31 is bad.
- Does not authorize a Freqtrade backtest.
- Does not authorize deployment or live shadow launch.
- Does not conclude V11.31 can replace V10.8.2 or V11.30.

## Recommended Next Task

```text
Task 123: V11.31 Expanded Replay Result Review / Backtest Reconsideration
```
