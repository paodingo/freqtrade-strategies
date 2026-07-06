# TASK-0038: V11.29 Ranging-Short Offline Calibration Design

## Goal

Define an offline-only calibration design for the V11.29
`v66_ranging_short_edge` candidate family.

## Preconditions

- Task 37 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task38_v1129_ranging_short_offline_calibration_design.md`
- `tasks/active/TASK-0038-v1129-ranging-short-offline-calibration-design.md`

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

- Defined the narrow calibration objective for `v66_ranging_short_edge`.
- Defined required data windows and metrics.
- Defined offline calibration steps.
- Defined pass/fail gates before any live strategy/config change.
- Documented explicit non-goals and risks.
- Recommended Task 39 as a candidate-only offline return study.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 39
automatically.

