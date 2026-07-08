# Task 86: V11.30 Loose-Range Replay Report Builder

## Summary

Implemented a read-only V11.30 loose-range replay report builder and generated
JSON/Markdown reports.

Conclusion:

- loose-range watch replay produced `29` candidates;
- `23` candidates remained enabled after alpha/taker filters;
- enabled samples are spread across all six pairs and three days;
- 4-candle and 8-candle close-to-close proxy returns are positive;
- 16-candle proxy weakens;
- this supports watch-only telemetry, not live threshold modification.

## Files Created

- `scripts/build_v1130_loose_range_replay_report.js`
- `reports/v1130_observation/v1130_loose_range_replay_report.json`
- `reports/v1130_observation/v1130_loose_range_replay_report.md`

## Replay Counts

| metric | count |
|---|---:|
| candidates | 29 |
| enabled | 23 |
| blocked | 6 |
| blocked by `takerSellPressure` | 6 |
| blocked by alpha short | 0 |

## Forward Return Summary

| horizon | samples | mean bps | median bps | win rate | min bps | max bps |
|---|---:|---:|---:|---:|---:|---:|
| 1 candle | 23 | -1.88 | -5.47 | 0.3913 | -72.66 | 73.97 |
| 4 candles | 23 | 20.15 | 38.09 | 0.7391 | -158.04 | 147.06 |
| 8 candles | 23 | 34.13 | 51.09 | 0.5652 | -152.80 | 189.00 |
| 16 candles | 23 | 16.69 | -17.67 | 0.4348 | -161.32 | 256.32 |

## Concentration

Enabled by pair:

| pair | enabled |
|---|---:|
| `ETH/USDT:USDT` | 3 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 6 |
| `LINK/USDT:USDT` | 3 |
| `XRP/USDT:USDT` | 2 |
| `BCH/USDT:USDT` | 6 |

Enabled by day:

| day | enabled |
|---|---:|
| `2026-07-06` | 12 |
| `2026-07-07` | 8 |
| `2026-07-08` | 3 |

## Interpretation

The loose-range watch gate has enough signal frequency to justify telemetry,
but not enough proof to justify live entry threshold changes.

Reasons:

- sample size is still small;
- no fill, fee, funding, slippage, latency, or protection modeling;
- 16-candle behavior weakens;
- current live V11.30 still has zero orders/trades.

## Validation

Commands:

```powershell
node --check scripts/build_v1130_loose_range_replay_report.js
node scripts/build_v1130_loose_range_replay_report.js
.\scripts\run_agent_readiness_checks.ps1
```

The builder requires `V1130_LOOSE_RANGE_REPLAY_INPUT_JSON`.

## Non-Actions

This task did not:

- modify live strategy;
- modify bot config;
- start, stop, or restart bots;
- read secrets;
- run backtests;
- write SQLite;
- place orders.

## Recommended Next Task

Proceed with:

```text
Task 87: Decide whether to implement a watch-only telemetry lane
```
