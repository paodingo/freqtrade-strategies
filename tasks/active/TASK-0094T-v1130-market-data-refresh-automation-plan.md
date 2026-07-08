# TASK-0094T: V11.30 Market Data Refresh Automation Plan

## Status

Completed.

## Objective

Define a safe V11.30-specific market data refresh automation plan without
installing automation or modifying server files.

## Result

Plan completed.

Recommended path:

1. create a dedicated V11.30 OHLCV-only script;
2. give that script an exact guard exception;
3. verify it does not start, stop, restart, or trade;
4. install a dedicated timer only in a separate authorized task;
5. observe at least one timer cycle before rerunning V11.30 telemetry.

## Key Decision

Do not reuse `scripts/refresh_data.sh`.

Reason:

```text
legacy multi-bot maintenance script with bot lifecycle side effects
```

## Recommended Next

Run:

```text
Task 94U: Implement V11.30 OHLCV-only refresh script
```

Then:

```text
Task 94V: Install and verify V11.30 market data refresh timer
```

## Boundaries

- No cron installed.
- No systemd timer installed.
- No server files modified.
- No data refresh run.
- No bot start/stop/restart.
- No strategy changes.
- No bot config changes.
- No dashboard or deploy changes.
- No secrets read.
