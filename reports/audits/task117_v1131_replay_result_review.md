# Task 117: V11.31 Replay Result Review / Backtest Go-No-Go

## Summary

Reviewed the V11.31 offline replay result from Task 116 and made a backtest
go/no-go decision.

Conclusion:

```text
no_go_for_immediate_backtest_deploy_expand_replay_first
```

The V11.31 replay is promising but too thin for a direct backtest/deploy path.
The correct next move is to expand replay coverage or fix the stale `1h` data
decision before committing more expensive validation.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `3f1b7ed` |
| starting status | clean |
| readiness before review | passed |
| source report | `reports/v1131_observation/v1131_loose_range_replay_report.json` |

## Evidence Reviewed

| field | value |
|---|---:|
| candidates | `29` |
| enabled | `23` |
| blocked | `6` |
| max pair share | `0.2609` |
| sample gate | `30` |
| sample status | `thin` |
| 4-candle fee-adjusted mean | `10.15 bps` |
| 8-candle fee-adjusted mean | `24.13 bps` |
| 1h status | `excluded_stale` |

## Decision

Backtest decision:

```text
no_go_for_immediate_backtest
```

Reason:

- enabled sample count is `23`, below the initial `30` sample gate;
- replay is close-to-close proxy evidence, not strategy lifecycle evidence;
- no fill/slippage/funding/latency model exists;
- no exit distribution has been proven;
- `1h` is still excluded due to stale OHLCV.

## Positive Signals

The candidate remains worth pursuing because:

- fee-adjusted `4_candle` and `8_candle` mean returns are positive;
- pair concentration is not single-pair dominated;
- the strategy is locally implemented and statically compatible;
- the replay harness is reproducible from committed evidence.

## Blocking Gaps

Blocking gaps before backtest:

- sample count below gate;
- no lifecycle exit replay;
- no drawdown calculation;
- no order/fill model;
- stale `1h` data remains unresolved if future filters need it;
- no same-window comparison against current V11.30 dry-run trade outcomes.

## Recommended Next Task

Proceed with:

```text
Task 118: V11.31 Replay Coverage Extension Plan
```

Task 118 should decide whether to:

1. extend V11.31 replay over a wider committed OHLCV/report window; or
2. run `Task 103R` to refresh exact `1h` futures OHLCV first; or
3. wait for V11.30/V11.31 live-observation evidence before spending on backtest.

## Explicit Non-Decisions

This task does not decide:

- V11.31 is good enough to deploy;
- V11.31 is bad enough to abandon;
- V11.31 can replace V10.8.2;
- current V11.30 should be stopped or modified;
- live/server operations should happen.

## Safety Boundary

This task did not:

- run backtests;
- deploy V11.31;
- start, stop, or restart bots;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- refresh or download data;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- force-close trades;
- produce a replacement conclusion.

