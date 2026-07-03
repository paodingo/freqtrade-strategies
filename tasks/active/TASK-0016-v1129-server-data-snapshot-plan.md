# TASK-0016: V11.29 Server Data Snapshot Plan

状态：已完成，未进入 Task 17。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

根据 Task 15 结论，制定 V11.29 server-side dry-run SQLite 只读取证方案。当前任务只生成计划，不登录服务器，不执行 SSH，不复制数据，不读取 secret。

## 前置条件结果

- Task 15：通过，commit `6f1374e Locate V11.29 execution data sources`
- 当前分支：通过，`codex/btc-mvp-system-harnessed`
- `git status --short --untracked-files=all`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 输入结论

Task 15 发现：

- 本地没有 `user_data/tradesv3_v1129.dryrun.sqlite`
- V11.29 config 的 `db_url` 指向 `sqlite:////freqtrade/project/user_data/tradesv3_v1129.dryrun.sqlite`
- 需要服务器侧只读取证方案

## 输出

- `reports/audits/task16_v1129_server_data_snapshot_plan.md`

## 本任务允许修改

- `reports/audits/task16_v1129_server_data_snapshot_plan.md`
- `tasks/active/TASK-0016-v1129-server-data-snapshot-plan.md`

## 本任务未执行

- 未登录服务器
- 未执行 SSH
- 未读取 secret
- 未启动、停止、重启 bot
- 未运行回测
- 未复制 SQLite
- 未修改任何策略
- 未修改 bot 配置
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 17

## 下一步

推荐 Task 17：`V11.29 SQLite Snapshot Schema Inspection`。

Task 17 应在人工授权并完成只读 SQLite snapshot 复制后，只读取本地 snapshot schema 和聚合统计。
