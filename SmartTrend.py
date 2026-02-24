"""
智能趋势策略 (SmartTrend)
核心思路：
1. 布林带判断市场状态（趋势 vs 震荡）
2. 震荡市不交易，只在趋势市出手
3. MACD + EMA 双重确认趋势方向
4. RSI 防追高 + 成交量确认
5. 动态止损：赚得越多，保护越紧
"""
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class SmartTrend(IStrategy):
    INTERFACE_VERSION = 3

    # === 最小收益目标 ===
    # 不急着卖，让利润跑
    minimal_roi = {
        "0": 0.08,     # 8% 直接卖
        "60": 0.05,    # 1小时后 5% 就卖
        "180": 0.03,   # 3小时后 3% 就卖
        "360": 0.02,   # 6小时后 2% 就卖
    }

    # === 止损 ===
    stoploss = -0.05   # 最大亏损 5%（比 DoublEMA 的 3% 宽松）

    # === 追踪止损 ===
    # 价格上涨后，止损线跟着上移，锁住利润
    trailing_stop = True
    trailing_stop_positive = 0.015        # 涨了 1.5% 后开始追踪
    trailing_stop_positive_offset = 0.03  # 涨了 3% 才启动追踪
    trailing_only_offset_is_reached = True

    # K线周期
    timeframe = '1h'

    # 启动需要的历史K线
    startup_candle_count = 60

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算所有技术指标"""

        # ========== 1. 布林带（判断市场状态）==========
        # 布林带 = 中轨（均线）± 2倍标准差
        # 带宽窄 = 横盘震荡，带宽宽 = 趋势行情
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']
        
        # 布林带宽度（判断是否在震荡）
        dataframe['bb_width'] = (
            (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        )
        # 布林带宽度的均值（动态阈值）
        dataframe['bb_width_mean'] = dataframe['bb_width'].rolling(window=50).mean()

        # ========== 2. MACD（动量确认）==========
        # MACD > Signal线 = 上涨动量
        # MACD < Signal线 = 下跌动量
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macd_signal'] = macd['macdsignal']
        dataframe['macd_hist'] = macd['macdhist']  # 柱状图

        # ========== 3. EMA 均线（趋势方向）==========
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)
        dataframe['ema_trend'] = ta.EMA(dataframe, timeperiod=50)  # 大趋势

        # ========== 4. RSI（超买超卖）==========
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # ========== 5. 成交量 ==========
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_mean']

        # ========== 6. ATR（波动率，用于判断市场活跃度）==========
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['atr_pct'] = dataframe['atr'] / dataframe['close']  # ATR 占价格的百分比

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        买入条件（必须同时满足所有条件）：
        1. 布林带在扩张（不是震荡市）
        2. 价格在 EMA50 上方（大趋势向上）
        3. EMA 金叉（短期趋势向上）
        4. MACD 柱状图为正且在增长（动量在加速）
        5. RSI 在合理区间（不追高）
        6. 成交量放大（有真实买盘）
        """
        dataframe.loc[
            (
                # 条件1：布林带扩张 → 市场在走趋势，不是横盘
                (dataframe['bb_width'] > dataframe['bb_width_mean']) &

                # 条件2：价格在大趋势线上方 → 大方向是涨的
                (dataframe['close'] > dataframe['ema_trend']) &

                # 条件3：EMA 金叉 → 短期趋势刚转多
                (dataframe['ema_fast'] > dataframe['ema_slow']) &
                (dataframe['ema_fast'].shift(1) <= dataframe['ema_slow'].shift(1)) &

                # 条件4：MACD 柱状图为正 → 上涨动量确认
                (dataframe['macd_hist'] > 0) &

                # 条件5：RSI 在 35-65 之间 → 不追高也不抄底
                (dataframe['rsi'] > 35) &
                (dataframe['rsi'] < 65) &

                # 条件6：成交量 > 平均值的 1.2 倍 → 有真实交易
                (dataframe['volume_ratio'] > 1.2) &

                # 基本过滤
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        卖出条件（满足任一即卖）：
        信号1：EMA 死叉 + MACD 转负（趋势反转）
        信号2：RSI 超买（> 75）+ MACD 柱状图缩小（涨不动了）
        """
        dataframe.loc[
            (
                (
                    # 信号1：趋势反转
                    (dataframe['ema_fast'] < dataframe['ema_slow']) &
                    (dataframe['macd_hist'] < 0)
                ) |
                (
                    # 信号2：超买 + 动量衰减
                    (dataframe['rsi'] > 75) &
                    (dataframe['macd_hist'] < dataframe['macd_hist'].shift(1)) &
                    (dataframe['macd_hist'].shift(1) < dataframe['macd_hist'].shift(2))
                )
            ) &
            (dataframe['volume'] > 0),
            'exit_long'] = 1

        return dataframe
