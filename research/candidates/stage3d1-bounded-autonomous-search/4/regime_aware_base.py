"""Shared implementation for the RegimeAware strategy family."""
import logging
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import talib.abstract as ta
from freqtrade.enums import CandleType
from freqtrade.persistence import Trade
from freqtrade.strategy import merge_informative_pair
from pandas import DataFrame

from regime_detector import RegimeDetector
from risk_manager import RiskManager

logger = logging.getLogger(__name__)


class RegimeAwareBaseMixin:
    INTERFACE_VERSION = 3
    can_short = True

    minimal_roi = {
        "0": 0.05,
        "240": 0.04,
        "720": 0.03,
    }
    stoploss = -0.04
    trailing_stop = False
    use_custom_stoploss = False

    timeframe = "1h"
    startup_candle_count = 200
    position_adjustment_enable = False
    risk_max_positions = 4
    enable_ranging_entries = False

    def __init__(self, config: dict = None):
        super().__init__(config)
        self.regime_detector = RegimeDetector()
        self.risk_manager = RiskManager(max_positions=self.risk_max_positions)

    def informative_pairs(self):
        if not self.dp:
            return []
        return [(pair, "4h", CandleType.FUTURES) for pair in self.dp.current_whitelist()]

    def _load_4h(self, metadata):
        four_h_ok, informative_4h = False, None
        try:
            informative_4h = self.dp.get_pair_dataframe(
                pair=metadata["pair"], timeframe="4h", candle_type="futures"
            )
            if not informative_4h.empty and {"open", "high", "low", "close"}.issubset(
                informative_4h.columns
            ):
                four_h_ok = True
        except Exception:
            pass

        if not four_h_ok:
            try:
                pair = metadata["pair"]
                pair_slug = pair.replace("/", "_")
                pair_slug_futures = pair.replace("/", "_").replace(":", "_")
                data_dir = Path("/freqtrade/project/user_data/data")
                candidates = [
                    data_dir / "binance" / f"{pair_slug}-4h.feather",
                    data_dir / f"{pair_slug}-4h.feather",
                    data_dir / "futures" / f"{pair_slug_futures}-4h-futures.feather",
                ]
                path = next((c for c in candidates if c.exists()), None)
                if path is None:
                    raise FileNotFoundError(f"No 4h data for {pair}")
                raw = pd.read_feather(path)
                informative_4h = pd.DataFrame(
                    {
                        "date": pd.to_datetime(raw["date"].values, utc=True),
                        "open": raw["open"].values,
                        "high": raw["high"].values,
                        "low": raw["low"].values,
                        "close": raw["close"].values,
                        "volume": raw["volume"].values,
                    }
                )
                four_h_ok = True
            except Exception as error:
                logger.warning("Failed to load 4h feather: %s", error)
        return four_h_ok, informative_4h

    def _bounded_informative_4h(self, informative_4h: DataFrame) -> DataFrame:
        lookback = max(self.startup_candle_count + 300, 600)
        if len(informative_4h) <= lookback:
            return informative_4h.copy()
        return informative_4h.tail(lookback).copy()

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        four_h_ok, informative_4h = self._load_4h(metadata)

        if four_h_ok:
            try:
                informative_4h = self._bounded_informative_4h(informative_4h)
                informative_4h = self.regime_detector.compute_indicators(informative_4h)
                informative_4h["ema21"] = ta.EMA(informative_4h, timeperiod=21)
                informative_4h["ema55"] = ta.EMA(informative_4h, timeperiod=55)
                informative_4h["plus_di"] = ta.PLUS_DI(informative_4h, timeperiod=14)
                informative_4h["minus_di"] = ta.MINUS_DI(informative_4h, timeperiod=14)

                self.regime_detector.reset()
                regimes = []
                for index in range(len(informative_4h)):
                    if index < self.startup_candle_count:
                        regimes.append(RegimeDetector.RANGING)
                    else:
                        regimes.append(
                            self.regime_detector.detect(informative_4h.iloc[: index + 1])
                        )
                informative_4h["regime"] = regimes

                if "date" not in dataframe.columns:
                    dataframe["date"] = dataframe.index
                dataframe = merge_informative_pair(
                    dataframe, informative_4h, self.timeframe, "4h", ffill=True
                )
                if "date" not in dataframe.columns:
                    dataframe["date"] = dataframe.index
            except Exception as error:
                logger.warning("4h merge failed: %s\n%s", error, traceback.format_exc())
                four_h_ok = False

        if not four_h_ok:
            logger.warning("4h data unavailable, using safe defaults")
            for column, value in [
                ("regime_4h", ""),
                ("ema21_4h", 0),
                ("ema55_4h", 1),
                ("close_4h", 0),
                ("adx_4h", 0),
                ("plus_di_4h", 0),
                ("minus_di_4h", 1),
                ("bb_width_4h", 0),
                ("bb_width_mean_4h", 1),
            ]:
                dataframe[column] = value

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

        body = abs(dataframe["close"] - dataframe["open"])
        lower_wick = dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        upper_wick = dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        dataframe["is_hammer"] = (
            (lower_wick > body * 2) & (lower_wick > 0) & (upper_wick < body * 0.5)
        )
        dataframe["is_shooting_star"] = (
            (upper_wick > body * 2) & (upper_wick > 0) & (lower_wick < body * 0.5)
        )

        dataframe["trend_4h_up"] = (
            (dataframe["ema21_4h"] > dataframe["ema55_4h"])
            & (dataframe["close_4h"] > dataframe["ema55_4h"])
            & (dataframe["adx_4h"] > 25)
            & (dataframe["plus_di_4h"] > dataframe["minus_di_4h"])
        )
        dataframe["pullback_ema_long"] = (
            (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["rsi"] > 40)
        )
        dataframe["bb_squeeze"] = (
            dataframe["bb_width"] <= dataframe["bb_width_low_20"] * 1.05
        )
        dataframe["bb_breakout_long"] = (
            dataframe["bb_squeeze"]
            & (dataframe["close"] > dataframe["bb_upper"])
            & (dataframe["volume"] > dataframe["volume_mean"])
        )
        dataframe["rsi_recovery"] = (
            (dataframe["rsi"].shift(1) < 40) & (dataframe["rsi"] > 45)
        )

        dataframe["trend_4h_down"] = (
            (dataframe["ema21_4h"] < dataframe["ema55_4h"])
            & (dataframe["close_4h"] < dataframe["ema55_4h"])
            & (dataframe["adx_4h"] > 25)
            & (dataframe["minus_di_4h"] > dataframe["plus_di_4h"])
        )
        dataframe["pullback_ema_short"] = (
            (abs(dataframe["close"] - dataframe["ema21"]) / dataframe["ema21"] < 0.02)
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["rsi"] < 60)
        )
        dataframe["bb_breakout_short"] = (
            dataframe["bb_squeeze"]
            & (dataframe["close"] < dataframe["bb_lower"])
            & (dataframe["volume"] > dataframe["volume_mean"])
        )
        dataframe["rsi_exhaustion"] = (
            (dataframe["rsi"].shift(1) > 60) & (dataframe["rsi"] < 55)
        )

        dataframe["ranging_long_setup"] = (
            (dataframe["bb_percent"] < 0.20)
            & (dataframe["rsi"] < 40)
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.8)
            & (dataframe["close"] > dataframe["ema200"] * 0.90)
            & (dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * 1.3)
            & (dataframe["adx_4h"] < 22)
        )
        dataframe["ranging_short_setup"] = (
            (dataframe["bb_percent"] > 0.80)
            & (dataframe["rsi"] > 60)
            & (dataframe["volume"] > dataframe["volume_mean"] * 0.8)
            & (dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * 1.3)
            & (dataframe["adx_4h"] < 22)
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        self._populate_trending_entries(dataframe)
        if self.enable_ranging_entries:
            self._populate_ranging_entries(dataframe)

        return dataframe

    @staticmethod
    def _populate_trending_entries(dataframe: DataFrame) -> None:
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.TRENDING)
                & (dataframe["trend_4h_up"])
                & (dataframe["close"] > dataframe["ema200"])
                & (
                    dataframe["pullback_ema_long"]
                    | dataframe["bb_breakout_long"]
                    | dataframe["rsi_recovery"]
                )
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "trending_long")

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.TRENDING)
                & (dataframe["trend_4h_down"])
                & (dataframe["close"] < dataframe["ema200"])
                & (
                    dataframe["pullback_ema_short"]
                    | dataframe["bb_breakout_short"]
                    | dataframe["rsi_exhaustion"]
                )
                & (dataframe["volume"] > 0)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "trending_short")

    @staticmethod
    def _populate_ranging_entries(dataframe: DataFrame) -> None:
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["ranging_long_setup"])
                & (dataframe["close"] > dataframe["ema200"])
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "ranging_long")

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["ranging_short_setup"])
                & (dataframe["close"] < dataframe["ema200"])
                & (dataframe["volume"] > 0)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "ranging_short")

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["close"] < dataframe["ema200"] * 0.90)
                & (dataframe["volume"] > 0)
            ),
            ["exit_long", "exit_tag"],
        ] = (1, "ranging_breakdown")
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        last = dataframe.iloc[-1]
        entry_mode = trade.enter_tag or "trending_long"

        if "ranging" in entry_mode:
            trade_duration = current_time - trade.open_date_utc
            if trade_duration > timedelta(hours=48):
                return "ranging_time_stop"

            if "_long" in entry_mode:
                bb_upper = last.get("bb_upper", 0)
                if bb_upper > 0 and current_rate >= bb_upper:
                    return "ranging_target_upper"
                bb_middle = last.get("bb_middle", 0)
                if bb_middle > 0 and current_rate >= bb_middle:
                    return "ranging_target_middle"
                if last.get("rsi", 50) > 65:
                    return "ranging_overbought"
            else:
                bb_lower = last.get("bb_lower", 0)
                if bb_lower > 0 and current_rate <= bb_lower:
                    return "ranging_target_lower"
                bb_middle = last.get("bb_middle", 0)
                if bb_middle > 0 and current_rate <= bb_middle:
                    return "ranging_target_middle"
                if last.get("rsi", 50) < 35:
                    return "ranging_oversold"

        if "trending" in entry_mode:
            trade_duration = current_time - trade.open_date_utc
            if trade_duration > timedelta(days=5) and current_profit < 0:
                return "trending_time_stop"

        return None

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str,
        side: str,
        **kwargs,
    ) -> bool:
        if self.risk_manager.is_circuit_breaker_active(current_time):
            cooldown = self.risk_manager.get_cooldown_remaining(current_time)
            if cooldown:
                logger.warning("Circuit breaker active. Cooldown: %s", cooldown)
            return False
        open_trades = Trade.get_trades_proxy(is_open=True)
        if len(open_trades) >= self.risk_max_positions:
            return False
        return True

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        exit_reason: str,
        current_time: datetime,
        **kwargs,
    ) -> bool:
        self.risk_manager.record_trade_result(
            trade.calc_profit_ratio(rate), current_time
        )
        return True

    def custom_entry_price(
        self,
        pair: str,
        trade: Trade | None,
        current_time: datetime,
        proposed_rate: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if side == "short":
            return proposed_rate * 0.9997
        return proposed_rate * 1.0003

    def custom_exit_price(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        proposed_rate: float,
        current_profit: float,
        exit_tag: str | None,
        **kwargs,
    ) -> float:
        if getattr(trade, "is_short", False):
            return proposed_rate * 1.0003
        return proposed_rate * 0.9997

    def bot_start(self, **kwargs):
        self.regime_detector.reset()
        self.risk_manager.reset()
