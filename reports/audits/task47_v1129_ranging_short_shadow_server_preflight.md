# Task 47: V11.29 Ranging-Short Shadow Server Preflight

## Summary

Performed a read-only server preflight for the proposed V11.29 ranging-short
shadow bot.

Result: the shadow bot should not be started yet. Port `8123` appears unused,
but the required shadow strategy/config files are not present inside the
container project path, and the server has very limited memory headroom.

This task did not copy files, did not start/stop/restart any container, did not
run `freqtrade trade`, did not run backtests, did not read env files, and did
not modify server files.

## Local Preconditions

```text
cwd: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
readiness before task: pass
git status before task: clean
```

## Server Access

```text
host: 43.134.72.69
user: ubuntu
provided key path: D:\key\openclaw
actual local key file used: D:\key\openclaw\clf.pem
```

Only key metadata/path was inspected locally. Key contents were not read or
printed.

## Commands Run

Read-only server commands:

```text
hostname
date -Is
docker ps --format ...
ss -ltn | grep ':8123 ' || true
test -d /freqtrade/project
test -e target shadow paths
df -h / /freqtrade/project
free -h
docker stats --no-stream --format ...
docker exec freqtrade-v1129 sh -lc 'pwd; test -d /freqtrade/project; test -e target shadow paths'
docker exec freqtrade-v1082 sh -lc 'pwd; test -d /freqtrade/project; test -e target shadow paths'
```

No `docker inspect` full output was used. No env files were read.

## Server Evidence

```text
hostname: VM-0-8-ubuntu
server time: 2026-07-06T22:04:16+08:00
```

Running containers:

| Container | Image | Status | Port |
| --- | --- | --- | --- |
| `freqtrade-v1129` | `freqtradeorg/freqtrade:stable` | `Up 2 days` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1082` | `freqtradeorg/freqtrade:stable` | `Up 6 days` | `127.0.0.1:8091->8091/tcp` |

## Port Preflight

```text
proposed shadow API port: 8123
observed listener on 8123: none
status: available from this check
```

This does not reserve the port. Re-check immediately before any future start.

## Path Preflight

Host path:

```text
/freqtrade/project: missing on host
```

Container paths:

```text
freqtrade-v1129: /freqtrade/project exists
freqtrade-v1082: /freqtrade/project exists
```

Shadow target files inside containers:

| Path | Status |
| --- | --- |
| `/freqtrade/project/strategies/RegimeAwareV1129RangingShortShadow.py` | missing |
| `/freqtrade/project/user_data/config_multi_futures_v1129_ranging_short_shadow.json` | missing |
| `/freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite` | missing |

Interpretation: server file placement must be solved before any start task.
Because the project path exists inside containers but not on the host, a later
task must identify the actual host bind mount or use an explicitly authorized
container-safe copy method.

## Resource Preflight

Disk:

```text
/dev/vda2 size: 50G
used: 25G
available: 23G
use: 54%
```

Memory:

```text
total: 1.9Gi
used: 1.7Gi
free: 78Mi
available: 247Mi
swap total: 5.9Gi
swap used: 3.0Gi
swap free: 3.0Gi
```

Container memory:

| Container | CPU | Memory | Memory % |
| --- | --- | --- | --- |
| `freqtrade-v1129` | `0.16%` | `132.3MiB / 1.922GiB` | `6.73%` |
| `freqtrade-v1082` | `0.16%` | `525.4MiB / 1.922GiB` | `26.70%` |

Interpretation: disk is acceptable, but memory headroom is tight and swap is
already heavily used. Starting a third Freqtrade container without a resource
decision is not recommended.

## Deployment Readiness

Not ready to deploy/start.

Blocking items:

1. Shadow strategy/config are not present on the server/container project path.
2. Host bind mount location was not identified in this task.
3. Available memory is low and swap usage is high.
4. No explicit authorization exists in this task to copy files or start a
   container.

Non-blocking positive checks:

1. Existing V10.8.2 and V11.29 containers are running.
2. Proposed API port `8123` appeared unused.
3. Container-internal `/freqtrade/project` exists.
4. Disk headroom appears acceptable.

## Explicit Non-Actions

This task did not:

- read `.env`;
- read `user_data/monitor.env`;
- print or copy credentials;
- run full `docker inspect`;
- copy files to the server;
- modify server files;
- start, stop, or restart containers;
- run `freqtrade trade`;
- run backtests;
- write SQLite;
- modify strategies;
- modify bot configs;
- modify dashboard or deploy files;
- modify the original dirty workspace.

## Recommended Task 48

Recommended next task:

```text
Task 48: V11.29 Ranging-Short Shadow File Placement and Resource Decision
```

Task 48 should remain bounded and should decide one of these options before any
start:

1. identify the host bind mount and copy only the two Task 45 files there;
2. use a container-safe exact-file copy method if host bind mount discovery is
   not possible;
3. delay deployment because memory headroom is insufficient;
4. stop no existing bot unless separately and explicitly authorized.

If Task 48 authorizes file copy, it must still not start the shadow bot unless
the task explicitly says so.
