# Task 129: V11.30 Runtime Performance Warning Investigation

## Summary

Investigated the V11.30 runtime performance warning from Task 126 using
read-only server checks.

Decision:

```text
runtime_warning_confirmed_needs_instrumented_perf_audit
```

The bot is running and current CPU/memory usage was low in the snapshot, but the
log shows at least one analysis-cycle overrun and one Binance market reload
timeout. This is enough to treat runtime stability as an active risk.

## Server Checks

| item | value |
|---|---|
| host | `43.134.72.69` |
| user | `ubuntu` |
| hostname | `VM-0-8-ubuntu` |
| server time checked | `2026-07-09T15:50:03+08:00` |
| V11.30 container | `freqtrade-v1130-crash-rebound-shadow` |
| V11.30 state | `Up 18 hours` |
| V11.29 container | `freqtrade-v1129` |
| V11.29 state | `Up 5 days` |

## Resource Snapshot

| container | CPU | memory | memory percent |
|---|---:|---:|---:|
| `freqtrade-v1130-crash-rebound-shadow` | `0.00%` | `173MiB / 1.922GiB` | `8.79%` |
| `freqtrade-v1129` | `0.14%` | `322.1MiB / 1.922GiB` | `16.37%` |

This snapshot does not show sustained CPU or memory saturation. It also does
not rule out intermittent spikes during analysis cycles.

## Log Findings

Confirmed warning:

```text
2026-07-09 07:19:56 ... Strategy analysis took 260.81s, more than 25% of the timeframe (225.00s).
```

Confirmed exchange/API issue:

```text
2026-07-09 05:40:25 ... _load_async_markets() returned exception: RequestTimeout
2026-07-09 05:40:26 ... Could not load markets.
... binance GET https://dapi.binance.com/dapi/v1/exchangeInfo
```

The log tail also showed repeated `state='RUNNING'` heartbeats after these
events.

## Interpretation

Observed:

- V11.30 is still running.
- V11.29 is also still running, sharing the same constrained host.
- V11.30 had a strategy analysis overrun.
- V11.30 had at least one Binance `exchangeInfo` timeout.

Unknown:

- whether the analysis overrun coincided with trade entry/exit delay;
- whether V11.29 contributes materially to CPU, memory, I/O, or network
  contention;
- whether the warning is frequent outside the sampled log window;
- which indicator or data-loading step dominates the analysis time.

## Risk

Runtime warning can lead to delayed orders or missed signals. Given V11.30's
current two closed trades are both time-exit losses, runtime performance should
be investigated before promoting the strategy or adding more live bots.

## Recommended Next Task

Proceed with:

```text
Task 132: V11.30 Instrumented Runtime Performance Audit Plan
```

Task 132 should define a read-only or telemetry-only way to measure per-cycle
analysis time, pair count, candle loading cost, API timeout frequency, and
container resource spikes without changing trading behavior.

## Safety Boundary

This task did not:

- read `.env` or `user_data/monitor.env`;
- print API keys, exchange credentials, server keys, or dashboard passwords;
- run `docker inspect`;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- modify server files;
- modify strategy code;
- modify bot config;
- modify dashboard or deploy files.

