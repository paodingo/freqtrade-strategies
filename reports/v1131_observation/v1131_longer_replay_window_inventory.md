# V11.31 Longer Replay Window Inventory

## Summary

This inventory uses committed read-only evidence only. It does not access the
server, refresh market data, run a backtest, or modify strategy/config files.

Decision:

```text
longer_window_data_not_yet_available_in_committed_evidence
```

## Sources

- `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/audits/task124_v1131_longer_replay_window_acquisition_plan.md`

## Committed Window Inventory

| timeframe | state | rows | rows per pair | approximate days per pair | latest candle | 7d support | 14d support |
|---|---|---:|---:|---:|---|---|---|
| 15m | `observed` | 1440 | 240 | 2.5 | `2026-07-08T11:30:00.000Z` | `false` | `false` |
| 4h | `unknown` | unknown | unknown | unknown | unknown | `unknown` | `unknown` |
| 1h | `excluded` | n/a | n/a | n/a | n/a | n/a | n/a |

## Replay Sample Inventory

| layer | state | value | gate | sample status |
|---|---|---:|---:|---|
| alpha-screened replay enabled | `observed` | 23 | 30 | `thin` |
| OHLCV watch-only enabled | `observed` | 29 | 30 | `thin` |
| alpha/taker/protection for wider window | `unknown` | unknown | 30 | `unknown` |

## Decision

| item | value |
|---|---|
| can reconsider backtest | `false` |
| can deploy shadow | `false` |
| can evaluate replacement | `false` |
| reason | Committed evidence covers about 2.5 days of 15m watch data and does not expose a 7d/14d alpha-screened replay or row-level 4h inventory. |

## Required Before Backtest Reconsideration

- `authorized_longer_15m_window_inventory`
- `authorized_4h_informative_window_inventory`
- `alpha_taker_protection_reconstruction_or_explicit_unknown_marking`
- `sample_count_after_final_filters_at_or_above_gate`
- `per_pair_and_per_day_concentration_review`

## Task 124 Alignment

| item | value |
|---|---|
| source mentions server/data acquisition | `true` |
| action this task | `no_server_access_no_download_no_backtest` |

## What This Cannot Conclude

- Does not prove V11.31 is profitable.
- Does not prove V11.31 is bad.
- Does not authorize a Freqtrade backtest.
- Does not authorize deployment or live shadow launch.
- Does not conclude V11.31 can replace V10.8.2, V11.29, or V11.30.

## Recommended Next Task

```text
Task 136: V11.31 Longer Replay Window Data Source Authorization
```
