# V11.30 Gate Telemetry Report

## Summary

This report persists the audited Task 68 V11.30 gate replay evidence into JSON
and Markdown artifacts.

Conclusion:

- latest checked candle gate state: `not_candidate` for all checked pairs;
- window-level replay found `9` enabled crash-rebound examples;
- V11.30 SQLite zero trades/orders from Task 72 remains insufficient evidence;
- this report does not prove profitability or replacement readiness.

## Metadata

- strategy: `RegimeAwareV1130CrashReboundShadow`
- version: `V11.30`
- generated at: `2026-07-08T06:12:31.847Z`
- source: `task68_read_only_gate_replay`
- timeframe: `15m`
- can place orders: `false`
- reads secret: `false`
- runs backtest: `false`
- downloads or refreshes data: `false`

## Latest Candle Gate State

| pair | candle time | gate | failed conditions |
|---|---|---|---|
| `ETH/USDT:USDT` | `2026-07-08T03:00:00Z` | `not_candidate` | `return, range` |
| `SOL/USDT:USDT` | `2026-07-08T03:00:00Z` | `not_candidate` | `return, range, rsi` |
| `DOGE/USDT:USDT` | `2026-07-08T03:00:00Z` | `not_candidate` | `return, range, rsi, volume` |
| `LINK/USDT:USDT` | `2026-07-08T03:00:00Z` | `not_candidate` | `return, range, rsi, volume` |
| `XRP/USDT:USDT` | `2026-07-08T03:00:00Z` | `not_candidate` | `return, range, volume` |
| `BCH/USDT:USDT` | `2026-07-08T03:00:00Z` | `not_candidate` | `return, range` |

## Window Gate Counts

| gate | count |
|---|---:|
| `not_candidate` | 1429 |
| `enabled_crash_rebound_long` | 9 |
| `blocked_taker_sell_pressure` | 2 |

## Raw Fail Counts

| condition | count |
|---|---:|
| `range` | 1400 |
| `return` | 1322 |
| `volume` | 688 |
| `rsi` | 362 |

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

## Zero-Trade Interpretation

- V11.30 trades: `0` observed in Task 72.
- V11.30 orders: `0` observed in Task 72.
- These are observed counts, not a strategy failure conclusion.
- The latest checked candles did not qualify for entry in the audited replay.

## Limitations

- This report is generated from audited replay evidence, not from a live V11.30 API.
- It does not download or refresh market data.
- It does not read secrets, strategies, bot configs, or live SQLite content.
- It does not prove profitability or replacement readiness.

## Recommended Next Tasks

- Task 77: V11.30 post-refresh gate telemetry rerun after approved data maintenance
- Task 78: V11.30 live observation window with persisted gate telemetry
