# Freqtrade 策略集合

智能趋势策略 + 双均线 + 网格策略

## 策略说明

### SmartTrend (推荐)
智能趋势策略，只在趋势市交易，震荡市空仓
- 布林带判断市场状态
- EMA + MACD 双重确认趋势
- RSI 防追高
- 回测：2024-2026 亏损 6.1%，最大回撤 11%

### DoublEMA
双均线交叉策略（入门级）
- EMA10 上穿 EMA30 买入
- 带有 RSI 和成交量过滤
- 回测：2024-2026 亏损 36.8%

### GridBot
均值回归网格策略（震荡市专用）
- 布林带上下轨买卖
- 分批加仓（DCA）
- 回测：2024-2026 亏损 91.7%（单边下跌时风险高）

## 使用方法

```bash
cd /root/freqtrade
freqtrade trade --config user_data/config.json --strategy SmartTrend
```

## 风险提示

回测结果不等于实盘表现，请谨慎交易。
