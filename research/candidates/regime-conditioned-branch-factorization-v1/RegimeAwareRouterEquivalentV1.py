"""Isolated semantic-equivalence Candidate for shared regime routing only."""

from __future__ import annotations

import sys
from pathlib import Path


STRATEGY_ROOT = Path(__file__).resolve().parents[3] / "strategies"
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from RegimeAwareV6 import RegimeAwareV6  # noqa: E402


class SharedRegimeRouter:
    """Move only the existing regime-dispatch interface into an isolated object."""

    @staticmethod
    def populate_entry_signals(strategy: RegimeAwareV6, dataframe):
        strategy._populate_trending_entries(dataframe)
        if strategy.enable_ranging_entries:
            strategy._populate_ranging_entries(dataframe)


class RegimeAwareRouterEquivalentV1(RegimeAwareV6):
    """Keep every condition and signal group unchanged behind the new router interface."""

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0

        SharedRegimeRouter.populate_entry_signals(self, dataframe)

        return dataframe
