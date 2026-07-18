# Ranging-short router 指标方向契约审计

## 结论

4h 指标方向拓扑通过结构审计，但只具备有条件的 Candidate 准备资格。
当前提交证据中的 12 个信号全部满足完成 K 线对齐，没有未来函数违规；方向拓扑把原本 `R-R-R=12` 的单一水平状态细分为 `D-D-D=2`、`U-U-D=5`、`U-U-U=5`。

建议后续唯一单变量 gate 为 `block_unanimous_router_indicator_expansion`：当 ADX、BB-width、ATR 同时上升，即 `U-U-U` 时阻止 ranging-short 新入场。它将阻止 5 个 pre-gate 信号并保留 7 个。该选择只依据经济机制，没有读取收益结果。

## 防未来函数契约

- 1h 信号在该 K 线结束时决策。
- 4h 指标只有在对应 4h K 线结束后才可用。
- 当前与上一根已完成 4h 指标逐项比较：上升=`U`、下降=`D`、相等=`F`。
- 对齐违规：`0`。

## 信息增量与边界

- 当前水平 router 熵：`0.0` bit。
- 方向拓扑熵：`1.483355754982` bit。
- 未更改已关闭阈值、重复信号机制、风险或执行语义。
- Candidate / Backtest / Validation / Holdout：`0 / 0 / 0 / 0`。
- 分支清理保留了提交后的逐行证据，但没有保留被忽略的原始 feather 数据；创建 Candidate 前必须先按封存 lineage 恢复并复现原始数据。

## 下一步

已编译 `ranging-short-router-unanimous-expansion-candidate-preparation-v1`，状态为 `pending_human_review`。它只允许恢复数据、创建一个 Candidate 并运行零回测覆盖 preflight；回测仍未获授权。
