# Ranging-short router-state 只读归因报告

## 结论

当前 router contract 下不存在可采纳的新 context。12 条 `ranging_short` pre-gate 信号全部属于 `R-R-R`，即 ADX、BB-width、ATR 三票均为 ranging。

原 carry context 覆盖为 `0/12`；当前 raw ranging context 和 `R-R-R` 均覆盖 `12/12`，在观测样本上等价于整个分支，因此不能作为新的单一 context Candidate。

## 逐切片归因

| 切片 | R-R-R 信号 | 其他拓扑 |
|---|---:|---:|
| s01 | 0 | 0 |
| s02 | 2 | 0 |
| s03 | 9 | 0 |
| s04 | 1 | 0 |

## 执行边界

- 新 Candidate：`0`。
- Backtest：`0`。
- Validation / Holdout：`0 / 0`。
- 连续阈值搜索：未执行。
- 正式策略与 router：未修改。

最终决策：`no_admissible_router_context_under_current_contract`。只有经过单独人工审批的新结构观测量或新数据，才能重启该研究线。
