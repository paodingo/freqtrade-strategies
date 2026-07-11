# Stage 4A 人工审批摘要

## 当前决定

- Research Constitution：`pending_human_review`，未自动批准。
- Proposal 自动批准数：`0`。
- Campaign 执行数：`0`；Candidate 创建数：`0`。
- Validation / Holdout 访问数：`0 / 0`。

## 候选方向

| 排名 | Proposal | 风险 | 信息增量 | 路由 |
|---:|---|---|---:|---|
| 1 | `cross-pair-data-readiness-audit-v1` | low | 0.92 / high | `auto_approvable_future` |
| 2 | `exit-logic-structure-audit-v1` | low | 0.81 / high | `auto_approvable_future` |
| 3 | `regime-branch-structure-audit-v1` | low | 0.73 / medium | `auto_approvable_future` |

最高优先级方向只审计跨 pair 数据就绪度，不下载新数据、不运行回测，也不修改策略或风险语义。其 dry-run Campaign 已编译并通过现有控制面校验，但 `execution_authorized: false`。

## 明确拒绝

- 相邻 ranging threshold 搜索：`closed_branch_no_reopen_evidence`。
- 重复 temporal profile：`duplicate_research_question`。
- 直接跨 pair 回测：`insufficient_data`，当前缺少 sealed non-BTC strategy dataset。
- 自动风险参数搜索：`forbidden_by_constitution`。

## 进入 Stage 4B 前需要人工决定

1. 审批或修改 `research/governance/research-constitution.yaml`。
2. 明确批准选中的 Proposal；`auto_approvable_future` 在 Stage 4A 不等于批准。
3. 若后续需要新 pair 数据，单独批准 Dataset/market scope 和 provisioning；不得访问 Validation/Holdout。
4. 确认 Campaign 的 frozen inputs、预算、blocked paths、停止条件和 Git Definition of Done。
