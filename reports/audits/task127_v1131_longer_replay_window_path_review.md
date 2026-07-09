# Task 127: V11.31 Longer Replay Window Inventory Exact Path Review

## Summary

Reviewed the exact future paths needed for a longer read-only V11.31 replay
window inventory.

Decision:

```text
approve_exact_inventory_paths_only_require_guard_exception_before_implementation
```

This task does not modify guards, does not acquire data, does not run backtests,
and does not touch server runtime.

## Source Plan

| source | path |
|---|---|
| Task 124 plan | `reports/audits/task124_v1131_longer_replay_window_acquisition_plan.md` |
| Task 123 review | `reports/audits/task123_v1131_expanded_replay_result_review.md` |

## Approved Future Paths

Only these exact paths should be considered for the future inventory task:

```text
scripts/build_v1131_longer_replay_window_inventory.js
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

## Required Guard Policy

A future guard task may allow only the exact paths above.

It must not allow:

```text
reports/v1131_observation/**
reports/*v1131*
scripts/build_v1131_*
scripts/*v1131*
```

## Future Task Boundary

The future inventory task may:

- read committed evidence;
- read only explicitly authorized OHLCV snapshot metadata;
- report 7d / 14d availability for `15m` and `4h`;
- report whether `1h` remains excluded;
- report whether alpha/taker/protection evidence is available or unknown.

It must not:

- run a Freqtrade backtest;
- modify strategy code;
- modify bot config;
- start, stop, or restart bots;
- read secrets;
- copy SQLite snapshots into Git;
- treat OHLCV-only candidates as final strategy entries.

## Recommended Next Task

Proceed with:

```text
Task 130: V11.31 Longer Replay Window Inventory Guard Exception
```

Do not implement the inventory builder before the exact guard exception passes
readiness and blocking self-tests.

