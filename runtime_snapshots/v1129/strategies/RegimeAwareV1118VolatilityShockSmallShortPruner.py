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
        one_hour_return = (close / close.shift(4)) - 1
        abs_1h_mean_24h = one_hour_return.abs().rolling(24, min_periods=24).mean()
        seven_day_return = (close / close.shift(96 * 7)) - 1
        return (
            (abs_1h_mean_24h >= cls.shock_abs_1h_mean_24h_min)
            & (seven_day_return <= cls.shock_return_7d_max)
        ).fillna(False)
