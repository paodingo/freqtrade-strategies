# TASK-0112: V11.31 Offline Replay / Backtest Plan

## Status

Completed.

## Goal

Plan the offline validation sequence for V11.31 before any replay, backtest, or
deployment is executed.

## Allowed Outputs

- `reports/audits/task112_v1131_offline_replay_backtest_plan.md`
- `tasks/active/TASK-0112-v1131-offline-replay-backtest-plan.md`

## Result

Recommended validation order:

1. local import/static compatibility check;
2. offline replay harness;
3. backtest plan only after replay passes;
4. server preflight only after backtest passes;
5. dry-run deployment only as a separate authorized task.

## Boundaries

This task did not:

- run replay;
- run backtests;
- modify strategies;
- modify configs;
- refresh data;
- deploy or restart bots;
- read secrets.

