"""RegimeAware V6.6 - selective range-edge trader."""
from datetime import timedelta

import pandas as pd
from freqtrade.persistence import Trade

from RegimeAwareV65 import RegimeAwareV65
from regime_detector import RegimeDetector


class RegimeAwareV66(RegimeAwareV65):
    """V6.6 trades ranging markets only near well-defined box edges."""

    minimal_roi = {
        "0": 0.006,
        "30": 0.004,
        "90": 0.0015,
    }
    stoploss = -0.02

    initial_stake_amount = 2500
    add_stake_amount = 1000
    max_total_stake_amount = 4500
    max_entry_position_adjustment = 1
    min_scale_in_profit = 0.006
    min_scale_in_minutes = 30
    old_position_stake_floor = initial_stake_amount * 0.8

    max_scale_in_account_loss_pct = 0.025
    max_scale_in_atr_pct = 0.035
    scale_in_tag_prefix = "v66"

    lower_edge_24h = 0.28
    upper_edge_24h = 0.72
    lower_edge_48h = 0.35
    upper_edge_48h = 0.65
    min_range_width_24h = 0.018
    min_range_width_48h = 0.025
    max_range_adx_4h = 42
    max_range_bb_width_expansion = 1.15
    midbox_take_profit = 0.0015
    ranging_timeout_hours = 4

    def populate_indicators(self, dataframe, metadata: dict):
        dataframe = super().populate_indicators(dataframe, metadata)
        return self._add_range_box_columns(dataframe)

    @classmethod
    def _add_range_box_columns(cls, dataframe):
        for hours, window in [(24, 96), (48, 192)]:
            high_col = f"range_high_{hours}h"
            low_col = f"range_low_{hours}h"
            pos_col = f"range_position_{hours}h"
            width_col = f"range_width_{hours}h"

            dataframe[high_col] = dataframe["high"].rolling(window, min_periods=window // 2).max()
            dataframe[low_col] = dataframe["low"].rolling(window, min_periods=window // 2).min()
            width = dataframe[high_col] - dataframe[low_col]
            safe_width = width.mask(width <= 0)
            dataframe[pos_col] = ((dataframe["close"] - dataframe[low_col]) / safe_width).clip(0, 1)
            dataframe[width_col] = (width / dataframe["close"]).where(dataframe["close"] > 0)

        return dataframe

    @classmethod
    def _populate_ranging_entries(cls, dataframe) -> None:
        cls._ensure_range_columns(dataframe)

        enough_range = (
            (dataframe["range_width_24h"] >= cls.min_range_width_24h)
            & (dataframe["range_width_48h"] >= cls.min_range_width_48h)
        )
        range_not_expanding = (
            (dataframe["adx_4h"] < cls.max_range_adx_4h)
            & (dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * cls.max_range_bb_width_expansion)
        )
        volume_ok = dataframe["volume"] > dataframe["volume_mean"] * 0.7

        near_lower_edge = (
            (dataframe["range_position_24h"] <= cls.lower_edge_24h)
            & (dataframe["range_position_48h"] <= cls.lower_edge_48h)
        )
        near_upper_edge = (
            (dataframe["range_position_24h"] >= cls.upper_edge_24h)
            & (dataframe["range_position_48h"] >= cls.upper_edge_48h)
        )

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & near_lower_edge
                & enough_range
                & range_not_expanding
                & (dataframe["bb_percent"] < 0.18)
                & (dataframe["rsi"] < 43)
                & volume_ok
                & (dataframe["close"] > dataframe["ema200"] * 0.90)
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "v66_ranging_long_edge")

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & near_upper_edge
                & enough_range
                & range_not_expanding
                & (dataframe["bb_percent"] > 0.82)
                & (dataframe["rsi"] > 57)
                & volume_ok
                & (dataframe["close"] < dataframe["ema200"] * 1.10)
                & (dataframe["volume"] > 0)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "v66_ranging_short_edge")

    @staticmethod
    def _ensure_range_columns(dataframe) -> None:
        defaults = {
            "adx_4h": 100,
            "bb_width_4h": 1.0,
            "bb_width_mean_4h": 0.0,
            "range_position_24h": 0.5,
            "range_position_48h": 0.5,
            "range_width_24h": 0.0,
            "range_width_48h": 0.0,
        }
        for column, value in defaults.items():
            if column not in dataframe:
                dataframe[column] = value

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        reverse_exit = self._reverse_signal_exit_reason(pair, trade)
        if reverse_exit:
            return reverse_exit

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        last = dataframe.iloc[-1]
        entry_mode = trade.enter_tag or "trending_long"
        duration = current_time - trade.open_date_utc

        if "trending" in entry_mode and last.get("regime_4h") == RegimeDetector.RANGING:
            if current_profit < 0 or duration > timedelta(hours=6):
                return "v66_trend_invalidated_by_range"

        if "ranging" in entry_mode:
            if self._returned_to_midbox(trade, last, current_profit):
                return "v66_ranging_midbox_take_profit"
            if duration > timedelta(hours=self.ranging_timeout_hours):
                return "v66_ranging_time_stop"

        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    def _returned_to_midbox(self, trade: Trade, last: pd.Series, current_profit: float) -> bool:
        if current_profit < self.midbox_take_profit:
            return False

        position = self._finite_float(last.get("range_position_24h"))
        if position is None:
            return False

        if getattr(trade, "is_short", False):
            return position <= 0.55
        return position >= 0.45

    @staticmethod
    def _finite_float(value) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(number):
            return None
        return number
