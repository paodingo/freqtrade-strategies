# Task 148: V11.31 Longer Replay Data Acquisition Authorization

## Summary

Authorized a future V11.31 longer replay data acquisition task as a bounded
read-only evidence step. This task does not access the server, copy files,
download data, run a backtest, modify strategy files, modify bot config, or
start/stop/restart any bot.

Decision:

```text
authorize_future_read_only_data_acquisition_plan
```

## Sources Reviewed

```text
reports/audits/task147_v1131_longer_replay_data_source_inventory_implementation.md
reports/v1131_observation/v1131_longer_replay_data_source_inventory.json
reports/v1131_observation/v1131_longer_replay_data_source_inventory.md
```

## Current Evidence State

| field | state |
|---|---|
| approved pair set | `observed` |
| `15m` source paths | `observed` |
| `15m` total source rows | `88271` per pair in committed source report |
| committed replay rows | `240` per pair |
| committed replay days | `2.5` |
| committed `7d` support | `false` |
| committed `14d` support | `false` |
| row-level `4h` inventory | `unknown` |
| alpha/taker/protection longer-window state | `unknown` |
| backtest reconsideration | `false` |

## Authorized Future Read-Only Questions

A future data acquisition task may answer only these questions:

- can a bounded longer `15m` window be acquired for exactly the approved V11.31
  pair set;
- can aligned `4h` informative data be acquired for the same window;
- can the acquired window cover `7d` and `14d`;
- can alpha/taker/protection state be reconstructed or must it remain
  `unknown`;
- can an updated replay report reach the sample gate after final filters.

## Explicitly Not Authorized

The future task is not authorized to:

- modify `strategies/**`;
- modify `user_data/**` or bot configs;
- modify `configs/**`, `dashboard/**`, or `deploy/**`;
- read `.env`, `user_data/monitor.env`, API keys, passwords, tokens, or server
  private keys;
- start, stop, restart, or deploy a bot;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- claim V11.31 is profitable, stable, or deployable.

## Acquisition Boundary Draft

Any actual acquisition task must be separately authorized and should remain
read-only. It may propose a bounded source/target plan such as:

```text
source: approved V11.31 15m and 4h OHLCV files for the six-pair set
target: non-secret report-local evidence or generated report artifacts
window: explicit 7d / 14d window
```

No data copy or download is performed by this task.

## Recommended Next Task

Proceed with:

```text
Task 151: V11.31 Longer Replay Data Acquisition Exact Path Review
```

