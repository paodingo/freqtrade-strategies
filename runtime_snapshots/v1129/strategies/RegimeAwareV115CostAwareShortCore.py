"""RegimeAware V11.5: cost-aware short core quality gate."""

import os

import pandas as pd

from RegimeAwareV111HighAttackFilteredShortCore import RegimeAwareV111HighAttackFilteredShortCore


class RegimeAwareV115CostAwareShortCore(RegimeAwareV111HighAttackFilteredShortCore):
    """Keep V11.1 density, but block rebound and low-edge high-cost shorts."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v115")
    scale_in_tag_prefix = "v115"

    rebound_rsi_min = 56.0
    low_edge_bb_percent_min = 0.38
    low_edge_atr_pct_max = 0.004
    weak_pair_stake_amount = 750
    weak_pairs = {
        "ETH/USDT:USDT",
        "XRP/USDT:USDT",
    }

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v115_quality_gate"] = "pass"
        short_entry = result.get("enter_short", 0) == 1

        rebound_risk = short_entry & self._rebound_risk_mask(result)
        if rebound_risk.any():
            self._block_entries(result, rebound_risk)
            result.loc[rebound_risk, "enter_tag"] = "v115_rebound_risk_block"
            result.loc[rebound_risk, "v115_quality_gate"] = "rebound_risk"

        short_entry = result.get("enter_short", 0) == 1
        low_edge_cost = short_entry & self._low_edge_cost_mask(result)
        if low_edge_cost.any():
            self._block_entries(result, low_edge_cost)
            result.loc[low_edge_cost, "enter_tag"] = "v115_low_edge_cost_block"
            result.loc[low_edge_cost, "v115_quality_gate"] = "low_edge_cost"

        return result

    @classmethod
    def _stake_for_pair(cls, pair: str) -> float:
        if pair in cls.weak_pairs:
            return cls.weak_pair_stake_amount
        return super()._stake_for_pair(pair)

    @classmethod
    def _rebound_risk_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        ema21 = cls._series(dataframe, "ema21", float("inf"))
        rsi = cls._series(dataframe, "rsi", 0)
        return (
            (close >= ema21)
            & (rsi >= cls.rebound_rsi_min)
        ).fillna(False)

    @classmethod
    def _low_edge_cost_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0).where(cls._series(dataframe, "close", 0) > 0)
        atr_pct = cls._series(dataframe, "atr", 0) / close
        bb_percent = cls._series(dataframe, "bb_percent", 0.5)
        rsi = cls._series(dataframe, "rsi", 50)
        return (
            (bb_percent >= cls.low_edge_bb_percent_min)
            & (atr_pct <= cls.low_edge_atr_pct_max)
            & (rsi >= 47)
        ).fillna(False)

    @staticmethod
    def _series(dataframe, column: str, default):
        if column in dataframe:
            return dataframe[column]
        return pd.Series(default, index=dataframe.index)

