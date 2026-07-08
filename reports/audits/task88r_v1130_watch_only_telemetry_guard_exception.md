# Task 88R: V11.30 Watch-Only Telemetry Guard Exception

## Summary

Added exact guard exceptions for the future V11.30 watch-only telemetry report.

This task only expands the harness allowlist for three explicit paths. It does
not allow broad V11.30 report directories, broad script patterns, strategy code,
bot config, dashboard code, SQLite snapshots, server operations, or order-capable
behavior.

## Exact Paths Allowed

- `scripts/build_v1130_watch_only_telemetry_report.js`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.md`

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

## Validation Plan

Run:

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

Self-tests should confirm:

- the three exact Task 88 paths pass;
- an unapproved V11.30 observation report remains blocked;
- an unapproved V11.30 builder script remains blocked;
- a V11.30 strategy path remains blocked;
- a V11.30 bot config path remains blocked.

## Non-Actions

This task did not:

- implement the telemetry builder;
- generate telemetry reports;
- modify live strategy behavior;
- modify bot configuration;
- read secrets;
- start, stop, or restart bots;
- run backtests;
- log in to the server.

## Recommended Next Task

Proceed with:

```text
Task 88: Implement V11.30 watch-only telemetry report
```
