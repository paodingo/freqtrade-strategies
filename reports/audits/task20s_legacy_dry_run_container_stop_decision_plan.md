# Task 20S: Legacy Dry-Run Container Stop Decision Plan

状态：已完成。只读审查 legacy dry-run 容器是否可以停止；未停止、重启或删除任何服务器容器。

## Summary

服务器资源有限，当前同时运行 `freqtrade-v1129`、`freqtrade-v1127`、`freqtrade-v1116`、`freqtrade-v1082`。本任务只读检查 legacy 容器 `freqtrade-v1116` 和 `freqtrade-v1127` 的资源占用、open trades/orders、日志、dashboard 代码引用。

结论：

- `freqtrade-v1127` 是最安全的停止候选：DB 中 `trades = 0`、`orders = 0`、`open_trades = 0`、`open_orders = 0`，dashboard 代码未发现直接引用。
- `freqtrade-v1116` 不建议直接停止：虽然当前 `open_trades = 0`、`open_orders = 0`，但 dashboard 默认配置仍指向 `v1116` / `8109`，并且该容器资源占用最高。停它前应先确认 dashboard 环境变量是否已经覆盖默认值，或先迁移 dashboard 默认引用。
- `freqtrade-v1129` 不应停止：它是当前 V11.29 观察对象。
- `freqtrade-v1082` 不应停止：它仍是 V10.8.2 benchmark evidence 来源。

## Boundary confirmation

本任务只执行只读操作：

- `docker ps --format ...`
- `docker stats --no-stream --format ...`
- `docker logs --tail ...`
- `docker exec ... python sqlite3 read-only query`
- `grep -RInE ... dashboard`

本任务没有：

- 执行 `docker stop`
- 执行 `docker start`
- 执行 `docker restart`
- 执行 `docker rm`
- 执行 `freqtrade trade`
- 运行回测
- 读取 `.env`
- 读取 `user_data/monitor.env`
- 运行 `docker inspect`
- 修改服务器文件
- 修改策略或 bot 配置
- 修改 dashboard
- 修改 deploy
- 修改原始脏工作区

## Server evidence

服务器：

```text
host: VM-0-8-ubuntu
date: 2026-07-03T22:13:38+08:00
```

运行容器：

| Container | Status | Port |
|---|---|---|
| `freqtrade-v1129` | `Up 5 hours` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1127` | `Up 5 hours` | `127.0.0.1:8120->8120/tcp` |
| `freqtrade-v1116` | `Up 2 days` | `127.0.0.1:8109->8109/tcp` |
| `freqtrade-v1082` | `Up 3 days` | `127.0.0.1:8091->8091/tcp` |

## Resource snapshot

`docker stats --no-stream` observed:

| Container | CPU | Memory | Memory % | PIDs |
|---|---:|---:|---:|---:|
| `freqtrade-v1129` | `0.13%` | `88.64MiB / 1.922GiB` | `4.50%` | `9` |
| `freqtrade-v1127` | `0.14%` | `83.9MiB / 1.922GiB` | `4.26%` | `9` |
| `freqtrade-v1116` | `6.48%` | `442MiB / 1.922GiB` | `22.46%` | `14` |
| `freqtrade-v1082` | `7.31%` | `131.1MiB / 1.922GiB` | `6.66%` | `14` |

Interpretation:

- `freqtrade-v1116` is the clearest resource pressure target by memory usage.
- `freqtrade-v1127` has low resource usage but appears unnecessary based on current evidence.
- `freqtrade-v1082` had non-trivial CPU in this snapshot but remains benchmark evidence.

## Legacy DB evidence

Read-only SQLite query via Python inside container:

| Container | DB | Size | Trades | Orders | Open trades | Open orders | Latest open | Latest close |
|---|---|---:|---:|---:|---:|---:|---|---|
| `freqtrade-v1116` | `tradesv3_v1116.dryrun.sqlite` | `94208` | `1` | `2` | `0` | `0` | `2026-07-02 00:35:24.207965` | `2026-07-02 03:52:16.763000` |
| `freqtrade-v1127` | `tradesv3_v1127.dryrun.sqlite` | `94208` | `0` | `0` | `0` | `0` | `-` | `-` |

Observed meaning:

- Stopping `freqtrade-v1127` would not interrupt open trades or open orders based on current DB.
- Stopping `freqtrade-v1116` would not interrupt open trades or open orders based on current DB, but it may affect dashboard defaults.

## Log findings

`freqtrade-v1116` recent logs show:

- repeated `Bot heartbeat ... state='RUNNING'`
- repeated `No data found for (..., 4h, )`
- no stop/restart action was taken in this task

`freqtrade-v1127` recent logs show:

- repeated `Bot heartbeat ... state='RUNNING'`
- no recent trade/order evidence from DB
- no stop/restart action was taken in this task

## Dashboard reference findings

Targeted read-only grep under `dashboard` found:

```text
dashboard/lib/config.js: const BASE_KEY = process.env.BOT_BASE_KEY || process.env.BOT_PRIMARY_KEY || "v1116";
dashboard/lib/config.js: const BASE_URL = process.env.BOT_BASE_URL || process.env.BOT_PRIMARY_URL || "http://localhost:8109";
```

This means `freqtrade-v1116` may still be the dashboard default if environment variables do not override it. This task did not read `user_data/monitor.env`, so it cannot prove the currently running monitor has overridden those defaults.

No targeted dashboard code reference to `v1127` / `8120` was observed.

## Stop recommendation

Recommended stop order if the user explicitly authorizes a future stop task:

1. `freqtrade-v1127`
   - Reason: no trades/orders/open state, no dashboard code reference found, not part of current V11.29 vs V10.8.2 evidence chain.

2. `freqtrade-v1116`, only after dashboard dependency is resolved
   - Reason: high resource usage and no open trades/orders, but dashboard defaults still reference it.
   - Required precondition: confirm monitor env overrides `BOT_BASE_URL` / `BOT_PRIMARY_URL`, or update dashboard plan so stopping `8109` will not break the dashboard default view.

Do not stop in the same task:

- `freqtrade-v1129`: active V11.29 observation target.
- `freqtrade-v1082`: current V10.8.2 benchmark evidence source.

## Explicit command draft for a future authorized stop task

Do not execute these without explicit user authorization:

```bash
docker stop freqtrade-v1127
docker ps --format '{{.Names}}|{{.Status}}|{{.Ports}}'
```

For `freqtrade-v1116`, use only after dashboard dependency is resolved:

```bash
docker stop freqtrade-v1116
docker ps --format '{{.Names}}|{{.Status}}|{{.Ports}}'
```

No `docker rm` is recommended in the first stop task. Stop first, observe dashboard and V11.29/V10.8.2 behavior, then decide separately whether removal is needed.

## Recommended next task

推荐 `Task 20S-STOP1: Stop legacy freqtrade-v1127 dry-run container`。

Scope:

- only stop `freqtrade-v1127`;
- do not stop `freqtrade-v1116`, `freqtrade-v1129`, or `freqtrade-v1082`;
- after stopping, verify `docker ps`, dashboard availability, and V11.29/V10.8.2 still running;
- generate an audit record;
- do not remove container or delete DB.

After that, run a separate dashboard dependency check before deciding whether to stop `freqtrade-v1116`.

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task20s_legacy_dry_run_container_stop_decision_plan.md
tasks/active/TASK-0020S-legacy-dry-run-container-stop-decision-plan.md
```
