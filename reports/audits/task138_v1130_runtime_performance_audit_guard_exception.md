# Task 138: V11.30 Runtime Performance Audit Guard Exception

## Summary

Added narrow guard exceptions for the future telemetry-only V11.30 runtime
performance audit report builder.

Decision:

```text
exact_paths_allowed_no_broad_v1130_surface
```

## Source Reviewed

```text
reports/audits/task135_v1130_runtime_performance_audit_path_review.md
```

## Exact Paths Added

Added only these exact paths to `scripts/guard_harness_diff.js` and
`scripts/guard_trading_surface.js`:

```text
scripts/build_v1130_runtime_performance_audit.js
reports/v1130_observation/v1130_runtime_performance_audit.json
reports/v1130_observation/v1130_runtime_performance_audit.md
```

`scripts/guard_trading_surface.js` also now blocks unapproved
`scripts/build_v1130_*` and `reports/v1130_observation/` paths unless they are
present in the exact exception set.

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
v1130 exact harness self-test: pass
v1130 exact trading self-test: pass
v1130 broad harness self-test: blocked
v1130 broad trading self-test: blocked
v1130 builder broad trading self-test: blocked
config blocked trading self-test: blocked
```

## Recommended Next Task

Proceed with:

```text
Task 141: V11.30 Runtime Performance Audit Implementation
```
