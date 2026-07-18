"""RegimeAware V11.27: micro-size two narrow DOGE/LTC short traps."""

import os

from RegimeAwareV1124ReboundChaseSizer import RegimeAwareV1124ReboundChaseSizer


class RegimeAwareV1127DualTrapMicroSizer(RegimeAwareV1124ReboundChaseSizer):
    """Keep V11.24 entries, but cut stake in two specific core-short traps."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1127")
    scale_in_tag_prefix = "v1127"

    dual_trap_micro_stake_amount = 500

    doge_rebound_rsi_max = 52.0
    doge_rebound_range48_max = 0.30
    doge_rebound_one_hour_return_min = 0.001
    doge_rebound_four_hour_return_min = 0.01
    doge_rebound_di_ratio_min = 4.0
    doge_rebound_volume_ratio_max = 0.60

    ltc_panic_rsi_max = 42.0
    ltc_panic_range48_min = 0.30
    ltc_panic_range48_max = 0.42
    ltc_panic_one_hour_return_min = -0.002
    ltc_panic_four_hour_return_min = -0.008
    ltc_panic_di_ratio_min = 1.8
    ltc_panic_volume_ratio_min = 1.5

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1127_dual_trap_gate"] = "pass"
        pair = metadata.get("pair", "")
        if pair not in {"DOGE/USDT:USDT", "LTC/USDT:USDT"}:
            return result

        short_entry = result.get("enter_short", 0) == 1
        enter_tag = result.get("enter_tag", "")
        core_short = short_entry & (enter_tag == "v102_trending_short_core")

        if pair == "DOGE/USDT:USDT":
            doge_trap = core_short & self._doge_rebound_trap_mask(result)
            if doge_trap.any():
                result.loc[doge_trap, "enter_tag"] = "v1127_doge_rebound_trap_micro_short"
                result.loc[doge_trap, "v1127_dual_trap_gate"] = "micro_stake_doge_rebound_trap"

        if pair == "LTC/USDT:USDT":
            ltc_trap = core_short & self._ltc_panic_chase_mask(result)
            if ltc_trap.any():
                result.loc[ltc_trap, "enter_tag"] = "v1127_ltc_panic_chase_micro_short"
                result.loc[ltc_trap, "v1127_dual_trap_gate"] = "micro_stake_ltc_panic_chase"

        return result

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if side == "short" and entry_tag in {
            "v1127_doge_rebound_trap_micro_short",
            "v1127_ltc_panic_chase_micro_short",
        }:
            return self._capped_stake(self.dual_trap_micro_stake_amount, proposed_stake, min_stake, max_stake)
        return super().custom_stake_amount(
            pair,
            current_time,
            current_rate,
            proposed_stake,
            min_stake,
            max_stake,
            leverage,
            entry_tag,
            side,
            **kwargs,
        )

    @classmethod
    def _doge_rebound_trap_mask(cls, dataframe):
        one_hour_return, four_hour_return = cls._return_features(dataframe)
        return (
            (cls._series(dataframe, "rsi", 50) <= cls.doge_rebound_rsi_max)
            & (cls._series(dataframe, "range_position_48h", 0.5) <= cls.doge_rebound_range48_max)
            & (one_hour_return >= cls.doge_rebound_one_hour_return_min)
            & (four_hour_return >= cls.doge_rebound_four_hour_return_min)
            & (cls._di_ratio(dataframe) >= cls.doge_rebound_di_ratio_min)
            & (cls._volume_ratio(dataframe) <= cls.doge_rebound_volume_ratio_max)
        ).fillna(False)

    @classmethod
    def _ltc_panic_chase_mask(cls, dataframe):
        one_hour_return, four_hour_return = cls._return_features(dataframe)
        range_position = cls._series(dataframe, "range_position_48h", 0.5)
        return (
            (cls._series(dataframe, "rsi", 50) <= cls.ltc_panic_rsi_max)
            & (range_position >= cls.ltc_panic_range48_min)
            & (range_position <= cls.ltc_panic_range48_max)
            & (one_hour_return >= cls.ltc_panic_one_hour_return_min)
            & (four_hour_return >= cls.ltc_panic_four_hour_return_min)
            & (cls._di_ratio(dataframe) >= cls.ltc_panic_di_ratio_min)
            & (cls._volume_ratio(dataframe) >= cls.ltc_panic_volume_ratio_min)
        ).fillna(False)

    @classmethod
    def _return_features(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        one_hour_return = (close / close.shift(4)) - 1
        four_hour_return = (close / close.shift(16)) - 1
        return one_hour_return, four_hour_return

    @classmethod
    def _di_ratio(cls, dataframe):
        plus_di = cls._series(dataframe, "plus_di_4h", 0)
        minus_di = cls._series(dataframe, "minus_di_4h", 0)
        return minus_di / plus_di.where(plus_di > 0, 1)

    @classmethod
    def _volume_ratio(cls, dataframe):
        volume = cls._series(dataframe, "volume", 0)
        volume_mean = cls._series(dataframe, "volume_mean", 0)
        return volume / volume_mean.where(volume_mean > 0, 1)

