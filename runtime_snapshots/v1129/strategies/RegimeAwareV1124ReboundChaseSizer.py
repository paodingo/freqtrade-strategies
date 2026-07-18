"""RegimeAware V11.24: reduce stake in rebound-chase windows without blocking."""

import os

from RegimeAwareV1122AdaCapitulationHalfSizer import RegimeAwareV1122AdaCapitulationHalfSizer


class RegimeAwareV1124ReboundChaseSizer(RegimeAwareV1122AdaCapitulationHalfSizer):
    """Keep V11.22 entries, but cut stake when rebound pressure raises tail risk."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1124")
    scale_in_tag_prefix = "v1124"

    ada_rebound_micro_stake_amount = 500
    ada_rebound_chase_1h_min = 0.0
    ld_core_rebound_half_stake_amount = 1250
    ld_core_rebound_4h_min = 0.02
    ld_core_rebound_pairs = {"LTC/USDT:USDT", "DOGE/USDT:USDT"}

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1124_rebound_sizer_gate"] = "pass"
        pair = metadata.get("pair", "")
        short_entry = result.get("enter_short", 0) == 1
        enter_tag = result.get("enter_tag", "")

        if pair == "ADA/USDT:USDT":
            ada_rebound = (
                short_entry
                & (enter_tag == "v1122_ada_capitulation_half_short")
                & self._ada_rebound_chase_mask(result)
            )
            if ada_rebound.any():
                result.loc[ada_rebound, "enter_tag"] = "v1124_ada_rebound_micro_short"
                result.loc[ada_rebound, "v1124_rebound_sizer_gate"] = "micro_stake_ada_rebound"

        if pair in self.ld_core_rebound_pairs:
            ld_rebound = (
                short_entry
                & (enter_tag == "v102_trending_short_core")
                & self._ld_core_rebound_mask(result)
            )
            if ld_rebound.any():
                result.loc[ld_rebound, "enter_tag"] = "v1124_ld_core_rebound_half_short"
                result.loc[ld_rebound, "v1124_rebound_sizer_gate"] = "half_stake_ld_core_rebound"

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
        if entry_tag == "v1124_ada_rebound_micro_short":
            return self._capped_stake(self.ada_rebound_micro_stake_amount, proposed_stake, min_stake, max_stake)
        if entry_tag == "v1124_ld_core_rebound_half_short":
            return self._capped_stake(self.ld_core_rebound_half_stake_amount, proposed_stake, min_stake, max_stake)
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

    def _capped_stake(self, target_stake: float, proposed_stake: float, min_stake: float | None, max_stake: float) -> float:
        _, available_balance = self._stake_balances(0.0, max_stake)
        stake = min(
            float(target_stake),
            float(proposed_stake),
            float(max_stake),
            available_balance,
        )
        if min_stake is not None and stake < float(min_stake):
            return 0.0
        return max(0.0, stake)

    @classmethod
    def _ada_rebound_chase_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        one_hour_return = (close / close.shift(4)) - 1
        return (one_hour_return >= cls.ada_rebound_chase_1h_min).fillna(False)

    @classmethod
    def _ld_core_rebound_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        four_hour_return = (close / close.shift(16)) - 1
        return (four_hour_return >= cls.ld_core_rebound_4h_min).fillna(False)

