# Task 50: V11.29 Ranging-Short Shadow Start Readiness and Resource Gate

## Summary

Performed a read-only start readiness and resource gate for the V11.29
ranging-short shadow bot.

Decision:

```text
do not start the shadow bot in Task 50
```

Reasons:

1. Task 50 did not explicitly authorize starting a new bot.
2. The shadow config is safe/dry-run, but `api_server.enabled` is currently
   `false`, so the planned `8123` API monitoring surface would not exist after
   start.
3. Server memory improved compared with Task 48, but swap usage is still high
   at `3.3GiB`.
4. Starting a third Freqtrade process should be a separate explicitly
   authorized task with a clear API/monitoring decision.

This task did not start, stop, or restart any bot. It did not run
`freqtrade trade`, did not run backtests, did not read env files, did not read
secrets, and did not modify server files.

## Local Preconditions

```text
cwd: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status before task: clean
readiness before task: pass
```

## Server Evidence

```text
host: 43.134.72.69
user: ubuntu
hostname: VM-0-8-ubuntu
server time: 2026-07-07T03:08:57+08:00
```

Running containers:

| Container | Image | Status | Port |
| --- | --- | --- | --- |
| `freqtrade-v1129` | `freqtradeorg/freqtrade:stable` | `Up 3 days` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1082` | `freqtradeorg/freqtrade:stable` | `Up 6 days` | `127.0.0.1:8091->8091/tcp` |

No existing container was restarted or stopped.

## File Readiness

Server files exist:

```text
/home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
/home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Server SHA256:

```text
25ea45add7ff254816da3f06a28c0c4fe7005fe4b4c110cd39de5a0e1b4b8d70  /home/ubuntu/freqtrade-strategies/strategies/RegimeAwareV1129RangingShortShadow.py
285801915aea45e6a48e9528bce0910bb42f923d7e27db973a8d490ef2033d4f  /home/ubuntu/freqtrade-strategies/user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

Strategy syntax:

```text
python3 -m py_compile: pass
```

## Config Sanity

Observed selected config fields:

```text
strategy: RegimeAwareV1129RangingShortShadow
dry_run: true
db_url: sqlite:////freqtrade/project/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite
api_server.enabled: false
api_server.listen_port: 8123
pair_whitelist: ETH/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, BCH/USDT:USDT, XRP/USDT:USDT
```

Interpretation:

- dry-run boundary is correct;
- strategy name is correct;
- DB path is isolated from V10.8.2 and current V11.29;
- pair allowlist matches Task 44/45;
- API port is configured but API is disabled, so web/API monitoring on `8123`
  would not work unless a later task explicitly patches the config.

## Port Readiness

```text
port 8123 listener: none observed
```

The port appears available, but is not reserved.

## Shadow DB State

No existing shadow DB files observed:

```text
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite: missing
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite-wal: missing
/home/ubuntu/freqtrade-strategies/user_data/tradesv3_v1129_ranging_short_shadow.dryrun.sqlite-shm: missing
```

This task did not create SQLite files.

## Resource Gate

Memory:

```text
total: 1.9Gi
used: 1.4Gi
free: 351Mi
available: 490Mi
swap total: 5.9Gi
swap used: 3.3Gi
swap free: 2.7Gi
```

Disk:

```text
filesystem: /dev/vda2
size: 50G
used: 25G
available: 23G
use: 54%
```

Container snapshot:

| Container | CPU | Memory | Memory % |
| --- | --- | --- | --- |
| `freqtrade-v1129` | `0.14%` | `98.69MiB / 1.922GiB` | `5.02%` |
| `freqtrade-v1082` | `5.22%` | `145MiB / 1.922GiB` | `7.37%` |

Interpretation: memory is better than Task 48, but the server is still under
swap pressure. A third bot should not be started without a deliberate
resource/start authorization.

## Server Git Status For Exact Paths

```text
?? strategies/RegimeAwareV1129RangingShortShadow.py
?? user_data/config_multi_futures_v1129_ranging_short_shadow.json
```

No server commit was made.

## Start Gate Decision

```text
start_ready_files: yes
start_ready_port: yes
start_ready_config_dry_run: yes
start_ready_api_monitoring: no
start_ready_resources: caution
start_authorized_by_task: no
final_decision: defer start
```

## Explicit Non-Actions

This task did not:

- start the shadow bot;
- stop or restart existing bots;
- run `freqtrade trade`;
- run backtests;
- create or write SQLite;
- read `.env`;
- read `user_data/monitor.env`;
- print or copy credentials;
- modify server files;
- modify strategies;
- modify bot configs;
- commit the server worktree.

## Recommended Task 51

Recommended next task:

```text
Task 51: V11.29 Ranging-Short Shadow API/Start Decision
```

Task 51 should explicitly decide one of these paths:

1. start shadow bot with API disabled and observe only SQLite/log evidence;
2. patch the shadow config to enable local-only API monitoring on `127.0.0.1:8123`;
3. defer start until memory/swap pressure is reduced.

If Task 51 authorizes start, it must include:

- exact command;
- exact container name;
- exact config path;
- exact API decision;
- memory/swap re-check immediately before start;
- no changes to V10.8.2 or current V11.29 unless separately authorized.
