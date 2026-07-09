# Task 150: V11.30 Live Telemetry Window Guard Exception

## Summary

Added narrow guard exceptions for the future read-only V11.30 live telemetry
window report builder.

Decision:

```text
exact_paths_allowed_no_broad_v1130_surface
```

## Source Reviewed

```text
reports/audits/task146_v1130_live_telemetry_window_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1130_live_telemetry_window_report.js
reports/v1130_observation/v1130_live_telemetry_window_report.json
reports/v1130_observation/v1130_live_telemetry_window_report.md
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
v1130 live telemetry exact harness self-test: pass
v1130 live telemetry exact trading self-test: pass
v1130 broad report harness self-test: blocked
v1130 broad report trading self-test: blocked
v1130 broad builder trading self-test: blocked
config blocked trading self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 153: V11.30 Live Telemetry Window Report Implementation
```
