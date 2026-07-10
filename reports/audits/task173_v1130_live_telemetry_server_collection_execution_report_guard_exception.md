# Task 173: V11.30 Live Telemetry Server Collection Execution Report Guard Exception

## Summary

Added narrow guard exceptions for the exact V11.30 live telemetry server
collection execution report paths approved by Task 170.

Decision:

```text
exact_paths_allowed_no_broad_v1130_surface
```

## Source Reviewed

```text
reports/audits/task170_v1130_live_telemetry_server_collection_execution_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1130_live_telemetry_server_collection_execution_report.js
reports/v1130_observation/v1130_live_telemetry_server_collection_execution_report.json
reports/v1130_observation/v1130_live_telemetry_server_collection_execution_report.md
```

## Explicitly Not Added

The guards were not widened to:

```text
scripts/build_v1130_*
reports/v1130_observation/**
reports/**/*v1130*
```

## Protected Surfaces Remain Blocked

The task did not lower protections for `strategies/**`, `user_data/**`,
`configs/**`, `dashboard/**`, `deploy/**`, secrets, bot lifecycle commands,
backtests, or live/server operations.

## Verification

Verification completed:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Result:

```text
node --check scripts/guard_harness_diff.js: pass
node --check scripts/guard_trading_surface.js: pass
readiness: pass (9 changed path(s) checked)
v1130 execution builder harness self-test: pass
v1130 execution builder trading self-test: pass
v1130 execution json trading self-test: pass
v1130 broad builder trading self-test: blocked
v1130 broad report trading self-test: blocked
strategy blocked self-test: blocked
config blocked self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 176: V11.30 Live Telemetry Server Collection Execution Report Implementation
```
