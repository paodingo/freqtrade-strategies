# Task 114: V11.31 Offline Replay Harness Exact Path Review

## Summary

Reviewed the exact future path surface for a V11.31 offline replay harness.

Conclusion:

```text
v1131_replay_harness_requires_exact_guard_exception_before_implementation
```

This task is a path review only. It does not modify guards, write replay code,
run replay, run backtests, or touch server/runtime state.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `e6d24c6` |
| starting status | clean |
| readiness before review | passed |
| source plan | Task 112 |
| static check | Task 113 passed |

## Future Paths Recommended For Guard Review

Approve only as candidates for a future guard-exception task:

```text
scripts/build_v1131_loose_range_replay_report.js
reports/v1131_observation/v1131_loose_range_replay_report.json
reports/v1131_observation/v1131_loose_range_replay_report.md
```

The future task should not allow:

- `scripts/build_v1131_*`;
- `reports/v1131_observation/**`;
- `reports/**`;
- `strategies/**`;
- `user_data/**`;
- `configs/**`;
- `dashboard/**`;
- `deploy/**`.

## Replay Requirements

The future replay harness must:

- read existing OHLCV/report evidence only;
- use `15m + 4h` only unless a separate `1h` refresh task completes;
- output data coverage by pair/timeframe;
- output candidate/enabled/blocked rows;
- output forward returns for 1 / 4 / 8 / 16 candles;
- output fee-adjusted returns;
- output pair concentration;
- output explicit sample sufficiency;
- label `1h` as `excluded_stale`;
- avoid replacement conclusions.

## Required Future Guard Task

Proceed with:

```text
Task 115: V11.31 Offline Replay Harness Guard Exception
```

Task 115 should add exact exceptions for only:

```text
scripts/build_v1131_loose_range_replay_report.js
reports/v1131_observation/v1131_loose_range_replay_report.json
reports/v1131_observation/v1131_loose_range_replay_report.md
```

It should not write the replay implementation unless explicitly combined with
an implementation task.

## Stop Conditions

Stop before implementation if:

- readiness fails;
- worktree is dirty;
- stale `1h` would be used;
- output paths are not exact-authorized;
- server access is required;
- secrets are required;
- backtest or deployment is requested in the same task;
- strategy/config changes are requested.

## Safety Boundary

This task did not:

- modify guard scripts;
- write replay code;
- generate replay outputs;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- refresh or download data;
- read secrets;
- start, stop, or restart bots;
- produce a replacement conclusion.

