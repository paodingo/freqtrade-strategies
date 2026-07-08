# TASK-0088R: V11.30 Watch-Only Telemetry Guard Exception

## Status

Completed.

## Objective

Allow only the exact Task 88 V11.30 watch-only telemetry paths through the
harness and trading-surface guards.

## Allowed Changes

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task88r_v1130_watch_only_telemetry_guard_exception.md`
- `tasks/active/TASK-0088R-v1130-watch-only-telemetry-guard-exception.md`

## Exact Task 88 Paths

- `scripts/build_v1130_watch_only_telemetry_report.js`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.md`

## Boundaries

- No broad `reports/v1130_observation/**` allowance.
- No broad `scripts/build_v1130_*` allowance.
- No strategy changes.
- No bot config changes.
- No dashboard changes.
- No SQLite snapshot allowance.
- No server or live bot operations.
- No secrets.

## Next

Run Task 88 to implement and generate the watch-only telemetry report.
