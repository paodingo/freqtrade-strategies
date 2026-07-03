# Task 22V: Deploy V11.29 4h Performance Fix to Server

## Summary

Task 22V 已执行受控部署：将 Task 22F 中的 `strategies/regime_aware_base.py` 4h bounded lookback 修复同步到服务器 `freqtrade-v1129` 容器，并只重启了 `freqtrade-v1129`。

部署结果：

- `freqtrade-v1129` container: `Up`
- `freqtrade-v1082` container: 保持运行，未重启
- V11.29 策略文件 hash 已与本地一致
- Freqtrade 内部 bot state: `STOPPED`
- V11.29 SQLite: `trades=0`, `orders=0`
- 当前不能观察性能修复后的真实 analysis 周期，因为 trader 未运行

本任务没有读取 `.env`、`user_data/monitor.env`、API key、交易所凭证、服务器密钥或 dashboard 密码。

## Local Context

- Clean worktree path: `D:\code\freqtrade-strategies-clean`
- Branch: `codex/btc-mvp-system-harnessed`
- Source commit before deployment: `63404ed`
- Local source file: `strategies/regime_aware_base.py`
- Local SHA256:

```text
f9c3a4bca25d8b94163901364a7362bd61e12f7f8c5bc28603021dd47e9323ce
```

## Server Evidence

Server identity:

```text
hostname: VM-0-8-ubuntu
date -u: Fri Jul  3 03:29:12 PM UTC 2026
```

Pre-deploy container state:

```text
freqtrade-v1129   Up 6 hours   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days    127.0.0.1:8091->8091/tcp
```

Pre-deploy target file:

```text
/freqtrade/project/strategies/regime_aware_base.py
size: 16K
sha256: 6f174a7ee310f845974d4899f873ad24a1b9afe2cb9e19c765202fd7a4dd45bc
```

## Backup

Before overwrite, the existing V11.29 container file was copied inside the container:

```text
/tmp/codex-task22v/regime_aware_base.py.before-task22v-20260703-232929
sha256: 6f174a7ee310f845974d4899f873ad24a1b9afe2cb9e19c765202fd7a4dd45bc
```

No bot config or secret file was backed up or read.

## Deployment Action

Uploaded one local file to server temp directory:

```text
/tmp/codex-task22v-20260703-232929/regime_aware_base.py
sha256: f9c3a4bca25d8b94163901364a7362bd61e12f7f8c5bc28603021dd47e9323ce
```

Copied into V11.29 container:

```text
freqtrade-v1129:/freqtrade/project/strategies/regime_aware_base.py
```

Post-copy target file:

```text
/freqtrade/project/strategies/regime_aware_base.py
size: 16K
owner: ftuser:1001
sha256: f9c3a4bca25d8b94163901364a7362bd61e12f7f8c5bc28603021dd47e9323ce
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
- any backtest
- any bot config edit
- any strategy edit on server other than the single deployed file

Post-restart container state:

```text
freqtrade-v1129   Up About a minute   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days           127.0.0.1:8091->8091/tcp
```

## Log Findings

Post-restart logs confirm:

```text
Runmode set to dry_run.
Using DB: "sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite"
Instance is running with dry_run enabled
Using resolved strategy RegimeAwareV1129ResidualDragMicroSizer
Whitelist with 12 pairs
```

But the bot entered stopped state:

```text
2026-07-03 15:30:15,586 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='STOPPED'
2026-07-03 15:30:52,701 - freqtrade.rpc.api_server.webserver - ERROR - API Error calling: trader is not running
2026-07-03 15:31:15,593 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='STOPPED'
```

No post-deploy `Strategy analysis took ...` observation is available yet because trader is not running.

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

The deployed code is present, but `freqtrade-v1129` is currently not trading because internal state is `STOPPED`.

Starting the bot through API or another control surface is a separate high-risk live/server operation. This task did not perform it automatically.

## Recommended Next Task

Recommended next task:

```text
Task 22W: V11.29 Post-Deploy Start Authorization and Runtime Observation
```

Suggested scope:

1. Explicitly authorize starting only `freqtrade-v1129`.
2. Use the safest available control path without reading secrets.
3. Confirm internal state changes from `STOPPED` to `RUNNING`.
4. Observe logs for at least one analysis cycle.
5. Check whether `Strategy analysis took ...` warnings disappear.
6. Keep V10.8.2 running as benchmark and do not restart it.

