"""Development-only Candidate adding one causal structure-reversal long branch."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
ROUTER_REFERENCE_ROOT = (
    REPO_ROOT / "research/candidates/regime-conditioned-branch-factorization-v1"
)
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for module_root in (ROUTER_REFERENCE_ROOT, SCRIPTS_ROOT):
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))

from RegimeAwareRouterEquivalentV1 import RegimeAwareRouterEquivalentV1  # noqa: E402
from analyze_chan_structure_readiness import POLICY, structure_sequences  # noqa: E402


class RegimeAwareChanStructureLongV1(RegimeAwareRouterEquivalentV1):
    """Preserve the baseline and add one confirmed higher-low reversal signal group."""

    structure_entry_tag_trending = "chan_structure_long_trending"
    structure_entry_tag_ranging = "chan_structure_long_ranging"

    @staticmethod
    def causal_structure_long_mask(dataframe: pd.DataFrame) -> pd.Series:
        sequences = structure_sequences(dataframe, POLICY)
        mask = pd.Series(False, index=dataframe.index, dtype=bool)
        for event in sequences["long_unique_signals"]:
            mask.iloc[event["signal_confirmation_index"]] = True
        return mask

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe["chan_structure_long_signal"] = self.causal_structure_long_mask(dataframe).astype("int8")
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)

        structure_signal = dataframe["chan_structure_long_signal"].fillna(0).astype(int) == 1
        recognized_regime = dataframe["regime_4h"].isin(("trending", "ranging"))
        no_existing_long = dataframe["enter_long"].fillna(0).astype(int) != 1
        novel_signal = structure_signal & recognized_regime & no_existing_long & (dataframe["volume"] > 0)

        dataframe["research_chan_structure_long_pre_gate"] = structure_signal.astype("int8")
        dataframe["research_chan_structure_long_novel"] = novel_signal.astype("int8")
        dataframe.loc[
            novel_signal & (dataframe["regime_4h"] == "trending"),
            ["enter_long", "enter_tag"],
        ] = (1, self.structure_entry_tag_trending)
        dataframe.loc[
            novel_signal & (dataframe["regime_4h"] == "ranging"),
            ["enter_long", "enter_tag"],
        ] = (1, self.structure_entry_tag_ranging)

        return dataframe
