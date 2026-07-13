"""Isolated Candidate that gates only the final ranging-short entry contribution."""

from __future__ import annotations

import sys
from pathlib import Path


ROUTER_REFERENCE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "regime-conditioned-branch-factorization-v1"
)
if str(ROUTER_REFERENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(ROUTER_REFERENCE_ROOT))

from RegimeAwareRouterEquivalentV1 import RegimeAwareRouterEquivalentV1  # noqa: E402


class RegimeAware_Ablation_RangingShort_C1(RegimeAwareRouterEquivalentV1):
    """Preserve the routed signal, then gate only ranging_short from enter_short."""

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe = super().populate_entry_trend(dataframe, metadata)

        ranging_short_pre_gate = (
            (dataframe["enter_short"].fillna(0).astype(int) == 1)
            & (dataframe["enter_tag"] == "ranging_short")
        )
        dataframe["research_ranging_short_entry_pre_gate"] = (
            ranging_short_pre_gate.astype("int8")
        )
        dataframe.loc[ranging_short_pre_gate, "enter_short"] = 0

        return dataframe
