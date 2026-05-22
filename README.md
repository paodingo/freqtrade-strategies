# Freqtrade 策略集合

基于 [freqtrade](https://github.com/freqtrade/freqtrade) 的交易策略。

## 策略说明

### RegimeAware（当前）

市场状态自适应策略，自动识别趋势/震荡并切换交易逻辑。

**架构**：
- **第 1 层 — 状态识别（4h）**：ADX + 布林带宽度 + ATR 三指标投票，3 根 K 线确认，带缓冲防抖
- **第 2 层 — 交易逻辑**：
  - 趋势模式：4h 定方向 + 1h 回调入场，ATR 追踪止损
  - 震荡模式：布林带均值回归，中轨/上轨分批止盈，48h 超时保护
- **第 3 层 — 统一风控**：ATR 动态止损 + 7% 硬止损 + 连亏 3 笔熔断 24h

**约束**：BTC/ETH 现货，做多 only，中等风险

## 使用方法

```bash
# 下载数据
freqtrade download-data --exchange binance --pairs BTC/USDT \
  --timeframes 1h 4h --timerange 20240101- \
  --config user_data/config_btc.json

# 回测
freqtrade backtesting --strategy RegimeAware \
  --strategy-path strategies \
  --config user_data/config_btc.json \
  --timerange 20240101-20260522

# 实盘（dry_run 模式下先验证）
freqtrade trade --strategy RegimeAware \
  --strategy-path strategies \
  --config user_data/config_btc.json
```

## 项目结构

```
strategies/
  RegimeAware.py         # 主策略
  regime_detector.py     # 状态识别模块
  risk_manager.py        # 风控模块
tests/                   # 单元测试
user_data/               # freqtrade 配置
docs/superpowers/        # 设计文档和计划
```

## 风险提示

回测结果不等于实盘表现，请谨慎交易。
