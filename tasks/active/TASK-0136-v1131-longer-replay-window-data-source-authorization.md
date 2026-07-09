# TASK-0136: V11.31 Longer Replay Window Data Source Authorization

## Status

Completed.

## Objective

Authorize only the next read-only V11.31 longer replay data-source inventory
boundary, without implementing data download, server access, backtest, strategy
changes, or bot config changes.

## Result

The next task may inventory longer `15m` and aligned `4h` data availability, but
may not run a backtest or claim deploy readiness.

## Proposed Future Exact Paths

```text
scripts/build_v1131_longer_replay_data_source_inventory.js
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
```

## Next Task

```text
Task 139: V11.31 Longer Replay Data Source Exact Path Review
```

