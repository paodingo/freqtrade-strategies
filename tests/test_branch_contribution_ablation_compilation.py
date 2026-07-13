import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import fingerprint, load_document, proposal_fingerprint  # noqa: E402


class BranchContributionAblationCompilationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = ROOT / "research/director/compiled/branch-contribution-ablation-v1"
        cls.campaign = load_document(cls.output / "campaign.yaml")
        cls.packet = load_document(cls.output / "human-decision-packet.json")
        cls.unit_map = load_document(cls.output / "ablation-unit-map.json")
        cls.proposal = load_document(ROOT / "research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json")
        cls.state = load_document(ROOT / "research/director/current-research-state.json")

    def test_proposal_and_campaign_fingerprints_are_exact(self):
        self.assertEqual(proposal_fingerprint(self.proposal), "8f7211ad73d4a3528da6fd92e0b7e958e2aebf6159fc2773bc8be8740f9e55cc")
        computed = fingerprint({key: value for key, value in self.campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
        self.assertEqual(computed, self.campaign["campaign_fingerprint"])
        self.assertEqual(computed, "a3db3e0e2d52f6caf700732150a396acee1fa7accc9f054eaef2cbab43e6490f")

    def test_rebuilt_state_is_clean_and_router_verified(self):
        self.assertTrue(self.state["git"]["versioned_worktree_clean"])
        self.assertRegex(self.state["git"]["head"], r"^[0-9a-f]{40}$")
        self.assertTrue(self.state["registry"]["available"])
        router = self.state["router_extraction_semantic_equivalence"]
        self.assertEqual(router["status"], "router_extraction_semantic_equivalence_verified")
        self.assertEqual(router["btc_trade_count"], 27)
        self.assertEqual(router["eth_trade_count"], 27)

    def test_all_queue_steps_are_unexecuted(self):
        self.assertEqual(len(self.campaign["experiment_queue"]), 3)
        self.assertTrue(all(item["status"] == "queued_unexecuted" for item in self.campaign["experiment_queue"]))
        self.assertTrue(all(item["requires_new_human_execution_approval"] for item in self.campaign["experiment_queue"]))
        self.assertFalse(self.campaign["execution_authorized"])

    def test_unit_map_has_five_eligible_groups_and_ineligible_router(self):
        eligible = [item for item in self.unit_map["units"] if item["eligible_as_single_candidate_unit"]]
        ineligible = [item for item in self.unit_map["units"] if not item["eligible_as_single_candidate_unit"]]
        self.assertEqual(len(eligible), 5)
        self.assertEqual([item["unit_id"] for item in ineligible], ["shared_regime_router"])
        self.assertIsNone(self.unit_map["selected_unit"])

    def test_budget_and_human_decision_packet_are_frozen(self):
        budget = self.campaign["budget"]
        self.assertEqual(budget["max_candidates"], 1)
        self.assertEqual(budget["max_backtest_calls"], 8)
        self.assertEqual(budget["max_wall_clock_minutes"], 120)
        self.assertEqual(budget["max_validation_accesses"], 0)
        self.assertEqual(budget["max_holdout_accesses"], 0)
        self.assertEqual(self.packet["approval_status"], "pending_human_execution_approval")
        self.assertFalse(self.packet["candidate_created"])
        self.assertFalse(self.packet["backtest_run"])

    def test_compilation_remained_unexecuted_before_exact_human_approval(self):
        self.assertFalse(self.packet["candidate_created"])
        self.assertFalse(self.packet["backtest_run"])
        approval = load_document(ROOT / "research/governance/approvals/branch-contribution-ablation-v1-execution-approval.json")
        self.assertTrue(approval["execution_authorized"])
        candidates = list((ROOT / "research/candidates/branch-contribution-ablation-v1").rglob("*.py"))
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "RegimeAware_Ablation_RangingShort_C1.py")
        stopped = load_document(ROOT / "research/analysis/branch-contribution-ablation-v1/campaign-stopped.json")
        self.assertEqual(stopped["research_verdict"], "not_evaluated")
        self.assertEqual(stopped["completed_backtest_calls"], 0)


if __name__ == "__main__":
    unittest.main()
