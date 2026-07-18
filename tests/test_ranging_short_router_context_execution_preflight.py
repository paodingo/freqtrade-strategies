from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
STRATEGIES = ROOT / "strategies"
for path in (SCRIPTS, STRATEGIES):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from RegimeAwareV6 import RegimeAwareV6  # noqa: E402
from research_director_common import load_document, sha256_file  # noqa: E402
import run_ranging_short_router_context_preflight as preflight  # noqa: E402


def load_candidate():
    path = ROOT / preflight.CANDIDATE_SOURCE
    spec = importlib.util.spec_from_file_location("test_router_context_candidate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RegimeAware_RouterCarryContext_C1


class RouterContextCandidateTests(unittest.TestCase):
    def test_frozen_candidate_identity_and_single_variable_manifest(self):
        manifest = load_document(ROOT / preflight.CANDIDATE_MANIFEST)
        self.assertEqual(
            sha256_file(ROOT / preflight.CANDIDATE_SOURCE),
            preflight.CANDIDATE_SHA256,
        )
        self.assertEqual(
            sha256_file(ROOT / preflight.CANDIDATE_MANIFEST),
            preflight.CANDIDATE_MANIFEST_SHA256,
        )
        self.assertEqual(manifest["candidate_count"], 1)
        self.assertEqual(manifest["conditions_changed"], 0)
        self.assertEqual(manifest["thresholds_changed"], 0)
        self.assertEqual(manifest["signal_groups_changed"], 0)
        self.assertEqual(
            manifest["single_structural_variable"],
            "ranging_short_entry_router_carry_context_gate",
        )

    def test_candidate_gates_only_context_pre_gate_intersection(self):
        candidate_class = load_candidate()
        frame = pd.DataFrame(
            {
                "enter_short": [1, 1, 1, 0],
                "enter_tag": [
                    "ranging_short",
                    "ranging_short",
                    "trending_short",
                    "ranging_short",
                ],
                "regime_4h": ["ranging", "ranging", "ranging", "ranging"],
                "adx_4h": [21.0, 19.0, 21.0, 21.0],
                "bb_width_4h": [1.2, 0.8, 1.2, 1.2],
                "bb_width_mean_4h": [1.0, 1.0, 1.0, 1.0],
                "atr_4h": [1.2, 0.8, 1.2, 1.2],
                "atr_mean_4h": [1.0, 1.0, 1.0, 1.0],
            }
        )
        strategy = candidate_class({})
        with patch.object(RegimeAwareV6, "populate_entry_trend", return_value=frame):
            result = strategy.populate_entry_trend(frame, {})
        self.assertEqual(result["enter_short"].tolist(), [0, 1, 1, 0])
        self.assertEqual(
            result["research_router_context_pre_gate_intersection"].tolist(),
            [1, 0, 0, 0],
        )
        self.assertEqual(result["enter_tag"].tolist(), frame["enter_tag"].tolist())

    def test_candidate_fails_closed_when_context_column_is_missing(self):
        candidate_class = load_candidate()
        frame = pd.DataFrame(
            {
                "enter_short": [1],
                "enter_tag": ["ranging_short"],
                "regime_4h": ["ranging"],
            }
        )
        strategy = candidate_class({})
        with patch.object(RegimeAwareV6, "populate_entry_trend", return_value=frame):
            with self.assertRaisesRegex(
                RuntimeError, "router_context_required_columns_missing"
            ):
                strategy.populate_entry_trend(frame, {})


class RouterContextCoverageStopTests(unittest.TestCase):
    def test_authority_is_bound_to_conditional_human_approval(self):
        checks = preflight.validate_authority(ROOT)
        self.assertTrue(all(checks.values()))

    def test_frozen_development_coverage_blocks_backtests(self):
        result = load_document(ROOT / preflight.OUTPUT_PATH)
        authorization = load_document(ROOT / preflight.AUTHORIZATION_PATH)
        stopped = load_document(ROOT / preflight.STOP_PATH)
        self.assertEqual(result["totals"]["evaluation_rows"], 5000)
        self.assertEqual(result["totals"]["context_true"], 1256)
        self.assertEqual(result["totals"]["context_false"], 3744)
        self.assertEqual(result["totals"]["ranging_short_pre_gate"], 12)
        self.assertEqual(result["totals"]["context_pre_gate_intersection"], 0)
        self.assertFalse(result["gate"]["passed"])
        self.assertEqual(
            result["gate"]["failure_code"],
            "router_context_coverage_insufficient",
        )
        self.assertEqual(result["backtest_calls"], 0)
        self.assertEqual(result["validation_accesses"], 0)
        self.assertEqual(result["holdout_accesses"], 0)
        self.assertFalse(authorization["execution_authorized"])
        self.assertEqual(authorization["max_backtest_calls"], 0)
        self.assertEqual(authorization["status"], "stopped_pre_backtest")
        self.assertEqual(
            sha256_file(ROOT / preflight.OUTPUT_PATH),
            stopped["coverage_preflight"]["sha256"],
        )
        self.assertEqual(
            sha256_file(ROOT / preflight.AUTHORIZATION_PATH),
            stopped["execution_authorization"]["sha256"],
        )

    def test_preflight_is_deterministic(self):
        expected = load_document(ROOT / preflight.OUTPUT_PATH)
        actual = preflight.run_preflight(ROOT)
        self.assertEqual(actual, expected)

    def test_no_sealed_dataset_path_is_referenced(self):
        source = (ROOT / "scripts/run_ranging_short_router_context_preflight.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("futures-validation-", source)
        self.assertNotIn("research/data/holdout", source)


if __name__ == "__main__":
    unittest.main()
