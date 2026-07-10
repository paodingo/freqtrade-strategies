# V11.31 Actual Data Acquisition Execution Report

## Summary

Read-only SSH metadata collection completed. No data was copied, refreshed, downloaded, or written.

## Server Context

| field | value |
| --- | --- |
| host | 43.134.72.69 |
| user | ubuntu |
| hostname | VM-0-8-ubuntu |
| server date | 2026-07-10T11:17:16+08:00 |
| selected source | container:freqtrade-v1130-crash-rebound-shadow |

## Window Summary

| timeframe | existing files | min rows | earliest | latest |
| --- | --- | --- | --- | --- |
| 15m | 6/6 | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| 4h | 6/6 | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |

## File Evidence

| pair | timeframe | exists | rows | first | last |
| --- | --- | --- | --- | --- | --- |
| ETH/USDT:USDT | 15m | true | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| ETH/USDT:USDT | 4h | true | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |
| SOL/USDT:USDT | 15m | true | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| SOL/USDT:USDT | 4h | true | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |
| DOGE/USDT:USDT | 15m | true | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| DOGE/USDT:USDT | 4h | true | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |
| LINK/USDT:USDT | 15m | true | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| LINK/USDT:USDT | 4h | true | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |
| XRP/USDT:USDT | 15m | true | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| XRP/USDT:USDT | 4h | true | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |
| BCH/USDT:USDT | 15m | true | 88429 | 2024-01-01 00:00:00+00:00 | 2026-07-10 03:00:00+00:00 |
| BCH/USDT:USDT | 4h | true | 5526 | 2024-01-01 00:00:00+00:00 | 2026-07-09 20:00:00+00:00 |

## Decisions

| decision | value |
| --- | --- |
| can authorize replay gate review | true |
| can run longer replay backtest | false |
| can deploy shadow | false |
| can claim profitability | false |

## Blocking Gaps

- Alpha/taker/protection timelines remain unknown.
- No backtest was run in this task.

## Recommended Next Task

Task 186: V11.31 Longer Replay Backtest Gate Review
