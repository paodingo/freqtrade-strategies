# Task 112: V11.31 Offline Replay / Backtest Plan

## Summary

Planned the offline validation path for the local V11.31 loose-range watch
shadow strategy implemented in Task 111.

Conclusion:

```text
v1131_requires_offline_replay_before_backtest_or_deploy
```

This task is a plan only. It does not run a backtest, does not run replay, does
not modify strategy behavior, does not modify bot config, and does not touch
server/runtime state.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `e6d24c6` |
| starting status | clean |
| readiness before plan | passed |
| source implementation | Task 111 |

## Validation Order

Recommended order:

1. Local import/static compatibility check.
2. Read-only offline replay harness using existing report/candle evidence.
3. If replay passes sample and risk gates, design a backtest task.
4. If backtest passes, create a server preflight task.
5. Only after server preflight, consider dry-run shadow deployment.

Do not skip directly to deployment.

## Replay Scope

First replay should be:

```text
V11.31 loose-range watch, 15m + 4h only
```

It must not use stale `1h` OHLCV. Task 103 found exact `1h` futures OHLCV was
stale at `2026-07-03T08:00:00Z`.

## Required Replay Metrics

Replay output must include:

- candidate count;
- enabled count after alpha/taker blockers;
- blocked count by reason;
- pair participation;
- pair concentration;
- 1 / 4 / 8 / 16 candle forward returns;
- fee-adjusted returns;
- MFE / MAE;
- sample sufficiency;
- data coverage by pair/timeframe;
- explicit `1h_excluded_stale` flag.

## Backtest Preconditions

A backtest task should not start until replay proves:

- sample count is not trivially small;
- pair concentration is acceptable;
- fee-adjusted returns are not only from one pair or one candle;
- the replay can be reproduced from committed code and declared data;
- stale `1h` is either refreshed separately or not used.

## Backtest Scope If Approved Later

Future backtest should be an explicit separate task and should define:

- exact strategy: `RegimeAwareV1131LooseRangeWatchShadow`;
- exact config: `user_data/config_multi_futures_v1131_loose_range_watch_shadow.json`;
- exact timerange;
- exact pairs;
- exact fee model;
- output paths;
- guard exceptions if new output paths are needed;
- no live/server operations.

## Stop Conditions

Stop before replay/backtest if:

- worktree is dirty;
- readiness fails;
- replay requires stale `1h`;
- replay requires secrets;
- output paths are not explicitly authorized;
- strategy/config changes are requested during validation;
- server deploy or bot restart is requested in the same task;
- the task attempts to claim V11.31 replacement readiness.

## Safety Boundary

This task did not:

- run replay;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- refresh or download data;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- force-close trades;
- produce a replacement conclusion.

## Recommended Next Task

Proceed with:

```text
Task 113: V11.31 Local Strategy Import / Static Compatibility Check
```

Then proceed with:

```text
Task 114: V11.31 Offline Replay Harness Exact Path Review
```

