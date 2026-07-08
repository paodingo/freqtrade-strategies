# TASK-0090: V11.30 Live Decision Trace Source Plan

## Status

Completed.

## Objective

Define a safe source plan for V11.30 live decision tracing.

## Result

The plan identifies the required per-candle fields, available read-only sources,
limitations, exact Task 91 artifact paths, and stop conditions.

## Boundaries

- No strategy changes.
- No bot config changes.
- No dashboard changes.
- No deploy changes.
- No secrets read.
- No bot start/stop/restart.
- No backtest.
- No SQLite writes.
- No orders.

## Next

Run Task 91R to add exact guard exceptions for the Task 91 artifacts.
