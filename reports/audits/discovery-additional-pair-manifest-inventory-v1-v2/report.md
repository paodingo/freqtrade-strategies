# 额外币种冻结数据清单审计

## 结论

审计已按停止条件结束。当前治理状态和 `research/data/snapshots` 下的冻结数据清单中，均没有发现 SOL、BNB、XRP、ADA 的 Development manifest。满足可比清单要求的候选币种为 **0 个**，低于预先冻结的 **至少 2 个**门槛，因此跨币种研究的数据前置条件不成立。

本结论只表示本地治理清单尚未就绪，不表示这些币种没有市场数据、不能复现交易行为，也不构成任何盈利或经济泛化判断。

## 冻结审计契约

- 候选集合：`SOL/USDT:USDT`、`BNB/USDT:USDT`、`XRP/USDT:USDT`、`ADA/USDT:USDT`
- 市场：Binance USD-M Futures
- 必需周期与流：`1h futures`、`4h futures`、`8h mark`、`8h funding_rate`
- 起点：`2024-01-01T00:00:00Z`
- 终点必须分别与 BTC/ETH 基准流一致
- 每个文件必须有内容 SHA256
- `sealed=true`、`campaign_mutable=false`
- 重复行与缺失间隔必须均为 0

## 基准清单

| 币种 | Dataset | Manifest SHA256 | 同窗口 | 缺失间隔 |
| --- | --- | --- | --- | ---: |
| BTC | `futures-dev-btc-usdt-usdt-20240101-20240830-v2` | `e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13` | 是 | 0 |
| ETH | `futures-dev-eth-usdt-usdt-20240101-20240830-v1` | `6557a265a1d2904452a236a84e1afeb9db4508e0ec6952a134ca494d2433b925` | 是 | 0 |

## 候选覆盖矩阵

| 候选币种 | 当前状态引用 | 冻结 Development manifest | 同窗口可验证 | 内容指纹可验证 | 合格 |
| --- | --- | --- | --- | --- | --- |
| SOL/USDT:USDT | 否 | 否 | 否 | 否 | 否 |
| BNB/USDT:USDT | 否 | 否 | 否 | 否 | 否 |
| XRP/USDT:USDT | 否 | 否 | 否 | 否 | 否 |
| ADA/USDT:USDT | 否 | 否 | 否 | 否 | 否 |

共审计 9 份 dataset manifest；候选币种在 manifest 和当前治理状态中的匹配数均为 0。

## 停止决定

- 状态：`stopped`
- 原因：`insufficient_frozen_additional_pair_manifests`
- 合格数：`0/2`
- 不自动下载、不自动封存、不扩大市场范围
- 若要重启，需另行人工批准候选币种范围、数据来源和可比时间边界

## 边界证明

- 网络访问：0
- 行情下载：0
- 行情文件读取：0
- 回测：0
- Candidate：0
- Campaign 编译/执行：0
- Validation/Holdout：0/0
- 策略与风险语义修改：0

结构化证据见 `research/analysis/discovery-additional-pair-manifest-inventory-v1-v2/analysis.json`。
