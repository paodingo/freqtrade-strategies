"""RegimeAware V6.5 - aggressive 15m ranging scalper."""
from datetime import timedelta

from freqtrade.persistence import Trade

from RegimeAwareV64 import RegimeAwareV64
from regime_detector import RegimeDetector


class RegimeAwareV65(RegimeAwareV64):
    """V6.5 adds faster mean-reversion entries for ranging BTC markets."""

    minimal_roi = {
        "0": 0.008,
        "30": 0.005,
        "120": 0.002,
    }
    stoploss = -0.025

    enable_ranging_entries = True
    initial_stake_amount = 3000
    add_stake_amount = 1500
    max_total_stake_amount = 6500
    min_scale_in_profit = 0.004
    min_scale_in_minutes = 15
    old_position_stake_floor = initial_stake_amount * 0.8

    max_scale_in_account_loss_pct = 0.035
    max_scale_in_atr_pct = 0.05
    scale_in_tag_prefix = "v65"

    @staticmethod
    def _populate_ranging_entries(dataframe) -> None:
        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["bb_percent"] < 0.25)
                & (dataframe["rsi"] < 45)
                & (dataframe["volume"] > dataframe["volume_mean"] * 0.6)
                & (dataframe["close"] > dataframe["ema200"] * 0.88)
                & (dataframe["volume"] > 0)
            ),
            ["enter_long", "enter_tag"],
        ] = (1, "ranging_long")

        dataframe.loc[
            (
                (dataframe["regime_4h"] == RegimeDetector.RANGING)
                & (dataframe["bb_percent"] > 0.75)
                & (dataframe["rsi"] > 55)
                & (dataframe["volume"] > dataframe["volume_mean"] * 0.6)
                & (dataframe["close"] < dataframe["ema200"] * 1.12)
                & (dataframe["volume"] > 0)
            ),
            ["enter_short", "enter_tag"],
        ] = (1, "ranging_short")

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

        entry_mode = trade.enter_tag or "trending_long"
        if "ranging" in entry_mode and current_time - trade.open_date_utc > timedelta(hours=6):
            return "v65_ranging_time_stop"
        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    def _reverse_signal_exit_reason(self, pair: str, trade: Trade) -> str | None:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None

        last = dataframe.iloc[-1]
        if getattr(trade, "is_short", False) and bool(last.get("enter_long", 0) == 1):
            return "v65_reverse_long_signal_exit"
        if not getattr(trade, "is_short", False) and bool(last.get("enter_short", 0) == 1):
            return "v65_reverse_short_signal_exit"
        return None

