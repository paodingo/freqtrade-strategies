# TASK-0041R: V11.29 Feather Historical Return Study Guard Exception

## Goal

Add exact guard exceptions for Task 41 feather-based historical return study
paths without weakening V11.29 trading-surface protection.

## Allowed Changes

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task41r_v1129_feather_historical_return_guard_exception.md`
- `tasks/active/TASK-0041R-v1129-feather-historical-return-guard-exception.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- SQLite snapshots
- market-data files
- live/server operations

## Completed Work

- Added exact allowlist entries for the Task 41 script and two report outputs.
- Updated the change surface matrix.

## Verification

- `node --check scripts/guard_harness_diff.js`
- `node --check scripts/guard_trading_surface.js`
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Commit and push this guard exception before implementing Task 41.

