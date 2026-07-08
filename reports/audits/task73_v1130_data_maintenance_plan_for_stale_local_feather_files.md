# Task 73: V11.30 Data Maintenance Plan For Stale Local Feather Files

## Summary

Task 67 found stale server-side local futures feather files under
`user_data/data/futures`. This task defines a safe maintenance plan only. It
does not download data, modify data files, restart bots, or change configs.

Conclusion:

- stale local feather files are a real maintenance gap;
- live runtime analyzed candles were fresh in Task 67, so stale feather files
  are not by themselves proof that V11.30 is blind;
- the existing `scripts/refresh_data.sh` is not safe to use directly for
  V11.30 because it is hard-coded to an older V6.5 config;
- data refresh should be handled as a separate task with exact commands,
  dry-run checks, and rollback-free boundaries.

## Evidence Reviewed

Task 67 observed stale local files:

- pair set:
  - `ETH/USDT:USDT`
  - `SOL/USDT:USDT`
  - `DOGE/USDT:USDT`
  - `LINK/USDT:USDT`
  - `XRP/USDT:USDT`
  - `BCH/USDT:USDT`
- timeframes:
  - `15m`
  - `4h`
- local feather mtime: around `2026-07-03 17:01 CST`

Task 67 also observed fresh runtime analyzed candles:

- latest candle: `2026-07-08T03:00:00Z`
- last analyzed: around `2026-07-08T03:15:34Z` to
  `2026-07-08T03:15:53Z`

## Current Refresh Script Risk

Existing script:

```text
scripts/refresh_data.sh
```

Observed concerns:

- the script comment says market data refresh plus bot health check;
- it is cron-oriented;
- it is hard-coded to:

```text
CONFIG="/freqtrade/project/user_data/config_btc_futures_v65.json"
DATADIR="/freqtrade/project/user_data/data"
```

Therefore it should not be used for V11.30 without a dedicated review and
patch task.

## Maintenance Goals

The maintenance flow should:

1. update only market OHLCV data files;
2. use the V11.30 pair universe explicitly;
3. cover `15m` and `4h`;
4. avoid bot start/stop/restart;
5. avoid reading secrets;
6. avoid modifying strategy or bot config;
7. capture pre/post file mtimes and latest candle timestamps;
8. keep generated data out of Git.

## Candidate Read-Only Preflight Commands

These commands are safe as a preflight only:

```bash
cd /home/ubuntu/freqtrade-strategies
hostname
date -Iseconds
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'freqtrade-v1130|freqtrade-v1129' || true
ls -lh user_data/data/futures/*-15m-futures.feather user_data/data/futures/*-4h-futures.feather 2>/dev/null
```

Optional read-only latest-candle inspection:

```bash
python3 - <<'PY'
import glob
import pandas as pd
for p in sorted(glob.glob("user_data/data/futures/*-15m-futures.feather")):
    df = pd.read_feather(p)
    print(p, df["date"].iloc[-1] if "date" in df else "missing_date")
PY
```

## Future Data Refresh Command Draft

The exact command must be verified in a separate implementation task before
execution. Draft shape:

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --datadir /freqtrade/project/user_data/data \
  --trading-mode futures \
  --timeframes 15m 4h \
  --pairs ETH/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT XRP/USDT:USDT BCH/USDT:USDT
```

This is a draft only. Do not execute it until a task explicitly authorizes data
download/update.

## Required Safety Checks For Future Task

Before any refresh:

- confirm the command does not start or restart trading;
- confirm it only writes market data under `user_data/data`;
- record current mtime and latest candle per pair/timeframe;
- confirm enough disk space;
- confirm bot containers remain running;
- confirm no `.env` or `monitor.env` is read or printed.

After refresh:

- record new mtime and latest candle per pair/timeframe;
- confirm V11.30 container is still running;
- confirm V11.30 SQLite was not written by the refresh except normal bot
  runtime activity;
- run readiness in clean worktree;
- keep refreshed feather files ignored and uncommitted.

## Forbidden Actions

Do not:

- use the current `scripts/refresh_data.sh` directly for V11.30;
- stop, start, or restart bots during data refresh;
- modify V11.30 strategy or config;
- read secrets;
- commit `user_data/data/**`;
- run backtests as part of refresh;
- claim that refresh proves profitability.

## Recommended Next Task

Recommended implementation task:

```text
Task 75: V11.30 Safe Market Data Refresh Dry-Run And Exact Command Approval
```

Only after Task 75 should a data refresh be executed.
