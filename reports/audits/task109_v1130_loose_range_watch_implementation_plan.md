# Task 109: V11.30 Loose-Range Watch Implementation Plan

## Summary

Defined a safe implementation plan for the `v1130_loose_range_watch` candidate
selected by Task 108.

Conclusion:

```text
loose_range_watch_requires_plan_and_guards_before_strategy_implementation
```

This task is a plan only. It does not create a strategy file, does not modify
V11.30, does not modify bot config, does not run a backtest, and does not touch
server/runtime state.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `7213a9d` |
| starting status | clean |
| readiness before plan | passed |
| source decision | Task 108 selected `v1130_loose_range_watch` as planning target |

## Candidate Definition

Candidate:

```text
v1130_loose_range_watch
```

Observed first-pass evidence:

| field | value |
|---|---:|
| samples | `23` |
| 4-candle mean | `20.15 bps` |
| 8-candle mean | `34.13 bps` |
| positive rate | `0.7391` |
| pair count | `6` |
| pair concentration | `0.2609` |
| sample status | `thin` |

Interpretation:

```text
Promising planning target, not execution proof.
```

## Implementation Hypothesis

The loose-range watch candidate should test whether a less restrictive
crash/rebound gate can capture rebound continuation across multiple pairs
without overfitting the current BCH-only V11.30 live sample.

Initial implementation should preserve these constraints:

- dry-run/shadow only;
- no live-money assumptions;
- no `1h` dependency until `1h` OHLCV is refreshed;
- no manual intervention in current V11.30 positions;
- no replacement conclusion.

## Proposed Strategy Surface For Future Task

A future implementation task may propose a new strategy file, but this task does
not authorize it. Candidate path for future review:

```text
strategies/RegimeAwareV1131LooseRangeWatchShadow.py
```

Possible future config path for a separate dry-run shadow task:

```text
user_data/config_multi_futures_v1131_loose_range_watch_shadow.json
```

These paths remain blocked until an exact guard/implementation task approves
them.

## Entry Hypothesis

Future implementation should start from the existing loose-range watch replay
logic:

- `15m` candle return threshold around the loose watch range;
- range expansion check;
- RSI bounded rebound zone;
- volume ratio floor;
- `4h` context only if already available;
- no stale `1h` features;
- alpha/taker blockers represented explicitly as observed/missing/unknown.

The implementation must not silently convert missing alpha or taker data into
`false`.

## Exit Hypothesis

Exit design must be planned before any strategy code is written because the
current V11.30 early live concern is exit quality.

Future review should compare:

- fixed time exit;
- rebound exhaustion exit;
- trailing protective exit;
- hard stop for failed rebound;
- no-tune baseline matching current V11.30 exit behavior.

No exit parameter should be changed in current V11.30 from this plan.

## Required Validation Before Strategy Code

Before writing any strategy file, run or create a separate task for:

1. exact strategy/config path allowlist review;
2. offline replay with candidate lifecycle assumptions;
3. drawdown and adverse excursion summary;
4. pair concentration check;
5. minimum sample gate;
6. comparison against current V11.30 crash-rebound baseline;
7. check whether `1h` data refresh is needed or intentionally excluded.

## Data Decision

Do not block the first loose-range implementation plan on `1h` data because the
selected candidate is explicitly a `15m + 4h` first-pass target.

However, if Task 110 or later wants multi-timeframe `1h` filters, run:

```text
Task 103R: Refresh V11.30 1h Futures OHLCV Data
```

before using those features.

## Future Task Options

Recommended next sequence:

1. `Task 110: V11.31 Loose-Range Watch Strategy Guard Review`
2. `Task 111: V11.31 Loose-Range Watch Strategy Implementation`
3. `Task 112: V11.31 Offline Replay / Backtest Plan`
4. `Task 103R`: only if `1h` features are needed

## Stop Conditions

Stop before implementation if:

- current worktree is dirty;
- readiness fails;
- strategy/config paths are not explicitly authorized;
- implementation requires stale `1h` data;
- the task needs secrets;
- the task needs bot restart/deploy;
- the task attempts to tune current V11.30 while open trade evidence is
  unresolved;
- the task attempts to claim replacement readiness.

## Safety Boundary

This task did not:

- write strategy code;
- modify current V11.30;
- modify bot configs;
- modify dashboard or deploy files;
- run backtests;
- refresh or download data;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- force-close V11.30 trades;
- produce a V11.30 replacement conclusion.

