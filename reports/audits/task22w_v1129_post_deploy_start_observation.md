# Task 22W: V11.29 Post-Deploy Start Authorization and Runtime Observation

## Summary

本任务尝试在不读取 secret 的边界内启动 `freqtrade-v1129`，以便观察 Task 22F / Task 22V 部署后的 4h regime 性能修复效果。

结果：

- `freqtrade-v1129` container: `Up`
- `freqtrade-v1082` container: `Up`，未触碰
- `freqtrade-v1129` internal state: `STOPPED`
- unauthenticated `/api/v1/start`: `401 Unauthorized`
- 未读取 `.env`
- 未读取 `user_data/monitor.env`
- 未读取 API password / token / dashboard password
- 未执行 authenticated start
- 未能进入真实 runtime observation window

因此，本任务没有启动 bot。下一步需要人工提供安全启动方式，或明确授权读取某个指定非打印凭证来源。

## Preconditions Checked

Local clean worktree:

```text
D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status --short: clean
readiness: pass
```

## Server Evidence

Server identity:

```text
hostname: VM-0-8-ubuntu
date -u: Fri Jul  3 03:40:01 PM UTC 2026
```

Container state:

```text
freqtrade-v1129   Up 10 minutes   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days       127.0.0.1:8091->8091/tcp
```

## Start Attempt

Attempted only the unauthenticated local API start endpoint:

```text
POST http://127.0.0.1:8122/api/v1/start
```

Response:

```text
{"detail":"Unauthorized"}
HTTP_STATUS=401
```

No credentialed request was attempted because this task boundary prohibited reading secrets.

## Runtime Logs

Recent V11.29 logs show:

```text
2026-07-03 15:38:15,610 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='STOPPED'
2026-07-03 15:38:52,786 - freqtrade.rpc.api_server.webserver - ERROR - API Error calling: trader is not running
2026-07-03 15:39:15,612 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='STOPPED'
2026-07-03 15:39:52,822 - freqtrade.rpc.api_server.webserver - ERROR - API Error calling: trader is not running
```

No post-start `RUNNING` state was observed because start was not authorized.

## Secret Boundary

This task did not read:

- `.env`
- `user_data/monitor.env`
- bot API password
- dashboard password
- exchange credentials
- server private key content
- token or JWT secret

The SSH private key path was used only by the local SSH client. Its file content was not printed or inspected.

## Operations Not Performed

This task did not:

- restart `freqtrade-v1129`;
- restart `freqtrade-v1082`;
- modify bot config;
- modify strategy files;
- modify dashboard;
- modify deploy scripts;
- run backtests;
- read or write SQLite beyond prior Task 22V evidence;
- claim V11.29 passed execution validation;
- claim V11.29 can replace V10.8.2.

## Blocking Reason

`freqtrade-v1129` requires authenticated API access to transition from `STOPPED` to `RUNNING`.

Without reading the configured API credentials, the agent cannot safely call `/api/v1/start`.

## Recommended Next Task

Recommended next task:

```text
Task 22X: Authorized V11.29 API Start and Runtime Observation
```

Required explicit authorization should choose one safe path:

1. User provides a one-time `curl` command with credentials already embedded and approved for execution.
2. User authorizes reading exactly one specified non-versioned credential source, without printing the secret.
3. User starts `freqtrade-v1129` manually, then agent performs read-only observation.

Task 22X should then verify:

- `freqtrade-v1129` internal state becomes `RUNNING`;
- at least one analysis cycle completes;
- whether `Strategy analysis took ...` warnings persist;
- whether `trades/orders` remain 0;
- no change to `freqtrade-v1082`.

