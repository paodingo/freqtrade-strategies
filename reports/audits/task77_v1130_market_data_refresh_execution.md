# Task 77: V11.30 Market Data Refresh Execution

## Summary

Executed the previously approved V11.30 market data refresh command on the
server. The command completed with exit code `0`, and target feather file mtimes
changed to `2026-07-08 14:30` server time.

Important conclusion:

- file mtimes changed, but the actual latest candle inside the checked futures
  feather files remained `2026-07-03`;
- this refresh did not close the stale local feather content gap;
- V11.30 and V11.29 containers stayed running;
- V11.30 SQLite still had `trades = 0` and `orders = 0`.

## Server Evidence

- host: `43.134.72.69`
- user: `ubuntu`
- hostname: `VM-0-8-ubuntu`
- start time: `2026-07-08T14:30:20+08:00`
- post-check time: `2026-07-08T14:31:07+08:00`

Containers before and after:

| container | status |
|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 4 hours` |
| `freqtrade-v1129` | `Up 4 days` |

No bot was stopped, started, or restarted.

## Command Executed

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --datadir /freqtrade/project/user_data/data \
  --trading-mode futures \
  --timeframes 15m 4h \
  --pairs ETH/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT XRP/USDT:USDT BCH/USDT:USDT \
  --data-format-ohlcv feather \
  --prepend
```

Result:

```text
REFRESH_EXIT=0
```

## File Mtime Result

Before refresh, target files had mtimes around:

```text
2026-07-03 17:01 +0800
```

After refresh, target files had mtimes around:

```text
2026-07-08 14:30 +0800
```

Checked pairs:

- `ETH/USDT:USDT`
- `SOL/USDT:USDT`
- `DOGE/USDT:USDT`
- `LINK/USDT:USDT`
- `XRP/USDT:USDT`
- `BCH/USDT:USDT`

Checked timeframes:

- `15m`
- `4h`

## Feather Content Result

Read-only container-side feather inspection showed the latest candle inside the
files did not advance:

| timeframe | rows per pair | first candle | latest candle |
|---|---:|---|---|
| `15m` | `87779` | `2024-01-01 00:00:00+00:00` | `2026-07-03 08:30:00+00:00` |
| `4h` | `5485` | `2024-01-01 00:00:00+00:00` | `2026-07-03 00:00:00+00:00` |

The same latest-candle result was observed for all six checked pairs.

Interpretation:

- `--prepend` appears to have rewritten/checked the files but did not append the
  missing July 3 to July 8 window;
- local feather content is still stale;
- a later correction task should try an append-oriented command without
  `--prepend`, or use a bounded `--timerange` if needed.

## V11.30 SQLite After Refresh

Read-only counts after refresh:

| table/query | observed count |
|---|---:|
| `trades` | 0 |
| `orders` | 0 |
| `trades where is_open = 1` | 0 |

These are observed counts only. They are not a strategy failure conclusion.

## Non-Actions

This task did not:

- read `.env` or `user_data/monitor.env`;
- print API keys, exchange credentials, dashboard passwords, or tokens;
- stop, start, or restart bots;
- modify strategy code;
- modify bot configs;
- run backtests;
- commit server `user_data/data/**`.

## Recommended Next Task

Proceed with:

```text
Task 78: V11.30 Gate Telemetry Rerun After Refresh
Task 80: Correct V11.30 data refresh command if local feather freshness remains required
```
