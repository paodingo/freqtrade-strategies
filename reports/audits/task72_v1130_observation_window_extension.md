# Task 72: V11.30 Observation Window Extension

## Summary

Performed a read-only follow-up observation of the currently running V11.30
crash-rebound shadow.

Conclusion:

- V11.30 is still running.
- V11.30 SQLite still shows `trades = 0`, `orders = 0`, and
  `open_trades = 0`.
- The observed log tail shows normal startup, pairlist load, protections, dry
  run warning, and heartbeat messages.
- No exception, traceback, exchange error, order placement, or trade event was
  observed in the checked tail.
- This observation is still too short to judge strategy quality or replacement
  readiness.

## Server Evidence

- host: `43.134.72.69`
- user: `ubuntu`
- hostname: `VM-0-8-ubuntu`
- server date observed: `2026-07-08T11:25:06+08:00`

Observed containers:

| container | status | ports |
|---|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 30 minutes` | none |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Resource snapshot:

| container | CPU | memory |
|---|---:|---:|
| `freqtrade-v1130-crash-rebound-shadow` | `0.00%` | `115.4MiB / 1.922GiB` |
| `freqtrade-v1129` | `10.98%` | `319.8MiB / 1.922GiB` |

## V11.30 DB Evidence

Checked file:

```text
user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Observed metadata:

- size: `94208` bytes
- mtime: `2026-07-08 10:54:45.750671663 +0800`

Read-only SQLite counts:

| table/query | observed count |
|---|---:|
| `trades` | 0 |
| `orders` | 0 |
| `trades where is_open = 1` | 0 |

Interpretation:

- `0` is an observed SQLite count.
- It must not be interpreted as strategy failure by itself.
- It also does not prove that V11.30 has been sufficiently observed.

## V10.8.2 Benchmark Availability

Observed local server candidate:

```text
user_data/tradesv3_v1082.dryrun.sqlite
```

Read-only counts:

| table | observed count |
|---|---:|
| `trades` | 6 |
| `orders` | 12 |

This confirms benchmark data availability only. It is not a same-window
performance comparison.

## Log Findings

Observed V11.30 log tail included:

- resolved strategy `RegimeAwareV1130CrashReboundShadow`;
- timeframe `15m`;
- stake amount `250`;
- max open trades `2`;
- `process_only_new_candles: True`;
- static pairlist with 6 pairs;
- protections: `CooldownPeriod`, `StoplossGuard`, `MaxDrawdown`;
- state changed to `RUNNING`;
- dry-run warning;
- recurring heartbeat messages.

Not observed in the checked tail:

- `exception`;
- `traceback`;
- exchange/API fatal error;
- order placement;
- trade open/close event.

## Dashboard Check Boundary

`curl http://localhost:8090/api/summary` returned `401` without credentials.

This task intentionally did not read dashboard password or secret env files, so
dashboard JSON was not fetched on the server.

## Current Interpretation

Observed:

- V11.30 process is alive.
- DB has no trades/orders.
- Logs do not show a runtime crash in the checked tail.

Unknown:

- whether every 15m cycle was analyzed successfully;
- whether gate candidates occurred after container start;
- whether gate failures are dominated by strict thresholds or by alpha-risk
  blocks;
- whether future volatile windows will trigger entries.

## Non-Actions

This task did not:

- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- run backtests;
- write SQLite;
- modify strategies or bot configs;
- modify the original dirty workspace.

## Recommended Next Task

Proceed with:

```text
Task 73: V11.30 Data Maintenance Plan For Stale Local Feather Files
```

Purpose:

- address stale local feather files without using the old hard-coded V6.5 data
  refresh script directly.
