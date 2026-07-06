# Task 41: V11.29 Feather-Based Ranging-Short Historical Return Study

## Summary

Implemented and ran a read-only feather-based historical return study generator:

```text
scripts/build_v1129_feather_ranging_short_historical_return_study.js
```

Generated:

```text
reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.json
reports/v1129_execution_validation/v1129_feather_ranging_short_historical_return_study.md
```

The generator reads server container feather files in read-only mode, derives
indicators from OHLCV, reconstructs a `v66_ranging_short_edge`-like candidate
family, and computes 1/2/4/8 candle forward return, MFE, MAE, and fee-adjusted
results.

This is not a Freqtrade backtest, not a live execution-quality report, and not
a V11.29 replacement verdict.

## Data Source

Read-only source:

```text
freqtrade-v1129
/freqtrade/project/user_data/data/futures
```

Study window:

```text
latest 30d ending 2026-07-03 08:45 UTC
```

Important limitation:

```text
The feather data ends on 2026-07-03 and does not include the latest runtime API
rows observed on 2026-07-06.
```

## Method

The Task 41 study is explicitly:

```text
derived_from_ohlcv_feather
```

It recomputes:

- `ema200`;
- `rsi`;
- Bollinger band percent;
- 24h/48h range width;
- 24h/48h range position;
- 4h ADX;
- 4h Bollinger width and width mean;
- derived 4h ranging/trending context.

Historical alpha-risk state is not reconstructed:

```text
alpha_state = missing
```

Therefore this report cannot replace Task 39's runtime alpha-allowed /
alpha-blocked split.

## Candidate Counts

| Metric | Count |
| --- | ---: |
| derived candidates | 1214 |
| study days | 30 |
| pair count | 12 |
| fee assumption | 10 bps |

Classification:

```text
research_candidate
```

Reason:

```text
derived candidate sample passes the initial fee-adjusted 4-candle mean gate
```

This classification means the candidate family deserves a decision review. It
does not authorize live trading.

## Aggregate Forward Return Summary

For a short candidate, positive return means the future close is lower than the
candidate close.

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1214 | 1.6147 | -8.3853 | 0.3979 | 27.4189 | 27.6761 |
| 2 | 1213 | 5.9944 | -4.0056 | 0.4625 | 39.1428 | 37.1132 |
| 4 | 1212 | 10.1647 | 0.1647 | 0.5149 | 55.8373 | 48.9276 |
| 8 | 1212 | 17.3426 | 7.3426 | 0.5817 | 78.6989 | 65.3719 |

## Pair-Level Result

| Pair | Candidates | 4-candle fee-adjusted mean bps |
| --- | ---: | ---: |
| BTC/USDT:USDT | 97 | -0.1956 |
| ETH/USDT:USDT | 65 | 14.8993 |
| SOL/USDT:USDT | 133 | -7.6870 |
| BNB/USDT:USDT | 110 | -4.3756 |
| XRP/USDT:USDT | 112 | 2.3791 |
| DOGE/USDT:USDT | 94 | 1.0184 |
| ADA/USDT:USDT | 90 | -12.6730 |
| LINK/USDT:USDT | 104 | 3.4790 |
| AVAX/USDT:USDT | 138 | 6.0043 |
| LTC/USDT:USDT | 158 | 0.4521 |
| TRX/USDT:USDT | 7 | -6.5083 |
| BCH/USDT:USDT | 106 | 3.0939 |

## Comparison With Task 39

Task 39 runtime API sample:

- about 5.49 days;
- 111 candidates;
- 4-candle fee-adjusted mean: `-16.4547 bps`;
- alpha-allowed 4-candle fee-adjusted mean: `-15.5344 bps`;
- classification: `insufficient`.

Task 41 feather historical sample:

- 30 days;
- 1214 derived candidates;
- 4-candle fee-adjusted mean: `0.1647 bps`;
- 8-candle fee-adjusted mean: `7.3426 bps`;
- alpha state: `missing`;
- classification: `research_candidate`.

Interpretation:

- The short runtime sample was not enough to reject the candidate family.
- The longer feather sample is enough to justify a review.
- The edge is thin at 4 candles and pair-dependent.
- Historical alpha state remains a blocking gap before any live decision.

## What This Can Conclude

Observed:

- Server feather files can support a 30d OHLCV-derived study.
- The derived candidate family has more than 100 samples.
- The aggregate 4-candle fee-adjusted mean is slightly positive.

Derived:

- The candidate family should not be immediately rejected based on the 5.49d
  runtime API window alone.
- Pair-level filtering is likely important because results are uneven.

Insufficient:

- This is not a full strategy backtest.
- This is not a live execution-quality report.
- Historical alpha state is missing.
- The source feather data is stale relative to current runtime by about three
  days.
- This does not measure orders, fills, fees, funding, slippage, or latency.

Unknown:

- Whether the same candidate definition would survive exact live strategy
  indicator implementation.
- Whether alpha filtering would remove the profitable subset, the losing
  subset, or both.
- Whether a shadow dry-run implementation would preserve the observed candle
  edge after realistic execution constraints.

## Safety Decision

Do not enable live V11.29 ranging-short entries from this evidence.

The evidence supports a decision review and possibly a later explicitly
authorized shadow/dry-run design. It does not support direct strategy/config
modification.

## Validation

Commands run:

```powershell
node --check scripts/build_v1129_feather_ranging_short_historical_return_study.js
node scripts/build_v1129_feather_ranging_short_historical_return_study.js
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- download or refresh market data;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Recommended Task 42

Recommended next task:

```text
Task 42: V11.29 Ranging-Short Calibration Decision Review
```

Scope:

- Compare Task 39 and Task 41.
- Decide whether ranging-short should be rejected, studied further, or moved to
  a separately authorized shadow/dry-run design.
- Define any required pair filters, alpha requirements, and stop conditions.
- Do not modify live strategy/config in the review task.

