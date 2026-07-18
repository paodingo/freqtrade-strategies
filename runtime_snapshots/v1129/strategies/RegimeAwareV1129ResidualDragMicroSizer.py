"""RegimeAware V11.29: micro-size residual negative contribution clusters."""

import os

from RegimeAwareV1127DualTrapMicroSizer import RegimeAwareV1127DualTrapMicroSizer


class RegimeAwareV1129ResidualDragMicroSizer(RegimeAwareV1127DualTrapMicroSizer):
    """Keep V11.27's winners, but cut exposure on verified residual drag clusters."""

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1129")
    scale_in_tag_prefix = "v1129"

    residual_micro_stake_amount = 500
    residual_probe_stake_amount = 250

    residual_micro_tags = {
        "v1129_ada_capitulation_micro_short",
        "v1129_eth_core_watch_micro_short",
        "v1129_ltc_rebound_micro_short",
    }
    residual_probe_tags = {
        "v1129_sol_exhaustion_probe_short",
        "v1129_ltc_exhaustion_probe_short",
        "v1129_btc_exhaustion_probe_short",
        "v1129_xrp_exhaustion_probe_short",
        "v1129_ltc_panic_probe_short",
        "v1129_doge_rebound_probe_short",
    }

    def populate_entry_trend(self, dataframe, metadata: dict):
        result = super().populate_entry_trend(dataframe, metadata)
        if result.empty:
            return result

        result["v1129_residual_drag_gate"] = "pass"
        pair = metadata.get("pair", "")
        short_entry = result.get("enter_short", 0) == 1

        self._retag_short(
            result,
            short_entry,
            pair,
            "ADA/USDT:USDT",
            "v1122_ada_capitulation_half_short",
            "v1129_ada_capitulation_micro_short",
            "micro_stake_ada_capitulation_residual_drag",
        )
        self._retag_short(
            result,
            short_entry,
            pair,
            "ETH/USDT:USDT",
            "v102_trending_short_core",
            "v1129_eth_core_watch_micro_short",
            "micro_stake_eth_core_watch_drag",
        )
        self._retag_short(
            result,
            short_entry,
            pair,
            "LTC/USDT:USDT",
            "v1124_ld_core_rebound_half_short",
            "v1129_ltc_rebound_micro_short",
            "micro_stake_ltc_rebound_residual_drag",
        )

        for target_pair, source_tag, target_tag, gate in (
            (
                "SOL/USDT:USDT",
                "v1115_exhausted_selloff_small_short",
                "v1129_sol_exhaustion_probe_short",
                "probe_stake_sol_exhaustion_drag",
            ),
            (
                "LTC/USDT:USDT",
                "v1115_exhausted_selloff_small_short",
                "v1129_ltc_exhaustion_probe_short",
                "probe_stake_ltc_exhaustion_drag",
            ),
            (
                "BTC/USDT:USDT",
                "v1115_exhausted_selloff_small_short",
                "v1129_btc_exhaustion_probe_short",
                "probe_stake_btc_exhaustion_drag",
            ),
            (
                "XRP/USDT:USDT",
                "v1115_exhausted_selloff_small_short",
                "v1129_xrp_exhaustion_probe_short",
                "probe_stake_xrp_exhaustion_drag",
            ),
            (
                "LTC/USDT:USDT",
                "v1127_ltc_panic_chase_micro_short",
                "v1129_ltc_panic_probe_short",
                "probe_stake_ltc_panic_drag",
            ),
            (
                "DOGE/USDT:USDT",
                "v1127_doge_rebound_trap_micro_short",
                "v1129_doge_rebound_probe_short",
                "probe_stake_doge_rebound_drag",
            ),
        ):
            self._retag_short(result, short_entry, pair, target_pair, source_tag, target_tag, gate)

        return result

    @classmethod
    def _retag_short(cls, dataframe, short_entry, pair, target_pair, source_tag, target_tag, gate):
        if pair != target_pair:
            return
        mask = short_entry & (dataframe.get("enter_tag", "") == source_tag)
        if mask.any():
            dataframe.loc[mask, "enter_tag"] = target_tag
            dataframe.loc[mask, "v1129_residual_drag_gate"] = gate

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
        if side == "short" and entry_tag in self.residual_micro_tags:
            return self._capped_stake(self.residual_micro_stake_amount, proposed_stake, min_stake, max_stake)
        if side == "short" and entry_tag in self.residual_probe_tags:
            return self._capped_stake(self.residual_probe_stake_amount, proposed_stake, min_stake, max_stake)
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

