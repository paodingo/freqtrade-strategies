# TASK-0014R: Allow V11.29 Empty Execution Report Sample Paths

状态：已完成，未进入 Task 14。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只为 Task 14 的 empty/insufficient 示例报告生成器增加精确 guard 例外，不放宽任何真实 V11.29 策略、配置、真实报告证据或交易面。

## 允许修改

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task14r_v1129_empty_report_guard_exception.md`
- `tasks/active/TASK-0014R-v1129-empty-report-guard-exception.md`

## 本任务未执行

- 未修改策略
- 未修改 bot 配置
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未允许真实 V11.29 execution report、trade data、SQLite、config、strategy、backtest、dashboard 数据
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 14

## 验证

要求验证：

```powershell
node --check scripts/guard_harness_diff.js
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

blocking self-test：

- Task 14 三个精确路径必须允许
- 非白名单 V11.29 execution report 必须阻断
- `reports/reliable_strategy_search_v1129/**` 必须阻断
- V11.29 strategy/config 必须阻断
- 临时文件必须清理

验证结果：

- `node --check scripts/guard_harness_diff.js`：通过
- `node --check scripts/guard_trading_surface.js`：通过
- `.\scripts\run_agent_readiness_checks.ps1`：通过
- Task 14 三个精确路径：允许
- 非白名单 V11.29 execution report：阻断
- `reports/reliable_strategy_search_v1129/**`：阻断
- V11.29 strategy/config：阻断
- 临时文件：已清理
