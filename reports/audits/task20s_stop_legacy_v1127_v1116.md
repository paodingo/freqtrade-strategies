# Task 20S-STOP: Stop Legacy Dry-Run Containers V1127 and V1116

状态：已完成。根据用户明确授权，停止 `freqtrade-v1127` 和 `freqtrade-v1116`。未删除容器，未删除 DB，未修改服务器文件。

## Summary

用户明确授权停止：

- `freqtrade-v1127`
- `freqtrade-v1116`

本任务执行了最小停止操作：

```bash
docker stop freqtrade-v1127 freqtrade-v1116
```

没有执行 `docker rm`，没有删除 SQLite，未修改策略或 bot 配置，未读取 secret。

## Preconditions

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- 停止前 `git status --short --untracked-files=all`：empty
- 停止前 readiness：pass
- Task 20S 已提交并给出停止决策建议
- 用户明确要求：`v1127和v1116，都停`

## Server evidence before stop

服务器：

```text
hostname: VM-0-8-ubuntu
date: 2026-07-03T22:43:18+08:00
```

停止前运行容器：

| Container | Status | Port |
|---|---|---|
| `freqtrade-v1129` | `Up 6 hours` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1127` | `Up 6 hours` | `127.0.0.1:8120->8120/tcp` |
| `freqtrade-v1116` | `Up 2 days` | `127.0.0.1:8109->8109/tcp` |
| `freqtrade-v1082` | `Up 3 days` | `127.0.0.1:8091->8091/tcp` |

停止前资源快照：

| Container | CPU | Memory | Memory % | PIDs |
|---|---:|---:|---:|---:|
| `freqtrade-v1129` | `0.15%` | `82.77MiB / 1.922GiB` | `4.21%` | `9` |
| `freqtrade-v1127` | `0.16%` | `81.78MiB / 1.922GiB` | `4.16%` | `9` |
| `freqtrade-v1116` | `19.22%` | `594.9MiB / 1.922GiB` | `30.23%` | `19` |
| `freqtrade-v1082` | `0.16%` | `149.1MiB / 1.922GiB` | `7.58%` | `18` |

## Stop command

Executed:

```bash
docker stop freqtrade-v1127 freqtrade-v1116
```

Command output:

```text
freqtrade-v1127
freqtrade-v1116
```

## Server evidence after stop

停止后时间：

```text
2026-07-03T22:43:33+08:00
```

停止后仍在运行：

| Container | Status | Port |
|---|---|---|
| `freqtrade-v1129` | `Up 6 hours` | `127.0.0.1:8122->8122/tcp` |
| `freqtrade-v1082` | `Up 3 days` | `127.0.0.1:8091->8091/tcp` |

停止目标状态：

| Container | Status |
|---|---|
| `freqtrade-v1127` | `Exited (137)` |
| `freqtrade-v1116` | `Exited (137)` |

停止后资源快照：

| Container | CPU | Memory | Memory % | PIDs |
|---|---:|---:|---:|---:|
| `freqtrade-v1129` | `0.18%` | `84.05MiB / 1.922GiB` | `4.27%` | `9` |
| `freqtrade-v1082` | `0.16%` | `124.1MiB / 1.922GiB` | `6.31%` | `18` |

Core health:

```text
freqtrade-v1129=running
freqtrade-v1082=running
```

Dashboard port check:

```text
dashboard_http=401
```

Interpretation: dashboard HTTP service remains reachable and requires authentication. This task did not read dashboard credentials.

## Explicit non-actions

本任务没有：

- 删除容器
- 删除 SQLite
- 修改服务器文件
- 修改策略
- 修改 bot 配置
- 修改 dashboard
- 修改 deploy
- 读取 `.env`
- 读取 `user_data/monitor.env`
- 打印或读取 API key、交易所凭证、server key、dashboard password
- 停止 `freqtrade-v1129`
- 停止 `freqtrade-v1082`
- 启动任何 bot
- 重启任何 bot
- 运行回测

## Remaining running containers

保留：

- `freqtrade-v1129`: 当前 V11.29 observation target
- `freqtrade-v1082`: 当前 V10.8.2 benchmark evidence source

## Follow-up recommendation

下一步建议执行：

```text
Task 21: V11.29 4h Data Availability Root-Cause Plan
```

目标：解释为什么 runtime logs 报 `No data found for (..., 4h, )`，而服务器 data directory 中又能看到 futures 4h files。不要直接补数据，先查 pairlist、datadir、market type、文件新鲜度和 Freqtrade 读取映射。

## Verification

Final verification commands:

```powershell
.\scripts\run_agent_readiness_checks.ps1
git diff --name-only
git status --short --untracked-files=all
```

Expected final visible changes:

```text
reports/audits/task20s_stop_legacy_v1127_v1116.md
tasks/active/TASK-0020S-STOP-legacy-v1127-v1116.md
```
