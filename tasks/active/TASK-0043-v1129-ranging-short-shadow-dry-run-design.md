# TASK-0043: V11.29 Ranging-Short Shadow Dry-Run Design

## Goal

Design a separate V11.29 ranging-short shadow dry-run lane without implementing
or deploying it.

## Preconditions

- Task 42 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task43_v1129_ranging_short_shadow_dry_run_design.md`
- `tasks/active/TASK-0043-v1129-ranging-short-shadow-dry-run-design.md`

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

- Designed a separate shadow/dry-run lane identity.
- Defined proposed strategy/config/database/container/port labels as design
  only.
- Defined pair allowlist, watch-only pairs, and excluded pairs.
- Preserved alpha blocking by default.
- Defined observation requirements and stop conditions.
- Listed files that require later explicit authorization.
- Recommended Task 44 as a concrete implementation plan.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 44
automatically.

