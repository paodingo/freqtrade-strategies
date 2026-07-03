# TASK-0016S: V11.29 Server SQLite Snapshot Acquisition

状态：已完成，未进入 Task 17。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只读登录服务器，定位并复制 V11.29 dry-run SQLite 快照到本地 snapshot 目录。尽量同时定位并复制 V10.8.2 same-window SQLite 快照。当前任务只做数据库快照取证，不做 schema 解读，不做执行报告，不做替换判断。

## 前置条件结果

- Task 16：通过，commit `2d97845 Plan V11.29 server data snapshot`
- 当前分支：通过，`codex/btc-mvp-system-harnessed`
- `git status --short --untracked-files=all`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 服务器信息

- host：`43.134.72.69`
- user：`ubuntu`
- ssh key file：`D:\key\openclaw\clf.pem`

## Snapshot 结果

- V11.29 snapshot：`reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite`
- V10.8.2 snapshot：`reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite`

## 本任务允许修改

- `reports/audits/task16s_v1129_server_sqlite_snapshot_acquisition.md`
- `tasks/active/TASK-0016S-v1129-server-sqlite-snapshot-acquisition.md`
- `reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite`
- `reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite`

## 本任务未执行

- 未读取 `.env`
- 未读取 `user_data/monitor.env`
- 未打印、复制、移动、读取 secret 内容
- 未运行 `docker inspect`
- 未启动、停止、重启 bot
- 未运行 `freqtrade trade`
- 未运行回测
- 未写入原始 SQLite 数据库
- 未修改策略
- 未修改 bot 配置
- 未修改 dashboard
- 未修改 deploy
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 17

## 下一步

推荐 Task 17：`V11.29 SQLite Snapshot Schema Inspection`。
