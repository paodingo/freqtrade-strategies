# TASK-0045R: V11.29 Ranging-Short Shadow Guard Exception

## Goal

Add exact guard exceptions for the future V11.29 ranging-short shadow strategy
and config files without creating those files.

## Preconditions

- Task 44 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task45r_v1129_ranging_short_shadow_guard_exception.md`
- `tasks/active/TASK-0045R-v1129-ranging-short-shadow-guard-exception.md`

## Forbidden Changes

- creating `strategies/RegimeAwareV1129RangingShortShadow.py`
- creating `user_data/config_multi_futures_v1129_ranging_short_shadow.json`
- any other `strategies/**`
- any other `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- SQLite snapshot files
- market-data refresh or download
- live trading operations
- original dirty workspace

## Completed Work

- Added exact guard exceptions for Task 45 strategy/config paths.
- Updated the change surface matrix.
- Verified exact allowed paths pass.
- Verified broad/high-risk adjacent paths remain blocked.

## Verification

- `node --check scripts/guard_harness_diff.js`
- `node --check scripts/guard_trading_surface.js`
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 45
automatically.

