# Task 139: V11.31 Longer Replay Data Source Exact Path Review

## Summary

Reviewed the future exact path surface proposed by Task 136 for a read-only
V11.31 longer replay data-source inventory.

Decision:

```text
approve_exact_paths_only_for_future_guard_exception
```

This task does not implement the data-source inventory, does not access the
server, does not download market data, and does not run a backtest.

## Source Reviewed

```text
reports/audits/task136_v1131_longer_replay_window_data_source_authorization.md
```

## Approved Future Exact Paths

Only these exact paths should be considered for a later guard exception task:

```text
scripts/build_v1131_longer_replay_data_source_inventory.js
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
```

## Explicitly Not Approved

Do not approve broad patterns such as:

```text
scripts/build_v1131_*
reports/v1131_observation/**
reports/**/*v1131*
```

Do not approve changes under:

```text
strategies/**
user_data/**
configs/**
dashboard/**
deploy/**
```

## Required Future Guard Rules

A future guard exception must:

- allow only the three exact paths listed above;
- avoid broad directory or wildcard rules;
- keep strategy/config/dashboard/deploy surfaces blocked;
- keep secrets blocked;
- keep bot lifecycle operations forbidden;
- keep backtests forbidden until a separate task authorizes them.

## Recommended Next Task

Proceed with:

```text
Task 144: V11.31 Longer Replay Data Source Guard Exception
```

