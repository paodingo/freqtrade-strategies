# Task 22X: Authorized V11.29 API Start and Runtime Observation

## Summary

用户选择 Task 22W 推荐路径 2：授权读取一个指定凭证来源，但不打印 secret。

本任务在服务器上只读取 `freqtrade-v1129` 容器内：

```text
/freqtrade/project/user_data/config_multi_futures_v1129.json
```

中的 `api_server.username` 和 `api_server.password`，仅用于内存中构造 Basic Auth 调用：

```text
POST http://127.0.0.1:8122/api/v1/start
```

结果：

- authenticated start returned `HTTP_STATUS=200`
- `freqtrade-v1129` 从 `STOPPED` 进入 `RUNNING`
- `freqtrade-v1082` 未触碰
- 未打印 secret
- 未修改 bot config
- 未修改策略
- 未运行回测
- 观察窗口内未看到 `Strategy analysis took ...` warning
- 仍有 4h DataProvider warning
- V11.29 SQLite 仍为 `trades=0`, `orders=0`

## Local Preconditions

```text
path: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status --short: clean
readiness: pass
```

## Authorization Scope

Explicitly authorized path:

```text
freqtrade-v1129:/freqtrade/project/user_data/config_multi_futures_v1129.json
```

Fields read:

```text
api_server.username
api_server.password
```

Fields not printed:

```text
api_server.username
api_server.password
jwt_secret_key
exchange credentials
dashboard credentials
tokens
```

## Server Evidence

Server:

```text
hostname: VM-0-8-ubuntu
date -u before start: Fri Jul  3 03:42:36 PM UTC 2026
```

Container state before start:

```text
freqtrade-v1129   Up 12 minutes   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days       127.0.0.1:8091->8091/tcp
```

Start result:

```text
HTTP_STATUS=200
CURL_EXIT=0
```

## Runtime State

Observed transition:

```text
2026-07-03 15:42:15,619 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='STOPPED'
2026-07-03 15:42:40,620 - freqtrade.rpc.rpc_manager - INFO - Sending rpc message: {'type': status, 'status': 'running'}
2026-07-03 15:43:12,142 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-03 15:44:12,144 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-03 15:45:27,722 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
```

Post-start container state:

```text
freqtrade-v1129   Up 16 minutes   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days       127.0.0.1:8091->8091/tcp
```

## Performance Observation

During the observed post-start window, logs did not show:

```text
Strategy analysis took ...
Traceback
```

This is an early observation only. It does not prove the performance issue is permanently solved.

The prior 225s warning should be checked again after a longer runtime window.

## Remaining 4h Data Warning

The logs still show repeated 4h DataProvider warnings:

```text
No data found for (BTC/USDT:USDT, 4h, ).
No data found for (ETH/USDT:USDT, 4h, ).
No data found for (SOL/USDT:USDT, 4h, ).
...
No data found for (BCH/USDT:USDT, 4h, ).
```

This matches Task 21A / Task 22 findings: the strategy still calls Freqtrade DataProvider for `(pair, 4h, empty candle type)` before falling back to local futures feather files.

Task 22F fixed bounded lookback cost; it did not fix candle type mapping.

## SQLite Evidence

Read-only SQLite counts after start:

```text
trades=0
orders=0
```

This is an observed query result only. It is not interpreted as strategy failure.

## Resource Snapshot

One observed `docker stats --no-stream` sample:

```text
freqtrade-v1129 0.13% 279.7MiB / 1.922GiB
freqtrade-v1082 5.89% 384.1MiB / 1.922GiB
```

This is a point-in-time sample and should not be treated as a full performance benchmark.

## Boundary Confirmation

This task did not:

- print secrets;
- modify `.env`;
- modify `user_data/monitor.env`;
- modify bot config;
- modify strategy code;
- restart `freqtrade-v1082`;
- stop or restart `freqtrade-v1129`;
- touch `freqtrade-v1127` or `freqtrade-v1116`;
- run backtests;
- produce V11.29 replacement conclusion.

## Current State

Current operational state after this task:

- `freqtrade-v1129`: container up, bot state observed as `RUNNING`
- `freqtrade-v1082`: container up, unchanged benchmark
- V11.29 execution evidence: insufficient, `trades=0`, `orders=0`
- performance warning: not observed in short post-start window
- 4h DataProvider warning: still observed

## Recommended Next Task

Recommended next task:

```text
Task 23: V11.29 Post-Fix Runtime Observation
```

Suggested scope:

1. Observe `freqtrade-v1129` for a longer window.
2. Confirm whether `Strategy analysis took ...` stays absent.
3. Confirm whether `trades/orders` remain 0 or begin appearing.
4. Record 1h / 4h DataProvider warnings.
5. Do not modify strategy or config.

Follow-up if warnings persist:

```text
Task 24: V11.29 4h Candle Type Mapping Fix Plan
```

That task should handle the remaining `No data found for (..., 4h, )` warning separately from the performance fix.

