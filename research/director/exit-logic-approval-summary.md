# Exit Logic Structure Audit 人工审批摘要

- Proposal：`exit-logic-structure-audit-v1`
- Approval：`approved / human_user`
- Risk：`low`
- Expected information gain：`0.81`
- Compiled Campaign fingerprint：`a4c3b5d8d072963441d2dce1e989d71822062d65a58f610cac40145a79a9f3ae`
- Campaign execution：`completed`
- Result：`no_exit_change_warranted_insufficient_causal_evidence`

## 结构结论

4 个 temporal slices 共记录 82 个 exits：ROI 40、stop-loss 28、ranging target 9、trending time-stop 3、force exit 2。唯一负收益 slice 的 stop-loss 占比较高，但正收益 slices 同样包含显著 stop-loss exits，因此 exit-reason 分布不足以建立因果结论。

此前 signal-to-trade attribution 的直接 exit delta 为 0；first-trigger conflict 与真实 missed post-exit reentry 均为 0。本次没有依据修改 ROI、stoploss、time-stop、protections、策略结构或风险语义。

## 边界

- Candidate / strategy modification：`false / false`
- Backtest ranking / parameter search / Hyperopt：`false / false / false`
- Validation / Holdout：`0 / 0`
- 第二个 Campaign / Stage 4C：`false / false`

## 下一 Proposal

- `regime-branch-structure-audit-v1`
- Risk：`low`
- Expected information gain：`0.73`
- Approval / execution：`false / false`

该 Proposal 需要新的人工选择事件，本次未自动执行。
