# TASK-0013R: Allow V11.29 Harness Schema Docs in Trading-Surface Guard

状态：已完成，未进入 Task 14。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只为 `docs/harness/v1129_execution_report_schema.md` 增加精确例外，使 Task 13 的 harness schema 文档可以通过 readiness；不放宽任何真实交易面。

## 允许修改

- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task13r_v1129_schema_guard_exception.md`
- `tasks/active/TASK-0013R-v1129-schema-guard-exception.md`

## 本任务未执行

- 未修改策略
- 未修改 bot 配置
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未放宽 V11.29 策略/config/report evidence 阻断
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 14

## 验证

要求验证：

```powershell
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

blocking self-test：

- `strategies/RegimeAwareV1129GuardSelfTest.py` 返回阻断
- `user_data/config_multi_futures_v1129_guard_selftest.json` 返回阻断
- `reports/reliable_strategy_search_v1129/guard_selftest.json` 返回阻断

临时文件验证后必须清理。

验证结果：

- `node --check scripts/guard_trading_surface.js`：通过
- `.\scripts\run_agent_readiness_checks.ps1`：通过
- 三个 blocking self-test：均按预期返回 `1`
- 临时 self-test 文件：已清理
