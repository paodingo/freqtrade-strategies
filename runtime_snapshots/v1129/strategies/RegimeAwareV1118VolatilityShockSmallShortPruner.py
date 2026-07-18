"""RegimeAware V11.18: prune small shorts only during volatility shocks."""

import os

from RegimeAwareV1116SelectiveAltRecoverySizer import RegimeAwareV1116SelectiveAltRecoverySizer


class RegimeAwareV1118VolatilityShockSmallShortPruner(RegimeAwareV1116SelectiveAltRecoverySizer):
    """Keep V11.16, but block residual small shorts only in acute selloff shocks."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1118")
    scale_in_tag_prefix = "v1118"

    residual_small_short_allowed_pairs = {"ADA/USDT:USDT"}
    residual_small_short_tag = "v1115_exhausted_selloff_small_short"
    shock_abs_1h_mean_24h_min = 0.0055
    shock_return_7d_max = -0.03

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1118_volatility_shock_gate"] = "pass"
        pair = metadata.get("pair", "")
        if pair in self.residual_small_short_allowed_pairs:
            return result

        residual_small_short = (
            (result.get("enter_short", 0) == 1)
            & (result.get("enter_tag", "") == self.residual_small_short_tag)
        )
        shock_prune = residual_small_short & self._volatility_shock_mask(result)
        if shock_prune.any():
            self._block_entries(result, shock_prune)
            result.loc[shock_prune, "enter_tag"] = "v1118_volatility_shock_small_short_block"
            result.loc[shock_prune, "v1118_volatility_shock_gate"] = "blocked_shock_small_short"
        return result

    @classmethod
    def _volatility_shock_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        one_hour_return = (close / close.shift(4)) …7218 tokens truncated…  near_lower_edge = (
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

