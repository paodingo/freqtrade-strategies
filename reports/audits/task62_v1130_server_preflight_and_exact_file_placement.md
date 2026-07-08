# Task 62: V11.30 Server Preflight And Exact File Placement

## Summary

Completed V11.30 server preflight and exact file placement for the crash-rebound
shadow strategy. The V11.30 strategy and dry-run config were copied to the
server repo as two exact files only.

This task did not start, stop, or restart any bot. It did not read `.env`,
`user_data/monitor.env`, API keys, exchange credentials, server keys, dashboard
passwords, or tokens.

## Local Preconditions

- local directory: `D:\code\freqtrade-strategies-clean`
- branch: `codex/btc-mvp-system-harnessed`
- starting commit: `fc0249d`
- local `git status --short --untracked-files=all`: clean
- readiness check before server work: passed

## Server Access

- host: `43.134.72.69`
- user: `ubuntu`
- key path used: `D:\key\openclaw\clf.pem`

The key file content was not read or printed.

## Server Preflight Evidence

Read-only commands used:

```bash
hostname
date -Is
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
free -h
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
test -d /home/ubuntu/freqtrade-strategies
test -d /home/ubuntu/freqtrade-strategies/strategies
test -d /home/ubuntu/freqtrade-strategies/user_data
test -f /home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1130CrashReboundShadow.py
test -f /home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1130_crash_rebound_shadow.json
```

Observed server:

- hostname: `VM-0-8-ubuntu`
- server date: `2026-07-08T10:43:49+08:00`
- repo: `/home/ubuntu/freqtrade-strategies` exists
- target strategy dir: exists
- target user_data dir: exists
- V11.30 strategy before copy: missing
- V11.30 config before copy: missing

Running containers before placement:

| Container | Status | Ports |
|---|---|---|
| `freqtrade-v1129-ranging-short-shadow` | `Up 31 hours` | none shown |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Resource snapshot:

| Resource | Observed |
|---|---|
| memory total | `1.9Gi` |
| memory used | `1.7Gi` |
| memory free | `82Mi` |
| memory available | `232Mi` |
| swap total | `5.9Gi` |
| swap used | `3.0Gi` |

Container memory snapshot:

| Container | CPU | Memory |
|---|---:|---:|
| `freqtrade-v1129-ranging-short-shadow` | `0.00%` | `232.1MiB / 1.922GiB` |
| `freqtrade-v1129` | `0.14%` | `292.5MiB / 1.922GiB` |

Interpretation:

- exact file placement is acceptable;
- starting a third bot is not acceptable from this task because available memory
  is only about `232MiB` and swap is already about `3.0GiB` used.

## Exact Files Placed

Copied exactly:

| Local source | Server target |
|---|---|
| `strategies/RegimeAwareV1130CrashReboundShadow.py` | `/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1130CrashReboundShadow.py` |
| `user_data/config_multi_futures_v1130_crash_rebound_shadow.json` | `/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1130_crash_rebound_shadow.json` |

No directories were recursively copied.

## Hash Verification

Local hashes:

| File | SHA256 |
|---|---|
| `strategies/RegimeAwareV1130CrashReboundShadow.py` | `1582603D55FF9FA97721E0496D0CB896526EC9EF0BAFF5640544330235676701` |
| `user_data/config_multi_futures_v1130_crash_rebound_shadow.json` | `3B8FF99D2F48ED39172576CD1FBF97C83A1653D3FF9F574DE85B3CC4CA9B208F` |

Server hashes:

| File | SHA256 |
|---|---|
| `/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1130CrashReboundShadow.py` | `1582603d55ff9fa97721e0496d0cb896526ec9ef0baff5640544330235676701` |
| `/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1130_crash_rebound_shadow.json` | `3b8ff99d2f48ed39172576cd1fbf97c83a1653d3ff9f574de85b3cc4ca9b208f` |

Result:

- hashes match.

## Server Post-Placement Evidence

Server file sizes:

- strategy: `7.0K`
- config: `1.1K`

Config JSON check:

- `python3 -m json.tool ...`: `config_json_ok`

Running containers after placement:

| Container | Status | Ports |
|---|---|---|
| `freqtrade-v1129-ranging-short-shadow` | `Up 31 hours` | none shown |
| `freqtrade-v1129` | `Up 4 days` | `127.0.0.1:8122->8122/tcp` |

Server repo status for exact placed paths:

```text
?? strategies/RegimeAwareV1130CrashReboundShadow.py
?? user_data/config_multi_futures_v1130_crash_rebound_shadow.json
```

The server repo was not committed.

## Non-Actions

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print or copy API keys, exchange credentials, server keys, dashboard
  passwords, or tokens;
- run `docker inspect`;
- start, stop, or restart any container;
- run `docker start`, `docker stop`, `docker restart`;
- run `freqtrade trade`;
- run a backtest;
- write to any SQLite database;
- modify dashboard or deploy files;
- modify strategy/config files other than the two exact V11.30 placement targets;
- modify the original dirty workspace.

## Start Decision

Do not start V11.30 in this task.

Reason:

- available memory is low (`232Mi`);
- swap is already materially used (`3.0Gi / 5.9Gi`);
- `freqtrade-v1129` and `freqtrade-v1129-ranging-short-shadow` are already
  running;
- Task 62 was authorized for preflight and exact placement, not bot start.

## Recommended Next Task

Recommended next task:

```text
Task 63: V11.30 Runtime Resource Decision And Shadow Start Authorization
```

Recommended scope:

- decide whether to stop `freqtrade-v1129-ranging-short-shadow` before starting
  V11.30;
- re-check `free -h` and `docker stats --no-stream`;
- start only one V11.30 dry-run shadow container if resources are acceptable;
- keep `freqtrade-v1129` untouched unless explicitly authorized;
- record first runtime evidence without making replacement or profitability
  claims.
