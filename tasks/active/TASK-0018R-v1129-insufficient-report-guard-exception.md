# TASK-0018R: V11.29 Insufficient Report Guard Exception

状态：已完成，未进入 Task 18。

执行目录：`D:\code\freqtrade-strategies-clean`

分支：`codex/btc-mvp-system-harnessed`

## 目标

只为 Task 18 的 snapshot-based insufficient report 生成器和报告结果增加精确 guard 例外，不放宽任何真实 V11.29 策略、配置、交易数据、SQLite、dashboard、server 或 live 面。

## 允许修改文件

- `scripts/guard_harness_diff.js`
- `scripts/guard_trading_surface.js`
- `docs/harness/change_surface_matrix.md`
- `reports/audits/task18r_v1129_insufficient_report_guard_exception.md`
- `tasks/active/TASK-0018R-v1129-insufficient-report-guard-exception.md`

## 精确例外

`guard_harness_diff.js` 仅新增：

- `scripts/build_v1129_snapshot_insufficient_report.js`
- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json`
- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md`

`guard_trading_surface.js` 仅新增：

- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.json`
- `reports/v1129_execution_validation/v1129_snapshot_insufficient_report.md`

## 未放宽事项

- 未允许 `reports/v1129_execution_validation/**`
- 未允许 `reports/*v1129*`
- 未允许 `scripts/build_v1129_*`
- 未允许 SQLite snapshot 进入 Git
- 未允许真实 execution report 任意通配路径
- 未新增全局 bypass
- 未降低高风险交易面阻断

## 验证

- syntax checks：通过
- readiness：通过
- blocking self-test：通过
- 临时文件：已清理

## 下一步

可以在 Task 18 中仅使用本任务精确允许的 Task 18 路径继续生成 snapshot-based insufficient report。
