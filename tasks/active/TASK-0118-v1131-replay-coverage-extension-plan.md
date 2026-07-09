# TASK-0118: V11.31 Replay Coverage Extension Plan

## Objective

Define the next safe validation step for `RegimeAwareV1131LooseRangeWatchShadow`
after Task 117 concluded that immediate backtest/deploy is not justified.

## Preconditions

- Current worktree: `D:\code\freqtrade-strategies-clean`
- Current branch: `codex/btc-mvp-system-harnessed`
- Starting status: clean
- Readiness checks: passed
- Source evidence:
  - `reports/audits/task117_v1131_replay_result_review.md`
  - `reports/v1131_observation/v1131_loose_range_replay_report.md`
  - `reports/v1131_observation/v1131_loose_range_replay_report.json`

## Allowed Files

- `reports/audits/task118_v1131_replay_coverage_extension_plan.md`
- `tasks/active/TASK-0118-v1131-replay-coverage-extension-plan.md`

## Forbidden Surfaces

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API keys, exchange credentials, server keys, dashboard passwords
- live/server operations
- bot start/stop/restart
- backtests

## Result

Task 118 recommends expanding V11.31 replay coverage from committed/read-only
evidence before any backtest or deploy decision.

Future exact paths proposed:

```text
scripts/build_v1131_loose_range_replay_coverage_extension.js
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md
```

## Stop Condition

Stop after generating the Task 118 report and task record. Do not implement the
coverage extension in this task.

