"""RegimeAware V11.22: half-size ADA shorts after local capitulation."""

import os

from RegimeAwareV1118VolatilityShockSmallShortPruner import RegimeAwareV1118VolatilityShockSmallShortPruner


class RegimeAwareV1122AdaCapitulationHalfSizer(RegimeAwareV1118VolatilityShockSmallShortPruner):
    """Keep V11.18, but reduce only ADA shorts after sharp local selloffs."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1122")
    scale_in_tag_prefix = "v1122"

    ada_capitulation_half_stake_amount = 1250
    ada_capitulation_range48_max = 0.10
    ada_capitulation_4h_drop_max = -0.02
    ada_capitulation_tags = {"v102_trending_short_core", "v1116_alt_down_day_medium_short"}

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1122_ada_capitulation_gate"] = "pass"
        if metadata.get("pair", "") != "ADA/USDT:USDT":
            return result

        short_entry = result.get("enter_short", 0) == 1
        enter_tag = result.get("enter_tag", "")
        capitulation = (
            short_entry
            & enter_tag.isin(self.ada_capitulation_tags)
            & self._ada_capitulation_half_stake_mask(result)
        )
        if capitulation.any():
            result.loc[capitulation, "enter_tag"] = "v1122_ada_capitulation_half_short"
            result.loc[capitulation, "v1122_ada_capitulation_gate"] = "half_stake"
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
        if entry_tag == "v1122_ada_capitulation_half_short":
            _, available_balance = self._stake_balances(0.0, max_stake)
            stake = min(
                self.ada_capitulation_half_stake_amount,
                float(proposed_stake),
                float(max_stake),
                available_balance,
            )
            if min_stake is not None and stake < float(min_stake):
                return 0.0
            return max(0.0, stake)
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
    def _ada_capitulation_half_stake_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        four_hour_return = (close / close.shift(16)) - 1
        range_position_48h = cls._series(dataframe, "range_position_48h", 0.5)
        return (
            (range_position_48h <= cls.ada_capitulation_range48_max)
            & (four_hour_return <= cls.ada_capitulation_4h_drop_max)
        ).fillna(False)

