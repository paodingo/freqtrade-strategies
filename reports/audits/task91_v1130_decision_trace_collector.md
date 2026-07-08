# Task 91: V11.30 Read-Only Decision Trace Collector

## Summary

Implemented and ran a read-only V11.30 decision trace collector.

The collector converts existing read-only evidence into a structured decision
trace report. It does not connect to exchange APIs, does not read secrets, does
not modify live strategy behavior, and does not place orders.

## Generated Files

- `scripts/build_v1130_decision_trace_report.js`
- `reports/v1130_observation/v1130_decision_trace_report.json`
- `reports/v1130_observation/v1130_decision_trace_report.md`

## Input Sources

| source | status |
|---|---|
| `reports/v1130_observation/v1130_watch_only_telemetry_report.json` | read locally |
| V11.30 container state from `docker ps` | read-only observed |
| V11.30 Docker log tail | read-only observed |
| V11.30 SQLite count in `mode=ro` | read-only observed |

V11.30 container state:

```text
freqtrade-v1130-crash-rebound-shadow|Up 7 hours|
```

V11.30 runtime counts:

| metric | value |
|---|---:|
| trades | 0 |
| orders | 0 |
| open trades | 0 |

## Latest Decision Trace

Latest checked candle:

```text
2026-07-08T06:15:00Z
```

| pair | strict gate | watch gate | derived blocked reason |
|---|---|---|---|
| `ETH/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, volume` |
| `SOL/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, rsi` |
| `DOGE/USDT:USDT` | `not_candidate` | `not_candidate` | `return, rsi` |
| `LINK/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, rsi` |
| `XRP/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, rsi` |
| `BCH/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, volume` |

## Field Availability

Observed or derived:

- `return_ratio`
- `range_ratio`
- `rsi`
- `volume_ratio`
- latest strict/watch gate state
- V11.30 trade/order/open-trade counts
- container running state
- log-tail error count

Unknown from existing read-only sources:

- `alpha_flags`
- `taker_buy_pressure`
- `taker_sell_pressure`
- `protection_blocked`
- `wallet_or_stake_blocked`
- `max_open_trades_blocked`
- final live strategy `enter_long` decision reason

## Classification

```text
insufficient
```

Existing sources still do not expose the full live strategy decision path.

## Validation

Commands:

```powershell
node --check scripts/build_v1130_decision_trace_report.js
node scripts/build_v1130_decision_trace_report.js
```

The builder requires:

```powershell
$env:V1130_DECISION_TRACE_INPUT_JSON = "<input-json>"
```

## Safety Boundary

This task did not:

- modify strategy code;
- modify bot config;
- modify dashboard code;
- modify deploy code;
- read secrets;
- start, stop, or restart bots;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- place orders;
- claim V11.30 can replace V10.8.2.

## Recommended Next Task

Proceed with:

```text
Task 92: V11.30 Decision Trace Observation Window
```
