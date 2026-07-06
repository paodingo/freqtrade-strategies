# TASK-0034: V11.29 Pre-Filter Signal Reconstruction Plan

## Goal

Define a safe read-only plan to reconstruct V11.29 signal counts before and after alpha filtering, V10.2 short-core pruning, pair-tier/stake eligibility, and later V11 gates.

## Preconditions

- Task 33 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task34_v1129_pre_filter_signal_reconstruction_plan.md`
- `tasks/active/TASK-0034-v1129-pre-filter-signal-reconstruction-plan.md`

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
- Read Task 33 alpha filter and short-core gate audit.
- Defined the Task 35 reconstruction layers:
  - data freshness;
  - base raw trend/range conditions;
  - alpha filter effects;
  - V10.2 short-core pruning;
  - pair tier / stake eligibility;
  - V11 gate / retag effects.
- Defined Task 35 output schema.
- Defined exact guard-prep requirements if current guards block Task 35 paths.
- Defined stop conditions to avoid strategy/config/live/server/secret changes.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 35 automatically.
