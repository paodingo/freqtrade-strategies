# Task 155: V11.30 Live Telemetry Window Server Collection Authorization

## Summary

Authorized a future V11.30 live telemetry server collection task as a bounded
read-only evidence step. This task itself does not connect to the server, read
fresh logs, run commands, modify files, restart bots, or run backtests.

Decision:

```text
authorize_future_read_only_server_telemetry_collection_plan
```

## Sources Reviewed

```text
reports/audits/task153_v1130_live_telemetry_window_report_implementation.md
reports/v1130_observation/v1130_live_telemetry_window_report.json
reports/v1130_observation/v1130_live_telemetry_window_report.md
```

## Current Evidence State

| field | state |
|---|---|
| known analysis overrun | `observed` |
| known exchange timeout | `observed` |
| fresh log window | `not collected` |
| fresh docker stats | `not collected` |
| fresh SQLite timing join | `not collected` |
| runtime stability claim | `not allowed` |
| promotion | `blocked` |

## Future Read-Only Server Collection Scope

A future task may propose bounded read-only commands such as:

```text
docker logs --tail <bounded-lines> freqtrade-v1130-crash-rebound-shadow
docker stats --no-stream <approved-container-names>
read-only SQLite count/timestamp queries
```

Those commands must avoid secrets, full `docker inspect`, writes, bot lifecycle
commands, and backtests.

## Explicitly Not Authorized

The future task is not authorized to:

- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- run full `docker inspect`;
- start, stop, restart, or deploy any bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- modify strategy files or bot config;
- claim V11.30 is stable, profitable, or replaceable.

## Recommended Next Task

Proceed with:

```text
Task 158: V11.30 Live Telemetry Server Collection Exact Path Review
```

