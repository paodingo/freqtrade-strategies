# TASK-0017: V11.29 SQLite Snapshot Schema Inspection

状态：已完成，未进入 Task 18。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只读检查本地 V11.29 与 V10.8.2 SQLite snapshot 的 schema、表结构、样本数量和时间范围，确认它们是否足以支持后续真实执行验证报告。

## 前置条件结果

- Task 16S：已提交，commit `688a326 Acquire V11.29 and V10.8.2 SQLite snapshots`
- 当前分支：通过，`codex/btc-mvp-system-harnessed`
- `git status --short --untracked-files=all`：前置检查通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：前置检查通过
- V11.29 snapshot：存在，`reports/v1129_execution_validation/snapshots/tradesv3_v1129.snapshot.sqlite`
- V10.8.2 snapshot：存在，`reports/v1129_execution_validation/snapshots/tradesv3_v1082.snapshot.sqlite`

## 只读检查方式

- 使用 bundled Python `sqlite3`
- SQLite URI 使用 `mode=ro`
- SQLite connection 设置 `PRAGMA query_only=ON`
- 未写入、复制、删除、移动或修改任何 SQLite snapshot

## 主要发现

- 两个 snapshot 的 SHA256 均与 Task 16S 报告一致。
- 两个 snapshot 均包含 `trades` 与 `orders` 表。
- V11.29 `trades` 表存在但为 0 行。
- V11.29 `orders` 表存在但为 0 行。
- V10.8.2 包含 6 条 closed trades 与 12 条 orders。
- V11.29 当前样本状态为 `insufficient`。
- 当前 snapshot 不支持 V11.29 与 V10.8.2 的 same-window execution quality comparison。

## 允许修改文件

- `reports/audits/task17_v1129_sqlite_snapshot_schema_inspection.md`
- `tasks/active/TASK-0017-v1129-sqlite-snapshot-schema-inspection.md`

## 未执行事项

- 未修改 SQLite snapshot 文件
- 未复制 SQLite snapshot 文件
- 未删除 SQLite snapshot 文件
- 未读取 `.env`
- 未读取 `user_data/monitor.env`
- 未读取 secret
- 未登录服务器
- 未启动、停止或重启 bot
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未修改 dashboard
- 未修改 deploy
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未生成 V11.29 替换 V10.8.2 的结论
- 未进入 Task 18

## 输出

- `reports/audits/task17_v1129_sqlite_snapshot_schema_inspection.md`

## 下一步

推荐 Task 18：`V11.29 Execution Report Builder`。

Task 18 应仅在受限范围内进行：读取 snapshot 并生成诚实的 execution report，当 V11.29 trades/orders 样本缺失时必须输出 `insufficient`，不得输出 V11.29 已通过真实执行验证或可以替换 V10.8.2。
