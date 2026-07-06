# Task 40: V11.29 Ranging-Short Historical Data Coverage Extension

## Summary

This task performed a read-only historical data coverage check for the
V11.29 `v66_ranging_short_edge` offline calibration path.

It did not download data, modify data files, run backtests, modify strategy
code, modify bot configuration, start/stop/restart containers, read secrets, or
change server state.

Main finding:

```text
30d+ futures 15m/4h historical candle data exists inside the running
freqtrade containers for the V11.29 pair universe.
```

Important caveat:

```text
The historical feather data currently stops at 2026-07-03, while the runtime
API has live/analyzed rows through 2026-07-06. Therefore the historical dataset
is long enough for offline calibration, but not fully current.
```

## Sources Checked

Current clean worktree:

```text
D:\code\freqtrade-strategies-clean\user_data\data
```

Result:

```text
No usable tracked/untracked clean-worktree data files found.
```

Original dirty worktree, read-only:

```text
D:\code\freqtrade-strategies\user_data\data
```

Result:

```text
Some futures feather data exists, but it is incomplete for this task. It should
remain evidence-only and should not be automatically copied into the clean
worktree.
```

Server containers, read-only:

```text
freqtrade-v1129 /freqtrade/project/user_data/data/futures
freqtrade-v1082 /freqtrade/project/user_data/data/futures
```

Result:

```text
Both containers expose the same futures data set shape.
```

## Container State

Read-only `docker ps --format` showed:

| Container | Status | Port |
| --- | --- | --- |
| `freqtrade-v1129` | Up 2 days | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1082` | Up 6 days | `127.0.0.1:8091->8091/tcp` |

No container lifecycle command was run.

## Historical Data Coverage Matrix

Read-only feather inspection inside `freqtrade-v1129`:

| Pair | 15m exists | 15m rows | 15m min | 15m max | 4h exists | 4h rows | 4h min | 4h max |
| --- | --- | ---: | --- | --- | --- | ---: | --- | --- |
| BTC/USDT:USDT | yes | 8100 | 2026-04-10 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| ETH/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| SOL/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| BNB/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| XRP/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| DOGE/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| ADA/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| LINK/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| AVAX/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| LTC/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| TRX/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |
| BCH/USDT:USDT | yes | 87780 | 2024-01-01 00:00 UTC | 2026-07-03 08:45 UTC | yes | 5486 | 2024-01-01 00:00 UTC | 2026-07-03 04:00 UTC |

## Coverage Assessment

Observed:

- Required `15m-futures` files exist for all 12 V11.29 pairs.
- Required `4h-futures` files exist for all 12 V11.29 pairs.
- BTC has about 84 days of 15m futures data.
- The other 11 pairs have data from 2024-01-01 through 2026-07-03.
- The pair universe is sufficient for a 30d+ offline candidate study ending on
  2026-07-03.

Derived:

- Task 39's runtime API limit was the immediate reason the candidate return
  report only had about 5.49 days.
- A historical feather-based study can expand the sample window without
  touching live strategy or bot config.

Insufficient:

- The feather data is not current through 2026-07-06.
- This task did not validate whether all informative columns needed by the
  strategy are already materialized in feather files. The raw feather files
  contain OHLCV columns; derived indicators/regime columns must be recomputed
  by a future offline script if needed.
- This task did not run the extended return study yet.

Unknown:

- Whether the 2026-07-03 to 2026-07-06 gap materially changes candidate
  outcomes.
- Whether a safe data refresh job is currently configured but not running.
- Whether historical alpha-risk state can be reconstructed for the full 30d
  window.

## Data Freshness Gap

The historical data max timestamp:

```text
2026-07-03 08:45 UTC for 15m futures
2026-07-03 04:00 UTC for 4h futures
```

Task 39 runtime API had analyzed rows through 2026-07-06. This means:

- server runtime data exists beyond the feather history;
- local/server feather history is stale by roughly three days;
- a 30d offline study can proceed using data ending 2026-07-03;
- a later safe data-refresh task is still needed if we want fully current
  historical feather coverage.

## Recommended Task 41

Recommended next task:

```text
Task 41: V11.29 Feather-Based Ranging-Short Historical Return Study
```

Suggested scope:

- Add an exact guard exception first if new script/report paths are blocked.
- Build a read-only script that consumes container feather files.
- Recompute the V66 ranging-short candidate conditions from OHLCV.
- Join or derive the required 4h context without modifying source data.
- Compute 1/2/4/8 candle forward return, MFE, MAE, and fee-adjusted results
  over at least the latest 30d ending 2026-07-03.
- Keep alpha-risk handling explicit:
  - `missing` if full historical alpha state is unavailable;
  - do not pretend alpha allowed/blocked data exists if it cannot be
    reconstructed.

## Later Task: Safe Data Refresh

A separate later task should decide whether to refresh feather data through
2026-07-06 or later.

That task must be explicitly authorized because data refresh can touch
`user_data/data/**` and may involve exchange API access. It should not be
bundled into this read-only coverage task.

## Boundary Confirmation

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- read or print API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a Freqtrade backtest;
- download or refresh market data;
- write SQLite;
- modify server files;
- modify the original dirty workspace.

## Verification

Required completion checks:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

