# Task 24V: Deploy V11.29 4h Informative Futures Mapping Fix

## Summary

Task 24V 已执行受控部署：将 Task 24F 中的 `strategies/regime_aware_base.py` 4h futures informative mapping 修复同步到服务器 `freqtrade-v1129` 容器，并只重启了 `freqtrade-v1129`。

部署结果：

- `freqtrade-v1129` container: `Up`
- `freqtrade-v1082` container: 未触碰，保持运行
- server `regime_aware_base.py` hash 已与本地一致
- `freqtrade-v1129` internal bot state after restart: `STOPPED`
- V11.29 SQLite after deploy: `trades=0`, `orders=0`
- 由于 trader 未运行，本任务无法完成 fresh analysis cycle 观察

本任务没有读取 `.env`、`user_data/monitor.env`、API key、交易所凭证、dashboard password 或其他 secret。

## Local Context

```text
path: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
source commit: 9235e96
```

Local source file:

```text
strategies/regime_aware_base.py
```

Local SHA256:

```text
81a572e78f33209b6ec9b493bc469ad3e99c9cca115e21e6993e5e9c45fa87ba
```

## Server Evidence

Server:

```text
hostname: VM-0-8-ubuntu
date -u before deploy: Fri Jul  3 04:32:52 PM UTC 2026
```

Pre-deploy container state:

```text
freqtrade-v1129   Up About an hour   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days          127.0.0.1:8091->8091/tcp
```

Pre-deploy server file:

```text
/freqtrade/project/strategies/regime_aware_base.py
sha256: f9c3a4bca25d8b94163901364a7362bd61e12f7f8c5bc28603021dd47e9323ce
```

## Backup

Before overwrite, the existing V11.29 container file was copied inside the container:

```text
/tmp/codex-task24v/regime_aware_base.py.before-task24v-20260704-003305
sha256: f9c3a4bca25d8b94163901364a7362bd61e12f7f8c5bc28603021dd47e9323ce
```

No bot config or secret file was backed up or read.

## Deployment Action

Uploaded one local file to server temp directory:

```text
/tmp/codex-task24v-20260704-003305/regime_aware_base.py
sha256: 81a572e78f33209b6ec9b493bc469ad3e99c9cca115e21e6993e5e9c45fa87ba
```

Copied into V11.29 container:

```text
freqtrade-v1129:/freqtrade/project/strategies/regime_aware_base.py
```

Post-copy target file:

```text
/freqtrade/project/strategies/regime_aware_base.py
size: 17K
owner: ftuser:1001
sha256: 81a572e78f33209b6ec9b493bc469ad3e99c9cca115e21e6993e5e9c45fa87ba
```

## Restart Scope

Executed:

```text
docker restart freqtrade-v1129
```

Did not execute:

- `docker restart freqtrade-v1082`
- `docker stop freqtrade-v1082`
- `docker start freqtrade-v1082`
- any command against `freqtrade-v1127` or `freqtrade-v1116`
- authenticated `/api/v1/start`
- backtests
- bot config edits

Post-restart container state:

```text
freqtrade-v1129   Up 47 seconds   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days       127.0.0.1:8091->8091/tcp
```

## Log Findings

Post-restart logs confirm startup:

```text
Runmode set to dry_run.
Using DB: "sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite"
Instance is running with dry_run enabled
Using resolved strategy RegimeAwareV1129ResidualDragMicroSizer
Whitelist with 12 pairs
```

But internal bot state is stopped:

```text
2026-07-03 16:33:41,073 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='STOPPED'
2026-07-03 16:33:37,449 - freqtrade.rpc.api_server.webserver - ERROR - API Error calling: trader is not running
2026-07-03 16:34:12,560 - freqtrade.rpc.api_server.webserver - ERROR - API Error calling: trader is not running
```

Because the trader is stopped, this task could not observe a fresh analysis cycle after the Task 24F mapping fix.

## SQLite Evidence

Read-only SQLite count after deployment:

```text
trades=0
orders=0
```

This is an observed database count only. It is not interpreted as strategy failure.

## Boundary Confirmation

This task:

- did not read secret files;
- did not print credentials;
- did not modify bot configs;
- did not modify dashboard;
- did not modify deploy scripts;
- did not run backtests;
- did not touch `freqtrade-v1082`;
- did not claim V11.29 can replace V10.8.2.

## Blocking Issue

The Task 24F code is deployed, but `freqtrade-v1129` is currently not trading because internal state is `STOPPED`.

Starting the bot through authenticated API requires a separate explicit authorization to read or use the API credentials. This task did not perform authenticated start.

## Recommended Next Task

Recommended next task:

```text
Task 24W: Authorized V11.29 Post-Mapping Start and Fresh 4h Warning Observation
```

Suggested scope:

1. Explicitly authorize starting only `freqtrade-v1129`.
2. Use the previously validated credential-safe path or user-provided one-time command.
3. Confirm internal state changes from `STOPPED` to `RUNNING`.
4. Observe at least one fresh analysis cycle.
5. Check whether `No data found for (..., 4h, )` disappears.
6. Check whether any warning now shows `futures` as candle type.
7. Keep `freqtrade-v1082` untouched.

