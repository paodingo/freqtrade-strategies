# V11.31 Longer Replay Data Source Inventory

## Summary

This report inventories V11.31 longer replay data-source readiness from
committed read-only evidence only. It does not connect to the server, download
data, run a backtest, modify strategy files, or modify bot config.

Decision:

```text
longer_replay_data_source_inventory_incomplete
```

## Sources

- `reports/v1131_observation/v1131_longer_replay_window_inventory.json`
- `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/audits/task136_v1131_longer_replay_window_data_source_authorization.md`

## Data Source Inventory

| timeframe | state | kind | 7d support | 14d support | caveat |
|---|---|---|---|---|---|
| 15m | `observed` | `server_read_only_feather_snapshot_report` | `false` | `false` | Committed replay output still uses only the latest 240 15m candles per pair. |
| 4h | `unknown` | `informative_timeframe_required_but_not_row_level_inventory` | `unknown` | `unknown` | Committed V11.31 coverage evidence says 4h informative features were used, but does not include row-level 4h window inventory. |
| 1h | `excluded` | n/a | n/a | n/a | V11.31 currently excludes 1h features because earlier checks marked exact futures OHLCV stale. |

## Per-Pair Source Matrix

| pair | 15m source | 15m total rows | latest 15m source window | committed replay rows | committed replay days | 4h source |
|---|---|---:|---|---:|---:|---|
| `ETH/USDT:USDT` | `observed` | 88271 | `2026-07-08T11:30:00+00:00` | 240 | 2.5 | `unknown` |
| `SOL/USDT:USDT` | `observed` | 88271 | `2026-07-08T11:30:00+00:00` | 240 | 2.5 | `unknown` |
| `DOGE/USDT:USDT` | `observed` | 88271 | `2026-07-08T11:30:00+00:00` | 240 | 2.5 | `unknown` |
| `LINK/USDT:USDT` | `observed` | 88271 | `2026-07-08T11:30:00+00:00` | 240 | 2.5 | `unknown` |
| `XRP/USDT:USDT` | `observed` | 88271 | `2026-07-08T11:30:00+00:00` | 240 | 2.5 | `unknown` |
| `BCH/USDT:USDT` | `observed` | 88271 | `2026-07-08T11:30:00+00:00` | 240 | 2.5 | `unknown` |

## Alpha/Taker/Protection Status

| field | state | reason |
|---|---|---|
| `wider_window_alpha_flags` | `unknown` | Committed wider watch layer is OHLCV-only. |
| `wider_window_taker_buy_pressure` | `unknown` | No committed taker-buy pressure source is available for the longer window. |
| `wider_window_taker_sell_pressure` | `unknown` | No committed taker-sell pressure source is available for the longer window. |
| `protection_or_pairlock_state` | `unknown` | No committed protection/pairlock timeline is available for the longer window. |

## Replay Gate State

| item | value |
|---|---|
| alpha-screened enabled | 23 |
| OHLCV watch-only enabled | 29 |
| sample gate | 30 |
| can reconsider backtest | `false` |
| can deploy shadow | `false` |
| reason | Longer source may exist in server feather paths, but committed evidence has not produced an aligned 7d/14d 15m+4h replay with alpha/taker/protection state. |

## Authorized Next Questions

- `confirm_longer_15m_window_by_exact_pair_set`
- `confirm_aligned_4h_informative_window`
- `confirm_7d_and_14d_coverage`
- `confirm_or_mark_unknown_alpha_taker_protection_state`
- `only_then_reconsider_backtest_gate`

## What This Cannot Conclude

- Does not prove V11.31 is profitable.
- Does not prove V11.31 is bad.
- Does not authorize a Freqtrade backtest.
- Does not authorize deployment or live shadow launch.
- Does not conclude V11.31 can replace V10.8.2, V11.29, or V11.30.

## Recommended Next Task

```text
Task 148: V11.31 Longer Replay Data Acquisition Authorization
```
