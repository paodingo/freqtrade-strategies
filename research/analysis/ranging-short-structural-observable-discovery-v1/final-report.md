# Ranging-short 结构观测量 Discovery 报告

## 结论

本批只做只读 Discovery，不创建 Candidate、不回测，也不读取收益结果。

优先进入下一次人工审阅的是 `router_indicator_direction_topology`：
比较 ADX、BB-width、ATR 相对上一根已完成 4h K 线的方向，现有 12 个 pre-gate 信号自然分成 `D-D-D=2`、`U-U-D=5`、`U-U-U=5`。

## 排名

| 排名 | 观测量 | 分数 | 覆盖 |
|---:|---|---:|---|
| 1 | `router_indicator_direction_topology` | 19/20 | D-D-D=2, U-U-D=5, U-U-U=5 |
| 2 | `completed_mark_futures_basis_sign` | 17/20 | negative=10, positive=2 |
| 3 | `funding_sign` | 17/20 | negative=1, positive=11 |
| 4 | `volume_mean_direction` | 14/20 | D=2, U=10 |
| 5 | `close_return_direction` | 13/20 | D=4, U=8 |

## 明确排除

- router 状态切换：12/12 都是持续 `R-R-R`，等价于整个观测分支。
- 重复信号 episode：旧机制审计已经闭环，本批不自动重开。
- Alpha/Taker/OI/Order book：没有封存的历史源，不能编造。
- 跨币种相对状态：需要单独的数据对齐与作用域审批。

## 下一步边界

已编译 `ranging-short-router-indicator-direction-review-v1`，状态为 `pending_human_review`。
该提案预算仍为零：只允许固化防未来函数的方向语义与覆盖复核；任何 Candidate、Backtest、Validation 或 Holdout 都要另行批准。
