# Task 16S: V11.29 Server SQLite Snapshot Acquisition

状态：已完成，未进入 Task 17。

结论：本任务只读登录服务器并成功取得 V11.29 dry-run SQLite snapshot，同时取得 V10.8.2 same-window 对照 SQLite snapshot。未读取 `.env`、`user_data/monitor.env` 或任何 secret 内容；未执行 `docker inspect`；未启动、停止、重启 bot；未运行回测；未修改策略、bot 配置、dashboard、deploy 或原始脏工作区。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 16 commit：`2d97845 Plan V11.29 server data snapshot`
- server：`ubuntu@43.134.72.69`
- ssh key path：`D:\key\openclaw\clf.pem`

前置 gate：

```text
git status --short --untracked-files=all
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

## 2. SSH key handling

用户提供的 `D:\key\openclaw` 是目录，实际 key 文件为：

```text
D:\key\openclaw\clf.pem
```

为满足 Windows OpenSSH 对私钥权限的要求，只调整了本地 key 文件 ACL 元数据，未读取、打印、复制或移动 key 内容。

最终 ACL：

```text
D:\key\openclaw\clf.pem KZY\paodi:(R)
                        BUILTIN\Administrators:(F)
                        NT AUTHORITY\SYSTEM:(F)
```

## 3. 服务器只读定位结果

只读命令：

```powershell
ssh -i D:\key\openclaw\clf.pem ubuntu@43.134.72.69 "hostname; date -Is; docker ps --format '{{.Names}} {{.Status}}'"
```

输出：

```text
VM-0-8-ubuntu
2026-07-03T20:49:20+08:00
freqtrade-v1129 Up 4 hours
freqtrade-v1127 Up 4 hours
freqtrade-v1116 Up 2 days
freqtrade-v1082 Up 3 days
```

候选容器：

- V11.29：`freqtrade-v1129`
- V10.8.2：`freqtrade-v1082`

## 4. SQLite 源路径确认

只读检查路径：

```text
/freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite
/freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite
```

服务器检查结果：

```text
CONTAINER freqtrade-v1129
-rw-r--r-- 1 ftuser ftuser 92K Jul  2 09:25 /freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite
-rw-r--r-- 1 ftuser ftuser 92K Jun 26 02:22 /freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite

CONTAINER freqtrade-v1082
-rw-r--r-- 1 ftuser ftuser 92K Jul  2 09:25 /freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite
-rw-r--r-- 1 ftuser ftuser 92K Jun 26 02:22 /freqtrade/project/user_data/tradesv3_v1082.dryrun.sqlite
```

## 5. Snapshot 生成方式

容器内可用工具：

```text
freqtrade-v1129: /usr/bin/sqlite3
freqtrade-v1082: /usr/bin/sqlite3
```

生成方式：

- 在容器内使用 SQLite `.backup` 从 live dry-run DB 生成 `/tmp/*.snapshot.sqlite`。
- 使用 `docker cp` 将容器内临时 snapshot 复制到服务器 `/tmp/v1129-sqlite-snapshot-20260703-205048/`。
- 使用 `scp` 将服务器 `/tmp` snapshot 下载到本地 clean worktree。
- 删除容器内临时 snapshot 和服务器 `/tmp` 临时 snapshot。

未对原始 SQLite 执行写入命令。

## 6. 本地 snapshot 结果

本地目标目录：

```text
reports/v1129_execution_validation/snapshots/
```

取得文件：

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite` | 94208 bytes | `B8C14EAE337A065CD69BBC6CED26BB1782F088818D5E2B552D4433C837D83EE5` |
| `reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite` | 94208 bytes | `3B953C9DC1AE3F2441375A8CCF31C573E56C05D98E9EFB7C9BC4138EEF426BBC` |

远端快照 hash：

```text
b8c14eae337a065cd69bbc6ced26bb1782f088818d5e2b552d4433c837d83ee5  /tmp/v1129-sqlite-snapshot-20260703-205048/tradesv3_v1129.snapshot.sqlite
3b953c9dc1ae3f2441375a8ccf31c573e56c05d98e9efb7c9bc4138eef426bbc  /tmp/v1129-sqlite-snapshot-20260703-205048/tradesv3_v1082.snapshot.sqlite
```

本地与远端 hash 一致。

服务器临时目录清理结果：

```text
cleaned
```

## 7. 是否取得 snapshot

- V11.29 snapshot：已取得
- V10.8.2 same-window snapshot：已取得

注意：本任务不读取 schema、不统计 trades/orders、不判断样本窗口，不生成替换结论。

## 8. 执行边界确认

- 未读取 `.env`
- 未读取 `user_data/monitor.env`
- 未打印、复制、移动、读取 API key、交易所凭证、服务器密钥、dashboard 密码内容
- 未运行 `docker inspect`
- 未启动、停止、重启 bot
- 未执行 `docker restart` / `docker stop` / `docker start`
- 未运行 `freqtrade trade`
- 未运行回测
- 未写入原始 SQLite 数据库
- 未修改策略
- 未修改 bot 配置
- 未修改 dashboard
- 未修改 deploy
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 17

## 9. 后续建议

推荐 Task 17：`V11.29 SQLite Snapshot Schema Inspection`。

Task 17 应只读取本地 snapshot：

- `reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite`
- `reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite`

Task 17 不应登录服务器、不应读取 secret、不应启动/停止 bot、不应运行回测、不应修改策略或 bot 配置。
