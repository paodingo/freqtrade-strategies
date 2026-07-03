# TASK-0015: V11.29 Execution Data Locator

状态：已完成，未进入 Task 16。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只读定位真实 V11.29 execution 数据源，确认是否存在可用于生成真实执行验证报告的数据，包括 dry-run trades、orders、open/closed trade、monitor history、dashboard API 缓存、live window execution check 报告等。

## 前置条件结果

- Task 14：通过，commit `7be3ff7 Add V11.29 empty execution report generator`
- 当前分支：通过，`codex/btc-mvp-system-harnessed`
- `git status --short --untracked-files=all`：通过，输出为空
- `.\scripts\run_agent_readiness_checks.ps1`：通过

## 只读检查

已运行：

```powershell
git -C D:\code\freqtrade-strategies -c core.quotepath=false status --short --untracked-files=all -- user_data reports dashboard scripts
git -C D:\code\freqtrade-strategies -c core.quotepath=false ls-files --others --exclude-standard -- user_data reports dashboard scripts
```

并只读检查了：

- `user_data/*.sqlite`
- `user_data/*.sqlite-*`
- `user_data/tradesv3*.sqlite`
- `user_data/backtest_results/**`
- `user_data/monitor_history.sqlite`
- `reports/live_window_execution_check/**`
- `reports/v11*execution*`
- `reports/*v1129*`
- dashboard API / monitor store 相关脚本路径
- V11.29 bot config 中的 `db_url` 行

## 输出

- `reports/audits/task15_v1129_execution_data_locator.md`

## 本任务允许修改

- `reports/audits/task15_v1129_execution_data_locator.md`
- `tasks/active/TASK-0015-v1129-execution-data-locator.md`

## 本任务未执行

- 未修改原始工作区 `D:\code\freqtrade-strategies`
- 未复制文件
- 未删除文件
- 未移动文件
- 未 stash
- 未 commit 原始工作区
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未修改策略
- 未修改 bot 配置
- 未进入 Task 16

## 结论

当前没有找到本地 V11.29 dry-run trade SQLite。已定位的候选是 `user_data/monitor_history.sqlite` 和 `reports/live_window_execution_check/*`，但尚未读取内容，不能证明包含真实 trades、orders、fees、funding、slippage 或 latency。

当前不能生成真实执行验证报告，只能继续 insufficient 报告。推荐 Task 16：`Read-only Data Source Schema Inspection`。
