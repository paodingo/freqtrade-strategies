# Task 167: V11.30 Live Telemetry Server Collection Execution Authorization

## Summary

Reviewed the Task 164 plan-only artifact and authorized a future bounded
read-only V11.30 live telemetry server collection execution task. This task does
not connect to the server, read fresh logs, run server commands, modify files,
restart bots, or run backtests.

Decision:

```text
authorize_future_bounded_read_only_server_telemetry_collection_execution
```

## Sources Reviewed

```text
reports/audits/task164_v1130_live_telemetry_server_collection_plan_implementation.md
reports/v1130_observation/v1130_live_telemetry_server_collection_plan.json
reports/v1130_observation/v1130_live_telemetry_server_collection_plan.md
```

## Current Evidence State

| field | state |
|---|---|
| committed analysis overrun | `observed` |
| committed exchange timeout | `observed` |
| fresh log window | `not collected` |
| fresh docker stats | `not collected` |
| fresh SQLite timing join | `not collected` |
| runtime stability claim | `not allowed` |
| replacement evaluation | `not allowed` |

## Authorized Future Execution Scope

A future task may perform only bounded, read-only telemetry collection:

- `hostname` and `date`;
- bounded `docker ps --format ...`;
- bounded `docker logs --tail <bounded-lines> freqtrade-v1130-crash-rebound-shadow`;
- point-in-time `docker stats --no-stream` for approved container names;
- read-only SQLite count/timestamp queries only against explicitly approved
  paths.

## Explicitly Not Authorized

The future task is not authorized to:

- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- run full `docker inspect`;
- start, stop, restart, or deploy any bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- write SQLite data;
- modify strategy files, bot configs, dashboard files, or deploy files;
- claim V11.30 stability, profitability, or replacement fitness.

## Stop Conditions For Future Execution

The future task must stop if a command would expose secrets, change bot state,
write files, require config changes, or exceed the bounded read-only collection
scope.

## Recommended Next Task

Proceed with:

```text
Task 170: V11.30 Live Telemetry Server Collection Execution Path Review
```

