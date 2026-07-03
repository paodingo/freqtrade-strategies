# Task 13R: Allow V11.29 Harness Schema Docs in Trading-Surface Guard

结论：本任务只为 `docs/harness/v1129_execution_report_schema.md` 增加了精确 guard 例外，使 Task 13 的 harness schema 文档可以通过 readiness。该例外不放宽策略、bot 配置、dashboard、deploy、V11.29 报告证据、live/server 操作面或 secret 阻断。

## 1. 背景

Task 13 只生成了以下 3 个允许文件：

- `docs/harness/v1129_execution_report_schema.md`
- `reports/audits/task13_v1129_execution_report_schema.md`
- `tasks/active/TASK-0013-v1129-execution-report-schema.md`

但 `scripts/guard_trading_surface.js` 会用版本化路径正则拦截 changed path 中的 `v1129`，导致 harness schema 文档被误判为 V11.29 交易面。

## 2. 本次修改

修改文件：

- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task13r_v1129_schema_guard_exception.md`
- `tasks/active/TASK-0013R-v1129-schema-guard-exception.md`

guard 修改：

- 新增 `EXACT_VERSIONED_DOC_EXCEPTIONS`
- 唯一例外路径：`docs/harness/v1129_execution_report_schema.md`
- `blockedReason()` 在检查高风险面之前先识别该精确路径

未新增以下泛化规则：

- 未允许 `docs/harness/*v1129*`
- 未允许 `docs/**`
- 未允许任意包含 `v1129` 的文档
- 未新增全局 bypass

## 3. 未放宽的阻断面

以下阻断保持不变：

- `strategies/**`
- `user_data/**`
- `configs/**`
- `dashboard/**`
- `deploy/**`
- `.env`
- `user_data/monitor.env`
- `reports/reliable_strategy_search_v1129/**`
- V10.8.2/V11.29 策略、配置、报告证据
- live/server 操作面

## 4. 验证结果

已运行：

```powershell
node --check scripts/guard_trading_surface.js
.\scripts\run_agent_readiness_checks.ps1
```

结果：

```text
node --check scripts/guard_trading_surface.js
<exit 0>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (7 changed path(s) checked)
guard_no_secret_material: pass (7 changed path(s) checked)
guard_trading_surface: pass (7 changed path(s) checked)
```

blocking self-test 覆盖：

- `strategies/RegimeAwareV1129GuardSelfTest.py` 必须被 `guard_trading_surface` 阻断并返回 `1`
- `user_data/config_multi_futures_v1129_guard_selftest.json` 必须被 `guard_trading_surface` 阻断并返回 `1`
- `reports/reliable_strategy_search_v1129/guard_selftest.json` 必须被 `guard_trading_surface` 阻断并返回 `1`

临时 self-test 文件在验证后清理。

blocking self-test 结果：

```text
strategies/RegimeAwareV1129GuardSelfTest.py
guard_trading_surface: blocked high-risk diff
- strategies/RegimeAwareV1129GuardSelfTest.py: strategy code is blocked by default
exit 1

user_data/config_multi_futures_v1129_guard_selftest.json
guard_trading_surface: blocked high-risk diff
- user_data/config_multi_futures_v1129_guard_selftest.json: bot config/runtime data is blocked by default
exit 1

reports/reliable_strategy_search_v1129/guard_selftest.json
guard_trading_surface: blocked high-risk diff
- reports/reliable_strategy_search_v1129/guard_selftest.json: V11.29 report surface is blocked by default
exit 1
```

## 5. 执行边界确认

- 未修改策略
- 未修改 bot 配置
- 未读取 secret
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未放宽 V11.29 策略/config/report evidence 阻断
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 14

## 6. 下一步

Task 13 的 3 个文件和 Task 13R 的 guard 例外文件通过 readiness 后，可以由用户决定是否提交 Task 13/13R，再进入 Task 14。
