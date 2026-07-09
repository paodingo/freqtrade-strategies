# Task 125: Next Candidate Family Selection Review

## Summary

Reviewed the candidate families after V11.31 failed to clear the expanded
replay backtest gate.

Decision:

```text
park_v1131_keep_v1130_live_observation_prioritize_ranging_short_research_next
```

V11.31 remains plausible but not backtest-ready. V11.30 has live execution
evidence but needs quality refresh. The next research family to prepare is
`ranging_short_volatility_fade`, because it has the largest historical sample,
while keeping its alpha-state and execution gaps explicit.

## Source Evidence

| source | path |
|---|---|
| Task 123 V11.31 review | `reports/audits/task123_v1131_expanded_replay_result_review.md` |
| candidate search summary | `reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json` |
| V11.31 coverage extension | `reports/v1131_observation/v1131_loose_range_replay_coverage_extension.json` |

## Candidate Ranking Review

| rank | candidate | sample | edge | limitation | action |
|---:|---|---:|---:|---|---|
| 1 | `v1130_loose_range_watch` / V11.31 | `23` alpha-screened | positive 4/8 candle proxy | below sample gate | park, gather longer window |
| 2 | `crash_rebound_continuation` / V11.30 | `15` replay, live-capable | positive proxy | early live quality weak | keep observing live |
| 3 | `ranging_short_volatility_fade` | `1214` historical OHLCV-derived | positive mean `7.3426 bps` | alpha missing, not execution proof | prepare next research review |
| 4 | `blowoff_short_fade` | `1075` | negative | negative fee-adjusted mean | keep as control/risk family |
| 5 | `selloff_continuation_short` | `122` | negative | negative fee-adjusted mean | deprioritize |

## Selection

Next research target:

```text
ranging_short_volatility_fade
```

Reason:

- it has a large historical OHLCV-derived sample;
- it is a different family from the current long-only crash/rebound variants;
- it may diversify behavior if V11.30/V11.31 long rebound logic remains weak;
- it should be reviewed before writing any new strategy code.

## Required Caution

The `ranging_short_volatility_fade` evidence is not enough to implement or
deploy a strategy directly because:

- alpha state is missing;
- pair concentration is unknown;
- exit distribution is missing;
- max drawdown is unknown;
- fill/slippage/funding/latency are unknown;
- it is not a Freqtrade backtest;
- it is not live execution evidence.

## Recommended Next Task

Proceed with:

```text
Task 128: Ranging Short Candidate Evidence Deep Review
```

Task 128 should remain read-only and should not modify strategies or bot
configs.

