# Task 31: V11.29 Safe Runtime Data Freshness Probe

## Summary

This task used read-only server/API probes to determine whether V11.29 is receiving fresh runtime candle data.

Conclusion:

- The local downloaded/fallback futures feather files are stale, as documented in Task 28 and Task 30.
- The running V11.29 bot does have API-readable runtime `15m` strategy data for all 12 whitelist pairs on `2026-07-06`.
- The runtime `15m` dataframe includes informative `4h` context columns such as `date_4h`, `regime_4h`, `trend_4h_up`, `trend_4h_down`, and V11 gate columns.
- Therefore the current zero-trade condition is not explained by "no runtime candle data at all".
- In the observed 24h window, all 12 pairs had `enter_long_signals=0` and `enter_short_signals=0`.
- Some rows had non-empty `enter_tag` values, but final `enter_long` and `enter_short` stayed `0`, so tags alone did not become tradable entries.

This task did not modify strategies, bot configs, dashboard, deploy scripts, secrets, SQLite files, or server runtime state. It did not start, stop, or restart any bot.

## Scope And Safety

Server:

```text
host=43.134.72.69
user=ubuntu
```

Allowed read-only actions performed:

- SSH login.
- `hostname`.
- `date -Is`.
- `docker ps --format ...`.
- local Freqtrade API GET requests on `localhost:8122`.
- JSON summary parsing of `/api/v1/pair_candles`.

Forbidden actions not performed:

- no `docker inspect`;
- no `.env` read;
- no `user_data/monitor.env` read;
- no secret printing;
- no `docker start` / `docker stop` / `docker restart`;
- no `freqtrade trade`;
- no backtest;
- no SQLite write;
- no strategy/config/dashboard/deploy modification.

## Server Evidence

Observation time:

```text
server date: 2026-07-06T14:51:41+08:00
runtime probe UTC: 2026-07-06T06:52:44Z to 2026-07-06T06:53:48Z
hostname: VM-0-8-ubuntu
```

Containers:

```text
freqtrade-v1129 Up 2 days 127.0.0.1:8122->8122/tcp
freqtrade-v1082 Up 6 days 127.0.0.1:8091->8091/tcp
```

V11.29 API probes:

| Endpoint | HTTP | Notes |
| --- | ---: | --- |
| `ping` | 200 | readable |
| `show_config` | 200 | readable; full config not printed |
| `count` | 200 | readable |
| `profit` | 200 | readable |
| `status` | 200 | readable |
| `locks` | 200 | readable |
| `whitelist` | 200 | readable |
| `pair_candles?pair=BTC/USDT:USDT&timeframe=15m&limit=3` | 200 | runtime strategy dataframe available |
| `pair_candles/.../15m` path form | 404 | unsupported route |
| `candles?...` | 404 | unsupported route |
| `available_pairs?timeframe=15m` | 503 | not usable in current bot state |

## Runtime Candle Evidence

The API endpoint below was the useful read-only source:

```text
http://localhost:8122/api/v1/pair_candles?pair=<pair>&timeframe=15m&limit=<n>
```

For `BTC/USDT:USDT`, the response contained:

```text
strategy=RegimeAwareV1129ResidualDragMicroSizer
pair=BTC/USDT:USDT
timeframe=15m
columns=86
all_columns=82
```

Important dataframe columns included:

```text
date
open/high/low/close/volume
date_4h
open_4h/high_4h/low_4h/close_4h/volume_4h
adx_4h
regime_4h
trend_4h_up
trend_4h_down
enter_tag
enter_long
enter_short
v115_quality_gate
v1113_micro_rebound_gate
v1115_selloff_gate
v1116_alt_recovery_gate
v1118_volatility_shock_gate
v1122_ada_capitulation_gate
v1124_rebound_sizer_gate
v1127_dual_trap_gate
v1129_residual_drag_gate
```

BTC last-row example:

```text
last_15m=2026-07-06T06:30:00Z
date_4h=2026-07-06T00:00:00Z
enter_long=0
enter_short=0
enter_tag=""
v1129_residual_drag_gate=pass
```

Interpretation:

- Runtime `15m` data is available and current-day, not stuck at the stale local feather timestamp from `2026-07-03`.
- Runtime `4h` context is present inside the `15m` strategy dataframe.
- Direct `timeframe=4h` `pair_candles` requests returned `length=0`, so standalone `4h` dataframe is not the proof source.
- The `4h` proof source is the informative columns embedded into the analyzed `15m` dataframe.

## Pair Freshness Matrix

24h read-only probe:

```text
timeframe=15m
limit=96
observed_at_utc=2026-07-06T06:53:27Z
```

| Pair | Rows | Data start | Data stop | Last analyzed | Last 15m | Last 4h context | enter_long rows | enter_short rows | nonempty enter_tag rows |
| --- | ---: | --- | --- | --- | --- | --- | ---: | ---: | ---: |
| BTC/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:32Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 30 |
| ETH/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:34Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 43 |
| SOL/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:20Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 1 |
| BNB/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:36Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 49 |
| XRP/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:28Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 41 |
| DOGE/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:38Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 32 |
| ADA/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:40Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 38 |
| LINK/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:42Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 35 |
| AVAX/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:44Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 1 |
| LTC/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:46Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 45 |
| TRX/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:48Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 51 |
| BCH/USDT:USDT | 96 | 2026-07-05 06:45Z | 2026-07-06 06:30Z | 2026-07-06 06:45:50Z | 2026-07-06 06:30Z | 2026-07-06 00:00Z | 0 | 0 | 48 |

## Signal Findings

Observed over the 24h `15m` window:

```text
enter_long_signals_api=0 for all 12 pairs
enter_short_signals_api=0 for all 12 pairs
enter_long_rows=0 for all 12 pairs
enter_short_rows=0 for all 12 pairs
```

At the same time, non-empty `enter_tag` rows existed for many pairs:

```text
BTC 30
ETH 43
SOL 1
BNB 49
XRP 41
DOGE 32
ADA 38
LINK 35
AVAX 1
LTC 45
TRX 51
BCH 48
```

Interpretation:

- The strategy dataframe is being produced.
- The strategy is assigning tag-like intermediate labels on many rows.
- Final tradable `enter_long` / `enter_short` remained `0` in the observed 24h window.
- This points the next investigation toward entry-condition semantics, final signal assignment, gate ordering, or intentional clearing of entries.

This does not prove strategy failure and does not prove V11.29 can or cannot replace V10.8.2.

## Data Freshness Answer

The answer is now more precise:

```text
Local downloaded/fallback data is not real-time updated.
The running V11.29 runtime API does have current-day analyzed 15m data and embedded 4h context.
```

So the system does have runtime data, but the local cached/downloaded data artifacts are stale. The zero-trade condition should no longer be framed as simply "no real-time data"; it should be framed as:

```text
V11.29 runtime data is available, but final entry signals are zero in the observed window.
```

## Remaining Unknowns

- Whether a longer window than 24h contains V11.29 `enter_long` or `enter_short`.
- Whether non-empty `enter_tag` values are intentionally diagnostic labels or should have become entries.
- Which exact strategy layer sets tags while leaving final entries at `0`.
- Whether custom stake sizing would allow an order if final entries appeared.
- Whether the 15m one-candle lag observed at `06:53Z` is normal exchange/dataframe timing or a recurring refresh delay.
- Whether V10.8.2 has materially different same-window signal behavior.

## Recommended Task 32

Recommended next task:

```text
Task 32: V11.29 Entry Signal Semantics Audit
```

Scope:

- Read-only inspect V11.29 strategy inheritance and signal assignment order.
- Explain how `enter_tag` can be non-empty while `enter_long` / `enter_short` remain `0`.
- Compare V11.29 final entry assignment with V10.8.2 or another known-trading baseline.
- Do not modify strategy or bot config.
- Do not run backtests.
- Do not restart bots.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read or print `user_data/monitor.env`;
- print API key, exchange credentials, server keys, dashboard password, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- copy SQLite;
- modify original dirty workspace.
