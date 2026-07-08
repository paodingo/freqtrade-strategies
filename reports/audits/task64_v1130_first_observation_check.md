# Task 64: V11.30 First Observation Check

## Summary

Completed the first read-only observation check for
`freqtrade-v1130-crash-rebound-shadow`.

Result:

- V11.30 container is running.
- V11.30 heartbeat is present.
- V11.30 dry-run SQLite DB exists.
- Current V11.30 `trades = 0`.
- Current V11.30 `orders = 0`.
- Resource pressure remains high but the server is still running both expected
  containers.

This task did not modify strategies, bot configs, server files, dashboard code,
SQLite data, or live/server runtime state.

## Preconditions

- local directory: `D:\code\freqtrade-strategies-clean`
- branch: `codex/btc-mvp-system-harnessed`
- starting commit: `cb6cef6`
- local status before task: clean
- readiness before task: passed

## Server Observation

Observed server:

- host: `43.134.72.69`
- user: `ubuntu`
- hostname: `VM-0-8-ubuntu`
- server time: `2026-07-08T11:09:39+08:00`

Running containers:

| Container | Status | Ports |
|---|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up 15 minutes` | none shown |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

The old `freqtrade-v1129-ranging-short-shadow` container was not running, as
expected after Task 63.

## Resource Snapshot

| Resource | Observed |
|---|---:|
| memory total | `1.9Gi` |
| memory used | `1.7Gi` |
| memory free | `72Mi` |
| memory available | `269Mi` |
| swap total | `5.9Gi` |
| swap used | `2.4Gi` |

Container resource snapshot:

| Container | CPU | Memory |
|---|---:|---:|
| `freqtrade-v1130-crash-rebound-shadow` | `5.17%` | `135.9MiB / 1.922GiB` |
| `freqtrade-v1129` | `10.06%` | `337.7MiB / 1.922GiB` |

Interpretation:

- V11.30 is not currently the dominant memory user.
- Server memory remains tight.
- Do not start additional bots without another resource decision task.

## SQLite Observation

V11.30 DB:

```text
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

File stat:

- size: `94208`
- mtime: `2026-07-08 10:54:45.750671663 +0800`

Tables discovered:

- `KeyValueStore`
- `orders`
- `pairlocks`
- `trade_custom_data`
- `trades`
- `wallet_history`

Read-only row counts:

| Table | Rows |
|---|---:|
| `trades` | `0` |
| `orders` | `0` |
| `pairlocks` | `0` |
| `wallet_history` | `0` |

Trade status:

- open trades: `0`
- closed trades: `0`
- trade entry tags: `[]`

## Schema Availability

`trades` table contains useful execution fields including:

- `pair`
- `is_open`
- `fee_open`
- `fee_close`
- `open_rate`
- `open_rate_requested`
- `close_rate`
- `close_rate_requested`
- `close_profit`
- `close_profit_abs`
- `stake_amount`
- `amount`
- `open_date`
- `close_date`
- `exit_reason`
- `strategy`
- `enter_tag`
- `timeframe`
- `is_short`
- `funding_fees`
- `funding_fee_running`

`orders` table contains useful order fields including:

- `ft_trade_id`
- `ft_order_side`
- `ft_pair`
- `ft_is_open`
- `ft_price`
- `order_id`
- `status`
- `symbol`
- `order_type`
- `side`
- `price`
- `average`
- `amount`
- `filled`
- `remaining`
- `cost`
- `order_date`
- `order_filled_date`
- `order_update_date`
- `funding_fee`
- `ft_fee_base`
- `ft_order_tag`

Because there are currently no rows, these fields are schema-available but not
yet sample-available.

## Log Findings

V11.30 logs confirm:

- config loaded from
  `/freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json`;
- dry-run mode enabled;
- DB path:
  `sqlite:////freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite`;
- strategy loaded from
  `/freqtrade/project/strategies/RegimeAwareV1130CrashReboundShadow.py`;
- timeframe: `15m`;
- stake amount: `250`;
- max open trades: `2`;
- pairlist has six pairs:
  `ETH`, `SOL`, `DOGE`, `LINK`, `XRP`, `BCH`;
- state changed to `RUNNING`;
- repeated heartbeat lines are present through `2026-07-08 03:09:25`.

No V11.30 `ERROR`, `Traceback`, or stop evidence was observed in the filtered
log summary.

## V11.29 Side Observation

Recent `freqtrade-v1129` logs still show:

- a Binance `RequestTimeout` during `reload_markets`;
- a strategy analysis warning:
  `Strategy analysis took 308.81s`, above 25% of the timeframe;
- continued `RUNNING` heartbeats afterward.

Interpretation:

- V11.29 API/runtime instability is not fully gone;
- this does not directly prove V11.30 health or weakness;
- keep V11.29 performance/API issues separate from V11.30 first observation.

## What This Can Conclude

This task can conclude:

- V11.30 shadow is running.
- V11.30 DB exists.
- V11.30 has not produced observed orders/trades yet.
- Initial runtime logs look healthy enough for continued observation.

## What This Cannot Conclude

This task cannot conclude:

- V11.30 has no signals.
- V11.30 gate is too strict.
- V11.30 is profitable or unprofitable.
- V11.30 can replace V11.29 or V10.8.2.
- `orders=0` means strategy failure.

## Non-Actions

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- read or print secrets;
- run `docker inspect`;
- start, stop, or restart containers;
- run `freqtrade trade`;
- run a backtest;
- write SQLite;
- modify strategy/config/dashboard/deploy files.

## Recommended Next Task

Recommended next task:

```text
Task 65: V11.30 Signal/Gate Telemetry Gap Audit
```

Purpose:

- explain what evidence is missing before interpreting `orders=0`;
- define the minimum read-only replay/telemetry needed to know whether V11.30
  had no signal, was blocked by alpha/gate, or simply had no qualifying market
  conditions.
