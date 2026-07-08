# Task 86R: Allow V11.30 Loose-Range Replay Exact Paths

## Summary

Added exact guard exceptions for the V11.30 loose-range replay report builder
and its generated JSON/Markdown outputs.

Allowed exact paths:

- `scripts/build_v1130_loose_range_replay_report.js`
- `reports/v1130_observation/v1130_loose_range_replay_report.json`
- `reports/v1130_observation/v1130_loose_range_replay_report.md`

## Guard Files Changed

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`

## Explicit Non-Allowances

This task did not allow:

- `reports/v1130_observation/**`;
- `scripts/build_v1130_*`;
- SQLite snapshots;
- strategy/config/dashboard changes;
- live/server operations.

## Non-Actions

This task did not:

- modify strategies;
- modify bot configs;
- start, stop, or restart bots;
- read secrets;
- run backtests.

## Recommended Next Task

Proceed with:

```text
Task 86: V11.30 loose-range replay report builder
```
