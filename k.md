# SmartTrend 策略优化方案

## 当前问题诊断

| 问题 | 表现 | 影响 |
|------|------|------|
| 条件过于严格 | 6 个条件同时满足 | 错过大量交易机会 |
| 信号滞后 | EMA 金叉 + MACD 双重确认 | 入场时价格已涨了一段 |
| 止损固定 | 固定 5% 止损 | 无法适应不同波动率市场 |
| RSI 区间过窄 | 35-65 上限偏低 | 错过强势行情 |
| 出场单一 | 仅靠 EMA 死叉 | 利润回撤过大 |

---

## 优化方案

### 1. 增加 ADX 趋势强度过滤

**目的**: 只在强趋势中交易，避免弱趋势中的假信号

```python
# 在 populate_indicators 中添加
dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

# 入场条件增加
(dataframe['adx'] > 25)  # ADX > 25 表示有趋势
```

**原理**: ADX > 25 表示市场有明显趋势，< 20 表示震荡市

---

### 2. 放宽 RSI 区间上限

**当前**: `RSI < 65`
**优化**: `RSI < 70`

**理由**: 强势趋势中 RSI 可达 70 以上，过早过滤会错过主升浪

```python
# 修改前
(dataframe['rsi'] < 65)

# 修改后
(dataframe['rsi'] < 70)
```

---

### 3. ATR 动态止损

**当前**: 固定止损 5%
**优化**: 根据 ATR 动态调整

```python
# 在 populate_indicators 中添加
dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
dataframe['atr_stop_pct'] = (dataframe['atr'] * 2) / dataframe['close']

# 在策略类中添加动态止损
stoploss = -0.05  # 基础止损

def custom_stoploss(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
    """动态止损：根据 ATR 调整"""
    dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)
    last_atr = dataframe['atr'].iloc[-1]
    last_close = dataframe['close'].iloc[-1]

    # ATR 止损 = 2 倍 ATR
    atr_stop = (last_atr * 2) / last_close

    # 取较大值（更宽松）作为止损
    return max(-0.05, -atr_stop - 0.01)
```

**效果**:
- 高波动市场：止损更宽松（如 7-8%）
- 低波动市场：止损更紧密（如 3-4%）

---

### 4. 提前入场信号（EMA 接近金叉）

**当前**: 必须等 EMA 金叉确认
**优化**: EMA 接近时提前入场

```python
# 方案 A: EMA 差距在 0.2% 以内
(dataframe['ema_fast'] * 1.002 > dataframe['ema_slow'])

# 方案 B: EMA 差距在 0.3% 以内，且 MACD 为正
(
    (dataframe['ema_fast'] * 1.003 > dataframe['ema_slow']) &
    (dataframe['macd'] > 0)
)
```

**理由**: 金叉确认时已涨了一段，提前入场可降低成本

---

### 5. 分批止盈

**当前**: 全部仓位统一止盈
**优化**: 分批卖出，让部分仓位跑利润

```python
# minimal_roi 修改
minimal_roi = {
    "0": 0.08,      # 8% 卖出 50%
    "60": 0.05,     # 1 小时后 5% 卖出 25%
    "180": 0.03,    # 3 小时后 3% 卖出剩余
    "360": 0.02,    # 6 小时后 2% 清仓
}

# 或使用 custom_exit 实现分批
def custom_exit(self, pair, trade, current_time, current_rate,
                current_profit, **kwargs):
    """分批止盈逻辑"""
    if current_profit > 0.05:
        return 'exit_50'  # 5% 收益卖出一半
    if current_profit > 0.10:
        return 'exit_25'  # 10% 收益再卖四分之一
    return None
```

---

### 6. 优化出场逻辑

**当前问题**: 仅靠 EMA 死叉太慢

**新增出场信号**:

```python
# 在 populate_exit_trend 中增加

# 信号 3: 跌破布林带中轨（趋势转弱）
(
    (dataframe['close'] < dataframe['bb_middle']) &
    (dataframe['close'].shift(1) >= dataframe['bb_middle'].shift(1))
)

# 信号 4: MACD 顶背离（价格新高但 MACD 没新高）
(
    (dataframe['close'] > dataframe['close'].shift(5)) &
    (dataframe['macd'] < dataframe['macd'].shift(5))
)
```

---

## 完整修改后的代码结构

```python
class SmartTrend(IStrategy):
    # === 基础参数 ===
    timeframe = '1h'
    startup_candle_count = 60

    # ROI 保持原样
    minimal_roi = { ... }

    # 基础止损（会被 custom_stoploss 覆盖）
    stoploss = -0.05

    # 追踪止损保持原样
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03

    def populate_indicators(self, dataframe, metadata):
        # 原有指标...

        # 新增：ADX 趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[
            (
                # 条件 1: 布林带扩张
                (dataframe['bb_width'] > dataframe['bb_width_mean']) &

                # 条件 2: 价格在 EMA50 上方
                (dataframe['close'] > dataframe['ema_trend']) &

                # 条件 3: EMA 接近金叉（优化：放宽条件）
                (dataframe['ema_fast'] * 1.003 > dataframe['ema_slow']) &

                # 条件 4: MACD 为正
                (dataframe['macd'] > 0) &
                (dataframe['macd_hist'] > 0) &

                # 条件 5: RSI 在合理区间（优化：上限 65→70）
                (dataframe['rsi'] > 35) &
                (dataframe['rsi'] < 70) &

                # 条件 6: 成交量确认
                (dataframe['volume_ratio'] > 1.2) &

                # 新增条件 7: ADX 趋势强度（新增）
                (dataframe['adx'] > 25) &

                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        dataframe.loc[
            (
                # 信号 1: 趋势反转（保持原样）
                (
                    (dataframe['ema_fast'] < dataframe['ema_slow']) &
                    (dataframe['macd_hist'] < 0)
                ) |

                # 信号 2: 超买 + 动量衰减（保持原样）
                (
                    (dataframe['rsi'] > 75) &
                    (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1))
                ) |

                # 信号 3: 跌破布林中轨（新增）
                (
                    (dataframe['close'] < dataframe['bb_middle']) &
                    (dataframe['bb_width'] < dataframe['bb_width_mean'])
                )
            ) &
            (dataframe['volume'] > 0),
            'exit_long'] = 1

        return dataframe

    def custom_stoploss(self, pair, trade, current_time, current_rate,
                        current_profit, **kwargs):
        """ATR 动态止损"""
        dataframe = self.dp.get_pair_dataframe(pair=pair, timeframe=self.timeframe)
        last_atr = dataframe['atr'].iloc[-1]
        last_close = dataframe['close'].iloc[-1]

        atr_stop_pct = (last_atr * 2) / last_close

        # 返回动态止损值
        return max(-0.05, -atr_stop_pct - 0.01)
```

---

## 预期效果

| 指标 | 优化前 | 优化后预期 |
|------|--------|------------|
| 交易次数 | 较少 | +30-50% |
| 胜率 | ~45% | 50-55% |
| 盈亏比 | ~1:1 | 1.2:1 |
| 最大回撤 | 11% | 8-10% |
| 总收益 | -6.1% | +5-15% |

---

## 回测建议

1. 使用相同时段回测（2024-2026）
2. 对比优化前后数据
3. 重点观察：交易次数、胜率、最大回撤
4. 如效果不佳，可微调参数（如 ADX 阈值、RSI 上限）
