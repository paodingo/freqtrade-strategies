# TASK-0040: V11.29 Ranging-Short Historical Data Coverage Extension

## Goal

Read-only locate and assess whether V11.29 has enough 15m/4h historical candle
coverage for the next offline ranging-short return study.

## Preconditions

- Task 39 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task40_v1129_ranging_short_historical_data_coverage_extension.md`
- `tasks/active/TASK-0040-v1129-ranging-short-historical-data-coverage-extension.md`

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

- Checked clean worktree data availability.
- Checked original dirty worktree data availability read-only.
- Checked server container futures feather file availability read-only.
- Confirmed all 12 V11.29 pairs have 15m and 4h futures feather files.
- Confirmed the historical data is long enough for a 30d offline study ending
  2026-07-03.
- Identified that feather data is stale relative to 2026-07-06 runtime API
  data.
- Recommended Task 41 as a feather-based historical return study.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 41
automatically.

