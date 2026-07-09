# TASK-0115: V11.31 Offline Replay Harness Guard Exception

## Status

Completed.

## Goal

Add exact guard exceptions for the V11.31 offline replay harness script and
outputs.

## Allowed Files

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task115_v1131_offline_replay_harness_guard_exception.md`
- `tasks/active/TASK-0115-v1131-offline-replay-harness-guard-exception.md`

## Exact Allowance

```text
scripts/build_v1131_loose_range_replay_report.js
reports/v1131_observation/v1131_loose_range_replay_report.json
reports/v1131_observation/v1131_loose_range_replay_report.md
```

## Boundaries

This task did not:

- allow `scripts/build_v1131_*`;
- allow `reports/v1131_observation/**`;
- write replay code;
- run replay/backtests;
- modify strategies/configs;
- deploy or restart bots;
- read secrets.

Recommended next task:

```text
Task 116: V11.31 Offline Replay Harness Implementation
```

