# 实施简报：Regime-conditioned ranging-short routing evidence review

Campaign：`stage4a-regime-conditioned-ranging-short-routing-v1`
Fingerprint：`7c3156a5215f96da0e261bc4a3ba8d4ceba39f95b681066b8138e3aa31b3bd26`
编译模式：`dry_run`
执行授权：`false`

## 当前证据

- `s01`：`inconclusive`
- `s02`：`positive_contributor`
- `s03`：`negative_contributor`
- `s04`：`negative_contributor`

正式 `ranging_short_entry` 保持不变。Router extraction 的语义等价性已经验证，但现有四个时间切片只能证明贡献方向随时间变化，不能把时间切片直接解释为市场 regime。

## 当前只读范围

1. `freeze the four approved temporal conclusions and verified router structure`
2. `build a read-only router-context evidence matrix and expose attribution gaps`
3. `prepare one single-variable future approval envelope without selecting or executing a Candidate`

当前预算为 `0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`。本次只冻结证据矩阵、缺口和人工决策边界，不执行编译后的 Campaign。

## 编译建议

`insufficient_router_context_evidence`

现有证据不足以预先声明一个可验证的 router context。若未来获得精确、事先声明且不依赖结果选择的 context，必须另建 medium-risk Proposal，并重新冻结 Proposal/Campaign fingerprint。

未来单独审批预算上限为 `1 Candidate / 16 Development-only Backtests / 0 Validation / 0 Holdout`；不得增加时间切片，不得修改阈值、entry/exit、风险或正式策略。

## 仍需人工批准

- 精确且可由运行代码观测的单一 router context；
- 新 Proposal 与 Compiled Campaign fingerprint；
- 唯一 Candidate 的路径、类名、源码 hash 和 diff allowlist；
- `16` 次 Development-only Backtest 的独立执行授权。

在这些事项获批前，系统应保持 `retain_branch_no_routing_change`。
