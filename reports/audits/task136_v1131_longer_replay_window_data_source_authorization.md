# Task 136: V11.31 Longer Replay Window Data Source Authorization

## Summary

Authorized the next V11.31 longer replay data-source step as a read-only
planning boundary. This task does not download market data, access the server,
run a backtest, modify strategy files, or modify bot config.

Decision:

```text
authorize_read_only_data_source_inventory_before_any_backtest
```

## Source Reviewed

```text
reports/audits/task133_v1131_longer_replay_window_inventory_implementation.md
reports/v1131_observation/v1131_longer_replay_window_inventory.json
reports/v1131_observation/v1131_longer_replay_window_inventory.md
```

## Current Evidence State

| item | state |
|---|---|
| committed `15m` rows per pair | `240` |
| committed `15m` approximate days per pair | `2.5` |
| committed `15m` supports `7d` | `false` |
| committed `15m` supports `14d` | `false` |
| row-level `4h` inventory | `unknown` |
| alpha-screened replay enabled | `23` |
| OHLCV watch-only enabled | `29` |
| backtest reconsideration | `not authorized` |

## Authorized Future Read-Only Questions

The next data-source task may answer only these questions:

- whether a longer `15m` OHLCV window exists for the approved V11.31 pair set;
- whether corresponding `4h` informative data exists and is aligned;
- whether the available window can cover `7d` and `14d`;
- whether the data can support an alpha/taker/protection reconstruction task;
- whether data freshness is sufficient for 2026-07 runtime conditions.

## Explicitly Not Authorized

The next task is not authorized to:

- modify `strategies/**`;
- modify `user_data/**` or bot configs;
- modify `configs/**`, `dashboard/**`, or `deploy/**`;
- read `.env`, `user_data/monitor.env`, API keys, passwords, or tokens;
- start, stop, restart, or deploy a bot;
- run a Freqtrade backtest;
- claim V11.31 is profitable or deployable.

## Proposed Future Exact Paths

If a local report builder is required, it should be reviewed in a separate exact
path task before any guard change:

```text
scripts/build_v1131_longer_replay_data_source_inventory.js
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
```

Do not approve broad patterns such as:

```text
scripts/build_v1131_*
reports/v1131_observation/**
```

## Recommended Next Task

Proceed with:

```text
Task 139: V11.31 Longer Replay Data Source Exact Path Review
```

