# TASK-0029: V11.29 Signal Decision Telemetry Plan

## Goal

Define a narrow read-only telemetry plan to explain why V11.29 has `trades=0/orders=0`, especially whether the cause is stale data, missing entry signals, upstream gate filtering, stake sizing, locks, capacity, or another runtime condition.

## Preconditions

- Task 28 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `reports/audits/task29_v1129_signal_decision_telemetry_plan.md`
- `tasks/active/TASK-0029-v1129-signal-decision-telemetry-plan.md`

## Forbidden Changes

- `strategies/**`
- `user_data/**` bot configs
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- API key, exchange credentials, server keys, dashboard password
- V10.8.2 strategy/config
- V11.29 strategy/config
- live trading operations

## Completed Work

- Reviewed Task 28 zero-trade signal audit.
- Documented that local downloaded/fallback futures feather data is stale and not current.
- Preserved the evidence boundary that stale local data is not yet proven to be the live zero-trade cause.
- Defined a read-only signal decision telemetry schema.
- Defined data freshness, signal gate, stake decision, and runtime context fields.
- Defined Task 30 implementation and validation boundaries.

## Verification

- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 30 automatically.
