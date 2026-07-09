# TASK-0122: V11.31 Replay Coverage Extension Implementation

## Objective

Implement the exact-path V11.31 replay coverage extension generator approved by
Tasks 119 and 121.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Readiness checks: passed
- Task 121 guard exception committed

## Allowed Files

- `scripts/build_v1131_loose_range_replay_coverage_extension.js`
- `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json`
- `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md`
- `reports/audits/task122_v1131_replay_coverage_extension_implementation.md`
- `tasks/active/TASK-0122-v1131-replay-coverage-extension-implementation.md`

## Forbidden Surfaces

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- server operations
- bot start/stop/restart
- Freqtrade backtests

## Result

The generator creates JSON and Markdown reports from committed/read-only
evidence. It finds that alpha-screened V11.31 proxy replay remains below the
initial backtest gate.

## Stop Condition

Stop after generating outputs and verification. Do not run backtests or deploy.

