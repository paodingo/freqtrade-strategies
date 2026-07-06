# TASK-0039: V11.29 Ranging-Short Offline Candidate Return Study

## Goal

Generate a read-only offline candidate return study for V11.29
`v66_ranging_short_edge` candidates.

## Preconditions

- Task 39R committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `scripts/build_v1129_ranging_short_offline_return_study.js`
- `reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.json`
- `reports/v1129_execution_validation/v1129_ranging_short_offline_return_study.md`
- `reports/audits/task39_v1129_ranging_short_offline_candidate_return_study.md`
- `tasks/active/TASK-0039-v1129-ranging-short-offline-candidate-return-study.md`

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

- Added a read-only candidate return study generator.
- Generated JSON and Markdown reports.
- Computed 1/2/4/8 candle forward returns, MFE, MAE, and fee-adjusted returns.
- Split candidates by pair and alpha short-block state.
- Classified the current study as `insufficient` because runtime candle
  coverage is shorter than the 30d calibration gate.

## Verification

- `node --check scripts/build_v1129_ranging_short_offline_return_study.js`
- `node scripts/build_v1129_ranging_short_offline_return_study.js`
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 40
automatically.

