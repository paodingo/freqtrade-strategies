# Task 75: V11.30 Safe Market Data Refresh Dry-Run And Exact Command Approval

## Summary

Prepared an exact, safety-bounded V11.30 market data refresh command for a
future task. This task did not download data and did not modify server files.

Conclusion:

- V11.30 container is running.
- V11.30 config path exists on the server.
- `freqtrade download-data --help` is available inside the V11.30 container.
- There is enough disk space for a small OHLCV refresh.
- The refresh command should be executed only in a later explicitly authorized
  task.

## Server Evidence

- host: `43.134.72.69`
- user: `ubuntu`
- hostname: `VM-0-8-ubuntu`
- server date observed: `2026-07-08T14:04:24+08:00`

Observed containers:

| container | status |
|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 3 hours` |
| `freqtrade-v1129` | `Up 4 days` |

Checked paths:

| path | result |
|---|---|
| `user_data/config_multi_futures_v1130_crash_rebound_shadow.json` | regular file, 1062 bytes |
| `user_data/data` | directory |

Storage:

- `user_data/data`: `39M`
- filesystem available: `22G`

## Download Command Capability

Read-only help check:

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data --help
```

Relevant supported options observed:

- `--config`
- `--datadir`
- `--pairs`
- `--timeframes`
- `--trading-mode`
- `--data-format-ohlcv`
- `--prepend`

No data download command was executed.

## Approved Future Command Draft

This command is approved as a draft for a later task only. It must not be run
until the user explicitly authorizes data refresh.

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

## Required Pre/Post Checks For Execution Task

Before running the refresh:

```bash
cd /home/ubuntu/freqtrade-strategies
date -Iseconds
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'freqtrade-v1130|freqtrade-v1129'
ls -lh user_data/data/futures/*-15m-futures.feather user_data/data/futures/*-4h-futures.feather 2>/dev/null
df -h .
```

After running the refresh:

```bash
date -Iseconds
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'freqtrade-v1130|freqtrade-v1129'
ls -lh user_data/data/futures/*-15m-futures.feather user_data/data/futures/*-4h-futures.feather 2>/dev/null
```

The execution task should also inspect latest candle timestamps in read-only
mode after the refresh.

## Forbidden Actions

Do not:

- use `scripts/refresh_data.sh` directly;
- run `--erase`;
- stop, start, or restart bots;
- read `.env` or `user_data/monitor.env`;
- read or print API keys, exchange credentials, dashboard password, or tokens;
- modify strategy or bot config;
- run backtests;
- commit refreshed `user_data/data/**`.

## Non-Actions

This task did not:

- download market data;
- modify server files;
- modify local strategy/config/dashboard files;
- read secrets;
- start, stop, or restart bots;
- run backtests.

## Recommended Next Task

Proceed with:

```text
Task 76R: Allow V11.30 gate telemetry exact paths
Task 76: V11.30 Gate Telemetry Report Builder
```

The actual data refresh should be a separate explicit task after telemetry
reporting is available.
