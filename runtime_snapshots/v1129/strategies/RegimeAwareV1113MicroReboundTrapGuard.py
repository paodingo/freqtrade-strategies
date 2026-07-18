"""RegimeAware V11.13: block short entries after micro rebound traps."""

import os

from RegimeAwareV115CostAwareShortCore import RegimeAwareV115CostAwareShortCore


class RegimeAwareV1113MicroReboundTrapGuard(RegimeAwareV115CostAwareShortCore):
    """Keep V11.5, but avoid shorting after a small intrahour rebound."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1113")
    scale_in_tag_prefix = "v1113"

    micro_rebound_min = 0.003
    micro_rebound_bb_percent_min = 0.20

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1113_micro_rebound_gate"] = "pass"
        short_entry = result.get("enter_short", 0) == 1
        trap = short_entry & self._micro_rebound_trap_mask(result)
        if trap.any():
            self._block_entries(result, trap)
            result.loc[trap, "enter_tag"] = "v1113_micro_rebound_trap_block"
            result.loc[trap, "v1113_micro_rebound_gate"] = "micro_rebound_trap"
        return result

    @classmethod
    def _micro_rebound_trap_mask(cls, dataframe):
        close = cls._series(dataframe, "close", 0)
        bb_percent = cls._series(dataframe, "bb_percent", 0.5)
        one_hour_rebound = (close / close.shift(4)) - 1
        return (
            (one_hour_rebound >= cls.micro_rebound_min)
            & (bb_percent >= cls.micro_rebound_bb_percent_min)
        ).fillna(False)

