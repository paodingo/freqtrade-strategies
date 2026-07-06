import os

from pandas import DataFrame

from RegimeAwareV1129ResidualDragMicroSizer import RegimeAwareV1129ResidualDragMicroSizer


class RegimeAwareV1129RangingShortShadow(RegimeAwareV1129ResidualDragMicroSizer):
    """
    Dry-run shadow lane for V11.29 ranging-short observation.

    This strategy preserves the V11.29 parent behavior and adds a separate,
    pair-limited ranging-short candidate path only when alpha telemetry says
    shorts are not blocked.
    """

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1129_shadow")
    scale_in_tag_prefix = "v1129_shadow"

    shadow_entry_tag = "v1129_shadow_ranging_short"
    shadow_stake_amount = 250
    shadow_allowed_pairs = {
        "ETH/USDT:USDT",
        "AVAX/USDT:USDT",
        "LINK/USDT:USDT",
        "BCH/USDT:USDT",
        "XRP/USDT:USDT",
    }

    shadow_upper_edge_24h = 0.72
    shadow_upper_edge_48h = 0.65
    shadow_min_range_width_24h = 0.018
    shadow_min_range_width_48h = 0.025
    shadow_max_adx_4h = 42
    shadow_bb_width_expansion_limit = 1.15
    shadow_min_bb_percent = 0.82
    shadow_min_rsi = 57
    shadow_min_volume_ratio = 0.7
    shadow_max_close_to_ema200 = 1.10

    def _shadow_ranging_short_mask(self, dataframe: DataFrame):
        required_columns = [
            "range_position_24h",
            "range_position_48h",
            "range_width_24h",
            "range_width_48h",
            "adx_4h",
            "bb_width_4h",
            "bb_width_mean_4h",
            "bb_percent",
            "rsi",
            "volume",
            "volume_mean",
            "close",
            "ema200",
        ]
        missing = [column for column in required_columns if column not in dataframe.columns]
        if missing:
            return None, missing

        return (
            (dataframe["range_position_24h"] >= self.shadow_upper_edge_24h)
            & (dataframe["range_position_48h"] >= self.shadow_upper_edge_48h)
            & (dataframe["range_width_24h"] >= self.shadow_min_range_width_24h)
            & (dataframe["range_width_48h"] >= self.shadow_min_range_width_48h)
            & (dataframe["adx_4h"] < self.shadow_max_adx_4h)
            & (dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * self.shadow_bb_width_expansion_limit)
            & (dataframe["bb_percent"] > self.shadow_min_bb_percent)
            & (dataframe["rsi"] > self.shadow_min_rsi)
            & (dataframe["volume"] > dataframe["volume_mean"] * self.shadow_min_volume_ratio)
            & (dataframe["close"] < dataframe["ema200"] * self.shadow_max_close_to_ema200)
            & (dataframe["volume"] > 0)
        ), []

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        pair = metadata.get("pair", "")

        dataframe["v1129_shadow_ranging_short_gate"] = "not_candidate"

        if pair not in self.shadow_allowed_pairs:
            dataframe["v1129_shadow_ranging_short_gate"] = "blocked_pair_not_allowlisted"
            return dataframe

        if "alpha_filter_block_short" not in dataframe.columns:
            dataframe["v1129_shadow_ranging_short_gate"] = "blocked_missing_alpha_filter"
            return dataframe

        ranging_mask, missing_columns = self._shadow_ranging_short_mask(dataframe)
        if ranging_mask is None:
            dataframe["v1129_shadow_ranging_short_gate"] = (
                "blocked_missing_columns:" + ",".join(missing_columns)
            )
            return dataframe

        alpha_allows_short = ~dataframe["alpha_filter_block_short"].fillna(True).astype(bool)
        no_existing_short = dataframe.get("enter_short", 0) != 1
        shadow_mask = ranging_mask & alpha_allows_short & no_existing_short

        alpha_blocked_mask = ranging_mask & ~alpha_allows_short
        dataframe.loc[alpha_blocked_mask, "v1129_shadow_ranging_short_gate"] = "blocked_alpha_short"
        dataframe.loc[shadow_mask, "enter_short"] = 1
        dataframe.loc[shadow_mask, "enter_tag"] = self.shadow_entry_tag
        dataframe.loc[shadow_mask, "v1129_shadow_ranging_short_gate"] = "enabled_shadow_ranging_short"

        return dataframe

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
        if side == "short" and entry_tag == self.shadow_entry_tag:
            return self._capped_stake(self.shadow_stake_amount, proposed_stake, min_stake, max_stake)

        return super().custom_stake_amount(
            pair=pair,
            current_time=current_time,
            current_rate=current_rate,
            proposed_stake=proposed_stake,
            min_stake=min_stake,
            max_stake=max_stake,
            leverage=leverage,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )
