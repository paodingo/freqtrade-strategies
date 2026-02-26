# SmartTrend 策略优化建议

## 一、 引入动态波动率（ATR）优化追踪止损

**问题**：原本使用写死的固定比例（涨3%回撤1.5%止损），在波动率相差极大的币种（比如 BTC 波动小，MEME 币波动大）上表现会极不适应。

**优化方案**：改用系统内置的自定义止损函数（`custom_stoploss`），利用 `ATR` 动态计算安全距离。当处于高波动率时，给市场留足震荡空间；低波动率时，收紧止损保护利润。

**代码实现**：
```python
    # 启用自定义止损开关
    use_custom_stoploss = True

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        动态追踪止损：如果赚得不多，用基础保底 5%止损。
        如果利润超过了当前币种 2 倍 ATR 的波动范围，就开始动态收紧止损线到 1.5 倍 ATR 位置。
        由于每次运算都读取当前K线最新 ATR，从而实现：高波动留空间，低波动早套现。
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # 提取动态 ATR (百分比形式)
        atr_pct = last_candle['atr_pct']

        # 如果目前的利润已经覆盖了 2 倍的 ATR 正常波动率，说明走出了趋势
        if current_profit > (atr_pct * 2):
            # 锁定在最高点回落 1.5 倍 ATR 的位置。
            # 这是自适应的 trailing stop！
            return -(atr_pct * 1.5)

        # 还没涨跌出趋势前，保持静态最大容忍回撤
        return -0.05
```

## 二、 放宽“瞬时共振”的进场条件

**问题**：原版要求 EMA金叉、MACD由负转正、布林带张口 必须在同一根 K向上发生，很容易因为指标快慢不同步而错过最有利的行情。

**优化方案**：将“瞬间金叉”改为“状态保持”，即“短期趋势已经形成，只需等待回踩或动能确认即可”。

**代码实现（修改 `populate_entry_trend`）**：
```python
                # 优化前：只有发生金叉的一瞬间进（错过就没了）
                # (dataframe['ema_fast'] > dataframe['ema_slow']) &
                # (dataframe['ema_fast'].shift(1) <= dataframe['ema_slow'].shift(1))
                
                # 优化后：只要多头排列成立（快线 > 慢线），且不追高（RSI有控制）即可
                (dataframe['ema_fast'] > dataframe['ema_slow']) &
                
                # 可以额外加一个“近期刚金叉”的宽松条件，比如“近 5 根 K 线内发生过金叉”
                # 放宽同步发生的苛刻要求，大幅度增加交易信号（避免踏空）
                
                # ...其余条件保持... / 可以把 RSI 的容忍度调宽松一点：
                (dataframe['rsi'] > 40) & 
                (dataframe['rsi'] < 70) &
```

## 三、 加入大级别多时间框架（MTF）过滤

**问题**：即使 1 小时级别满足了突破条件，如果日线（1d）或 4小时线（4h）处于大暴跌趋势中，1小时的突破大概率是“诱多死猫跳”。

**优化方案**：获取大周期（比如 4h 或 1d）的趋势线，作为不可违背的“防守底线”。

**代码实现（修改 `populate_indicators` 和入场条件）**：
```python
    from freqtrade.strategy import merge_informative_pair

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 获取 4h 级别的 K 线数据
        informative = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='4h')
        # 在 4h 级别算一根 EMA 50 大趋势线
        informative['ema_50_4h'] = ta.EMA(informative, timeperiod=50)
        
        # 将 4h 数据合并到我们 1h 的表中
        dataframe = merge_informative_pair(dataframe, informative, '1h', '4h', ffill=True)

        # ...下方计算原先 1h 的各个指标...
```

入场条件中加上最强过滤网：
```python
        dataframe.loc[
            (
                # 【新增】必须确保大级别（4小时线）的价格处于多头趋势！有效过滤大熊市的反抽
                (dataframe['close'] > dataframe['ema_50_4h_4h']) & 
                
                # ... 原本的1小时级别突破条件 ...
            )
        ]
```

## 四、 拥抱 Freqtrade 的特性：参数超参寻优 (Hyperopt)

**问题**：写死的参数（如 14, 20, 50, 65 等）无法适应不断变化的市场。

**优化方案**：利用 Freqtrade 强大的 `Hyperopt` 功能，让机器学习自动寻找最佳配置。

**代码实现**：
```python
    from freqtrade.strategy import IntParameter
    
    # === 将固定参数升级为可优化的空间 ===
    # 让机器在 60 到 75 之间去跑回测找最优RSI上限
    buy_rsi_max = IntParameter(60, 75, default=65, space='buy', optimize=True)
    buy_rsi_min = IntParameter(30, 45, default=35, space='buy', optimize=True)
    
    # 布林带计算周期：在 15-30 之间寻找
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 使用超参空间变量
                (dataframe['rsi'] > self.buy_rsi_min.value) &
                (dataframe['rsi'] < self.buy_rsi_max.value) &
                # ...
            )
        ]
```
> 后续可通过运行 `freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces buy roi stoploss` 寻找最佳参数组合。
