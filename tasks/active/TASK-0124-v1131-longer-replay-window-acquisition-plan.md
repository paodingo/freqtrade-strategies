# TASK-0124: Longer Read-Only V11.31 Replay Window Acquisition Plan

## Objective

Plan the safest way to acquire a longer V11.31 replay evidence window after Task
123 kept backtest at `no_go`.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Task 123 concluded V11.31 remains below the backtest gate

## Allowed Files

- `reports/audits/task124_v1131_longer_replay_window_acquisition_plan.md`
- `tasks/active/TASK-0124-v1131-longer-replay-window-acquisition-plan.md`

## Result

Recommended a future read-only `7d` / `14d` `15m` + `4h` replay window
inventory before any backtest or deploy decision.

## Stop Condition

Stop after generating this plan. Do not acquire data, run backtests, modify
strategy/config, or touch server runtime.

