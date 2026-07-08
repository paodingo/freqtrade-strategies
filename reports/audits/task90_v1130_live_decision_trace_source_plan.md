# Task 90: V11.30 Live Decision Trace Source Plan

## Summary

Define a safe source plan for V11.30 live decision tracing.

Current problem:

- V11.30 is running.
- SQLite still shows `0` trades and `0` orders.
- OHLCV-only telemetry found strict/watch candidates in the recent window.
- The live strategy's final decision path is still not observable.

This task is a plan only. It does not modify strategy code, bot config, live
state, dashboard, or server files.

## Required Decision Trace Fields

Each row should represent one pair on one candle.

Required fields:

- `pair`
- `timeframe`
- `candle_time`
- `source_kind`
- `strict_gate`
- `watch_gate`
- `return_ratio`
- `range_ratio`
- `rsi`
- `volume_ratio`
- `alpha_flags`
- `taker_buy_pressure`
- `taker_sell_pressure`
- `pairlist_included`
- `protection_blocked`
- `wallet_or_stake_blocked`
- `max_open_trades_blocked`
- `enter_long`
- `enter_tag`
- `blocked_reason`
- `data_quality`

State values must be explicit:

- `observed`
- `derived`
- `missing`
- `unknown`
- `not_applicable`
- `insufficient`

## Candidate Sources

| source | path or command | read scope | value | limitation |
|---|---|---|---|---|
| V11.30 Docker logs | `docker logs --tail <n> freqtrade-v1130-crash-rebound-shadow` | read-only | runtime state, pairlist, errors, heartbeats | usually lacks per-candle gate decisions |
| V11.30 dry-run SQLite | `/freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite` | read-only SQLite | trades/orders/open trade counts | no rejected signal rows when no orders exist |
| OHLCV feather data | `/freqtrade/project/user_data/data/futures/*-15m-futures.feather` | read-only file read | return/range/rsi/volume proxy decisions | alpha/taker/protection state unknown |
| monitor history SQLite | `/freqtrade/project/user_data/monitor_history.sqlite` | read-only schema/count inspection first | possible API/status snapshots | contents must be schema-inspected before relying on fields |
| dashboard API cache | dashboard code/cache paths | read-only inventory first | may expose display state | may be stale or derived |

## Recommended Trace Strategy

Task 91 should implement a read-only collector that produces a trace report
from existing sources only:

1. Read the Task 88 watch-only report.
2. Read V11.30 server logs tail in read-only mode.
3. Read V11.30 SQLite counts in `mode=ro`.
4. Optionally inspect `monitor_history.sqlite` schema in read-only mode.
5. Produce a JSON/Markdown report with observed, derived, missing, and unknown
   fields clearly separated.

The collector must not:

- modify strategy code;
- modify bot config;
- write SQLite;
- read `.env` or `user_data/monitor.env`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- place orders;
- claim replacement readiness.

## Exact Future Artifact Paths

Recommended exact paths for Task 91:

- `scripts/build_v1130_decision_trace_report.js`
- `reports/v1130_observation/v1130_decision_trace_report.json`
- `reports/v1130_observation/v1130_decision_trace_report.md`
- `reports/audits/task91_v1130_decision_trace_collector.md`
- `tasks/active/TASK-0091-v1130-decision-trace-collector.md`

Because `reports/v1130_observation/*` and `scripts/build_v1130_*` are not
generally allowed, Task 91R must add exact guard exceptions before Task 91.

## Stop Conditions

Stop and report instead of expanding scope if:

- live API credentials are needed;
- `.env` or `user_data/monitor.env` is needed;
- per-candle alpha/taker fields are not present in available sources;
- the only way to collect truth is to modify strategy code;
- bot restart is required.

## Recommended Next Task

Proceed with:

```text
Task 91R: Allow exact V11.30 decision trace artifact paths
```
