# TASK-0133: V11.31 Longer Replay Window Inventory Implementation

## Status

Completed.

## Objective

Implement a read-only generator that inventories currently committed V11.31
longer replay window evidence.

## Allowed Files

```text
scripts/build_v1131_longer_replay_window_inventory.js
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
reports/audits/task133_v1131_longer_replay_window_inventory_implementation.md
tasks/active/TASK-0133-v1131-longer-replay-window-inventory-implementation.md
```

## Boundaries

- No strategy changes.
- No bot config changes.
- No dashboard or deploy changes.
- No secret reads.
- No server access.
- No bot start/stop/restart.
- No backtest.

## Result

The committed evidence covers about `2.5` days of `15m` watch data, not `7d` or
`14d`. Row-level `4h` inventory remains `unknown`. The task does not authorize a
backtest or deployment.

## Next Task

```text
Task 136: V11.31 Longer Replay Window Data Source Authorization
```

