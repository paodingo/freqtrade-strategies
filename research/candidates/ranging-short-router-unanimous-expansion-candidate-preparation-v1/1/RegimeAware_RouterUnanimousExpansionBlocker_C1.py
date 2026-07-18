"""Single-variable Candidate blocking unanimous 4h router-indicator expansion."""

from __future__ import annotations

import sys
from pathlib import Path


STRATEGY_ROOT = Path(__file__).resolve().parents[4] / "strategies"
if str(STRATEGY_ROOT) not in sys.path:
    sys.path.insert(0, str(STRATEGY_ROOT))

from RegimeAwareV6 import RegimeAwareV6  # noqa: E402


class RegimeAware_RouterUnanimousExpansionBlocker_C1(RegimeAwareV6):
    """Block ranging-short when ADX, BB-width and ATR all rise versus prior 4h."""

    _direction_columns = ("adx_4h", "bb_width_4h", "atr_4h")

    @staticmethod
    def _direction(current, previous) -> str:
        if current != current or previous != previous:
            return "unknown"
        if current > previous:
            return "U"
        if current < previous:
            return "D"
        return "F"

    def populate_entry_trend(self, dataframe, metadata: dict):
        dataframe = super().populate_entry_trend(dataframe, metadata)

        required = {"date_4h", *self._direction_columns}
        missing = sorted(required.difference(dataframe.columns))
        if missing:
            raise RuntimeError(
                "router_indicator_direction_columns_missing:" + ",".join(missing)
            )

        informative = (
            dataframe[["date_4h", *self._direction_columns]]
            .dropna(subset=["date_4h"])
            .drop_duplicates("date_4h", keep="first")
            .sort_values("date_4h")
            .copy()
        )
        direction_columns = []
        for column in self._direction_columns:
            direction_column = f"research_{column}_direction"
            informative[direction_column] = [
                self._direction(current, previous)
                for current, previous in zip(
                    informative[column], informative[column].shift(1)
                )
            ]
            direction_columns.append(direction_column)
        informative["research_router_indicator_direction_topology"] = (
            informative[direction_columns].agg("-".join, axis=1)
        )
        topology_by_date = informative.set_index("date_4h")[
            "research_router_indicator_direction_topology"
        ]
        dataframe["research_router_indicator_direction_topology"] = dataframe[
            "date_4h"
        ].map(topology_by_date)

        pre_gate = (
            (dataframe["enter_short"].fillna(0).astype(int) == 1)
            & (dataframe["enter_tag"] == "ranging_short")
        )
        blocked = pre_gate & (
            dataframe["research_router_indicator_direction_topology"] == "U-U-U"
        )
        dataframe["research_ranging_short_entry_pre_gate"] = pre_gate.astype("int8")
        dataframe["research_unanimous_expansion_blocked"] = blocked.astype("int8")
        dataframe.loc[blocked, "enter_short"] = 0
        return dataframe
