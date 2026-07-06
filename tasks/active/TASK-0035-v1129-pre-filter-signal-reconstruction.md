# TASK-0035: V11.29 Pre-Filter Signal Reconstruction

## Goal

Implement and run the read-only V11.29 pre-filter signal reconstruction generator defined in Task 34 to identify which signal layer suppresses final entries.

## Preconditions

- Task 35R committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `scripts/build_v1129_pre_filter_signal_reconstruction.js`
- `reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.json`
- `reports/v1129_execution_validation/v1129_pre_filter_signal_reconstruction.md`
- `reports/audits/task35_v1129_pre_filter_signal_reconstruction.md`
- `tasks/active/TASK-0035-v1129-pre-filter-signal-reconstruction.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**` bot configs
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

## Completed Work

- Added `scripts/build_v1129_pre_filter_signal_reconstruction.js`.
- Generated JSON and Markdown reconstruction reports.
- Reconstructed raw trend/range conditions from runtime dataframe columns.
- Reconstructed alpha filter effects.
- Reconstructed V10.2 short-core pruning effects.
- Counted V11 gate effects.
- Identified `raw_trending_short_absent` as the current primary suppressing layer.

## Verification

- `node --check scripts/build_v1129_pre_filter_signal_reconstruction.js`
- `node scripts/build_v1129_pre_filter_signal_reconstruction.js`
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 36 automatically.
