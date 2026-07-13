from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compile_research_campaign import compile_campaign
from research_director_common import load_document, proposal_fingerprint, sha256_file


PROPOSAL_PATH = ROOT / "research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json"


class RangingShortBranchDecisionReviewCompilationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = load_document(PROPOSAL_PATH)
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        cls.campaign, _, _ = compile_campaign(ROOT, cls.proposal, cls.state, cls.constitution)
        cls.plan = cls.campaign["ranging_short_branch_decision_review_plan"]

    def test_proposal_fingerprint_and_compilation_authority_are_exact(self):
        expected = "e5b01ecdfc922b06a20e8e0c1eb901fd363563da23d246819cfa8e268247c0c3"
        self.assertEqual(proposal_fingerprint(self.proposal), expected)
        self.assertEqual(self.proposal["semantic_fingerprint"], expected)
        self.assertEqual(self.campaign["proposal_fingerprint"], expected)
        self.assertFalse(self.campaign["execution_authorized"])
        self.assertEqual(self.campaign["budget"]["max_backtest_calls"], 0)
        self.assertEqual(self.campaign["budget"]["max_validation_accesses"], 0)
        self.assertEqual(self.campaign["budget"]["max_holdout_accesses"], 0)

    def test_metric_semantics_are_candidate_minus_baseline_and_consistent(self):
        audit = self.plan["metric_semantics_audit"]
        self.assertEqual(audit["status"], "passed")
        self.assertTrue(audit["all_arithmetic_consistent"])
        self.assertEqual(audit["pairs"]["btc"]["calculation_direction"], "candidate_minus_baseline")
        eth = audit["pairs"]["eth"]["metrics"]["max_drawdown"]
        self.assertAlmostEqual(eth["baseline"], 340.65008476)
        self.assertAlmostEqual(eth["candidate"], 291.71629049)
        self.assertAlmostEqual(eth["delta"], -48.93379427)
        self.assertEqual(eth["unit"], "USDT")
        self.assertEqual(eth["kind"], "absolute_not_percentage_point")

    def test_balanced_gate_is_not_misreported_as_development_eligible(self):
        gate = self.plan["development_gate_audit"]
        self.assertEqual(gate["policy_id"], "balanced-research-gate-v1")
        self.assertEqual(gate["coverage_gate"]["status"], "partially_satisfied_not_formally_established")
        self.assertEqual(gate["behavior_materiality"]["status"], "satisfied")
        self.assertEqual(gate["no_material_degradation"]["status"], "not_formally_established")
        self.assertEqual(gate["material_improvement"]["status"], "not_met_on_available_metrics")
        self.assertEqual(gate["directional_coverage"]["status"], "satisfied")
        self.assertFalse(gate["development_eligible"])
        self.assertEqual(self.plan["evidence_scope"]["eth_development"], "descriptive_cross_pair_only")

    def test_temporal_recommendation_and_option_budgets_are_frozen(self):
        self.assertEqual(self.plan["recommendation"], "temporal_ablation_review_worth_authorizing")
        temporal = self.plan["options"]["B_temporal"]["budget"]
        self.assertEqual(temporal["pre_frozen_slices"], 4)
        self.assertEqual(temporal["backtest_calls"], 16)
        self.assertEqual(temporal["validation_accesses"], 0)
        self.assertEqual(temporal["holdout_accesses"], 0)
        validation = self.plan["options"]["A_validation"]["budget"]
        self.assertEqual(validation["backtest_calls"], 2)
        self.assertEqual(validation["validation_accesses"], 1)

    def test_candidate_and_formal_branch_are_frozen(self):
        frozen = self.plan["frozen_candidate"]
        self.assertTrue(frozen["reused"])
        self.assertFalse(frozen["new_candidate_required"])
        self.assertEqual(frozen["source_sha256"], "e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0")
        self.assertEqual(sha256_file(ROOT / frozen["path"]), frozen["source_sha256"])
        source = (ROOT / "strategies/regime_aware_base.py").read_text(encoding="utf-8")
        self.assertIn('"ranging_short"', source)
        self.assertFalse(self.plan["execution_boundary"]["campaign_executed"])
        self.assertFalse(self.plan["execution_boundary"]["backtest_run"])


if __name__ == "__main__":
    unittest.main()
