# V11.31 Loose-Range Watch Replay Report

## Summary

This is a read-only replay-planning report for:

```text
RegimeAwareV1131LooseRangeWatchShadow
```

It reuses existing V11.30 loose-range replay evidence because V11.31 implements
the same loose-range entry thresholds as a local shadow strategy.

## Data Gate

| item | value |
|---|---|
| timeframe | `15m` |
| informative timeframes | `4h` |
| excluded timeframe | `1h: Task 103 found exact 1h futures OHLCV stale` |
| backtest run | `false` |
| strategy modified by report | `false` |
| bot config modified by report | `false` |
| server operation | `false` |

## Counts

| metric | count |
|---|---:|
| candidates | 29 |
| enabled | 23 |
| blocked | 6 |
| blocked by taker sell pressure | 6 |
| blocked by alpha short | 0 |

## Forward Returns

| horizon | samples | mean bps | median bps | win rate | min bps | max bps |
|---|---:|---:|---:|---:|---:|---:|
| `1_candle` | 23 | -1.88 | -5.47 | 0.3913 | -72.66 | 73.97 |
| `4_candle` | 23 | 20.15 | 38.09 | 0.7391 | -158.04 | 147.06 |
| `8_candle` | 23 | 34.13 | 51.09 | 0.5652 | -152.8 | 189 |
| `16_candle` | 23 | 16.69 | -17.67 | 0.4348 | -161.32 | 256.32 |

## Fee-Adjusted Forward Returns

| horizon | samples | mean bps | median bps | fee bps |
|---|---:|---:|---:|---:|
| `1_candle` | 23 | -11.88 | -15.47 | 10 |
| `4_candle` | 23 | 10.15 | 28.09 | 10 |
| `8_candle` | 23 | 24.13 | 41.09 | 10 |
| `16_candle` | 23 | 6.69 | -27.67 | 10 |

## Concentration

| pair | enabled |
|---|---:|
| `ETH/USDT:USDT` | 3 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 6 |
| `LINK/USDT:USDT` | 3 |
| `XRP/USDT:USDT` | 2 |
| `BCH/USDT:USDT` | 6 |

max_pair_share: `0.2609`

## Sample Status

- status: `thin`
- enabled_samples: `23`
- minimum_gate: `30`
- reason: enabled sample count is below the initial gate

## Limitations

- Derived from existing V11.30 loose-range replay evidence because V11.31 uses the same loose-range entry thresholds.
- Not a Freqtrade backtest.
- No fills, funding, slippage, latency, protections, wallet constraints, or order book execution quality are modeled.
- Exit distribution is not proven; forward returns are close-to-close proxies.
- 1h OHLCV is excluded because the exact futures 1h data was stale in Task 103.
- Does not prove V11.31 can replace V10.8.2 or V11.30.

## Verdict

- can_proceed_to_backtest_plan: `false`
- can_deploy_shadow: `false`
- can_evaluate_replacement: `false`
- reason: The replay has positive 4/8 candle proxy evidence but only 23 enabled samples and no execution-quality model.
- next_required_task: `Task 117: V11.31 Replay Result Review / Backtest Go-No-Go`
