# Task 80: V11.30 Data Refresh Command Correction

## Summary

Corrected the V11.30 market data refresh command by removing `--prepend`.

Task 77 proved that `--prepend` rewrote/checkpointed files but did not append
the missing July 3 to July 8 data. The corrected append-oriented command
successfully advanced the local futures feather files.

Conclusion:

- corrected command exited with `0`;
- all six checked pairs now have `15m` futures feather latest candle
  `2026-07-08 06:15:00+00:00`;
- all six checked pairs now have `4h` futures feather latest candle
  `2026-07-08 00:00:00+00:00`;
- V11.30 and V11.29 containers remained running;
- V11.30 SQLite still showed `trades = 0`, `orders = 0`, `open_trades = 0`;
- no bot was stopped, started, or restarted.

## Server Evidence

- host: `43.134.72.69`
- user: `ubuntu`
- hostname: `VM-0-8-ubuntu`
- start time: `2026-07-08T14:41:30+08:00`
- post time: `2026-07-08T14:41:44+08:00`

Containers:

| container | status |
|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 4 hours` |
| `freqtrade-v1129` | `Up 4 days` |

## Corrected Command

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --datadir /freqtrade/project/user_data/data \
  --trading-mode futures \
  --timeframes 15m 4h \
  --pairs ETH/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT XRP/USDT:USDT BCH/USDT:USDT \
  --data-format-ohlcv feather
```

Result:

```text
REFRESH_EXIT=0
```

Important difference from Task 77:

- `--prepend` was removed.
- No `--erase` was used.

## Pre-Refresh Content

Before the corrected command:

| timeframe | rows per pair | latest candle |
|---|---:|---|
| `15m` | `87779` | `2026-07-03 08:30:00+00:00` |
| `4h` | `5485` | `2026-07-03 00:00:00+00:00` |

## Post-Refresh Content

After the corrected command:

| timeframe | rows per pair | first candle | latest candle |
|---|---:|---|---|
| `15m` | `88250` | `2024-01-01 00:00:00+00:00` | `2026-07-08 06:15:00+00:00` |
| `4h` | `5515` | `2024-01-01 00:00:00+00:00` | `2026-07-08 00:00:00+00:00` |

The same row counts and latest timestamps were observed for:

- `ETH/USDT:USDT`
- `SOL/USDT:USDT`
- `DOGE/USDT:USDT`
- `LINK/USDT:USDT`
- `XRP/USDT:USDT`
- `BCH/USDT:USDT`

## V11.30 SQLite After Correction

Read-only counts:

| table/query | observed count |
|---|---:|
| `trades` | 0 |
| `orders` | 0 |
| `trades where is_open = 1` | 0 |

This remains insufficient live execution evidence. It is not a strategy failure
conclusion.

## Interpretation

The previous `--prepend` option was the likely reason the refresh failed to
append the missing current window. Removing it fixed the local feather freshness
gap.

This does not mean:

- V11.30 should have traded;
- V11.30 is profitable;
- V11.30 can replace any benchmark.

## Non-Actions

This task did not:

- use `--erase`;
- read `.env` or `user_data/monitor.env`;
- print API keys, exchange credentials, dashboard passwords, or tokens;
- stop, start, or restart bots;
- modify strategies;
- modify bot configs;
- run backtests;
- commit server `user_data/data/**`.

## Recommended Next Task

Proceed with:

```text
Task 81: V11.30 range-threshold offline return study
```
