"""
双均线交叉策略 (Double EMA Crossover)
- 入门级量化策略
- 短期EMA上穿长期EMA → 买入
- 短期EMA下穿长期EMA → 卖出
- 附带RSI过滤和止损保护
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta


class DoublEMA(IStrategy):
    # 策略参数
    INTERFACE_VERSION = 3
    
    # 最小ROI：持仓多久后至少赚多少才卖
    minimal_roi = {
        "0": 0.05,    # 立即：5%利润就卖
        "30": 0.03,   # 30分钟后：3%利润就卖
        "60": 0.02,   # 1小时后：2%利润就卖
        "120": 0.01,  # 2小时后：1%利润就卖
    }

    # 止损：亏损超过3%自动卖出
    stoploss = -0.03

    # 追踪止损：价格上涨后，止损线跟着上移
    trailing_stop = True
    trailing_stop_positive = 0.01      # 盈利1%后启动追踪
    trailing_stop_positive_offset = 0.02  # 盈利2%时开始追踪
    trailing_only_offset_is_reached = True

    # K线周期
    timeframe = '1h'

    # 启动时需要的历史K线数量
    startup_candle_count = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算技术指标"""
        # 双均线
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=10)   # 快线：10周期
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=30)   # 慢线：30周期
        
        # RSI 过滤（防止追高）
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # 成交量均线（确认趋势有效性）
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """买入条件"""
        dataframe.loc[
            (
                # 快线上穿慢线（金叉）
                (dataframe['ema_fast'] > dataframe['ema_slow']) &
                (dataframe['ema_fast'].shift(1) <= dataframe['ema_slow'].shift(1)) &
                # RSI 不超买（< 70）
                (dataframe['rsi'] < 70) &
                # 成交量高于平均（确认趋势）
                (dataframe['volume'] > dataframe['volume_mean']) &
                # 基本过滤
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """卖出条件"""
        dataframe.loc[
            (
                # 快线下穿慢线（死叉）
                (dataframe['ema_fast'] < dataframe['ema_slow']) &
                (dataframe['ema_fast'].shift(1) >= dataframe['ema_slow'].shift(1)) &
                # 基本过滤
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1

        return dataframe
