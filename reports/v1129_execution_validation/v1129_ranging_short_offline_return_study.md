# V11.29 Ranging-Short Offline Candidate Return Study

## Summary

This report studies the `v66_ranging_short_edge` candidate family using the
read-only V11.29 runtime `pair_candles` API. It does not run a Freqtrade
backtest, read secrets, modify strategy code, modify bot configuration, write
SQLite, or start/stop/restart any bot.

- Candidate count: 111
- Max available runtime candle window: 5.4896 days
- Fee assumption: 10 bps round trip
- Classification: `insufficient`
- Can enable live ranging-short: `false`
- Can claim V11.29 replacement: `false`

## Classification Reasons

- available runtime candle window is shorter than the 30d minimum gate

## Aggregate Forward Return Summary

For a short candidate, positive return means the future close is lower than the
candidate close. Fee-adjusted return subtracts the conservative round-trip fee
assumption.

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 111 | 0.7886 | -9.2114 | 0.3333 | 20.4967 | 22.6922 |
| 2 | 111 | -0.9409 | -10.9409 | 0.3604 | 27.8754 | 31.8075 |
| 4 | 111 | -6.4547 | -16.4547 | 0.3514 | 35.3689 | 45.8417 |
| 8 | 111 | -15.599 | -25.599 | 0.3694 | 47.1988 | 73.7445 |

## Alpha-Allowed Candidate Summary

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 85 | 1.5558 | -8.4442 | 0.3176 | 20.0926 | 23.0007 |
| 2 | 85 | -1.2624 | -11.2624 | 0.3647 | 27.6336 | 32.3286 |
| 4 | 85 | -5.5344 | -15.5344 | 0.3882 | 35.7277 | 46.0665 |
| 8 | 85 | -13.8695 | -23.8695 | 0.4118 | 48.7151 | 72.3488 |

## Alpha-Blocked Candidate Summary

| Horizon candles | Count | Gross mean bps | Fee-adjusted mean bps | Fee-adjusted positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 26 | -1.7196 | -11.7196 | 0.3846 | 21.8179 | 21.6839 |
| 2 | 26 | 0.1103 | -9.8897 | 0.3462 | 28.6661 | 30.104 |
| 4 | 26 | -9.4633 | -19.4633 | 0.2308 | 34.1962 | 45.1066 |
| 8 | 26 | -21.2533 | -31.2533 | 0.2308 | 42.2415 | 78.3075 |

## Pair Matrix

| Pair | Rows | Available days | Candidates | 1d | 7d | 30d | Alpha allowed | Alpha blocked | 4-candle fee-adjusted mean bps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 528 | 5.4896 | 4 | 4 | 4 | 4 | 4 | 0 | 14.2424 |
| ETH/USDT:USDT | 528 | 5.4896 | 0 | 0 | 0 | 0 | 0 | 0 | missing |
| SOL/USDT:USDT | 528 | 5.4896 | 0 | 0 | 0 | 0 | 0 | 0 | missing |
| BNB/USDT:USDT | 528 | 5.4896 | 15 | 0 | 15 | 15 | 10 | 5 | -15.8643 |
| XRP/USDT:USDT | 528 | 5.4896 | 0 | 0 | 0 | 0 | 0 | 0 | missing |
| DOGE/USDT:USDT | 528 | 5.4896 | 27 | 0 | 27 | 27 | 20 | 7 | -10.4383 |
| ADA/USDT:USDT | 528 | 5.4896 | 0 | 0 | 0 | 0 | 0 | 0 | missing |
| LINK/USDT:USDT | 528 | 5.4896 | 0 | 0 | 0 | 0 | 0 | 0 | missing |
| AVAX/USDT:USDT | 528 | 5.4896 | 37 | 1 | 37 | 37 | 30 | 7 | -10.2284 |
| LTC/USDT:USDT | 528 | 5.4896 | 20 | 0 | 20 | 20 | 16 | 4 | -41.9578 |
| TRX/USDT:USDT | 528 | 5.4896 | 8 | 0 | 8 | 8 | 5 | 3 | -18.2542 |
| BCH/USDT:USDT | 528 | 5.4896 | 0 | 0 | 0 | 0 | 0 | 0 | missing |

## Representative Candidate Outcomes

| Pair | Time UTC | Blocked reason | Alpha short block | 4-candle fee-adjusted bps | 4-candle MFE bps | 4-candle MAE bps |
| --- | --- | --- | --- | ---: | ---: | ---: |
| BTC/USDT:USDT | 2026-07-05T22:30:00Z | v102_short_core_prunes_ranging_non_core_short | false | -29.4348 | 0.9127 | 70.0125 |
| BTC/USDT:USDT | 2026-07-05T22:45:00Z | v102_short_core_prunes_ranging_non_core_short | false | 5.6944 | 27.3553 | 42.9398 |
| BTC/USDT:USDT | 2026-07-05T23:00:00Z | v102_short_core_prunes_ranging_non_core_short | false | 49.0118 | 78.1977 | 5.848 |
| BTC/USDT:USDT | 2026-07-05T23:15:00Z | v102_short_core_prunes_ranging_non_core_short | false | 31.698 | 42.5621 | 8.1385 |
| BNB/USDT:USDT | 2026-07-03T08:30:00Z | v102_short_core_prunes_ranging_non_core_short | false | -3.264 | 38.9981 | 0 |
| BNB/USDT:USDT | 2026-07-03T09:00:00Z | v102_short_core_prunes_ranging_non_core_short | false | -6.6301 | 19.3324 | 19.3324 |
| BNB/USDT:USDT | 2026-07-03T09:15:00Z | alpha_filter_block_short | true | -16.9196 | 15.7908 | 22.8878 |
| BNB/USDT:USDT | 2026-07-03T10:30:00Z | v102_short_core_prunes_ranging_non_core_short | false | -20.4253 | 9.1884 | 36.2236 |

## What This Can Conclude

Observed:

- Runtime candle data was readable through the V11.29 API.
- The candidate family exists in the current runtime dataframe.
- Forward return, MFE, and MAE can be derived from candles for available rows.

Derived:

- The current sample can rank candidate behavior by pair and alpha state.
- The current sample can inform a later historical data extension task.

Insufficient:

- The available runtime window is shorter than the 30d calibration gate.
- This report is not a live execution-quality report.
- This report does not verify fees, fills, funding, slippage, or latency from
  real orders.
- This report cannot justify live strategy/config changes.

## Recommended Next Task

Task 40: V11.29 Ranging-Short Historical Data Coverage Extension

Scope:

- Acquire or locate at least 30d of clean 15m/4h candle context for the
  candidate family.
- Re-run the same candidate-only return study on the longer window.
- Keep the work offline until sample sufficiency and fee-adjusted gates are
  satisfied.

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
- write SQLite;
- modify server files;
- modify the original dirty workspace.
