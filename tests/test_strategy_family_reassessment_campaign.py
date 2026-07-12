import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from protected_manifest_hash import validate_protected_manifests  # noqa: E402
from research_director_common import load_document, sha256_file  # noqa: E402


PROPOSAL_FINGERPRINT = "32c5b3c956bbb33ccbc9e8d3d509add58183dc7faa51524458562d5136b3e8f6"
CAMPAIGN_FINGERPRINT = "1b3900b566df7a07313a9e9832e30c1e9a16efeade246c486b3a052b38a2b8a1"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
ALLOWED_DECISIONS = {
    "retain_family_for_further_research",
    "retain_execution_baseline_only",
    "restructure_family_worth_studying",
    "retire_family_from_active_research",
    "insufficient_evidence_for_family_decision",
}


class StrategyFamilyReassessmentCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approval = load_document(
            ROOT / "research/governance/approvals/strategy-family-reassessment-v1-execution-approval.json"
        )
        compiled = ROOT / "research/director/compiled/strategy-family-reassessment-v1"
        cls.authorization = load_document(compiled / "execution-authorization.json")
        cls.result = load_document(compiled / "execution/campaign-execution.json")
        analysis = ROOT / "research/analysis/strategy-family-reassessment"
        cls.matrix = load_document(analysis / "family-evidence-matrix.json")
        cls.packet = load_document(analysis / "human-review-packet.json")
        cls.report = load_document(
            ROOT / "reports/audits/strategy-family-reassessment/strategy-family-reassessment-final-report.json"
        )

    def test_human_approval_matches_frozen_fingerprints_and_scope(self):
        self.assertEqual(self.approval["proposal_fingerprint"], PROPOSAL_FINGERPRINT)
        self.assertEqual(self.approval["compiled_campaign_fingerprint"], CAMPAIGN_FINGERPRINT)
        self.assertEqual(self.authorization["approved_proposal_fingerprint"], PROPOSAL_FINGERPRINT)
        self.assertEqual(self.authorization["approved_compiled_fingerprint"], CAMPAIGN_FINGERPRINT)
        self.assertTrue(self.approval["execution_authorized"])
        self.assertEqual(self.approval["execution_scope"], "read_only_audit_only")
        self.assertEqual(self.approval["portfolio_budget"], {"max_campaigns": 1, "max_wall_clock_minutes": 60})

    def test_campaign_used_only_read_only_authority(self):
        self.assertEqual(self.result["status"], "completed")
        self.assertFalse(self.result["strategy_modified"])
        self.assertFalse(self.result["candidate_created"])
        self.assertFalse(self.result["backtest_run"])
        self.assertFalse(self.result["hyperopt_run"])
        self.assertEqual(self.result["validation_accesses"], 0)
        self.assertEqual(self.result["holdout_accesses"], 0)
        self.assertFalse(self.result["next_campaign_compiled"])
        self.assertFalse(self.result["next_campaign_executed"])
        self.assertTrue(all(self.report["authority"]["checks"].values()))

    def test_evidence_matrix_covers_every_required_decision_dimension(self):
        dimensions = {item["dimension"] for item in self.matrix["dimensions"]}
        self.assertEqual(
            dimensions,
            {
                "cross_time",
                "cross_pair",
                "long_short",
                "regime_branches",
                "entry_exit_contribution",
                "risk_drawdown",
                "complexity",
                "closed_research",
                "untested_structure_hypothesis",
            },
        )
        for source in self.matrix["source_paths"]:
            self.assertTrue((ROOT / source).is_file(), source)

    def test_decision_and_unique_structure_direction_are_explicit(self):
        self.assertIn(self.packet["decision"], ALLOWED_DECISIONS)
        self.assertEqual(self.packet["decision"], "restructure_family_worth_studying")
        direction = self.packet["unique_priority_structure_direction"]
        self.assertEqual(direction["hypothesis_id"], "regime-conditioned-branch-factorization-v1")
        self.assertEqual(direction["risk_class"], "medium")
        self.assertTrue(direction["new_candidate_required"])
        self.assertFalse(direction["new_data_required"])
        self.assertTrue(direction["backtest_required"])
        self.assertFalse(direction["validation_required"])
        self.assertFalse(direction["holdout_required"])
        self.assertIn("Hyperopt", direction["forbidden_next_campaign_scope"])
        self.assertIn("automatic execution", direction["forbidden_next_campaign_scope"])

    def test_protected_authorities_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), STRATEGY_SHA256)
        manifest_result = validate_protected_manifests(ROOT)
        self.assertTrue(manifest_result["passed"])
        self.assertTrue(all(all(item["checks"].values()) for item in manifest_result["manifests"]))


if __name__ == "__main__":
    unittest.main()
