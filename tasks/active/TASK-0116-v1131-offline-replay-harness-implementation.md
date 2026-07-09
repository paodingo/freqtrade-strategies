# TASK-0116: V11.31 Offline Replay Harness Implementation

## Status

Completed.

## Goal

Implement and run a read-only V11.31 offline replay harness.

## Allowed Files

- `scripts/build_v1131_loose_range_replay_report.js`
- `reports/v1131_observation/v1131_loose_range_replay_report.json`
- `reports/v1131_observation/v1131_loose_range_replay_report.md`
- `reports/audits/task116_v1131_offline_replay_harness_implementation.md`
- `tasks/active/TASK-0116-v1131-offline-replay-harness-implementation.md`

## Result

Generated replay-planning output.

Key result:

```text
enabled = 23
sample_status = thin
fee_adjusted_4_candle_mean_bps = 10.15
fee_adjusted_8_candle_mean_bps = 24.13
```

## Boundaries

This task did not:

- run backtests;
- deploy or restart bots;
- modify strategy/config files;
- refresh data;
- read secrets;
- claim replacement readiness.

Recommended next task:

```text
Task 117: V11.31 Replay Result Review / Backtest Go-No-Go
```

