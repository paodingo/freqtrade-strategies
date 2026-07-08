# Task 81: V11.30 Range Threshold Offline Return Study

## Summary

Performed a read-only offline return study for the V11.30 watch scenario
`range >= 0.008`, keeping the existing return, RSI, volume, and alpha block
logic.

Conclusion:

- candidate count: `29`;
- enabled count after alpha/taker filters: `23`;
- blocked by taker sell pressure: `6`;
- blocked by alpha short: `0`;
- 1-candle forward return was weak;
- 4-candle and 8-candle close-to-close forward returns were positive in this
  small proxy window;
- this is not a backtest and not a live strategy-change approval.

## Method

Data source:

- read-only `v1129` local API `pair_candles` proxy;
- 6 V11.30 pairs;
- timeframe: `15m`;
- window: `240` candles per pair.

Scenario parameters:

| parameter | value |
|---|---:|
| `min_return` | `0.004` |
| `min_range` | `0.008` |
| `min_rsi` | `35` |
| `max_rsi` | `62` |
| `min_volume_ratio` | `0.8` |

Forward return method:

- close-to-close long approximation;
- horizons:
  - 1 candle;
  - 4 candles;
  - 8 candles.

## Candidate Counts

| metric | count |
|---|---:|
| candidates | 29 |
| enabled | 23 |
| blocked total | 6 |
| blocked by `takerSellPressure` | 6 |
| blocked by alpha short | 0 |

## Forward Return Summary

| horizon | samples | mean bps | median bps | win rate | min bps | max bps |
|---|---:|---:|---:|---:|---:|---:|
| 1 candle | 23 | -1.88 | -5.47 | 0.3913 | -72.66 | 73.97 |
| 4 candles | 23 | 20.15 | 38.09 | 0.7391 | -158.04 | 147.06 |
| 8 candles | 23 | 34.13 | 51.09 | 0.5652 | -152.80 | 189.00 |

## Interpretation

Observed:

- loosening range from `0.012` to `0.008` materially increases candidates;
- the 4-candle horizon looks strongest in this small proxy window;
- the 1-candle horizon is not compelling.

Not concluded:

- this does not include fees, funding, slippage, latency, fills, or protections;
- this does not prove profitability;
- this does not justify changing the live V11.30 threshold directly;
- this does not evaluate replacement readiness.

## Risk Notes

The range relaxation may increase noisy signals. A safer next design is a
two-tier system:

- keep strict V11.30 live entry unchanged;
- add a looser watch gate for telemetry/alerting only;
- only promote the looser gate after replay/backtest and live observation.

## Non-Actions

This task did not:

- modify strategy thresholds;
- modify bot configs;
- start, stop, or restart bots;
- read secrets;
- run backtests;
- write SQLite.

## Recommended Next Task

Proceed with:

```text
Task 82: V11.30 live observation continuation with telemetry
Task 83: V11.30 loose-range watch gate design
```
