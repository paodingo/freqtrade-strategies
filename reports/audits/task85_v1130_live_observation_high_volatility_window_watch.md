# Task 85: V11.30 Live Observation High-Volatility Window Watch

## Summary

Continued V11.30 live observation while waiting for the next actionable
high-volatility window.

Conclusion:

- V11.30 is still running;
- V11.30 DB still shows `trades = 0`, `orders = 0`, `open_trades = 0`;
- latest API-proxy analyzed candle advanced to `2026-07-08T08:45:00Z`;
- log tail shows heartbeat, whitelist refresh, and wallet sync;
- no order/trade/error event was observed in the checked tail;
- the latest candles still do not justify saying V11.30 should have traded.

## Server Evidence

- host: `43.134.72.69`
- user: `ubuntu`
- hostname: `VM-0-8-ubuntu`
- observed server date: `2026-07-08T17:04:38+08:00`

Containers:

| container | status | ports |
|---|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 6 hours` | none |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Resource snapshot:

| container | CPU | memory |
|---|---:|---:|
| `freqtrade-v1130-crash-rebound-shadow` | `0.00%` | `361.7MiB / 1.922GiB` |
| `freqtrade-v1129` | `0.15%` | `380.1MiB / 1.922GiB` |

## V11.30 DB Evidence

SQLite path:

```text
user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Metadata:

- size: `94208`
- mtime: `2026-07-08T10:54:45+0800`

Read-only counts:

| table/query | count |
|---|---:|
| `trades` | 0 |
| `orders` | 0 |
| `trades where is_open = 1` | 0 |

## Latest Analyzed Candle Proxy

| pair | last analyzed | last candle | return | range | RSI |
|---|---|---|---:|---:|---:|
| `ETH/USDT:USDT` | `2026-07-08T09:00:21.269654Z` | `2026-07-08T08:45:00Z` | 0.00115 | 0.00598 | 32.83 |
| `SOL/USDT:USDT` | `2026-07-08T09:00:24.496999Z` | `2026-07-08T08:45:00Z` | 0.00169 | 0.00790 | 22.96 |
| `DOGE/USDT:USDT` | `2026-07-08T09:00:30.684405Z` | `2026-07-08T08:45:00Z` | -0.00042 | 0.00744 | 23.02 |
| `LINK/USDT:USDT` | `2026-07-08T09:00:32.665094Z` | `2026-07-08T08:45:00Z` | -0.00013 | 0.00845 | 25.21 |
| `XRP/USDT:USDT` | `2026-07-08T09:00:28.726316Z` | `2026-07-08T08:45:00Z` | -0.00009 | 0.00657 | 25.00 |
| `BCH/USDT:USDT` | `2026-07-08T09:00:40.594664Z` | `2026-07-08T08:45:00Z` | -0.00068 | 0.01107 | 33.92 |

## Interpretation

The latest candles are not strict V11.30 candidates:

- returns are below the strict `0.004` requirement;
- several RSI values are below the `35` minimum;
- range is close to the loose watch threshold for `LINK` and `BCH`, but not
  enough to justify live action.

This supports continuing observation and adding watch telemetry rather than
immediately changing live thresholds.

## Log Findings

Observed:

- recurring `Bot heartbeat` with state `RUNNING`;
- whitelist refresh for six pairs;
- wallet sync.

Not observed:

- order placement;
- trade open/close;
- exception;
- traceback;
- stopped state.

## Non-Actions

This task did not:

- read secrets;
- stop, start, or restart bots;
- modify strategies;
- modify bot configs;
- run backtests;
- write SQLite.

## Recommended Next Task

Recommended next sequence:

```text
Task 86R: Allow exact loose-range replay report paths
Task 86: V11.30 loose-range replay report builder
Task 87: Decide whether to implement a watch-only telemetry lane
```
