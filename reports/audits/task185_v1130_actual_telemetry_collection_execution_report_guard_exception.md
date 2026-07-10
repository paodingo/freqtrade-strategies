# Task 185: V11.30 Actual Telemetry Collection Execution Report Guard Exception

## Summary

Added narrow guard exceptions for the exact V11.30 actual telemetry collection
execution report paths approved by Task 182.

Decision:

```text
exact_paths_allowed_no_broad_v1130_surface
```

## Source Reviewed

```text
reports/audits/task182_v1130_actual_telemetry_collection_execution_report_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1130_live_telemetry_server_collection_actual_execution_report.js
reports/v1130_observation/v1130_live_telemetry_server_collection_actual_execution_report.json
reports/v1130_observation/v1130_live_telemetry_server_collection_actual_execution_report.md
```

## Explicitly Not Added

The guards were not widened to `scripts/build_v1130_*`,
`reports/v1130_observation/**`, or `reports/**/*v1130*`.

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
v1130 actual builder harness self-test: pass
v1130 actual json trading self-test: pass
v1130 broad report trading self-test: blocked
strategy blocked self-test: blocked
config blocked self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 188: V11.30 Actual Telemetry Collection Execution Report Implementation
```
