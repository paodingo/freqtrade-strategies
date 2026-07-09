# Task 128: Ranging Short Candidate Evidence Deep Review

## Summary

Reviewed the `ranging_short_volatility_fade` candidate family selected by Task
125.

Decision:

```text
research_candidate_requires_alpha_and_recent_window_validation
```

The ranging-short family has a large historical OHLCV-derived sample and a
positive 8-candle fee-adjusted mean, but it is not ready for strategy
implementation, backtest, or deployment. It needs alpha-state reconstruction and
a more recent window check first.

## Source Evidence

| source | path |
|---|---|
| Task 125 selection review | `reports/audits/task125_next_candidate_family_selection_review.md` |
| candidate search summary | `reports/candidate_search/2026-07-09-v1130-15m-4h-first-pass/candidate_search_summary.json` |
| ranging-short historical study | `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json` |
| ranging-short markdown report | `reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md` |

## Aggregate Evidence

| horizon | count | fee-adjusted mean bps | fee-adjusted positive rate | MFE mean bps | MAE mean bps |
|---:|---:|---:|---:|---:|---:|
| `1` | `1214` | `-8.3853` | `0.3979` | `27.4189` | `27.6761` |
| `2` | `1213` | `-4.0056` | `0.4625` | `39.1428` | `37.1132` |
| `4` | `1212` | `0.1647` | `0.5149` | `55.8373` | `48.9276` |
| `8` | `1212` | `7.3426` | `0.5817` | `78.6989` | `65.3719` |

The useful signal is concentrated at longer short horizons. The 1- and
2-candle horizons are negative after fees.

## Pair-Level Notes

From the existing pair matrix:

- positive 4-candle fee-adjusted examples include `ETH`, `XRP`, `DOGE`,
  `LINK`, `AVAX`, `LTC`, and `BCH`;
- weaker or negative 4-candle fee-adjusted examples include `BTC`, `SOL`,
  `BNB`, `ADA`, and `TRX`;
- `TRX` has only `7` candidates and should not drive decisions;
- pair concentration and drawdown path are still not proven in the current
  summary.

## Why This Candidate Is Interesting

- It has `1214` historical OHLCV-derived candidates.
- It is a different behavior family from the current long rebound variants.
- It may diversify the system if long crash-rebound logic continues to lose in
  live dry-run.
- The 8-candle fee-adjusted mean is positive and sample size is large.

## Why It Is Not Ready

Blocking gaps:

- alpha state is `missing`;
- exchange/order execution is not modeled;
- funding, slippage, latency, and real fees are not proven;
- exit distribution is missing;
- max drawdown is unknown;
- recent runtime window is missing because the source feather data ended at
  `2026-07-03T08:45:00+00:00`;
- no Freqtrade backtest exists;
- no live dry-run evidence exists.

## Recommended Next Task

Proceed with:

```text
Task 131: Ranging Short Alpha-State Reconstruction Plan
```

Task 131 should stay read-only and decide which alpha/taker/protection fields
must be reconstructed before any strategy implementation task.

## Non-Conclusion

This task does not conclude:

- the ranging-short candidate is profitable;
- the ranging-short candidate should be implemented now;
- V11.30 or V11.31 should be abandoned;
- any bot should be started, stopped, or restarted.

