# Task 108: Candidate Search First-Pass Review And Implementation Target Decision

## Summary

Reviewed the Task 107 candidate-search first-pass output and selected the next
planning target.

Conclusion:

```text
review_v1130_loose_range_watch_first_but_do_not_implement_strategy_yet
```

Task 107 ranks `v1130_loose_range_watch` first, but the result is still a
planning signal. It is not a backtest, not a live execution report, and not
enough to modify strategy behavior or bot config.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `7213a9d` |
| starting status | clean |
| readiness before review | passed |
| source output | `reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json` |

## First-Pass Ranking

| rank | candidate | score | samples | net bps | positive rate | data status |
|---:|---|---:|---:|---:|---:|---|
| 1 | `v1130_loose_range_watch` | `51.64` | `23` | `20.15` | `0.7391` | `ready_15m_4h_1h_excluded_stale` |
| 2 | `crash_rebound_continuation` | `49.45` | `15` | `21.5559` | `0.6667` | `ready_15m_4h_1h_excluded_stale` |
| 3 | `ranging_short_volatility_fade` | `47.94` | `1214` | `7.3426` | `0.5817` | `historical_only_latest_window_not_included` |
| 4 | `blowoff_short_fade` | `32.71` | `1075` | `-18.653` | `0.4009` | `ready_15m_4h_1h_excluded_stale` |
| 5 | `selloff_continuation_short` | `29.46` | `122` | `-19.9735` | `0.3361` | `ready_15m_4h_1h_excluded_stale` |

## Decision

Proceed with a planning task for:

```text
v1130_loose_range_watch
```

Rationale:

- It ranks first in the first-pass matrix.
- It has better pair dispersion than the live BCH-only V11.30 trade sample.
- It uses the already-ready `15m + 4h` evidence lane and does not require stale
  `1h` data.
- It remains close enough to V11.30 to reuse observation and telemetry concepts.

## Why Not Implement Immediately

Implementation is not authorized yet because:

- sample size is thin: `23` replay samples;
- Task 107 is not a backtest;
- profit factor and max drawdown are `unknown`;
- exit reason distribution is `missing`;
- live execution quality for V11.30 remains insufficient;
- current V11.30 BCH trade outcome is still outside this review;
- no strategy path allowlist has been approved for a new implementation.

## Candidate-Specific Risks

| risk | status | impact |
|---|---|---|
| thin sample | observed | high risk of overfitting |
| no backtest | observed | cannot estimate drawdown, trade lifecycle, or exit distribution |
| no `1h` features | intentional | first pass excludes stale data; implementation should avoid `1h` dependency |
| V11.30 live sample weak | observed | do not tune current V11.30 from this report alone |
| strategy/config changes unauthorized | observed | implementation requires separate exact task |

## Rejected Immediate Actions

Do not do these from Task 108:

- modify `strategies/**`;
- modify `user_data/**` bot configs;
- deploy or restart bots;
- run a backtest under this task;
- refresh data under this task;
- force-close V11.30 BCH trade;
- claim V11.30 can replace V10.8.2;
- claim `v1130_loose_range_watch` is profitable in live execution.

## Recommended Next Task

Proceed with:

```text
Task 109: V11.30 Loose-Range Watch Implementation Plan
```

Task 109 should remain a plan only and should define:

- candidate behavior;
- entry/exit hypotheses;
- required data;
- future exact file paths if implementation is later approved;
- validation gates before strategy code can be touched.

## Safety Boundary

This task did not:

- write code;
- run backtests;
- refresh or download market data;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart bots;
- force-close V11.30 trades;
- produce a V11.30 replacement conclusion.

