# Task 13: V11.29 Execution Report Schema

结论：本任务已根据 Task 12 的数据源盘点定义 V11.29 真实执行验证报告的 JSON schema 和 Markdown 报告结构。当前阶段只定义 schema，不生成真实执行报告，不声称 V11.29 已完成验证，不判断 V11.29 是否可以替换 V10.8.2。

最终 readiness 出现阻断：Task 13 明确要求新增 `docs/harness/v1129_execution_report_schema.md`，但现有 `scripts/guard_trading_surface.js` 的版本化路径规则会拦截包含 `v1129` 的 changed path。本任务未被授权修改 guard，因此未扩大 allowlist。

## 1. 执行基线

- 当前目录：`D:\code\freqtrade-strategies-clean`
- 当前分支：`codex/btc-mvp-system-harnessed`
- Task 12 commit：`d8f7a13 Inventory V11.29 execution data sources`

前置 gate：

```text
git status --short --untracked-files=all
<empty>

.\scripts\run_agent_readiness_checks.ps1
guard_harness_diff: pass (0 changed path(s) checked)
guard_no_secret_material: pass (0 changed path(s) checked)
guard_trading_surface: pass (0 changed path(s) checked)
```

必须只读查看的文件已查看：

- `reports/audits/task12_v1129_execution_data_inventory.md`
- `tasks/active/TASK-0012-v1129-execution-data-inventory.md`

## 2. Task 12 输入摘要

Task 12 明确了以下约束和事实：

- 当前路径级证据不足以直接生成 V11.29 真实执行验证报告。
- 未定位常见 Freqtrade dry-run trade SQLite。
- `user_data/monitor_history.sqlite` 存在，但未证明包含 V11.29 trade 样本。
- `reports/live_window_execution_check/*` 存在，但未证明字段覆盖或样本窗口。
- V11.29 策略/配置/脚本路径存在，但不能证明实际 dry-run/live 使用。
- V10.8.2 有回测/研究证据路径，但未证明有同窗口真实执行对照样本。

## 3. Schema 输出

新增 schema 文档：

- `docs/harness/v1129_execution_report_schema.md`

该文档定义：

- 统一证据状态：`observed`、`derived`、`missing`、`unknown`、`not_applicable`
- 通用字段 envelope：`state`、`value`、`unit`、`source_refs`、`confidence`、`notes`
- JSON schema 模块：
  - `metadata`
  - `bot_runtime`
  - `execution_samples`
  - `trade_execution_quality`
  - `strategy_behavior`
  - `benchmark_comparison`
  - `data_gaps`
  - `verdict`
- Markdown 报告结构：
  1. Summary
  2. Data availability
  3. Execution sample status
  4. Runtime health
  5. Execution quality
  6. V10.8.2 comparison readiness
  7. Missing data
  8. Blocking gaps
  9. What this report cannot conclude
  10. Recommended next task

## 4. 关键防误判规则

Schema 明确要求：

- 没有真实 trade 样本时，`metadata.sample_status` 必须允许并使用 `insufficient`。
- 没有 SQLite/API/monitor 数据证明时，不得把字段写成 `0`，必须用 `missing` 或 `unknown`。
- 未验证异常来源时，不得写成 runtime health 正常。
- 未找到数据来源时，不得写成已验证空数据集。
- `observed` 只能用于直接验证的真实执行数据。
- `derived` 只能用于由 `observed` 输入计算得出的字段。
- `verdict.can_evaluate_replacement` 默认必须为 `false`，直到 V11.29 与 V10.8.2 同窗口真实执行证据都被验证。

## 5. 执行边界确认

- 未修改策略
- 未修改 bot 配置
- 未读取 secret、`.env`、`user_data/monitor.env`
- 未启动 bot
- 未登录服务器
- 未运行回测
- 未生成真实执行报告
- 未生成真实执行结论
- 未判断 V11.29 是否可以替换 V10.8.2
- 未修改原始脏工作区 `D:\code\freqtrade-strategies`
- 未进入 Task 14

## 6. 后续建议

推荐 Task 14：`V11.29 Execution Data Collection Plan`。

Task 14 应继续保持只读和 schema-first 边界，目标是定义如何安全采集或导出：

- Freqtrade DB/API trade、order、fee 字段
- `user_data/monitor_history.sqlite` 表结构和时间窗口
- live window report 字段覆盖
- V11.29 与 V10.8.2 同窗口样本
- stopped/API 500/jq parse error 等 runtime health 事件
- signal、blocked signal、unfilled signal、fill event 的关联键

Task 14 仍不应启动 bot、登录服务器、运行回测、读取 secret 或修改交易面。

在进入 Task 14 前，建议先由一个窄任务处理 guard mismatch：

- 目标：只允许 `docs/harness/v1129_execution_report_schema.md` 作为 schema 文档路径通过 `guard_trading_surface`。
- 限制：不得放宽 `strategies/**`、`user_data/**`、`configs/**`、`dashboard/**`、`deploy/**`、`reports/reliable_strategy_search_v1129/**`。
- 限制：不得允许 V10.8.2/V11.29 策略、配置、报告、live/server 操作面。
