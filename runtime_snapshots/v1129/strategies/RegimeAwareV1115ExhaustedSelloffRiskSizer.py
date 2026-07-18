"""RegimeAware V11.15: size down exhausted selloff shorts."""

import os

from RegimeAwareV1113MicroReboundTrapGuard import RegimeAwareV1113MicroReboundTrapGuard


class RegimeAwareV1115ExhaustedSelloffRiskSizer(RegimeAwareV1113MicroReboundTrapGuard):
    """Keep V11.13 entries, but cut stake when shorts chase a mature selloff."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1115")
    scale_in_tag_prefix = "v1115"

    exhausted_selloff_small_stake_amount = 625
    exhausted_selloff_4h_drop_max = -0.01
    exhausted_selloff_min_range_position_48h = 0.05

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1115_selloff_gate"] = "pass"
        short_entry = result.get("enter_short", 0) == 1
        small_stake = short_entry & self._exhausted_selloff_small_stake_mask(result)
        if small_stake.any():
            result.loc[small_stake, "enter_tag"] = "v1115_exhausted_selloff_small_short"
            result.loc[small_stake, "v1115_selloff_gate"] = "small_stake"
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
        if entry_tag == "v1115_exhausted_selloff_small_short":
            _, available_balance = self._stake_balances(0.0, max_stake)
            stake = min(
                self.exhausted_selloff_small_stake_amount,
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
    def _exhausted_selloff_small_stake_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        four_hour_ret = (close / close.shift(16)) - 1
        range_position_48h = cls._series(dataframe, "range_position_48h", 0)
        return (
            (four_hour_ret <= cls.exhausted_selloff_4h_drop_max)
            & (range_position_48h >= cls.exhausted_selloff_min_range_position_48h)
        ).fillna(False)

