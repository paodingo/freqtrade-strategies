# Task 94S: V11.30 One-Time Safe Market Data Refresh

## Summary

Executed the approved one-time V11.30 OHLCV refresh command.

Result:

```text
v1130_market_data_refreshed_once
```

The refresh advanced all six V11.30 observation pairs:

- `15m` latest candle advanced from `2026-07-08T06:15:00Z` to
  `2026-07-08T09:45:00Z`.
- `4h` latest candle advanced from `2026-07-08T00:00:00Z` to
  `2026-07-08T04:00:00Z`.

This task did not install continuous automation and did not claim that V11.30
has generated trades.

## Preconditions

- Worktree: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Starting commit: `50ba915`
- Starting `git status --short --untracked-files=all`: empty
- Readiness check before execution: passed

## Server Evidence

Pre-refresh server evidence:

```text
hostname: VM-0-8-ubuntu
date_utc: 2026-07-08T10:02:05Z
freqtrade-v1130-crash-rebound-shadow: Up 7 hours
freqtrade-v1129: Up 4 days
```

Post-refresh server evidence:

```text
date_utc: 2026-07-08T10:02:58Z
freqtrade-v1130-crash-rebound-shadow: Up 7 hours
freqtrade-v1129: Up 4 days
```

Both relevant containers remained running. No start, stop, or restart command
was executed.

## Command Executed

Only the Task 80 corrected command shape was executed:

```bash
docker exec freqtrade-v1130-crash-rebound-shadow freqtrade download-data \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --datadir /freqtrade/project/user_data/data \
  --trading-mode futures \
  --timeframes 15m 4h \
  --pairs ETH/USDT:USDT SOL/USDT:USDT DOGE/USDT:USDT LINK/USDT:USDT XRP/USDT:USDT BCH/USDT:USDT \
  --data-format-ohlcv feather
```

The command exited with code `0`.

Important boundaries:

- `scripts/refresh_data.sh` was not used.
- `--prepend` was not used.
- `--erase` was not used.
- `freqtrade trade` was not executed.
- No bot lifecycle command was executed.

Because this is futures data, Freqtrade also logged downloads for associated
`1h` mark and funding-rate data while executing the approved command. This task
did not separately request or broaden the target pair/config scope.

## Pre-Refresh Data State

Read-only check time:

```text
2026-07-08T10:02:06Z
```

| pair | timeframe | rows | latest candle | mtime UTC |
|---|---:|---:|---|---|
| `ETH` | `15m` | 88250 | `2026-07-08T06:15:00Z` | `2026-07-08T06:41:39Z` |
| `ETH` | `4h` | 5515 | `2026-07-08T00:00:00Z` | `2026-07-08T06:41:40Z` |
| `SOL` | `15m` | 88250 | `2026-07-08T06:15:00Z` | `2026-07-08T06:41:42Z` |
| `SOL` | `4h` | 5515 | `2026-07-08T00:00:00Z` | `2026-07-08T06:41:42Z` |
| `DOGE` | `15m` | 88250 | `2026-07-08T06:15:00Z` | `2026-07-08T06:41:42Z` |
| `DOGE` | `4h` | 5515 | `2026-07-08T00:00:00Z` | `2026-07-08T06:41:42Z` |
| `LINK` | `15m` | 88250 | `2026-07-08T06:15:00Z` | `2026-07-08T06:41:42Z` |
| `LINK` | `4h` | 5515 | `2026-07-08T00:00:00Z` | `2026-07-08T06:41:42Z` |
| `XRP` | `15m` | 88250 | `2026-07-08T06:15:00Z` | `2026-07-08T06:41:42Z` |
| `XRP` | `4h` | 5515 | `2026-07-08T00:00:00Z` | `2026-07-08T06:41:42Z` |
| `BCH` | `15m` | 88250 | `2026-07-08T06:15:00Z` | `2026-07-08T06:41:43Z` |
| `BCH` | `4h` | 5515 | `2026-07-08T00:00:00Z` | `2026-07-08T06:41:43Z` |

## Post-Refresh Data State

Read-only check time:

```text
2026-07-08T10:03:00Z
```

| pair | timeframe | rows | latest candle | mtime UTC |
|---|---:|---:|---|---|
| `ETH` | `15m` | 88264 | `2026-07-08T09:45:00Z` | `2026-07-08T10:02:31Z` |
| `ETH` | `4h` | 5516 | `2026-07-08T04:00:00Z` | `2026-07-08T10:02:32Z` |
| `SOL` | `15m` | 88264 | `2026-07-08T09:45:00Z` | `2026-07-08T10:02:34Z` |
| `SOL` | `4h` | 5516 | `2026-07-08T04:00:00Z` | `2026-07-08T10:02:34Z` |
| `DOGE` | `15m` | 88264 | `2026-07-08T09:45:00Z` | `2026-07-08T10:02:34Z` |
| `DOGE` | `4h` | 5516 | `2026-07-08T04:00:00Z` | `2026-07-08T10:02:34Z` |
| `LINK` | `15m` | 88264 | `2026-07-08T09:45:00Z` | `2026-07-08T10:02:34Z` |
| `LINK` | `4h` | 5516 | `2026-07-08T04:00:00Z` | `2026-07-08T10:02:34Z` |
| `XRP` | `15m` | 88264 | `2026-07-08T09:45:00Z` | `2026-07-08T10:02:35Z` |
| `XRP` | `4h` | 5516 | `2026-07-08T04:00:00Z` | `2026-07-08T10:02:35Z` |
| `BCH` | `15m` | 88264 | `2026-07-08T09:45:00Z` | `2026-07-08T10:02:35Z` |
| `BCH` | `4h` | 5516 | `2026-07-08T04:00:00Z` | `2026-07-08T10:02:35Z` |

## Validation Result

Observed refresh delta:

- `15m`: `+14` rows per pair.
- `4h`: `+1` row per pair.
- Latest `15m` candle now trails the post-check server time by one incomplete
  15-minute candle boundary, which is expected for closed-candle data.
- Latest `4h` candle is `2026-07-08T04:00:00Z`; the `08:00` candle was still
  incomplete at the check time.

This is enough to confirm that the one-time refresh command updated V11.30
local market data content.

## Forbidden Surface Confirmation

This task did not:

- modify strategies;
- modify bot configs;
- modify dashboard;
- modify deploy files;
- read `.env`;
- read `user_data/monitor.env`;
- print API keys, exchange credentials, server keys, dashboard passwords, or
  tokens;
- start, stop, or restart any bot;
- run `freqtrade trade`;
- run backtests;
- modify the original dirty worktree;
- run the legacy `scripts/refresh_data.sh`.

## Remaining Risk

This was a one-time refresh only. V11.30 still lacks a dedicated safe continuous
market data refresh automation.

The active legacy cron refresh script remains unsuitable as the V11.30-specific
solution because it has broader bot lifecycle and reporting side effects.

## Next Recommendation

Proceed with:

```text
Task 94T: V11.30 market data refresh automation plan
```

Then rerun a fresh V11.30 observation pass:

```text
Task 88/91 style telemetry and decision trace after fresh data
```

This task does not authorize live threshold changes or any V11.30 replacement
conclusion.
