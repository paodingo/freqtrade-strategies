# Task 89: V11.30 Live Observation Strict vs Watch-Only

## Summary

Performed a read-only live observation of V11.30 strict gate state versus the
new watch-only telemetry lane.

Conclusion:

- V11.30 container is running;
- no recent V11.30 log evidence of crash, exception, or stopped state was found
  in the checked tail;
- V11.30 SQLite still has `0` trades, `0` orders, and `0` open trades;
- latest checked candle (`2026-07-08T06:15:00Z`) is `not_candidate` for both
  strict and watch-only gates across all six checked pairs;
- the last 240 candles per pair contain watch-only OHLCV opportunities, but
  alpha/taker filters were not available from the feather input and remain
  `unknown`;
- this does not prove strategy failure, profitability, or replacement
  readiness.

## Server Evidence

Read-only commands observed:

```text
hostname: VM-0-8-ubuntu
server_time_utc: 2026-07-08T09:26:27Z
```

Containers:

| container | status | ports |
|---|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 7 hours` | none exposed |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

No `docker start`, `docker stop`, `docker restart`, `freqtrade trade`, or
backtest command was run.

## V11.30 Runtime Evidence

SQLite source:

```text
/freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Observed read-only counts:

| metric | value |
|---|---:|
| trades | 0 |
| orders | 0 |
| open trades | 0 |

The database file exists and was not modified by this task.

## Strict vs Watch-Only Telemetry

Source:

```text
reports/v1130_observation/v1130_watch_only_telemetry_report.json
```

Scope:

```text
OHLCV-only; alpha/taker filters unknown from feather input
```

Window:

- timeframe: `15m`
- checked pairs: `6`
- rows: `1440`
- latest candle: `2026-07-08T06:15:00Z`

Counts:

| metric | count |
|---|---:|
| strict OHLCV candidates | 12 |
| watch OHLCV candidates | 32 |
| watch-only OHLCV candidates | 20 |
| not candidate | 1408 |

Latest checked rows:

| pair | strict gate | watch gate | watch failed conditions |
|---|---|---|---|
| `ETH/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, volume` |
| `SOL/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, rsi` |
| `DOGE/USDT:USDT` | `not_candidate` | `not_candidate` | `return, rsi` |
| `LINK/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, rsi` |
| `XRP/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, rsi` |
| `BCH/USDT:USDT` | `not_candidate` | `not_candidate` | `return, range, volume` |

## Log Findings

V11.30 log tail showed:

- recurring `Bot heartbeat` with state `RUNNING`;
- `Wallets synced`;
- whitelist with 6 pairs:
  - `ETH/USDT:USDT`
  - `SOL/USDT:USDT`
  - `DOGE/USDT:USDT`
  - `LINK/USDT:USDT`
  - `XRP/USDT:USDT`
  - `BCH/USDT:USDT`

No checked V11.30 log tail evidence of:

- `Traceback`;
- `Exception`;
- `stopped`;
- API failure;
- order placement;
- trade open/close.

Absence in the checked log tail is not proof that no such event ever occurred.

## Current V11.29 Container Note

The currently running `freqtrade-v1129` container is separate from the historical
V10.8.2 benchmark evidence.

Current checked DB:

```text
/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite
```

Observed counts were also `0` trades and `0` orders. This should not be confused
with prior V10.8.2 historical benchmark samples.

## Interpretation

Most likely current state:

- V11.30 is running and analyzing candles;
- the latest candle did not pass even the loose watch OHLCV gate;
- the wider recent window does contain loose watch OHLCV candidates;
- there is still no observed real V11.30 execution sample;
- alpha/taker filter truth cannot be proven from the current feather-only input.

This task does not conclude that V11.30 is good, bad, profitable, unprofitable,
or replaceable.

## Blocking Gaps

- No live API exposure for V11.30;
- no persisted per-candle strategy decision trace from the live strategy;
- alpha/taker filter state is not available in the feather-only telemetry input;
- no V11.30 orders/trades to evaluate fills, fees, funding, slippage, or latency.

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

## Recommended Task 90

Proceed with:

```text
Task 90: V11.30 live decision-trace source plan
```

Recommended scope:

- identify a safe way to persist per-pair, per-candle strategy gate decisions;
- include strict gate, loose watch gate, alpha/taker filters, protections, and
  pairlist state;
- keep it read-only or dry telemetry only;
- do not modify trading behavior;
- do not expose secrets;
- do not use the watch lane to place orders.
