# Task 76R: Allow V11.30 Gate Telemetry Exact Paths

## Summary

Added exact guard exceptions for the V11.30 gate telemetry report builder and
its two generated output files.

This task does not allow broad V11.30 report, script, strategy, config,
dashboard, SQLite, or server surfaces.

## Exact Paths Allowed

The following exact paths were allowed:

- `scripts/build_v1130_gate_telemetry_report.js`
- `reports/v1130_observation/v1130_gate_telemetry_report.json`
- `reports/v1130_observation/v1130_gate_telemetry_report.md`

## Guard Files Changed

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`

## Explicit Non-Allowances

This task did not allow:

- `reports/v1130_observation/**`
- `scripts/build_v1130_*`
- `reports/*v1130*`
- SQLite snapshots;
- strategy files beyond previously approved exact V11.30 strategy path;
- bot configs beyond previously approved exact V11.30 config path;
- dashboard broad changes;
- server/live operations.

## Validation Plan

Run:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Self-test expected behavior:

- the 3 exact Task 76 paths pass;
- `reports/v1130_observation/v1130_real_execution_report.json` remains blocked
  by `guard_harness_diff.js`;
- `scripts/build_v1130_unapproved.js` remains blocked by
  `guard_harness_diff.js`.

## Non-Actions

This task did not:

- modify strategies;
- modify bot configs;
- read secrets;
- start, stop, or restart bots;
- run backtests;
- access live/server state.

## Recommended Next Task

Proceed with:

```text
Task 76: V11.30 Gate Telemetry Report Builder
```
