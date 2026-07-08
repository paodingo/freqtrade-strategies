# Task 67: V11.30 Live Candle Data Freshness Audit

## Summary

V11.30 runtime was checked read-only on the server to distinguish stale local
data files from the live analyzed data used by the running system.

Conclusion:

- V11.30 container was running.
- Server-side local feather files under `user_data/data/futures` were stale
  with mtimes from `2026-07-03`.
- Fresh analyzed candles were available through the running Freqtrade API data
  source used as a read-only proxy, with latest 15m candle at
  `2026-07-08T03:00:00Z` and `last_analyzed` around
  `2026-07-08T03:15:34Z` to `2026-07-08T03:15:53Z`.
- This task did not download data, modify data, restart bots, or read secrets.

## Server Evidence

- host: `43.134.72.69`
- user: `ubuntu`
- server date observed: `2026-07-08T11:16:13+08:00`
- running containers observed:
  - `freqtrade-v1130-crash-rebound-shadow`
  - `freqtrade-v1129`

Resource snapshot:

- memory total: `1.9Gi`
- memory used: `1.6Gi`
- memory available: `337Mi`
- swap used: `2.5Gi` of `5.9Gi`
- V11.30 container memory: about `116MiB`
- V11.29 container memory: about `374.9MiB`

## V11.30 SQLite Evidence

Observed path:

```text
user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Observed file state:

- size: `94208` bytes
- mtime: `2026-07-08 10:54:45 +0800`

The DB existed, but this task did not inspect or write SQLite contents.

## Local Feather Freshness

The checked futures data files for V11.30 pairs had mtimes from
`2026-07-03 17:01 CST`.

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

Interpretation:

- local feather files are stale;
- this does not by itself prove the running bot uses stale candles, because the
  running Freqtrade instance can maintain analyzed data independently.

## Runtime Analyzed Candle Freshness

Read-only API proxy checks returned fresh analyzed data for the V11.30 pair
set.

Each pair returned:

- rows: `5`
- latest candle: `2026-07-08T03:00:00Z`
- last analyzed: around `2026-07-08T03:15:34Z` to
  `2026-07-08T03:15:53Z`

Conclusion:

- live analyzed candle data was fresh at the time of observation;
- stale local feather mtimes should be treated as a data-maintenance gap, not
  immediate proof that the live bot was blind.

## Non-Actions

This task did not:

- read `.env` or `user_data/monitor.env`;
- read API keys, exchange credentials, server keys, or dashboard passwords;
- start, stop, or restart any bot;
- run backtests;
- modify strategies or bot configs;
- modify the original dirty workspace.

## Recommended Next Task

Proceed with:

```text
Task 68: V11.30 Live Gate Replay On Latest Candles
```

Purpose:

- replay the V11.30 gate logic on the fresh analyzed candle proxy;
- determine whether the latest candles actually satisfied entry conditions.
