# Task 63: V11.30 Runtime Resource Decision And Shadow Start Authorization

## Summary

Executed the V11.30 runtime resource decision and started the V11.30
crash-rebound dry-run shadow container.

Decision:

- do not run V11.29 ranging-short shadow and V11.30 crash-rebound shadow
  together on this small server;
- stop only the old `freqtrade-v1129-ranging-short-shadow`;
- keep the main `freqtrade-v1129` container running;
- start `freqtrade-v1130-crash-rebound-shadow` in dry-run mode.

This task did not read secrets, did not run a backtest, did not run live trading,
and did not modify strategy or bot config files.

## Local Preconditions

- local directory: `D:\code\freqtrade-strategies-clean`
- branch: `codex/btc-mvp-system-harnessed`
- starting commit: `469756e`
- local `git status --short --untracked-files=all`: clean
- readiness check before runtime work: passed

## Server Access

- host: `43.134.72.69`
- user: `ubuntu`
- key path used: `D:\key\openclaw\clf.pem`

The key file content was not read or printed.

## Pre-Start Server State

Observed at server date:

- `2026-07-08T10:53:32+08:00`

Running containers before action:

| Container | Status | Ports |
|---|---|---|
| `freqtrade-v1129-ranging-short-shadow` | `Up 32 hours` | none shown |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Resource snapshot before action:

| Resource | Observed |
|---|---:|
| memory total | `1.9Gi` |
| memory used | `1.7Gi` |
| memory free | `75Mi` |
| memory available | `214Mi` |
| swap total | `5.9Gi` |
| swap used | `3.0Gi` |

Container memory before action:

| Container | CPU | Memory |
|---|---:|---:|
| `freqtrade-v1129-ranging-short-shadow` | `0.00%` | `262.9MiB / 1.922GiB` |
| `freqtrade-v1129` | `0.15%` | `308.8MiB / 1.922GiB` |

Interpretation:

- starting V11.30 as a third bot was unsafe because available memory was only
  about `214Mi`;
- stopping the old V11.29 shadow was required before starting V11.30.

## Resource Action

Stopped only:

```bash
docker stop freqtrade-v1129-ranging-short-shadow
```

Did not stop:

- `freqtrade-v1129`

Post-stop containers:

| Container | Status | Ports |
|---|---|---|
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Post-stop resource snapshot:

| Resource | Observed |
|---|---:|
| memory total | `1.9Gi` |
| memory used | `1.5Gi` |
| memory free | `377Mi` |
| memory available | `478Mi` |
| swap total | `5.9Gi` |
| swap used | `1.9Gi` |

## V11.30 Start Command

Started:

```bash
docker run -d \
  --name freqtrade-v1130-crash-rebound-shadow \
  --restart unless-stopped \
  -v /home/ubuntu/freqtrade-strategies:/freqtrade/project \
  -w /freqtrade/project \
  freqtradeorg/freqtrade:stable \
  trade \
  --config /freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json \
  --strategy RegimeAwareV1130CrashReboundShadow \
  --strategy-path /freqtrade/project/strategies
```

Container id:

- `90a2fecdc25d24d0d753ce7e15c3fb45b46495869aca33f1e1dde2c9aac97a61`

No `api_server` port was exposed.
No env-file was used.

## Post-Start Runtime Evidence

Containers after start:

| Container | Status | Ports |
|---|---|---|
| `freqtrade-v1130-crash-rebound-shadow` | `Up` | none shown |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Resource snapshot shortly after start:

| Resource | Observed |
|---|---:|
| memory total | `1.9Gi` |
| memory used | `1.6Gi` |
| memory free | `108Mi` |
| memory available | `344Mi` |
| swap total | `5.9Gi` |
| swap used | `2.0Gi` |

Resource snapshot after short observation:

| Resource | Observed |
|---|---:|
| memory total | `1.9Gi` |
| memory used | `1.5Gi` |
| memory free | `72Mi` |
| memory available | `415Mi` |
| swap total | `5.9Gi` |
| swap used | `2.2Gi` |

Container memory after short observation:

| Container | CPU | Memory |
|---|---:|---:|
| `freqtrade-v1130-crash-rebound-shadow` | `0.00%` | `445.3MiB / 1.922GiB` |
| `freqtrade-v1129` | `0.14%` | `121.5MiB / 1.922GiB` |

## V11.30 Log Evidence

Startup log confirmed:

- Freqtrade version: `2026.5.1`
- config: `/freqtrade/project/user_data/config_multi_futures_v1130_crash_rebound_shadow.json`
- runmode: `dry_run`
- DB: `sqlite:////freqtrade/project/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite`
- strategy: `RegimeAwareV1130CrashReboundShadow`
- timeframe: `15m`
- stoploss: `-0.02`
- stake amount: `250`
- max open trades: `2`
- pair whitelist:
  - `ETH/USDT:USDT`
  - `SOL/USDT:USDT`
  - `DOGE/USDT:USDT`
  - `LINK/USDT:USDT`
  - `XRP/USDT:USDT`
  - `BCH/USDT:USDT`
- state: `RUNNING`
- heartbeat observed at:
  - `2026-07-08 02:55:08`
  - `2026-07-08 02:56:08`

## V11.30 SQLite Evidence

SQLite file exists:

```text
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite
```

Observed size shortly after start:

- `92K`

Read-only SQLite tables discovered:

- `KeyValueStore`
- `orders`
- `pairlocks`
- `trade_custom_data`
- `trades`
- `wallet_history`

Initial counts:

- `trades = 0`
- `orders = 0`

Interpretation:

- V11.30 has started and created its dry-run database;
- there is no evidence yet of orders or trades;
- this is an initial runtime observation only, not a strategy verdict.

## Non-Actions

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print or copy API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- stop `freqtrade-v1129`;
- start live trading;
- run a backtest;
- write to SQLite manually;
- modify strategy files;
- modify bot config files;
- modify dashboard or deploy files;
- modify the original dirty workspace.

## Current Runtime State

Expected running containers after Task 63:

- `freqtrade-v1129`
- `freqtrade-v1130-crash-rebound-shadow`

Expected stopped/replaced container:

- `freqtrade-v1129-ranging-short-shadow`

## What This Cannot Conclude

This task cannot conclude:

- V11.30 is profitable;
- V11.30 can replace V10.8.2;
- V11.30 can replace V11.29;
- V11.30 will produce trades;
- the zero initial orders/trades mean the strategy failed.

It only concludes:

- V11.30 crash-rebound shadow started successfully in dry-run mode;
- startup evidence and heartbeat are present;
- first SQLite evidence exists;
- first order/trade counts are still zero.

## Recommended Next Task

Recommended next task:

```text
Task 64: V11.30 First Observation Check
```

Recommended scope:

- observe container state, heartbeat, logs, DB size/mtime;
- query `trades`, `orders`, and entry tag counts read-only;
- check resource pressure;
- do not modify strategy/config;
- do not make replacement or profitability conclusions.
