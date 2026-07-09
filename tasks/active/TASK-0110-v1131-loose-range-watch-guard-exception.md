# TASK-0110: V11.31 Loose-Range Watch Strategy Guard Review

## Status

Completed.

## Goal

Add exact guard exceptions for the future V11.31 loose-range watch shadow
strategy, config, and test paths.

## Allowed Files

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task110_v1131_loose_range_watch_guard_exception.md`
- `tasks/active/TASK-0110-v1131-loose-range-watch-guard-exception.md`

## Exact Allowance

```text
strategies/RegimeAwareV1131LooseRangeWatchShadow.py
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
tests/test_regime_aware_v1131_loose_range_watch_shadow.py
```

## Boundaries

This task did not:

- allow broad `strategies/**`;
- allow broad `user_data/**`;
- allow broad `tests/**`;
- implement strategy behavior;
- run backtests;
- deploy or restart bots;
- read secrets.

Recommended next task:

```text
Task 111: V11.31 Loose-Range Watch Strategy Implementation
```

