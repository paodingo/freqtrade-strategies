# Task 20: V11.29 Data Coverage and Runtime Performance Audit

状态：已完成。只读审计服务器上的 V11.29 数据覆盖、运行性能和资源占用；未启动、停止、重启任何 bot。

## Summary

当前服务器资源有限，且实际运行的 Freqtrade 容器不止 V11.29 / V10.8.2。只读检查显示服务器上同时运行：

- `freqtrade-v1129`
- `freqtrade-v1127`
- `freqtrade-v1116`
- `freqtrade-v1082`

`freqtrade-v1129` 仍是当前真实执行验证对象，但目前 trades/orders 仍为 0。`freqtrade-v1082` 仍是 benchmark evidence 来源。`freqtrade-v1127` / `freqtrade-v1116` 是否仍有必要继续运行，需要进入单独的停止决策任务；本任务不停止它们。

结论：现在不建议直接停止 `freqtrade-v1082`，因为它仍承担 V10.8.2 benchmark / same-window reference 的角色。可以优先考虑对 `freqtrade-v1116` 和 `freqtrade-v1127` 做 `Task 20S: Legacy Dry-Run Container Stop Decision Plan`，只读确认它们是否还有未迁移证据、dashboard 依赖或实验价值，再由人工授权停止。

## Execution boundary

本任务只执行只读检查：

- `hostname`
- `date -Is`
- `docker ps --format ...`
- `docker stats --no-stream --format ...`
- `df -h`
- `docker logs --tail ...`
- `docker exec ... ls/find` 路径存在性和数据文件名检查

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
- 修改原始脏工作区

## Server/container evidence

服务器：

```text
host: VM-0-8-ubuntu
date: 2026-07-03T22:07:28+08:00
```

运行容器：

| Container | Status | Port |
|---|---|---|
| `freqtrade-v1129` | `Up 5 hours` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1127` | `Up 5 hours` | `127.0.0.1:8120->8120/tcp` |
| `freqtrade-v1116` | `Up 2 days` | `127.0.0.1:8109->8109/tcp` |
| `freqtrade-v1082` | `Up 3 days` | `127.0.0.1:8091->8091/tcp` |

## Runtime resource snapshot

`docker stats --no-stream` observed:

| Container | CPU | Memory | Memory % | PIDs |
|---|---:|---:|---:|---:|
| `freqtrade-v1129` | `16.05%` | `90.36MiB / 1.922GiB` | `4.59%` | `9` |
| `freqtrade-v1127` | `0.16%` | `90.15MiB / 1.922GiB` | `4.58%` | `14` |
| `freqtrade-v1116` | `13.26%` | `360MiB / 1.922GiB` | `18.30%` | `19` |
| `freqtrade-v1082` | `0.16%` | `116.7MiB / 1.922GiB` | `5.93%` | `19` |

Disk:

```text
/dev/vda2 50G total, 25G used, 23G available, 53% used
```

Interpretation:

- `freqtrade-v1116` is the clearest resource pressure candidate: it used the most memory and non-trivial CPU in this snapshot.
- `freqtrade-v1129` also showed non-trivial CPU during the snapshot, consistent with prior `Strategy analysis took ...` warnings.
- `freqtrade-v1127` and `freqtrade-v1082` were low CPU in this snapshot, but still consume memory.
- Disk is not the immediate bottleneck in this snapshot.

## V11.29 data coverage evidence

Path existence:

```text
/freqtrade/project/user_data/data exists
server-side file count under data maxdepth 5: 62
```

Observed data files include futures 15m / 1h / 4h files for multiple pairs:

```text
/freqtrade/project/user_data/data/futures/BTC_USDT_USDT-15m-futures.feather
/freqtrade/project/user_data/data/futures/BTC_USDT_USDT-1h-futures.feather
/freqtrade/project/user_data/data/futures/BTC_USDT_USDT-4h-futures.feather
/freqtrade/project/user_data/data/futures/ETH_USDT_USDT-15m-futures.feather
/freqtrade/project/user_data/data/futures/ETH_USDT_USDT-4h-futures.feather
/freqtrade/project/user_data/data/futures/SOL_USDT_USDT-15m-futures.feather
/freqtrade/project/user_data/data/futures/SOL_USDT_USDT-4h-futures.feather
/freqtrade/project/user_data/data/futures/BNB_USDT_USDT-15m-futures.feather
/freqtrade/project/user_data/data/futures/BNB_USDT_USDT-4h-futures.feather
/freqtrade/project/user_data/data/futures/XRP_USDT_USDT-15m-futures.feather
/freqtrade/project/user_data/data/futures/XRP_USDT_USDT-4h-futures.feather
/freqtrade/project/user_data/data/futures/DOGE_USDT_USDT-15m-futures.feather
/freqtrade/project/user_data/data/futures/DOGE_USDT_USDT-4h-futures.feather
```

This means the strongest conclusion is not "4h files are completely absent." The better hypothesis is:

- some pair/timeframe files may be stale or incomplete;
- V11.29 pairlist may include pairs not fully covered by current data;
- strategy informative pair naming may not match stored file naming;
- data refresh may not cover all required candle types;
- Freqtrade may be looking for a different market type / datadir mapping;
- runtime analysis may be delayed enough to miss usable signal windows.

## V11.29 runtime warning evidence

Task 19 already observed in V11.29 logs:

```text
No data found for (BTC/USDT:USDT, 4h, ).
No data found for (ETH/USDT:USDT, 4h, ).
No data found for (SOL/USDT:USDT, 4h, ).
No data found for (BNB/USDT:USDT, 4h, ).
No data found for (XRP/USDT:USDT, 4h, ).
No data found for (DOGE/USDT:USDT, 4h, ).
Strategy analysis took 225.62s, more than 25% of the timeframe (225.00s). This can lead to delayed orders and missed signals.
```

Current task confirmed that the server has futures `4h` files for at least those symbols, so the next audit should not blindly download more data. It should first compare:

- strategy pairlist;
- informative timeframe references;
- expected market type and stored file naming;
- file mtime / candle freshness;
- whether current bot has permission/path visibility to those exact files;
- whether 225s analysis time is caused by heavy strategy logic or too many pair/timeframe combinations.

## V11.29 trade/order status

This task relies on Task 17 / Task 18 / Task 19 evidence for SQLite counts:

| Source | V11.29 trades | V11.29 orders | Classification |
|---|---:|---:|---|
| Local snapshot inspection | `0` | `0` | observed |
| Server read-only DB inspection in Task 19 | `0` | `0` | observed |

This remains `insufficient`. It must not be interpreted as strategy failure.

## Can original server programs be stopped?

Short answer: not automatically in this task.

Current recommendation by container:

| Container | Stop recommendation | Reason |
|---|---|---|
| `freqtrade-v1129` | Do not stop now | It is the active V11.29 observation target. Stopping it ends the only current chance to observe whether trades/orders appear. |
| `freqtrade-v1082` | Do not stop yet | It is the V10.8.2 benchmark evidence source. Stop only after deciding same-window comparison no longer needs live reference. |
| `freqtrade-v1127` | Candidate for stop-plan review | It is not part of the current V11.29 vs V10.8.2 evidence chain, but may still contain unreviewed evidence or dashboard dependency. |
| `freqtrade-v1116` | Strong candidate for stop-plan review | It showed the highest memory and meaningful CPU in the snapshot, and is not part of the current core validation chain. |

If server resources must be reduced quickly, the safest next step is not immediate stop, but a narrow stop-decision task:

```text
Task 20S: Legacy Dry-Run Container Stop Decision Plan
```

That task should only read:

- container names/status;
- DB paths and current counts;
- latest logs;
- dashboard references;
- whether snapshot evidence already exists;
- whether any open trades/orders exist.

Then it can recommend an explicit stop order, likely starting with `freqtrade-v1116`, then `freqtrade-v1127`, while preserving V11.29 and V10.8.2 until comparison requirements are settled.

## Blocking gaps

- Need precise file freshness audit for each V11.29 pair/timeframe.
- Need mapping between V11.29 pairlist and available futures files.
- Need reason why Freqtrade logs `No data found` despite visible 4h futures files.
- Need performance bottleneck evidence for the `Strategy analysis took 225.62s` warning.
- Need proof whether `freqtrade-v1116` / `freqtrade-v1127` have open trades/orders before stopping them.
- Need confirmation whether dashboard or monitor expects those legacy containers.

## Recommended next tasks

1. `Task 20S: Legacy Dry-Run Container Stop Decision Plan`
   - Goal: decide whether `freqtrade-v1116` and `freqtrade-v1127` can be stopped safely.
   - Strictly read-only unless user explicitly authorizes stop.

2. `Task 21: V11.29 4h Data Availability Root-Cause Plan`
   - Goal: explain why runtime logs report `No data found` when 4h futures files exist.
   - Do not download or rewrite data until root cause is clear.

3. `Task 22: V11.29 Strategy Analysis Performance Bottleneck Audit`
   - Goal: identify why strategy analysis can reach 225s and whether it risks missed signals.

4. `Task 23: V11.29 Real Trades/Orders Re-observation`
   - Goal: after data/performance fixes or stop decisions, observe whether V11.29 creates real dry-run trades/orders.

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task20_v1129_data_coverage_runtime_performance_audit.md
tasks/active/TASK-0020-v1129-data-coverage-runtime-performance-audit.md
```
