# TASK-0094R: V11.30 Market Data Refresh Pipeline Diagnosis

## Status

Completed.

## Objective

Diagnose why V11.30 market data content is stale and define a safe refresh
plan.

## Result

There is no current safe automated V11.30-specific refresh pipeline.

The active cron path runs the legacy `scripts/refresh_data.sh`, which targets
older configs and old bot sets. It is not safe to use as the V11.30 data
freshness fix.

## Key Finding

The Task 80 corrected command without `--prepend` is still the approved command
shape for a one-time V11.30 OHLCV refresh, but this task did not execute it.

## Boundaries

- No data refresh executed.
- No bot start/stop/restart.
- No strategy changes.
- No bot config changes.
- No dashboard changes.
- No deploy changes.
- No secrets read.
- No backtests.

## Next

Run:

```text
Task 94S: Execute one-time V11.30 safe market data refresh
```
