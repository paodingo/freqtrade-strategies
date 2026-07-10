# Task 180: V11.31 Actual Data Acquisition Execution Report Guard Exception

## Summary

Added narrow guard exceptions for the exact V11.31 actual data acquisition
execution report paths approved by Task 177.

Decision:

```text
exact_paths_allowed_no_broad_v1131_surface
```

## Source Reviewed

```text
reports/audits/task177_v1131_actual_data_acquisition_execution_report_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1131_longer_replay_data_acquisition_actual_execution_report.js
reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.json
reports/v1131_observation/v1131_longer_replay_data_acquisition_actual_execution_report.md
```

## Explicitly Not Added

The guards were not widened to:

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
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
v1131 actual builder harness self-test: pass
v1131 actual json trading self-test: pass
v1131 actual md trading self-test: pass
v1131 broad builder trading self-test: blocked
v1131 broad report trading self-test: blocked
strategy blocked self-test: blocked
config blocked self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 183: V11.31 Actual Data Acquisition Execution Report Implementation
```
