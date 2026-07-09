# Task 123: V11.31 Expanded Replay Result Review / Backtest Reconsideration

## Summary

Reviewed the Task 122 coverage extension output and reconsidered whether V11.31
is ready for a Freqtrade backtest.

Decision:

```text
no_go_for_backtest_continue_evidence_or_choose_next_candidate
```

The extension improved visibility but did not clear the backtest gate.

## Source Reviewed

| source | path |
|---|---|
| coverage extension JSON | `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json` |
| coverage extension Markdown | `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.md` |
| Task 122 report | `reports/audits/task122_v1131_replay_coverage_extension_implementation.md` |

## Key Findings

| layer | enabled | status | interpretation |
|---|---:|---|---|
| alpha-screened replay | `23` | `thin` | best available proxy, still below `30` |
| OHLCV watch-only layer | `29` | `thin` | wider but alpha/taker/protection unknown |
| strict crash-rebound reference | `9` | `thin` | reference only |
| sensitivity combined-looser | `34` | `sufficient_initial` | not exact V11.31 thresholds; not authorized for strategy change |

Return evidence remains positive in the alpha-screened layer:

| metric | value |
|---|---:|
| fee-adjusted 4-candle mean | `10.15 bps` |
| fee-adjusted 8-candle mean | `24.13 bps` |

However, this is still proxy evidence and not lifecycle execution evidence.

## Backtest Reconsideration

Backtest decision:

```text
no_go
```

Reason:

- alpha-screened enabled samples remain `23`, below the `30` initial gate;
- OHLCV-only watch samples reach only `29` and do not prove final strategy
  entries;
- alpha/taker/protection decisions remain unknown for the wider layer;
- no exit lifecycle replay exists;
- no fill/slippage/funding/latency model exists;
- no drawdown path exists;
- no same-window live trade quality comparison exists.

## What This Means

V11.31 remains a plausible research candidate, but it is not strong enough to
spend compute/risk on Freqtrade backtest or deployment yet.

The next high-value move is either:

1. gather a longer committed/read-only 15m/4h replay window for exact V11.31
   thresholds; or
2. pivot to the next candidate family while keeping V11.31 parked; or
3. wait for V11.30 live evidence if the active bot is still the operational
   priority.

## Explicit Non-Conclusion

This task does not conclude:

- V11.31 is profitable;
- V11.31 is bad;
- V11.31 can replace V10.8.2;
- V11.31 can replace V11.30;
- V11.31 should be deployed;
- V11.31 should be backtested immediately.

## Safety Boundary

This task did not:

- run backtests;
- deploy V11.31;
- start, stop, or restart bots;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read secrets;
- access server state;
- write SQLite.

## Recommended Next Tasks

Proceed with one of these, depending on priority:

```text
Task 124: Longer Read-Only V11.31 Replay Window Acquisition Plan
Task 125: Next Candidate Family Selection Review
Task 126: V11.30 Live Evidence Refresh And Candidate Priority Rebalance
```

Do not run a Freqtrade backtest until a later task explicitly clears the sample
and lifecycle evidence gates.

