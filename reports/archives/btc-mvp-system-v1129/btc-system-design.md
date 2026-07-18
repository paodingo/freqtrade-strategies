# `btc_system` 原型设计提炼

## 目标

`btc_system` 是 2026-06-13 开始的一套独立 BTCUSDT 永续合约 MVP。其目标是不再持续堆叠 `RegimeAwareVxx`，而是拆出可解释、可回测、可模拟和可进行小资金验证的模块化交易系统。

## 模块边界

- `config.py`：集中加载和校验 YAML 风险阈值。
- `models.py`：统一 `MarketState`、`SignalScore`、`RiskState` 和 `PositionSize` 数据模型。
- `data/`：Freqtrade K 线、Funding、OI、成本和 replay dataset。
- `indicators/`：15m/1h/4h 指标与闭合 K 线对齐。
- `regime/`：识别趋势、震荡、高波动和未知状态，不直接产生交易。
- `signals/`：trend pullback、range mean reversion、volatility breakout 三类 arm，以及显式评分和路由。
- `risk/`：标准、进攻、降风险、暂停状态机及按止损距离定仓。
- `backtest/`：逐根 K 线回测、成交/成本模拟、信号审计和报告生成。
- `runtime/`：paper trader 与 live-readiness 检查。

## 核心约束

- 第一阶段只交易 `BTC/USDT:USDT`，最多一个持仓。
- 最大有效杠杆 2x；禁止亏损加仓。
- 15m 入场、1h 状态、4h 方向，只使用已收盘 K 线。
- 信号在下一根 15m 开盘成交并计入手续费、Funding 和滑点。
- 按账户风险除以止损距离计算名义仓位；不为满足最小下单额而放大风险。
- 5% 回撤降风险、8% 回撤暂停；连续亏损与近期胜率也进入状态机。
- OI 缺失时不得把信号升级为高质量。
- 回测必须输出稳定性、成本压力、市场状态和未来数据泄漏检查。

## 原型完成度

旧工作树中保留了 34 个 `btc_system` Python 文件、约 29 个对应测试，以及回测、paper、参数扫描和 readiness 脚本。所有 Python 文件可通过语法解析；归档时的通用运行环境缺少 `pytest`，因此没有把“测试存在”误报为“当前全部测试通过”。

历史 Phase 2 汇总曾把该原型标为通过，但结果目录包含大量重复的 signal audit，并且部分报告文本存在早期编码问题。该架构随后没有接入当前生产部署；生产路线继续采用 Freqtrade 策略、Supervisor、运行快照和自动发布体系。

## 可复用思想

- Regime 判断与开仓信号解耦。
- 所有交易决定携带 reasons/penalties。
- 风险状态机独立于单一策略类。
- 回测、模拟盘和生产共享成本与执行语义。
- OI/Funding 属于可降级数据源，缺失必须显式反映在置信度与权限上。

这些思想仍有价值，但原型代码本身已经成为替代路线，不应重新并入当前生产树。
