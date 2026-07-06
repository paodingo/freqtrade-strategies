# TASK-0042: V11.29 Ranging-Short Calibration Decision Review

## Goal

Review Task 39 and Task 41 evidence and decide the safe next step for the
V11.29 ranging-short research lane.

## Preconditions

- Task 41 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task42_v1129_ranging_short_calibration_decision_review.md`
- `tasks/active/TASK-0042-v1129-ranging-short-calibration-decision-review.md`

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

- Compared Task 39 runtime API candidate results with Task 41 feather-derived
  historical results.
- Decided not to reject the ranging-short lane outright.
- Decided not to enable live V11.29 ranging-short entries.
- Recommended a separately authorized shadow dry-run design task.
- Documented pair-filter, alpha, monitoring, database, and stop-condition
  requirements for the next task.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 43
automatically.

