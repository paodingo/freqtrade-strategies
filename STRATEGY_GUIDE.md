# 策略说明书

## 当前目标

当前目标不是继续把 V6.5 / V6.6 作为主线对比，而是把历史策略脉络整理清楚，并围绕 V11.29 建立真实执行验证链路。

截至当前证据，V11.29 仍是 `insufficient` 状态：

- V11.29 SQLite snapshot 中 `trades = 0`。
- V11.29 SQLite snapshot 中 `orders = 0`。
- V10.8.2 snapshot 中存在有限 closed trades / orders，可作为 benchmark data availability 证据。
- 由于 V11.29 没有真实 trades/orders 样本，不能计算 winrate、profit factor、slippage、fee quality、latency quality，也不能做 same-window execution quality comparison。

因此，本说明书只描述策略验证口径和历史版本定位，不得被理解为 V11.29 已通过验证或可以替换 V10.8.2。

## 当前验证口径

后续策略评估应优先回答这些问题：

- V11.29 是否具备完整的 4h informative data coverage。
- V11.29 是否存在策略分析耗时过长导致 missed signals / delayed orders 的风险。
- V11.29 是否实际产生 entry signals，或被 pairlist、protections、filters、资金、交易所/API 状态阻断。
- V11.29 是否能产生真实 dry-run trades/orders 样本。
- 是否能和 V10.8.2 建立同时间窗口的执行质量对照。

在这些问题解决前，任何“替换 V10.8.2”或“通过真实执行验证”的结论都不成立。

## 历史版本脉络

- `RegimeAwareV61`：历史对照版本，趋势入场、关闭震荡入场，并启用 Freqtrade protections。
- `RegimeAwareV62`：历史基线，在 V6.1 信号基础上支持固定额度的保守加仓。
- `RegimeAwareV63`：历史稳定基线；按账户最大亏损百分比反推加仓额度，并检查止损/强平距离、波动、冷却时间和可用余额。
- `RegimeAwareV64`：历史进攻挑战者；15m 趋势版，作为后续版本参考。
- `RegimeAwareV65`：历史进攻基线；曾用于 15m 震荡短线策略 dry-run。
- `RegimeAwareV66`：历史选择性候选；继承 V6.5，并加入 24h/48h 箱体位置过滤，只在箱体边缘交易。
- `RegimeAwareV6`、`RegimeAwareV8`、`RegimeAwareV9`：历史或实验参考版本。
- V10.8.2：当前验证链路中的 benchmark evidence 来源之一。
- V11.29：当前真实执行验证对象，但当前样本不足。

## 已知历史 V6.5 / V6.6 对比

V6.5 / V6.6 的旧目标是观察 V6.6 是否能牺牲一部分交易频率，换来比 V6.5 更好的入场位置、较小回撤和更快的错误承认。

| 项目 | V6.5 历史震荡进攻基线 | V6.6 历史选择性箱体候选 |
| --- | --- | --- |
| 趋势入场 | 保留 | 保留 |
| 震荡入场 | 开启并放宽 | 只在箱体上下沿开启 |
| 保护机制 | Cooldown、StoplossGuard、MaxDrawdown | Cooldown、StoplossGuard、MaxDrawdown |
| 主交易周期 | 15m | 15m |
| 额外门槛 | 止损/强平距离、波动、冷却、可用余额 | 额外要求 24h/48h 箱体位置和中部禁开 |

这段内容是历史策略解释，不代表当前云端运行面或 V11.29 验证结论。

## V11.29 后续观察指标

V11.29 后续一旦产生真实 dry-run trades/orders，才可以逐步观察：

- `trade_count` / `closed_trade_count` / `open_trade_count`。
- pair、side、entry_tag、exit_reason。
- open time、close time、holding duration。
- order price、filled price、fee、funding fee。
- slippage bps、latency、unfilled signals、blocked signals。
- pnl、pnl_ratio、drawdown、consecutive losses。
- 与 V10.8.2 的同窗样本可比性。

如果没有真实样本，上述字段必须保持 `missing`、`unknown` 或 `insufficient`，不能写成 `0` 来伪装结论。

## 下一步优化方向

推荐顺序：

1. 做 V11.29 数据覆盖和运行性能审计。
2. 如果确认 4h 数据缺失，制定安全补数据计划。
3. 如果确认分析耗时过长，做性能瓶颈审计。
4. 重新观察 V11.29 是否产生真实 trades/orders。
5. 只有在样本足够后，才生成真实执行验证报告。

## 风险提示

当前仍处于 dry-run 证据整理和真实执行验证准备阶段。真实交易前，需要额外验证交易所最小下单量、资金费率、手续费、滑点、API 稳定性、极端行情止损行为和 server/live 运维边界。
