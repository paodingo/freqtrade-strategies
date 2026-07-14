#!/usr/bin/env python3
"""Freeze the approved ranging-short router context as machine-readable data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from protected_manifest_hash import canonical_text_sha256
from research_director_common import fingerprint


CONTEXT_ID = "ranging_state_without_current_range_signal"


def build_context_contract(repo: Path) -> dict[str, Any]:
    """Bind the approved context to the current detector and router sources."""
    detector = repo / "strategies/regime_detector.py"
    base = repo / "strategies/regime_aware_base.py"
    detector_text = detector.read_text(encoding="utf-8")
    base_text = base.read_text(encoding="utf-8")
    required = (
        "adx < self.adx_range_threshold",
        "(bb_width / bb_width_mean) > 1.0",
        "atr_val > atr_mean",
        'dataframe["regime_4h"] == RegimeDetector.RANGING',
    )
    combined = detector_text + "\n" + base_text
    missing = [snippet for snippet in required if snippet not in combined]
    if missing:
        raise ValueError(f"router_context_source_contract_drift: {missing}")

    raw_ranging_signal = {
        "all": [
            {"column": "adx_4h", "operator": "lt", "value": 20},
            {
                "any": [
                    {
                        "left": "bb_width_4h",
                        "operator": "lte",
                        "right": "bb_width_mean_4h",
                    },
                    {
                        "left": "atr_4h",
                        "operator": "lte",
                        "right": "atr_mean_4h",
                    },
                ]
            },
        ]
    }
    output_regime = {
        "column": "regime_4h",
        "operator": "eq",
        "value": "ranging",
    }
    return {
        "schema_version": "ranging-short-router-context-contract-v1",
        "context_id": CONTEXT_ID,
        "context_count": 1,
        "output_regime": output_regime,
        "current_raw_ranging_signal": raw_ranging_signal,
        "context_expression": {
            "all": [output_regime, {"not": raw_ranging_signal}],
        },
        "evaluation_preconditions": [
            "bb_width_mean_4h > 0",
            "atr_mean_4h > 0",
        ],
        "source_files": [
            "strategies/regime_detector.py",
            "strategies/regime_aware_base.py",
        ],
        "source_sha256": {
            "strategies/regime_detector.py": canonical_text_sha256(detector),
            "strategies/regime_aware_base.py": canonical_text_sha256(base),
        },
        "threshold_search_authorized": False,
        "time_slice_used_as_regime_label": False,
    }


def context_contract_fingerprint(contract: dict[str, Any]) -> str:
    """Return the canonical fingerprint used by Proposal and Campaign specs."""
    return fingerprint(contract)
