"""Single-variable Candidate for the frozen ranging-short router-carry context."""

from __future__ import annotations

import sys
from pathlib import Path


STRATEGY_ROOT = Path(__file__).resolve().parents[4] / "strategies"
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from RegimeAwareV6 import RegimeAwareV6  # noqa: E402


class RegimeAware_RouterCarryContext_C1(RegimeAwareV6):
    """Gate ranging-short only in the frozen router carry context."""

    _router_context_columns = {
        "regime_4h",
        "adx_4h",
        "bb_width_4h",
        "bb_width_mean_4h",
        "atr_4h",
        "atr_mean_4h",
    }

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe = super().populate_entry_trend(dataframe, metadata)

        missing = sorted(self._router_context_columns.difference(dataframe.columns))
        if missing:
            raise RuntimeError(
                "router_context_required_columns_missing:" + ",".join(missing)
            )

        evaluation_preconditions = (
            (dataframe["bb_width_mean_4h"] > 0)
            & (dataframe["atr_mean_4h"] > 0)
        )
        raw_ranging_signal = (
            (dataframe["adx_4h"] < 20)
            & (
                (dataframe["bb_width_4h"] <= dataframe["bb_width_mean_4h"])
                | (dataframe["atr_4h"] <= dataframe["atr_mean_4h"])
            )
        )
        router_context = (
            evaluation_preconditions
            & (dataframe["regime_4h"] == "ranging")
            & ~raw_ranging_signal
        )
        ranging_short_pre_gate = (
            (dataframe["enter_short"].fillna(0).astype(int) == 1)
            & (dataframe["enter_tag"] == "ranging_short")
        )
        gated_rows = router_context & ranging_short_pre_gate

        dataframe["research_router_context_raw_ranging_signal"] = (
            raw_ranging_signal.astype("int8")
        )
        dataframe["research_router_context"] = router_context.astype("int8")
        dataframe["research_ranging_short_entry_pre_gate"] = (
            ranging_short_pre_gate.astype("int8")
        )
        dataframe["research_router_context_pre_gate_intersection"] = (
            gated_rows.astype("int8")
        )
        dataframe.loc[gated_rows, "enter_short"] = 0

        return dataframe
