# V11.30 Gate Telemetry Report

## Summary

This report persists the audited Task 68 V11.30 gate replay evidence into JSON
and Markdown artifacts.

Conclusion:

- latest checked candle gate state is persisted per checked pair;
- window-level replay found `9` enabled crash-rebound examples;
- V11.30 SQLite zero trades/orders from Task 72 remains insufficient evidence;
- this report does not prove profitability or replacement readiness.

## Metadata

- strategy: `RegimeAwareV1130CrashReboundShadow`
- version: `V11.30`
- generated at: `2026-07-08T06:34:32.274Z`
- source: `post_refresh_v1129_api_pair_candles_proxy`
- timeframe: `15m`
- can place orders: `false`
- reads secret: `false`
- runs backtest: `false`
- downloads or refreshes data: `false`

## Latest Candle Gate State

| pair | candle time | gate | failed conditions |
|---|---|---|---|
| `ETH/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `return, range, volume` |
| `SOL/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `return, range, rsi` |
| `DOGE/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `return, range, rsi` |
| `LINK/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `return, range, rsi` |
| `XRP/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `return, range, rsi` |
| `BCH/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `return, range, volume` |

## Window Gate Counts

| gate | count |
|---|---:|
| `not_candidate` | 1429 |
| `enabled_crash_rebound_long` | 9 |
| `blocked_taker_sell_pressure` | 2 |

## Raw Fail Counts

| condition | count |
|---|---:|
| `return` | 1324 |
| `range` | 1400 |
| `rsi` | 387 |
| `volume` | 707 |

## Enabled Examples

- `ETH/USDT:USDT` at `2026-07-07T14:45:00Z`
- `SOL/USDT:USDT` at `2026-07-06T13:30:00Z`
- `SOL/USDT:USDT` at `2026-07-07T14:45:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T15:30:00Z`
- `DOGE/USDT:USDT` at `2026-07-06T16:00:00Z`
- `LINK/USDT:USDT` at `2026-07-07T14:45:00Z`
- `XRP/USDT:USDT` at `2026-07-07T14:45:00Z`
- `BCH/USDT:USDT` at `2026-07-06T02:15:00Z`
- `BCH/USDT:USDT` at `2026-07-07T14:45:00Z`

## Sensitivity

| scenario | candidates | enabled | blocked taker sell pressure | blocked alpha short |
|---|---:|---:|---:|---:|
| `baseline` | 11 | 9 | 2 | 0 |
| `return_0_003` | 11 | 9 | 2 | 0 |
| `range_0_008` | 29 | 23 | 6 | 0 |
| `volume_ratio_0_6` | 11 | 9 | 2 | 0 |
| `rsi_30_68` | 14 | 10 | 4 | 0 |
| `combined_looser` | 46 | 34 | 12 | 0 |

## Zero-Trade Interpretation

- V11.30 trades: `0` observed in Task 72.
- V11.30 orders: `0` observed in Task 72.
- These are observed counts, not a strategy failure conclusion.
- The latest checked candles did not qualify for entry in the audited replay.

## Limitations

- This report is generated from a read-only post-refresh replay, not from a live V11.30 API.
- The builder itself does not download or refresh market data.
- It does not read secrets, strategies, bot configs, or live SQLite content.
- It does not prove profitability or replacement readiness.

## Recommended Next Tasks

- Task 79: V11.30 threshold sensitivity audit
- Task 80: V11.30 data refresh command correction if feather latest candles remain stale
