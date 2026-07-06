# TASK-0036: V11.29 Short-Core Condition Calibration Plan

## Goal

Create a read-only calibration plan for V11.29 short-core conditions based on
Task 35 evidence.

## Preconditions

- Task 35 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task36_v1129_short_core_condition_calibration_plan.md`
- `tasks/active/TASK-0036-v1129-short-core-condition-calibration-plan.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- V10.8.2 strategy/config modifications
- V11.29 strategy/config modifications
- SQLite snapshot files
- live trading operations
- original dirty workspace

## Completed Work

- Summarized the Task 35 reconstruction baseline.
- Defined the short-core calibration question.
- Listed candidate calibration paths.
- Defined validation gates before any live strategy/config change.
- Recommended Task 37 as a read-only ranging-short candidate matrix.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 37
automatically.

