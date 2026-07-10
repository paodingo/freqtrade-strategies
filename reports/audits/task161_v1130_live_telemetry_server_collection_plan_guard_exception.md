# Task 161: V11.30 Live Telemetry Server Collection Plan Guard Exception

## Summary

Added narrow guard exceptions for the exact V11.30 live telemetry server
collection plan paths approved by Task 158.

Decision:

```text
exact_paths_allowed_no_broad_v1130_surface
```

## Source Reviewed

```text
reports/audits/task158_v1130_live_telemetry_server_collection_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1130_live_telemetry_server_collection_plan.js
reports/v1130_observation/v1130_live_telemetry_server_collection_plan.json
reports/v1130_observation/v1130_live_telemetry_server_collection_plan.md
```

## Explicitly Not Added

The guards were not widened to:

```text
scripts/build_v1130_*
reports/v1130_observation/**
reports/**/*v1130*
```

## Protected Surfaces Remain Blocked

The task did not lower protections for:

```text
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
.env
user_data/monitor.env
bot lifecycle commands
backtests
live/server operations
```

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
v1130 exact builder harness self-test: pass
v1130 exact builder trading self-test: pass
v1130 broad builder trading self-test: blocked
v1130 broad report trading self-test: blocked
strategy blocked self-test: blocked
config blocked self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 164: V11.30 Live Telemetry Server Collection Plan Implementation
```
