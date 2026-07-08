# Task 88: V11.30 Watch-Only Telemetry Report

## Summary

Implemented and generated a V11.30 watch-only telemetry report.

The report compares the strict V11.30 gate with a loose-range watch-only gate
using a read-only server OHLCV snapshot. It does not implement a trading signal,
does not set `enter_long`, and cannot place orders.

## Generated Files

- `scripts/build_v1130_watch_only_telemetry_report.js`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.json`
- `reports/v1130_observation/v1130_watch_only_telemetry_report.md`

## Input Source

Read-only server-side input:

- host: `43.134.72.69`
- container: `freqtrade-v1130-crash-rebound-shadow`
- source type: `server_read_only_feather_ohlcv_snapshot`
- timeframe: `15m`
- pairs:
  - `ETH/USDT:USDT`
  - `SOL/USDT:USDT`
  - `DOGE/USDT:USDT`
  - `LINK/USDT:USDT`
  - `XRP/USDT:USDT`
  - `BCH/USDT:USDT`
- window: last `240` 15m candles per pair
- rows: `1440`

No API password, `.env`, `user_data/monitor.env`, API key, exchange credential,
or dashboard password was read.

## Telemetry Counts

Important interpretation:

```text
enabled = OHLCV gate pass only
alpha/taker filters = unknown from feather input
enter_long = 0
can_place_order = false
```

| metric | count |
|---|---:|
| strict candidates | 12 |
| strict enabled, OHLCV-only | 12 |
| watch candidates | 32 |
| watch enabled, OHLCV-only | 32 |
| watch-only enabled, OHLCV-only | 20 |
| not candidate | 1408 |

## Latest Candle State

Latest checked candle time:

```text
2026-07-08T06:15:00Z
```

All six checked pairs were `not_candidate` for both strict and watch-only gates
on the latest candle.

## Runtime Count Evidence

Read-only SQLite count source:

```text
/freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Observed:

| metric | value |
|---|---:|
| V11.30 trades | 0 |
| V11.30 orders | 0 |
| V11.30 open trades | 0 |

These are observed database counts. They are not a strategy failure conclusion.

## Safety Boundary

This task did not:

- modify strategy code;
- modify bot configuration;
- modify dashboard code;
- modify deploy code;
- read secrets;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run a backtest;
- write SQLite;
- place orders;
- claim V11.30 can replace V10.8.2.

## Validation

Commands:

```powershell
node --check scripts/build_v1130_watch_only_telemetry_report.js
node scripts/build_v1130_watch_only_telemetry_report.js
```

The generator requires:

```powershell
$env:V1130_WATCH_ONLY_TELEMETRY_INPUT_JSON = "<input-json>"
```

## Recommended Next Task

Proceed with:

```text
Task 89: V11.30 live observation strict-vs-watch-only comparison
```
