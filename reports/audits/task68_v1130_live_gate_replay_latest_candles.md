# Task 68: V11.30 Live Gate Replay On Latest Candles

## Summary

V11.30 crash-rebound gate logic was replayed read-only on the latest available
analyzed candle proxy for the V11.30 pair set.

Conclusion:

- the 240-candle window contained historical V11.30 crash-rebound candidates;
- the latest candle for every checked pair was `not_candidate`;
- current `orders = 0` is consistent with no latest qualifying signal during
  this observation point;
- this does not prove the strategy is good or bad, and does not prove that no
  future trade should occur.

## Data Source Limitation

V11.30 does not expose a REST API server. The replay used the running V11.29
local API `pair_candles` endpoint as a read-only analyzed-data proxy for the
same pair/timeframe window.

This task did not read V11.30 secrets, configs, or SQLite trade content.

## Replay Scope

Pairs:

- `ETH/USDT:USDT`
- `SOL/USDT:USDT`
- `DOGE/USDT:USDT`
- `LINK/USDT:USDT`
- `XRP/USDT:USDT`
- `BCH/USDT:USDT`

Timeframe:

- `15m`

Window:

- `240` rows per pair
- `1440` total rows

## Aggregate Gate Counts

Observed replay gate counts:

| gate | count |
|---|---:|
| `not_candidate` | 1429 |
| `enabled_crash_rebound_long` | 9 |
| `blocked_taker_sell_pressure` | 2 |

Raw condition fail counts:

| condition | count |
|---|---:|
| `range` | 1400 |
| `return` | 1322 |
| `volume` | 688 |
| `rsi` | 362 |

## Historical Enabled Examples

Enabled examples in the observed window:

- `ETH/USDT:USDT` at `2026-07-07T14:45:00Z`
- `SOL/USDT:USDT` at `2026-07-06T13:30:00Z`
- `SOL/USDT:USDT` at `2026-07-07T14:45:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T15:30:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T16:00:00Z`
- `LINK/USDT:USDT` at `2026-07-07T14:45:00Z`
- `XRP/USDT:USDT` at `2026-07-07T14:45:00Z`
- `BCH/USDT:USDT` at `2026-07-06T02:15:00Z`
- `BCH/USDT:USDT` at `2026-07-07T14:45:00Z`

Important note:

- V11.30 was started after several of these historical examples;
- historical replay examples do not imply the live bot should already have
  placed those orders.

## Latest Candle Status

Latest checked candle:

```text
2026-07-08T03:00:00Z
```

Latest candle gate result for all checked pairs:

```text
not_candidate
```

Observed latest-candle examples:

| pair | gate | key failed conditions |
|---|---|---|
| `ETH/USDT:USDT` | `not_candidate` | `return`, `range` |
| `SOL/USDT:USDT` | `not_candidate` | `return`, `range`, `rsi` |
| `DOGE/USDT:USDT` | `not_candidate` | `return`, `range`, `rsi`, `volume` |
| `LINK/USDT:USDT` | `not_candidate` | `return`, `range`, `rsi`, `volume` |
| `XRP/USDT:USDT` | `not_candidate` | `return`, `range`, `volume` |
| `BCH/USDT:USDT` | `not_candidate` | `return`, `range` |

## Interpretation

Observed:

- V11.30 entry gates can trigger in the 240-candle proxy window.
- At the latest observation point, no checked pair passed the entry gate.
- The lack of orders at that moment is consistent with gate behavior.

Not concluded:

- this task does not prove V11.30 is profitable;
- this task does not prove V11.30 should replace V10.8.2;
- this task does not prove V11.30 is too strict across all market regimes.

## Non-Actions

This task did not:

- read secrets;
- write SQLite;
- start, stop, or restart bots;
- run backtests;
- modify strategies or bot configs;
- modify the original dirty workspace.

## Recommended Next Task

Proceed with:

```text
Task 71: Dashboard Current Strategy Display Alignment
```

Purpose:

- show the currently running V11.30 shadow instead of the stopped old
  `v1129_shadow`;
- avoid misleading web dashboard status.
