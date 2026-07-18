# Ranging-short router context 覆盖门禁报告

## 结论

本轮在 Backtest 前按约定停止，原因码为 `router_context_coverage_insufficient`。

冻结的 context 在 4 个 Development 切片中确实出现，但它与原始 `ranging_short` 入场掩码的交集为 `0`。因此，计划中的 16 次 Backtest 不具备信息增益，执行授权保持为 `false`。

## 覆盖结果

| 切片 | context=true | context=false | ranging_short pre-gate | 交集 |
|---|---:|---:|---:|---:|
| s01 | 151 | 1099 | 0 | 0 |
| s02 | 545 | 705 | 2 | 0 |
| s03 | 283 | 967 | 9 | 0 |
| s04 | 277 | 973 | 1 | 0 |
| 合计 | 1256 | 3744 | 12 | 0 |

覆盖数据共 `5000` 根 1h K 线，全部来自冻结的 BTC Development 数据集。

## 执行边界

- Candidate：`1 / 1`，已冻结。
- Backtest：`0 / 16`，覆盖门禁阻止执行。
- Validation / Holdout：`0 / 0`。
- Hyperopt、threshold search：均未执行。
- 正式策略、正式 base、router：均未修改。

这一结果只说明当前预声明 context 无法归因已有 `ranging_short` 信号，不支持删除正式分支，也不自动授权搜索新 context 或修改阈值。
