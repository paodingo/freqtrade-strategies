"""Regime-aware strategy: auto-detects trending vs ranging and adapts behavior."""
from datetime import datetime, timedelta

from pandas import DataFrame

import talib.abstract as ta

from freqtrade.strategy import IStrategy, merge_informative_pair
from freqtrade.persistence import Trade

from .regime_detector import RegimeDetector
from .risk_manager import RiskManager


class RegimeAware(IStrategy):
    INTERFACE_VERSION = 3

    # --- ROI & Stoploss ---
    minimal_roi = {
        "0": 0.10,
        "720": 0.05,
    }

    stoploss = -0.07

    # --- Trailing stop (static fallback, overridden by custom_stoploss) ---
    trailing_stop = False

    # --- Timeframe ---
    timeframe = "1h"
    startup_candle_count = 200

    # --- Position adjustment (disabled — no DCA) ---
    position_adjustment_enable = False

    # --- Risk parameters ---
    risk_max_positions = 2

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.regime_detector = RegimeDetector()
        self.risk_manager = RiskManager(max_positions=self.risk_max_positions)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Compute all indicators on both 4h (regime) and 1h (trading)."""

        # === 4h indicators ===
        informative_4h = self.dp.get_pair_dataframe(
            pair=metadata["pair"], timeframe="4h"
        )
        informative_4h = self.regime_detector.compute_indicators(informative_4h)
        informative_4h["ema21"] = ta.EMA(informative_4h, timeperiod=21)
        informative_4h["ema55"] = ta.EMA(informative_4h, timeperiod=55)
        informative_4h["plus_di"] = ta.PLUS_DI(informative_4h, timeperiod=14)
        informative_4h["minus_di"] = ta.MINUS_DI(informative_4h, timeperiod=14)

        # Run regime detection sequentially through 4h candles
        self.regime_detector.reset()
        regimes = []
        min_candles = self.startup_candle_count
        for i in range(len(informative_4h)):
            if i < min_candles:
                regimes.append(RegimeDetector.RANGING)
            else:
                regime = self.regime_detector.detect(informative_4h.iloc[: i + 1])
                regimes.append(regime)
        informative_4h["regime"] = regimes

        # Merge 4h into 1h (regime column gets forward-filled to 1h)
        dataframe = merge_informative_pair(
            dataframe, informative_4h, self.timeframe, "4h", ffill=True
        )

        # === 1h indicators ===
        dataframe["ema21"] = ta.EMA(dataframe, timeperiod=21)
        dataframe["ema55"] = ta.EMA(dataframe, timeperiod=55)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)

        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_middle"] = bb["middleband"]
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_width"] = (
            (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        )
        dataframe["bb_width_mean"] = dataframe["bb_width"].rolling(50).mean()
        dataframe["bb_width_low_20"] = dataframe["bb_width"].rolling(20).min()
        dataframe["bb_percent"] = (
            (dataframe["close"] - dataframe["bb_lower"])
            / (dataframe["bb_upper"] - dataframe["bb_lower"])
        ).clip(0, 1)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_mean"] = dataframe["volume"].rolling(20).mean()
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Hammer candle detection
        body = abs(dataframe["close"] - dataframe["open"])
        lower_wick = dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        upper_wick = dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        dataframe["is_hammer"] = (
            (lower_wick > body * 2) & (lower_wick > 0) & (upper_wick < body * 0.5)
        )

        # === Trending mode entry signals ===
        dataframe["trend_4h_up"] = (
            (dataframe["ema21_4h"] > dataframe["ema55_4h"])
            & (dataframe["close_4h"] > dataframe["ema55_4h"])
            & (dataframe["adx_4h"] > 25)
            & (dataframe["plus_di_4h"] > dataframe["minus_di_4h"])
        )

        dataframe["pullback_ema"] = (
            (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.01)
            & (dataframe["is_hammer"])
        )

        dataframe["bb_squeeze"] = (
            dataframe["bb_width"] <= dataframe["bb_width_low_20"] * 1.05
        )
        dataframe["bb_breakout"] = (
            dataframe["bb_squeeze"]
            & (dataframe["close"] > dataframe["bb_upper"])
            & (dataframe["volume"] > dataframe["volume_mean"])
        )

        dataframe["rsi_recovery"] = (
            (dataframe["rsi"].shift(1) < 40) & (dataframe["rsi"] > 45)
        )

        # === Ranging mode entry signals ===
        dataframe["ranging_entry_setup"] = (
            (dataframe["bb_percent"] < 0.15)
            & (dataframe["rsi"] < 35)
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.8)
            & (dataframe["close"] > dataframe["ema200"] * 0.92)
            & (dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * 1.3)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Entry signals for both trending and ranging modes."""

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.TRENDING)
                & (dataframe["trend_4h_up"])
                & (
                    dataframe["pullback_ema"]
                    | dataframe["bb_breakout"]
                    | dataframe["rsi_recovery"]
                )
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "trending")

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["ranging_entry_setup"])
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "ranging")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Exit signals for safety conditions."""

        # Trending: exit on 4h trend reversal
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.TRENDING)
                & (dataframe["ema21_4h"] < dataframe["ema55_4h"])
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_reversal_4h")

        # Ranging: exit on trend breakdown below EMA200
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["close"] < dataframe["ema200"] * 0.90)
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "ranging_breakdown")

        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float,
                        after_fill: bool, **kwargs) -> float:
        """ATR-based dynamic trailing stop for trending mode.
        For ranging mode, uses tighter percentage-based stop."""
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return self.stoploss

        last = dataframe.iloc[-1]
        entry_mode = trade.enter_tag or "trending"

        if entry_mode == "trending":
            atr_pct = last.get("atr", 0) / current_rate if current_rate > 0 else 0.01
            if current_profit > atr_pct * 2:
                return -atr_pct * 1.5
            return -0.07

        else:  # ranging
            return -0.05

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs):
        """Custom exit logic.
        Ranging: BB middle/upper targets, 48h time stop.
        Trending: 4h trend reversal check.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        last = dataframe.iloc[-1]
        entry_mode = trade.enter_tag or "trending"

        if entry_mode == "ranging":
            trade_duration = current_time - trade.open_date_utc
            if trade_duration > timedelta(hours=48):
                return "ranging_time_stop"

            bb_upper = last.get("bb_upper", 0)
            if bb_upper > 0 and current_rate >= bb_upper:
                return "ranging_target_upper"

            bb_middle = last.get("bb_middle", 0)
            if bb_middle > 0 and current_rate >= bb_middle:
                return "ranging_target_middle"

            rsi = last.get("rsi", 50)
            if rsi > 65:
                return "ranging_overbought"

        if entry_mode == "trending":
            ema21_4h = last.get("ema21_4h", 0)
            ema55_4h = last.get("ema55_4h", 0)
            if ema21_4h > 0 and ema55_4h > 0 and ema21_4h < ema55_4h:
                return "trending_reversal"

        return None

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: str, side: str, **kwargs) -> bool:
        """Circuit breaker check before entry."""
        if self.risk_manager.is_circuit_breaker_active():
            cooldown = self.risk_manager.get_cooldown_remaining()
            if cooldown:
                self.log_once(
                    f"Circuit breaker active. Cooldown remaining: {cooldown}",
                    log_level="warning",
                )
            return False

        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self.risk_max_positions:
            return False

        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str,
                           exit_reason: str, current_time: datetime, **kwargs) -> bool:
        """Track trade results for circuit breaker."""
        profit_ratio = trade.calc_profit_ratio(rate)
        self.risk_manager.record_trade_result(profit_ratio, current_time)
        return True

    def bot_start(self, **kwargs):
        """Reset state at bot start."""
        self.regime_detector.reset()
        self.risk_manager.reset()
