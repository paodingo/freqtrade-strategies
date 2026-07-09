# TASK-0144: V11.31 Longer Replay Data Source Guard Exception

## Status

Completed.

## Objective

Allow only the exact future V11.31 longer replay data-source inventory harness
paths reviewed by Task 139.

## Exact Paths

```text
scripts/build_v1131_longer_replay_data_source_inventory.js
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
```

## Not Allowed

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Next Task

```text
Task 147: V11.31 Longer Replay Data Source Inventory Implementation
```

