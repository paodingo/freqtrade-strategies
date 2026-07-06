# TASK-0030: V11.29 Read-Only Signal Telemetry Implementation

## Goal

Implement the narrow read-only telemetry sample generator defined by Task 29, without modifying strategies, bot configs, dashboard, deploy scripts, secrets, SQLite snapshots, or live/server state.

## Preconditions

- Task 29 committed and pushed.
- Current branch: `codex/btc-mvp-system-harnessed`.
- Worktree clean before edits.
- Readiness checks pass before edits.

## Allowed Changes

- `scripts/build_v1129_signal_decision_telemetry.js`
- `reports/v1129_execution_validation/signal_decision_telemetry_sample.json`
- `reports/v1129_execution_validation/signal_decision_telemetry_sample.md`
- `reports/audits/task30_v1129_signal_decision_telemetry.md`
- `tasks/active/TASK-0030-v1129-signal-decision-telemetry.md`
- exact guard exceptions required for the three Task 30 V11.29 telemetry paths:
  - `scripts/guard_harness_diff.js`
  - `scripts/guard_trading_surface.js`
  - `docs/harness/change_surface_matrix.md`

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
- SQLite snapshot files
- live trading operations

## Completed Work

- Added exact guard exceptions for the Task 30 telemetry script and sample outputs.
- Added `scripts/build_v1129_signal_decision_telemetry.js`.
- Generated `signal_decision_telemetry_sample.json`.
- Generated `signal_decision_telemetry_sample.md`.
- Documented that local fallback data is stale while live DataProvider freshness remains `unknown`.
- Preserved all zero-trade evidence boundaries.

## Verification

- `node --check scripts/build_v1129_signal_decision_telemetry.js`
- `node scripts/build_v1129_signal_decision_telemetry.js`
- `node --check scripts/guard_harness_diff.js`
- `node --check scripts/guard_trading_surface.js`
- `.\scripts\run_agent_readiness_checks.ps1`
- `git diff --name-only`
- `git status --short --untracked-files=all`

## Stop Condition

Stop after report, verification, commit, and push. Do not implement Task 31 automatically.
