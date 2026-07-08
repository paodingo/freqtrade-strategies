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
- generated at: `2026-07-08T09:25:34.121Z`
- input generated at: `2026-07-08T09:24:48Z`
- source: `server_read_only_feather_ohlcv_snapshot`
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
| strict candidates | 12 |
| strict enabled | 12 |
| strict blocked | 0 |
| watch candidates | 32 |
| watch enabled | 32 |
| watch blocked | 0 |
| watch-only enabled | 20 |
| not candidate | 1408 |

## Latest Rows

| pair | candle time | strict gate | watch gate | watch enabled | strict failed | watch failed |
|---|---|---|---|---|---|---|
| `ETH/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `false` | `return, range, volume` | `return, range, volume` |
| `SOL/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `false` | `return, range, rsi` | `return, range, rsi` |
| `DOGE/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `false` | `return, range, rsi` | `return, rsi` |
| `LINK/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `false` | `return, range, rsi` | `return, range, rsi` |
| `XRP/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `false` | `return, range, rsi` | `return, range, rsi` |
| `BCH/USDT:USDT` | `2026-07-08T06:15:00Z` | `not_candidate` | `not_candidate` | `false` | `return, range, volume` | `return, range, volume` |

## Watch Enabled By Pair

| pair | count |
|---|---:|
| `ETH/USDT:USDT` | 4 |
| `SOL/USDT:USDT` | 3 |
| `DOGE/USDT:USDT` | 7 |
| `LINK/USDT:USDT` | 5 |
| `XRP/USDT:USDT` | 2 |
| `BCH/USDT:USDT` | 11 |

## Watch Enabled By Day

| day | count |
|---|---:|
| `2026-07-06` | 17 |
| `2026-07-07` | 10 |
| `2026-07-05` | 3 |
| `2026-07-08` | 2 |

## Watch-Only Examples

- `ETH/USDT:USDT` `2026-07-06T00:30:00Z` range=`0.008570287045530011` return=`0.005846702718519836`
- `ETH/USDT:USDT` `2026-07-06T13:30:00Z` range=`0.009500913771136373` return=`0.005373089584162161`
- `ETH/USDT:USDT` `2026-07-06T15:00:00Z` range=`0.008765968625256217` return=`0.006613023887978464`
- `SOL/USDT:USDT` `2026-07-06T00:30:00Z` range=`0.009974141115626183` return=`0.0077576653121538275`
- `DOGE/USDT:USDT` `2026-07-06T00:30:00Z` range=`0.009186181912278282` return=`0.005563462284901011`
- `DOGE/USDT:USDT` `2026-07-06T16:30:00Z` range=`0.008646665793266003` return=`0.00786060526660548`
- `DOGE/USDT:USDT` `2026-07-07T12:00:00Z` range=`0.009362043600374565` return=`0.006553430520261916`
- `DOGE/USDT:USDT` `2026-07-07T14:45:00Z` range=`0.010926750303520723` return=`0.008903278025091055`
- `DOGE/USDT:USDT` `2026-07-07T16:15:00Z` range=`0.009348290598290681` return=`0.006543803418803451`
- `LINK/USDT:USDT` `2026-07-06T13:30:00Z` range=`0.009397528321318165` return=`0.006694129763130885`
- `LINK/USDT:USDT` `2026-07-06T14:15:00Z` range=`0.01199132542416117` return=`0.00471998979461663`
- `LINK/USDT:USDT` `2026-07-06T15:00:00Z` range=`0.008021390374331628` return=`0.005984211866564726`
- `LINK/USDT:USDT` `2026-07-06T15:30:00Z` range=`0.011638203668564266` return=`0.0072106261859581355`
- `XRP/USDT:USDT` `2026-07-06T15:30:00Z` range=`0.009467350911343065` return=`0.00477791541320105`
- `BCH/USDT:USDT` `2026-07-05T19:00:00Z` range=`0.011373505934902188` return=`0.008892013730923631`
- `BCH/USDT:USDT` `2026-07-06T06:30:00Z` range=`0.008219635331914712` return=`0.004673092168398174`
- `BCH/USDT:USDT` `2026-07-07T05:30:00Z` range=`0.008745135779739751` return=`0.0058579856897778`
- `BCH/USDT:USDT` `2026-07-07T15:00:00Z` range=`0.009885297184567276` return=`0.004963503649634937`
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
