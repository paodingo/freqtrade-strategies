"""RegimeAware V6.7 alpha-quality gate variant."""

from RegimeAwareV661AlphaRisk import RegimeAwareV661AlphaRisk
from alpha_risk_filter import LONG_HOSTILE_FLAGS


class RegimeAwareV67AlphaRisk(RegimeAwareV661AlphaRisk):
    """V6.6.1 plus a cleaner-alpha requirement for inherited trend shorts."""

    minimal_roi = {
        "0": 0.0055,
        "30": 0.0035,
        "90": 0.0015,
    }
    stoploss = -0.018
    max_scale_in_account_loss_pct = 0.022
    scale_in_tag_prefix = "v67"

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe = super().populate_entry_trend(dataframe, metadata)

        short_mask = (
            (dataframe.get("enter_short", 0) == 1)
            & (dataframe.get("enter_tag", "") == "trending_short")
            & dataframe.get("alpha_risk_level").notna()
        )
        clean_alpha = (
            (dataframe["alpha_risk_level"] == "good")
            & (dataframe["alpha_risk_score"].fillna(99) <= 1)
            & ~dataframe["alpha_risk_flags"].fillna("").map(self._has_long_hostile_alpha)
        )
        dataframe.loc[short_mask & ~clean_alpha, "enter_short"] = 0
        return dataframe

    @staticmethod
    def _has_long_hostile_alpha(raw_flags: str) -> bool:
        flags = {flag for flag in str(raw_flags or "").split(",") if flag}
        return bool(flags & LONG_HOSTILE_FLAGS)
