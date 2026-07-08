# Task 95R: V11.30 Fresh-Data Telemetry And Decision Trace

## Summary

Reran V11.30 watch-only telemetry and decision trace after Task 94V installed
and verified the dedicated market data refresh timer.

Result:

```text
fresh_data_observation_complete_zero_trades_still_observed
```

The earlier stale-data blocker is no longer the primary explanation for the
current report inputs:

- latest observed `15m` candle: `2026-07-08T11:30:00Z`
- V11.30 dry-run trades: `0`
- V11.30 dry-run orders: `0`
- V11.30 open trades: `0`
- V11.30 log-tail errors: `0`

This task does not conclude that V11.30 is a failed strategy and does not
conclude whether it can or cannot replace V10.8.2.

## Files Updated

- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.md`
- `reports/v1130_observation/v1130_decision_trace_report.json`
- `reports/v1130_observation/v1130_decision_trace_report.md`

## Files Added

- `reports/audits/task95r_v1130_fresh_data_telemetry_decision_trace.md`
- `tasks/active/TASK-0095R-v1130-fresh-data-telemetry-decision-trace.md`

## Data Sources

Read-only sources:

- server feather files under
  `/freqtrade/project/user_data/data/futures/*_USDT_USDT-15m-futures.feather`
- V11.30 dry-run SQLite opened read-only:
  `/freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite`
- V11.30 container state from `docker ps`
- V11.30 log tail from `docker logs --tail 200`

Temporary input files were generated under the Windows temp directory and were
not added to Git.

## Freshness Evidence

Generated watch-only input:

```text
input_generated_at: 2026-07-08T11:53:41Z
latest_candle_time: 2026-07-08T11:30:00Z
observation_window: last_240_15m_candles_per_pair_after_task94v_timer
```

The updated observation is based on candle content after the Task 94V timer
installation, not the older stale `06:15Z` data.

## Watch-Only Telemetry Result

Window size:

```text
1440 rows
```

Updated counts:

| metric | count |
|---|---:|
| strict candidates | 10 |
| strict enabled | 10 |
| watch candidates | 29 |
| watch enabled | 29 |
| watch-only enabled | 19 |
| not candidate | 1411 |

Watch-enabled by pair:

| pair | count |
|---|---:|
| `ETH/USDT:USDT` | 4 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 5 |
| `LINK/USDT:USDT` | 4 |
| `XRP/USDT:USDT` | 3 |
| `BCH/USDT:USDT` | 10 |

Watch-enabled by day:

| day | count |
|---|---:|
| `2026-07-06` | 12 |
| `2026-07-07` | 12 |
| `2026-07-08` | 5 |

## Latest Candle Decision Trace

Latest checked candle:

```text
2026-07-08T11:30:00Z
```

| pair | strict gate | watch gate | derived / unknown reason |
|---|---|---|---|
| `ETH/USDT:USDT` | `not_candidate` | `not_candidate` | `range` |
| `SOL/USDT:USDT` | `not_candidate` | `v1130_loose_range_watch` | `alpha_taker_protection_unknown` |
| `DOGE/USDT:USDT` | `not_candidate` | `not_candidate` | `range` |
| `LINK/USDT:USDT` | `not_candidate` | `v1130_loose_range_watch` | `alpha_taker_protection_unknown` |
| `XRP/USDT:USDT` | `not_candidate` | `not_candidate` | `range` |
| `BCH/USDT:USDT` | `not_candidate` | `not_candidate` | `rsi, volume` |

Interpretation:

- latest fresh candle has watch-only opportunities for `SOL` and `LINK`;
- latest fresh candle has no strict live candidate;
- watch-only opportunities are not order-capable and must not be treated as
  live `enter_long` signals.

## Runtime Evidence

V11.30 runtime counts:

| metric | value |
|---|---:|
| trades | 0 |
| orders | 0 |
| open trades | 0 |

Container/log state:

```text
container: freqtrade-v1130-crash-rebound-shadow|Up 9 hours|
docker logs tail lines: 200
heartbeat lines: 191
error lines: 0
```

This supports:

```text
bot_running_no_recent_log_errors_zero_orders_observed
```

It does not prove final strategy decision reasons because current read-only
sources still do not expose per-candle live strategy decision internals.

## Classification

The updated decision trace remains:

```text
insufficient
```

Reason:

```text
Existing sources do not expose the final live strategy decision path.
```

Observed/derived fields:

- `return_ratio`
- `range_ratio`
- `rsi`
- `volume_ratio`
- latest strict/watch OHLCV gate state
- V11.30 trades/orders/open-trade counts
- container state
- log-tail error count

Missing or unknown fields:

- `alpha_flags`
- `taker_buy_pressure`
- `taker_sell_pressure`
- `protection_blocked`
- `wallet_or_stake_blocked`
- `max_open_trades_blocked`
- live strategy final `enter_long` reason

## What Changed Versus Previous Observation

Previous reports were based on stale `06:15Z` candle content.

The refreshed reports now use `11:30Z` latest candle content and still show:

- no V11.30 orders;
- no V11.30 trades;
- no recent log errors;
- watch-only opportunities exist in the recent window;
- strict live candidates exist in the 240-candle window but not on the latest
  candle.

Therefore, stale data is no longer sufficient as the zero-trade explanation.

The next blocker is observability of the final live decision path.

## Safety Boundary

This task did not:

- modify strategies;
- modify bot configs;
- modify dashboard;
- modify deploy files;
- read `.env`;
- read `user_data/monitor.env`;
- print secrets;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- place orders.

## Recommended Next Task

Proceed with:

```text
Task 96R: V11.30 final decision path observability plan
```

That task should decide how to safely expose or collect the missing final
decision fields without changing live trading behavior. Candidate paths:

1. read-only inspection of strategy logs if existing debug output is present;
2. read-only dashboard/API cache inspection if it already stores per-candle
   rejection causes;
3. a future explicitly approved strategy-instrumentation task that records
   decision reasons but does not alter entry/exit logic.

Do not change live thresholds until final-decision observability exists.
