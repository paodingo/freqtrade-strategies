# Task 120: V11.31 Backtest Go/No-Go Consolidation

## Summary

Consolidated V11.31 evidence from Tasks 112 through 119.

Current decision:

```text
no_go_for_immediate_backtest_or_deploy
```

V11.31 should continue through replay coverage extension first. It is not ready
for Freqtrade backtest, deployment, live shadow launch, or replacement judgment.

## Evidence Chain

| task | conclusion |
|---|---|
| Task 112 | planned offline replay/backtest route without running backtest |
| Task 113 | strategy/config/test static compatibility passed |
| Task 114 | reviewed exact replay harness paths |
| Task 115 | added exact guard exceptions for first-pass replay harness |
| Task 116 | generated first-pass replay evidence |
| Task 117 | concluded no-go for immediate backtest/deploy |
| Task 118 | recommended replay coverage extension first |
| Task 119 | approved exact future coverage extension paths only |

## Current Metrics

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

## Positive Evidence

- V11.31 local strategy and config exist.
- Unit tests pass.
- Static compatibility checks passed.
- First-pass replay has positive fee-adjusted `4_candle` and `8_candle`
  proxy returns.
- Pair concentration is not dominated by a single pair.

## Backtest Blockers

Backtest is still blocked because:

- enabled sample count is `23`, below the `30` initial gate;
- first-pass replay is not lifecycle replay;
- no exit distribution has been measured;
- no drawdown path has been measured;
- no fill, slippage, fee-quality, funding, latency, wallet, or protection model
  exists;
- stale `1h` remains unresolved if a future design wants `1h` filters;
- there is no same-window comparison against V11.30 live/dry-run trade outcomes.

## Go/No-Go Decision

| action | decision |
|---|---|
| immediate Freqtrade backtest | `no_go` |
| immediate deploy/live shadow | `no_go` |
| modify V11.31 strategy | `no_go` |
| modify bot config | `no_go` |
| expand replay coverage | `go` |
| exact guard exception for coverage extension | `go` |

## Required Before Reconsidering Backtest

Reconsider backtest only after:

- expanded replay reaches at least `30` enabled samples, or explains why it
  cannot;
- fee-adjusted `4_candle` / `8_candle` evidence remains positive;
- concentration remains acceptable;
- blocked-signal categories are reported;
- limitations remain explicit and do not become deployment claims.

## Explicit Non-Conclusion

This task does not conclude:

- V11.31 is profitable;
- V11.31 is bad;
- V11.31 can replace V10.8.2;
- V11.31 can replace V11.30;
- any bot should be started, stopped, or restarted.

## Recommended Next Tasks

Proceed in this order:

```text
Task 121: V11.31 Replay Coverage Extension Guard Exception
Task 122: V11.31 Replay Coverage Extension Implementation
Task 123: V11.31 Expanded Replay Result Review / Backtest Reconsideration
```

Do not run a Freqtrade backtest until Task 123 explicitly says the evidence is
ready enough to create a backtest task.

