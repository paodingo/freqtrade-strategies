import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document, proposal_fingerprint, sha256_file  # noqa: E402


class StrategyFamilyReassessmentPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = ROOT / "research/director/strategy-family-reassessment-v1"
        cls.director_run = load_document(base / "proposals/director-run.json")
        cls.proposal = load_document(base / "proposals/strategy-family-reassessment-v1.json")
        cls.route = load_document(base / "approval-route.json")
        compiled = ROOT / "research/director/compiled/strategy-family-reassessment-v1"
        cls.campaign = load_document(compiled / "campaign.yaml")
        cls.metadata = load_document(compiled / "compilation-metadata.json")

    def test_director_generated_one_medium_risk_proposal(self):
        self.assertEqual(self.director_run["recommendation"], "research_recommended")
        self.assertEqual(len(self.director_run["proposals"]), 1)
        self.assertEqual(self.proposal["proposal_id"], "strategy-family-reassessment-v1")
        self.assertEqual(self.proposal["risk_class"], "medium")
        self.assertEqual(proposal_fingerprint(self.proposal), self.proposal["semantic_fingerprint"])

    def test_risk_router_requires_human_approval(self):
        self.assertEqual(self.route["decision"], "human_approval_required")
        self.assertFalse(self.route["approval_granted"])
        self.assertFalse(self.route["execution_authorized_under_constitution"])
        risk = next(item for item in self.route["rule_decisions"] if item["rule"] == "risk_evidence")
        self.assertEqual(risk["details"]["medium_hits"], ["new_strategy_branch"])

    def test_compiler_output_is_dry_run_and_fingerprint_matches(self):
        self.assertEqual(self.campaign["compile_mode"], "dry_run")
        self.assertEqual(self.campaign["mode"], "dry_run")
        self.assertFalse(self.campaign["execution_authorized"])
        self.assertFalse(self.campaign["approval_granted"])
        self.assertEqual(self.campaign["campaign_fingerprint"], self.metadata["campaign_fingerprint"])
        self.assertFalse(self.metadata["campaign_executed"])
        self.assertFalse(self.metadata["candidate_created"])

    def test_compiled_budget_and_protected_data_boundaries(self):
        self.assertEqual(self.campaign["budget"]["max_experiments"], 3)
        self.assertEqual(self.campaign["budget"]["max_wall_clock_minutes"], 60)
        self.assertEqual(self.campaign["budget"]["max_validation_accesses"], 0)
        self.assertFalse(self.campaign["autonomy"]["access_sealed_holdout"])
        self.assertIn("research/data/holdout/**", self.campaign["scope"]["blocked_paths"])
        self.assertIn("strategies/**", self.campaign["scope"]["blocked_paths"])

    def test_no_execution_or_mutation_method_is_frozen(self):
        self.assertEqual(self.proposal["proposed_method"]["execution"], "no_backtest_no_candidate_no_strategy_change")
        self.assertIn("no strategy or Candidate diff test", self.proposal["required_tests"])
        self.assertEqual(self.proposal["validation_requirement"], "none")
        self.assertEqual(self.proposal["holdout_requirement"], "none")
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509")

    def test_all_evidence_is_existing_and_read_only(self):
        for item in self.proposal["supporting_evidence"]:
            self.assertTrue((ROOT / item["path"]).is_file(), item["path"])
        for dataset in self.proposal["required_datasets"]:
            self.assertEqual(dataset["access"], "existing_analysis_only")


if __name__ == "__main__":
    unittest.main()
