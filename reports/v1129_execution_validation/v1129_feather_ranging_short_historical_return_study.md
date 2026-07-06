# V11.29 Feather-Based Ranging-Short Historical Return Study

## Summary

This report studies a 30d feather-based, OHLCV-derived approximation of the
`v66_ranging_short_edge` candidate family. It reads server container feather
files in read-only mode. It does not download or refresh data, run a Freqtrade
backtest, read secrets, modify strategy code, modify bot configuration, write
SQLite, or start/stop/restart any bot.

- Method: `derived_from_ohlcv_feather`
- Study days: 30
- Candidate count: 1214
- Fee assumption: 10 bps round trip
- Alpha state: `missing`
- Classification: `research_candidate`
- Can enable live ranging-short: `false`
- Can claim V11.29 replacement: `false`

## Classification Reasons

- derived candidate sample passes the initial fee-adjusted 4-candle mean gate

## Aggregate Forward Return Summary

For a short candidate, positive return means future close is lower than the
candidate close. Fee-adjusted return subtracts the conservative round-trip fee
assumption.

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1214 | 1.6147 | -8.3853 | 0.3979 | 27.4189 | 27.6761 |
| 2 | 1213 | 5.9944 | -4.0056 | 0.4625 | 39.1428 | 37.1132 |
| 4 | 1212 | 10.1647 | 0.1647 | 0.5149 | 55.8373 | 48.9276 |
| 8 | 1212 | 17.3426 | 7.3426 | 0.5817 | 78.6989 | 65.3719 |

## Pair Matrix

| Pair | Source | Study days | Study rows | Candidates | Data min | Data max | 4-candle fee-adjusted mean bps |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| BTC/USDT:USDT | observed | 30 | 2881 | 97 | 2026-04-10T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | -0.1956 |
| ETH/USDT:USDT | observed | 30 | 2881 | 65 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 14.8993 |
| SOL/USDT:USDT | observed | 30 | 2881 | 133 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | -7.687 |
| BNB/USDT:USDT | observed | 30 | 2881 | 110 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | -4.3756 |
| XRP/USDT:USDT | observed | 30 | 2881 | 112 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 2.3791 |
| DOGE/USDT:USDT | observed | 30 | 2881 | 94 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 1.0184 |
| ADA/USDT:USDT | observed | 30 | 2881 | 90 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | -12.673 |
| LINK/USDT:USDT | observed | 30 | 2881 | 104 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 3.479 |
| AVAX/USDT:USDT | observed | 30 | 2881 | 138 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 6.0043 |
| LTC/USDT:USDT | observed | 30 | 2881 | 158 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 0.4521 |
| TRX/USDT:USDT | observed | 30 | 2881 | 7 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | -6.5083 |
| BCH/USDT:USDT | observed | 30 | 2881 | 106 | 2024-01-01T00:00:00+00:00 | 2026-07-03T08:45:00+00:00 | 3.0939 |

## Representative Candidate Outcomes

| Pair | Time UTC | Entry close | RSI | BB% | 4-candle fee-adjusted bps | 4-candle MFE bps | 4-candle MAE bps |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 2026-06-11T03:45:00+00:00 | 62657.5 | 70.3348 | 1 | -15.6498 | 23.1257 | 27.0518 |
| BTC/USDT:USDT | 2026-06-11T04:00:00+00:00 | 62635.8 | 69.4464 | 0.9724 | -3.7097 | 19.6693 | 30.5257 |
| BTC/USDT:USDT | 2026-06-11T04:45:00+00:00 | 62692.9 | 69.6447 | 0.9019 | 7.7373 | 26.3826 | 0.6061 |
| BTC/USDT:USDT | 2026-06-11T06:00:00+00:00 | 62754.5 | 67.0814 | 0.8369 | 10.9547 | 28.7151 | 38.069 |
| BTC/USDT:USDT | 2026-06-11T06:15:00+00:00 | 62845.5 | 69.1772 | 0.8722 | 3.748 | 43.1534 | 20.6697 |
| BTC/USDT:USDT | 2026-06-11T06:30:00+00:00 | 62919.8 | 70.8111 | 0.8847 | 33.3091 | 54.9112 | 0.0318 |
| BTC/USDT:USDT | 2026-06-11T08:15:00+00:00 | 62924.6 | 64.37 | 0.9542 | 10.6596 | 27.2231 | 18.8321 |
| BTC/USDT:USDT | 2026-06-11T08:45:00+00:00 | 62927.2 | 62.9119 | 0.936 | -5.6617 | 27.6351 | 6.9127 |

## Limitations

- Candidate signals are derived from raw OHLCV feather files and recomputed indicators.
- Historical alpha-risk allowed/blocked state is missing.
- This is not a Freqtrade backtest and not a live execution-quality report.
- Feather data ends on 2026-07-03 and does not include the latest runtime API rows observed on 2026-07-06.

## What This Can Conclude

Observed:

- 30d feather data can be read for the V11.29 pair universe.
- OHLCV-derived candidate reconstruction can be computed without modifying
  server files or strategy code.
- Forward return, MFE, and MAE can be computed from historical candles.

Derived:

- The result can inform a calibration decision review.
- Because alpha state is missing, this cannot replace the runtime
  alpha-allowed/blocked analysis.

Insufficient:

- This is not a full strategy backtest.
- This is not a live execution-quality report.
- This does not include real orders, fills, fees, funding, slippage, or latency.
- This does not authorize a live strategy/config change.

## Recommended Next Task

Task 42: V11.29 Ranging-Short Calibration Decision Review

Scope:

- Compare Task 39 runtime-data result and Task 41 feather-data result.
- Decide whether the ranging-short research lane is rejected, needs more data,
  or deserves a separately authorized shadow/dry-run design.
- Do not modify live V11.29 strategy/config in the review task.

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
