# V11.30 Decision Trace Report

## Summary

This report combines existing read-only evidence into a V11.30 decision trace.

Result:

- OHLCV-derived gate fields are available.
- V11.30 runtime counts are available.
- Alpha/taker/protection/final live decision path remains unknown.
- No order-capable behavior is emitted by this report.

## Metadata

- strategy: `RegimeAwareV1130CrashReboundShadow`
- version: `V11.30`
- generated at: `2026-07-08T09:36:26.386Z`
- can place orders: `false`
- modifies strategy: `false`
- modifies bot config: `false`
- reads secret: `false`

## Latest Decision Trace Rows

| pair | candle time | strict gate | watch gate | blocked state | blocked reason |
|---|---|---|---|---|---|
| `ETH/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `derived` | `return, range, volume` |
| `SOL/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `derived` | `return, range, rsi` |
| `DOGE/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `derived` | `return, rsi` |
| `LINK/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `derived` | `return, range, rsi` |
| `XRP/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `derived` | `return, range, rsi` |
| `BCH/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `derived` | `return, range, volume` |

## Observed

- OHLCV fields: `return_ratio, range_ratio, rsi, volume_ratio`
- V11.30 trades: `0`
- V11.30 orders: `0`
- container state: `freqtrade-v1130-crash-rebound-shadow|Up 7 hours|`

## Derived

- watch-only candidate count: `20`
- latest strict gates: `ETH/USDT:USDT:not_candidate; SOL/USDT:USDT:not_candidate; DOGE/USDT:USDT:not_candidate; LINK/USDT:USDT:not_candidate; XRP/USDT:USDT:not_candidate; BCH/USDT:USDT:not_candidate`
- latest watch gates: `ETH/USDT:USDT:not_candidate; SOL/USDT:USDT:not_candidate; DOGE/USDT:USDT:not_candidate; LINK/USDT:USDT:not_candidate; XRP/USDT:USDT:not_candidate; BCH/USDT:USDT:not_candidate`

## Missing Or Unknown

- `alpha_flags`
- `taker_buy_pressure`
- `taker_sell_pressure`
- `protection_blocked`
- `wallet_or_stake_blocked`
- `max_open_trades_blocked`
- `live_strategy_final_enter_long_reason`

## Classification

- state: `insufficient`
- value: Existing sources do not expose the final live strategy decision path.
- next required task: Task 92: V11.30 decision trace observation window

## Limitations

- This collector reads prepared input only and does not connect to exchange APIs.
- It does not read secrets or bot configs.
- It does not modify strategy behavior or bot runtime state.
- It cannot prove alpha/taker/protection blocks without an authorized source.
- It cannot conclude whether V11.30 can replace V10.8.2.
