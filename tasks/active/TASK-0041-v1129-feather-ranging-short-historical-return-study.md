# TASK-0041: V11.29 Feather-Based Ranging-Short Historical Return Study

## Goal

Generate a read-only 30d feather-based historical return study for V11.29
`v66_ranging_short_edge`-like candidates derived from OHLCV.

## Preconditions

- Task 41R committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `scripts/build_v1129_feather_ranging_short_historical_return_study.js`
- `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json`
- `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md`
- `reports/audits/task41_v1129_feather_ranging_short_historical_return_study.md`
- `tasks/active/TASK-0041-v1129-feather-ranging-short-historical-return-study.md`

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
- market-data refresh or download
- live trading operations
- original dirty workspace

## Completed Work

- Added a read-only feather-based historical return study generator.
- Generated JSON and Markdown reports.
- Recomputed OHLCV-derived ranging-short-like candidates over the latest 30d
  ending 2026-07-03.
- Computed 1/2/4/8 candle forward returns, MFE, MAE, and fee-adjusted returns.
- Explicitly marked historical alpha state as `missing`.

## Verification

- `node --check scripts/build_v1129_feather_ranging_short_historical_return_study.js`
- `node scripts/build_v1129_feather_ranging_short_historical_return_study.js`
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 42
automatically.

