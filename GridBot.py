"""
网格交易策略 (GridBot)

核心思路：
价格像弹球一样在一个区间里来回跳，
每次跳到下面就买一点，弹到上面就卖一点。
不需要判断趋势，震荡市就能赚钱。

原理图：
  卖 ──── 1050  ←  涨到这里卖掉，赚差价
  卖 ──── 1040
  卖 ──── 1030
  当前 ── 1020
  买 ──── 1010
  买 ──── 1000  ←  跌到这里买入，等反弹
  买 ────  990

freqtrade 不支持传统挂单网格，所以用"均值回归"模拟：
- 价格跌到布林带下轨 → 便宜了，买
- 价格涨到布林带上轨 → 贵了，卖
- 配合 RSI 超卖/超买确认
- 用 DCA（分批加仓）模拟多层网格
"""
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np


class GridBot(IStrategy):
    INTERFACE_VERSION = 3

    # === 收益目标：小利多销 ===
    minimal_roi = {
        "0": 0.03,     # 3% 就卖（网格利润本来就薄）
        "60": 0.02,    # 1小时后 2% 就卖
        "180": 0.015,  # 3小时后 1.5%
        "360": 0.01,   # 6小时后 1%
    }

    # === 止损：网格策略止损要宽一些 ===
    stoploss = -0.08   # 8% 止损（给价格回弹的空间）

    # === 追踪止损 ===
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # === 分批加仓（模拟网格层级）===
    position_adjustment_enable = True
    max_entry_position_adjustment = 2  # 最多加仓 2 次（共 3 层）

    # K线周期：15分钟（网格策略需要更快反应）
    timeframe = '15m'

    startup_candle_count = 100

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """计算指标"""

        # ========== 布林带（定义价格区间）==========
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_lower'] = bollinger['lowerband']

        # 价格在布林带中的位置（0=下轨, 0.5=中轨, 1=上轨）
        dataframe['bb_percent'] = (
            (dataframe['close'] - dataframe['bb_lower']) /
            (dataframe['bb_upper'] - dataframe['bb_lower'])
        )

        # 布林带宽度
        dataframe['bb_width'] = (
            (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        )

        # ========== RSI ==========
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # ========== 成交量 ==========
        dataframe['volume_mean'] = dataframe['volume'].rolling(window=20).mean()

        # ========== 支撑/阻力参考 ==========
        # 最近 50 根K线的最高最低
        dataframe['recent_high'] = dataframe['high'].rolling(window=50).max()
        dataframe['recent_low'] = dataframe['low'].rolling(window=50).min()
        dataframe['price_range'] = dataframe['recent_high'] - dataframe['recent_low']

        # 价格在区间中的位置（0=最低点, 1=最高点）
        dataframe['range_percent'] = np.where(
            dataframe['price_range'] > 0,
            (dataframe['close'] - dataframe['recent_low']) / dataframe['price_range'],
            0.5
        )

        # ========== 均线（判断大趋势，防止逆势抄底）==========
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        # ========== MFI 资金流向 ==========
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        买入条件：价格跌到"便宜区"
        1. 价格触及或跌破布林带下轨
        2. RSI 超卖（< 35）
        3. 有成交量（不是无量阴跌）
        4. 价格没有远低于 EMA200（防止接飞刀）
        """
        dataframe.loc[
            (
                # 价格在布林带下方 20% 区域
                (dataframe['bb_percent'] < 0.2) &

                # RSI 超卖
                (dataframe['rsi'] < 35) &

                # 成交量存在
                (dataframe['volume'] > dataframe['volume_mean'] * 0.5) &

                # 价格不能太离谱（不低于 EMA200 的 90%）
                (dataframe['close'] > dataframe['ema_200'] * 0.90) &

                # MFI 也在低位（资金在流入）
                (dataframe['mfi'] < 40) &

                # 基本过滤
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        卖出条件：价格涨到"贵区"
        1. 价格触及布林带上轨
        2. RSI 超买
        """
        dataframe.loc[
            (
                (
                    # 价格在布林带上方 80% 区域 + RSI 超买
                    (dataframe['bb_percent'] > 0.8) &
                    (dataframe['rsi'] > 65)
                ) |
                (
                    # 或者 RSI 严重超买
                    (dataframe['rsi'] > 78)
                )
            ) &
            (dataframe['volume'] > 0),
            'exit_long'] = 1

        return dataframe

    def adjust_trade_position(self, trade, current_time, current_rate,
                              current_profit, min_stake, max_stake,
                              current_entry_rate, current_exit_rate,
                              current_entry_profit, current_exit_profit,
                              **kwargs):
        """
        分批加仓（模拟网格的多层买入）
        - 亏损 3% → 加仓 1 次（第 2 层网格）
        - 亏损 5% → 再加仓 1 次（第 3 层网格）
        每次加仓拉低均价，等反弹就能赚
        """
        if current_profit > -0.03:
            return None  # 还没跌够，不加仓

        filled_entries = trade.nr_of_successful_entries

        # 第 2 层：亏 3% 加仓
        if filled_entries == 1 and current_profit < -0.03:
            return trade.stake_amount  # 加同样的金额

        # 第 3 层：亏 5% 再加仓（加更多，拉低均价）
        if filled_entries == 2 and current_profit < -0.05:
            return trade.stake_amount * 1.5  # 加 1.5 倍

        return None
