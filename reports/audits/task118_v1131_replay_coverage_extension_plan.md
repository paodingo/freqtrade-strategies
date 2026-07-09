# Task 118: V11.31 Replay Coverage Extension Plan

## Summary

Task 117 concluded that `RegimeAwareV1131LooseRangeWatchShadow` is promising
but too thin for immediate backtest or deploy.

Current decision:

```text
expand_replay_coverage_before_backtest
```

The preferred next step is to extend replay coverage using committed/read-only
evidence first. Do not run backtests, do not deploy V11.31, do not restart bots,
and do not refresh `1h` futures data unless a later task explicitly needs `1h`
features again.

## Source Evidence

| source | path |
|---|---|
| replay report | `reports/v1131_observation/v1131_loose_range_replay_report.json` |
| replay markdown | `reports/v1131_observation/v1131_loose_range_replay_report.md` |
| Task 117 review | `reports/audits/task117_v1131_replay_result_review.md` |

## Current Replay State

| metric | value |
|---|---:|
| candidates | `29` |
| enabled | `23` |
| blocked | `6` |
| sample gate | `30` |
| sample status | `thin` |
| max pair share | `0.2609` |
| fee-adjusted 4-candle mean | `10.15 bps` |
| fee-adjusted 8-candle mean | `24.13 bps` |
| `1h` status | `excluded_stale` |

## Decision

Proceed with a replay coverage extension before any backtest decision.

Rationale:

- enabled samples are below the initial `30` sample gate;
- current replay is close-to-close proxy evidence, not lifecycle evidence;
- no fill, slippage, funding, latency, wallet, or order-book execution quality
  model exists;
- no exit distribution or drawdown path has been measured;
- positive `4_candle` and `8_candle` proxy returns justify more read-only
  evidence gathering, not immediate deployment.

## Recommended Coverage Extension

The next implementation task should build a read-only coverage extension that:

- reuses committed OHLCV/report evidence only;
- keeps V11.31 strategy/config unchanged;
- expands the candidate sample beyond the current `23` enabled samples if
  existing committed evidence permits;
- preserves the same V11.31 loose-range entry thresholds;
- reports per-pair, per-day, and per-horizon concentration;
- calculates fee-adjusted proxy returns for `1`, `4`, `8`, and `16` candles;
- explicitly reports whether the expanded enabled sample count reaches `30`;
- still labels evidence as replay/proxy evidence, not a Freqtrade backtest.

## Proposed Future Exact Paths

Future implementation should use only these exact paths:

```text
scripts/build_v1131_loose_range_replay_coverage_extension.js
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json
reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md
```

No broad allowlist should be added for `reports/v1131_observation/**`,
`reports/*v1131*`, or `scripts/build_v1131_*`.

## What Not To Do Yet

Do not:

- run a Freqtrade backtest;
- deploy V11.31;
- start, stop, or restart any bot;
- modify strategies;
- modify bot configs;
- refresh market data;
- use stale `1h` data;
- read secrets;
- claim V11.31 can replace V10.8.2 or V11.30.

## Task 103R Decision

Do not run `Task 103R` immediately.

Reason: V11.31 currently excludes `1h`; a `1h` refresh becomes useful only if a
future design reintroduces `1h` filters or if replay coverage cannot be expanded
from existing committed `15m` / `4h` evidence.

## Recommended Next Task

Proceed with:

```text
Task 119: V11.31 Replay Coverage Extension Exact Path Review
```

Then proceed to a narrow guard exception task before implementing the replay
coverage extension.

