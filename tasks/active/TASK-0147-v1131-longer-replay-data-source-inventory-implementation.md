# TASK-0147: V11.31 Longer Replay Data Source Inventory Implementation

## Status

Completed.

## Objective

Generate a read-only V11.31 longer replay data-source inventory from committed
evidence.

## Allowed Files

```text
scripts/build_v1131_longer_replay_data_source_inventory.js
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
reports/audits/task147_v1131_longer_replay_data_source_inventory_implementation.md
tasks/active/TASK-0147-v1131-longer-replay-data-source-inventory-implementation.md
```

## Result

Committed evidence is not enough to authorize a backtest. The data-source
inventory shows observed `15m` paths, but committed replay coverage is still
about `2.5` days per pair and row-level `4h` inventory remains `unknown`.

## Next Task

```text
Task 148: V11.31 Longer Replay Data Acquisition Authorization
```

