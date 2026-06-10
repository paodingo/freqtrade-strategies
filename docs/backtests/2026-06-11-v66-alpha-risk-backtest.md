# V6.6 Alpha Risk Backtest

Date: 2026-06-11 Asia/Shanghai

## Scope

- Strategy baseline: `RegimeAwareV66`
- Audit strategy: `RegimeAwareV66AlphaRisk`
- Pair: `BTC/USDT:USDT`
- Timeframe: `15m`
- Config: `user_data/config_btc_futures_v66.json`
- Stake: `2500 USDT`
- Starting balance: `10000 USDT`
- Fee model: Freqtrade Binance futures backtest default in the configured container
- Alpha source: `user_data/monitor_history.sqlite`

Two windows were tested:

- Full alpha coverage window: `2026-06-04 00:00:00 UTC` to `2026-06-10 19:30:00 UTC`
- Wider 7-day window: `2026-06-03 00:00:00 UTC` to `2026-06-10 19:30:00 UTC`

The full coverage window is the main result because the historical alpha backfill starts after `2026-06-03 19:15:00 UTC`.

## Filter Modes

`directional`: Blocks only the side directly contradicted by alpha flags. For example, `takerSellPressure` blocks new shorts; `longCrowding` blocks new longs. `danger` blocks both sides.

`level`: Blocks all new entries when alpha risk level is `warning` or `danger`.

## Main Result: Full Alpha Coverage

| Variant | Trades | Profit USDT | Profit % | Final Balance | Winrate | Max DD USDT | Max DD % | Profit Factor | Long / Short |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V6.6 baseline | 50 | -66.916 | -0.669% | 9933.084 | 80.0% | 184.356 | 1.838% | 0.858 | 5 / 45 |
| Alpha directional | 36 | 37.727 | 0.377% | 10037.727 | 86.1% | 89.427 | 0.894% | 1.145 | 0 / 36 |
| Alpha level | 40 | 62.774 | 0.628% | 10062.774 | 87.5% | 89.427 | 0.894% | 1.242 | 4 / 36 |

Impact versus baseline:

- `directional`: `+104.643 USDT`, drawdown reduced by `94.929 USDT`.
- `level`: `+129.690 USDT`, drawdown reduced by `94.929 USDT`.

## Wider 7-Day Result

| Variant | Trades | Profit USDT | Profit % | Final Balance | Winrate | Max DD USDT | Max DD % | Profit Factor | Long / Short |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V6.6 baseline | 65 | 1.425 | 0.014% | 10001.425 | 83.1% | 184.356 | 1.826% | 1.003 | 5 / 60 |
| Alpha directional | 49 | 92.556 | 0.926% | 10092.556 | 87.8% | 107.764 | 1.070% | 1.297 | 0 / 49 |
| Alpha level | 53 | 117.603 | 1.176% | 10117.603 | 88.7% | 107.764 | 1.070% | 1.378 | 4 / 49 |

## Daily Breakdown: Full Coverage

| Day UTC | Baseline USDT | Directional USDT | Level USDT | Baseline Trades | Directional Trades | Level Trades |
|---|---:|---:|---:|---:|---:|---:|
| 2026-06-04 | -55.849 | -55.889 | -55.889 | 7 | 7 | 7 |
| 2026-06-05 | 54.787 | 91.128 | 91.128 | 22 | 14 | 14 |
| 2026-06-06 | -55.303 | -39.369 | -39.369 | 6 | 10 | 10 |
| 2026-06-07 | -99.362 | 3.700 | 3.700 | 3 | 1 | 1 |
| 2026-06-09 | 63.460 | 38.157 | 47.939 | 8 | 4 | 5 |
| 2026-06-10 | 25.350 | 0.000 | 15.265 | 4 | 0 | 3 |

## Tag Breakdown: Full Coverage

| Variant | Tag | Trades | Profit USDT | Winrate |
|---|---|---:|---:|---:|
| Baseline | `trending_short` | 45 | -102.049 | 80.0% |
| Baseline | `v66_ranging_long_edge` | 5 | 35.133 | 80.0% |
| Directional | `trending_short` | 36 | 37.727 | 86.1% |
| Level | `trending_short` | 36 | 37.727 | 86.1% |
| Level | `v66_ranging_long_edge` | 4 | 25.047 | 100.0% |

## Exit Breakdown: Full Coverage

| Variant | Exit | Trades | Profit USDT | Winrate |
|---|---|---:|---:|---:|
| Baseline | `roi` | 38 | 390.994 | 100.0% |
| Baseline | `stop_loss` | 9 | -466.496 | 0.0% |
| Baseline | `v66_ranging_time_stop` | 1 | -6.277 | 0.0% |
| Directional | `roi` | 31 | 297.220 | 100.0% |
| Directional | `stop_loss` | 5 | -259.493 | 0.0% |
| Level | `roi` | 34 | 320.685 | 100.0% |
| Level | `stop_loss` | 5 | -259.493 | 0.0% |

## Trade Replacement Notes

Because `max_open_trades = 1`, filtering a trade can free the slot and allow another trade later. The effect is therefore not equal to simply deleting blocked trades from the baseline trade list.

Directional mode versus baseline:

- Removed baseline trades: `35`, combined baseline profit `-44.076 USDT`.
- Added replacement trades: `21`, combined profit `60.568 USDT`.
- Common trades retained: `15`, combined profit `-22.840 USDT`.

Level mode versus baseline:

- Removed baseline trades: `33`, combined baseline profit `-63.858 USDT`.
- Added replacement trades: `23`, combined profit `65.833 USDT`.
- Common trades retained: `17`, combined profit `-3.058 USDT`.

Largest removed baseline losses:

| Open UTC | Side | Tag | Exit | Profit USDT | Profit % | Duration |
|---|---|---|---|---:|---:|---:|
| 2026-06-05 03:15 | short | `trending_short` | `stop_loss` | -52.391 | -2.102% | 90m |
| 2026-06-06 10:45 | short | `trending_short` | `stop_loss` | -52.087 | -2.105% | 870m |
| 2026-06-05 06:30 | short | `trending_short` | `stop_loss` | -51.786 | -2.102% | 60m |
| 2026-06-07 19:30 | short | `trending_short` | `stop_loss` | -51.630 | -2.102% | 150m |
| 2026-06-05 19:45 | short | `trending_short` | `stop_loss` | -51.435 | -2.102% | 15m |
| 2026-06-07 02:30 | short | `trending_short` | `stop_loss` | -51.427 | -2.102% | 345m |
| 2026-06-10 02:30 | long | `v66_ranging_long_edge` | `v66_ranging_time_stop` | -6.277 | -0.255% | 255m |

Best added replacement trades:

| Open UTC | Side | Tag | Exit | Profit USDT | Profit % | Duration |
|---|---|---|---|---:|---:|---:|
| 2026-06-09 14:00 | short | `trending_short` | `roi` | 14.928 | 0.600% | 15m |
| 2026-06-05 06:15 | short | `trending_short` | `roi` | 14.880 | 0.600% | 0m |
| 2026-06-05 07:00 | short | `trending_short` | `roi` | 14.849 | 0.600% | 0m |
| 2026-06-06 04:30 | short | `trending_short` | `roi` | 14.731 | 0.600% | 0m |
| 2026-06-05 11:00 | short | `trending_short` | `roi` | 9.995 | 0.400% | 30m |
| 2026-06-06 03:15 | short | `trending_short` | `roi` | 9.972 | 0.400% | 45m |
| 2026-06-04 19:00 | short | `trending_short` | `roi` | 9.945 | 0.400% | 60m |

## Conclusion

The alpha-risk layer improved V6.6 materially in this sample. The stronger result is `level` mode, which turned `-66.916 USDT` into `+62.774 USDT` on the full alpha coverage window and cut max drawdown from `184.356 USDT` to `89.427 USDT`.

This is still a short historical sample. The next step should be to keep V6.5 as the live benchmark and run V6.6 Alpha in observation/backtest mode until we have more out-of-sample evidence.
