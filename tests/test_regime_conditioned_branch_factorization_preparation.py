import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import fingerprint, load_document, proposal_fingerprint, sha256_file  # noqa: E402


PROPOSAL_FP = "f72b3304d73b5af8883bbb22c851d4d38465fae48adca7bd541f0dd1595b2a3b"
STRATEGY_SHA = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"


class RegimeConditionedBranchFactorizationPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proposal_path = ROOT / "research/director/next-after-strategy-family/proposals/regime-conditioned-branch-factorization-v1.json"
        cls.proposal = load_document(proposal_path)
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.approval = load_document(
            ROOT / "research/governance/approvals/regime-conditioned-branch-factorization-v1-compilation-approval.json"
        )
        compiled = ROOT / "research/director/compiled/regime-conditioned-branch-factorization-v1"
        cls.campaign = load_document(compiled / "campaign.yaml")
        cls.metadata = load_document(compiled / "compilation-metadata.json")
        cls.queue = json.loads((compiled / "experiment-queue.json").read_text(encoding="utf-8"))
        cls.packet = load_document(compiled / "human-decision-packet.json")
        analysis = ROOT / "research/analysis/regime-conditioned-branch-factorization"
        cls.structure = load_document(analysis / "current-structure-map.json")

    def test_current_state_and_proposal_are_revalidated(self):
        self.assertEqual(self.state["state_conflicts"], [])
        self.assertEqual(self.state["git"]["branch"], "research/regime-conditioned-branch-factorization-v1")
        self.assertTrue(self.state["git"]["versioned_worktree_clean"])
        self.assertEqual(proposal_fingerprint(self.proposal), PROPOSAL_FP)
        self.assertEqual(self.proposal["semantic_fingerprint"], PROPOSAL_FP)

    def test_approval_is_compilation_only(self):
        self.assertEqual(self.approval["proposal_fingerprint"], PROPOSAL_FP)
        self.assertEqual(self.approval["approval_status"], "approved_for_compilation_only")
        self.assertFalse(self.approval["execution_authorized"])
        self.assertFalse(self.approval["candidate_creation_authorized"])
        self.assertFalse(self.approval["backtest_authorized"])
        self.assertEqual(self.approval["validation_accesses_authorized"], 0)
        self.assertEqual(self.approval["holdout_accesses_authorized"], 0)

    def test_campaign_fingerprint_and_authority_are_frozen(self):
        computed = fingerprint(
            {key: value for key, value in self.campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}}
        )
        self.assertEqual(computed, self.campaign["campaign_fingerprint"])
        self.assertEqual(computed, self.metadata["campaign_fingerprint"])
        self.assertEqual(self.campaign["compile_mode"], "dry_run")
        self.assertEqual(self.campaign["current_authority"], "compile_and_review_only")
        self.assertFalse(self.campaign["execution_authorized"])
        self.assertFalse(self.metadata["campaign_executed"])
        self.assertFalse(self.metadata["candidate_created"])

    def test_all_29_conditions_and_five_groups_are_structurally_owned(self):
        plan = self.campaign["structural_research_plan"]["current_structure"]
        self.assertEqual(plan["condition_count"], 29)
        self.assertEqual(plan["signal_group_count"], 5)
        self.assertEqual(sum(plan["condition_owner_counts"].values()), 29)
        self.assertEqual(len({item["condition_id"] for item in plan["condition_ownership"]}), 29)
        self.assertTrue(all(item["signal_groups"] for item in plan["condition_ownership"]))
        self.assertEqual(self.structure["condition_count"], 29)
        self.assertEqual(set(self.structure["regime_branches"]), {"trending", "ranging"})

    def test_minimum_unit_is_one_equivalence_candidate_before_ablation(self):
        unit = self.campaign["structural_research_plan"]["minimum_testable_hypothesis"]
        self.assertEqual(unit["hypothesis_id"], "router-extraction-semantic-equivalence-v1")
        self.assertEqual(unit["candidate_count"], 1)
        self.assertEqual(unit["backtest_invocations"], 8)
        sequence = self.campaign["structural_research_plan"]["ordered_research_sequence"]
        self.assertEqual(sequence[1]["authority"], "requires_new_human_execution_approval")
        self.assertEqual(sequence[2]["authority"], "not_compiled_requires_separate_proposal_and_human_approval")
        self.assertFalse(self.packet["branch_ablation"]["included_in_compiled_campaign"])

    def test_queue_is_unexecuted_and_requires_new_human_approval(self):
        self.assertEqual(len(self.queue), 3)
        self.assertTrue(all(item["status"] == "queued_unexecuted" for item in self.queue))
        self.assertTrue(all(item["execution_authorized"] is False for item in self.queue))
        self.assertTrue(all(item["requires_new_human_execution_approval"] is True for item in self.queue))
        self.assertEqual(self.packet["status"], "awaiting_human_execution_approval")
        self.assertFalse(self.packet["candidate_created"])
        self.assertFalse(self.packet["backtest_run"])
        self.assertFalse((ROOT / "research/candidates/regime-conditioned-branch-factorization-v1").exists())

    def test_formal_strategy_and_protected_boundaries_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), STRATEGY_SHA)
        self.assertIn("strategies/**", self.campaign["scope"]["blocked_paths"])
        self.assertIn("research/data/holdout/**", self.campaign["scope"]["blocked_paths"])
        self.assertEqual(self.campaign["budget"]["max_validation_accesses"], 0)
        self.assertFalse(self.campaign["autonomy"]["access_sealed_holdout"])
        self.assertEqual(self.packet["validation_accesses"], 0)
        self.assertEqual(self.packet["holdout_accesses"], 0)


if __name__ == "__main__":
    unittest.main()
