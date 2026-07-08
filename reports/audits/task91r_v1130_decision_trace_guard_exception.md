# Task 91R: V11.30 Decision Trace Guard Exception

## Summary

Added exact guard exceptions for the V11.30 decision trace collector and its two
generated report artifacts.

This task does not allow broad V11.30 report directories, broad builder script
patterns, strategy files, bot config files, dashboard files, SQLite snapshots,
or live/server operations.

## Exact Paths Allowed

- `scripts/build_v1130_decision_trace_report.js`
- `reports/v1130_observation/v1130_decision_trace_report.json`
- `reports/v1130_observation/v1130_decision_trace_report.md`

## Files Modified

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`

## Explicit Non-Allowances

This task did not allow:

- `reports/v1130_observation/**`
- `reports/*v1130*`
- `scripts/build_v1130_*`
- SQLite snapshots
- strategy files
- bot config files
- dashboard files
- deploy files
- live/server operations
- any global bypass

## Validation

Required checks:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Self-tests should confirm:

- the three exact Task 91 paths pass;
- an unapproved V11.30 observation report remains blocked;
- an unapproved V11.30 builder script remains blocked;
- a V11.30 strategy path remains blocked;
- a V11.30 bot config path remains blocked.

## Recommended Next Task

Proceed with:

```text
Task 91: V11.30 Read-Only Decision Trace Collector
```
