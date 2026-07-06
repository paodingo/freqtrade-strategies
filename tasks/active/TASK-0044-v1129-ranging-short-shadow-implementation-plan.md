# TASK-0044: V11.29 Ranging-Short Shadow Implementation Plan

## Goal

Create a concrete implementation plan for the V11.29 ranging-short shadow
dry-run lane without implementing it.

## Preconditions

- Task 43 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task44_v1129_ranging_short_shadow_implementation_plan.md`
- `tasks/active/TASK-0044-v1129-ranging-short-shadow-implementation-plan.md`

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

- Defined exact proposed strategy and config file paths.
- Defined required guard exception sequence.
- Defined strategy and config implementation outline.
- Defined server runtime identity, DB, API port, and dry-run constraints.
- Defined validation, observation, stop, and rollback plans.
- Recommended Task 45R and Task 45.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 45R or
Task 45 automatically.

