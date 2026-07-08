# V11.30 Watch-Only Telemetry Report

## Summary

This report records V11.30 strict-gate versus loose-range watch-only telemetry.

It is not a trading signal implementation and cannot place orders.

Here, `enabled` means the read-only input passed the OHLCV gate conditions in
the telemetry model. Alpha/taker filters are `ohlcv_only_alpha_unknown`,
so this must not be interpreted as a live `enter_long` signal.

## Metadata

- strategy: `RegimeAwareV1130CrashReboundShadow`
- version: `V11.30`
- generated at: `2026-07-08T11:53:52.575Z`
- input generated at: `2026-07-08T11:53:41Z`
- source: `server_read_only_feather_ohlcv_snapshot_after_task94v_timer`
- timeframe: `15m`
- can place orders: `false`
- modifies strategy: `false`
- modifies bot config: `false`
- reads secret: `false`

## Window Summary

| metric | value |
|---|---:|
| rows | 1440 |
| filter scope | ohlcv_only_alpha_unknown |
| strict candidates | 10 |
| strict enabled | 10 |
| strict blocked | 0 |
| watch candidates | 29 |
| watch enabled | 29 |
| watch blocked | 0 |
| watch-only enabled | 19 |
| not candidate | 1411 |

## Latest Rows

| pair | candle time | strict gate | watch gate | watch enabled | strict failed | watch failed |
|---|---|---|---|---|---|---|
| `ETH/USDT:USDT` | `2026-07-08T11:30:00Z` | `not_candidate` | `not_candidate` | `false` | `range` | `range` |
| `SOL/USDT:USDT` | `2026-07-08T11:30:00Z` | `not_candidate` | `v1130_loose_range_watch` | `true` | `range` | `` |
| `DOGE/USDT:USDT` | `2026-07-08T11:30:00Z` | `not_candidate` | `not_candidate` | `false` | `range` | `range` |
| `LINK/USDT:USDT` | `2026-07-08T11:30:00Z` | `not_candidate` | `v1130_loose_range_watch` | `true` | `range` | `` |
| `XRP/USDT:USDT` | `2026-07-08T11:30:00Z` | `not_candidate` | `not_candidate` | `false` | `range` | `range` |
| `BCH/USDT:USDT` | `2026-07-08T11:30:00Z` | `not_candidate` | `not_candidate` | `false` | `range, rsi, volume` | `rsi, volume` |

## Watch Enabled By Pair

| pair | count |
|---|---:|
| `ETH/USDT:USDT` | 4 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 5 |
| `LINK/USDT:USDT` | 4 |
| `XRP/USDT:USDT` | 3 |
| `BCH/USDT:USDT` | 10 |

## Watch Enabled By Day

| day | count |
|---|---:|
| `2026-07-06` | 12 |
| `2026-07-07` | 12 |
| `2026-07-08` | 5 |

## Watch-Only Examples

- `ETH/USDT:USDT` `2026-07-06T00:30:00Z` range=`0.008570287045530011` return=`0.005846702718519836`
- `ETH/USDT:USDT` `2026-07-06T15:00:00Z` range=`0.008765968625256217` return=`0.006613023887978464`
- `ETH/USDT:USDT` `2026-07-07T00:15:00Z` range=`0.00885251192112298` return=`0.004367832720352904`
- `SOL/USDT:USDT` `2026-07-08T11:30:00Z` range=`0.008039419087136988` return=`0.005057053941908807`
- `DOGE/USDT:USDT` `2026-07-06T00:30:00Z` range=`0.009186181912278282` return=`0.005563462284901011`
- `DOGE/USDT:USDT` `2026-07-07T12:00:00Z` range=`0.009362043600374565` return=`0.006553430520261916`
- `DOGE/USDT:USDT` `2026-07-07T14:45:00Z` range=`0.010926750303520723` return=`0.008903278025091055`
- `DOGE/USDT:USDT` `2026-07-07T16:15:00Z` range=`0.009348290598290681` return=`0.006543803418803451`
- `LINK/USDT:USDT` `2026-07-06T13:30:00Z` range=`0.009397528321318165` return=`0.006694129763130885`
- `LINK/USDT:USDT` `2026-07-06T14:15:00Z` range=`0.01199132542416117` return=`0.00471998979461663`
- `LINK/USDT:USDT` `2026-07-08T11:30:00Z` range=`0.00802948532315387` return=`0.004738712649730026`
- `XRP/USDT:USDT` `2026-07-06T15:30:00Z` range=`0.009467350911343065` return=`0.00477791541320105`
- `BCH/USDT:USDT` `2026-07-06T14:15:00Z` range=`0.011251639101560833` return=`0.005414322575187258`
- `BCH/USDT:USDT` `2026-07-07T05:30:00Z` range=`0.008745135779739751` return=`0.0058579856897778`
- `BCH/USDT:USDT` `2026-07-07T15:00:00Z` range=`0.009885297184567276` return=`0.004963503649634937`
- `BCH/USDT:USDT` `2026-07-07T16:15:00Z` range=`0.008747201724566842` return=`0.006674405107370829`
- `BCH/USDT:USDT` `2026-07-08T00:30:00Z` range=`0.00907570054370563` return=`0.00677540777917196`
- `BCH/USDT:USDT` `2026-07-08T02:30:00Z` range=`0.009923888818804866` return=`0.004373239140490259`
- `BCH/USDT:USDT` `2026-07-08T04:00:00Z` range=`0.010401691331923923` return=`0.0064270613107821895`

## Runtime Evidence

- V11.30 trades: `0` (`observed`)
- V11.30 orders: `0` (`observed`)
- V11.30 open trades: `0` (`observed`)

## Limitations

- Watch-only telemetry does not set enter_long and cannot place orders.
- This report does not modify the live V11.30 strategy or bot config.
- This report does not prove profitability, fill quality, fees, funding, slippage, or latency.
- Observed zero trades/orders must not be interpreted as strategy failure without separate cause investigation.
- This report does not conclude whether V11.30 can replace V10.8.2.

## Recommendation

- status: `continue_watch_only_observation`
- next task: Task 89: V11.30 live observation strict-vs-watch-only comparison
