# Task 143: V11.30 Live Telemetry Window Collection Authorization

## Summary

Authorized the next V11.30 runtime work as a read-only live telemetry collection
plan. This task does not reconnect to the server, inspect fresh logs, start,
stop, or restart bots, modify strategy/config files, or run backtests.

Decision:

```text
authorize_read_only_live_telemetry_window_plan
```

## Sources Reviewed

```text
reports/audits/task141_v1130_runtime_performance_audit_implementation.md
reports/v1130_observation/v1130_runtime_performance_audit.json
reports/v1130_observation/v1130_runtime_performance_audit.md
```

## Current Evidence State

| field | state |
|---|---|
| analysis overrun | `observed` |
| max observed analysis duration | `260.81s` |
| warning threshold | `225.00s` |
| exchange timeout | `observed` |
| runtime stability claim | `not allowed` |
| promotion | `blocked` |

## Authorized Future Read-Only Questions

The next telemetry task may answer only these questions:

- how many analysis-overrun warnings occur in a bounded log window;
- whether exchange/API timeouts repeat in the same window;
- whether docker CPU/memory snapshots show repeated saturation;
- whether warnings correlate with trade/order timing;
- whether V11.29 co-running appears correlated with resource contention;
- whether more instrumentation is needed before any promotion decision.

## Allowed Future Read-Only Commands

A future server-authorized task may propose commands such as:

```text
docker logs --tail <bounded-lines> freqtrade-v1130-crash-rebound-shadow
docker stats --no-stream <container names>
readonly SQLite count/timestamp queries
```

Those commands require a separate execution task. This authorization does not
run them.

## Explicitly Not Authorized

The next task is not authorized to:

- read `.env`, `user_data/monitor.env`, API keys, passwords, or tokens;
- run `docker inspect` full output;
- start, stop, restart, or deploy any bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- modify strategy files or bot config;
- claim V11.30 is stable, profitable, or replaceable.

## Proposed Future Exact Paths

If a local report builder is required, it should be reviewed by a separate exact
path task before any guard change:

```text
scripts/build_v1130_live_telemetry_window_report.js
reports/v1130_observation/v1130_live_telemetry_window_report.json
reports/v1130_observation/v1130_live_telemetry_window_report.md
```

Do not approve broad patterns such as:

```text
scripts/build_v1130_*
reports/v1130_observation/**
reports/**/*v1130*
```

## Recommended Next Task

Proceed with:

```text
Task 146: V11.30 Live Telemetry Window Exact Path Review
```

