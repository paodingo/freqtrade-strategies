# Task 24W: Authorized V11.29 Post-Mapping Start and Fresh 4h Warning Observation

## Summary

本任务按用户授权，使用 credential-safe 路径启动 `freqtrade-v1129`，并观察 Task 24F/24V 部署后的 fresh runtime window。

结果：

- authenticated `/api/v1/start` returned `HTTP_STATUS=200`
- `freqtrade-v1129` observed `RUNNING`
- `freqtrade-v1129` API endpoints all returned `200`
- fresh observation window did not show `No data found for (..., 4h, )`
- fresh observation window did not show `Strategy analysis took ...`
- V11.29 SQLite still shows `trades=0`, `orders=0`
- `freqtrade-v1082` remained untouched and healthy

This task did not print secrets, modify configs, modify strategies, restart bots, or run backtests.

## Authorization Scope

The user authorized the previously validated credential-safe path.

Credential source used only in memory:

```text
freqtrade-v1129:/freqtrade/project/user_data/config_multi_futures_v1129.json
```

Fields read:

```text
api_server.username
api_server.password
```

No secret values were printed or written to this report.

## Server Context

```text
hostname: VM-0-8-ubuntu
date -u before start: Mon Jul  6 03:53:28 AM UTC 2026
```

Container state before start:

```text
freqtrade-v1129   Up 2 days   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 5 days   127.0.0.1:8091->8091/tcp
```

## Start Result

Authenticated start:

```text
POST http://127.0.0.1:8122/api/v1/start
HTTP_STATUS=200
CURL_EXIT=0
```

Observed running transition:

```text
2026-07-06 03:53:30,697 - freqtrade.rpc.rpc_manager - INFO - Sending rpc message: {'type': status, 'status': 'running'}
2026-07-06 03:54:34,613 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-06 03:55:34,619 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-06 03:56:34,623 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-06 03:57:34,643 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
```

## Fresh 4h Warning Observation

Fresh observation window after start did not show:

```text
No data found for (..., 4h, )
4h data unavailable
Strategy analysis took ...
Traceback
```

Observed startup and whitelist:

```text
2026-07-06 03:53:51,125 - freqtrade.plugins.pairlistmanager - INFO - Whitelist with 12 pairs
```

Interpretation:

- The Task 24F informative futures mapping fix appears to remove the prior fresh-cycle `(pair, 4h, empty candle type)` warning in this short observation window.
- This is not yet long-window proof.

## API Health

After start, V11.29 API:

```text
ping=200
show_config=200
count=200
profit=200
status=200
```

V11.29 SQLite:

```text
trades=0
orders=0
```

This remains insufficient execution evidence and does not prove strategy failure.

## Dashboard Lane Health Check

After V11.29 start:

```text
base_v1116 localhost:8109: all endpoints failed to connect
benchmark_v1082 localhost:8091: ping/show_config/count/profit/status all 200
scout_v1127 localhost:8120: all endpoints failed to connect
extra_v1129 localhost:8122: ping/show_config/count/profit/status all 200
```

Container reality:

```text
freqtrade-v1129 Up
freqtrade-v1082 Up
freqtrade-v1127 Exited
freqtrade-v1116 Exited
```

This explains why the web dashboard appears to only have V10.8.2 normal: the dashboard still includes stopped historical lanes `V11.16` and `V11.27`, while V11.29 is only configured as an extra scout lane.

## Boundary Confirmation

This task did not:

- print API credentials;
- read `.env`;
- read `user_data/monitor.env`;
- modify bot config;
- modify strategy code;
- restart `freqtrade-v1082`;
- restart `freqtrade-v1129`;
- touch `freqtrade-v1127` or `freqtrade-v1116`;
- run backtests;
- claim V11.29 replacement readiness.

## Current Assessment

Observed:

- V11.29 is running and API-healthy.
- V10.8.2 is running and API-healthy.
- Stopped historical lanes still referenced by dashboard are unhealthy by design.
- The fresh V11.29 4h warning was not observed after the mapping fix and start.
- V11.29 still has zero trades/orders.

Unknown:

- Whether no 4h warning remains absent over a longer window.
- Whether V11.29 will generate trades/orders.
- Whether dashboard should make V11.29 a primary lane or keep it scout-only.

## Recommended Next Task

Recommended next task:

```text
Task 25: Dashboard Runtime Topology Repair Plan
```

Goal:

- Update the dashboard topology plan so current visible lanes match actual running bots:
  - V11.29 on `8122`
  - V10.8.2 on `8091`
- Remove or mark stopped V11.16 / V11.27 lanes as historical.
- Do not restart bots or modify strategy/config in the planning task.

Follow-up:

```text
Task 26: Trade Monitor Alert Debounce Plan
```

Goal:

- Reduce noisy Telegram `API 异常` alerts by requiring retries or consecutive failures before alerting.

