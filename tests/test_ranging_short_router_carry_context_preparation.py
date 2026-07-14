from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_director  # noqa: E402
from research_director_common import load_document, proposal_fingerprint  # noqa: E402


PROPOSAL_ID = "ranging-short-router-carry-context-review-v1"

class RouterCarryContextContractTest(unittest.TestCase):
    def test_contract_freezes_one_runtime_observable_context(self):
        spec = importlib.util.find_spec("ranging_short_router_context")
        self.assertIsNotNone(spec, "router context contract module must exist")
        router_context = importlib.import_module("ranging_short_router_context")
        contract = router_context.build_context_contract(ROOT)

        self.assertEqual(
            contract["context_id"],
            "ranging_state_without_current_range_signal",
        )
        self.assertEqual(contract["context_count"], 1)
        self.assertEqual(
            contract["output_regime"],
            {"column": "regime_4h", "operator": "eq", "value": "ranging"},
        )
        self.assertEqual(
            contract["current_raw_ranging_signal"],
            {
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
            },
        )
        self.assertEqual(
            contract["context_expression"],
            {
                "all": [
                    contract["output_regime"],
                    {"not": contract["current_raw_ranging_signal"]},
                ]
            },
        )
        self.assertEqual(
            contract["evaluation_preconditions"],
            ["bb_width_mean_4h > 0", "atr_mean_4h > 0"],
        )
        self.assertFalse(contract["threshold_search_authorized"])
        self.assertFalse(contract["time_slice_used_as_regime_label"])


class RouterCarryProposalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.constitution = load_document(
            ROOT / "research/governance/research-constitution.yaml"
        )

    def test_director_emits_exactly_one_medium_risk_router_context(self):
        router_context = importlib.import_module("ranging_short_router_context")
        contract = router_context.build_context_contract(ROOT)
        run = research_director.generate(
            self.state,
            self.constitution,
            "compile approved ranging-short router carry context",
            {
                "max_campaigns": 1,
                "max_wall_clock_minutes": 30,
                "max_validation_accesses": 0,
            },
            "medium",
            10,
        )

        matches = [
            item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID
        ]
        self.assertEqual(len(matches), 1)
        proposal = matches[0]
        self.assertEqual(proposal["risk_class"], "medium")
        self.assertEqual(proposal["proposed_method"]["router_context"], contract)
        self.assertEqual(
            proposal_fingerprint(proposal), proposal["semantic_fingerprint"]
        )
        self.assertEqual(proposal["estimated_experiments"], 3)
        self.assertEqual(
            proposal["proposed_method"]["execution"],
            "no_candidate_no_backtest_no_validation_no_holdout",
        )
        allowed = "\n".join(proposal["allowed_changes"])
        forbidden = "\n".join(proposal["forbidden_changes"])
        self.assertNotIn("strategies/", allowed)
        self.assertNotIn("research/candidates/", allowed)
        for term in ("strategy", "candidate", "threshold", "backtest", "validation", "holdout", "hyperopt"):
            self.assertIn(term, forbidden.lower())


if __name__ == "__main__":
    unittest.main()
