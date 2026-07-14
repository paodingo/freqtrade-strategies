# Regime-conditioned ranging-short routing 人工决策报告

> 状态：**仅完成 Proposal 与 dry-run 编译，未执行 Campaign**

- Proposal fingerprint：`da057e978228b6a29a79cf8487b99c1082fa75159516be00d8d036abce85d745`
- Compiled Campaign fingerprint：`7c3156a5215f96da0e261bc4a3ba8d4ceba39f95b681066b8138e3aa31b3bd26`
- 风险等级：`medium`
- 当前授权：`0 Candidate / 0 Backtest / 0 Validation / 0 Holdout`
- 正式分支：`ranging_short_entry` 保留且未修改

## 已冻结证据

| 切片 | 贡献结论 | 移除信号 | 移除交易 | 收益差值 Candidate - Baseline | Profit Factor 差值 |
|---|---:|---:|---:|---:|---:|
| `s01` | `inconclusive` | 0 | 0 | 0.00000000 USDT | 0.00000000 |
| `s02` | `positive_contributor` | 2 | 1 | -7.18300403 USDT | -0.01492420 |
| `s03` | `negative_contributor` | 9 | 1 | 28.47135644 USDT | 0.10918274 |
| `s04` | `negative_contributor` | 1 | 3 | 32.83686152 USDT | 0.04470009 |

四个切片证明贡献方向随时间变化，但没有把这种变化归因到可在运行时直接观测、并在实验前声明的 router context。**时间切片不是市场 regime 标签**，不能据此事后挑选路由条件。

## 编译建议

`insufficient_router_context_evidence`

当前应继续保留正式分支，不创建 Candidate，也不执行 Backtest。若未来能先验声明一个精确的 router context，应另建中风险 Proposal 并重新人工审批。

## 未来单独审批上限

- Candidate：最多 `1` 个；
- Development-only Backtest：最多 `16` 次；
- 新增时间切片：`0`；
- Validation / Holdout：`0 / 0`；
- 必须重新冻结 Proposal fingerprint、Campaign fingerprint、Candidate 路径/类名/hash 与 diff allowlist。

## 仍需人工决定

1. 是否存在一个不依赖本次结果挑选的、可运行时观测的精确 router context；
2. 是否批准新的单变量 Candidate；
3. 是否批准 16 次 Development-only Backtest；
4. 是否接受继续保留分支且不作结构变更。

本报告不支持删除正式分支、修改阈值、改变 entry/exit 或访问 Validation/Holdout。
