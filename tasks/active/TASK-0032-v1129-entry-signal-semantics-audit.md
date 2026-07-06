# TASK-0032: V11.29 Entry Signal Semantics Audit

## Goal

Read-only explain why V11.29 runtime dataframe can contain non-empty `enter_tag` rows while final `enter_long` and `enter_short` remain zero.

## Preconditions

- Task 31 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task32_v1129_entry_signal_semantics_audit.md`
- `tasks/active/TASK-0032-v1129-entry-signal-semantics-audit.md`

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
- Read Task 31 runtime data freshness probe.
- Read V11.29 server container strategy files read-only.
- Read alpha-risk filter implementation read-only.
- Read V10.8.2 pair-tier code read-only.
- Queried V11.29 and V10.8.2 runtime dataframe summaries through read-only API.
- Confirmed `enter_tag` is not a final entry trigger.
- Confirmed alpha filter and short-core layers can leave tags while clearing final entry columns.
- Documented why current zero entries are not explained by missing runtime data.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 33 automatically.
