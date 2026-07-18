"""RegimeAware V11.16: promote selected alt exhausted-selloff shorts."""

import os

from RegimeAwareV1115ExhaustedSelloffRiskSizer import RegimeAwareV1115ExhaustedSelloffRiskSizer


class RegimeAwareV1116SelectiveAltRecoverySizer(RegimeAwareV1115ExhaustedSelloffRiskSizer):
    """Keep V11.15 quality gates, but size up ADA/SOL weak-day recovery shorts."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1116")
    scale_in_tag_prefix = "v1116"

    alt_recovery_medium_stake_amount = 1875
    alt_recovery_pairs = {"ADA/USDT:USDT", "SOL/USDT:USDT"}
    alt_recovery_day_ret_max = 0.0

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1116_alt_recovery_gate"] = "pass"
        pair = metadata.get("pair", "")
        if pair not in self.alt_recovery_pairs:
            return result

        short_entry = result.get("enter_short", 0) == 1
        v1115_small_short = result.get("enter_tag", "") == "v1115_exhausted_selloff_small_short"
        medium_stake = short_entry & v1115_small_short & self._alt_down_day_recovery_mask(result)
        if medium_stake.any():
            result.loc[medium_stake, "enter_tag"] = "v1116_alt_down_day_medium_short"
            result.loc[medium_stake, "v1116_alt_recovery_gate"] = "medium_stake"
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
        if entry_tag == "v1116_alt_down_day_medium_short":
            _, available_balance = self._stake_balances(0.0, max_stake)
            stake = min(
                self.alt_recovery_medium_stake_amount,
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
    def _alt_down_day_recovery_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        day_ret = (close / close.shift(96)) - 1
        return (day_ret <= cls.alt_recovery_day_ret_max).fillna(False)

