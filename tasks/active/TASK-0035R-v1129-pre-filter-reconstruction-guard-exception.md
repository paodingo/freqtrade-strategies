# TASK-0035R: V11.29 Pre-Filter Reconstruction Guard Exception

## Goal

Add exact guard exceptions for Task 35's read-only pre-filter signal reconstruction script and report outputs without widening any real trading, bot config, dashboard, deploy, secret, SQLite, or live/server surface.

## Preconditions

- Task 34 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task35r_v1129_pre_filter_reconstruction_guard_exception.md`
- `tasks/active/TASK-0035R-v1129-pre-filter-reconstruction-guard-exception.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- SQLite snapshot files
- live trading operations

## Completed Work

- Confirmed Task 35 paths were blocked before edits.
- Added exact exceptions for Task 35 script and output paths.
- Updated the change surface matrix.
- Verified exact Task 35 paths are allowed.
- Verified broad/real trading surfaces remain blocked.

## Verification

- `node --check scripts/guard_harness_diff.js`
- `node --check scripts/guard_trading_surface.js`
- guard self-tests for allowed and blocked paths
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 35 automatically in this task.
