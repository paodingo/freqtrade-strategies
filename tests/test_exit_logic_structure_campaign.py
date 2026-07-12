import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document, sha256_file  # noqa: E402
from route_research_approval import route_proposal  # noqa: E402
from stage4b1_governance import (  # noqa: E402
    verify_campaign_fingerprint,
    verify_constitution_approval,
    verify_human_selection_for,
)


class ExitLogicStructureCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        cls.constitution_event = load_document(ROOT / "research/governance/approvals/research-constitution-v1-approval.json")
        cls.proposal = load_document(ROOT / "research/director/next/proposals/exit-logic-structure-audit-v1.json")
        cls.selection = load_document(ROOT / "research/director/approvals/exit-logic-structure-audit-v1-human-selection.json")
        cls.campaign = load_document(ROOT / "research/director/compiled/exit-logic-structure-audit-v1/campaign.yaml")
        cls.authorization = load_document(ROOT / "research/director/compiled/exit-logic-structure-audit-v1/execution-authorization.json")
        cls.attribution = load_document(ROOT / "research/analysis/exit-logic-audit/exit-attribution.json")
        cls.decision = load_document(ROOT / "research/director/compiled/exit-logic-structure-audit-v1/execution/audit-decision.json")
        cls.execution = load_document(ROOT / "research/director/compiled/exit-logic-structure-audit-v1/execution/campaign-execution.json")
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.next_run = load_document(ROOT / "research/director/next-after-exit/proposals/director-run.json")
        cls.registry = load_document(ROOT / "research/director/registry-records.json")

    def test_01_constitution_hash_remains_approved(self):
        self.assertTrue(verify_constitution_approval(ROOT, self.constitution, self.constitution_event)["matched"])

    def test_02_human_selection_matches_only_exit_logic_proposal(self):
        result = verify_human_selection_for(self.proposal, self.selection, "exit-logic-structure-audit-v1")
        self.assertTrue(result["matched"])
        self.assertEqual(self.selection["excluded_proposal_ids"], ["regime-branch-structure-audit-v1"])

    def test_03_compiled_campaign_fingerprint_matches(self):
        result = verify_campaign_fingerprint(self.campaign, self.authorization["approved_compiled_fingerprint"])
        self.assertTrue(result["matched"])
        self.assertEqual(result["actual"], "a4c3b5d8d072963441d2dce1e989d71822062d65a58f610cac40145a79a9f3ae")

    def test_04_fingerprint_drift_is_blocked(self):
        changed = copy.deepcopy(self.campaign)
        changed["stop_conditions"].append("silent_change")
        result = verify_campaign_fingerprint(changed, self.authorization["approved_compiled_fingerprint"])
        self.assertFalse(result["matched"])
        self.assertEqual(result["reason_code"], "compiled_campaign_fingerprint_drift")

    def test_05_low_risk_route_is_approved_under_constitution(self):
        route = route_proposal(self.proposal, self.constitution, self.selection)
        self.assertEqual(route["decision"], "auto_approved_under_constitution")
        self.assertTrue(route["approval_granted"])

    def test_06_portfolio_budget_limits_execution_to_one(self):
        self.assertEqual(self.selection["portfolio_budget"]["max_campaigns"], 1)
        self.assertEqual(self.campaign["budget"]["max_campaigns"], 1)

    def test_07_all_three_read_only_steps_completed(self):
        self.assertEqual(len(self.execution["steps"]), 3)
        self.assertTrue(all(row["status"] == "completed_read_only" for row in self.execution["steps"]))

    def test_08_temporal_exit_counts_are_complete(self):
        self.assertEqual(self.attribution["slice_count"], 4)
        self.assertEqual(self.attribution["aggregate"]["total_exits"], 82)
        self.assertEqual(self.attribution["aggregate"]["exit_reason_counts"], {"force_exit": 2, "ranging_target_middle": 9, "roi": 40, "stop_loss": 28, "trending_time_stop": 3})

    def test_09_negative_slice_is_identified_without_causal_overclaim(self):
        self.assertEqual(self.attribution["aggregate"]["negative_return_slice_ids"], ["stage3e1-s02"])
        self.assertFalse(self.attribution["causal_claim_allowed"])

    def test_10_prior_exit_delta_evidence_is_zero(self):
        prior = self.attribution["prior_exit_delta_attribution"]
        self.assertEqual(prior["exit_delta_count"], 0)
        self.assertFalse(prior["direct_exit_mutation_evidence_available"])

    def test_11_first_trigger_and_reentry_evidence_show_no_conflict(self):
        evidence = self.attribution["first_trigger_semantics"]
        self.assertEqual(evidence["conflict_count"], 0)
        self.assertEqual(evidence["real_missed_reentry_opportunity_count"], 0)

    def test_12_no_exit_or_risk_change_is_warranted(self):
        self.assertEqual(self.decision["status"], "no_exit_change_warranted_insufficient_causal_evidence")
        self.assertFalse(self.decision["strategy_or_risk_change_warranted"])
        self.assertFalse(self.attribution["strategy_or_risk_change_warranted"])

    def test_13_no_candidate_strategy_mutation_backtest_or_hyperopt(self):
        self.assertFalse(self.decision["candidate_created"])
        self.assertFalse(self.decision["strategy_modified"])
        self.assertFalse(self.decision["backtest_or_parameter_search_run"])
        self.assertFalse(self.decision["hyperopt_run"])

    def test_14_no_validation_or_holdout_access(self):
        self.assertEqual(self.decision["validation_accesses"], 0)
        self.assertEqual(self.decision["holdout_accesses"], 0)

    def test_15_only_selected_campaign_executed(self):
        self.assertEqual(self.execution["executed_proposal_ids"], ["exit-logic-structure-audit-v1"])
        self.assertFalse(self.execution["second_campaign_executed"])

    def test_16_required_artifacts_exist(self):
        self.assertTrue((ROOT / "research/analysis/exit-logic-audit/exit-attribution.json").is_file())
        self.assertTrue((ROOT / "research/analysis/exit-logic-audit/exit-structure-audit.md").is_file())

    def test_17_registry_records_exactly_one_generic_campaign_run(self):
        self.assertEqual(self.registry["counts"]["research_campaign_runs"], 1)
        rows = self.registry["tables"]["research_campaign_runs"]
        self.assertEqual(rows[0]["proposal_id"], "exit-logic-structure-audit-v1")
        self.assertEqual(rows[0]["candidate_created"], 0)
        self.assertEqual(rows[0]["strategy_modified"], 0)

    def test_18_current_research_state_records_completion(self):
        state = self.state["exit_logic_structure_audit"]
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["campaign_executed"])
        self.assertFalse(state["strategy_or_risk_change_warranted"])
        self.assertEqual(self.state["state_conflicts"], [])

    def test_19_next_proposal_is_generated_but_not_executed(self):
        self.assertEqual([row["proposal_id"] for row in self.next_run["proposals"]], ["regime-branch-structure-audit-v1"])
        self.assertFalse(self.next_run["execution_authorized"])
        self.assertFalse(self.state["exit_logic_structure_audit"]["next_campaign_executed"])

    def test_20_strategy_hash_is_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509")

    def test_21_git_definition_of_done_remains_in_campaign(self):
        required = {"targeted tests pass", "readiness pass", "baseline verifier pass", "logical commit", "clean versioned worktree"}
        self.assertTrue(required.issubset(set(self.campaign["git_completion_requirements"])))

    def test_22_stage4c_did_not_start(self):
        self.assertFalse(self.execution["stage4c_started"])
        self.assertFalse(self.state["exit_logic_structure_audit"]["stage4c_started"])


if __name__ == "__main__":
    unittest.main()
