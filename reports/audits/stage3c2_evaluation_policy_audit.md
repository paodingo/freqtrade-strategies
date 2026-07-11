# Stage 3C.2 Evaluation Policy Source Audit

## 结论

当前仓库存在若干评价格式、风险说明和旧研究门槛，但没有一套已经批准、明确适用于本阶段 `BTC/USDT:USDT` 单交易对 futures Development/Validation split 的数值评价政策。

因此 `research/evaluation/evaluation-policy.yaml` 的状态为：

- `policy_approval_status: pending_human_review`

在该状态下，评价器可以执行 Development 的 Baseline/Candidate 指标计算和同数据集比较，但不得自动读取 Validation，不得把候选标记为通过或失败，最终状态应为 `development_evaluated_policy_pending`。

## 发现的规则来源

| 原始文件 | 原始规则 | 明确数值 | 现有流程认可 | 适用于 Futures | 适用于单交易对 | 适用于当前窗口 | 冲突/限制 |
|---|---|---:|---|---|---|---|---|
| `docs/验收报告格式.md` | 报告状态最高不应直接到 `live_ready`，未经过 dry-run/paper trading 时最高只到 `paper_ready`。 | 是 | 文档格式规则 | 是 | 是 | 是 | 本阶段更严格，最高仅 `validation_passed_provisional`，不得 Champion。 |
| `docs/验收报告格式.md` | 第二阶段硬指标含 70 天净收益、最近窗口交易数、最大回撤、成本压力、rolling 14d/30d。 | 是 | 报告模板 | 不完全明确 | 否，偏组合级 | 否，当前 Development/Validation 窗口较短且单交易对 | 不可直接作为当前 Stage 3C.2 批准门槛。 |
| `docs/验收报告格式.md` | 强通过指标含 `Profit Factor >= 1.5`、rolling 30d 大部分为正等。 | 是 | 报告模板 | 不完全明确 | 否，偏组合级 | 否 | 可作为审计来源，但不自动批准。 |
| `AUTONOMY.md` | 模型不得降低评价门、扩大 scope、绕过测试或自行晋升 Champion。 | 否 | Harness 规则 | 是 | 是 | 是 | 支持本阶段 policy pending 时停止在 Development。 |
| `WORKFLOW.md` | Runner 不决定 Champion，metric-gate failure 分类为 `candidate_rejected`。 | 否 | Harness 规则 | 是 | 是 | 是 | 指明职责边界，不提供数值门槛。 |
| `reports/audits/stage3b2_single_variable_semantic_mutation.md` | Stage 3B.2 结论 `mutation_verified_behavior_unchanged` 不是策略质量结果。 | 否 | 阶段验收报告 | 是 | 是 | 是 | 明确本候选尚未被质量评价。 |
| `reports/audits/stage3c1_research_data_plane.md` | Development/Validation 数据面可用，probe 仅为 `data_readiness_only`，`quality_verdict: not_evaluated`。 | 否 | 阶段验收报告 | 是 | 是 | 是 | 允许本阶段做 Development 指标，但不提供评价门槛。 |
| `research/data/validation-access-policy.yaml` | Validation 每 campaign/candidate 最多 1 次，必须受控访问。 | 是 | Stage 3C.1 治理 | 是 | 是 | 是 | 只有 policy 批准且 candidate frozen 后才可访问。 |
| `scripts/build_v1129_ranging_short_offline_return_study.js` | 旧研究中有 30d 最小窗口、100 candidate 样本、fee-adjusted 4-candle mean gate。 | 是 | 旧研究脚本 | 不适合作为当前 futures backtest gate | 否 | 否 | 旧候选搜索/alpha study 门槛，不可迁移为本阶段批准 policy。 |

## 待人工确认字段

- `coverage_requirements.min_total_trades`
- `coverage_requirements.min_long_trades`
- `coverage_requirements.min_short_trades`
- `absolute_gates.max_drawdown_percentage`
- `absolute_gates.min_profit_factor`
- `baseline_relative_gates` 中哪些指标必须优于 Baseline
- rolling-window 长度和最低正窗口比例
- Development inconclusive 是否允许人工冻结
- Validation provisional pass 所需最低条件

## 本阶段执行约束

- 不访问 sealed holdout。
- 不运行 Hyperopt、Lookahead Analysis、Recursive Analysis。
- 不生成新候选。
- 不修改任何策略源码。
- 不自动批准 policy。
- 不自动进入 Validation。
