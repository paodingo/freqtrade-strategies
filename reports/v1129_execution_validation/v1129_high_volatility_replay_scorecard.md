# V11.29 High-Volatility Replay Scorecard

## Summary

This report is a read-only replay scorecard for high-volatility candidate
families observed in the current V11.29 analyzed dataframe. It does not modify
strategy code, bot config, server files, SQLite, dashboard code, or live state.

Important: this report does not claim that any candidate is production-ready.
It only ranks candidate families for Task 58.

## Metadata

| Field | Value |
| --- | --- |
| Generated at | 2026-07-08T01:42:31.064Z |
| Source | freqtrade-v1129 analyzed dataframe via read-only API |
| Timeframe | 15m |
| Total rows | 8064 |
| Fee assumption | 10 bps |
| Pairs | 12 |

## Aggregate Counts

| Metric | Count |
| --- | ---: |
| final entry rows | 0 |
| alpha long block rows | 7728 |
| alpha short block rows | 2712 |
| high volatility | 43 |
| selloff continuation | 122 |
| blowoff short | 1075 |
| crash rebound | 15 |

## Candidate Ranking

| Rank | Candidate | Directional count | Horizon candles | Fee-adjusted mean bps | Positive rate | MAE mean bps |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | crash_rebound | 15 | 4 | 21.5559 | 0.6667 | 69.002 |
| 2 | blowoff_short | 1075 | 4 | -18.653 | 0.4009 | 65.7918 |
| 3 | selloff_continuation | 122 | 4 | -19.9735 | 0.3361 | 66.9187 |

## Candidate Details

### blowoff_short

Count: 1075

| Horizon candles | Count | Fee-adjusted mean bps | Fee-adjusted median bps | Positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1075 | -12.6173 | -10 | 0.3433 | 25.526 | 31.6107 |
| 2 | 1075 | -15.518 | -10 | 0.3674 | 34.8915 | 46.1531 |
| 4 | 1075 | -18.653 | -10 | 0.4009 | 46.9941 | 65.7918 |
| 8 | 1075 | -20.9402 | -11.2301 | 0.427 | 64.902 | 90.3689 |

### selloff_continuation

Count: 122

| Horizon candles | Count | Fee-adjusted mean bps | Fee-adjusted median bps | Positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 122 | -14.5011 | -18.7348 | 0.3279 | 36.0239 | 33.1204 |
| 2 | 122 | -16.556 | -14.335 | 0.3934 | 45.6948 | 45.3694 |
| 4 | 122 | -19.9735 | -28.485 | 0.3361 | 60.5804 | 66.9187 |
| 8 | 122 | -15.6572 | -4.6013 | 0.4508 | 76.6141 | 88.2561 |

### high_volatility

Count: 43

| Horizon candles | Count | Fee-adjusted mean bps | Fee-adjusted median bps | Positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | missing | missing | missing | missing | missing |
| 2 | 0 | missing | missing | missing | missing | missing |
| 4 | 0 | missing | missing | missing | missing | missing |
| 8 | 0 | missing | missing | missing | missing | missing |

### crash_rebound

Count: 15

| Horizon candles | Count | Fee-adjusted mean bps | Fee-adjusted median bps | Positive rate | MFE mean bps | MAE mean bps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 15 | -24.2379 | -27.3405 | 0.2 | 28.535 | 45.313 |
| 2 | 15 | -6.715 | 8.1131 | 0.6 | 46.6869 | 55.5285 |
| 4 | 15 | 21.5559 | 34.1647 | 0.6667 | 79.7281 | 69.002 |
| 8 | 15 | 51.9828 | 41.3761 | 0.6667 | 138.367 | 80.2927 |

## Pair Matrix

| Pair | Rows | Latest date | High volatility | Selloff continuation | Blowoff short | Crash rebound | Directional candidates |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 0 | 5 | 86 | 0 | 91 |
| ETH/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 2 | 9 | 99 | 1 | 109 |
| SOL/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 3 | 7 | 63 | 2 | 72 |
| BNB/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 0 | 2 | 103 | 0 | 105 |
| XRP/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 0 | 5 | 95 | 1 | 101 |
| DOGE/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 1 | 14 | 85 | 2 | 101 |
| ADA/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 18 | 29 | 111 | 1 | 141 |
| LINK/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 2 | 11 | 84 | 1 | 96 |
| AVAX/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 1 | 6 | 69 | 0 | 75 |
| LTC/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 1 | 8 | 69 | 0 | 77 |
| TRX/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 0 | 0 | 114 | 0 | 114 |
| BCH/USDT:USDT | 672 | 2026-07-08T01:15:00Z | 15 | 26 | 97 | 7 | 130 |

## Representative Directional Examples

| Candidate | Pair | Time UTC | Direction | Entry close | Horizon fee-adjusted bps | MFE bps | MAE bps | Alpha flags |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T13:30:00Z | short | 58989.1 | -110.6796 | 13.9856 | 182.8812 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T13:45:00Z | short | 59463.1 | -20.208 | 37.5359 | 101.7101 | longCrowding,topTraderAccountLongCrowding,takerBuyPressure |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T14:00:00Z | short | 59948.6 | -1.059 | 92.7128 | 19.9004 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T14:15:00Z | short | 59756.4 | -99.0281 | 60.847 | 127.7855 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T14:30:00Z | short | 59583 | -112.3614 | 31.9219 | 157.2596 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T14:45:00Z | short | 59523.8 | -109.9096 | 4.5192 | 167.3616 | longCrowding,topTraderAccountLongCrowding,takerSellPressure |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T15:00:00Z | short | 59895 | -46.1299 | 12.1546 | 104.3493 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T15:15:00Z | short | 60288.4 | 18.8281 | 60.2769 | 11.1962 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T15:30:00Z | short | 60192.9 | 12.0624 | 44.5069 | 8.4894 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T21:00:00Z | short | 60427.1 | -71.6942 | 20.3551 | 66.3113 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T21:15:00Z | short | 60504.5 | -12.8262 | 0.0165 | 135.1139 | longCrowding,topTraderAccountLongCrowding |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T21:30:00Z | short | 60788.8 | 42.6084 | 60.2085 | 87.7135 | longCrowding,topTraderAccountLongCrowding,takerBuyPressure |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T21:45:00Z | short | 60799.9 | 48.158 | 79.0462 | 85.8719 | longCrowding,topTraderAccountLongCrowding,takerBuyPressure |
| blowoff_short | BTC/USDT:USDT | 2026-07-01T22:00:00Z | short | 60799.9 | 85.839 | 98.2403 | 85.8719 | longCrowding,topTraderAccountLongCrowding,takerBuyPressure |
| blowoff_short | BTC/USDT:USDT | 2026-07-02T03:15:00Z | short | 60520.4 | -61.2224 | 11.5663 | 96.1824 | longCrowding,topTraderAccountLongCrowding,takerSellPressure |
| blowoff_short | BTC/USDT:USDT | 2026-07-02T03:30:00Z | short | 60781.3 | -4.8175 | 12.8987 | 52.8452 | longCrowding,topTraderAccountLongCrowding,takerSellPressure |

## Interpretation

Observed:

- The current V11.29 analyzed dataframe has enough rows to replay recent
  high-volatility candidate families.
- Final V11.29 entries remain zero in the replayed dataframe.
- Candidate families exist before any live strategy/config modification.

Derived:

- Direction-aware forward returns can rank candidate families.
- Task 58 should use this scorecard to choose whether V11.30 should focus on
  selloff continuation, blowoff short, crash rebound, or reject all three.

Insufficient:

- This is not a Freqtrade backtest.
- This does not prove fill quality, slippage, funding, or latency.
- This does not justify live trading or strategy/config changes by itself.

## Verdict

| Field | Value |
| --- | --- |
| report_status | observed_replay_scorecard |
| can_select_v1130_candidate | true |
| can_enable_live_trading | false |
| next_required_task | Task 58: V11.30 Candidate Selection |

Recommended next task: Task 58: V11.30 Candidate Selection
