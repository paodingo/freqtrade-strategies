"""RegimeAware V10.2 reliable short-core candidate."""

import os

from RegimeAwareV66 import RegimeAwareV66
from RegimeAwareV66AlphaRisk import RegimeAwareV66AlphaRisk


class RegimeAwareV102ReliableShortCoreAlpha(RegimeAwareV66AlphaRisk):
    """Keep the profitable V6.6 trend-short core and remove weak side arms."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v102")
    scale_in_tag_prefix = "v102"

    initial_stake_amount = 2500
    add_stake_amount = 0
    max_total_stake_amount = 2500
    max_entry_position_adjustment = 0
    old_position_stake_floor = initial_stake_amount * 0.8

    @property
    def protections(self):
        return [
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 192,
                "trade_limit": 1,
                "stop_duration_candles": 288,
                "only_per_pair": False,
            },
        ]

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        cls = self.__class__
        cls._ensure_entry_tag(result)
        core_short = cls._tag_contains(result, "trending_short")

        cls._block_entries(result, result.get("enter_long", 0) == 1)
        cls._block_entries(result, cls._tag_contains(result, "ranging"))
        cls._block_entries(result, (result.get("enter_short", 0) == 1) & ~core_short)

        result.loc[
            (result.get("enter_short", 0) == 1) & core_short,
            "enter_tag",
        ] = "v102_trending_short_core"
        return result

    def custom_exit(
        self,
        pair,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        if getattr(trade, "is_short", False) and "v102_trending_short_core" in (trade.enter_tag or ""):
            return RegimeAwareV66.custom_exit(
                self,
                pair,
                trade,
                current_time,
                current_rate,
                current_profit,
                **kwargs,
            )

        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    @staticmethod
    def _ensure_entry_tag(dataframe) -> None:
        if "enter_tag" not in dataframe:
            dataframe["enter_tag"] = ""
        else:
            dataframe["enter_tag"] = dataframe["enter_tag"].astype("object").fillna("")

    @staticmethod
    def _tag_contains(dataframe, value: str):
        return dataframe.get("enter_tag", "").astype(str).str.contains(value, regex=False)

    @staticmethod
    def _block_entries(dataframe, mask) -> None:
        dataframe.loc[mask, "enter_long"] = 0
        dataframe.loc[mask, "enter_short"] = 0

