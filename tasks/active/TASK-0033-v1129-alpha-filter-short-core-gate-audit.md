# TASK-0033: V11.29 Alpha Filter And Short-Core Gate Audit

## Goal

Read-only inspect alpha-risk samples and runtime dataframe gate summaries to determine whether V11.29 no-entry behavior is mainly due to alpha filter, missing `trending_short`, V10.2 short-core pruning, or later V11 gates.

## Preconditions

- Task 32 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task33_v1129_alpha_filter_short_core_gate_audit.md`
- `tasks/active/TASK-0033-v1129-alpha-filter-short-core-gate-audit.md`

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

- Verified clean worktree and readiness before edits.
- Read Task 32 entry signal semantics audit.
- Opened `monitor_history.sqlite` read-only.
- Inspected alpha-risk table names, schema, sample range, recent risk levels, and sanitized flags.
- Queried V11.29 runtime dataframe over the available multi-day API window.
- Queried V10.8.2 runtime dataframe over the available multi-day API window.
- Confirmed V11.29 has zero final entry rows over the visible window.
- Confirmed V11.29 has no surviving `trending_short` / `v102_trending_short_core` rows over the visible window.
- Confirmed alpha-risk flags broadly block long candidates and partially block short-side rows.
- Confirmed V11.29 late gates are not the observed primary blocker.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 34 automatically.
