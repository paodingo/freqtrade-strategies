# V11.30 Loose-Range Replay Report

## Summary

This report evaluates the watch-only V11.30 loose-range scenario:

```text
range >= 0.008
```

It does not modify the live strategy and does not place orders.

## Counts

| metric | count |
|---|---:|
| candidates | 29 |
| enabled | 23 |
| blocked | 6 |
| blocked by taker sell pressure | 6 |
| blocked by alpha short | 0 |

## Forward Return Summary

| horizon | samples | mean bps | median bps | win rate | min bps | max bps |
|---|---:|---:|---:|---:|---:|---:|
| `1_candle` | 23 | -1.88 | -5.47 | 0.3913 | -72.66 | 73.97 |
| `4_candle` | 23 | 20.15 | 38.09 | 0.7391 | -158.04 | 147.06 |
| `8_candle` | 23 | 34.13 | 51.09 | 0.5652 | -152.8 | 189 |
| `16_candle` | 23 | 16.69 | -17.67 | 0.4348 | -161.32 | 256.32 |

## Enabled Concentration By Pair

| pair | enabled |
|---|---:|
| `ETH/USDT:USDT` | 3 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 6 |
| `LINK/USDT:USDT` | 3 |
| `XRP/USDT:USDT` | 2 |
| `BCH/USDT:USDT` | 6 |

## Enabled Concentration By Day

| day | enabled |
|---|---:|
| `2026-07-06` | 12 |
| `2026-07-07` | 8 |
| `2026-07-08` | 3 |

## Enabled Examples

- `ETH/USDT:USDT` at `2026-07-06T00:30:00Z`
- `ETH/USDT:USDT` at `2026-07-06T13:30:00Z`
- `ETH/USDT:USDT` at `2026-07-07T14:45:00Z`
- `SOL/USDT:USDT` at `2026-07-06T00:30:00Z`
- `SOL/USDT:USDT` at `2026-07-06T13:30:00Z`
- `SOL/USDT:USDT` at `2026-07-07T14:45:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T00:30:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T15:30:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T16:00:00Z`
- `DOGE/USDT:USDT` at `2026-07-07T12:00:00Z`
- `DOGE/USDT:USDT` at `2026-07-07T14:45:00Z`
- `DOGE/USDT:USDT` at `2026-07-07T16:15:00Z`
- `LINK/USDT:USDT` at `2026-07-06T13:30:00Z`
- `LINK/USDT:USDT` at `2026-07-06T14:15:00Z`
- `LINK/USDT:USDT` at `2026-07-07T14:45:00Z`
- `XRP/USDT:USDT` at `2026-07-06T15:30:00Z`
- `XRP/USDT:USDT` at `2026-07-07T14:45:00Z`
- `BCH/USDT:USDT` at `2026-07-06T02:15:00Z`
- `BCH/USDT:USDT` at `2026-07-06T14:15:00Z`
- `BCH/USDT:USDT` at `2026-07-07T14:45:00Z`

## Limitations

- Watch-only replay; does not set enter_long or place orders.
- Close-to-close proxy only; no fills, fees, funding, slippage, latency, protections, or wallet constraints.
- Not a Freqtrade backtest and not a live strategy-change approval.
- Does not prove V11.30 can replace any benchmark.

## Recommendation

- status: `continue_watch_only_validation`
- reason: 4-candle and 8-candle proxy returns are positive, but sample size is small and costs/fills are not modeled.

## Next Tasks

- Task 87: decide whether to implement a watch-only telemetry lane
- Task 88R: allow exact watch-only telemetry implementation paths if approved
- Task 88: implement watch-only telemetry lane without live orders
