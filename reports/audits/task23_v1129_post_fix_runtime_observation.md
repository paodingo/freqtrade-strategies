# Task 23: V11.29 Post-Fix Runtime Observation

## Summary

Task 23 对 Task 22F/22V/22X 之后的 V11.29 运行状态做了只读观察。

结论：

- `freqtrade-v1129` container: `Up`
- `freqtrade-v1129` bot state: observed `RUNNING`
- `freqtrade-v1082`: remained `Up`, not touched
- post-fix observation window did not show `Strategy analysis took ...`
- V11.29 SQLite still shows `trades=0`, `orders=0`
- 4h DataProvider warning still exists earlier in the post-start window
- 当前仍不能判断 V11.29 可以替换 V10.8.2

This task did not modify strategy code, bot config, dashboard, deploy scripts, SQLite, or server files.

## Preconditions

Local gate:

```text
path: D:\code\freqtrade-strategies-clean
branch: codex/btc-mvp-system-harnessed
git status --short: clean
readiness: pass
```

## Server Observation Window

Server:

```text
hostname: VM-0-8-ubuntu
first observation: Fri Jul  3 03:55:17 PM UTC 2026
second observation: Fri Jul  3 03:58:32 PM UTC 2026
```

Container state:

```text
freqtrade-v1129   Up 25-28 minutes   127.0.0.1:8122->8122/tcp
freqtrade-v1082   Up 3 days          127.0.0.1:8091->8091/tcp
```

## Runtime State Evidence

V11.29 entered `RUNNING` after Task 22X:

```text
2026-07-03 15:42:40,620 - freqtrade.rpc.rpc_manager - INFO - Sending rpc message: {'type': status, 'status': 'running'}
2026-07-03 15:43:12,142 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
```

Stable heartbeats observed through the Task 23 window:

```text
2026-07-03 15:54:27,746 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-03 15:55:27,749 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-03 15:56:27,752 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-03 15:57:27,754 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
2026-07-03 15:58:27,757 - freqtrade.worker - INFO - Bot heartbeat. PID=1, version='2026.5.1', state='RUNNING'
```

## Performance Warning Observation

In the observed post-fix window, logs did not show:

```text
Strategy analysis took ...
Traceback
```

This is a short-window observation only. It suggests the bounded 4h lookback did not immediately reproduce the prior 225s analysis warning, but it is not yet a long-running performance proof.

## Remaining 4h Warning

The post-start window still showed the known DataProvider 4h warning:

```text
No data found for (BTC/USDT:USDT, 4h, ).
No data found for (ETH/USDT:USDT, 4h, ).
No data found for (SOL/USDT:USDT, 4h, ).
...
No data found for (BCH/USDT:USDT, 4h, ).
```

This warning was observed around `15:42-15:45 UTC`, before the later stable heartbeat-only window.

Interpretation:

- Task 22F addressed the full-history 4h regime calculation cost.
- It did not address the Freqtrade DataProvider lookup of `(pair, 4h, empty candle type)`.
- The warning should be handled separately as a candle type mapping / fallback cleanup task.

## SQLite Evidence

Read-only SQLite counts:

```text
trades=0
orders=0
```

This was observed in both Task 23 checks and remains an insufficient execution sample.

This does not prove strategy failure. It only proves no dry-run trades/orders have been written to the V11.29 SQLite snapshot during the checked window.

## Resource Snapshot

Point-in-time sample:

```text
freqtrade-v1129 10.22% 211.4MiB / 1.922GiB
freqtrade-v1082 0.15% 429.6MiB / 1.922GiB
```

The sample is not a full benchmark. It is only included as runtime context.

## What This Task Did Not Do

This task did not:

- modify `strategies/**`;
- modify `user_data/**`;
- modify `configs/**`;
- modify `dashboard/**`;
- modify `deploy/**`;
- read `.env`;
- read `user_data/monitor.env`;
- print or copy secrets;
- start, stop, or restart bots;
- run backtests;
- change pairlist, stake, leverage, ROI, stoploss, or protections;
- claim V11.29 can replace V10.8.2.

## Current Assessment

Observed:

- V11.29 is running.
- The immediate 225s analysis warning did not recur in the short post-fix window.
- V11.29 still has zero trades/orders.
- The 4h DataProvider warning remains a separate issue.

Derived:

- Task 22F likely reduced the most obvious performance bottleneck enough for the bot to remain responsive in this short window.
- Execution validation remains `insufficient`.

Unknown:

- Whether the analysis warning remains absent over a 1h / 4h / 24h window.
- Whether no trades/orders is caused by signal logic, market conditions, protection filters, or another runtime condition.
- Whether fixing the 4h DataProvider warning will affect signal generation.

## Recommended Next Tasks

Recommended next task:

```text
Task 24: V11.29 4h Candle Type Mapping Fix Plan
```

Goal:

- Plan how to remove or correct the `(pair, 4h, empty candle type)` DataProvider lookup without changing trading rules.

Then:

```text
Task 25: V11.29 Longer Runtime Evidence Window
```

Goal:

- Observe a longer runtime window for trades/orders and performance warnings after the 4h warning fix decision.

