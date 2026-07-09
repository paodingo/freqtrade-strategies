# Task 103: High-Volatility Window Dataset Readiness Plan

## Summary

Read-only checked whether the current V11.30 pair universe has usable
high-volatility window data for `15m`, `1h`, and `4h` offline candidate-search
work.

Conclusion:

```text
15m_and_4h_recent_data_ready_but_1h_futures_data_is_stale
```

No market data was downloaded. No server files were modified. No bot was
started, stopped, or restarted.

## Preconditions

| item | value |
|---|---|
| worktree | `D:\code\freqtrade-strategies-clean` |
| branch | `codex/btc-mvp-system-harnessed` |
| starting commit | `909b85f` |
| starting status | clean |
| readiness before check | passed |

## Read-Only Checks Performed

| check | result |
|---|---|
| server hostname | `VM-0-8-ubuntu` |
| server UTC time | `2026-07-09T03:07:17Z` |
| V11.30 container | `freqtrade-v1130-crash-rebound-shadow Up 14 hours` |
| V11.29 container | `freqtrade-v1129 Up 5 days` |
| data inspection method | `docker exec -i freqtrade-v1130-crash-rebound-shadow python -` read-only feather metadata |
| secret files read | no |
| data downloaded | no |
| bot restart/start/stop | no |

The first probe accidentally matched `*-1h-funding_rate.feather` when looking
for `1h`. A stricter second probe used only exact `*-<timeframe>-futures.feather`
OHLCV paths. The readiness decision below is based on the stricter OHLCV-only
probe.

## Pair Universe Checked

```text
ETH/USDT:USDT
SOL/USDT:USDT
DOGE/USDT:USDT
LINK/USDT:USDT
XRP/USDT:USDT
BCH/USDT:USDT
```

## Strict OHLCV Futures Coverage

| pair | 15m last candle UTC | 15m rows | 1h last candle UTC | 1h rows | 4h last candle UTC | 4h rows |
|---|---:|---:|---:|---:|---:|---:|
| `ETH/USDT:USDT` | `2026-07-09T02:45:00Z` | `88332` | `2026-07-03T08:00:00Z` | `21945` | `2026-07-08T20:00:00Z` | `5520` |
| `SOL/USDT:USDT` | `2026-07-09T02:45:00Z` | `88332` | `2026-07-03T08:00:00Z` | `21945` | `2026-07-08T20:00:00Z` | `5520` |
| `DOGE/USDT:USDT` | `2026-07-09T02:45:00Z` | `88332` | `2026-07-03T08:00:00Z` | `21945` | `2026-07-08T20:00:00Z` | `5520` |
| `LINK/USDT:USDT` | `2026-07-09T02:45:00Z` | `88332` | `2026-07-03T08:00:00Z` | `21945` | `2026-07-08T20:00:00Z` | `5520` |
| `XRP/USDT:USDT` | `2026-07-09T02:45:00Z` | `88332` | `2026-07-03T08:00:00Z` | `21945` | `2026-07-08T20:00:00Z` | `5520` |
| `BCH/USDT:USDT` | `2026-07-09T02:45:00Z` | `88332` | `2026-07-03T08:00:00Z` | `21945` | `2026-07-08T20:00:00Z` | `5520` |

## Readiness Assessment

| timeframe | status | reason |
|---|---|---|
| `15m` | ready for recent high-volatility window work | all six pairs reach `2026-07-09T02:45:00Z` |
| `4h` | ready for recent high-volatility window work | all six pairs reach `2026-07-08T20:00:00Z`, which is expected for 4h candle closure cadence at probe time |
| `1h` | stale / needs refresh before use | exact `*-1h-futures.feather` files stop at `2026-07-03T08:00:00Z` for all six pairs |

## Important Data Caveat

`*-1h-funding_rate.feather` files were fresh to `2026-07-09T00:00:00Z`, but
they are funding-rate series and must not be treated as `1h` OHLCV price data.

## What Can Proceed Now

The following can proceed without data refresh:

- `15m` crash/rebound replay over the recent volatile window;
- `4h` informative-regime checks over the same broad window;
- Task 104 offline harness design.

The following should wait for a separate safe data-refresh task:

- any candidate search that requires recent `1h` OHLCV features;
- any multi-timeframe model that requires synchronized `15m / 1h / 4h` recent
  inputs.

## Safe Data Refresh Plan If Needed

Open a separate exact-scope task before executing any download. Suggested
scope:

```text
Task 103R: Refresh V11.30 1h Futures OHLCV Data
```

Draft boundaries:

- only refresh exact `1h` futures OHLCV files for the six V11.30 pairs;
- do not modify strategies;
- do not modify bot configs;
- do not restart/start/stop bots unless separately authorized;
- do not read `.env` or `user_data/monitor.env`;
- record before/after row counts and last candle timestamps;
- re-run this readiness check after refresh.

## Stop Conditions

Do not run candidate-search implementation if:

- the design requires `1h` features before `1h` OHLCV is refreshed;
- the task requires strategy changes without exact authorization;
- the task requires bot config edits;
- the task requires server restart;
- the task needs secrets;
- V11.30 replacement conclusions are requested from insufficient samples.

## Safety Boundary

This task did not:

- download or refresh data;
- run backtests;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- read `.env` or `user_data/monitor.env`;
- print credentials;
- start, stop, or restart bots;
- force-close V11.30 trades;
- claim V11.30 is good or bad.

## Recommended Next Task

Proceed with:

```text
Task 104: Candidate Search Harness Design
```

Then open `Task 103R` only if the next implementation requires recent `1h`
OHLCV data.

