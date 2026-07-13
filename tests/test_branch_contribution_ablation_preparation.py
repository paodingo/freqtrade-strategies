import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from compile_research_campaign import compile_campaign  # noqa: E402
from research_director_common import load_document, proposal_fingerprint, sha256_file  # noqa: E402


PROPOSAL_FP = "8f7211ad73d4a3528da6fd92e0b7e958e2aebf6159fc2773bc8be8740f9e55cc"


class BranchContributionAblationPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = load_document(ROOT / "research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json")
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        cls.campaign, cls.metadata, cls.brief = compile_campaign(ROOT, cls.proposal, cls.state, cls.constitution)
        cls.plan = cls.campaign["branch_contribution_ablation_plan"]

    def test_proposal_and_compilation_only_approval_match(self):
        approval = load_document(ROOT / "research/governance/approvals/branch-contribution-ablation-v1-compilation-approval.json")
        self.assertEqual(proposal_fingerprint(self.proposal), PROPOSAL_FP)
        self.assertEqual(approval["proposal_fingerprint"], PROPOSAL_FP)
        self.assertEqual(approval["approval_status"], "approved_for_compilation_only")
        self.assertFalse(approval["execution_authorized"])

    def test_real_structure_yields_five_signal_groups_and_shared_router(self):
        units = {item["unit_id"]: item for item in self.plan["ablation_units"]}
        self.assertEqual(
            set(units),
            {
                "trending_long_entry",
                "trending_short_entry",
                "ranging_long_entry",
                "ranging_short_entry",
                "ranging_breakdown_exit_long",
                "shared_regime_router",
            },
        )
        self.assertFalse(units["shared_regime_router"]["eligible_as_single_candidate_unit"])
        self.assertEqual(self.plan["structure_source"]["condition_count"], 29)
        self.assertEqual(self.plan["structure_source"]["signal_group_count"], 5)

    def test_single_reversible_ablation_contract_is_frozen(self):
        contract = self.plan["single_structural_variable_contract"]
        mechanism = self.plan["reversible_ablation_mechanism"]
        self.assertEqual(contract["candidate_count"], 1)
        self.assertEqual(contract["selected_unit_count"], 1)
        self.assertFalse(mechanism["large_code_deletion_allowed"])
        self.assertIn("original_branch_code", mechanism["preserve"])

    def test_development_budget_and_temporal_boundary_are_explicit(self):
        design = self.plan["evaluation_design"]
        budget = self.plan["budget"]
        self.assertEqual(design["pairs"], ["BTC/USDT:USDT", "ETH/USDT:USDT"])
        self.assertEqual(design["planned_backtest_invocations"], 8)
        self.assertEqual(design["temporal_slices_in_initial_campaign"], 0)
        self.assertEqual(len(self.campaign["experiment_queue"]), 3)
        self.assertEqual(budget["max_candidates"], 1)
        self.assertEqual(budget["max_backtest_calls"], 8)
        self.assertEqual(budget["max_validation_accesses"], 0)
        self.assertEqual(budget["max_holdout_accesses"], 0)

    def test_contribution_metrics_and_deterministic_decisions_are_complete(self):
        self.assertIn("actual_trade_count_delta", self.plan["contribution_metrics"])
        self.assertIn("rolling_window_delta", self.plan["contribution_metrics"])
        self.assertIn("normalized_trade_hash", self.plan["contribution_metrics"])
        self.assertEqual(
            set(self.plan["decision_classifications"]),
            {
                "branch_positive_contributor",
                "branch_negative_contributor",
                "branch_mixed_regime_dependent",
                "branch_redundant",
                "branch_contribution_inconclusive",
                "ablation_execution_invalid",
            },
        )

    def test_router_baseline_and_closed_threshold_scope_are_preserved(self):
        baseline = self.plan["verified_baseline"]
        self.assertEqual(baseline["router_result_status"], "router_extraction_semantic_equivalence_verified")
        self.assertEqual(baseline["btc_trade_count"], 27)
        self.assertEqual(baseline["eth_trade_count"], 27)
        self.assertIn("threshold_or_risk_or_execution_change", self.plan["single_structural_variable_contract"]["forbidden_combinations"])

    def test_compilation_does_not_authorize_or_execute(self):
        self.assertFalse(self.campaign["execution_authorized"])
        self.assertEqual(self.campaign["current_authority"], "compile_and_review_only")
        self.assertFalse(self.plan["execution_boundary"]["candidate_created"])
        self.assertFalse(self.plan["execution_boundary"]["backtest_run"])
        self.assertIn("No Candidate, Backtest or ablation is created", self.brief)

    def test_protected_hashes_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509")
        self.assertEqual(sha256_file(ROOT / "strategies/regime_aware_base.py"), "8feaebff14b5e8c537ec310b44b2b1d448db20be1388e3aca51da15b306275f9")
        self.assertEqual(sha256_file(ROOT / "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"), "bee68e27b345a93a1fe8481275e365829c986f700d2719fdd10ffd907e1dffa1")

if __name__ == "__main__":
    unittest.main()
