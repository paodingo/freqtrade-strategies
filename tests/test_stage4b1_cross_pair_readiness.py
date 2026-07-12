import copy
import json
import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document, proposal_fingerprint, sha256_file  # noqa: E402
from route_research_approval import route_proposal  # noqa: E402
from stage4b1_governance import (  # noqa: E402
    APPROVED_CAMPAIGN_FINGERPRINT,
    classify_public_endpoint,
    provisioning_scope,
    verify_campaign_fingerprint,
    verify_constitution_approval,
    verify_human_selection,
)


class Stage4B1CrossPairReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        cls.constitution_event = load_document(ROOT / "research/governance/approvals/research-constitution-v1-approval.json")
        cls.proposal = load_document(ROOT / "research/director/proposals/cross-pair-data-readiness-audit-v1.json")
        cls.selection = load_document(ROOT / "research/director/approvals/cross-pair-data-readiness-audit-v1-human-selection.json")
        cls.campaign = load_document(ROOT / "research/director/compiled/cross-pair-data-readiness-audit-v1/campaign.yaml")
        cls.authorization = load_document(ROOT / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution-authorization.json")
        cls.decision = load_document(ROOT / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/readiness-decision.json")
        cls.requirements = load_document(ROOT / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/frozen-data-requirements.yaml")
        cls.matrix = load_document(ROOT / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/cross-pair-readiness-matrix.json")
        cls.execution = load_document(ROOT / "research/director/compiled/cross-pair-data-readiness-audit-v1/execution/campaign-execution.json")
        cls.state = load_document(ROOT / "research/director/current-research-state.json")
        cls.next_run = load_document(ROOT / "research/director/next/proposals/director-run.json")
        cls.registry_export = load_document(ROOT / "research/director/registry-records.json")

    def test_01_constitution_transitioned_to_human_approved(self):
        self.assertEqual(self.constitution["status"], "approved")
        self.assertEqual(self.constitution["approval_status"], "approved")
        self.assertEqual(self.constitution["approver_type"], "human_user")
        self.assertFalse(self.constitution["agent_mutable"])

    def test_02_constitution_hash_is_frozen_by_approval_event(self):
        result = verify_constitution_approval(ROOT, self.constitution, self.constitution_event)
        self.assertTrue(result["matched"])
        self.assertEqual(result["actual_sha256"], "ff0ca1b7f3aa4f7f0a7d6b893095ba618d1ecf50cf7044dfeb3152bd91826722")
        self.assertFalse(self.constitution_event["silent_modification_allowed"])

    def test_03_approved_compiled_campaign_fingerprint_matches(self):
        result = verify_campaign_fingerprint(self.campaign)
        self.assertTrue(result["matched"])
        self.assertEqual(result["actual"], APPROVED_CAMPAIGN_FINGERPRINT)

    def test_04_compiled_campaign_fingerprint_drift_blocks(self):
        changed = copy.deepcopy(self.campaign)
        changed["experiment_queue"][0]["action"] = "silently changed"
        result = verify_campaign_fingerprint(changed)
        self.assertFalse(result["matched"])
        self.assertEqual(result["reason_code"], "compiled_campaign_fingerprint_drift")

    def test_05_human_selection_and_low_risk_auto_approval(self):
        self.assertTrue(verify_human_selection(self.proposal, self.selection)["matched"])
        route = route_proposal(self.proposal, self.constitution, self.selection)
        self.assertEqual(route["decision"], "auto_approved_under_constitution")
        self.assertTrue(route["approval_granted"])

    def test_06_medium_and_high_risk_still_require_human_approval(self):
        for risk in ("medium", "high"):
            proposal = copy.deepcopy(self.proposal)
            proposal["risk_class"] = risk
            self.assertEqual(route_proposal(proposal, self.constitution, self.selection)["decision"], "human_approval_required")

    def test_07_forbidden_never_executes(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["risk_class"] = "forbidden"
        route = route_proposal(proposal, self.constitution, self.selection)
        self.assertEqual(route["decision"], "forbidden")
        self.assertFalse(route["approval_granted"])

    def test_08_portfolio_budget_is_exactly_one_campaign(self):
        self.assertEqual(self.selection["portfolio_budget"], {"max_campaigns": 1, "max_wall_clock_hours": 4, "max_validation_accesses": 0, "max_holdout_accesses": 0})
        self.assertEqual(self.campaign["budget"]["max_campaigns"], 1)

    def test_09_only_selected_proposal_executed(self):
        self.assertEqual(self.execution["executed_proposal_ids"], ["cross-pair-data-readiness-audit-v1"])
        self.assertEqual(set(self.execution["unexecuted_proposal_ids"]), {"exit-logic-structure-audit-v1", "regime-branch-structure-audit-v1"})

    def test_10_second_proposal_is_not_auto_approved(self):
        proposal = load_document(ROOT / "research/director/proposals/exit-logic-structure-audit-v1.json")
        route = route_proposal(proposal, self.constitution, self.selection)
        self.assertFalse(route["approval_granted"])
        self.assertNotEqual(route["decision"], "auto_approved_under_constitution")

    def test_11_unfrozen_pair_scope_produces_plan_only(self):
        scope = provisioning_scope(self.proposal, self.campaign)
        self.assertFalse(scope["provisioning_authorized"])
        self.assertEqual(scope["reason_code"], "human_scope_required_for_provisioning")
        self.assertFalse(self.decision["provisioning_executed"])

    def test_12_fully_frozen_public_scope_can_become_provisionable(self):
        campaign = copy.deepcopy(self.campaign)
        campaign["provisioning_scope"] = {"pair": "ETH/USDT:USDT", "timeframe": "1h", "coverage_rule": "2024-01-01..2024-08-30"}
        self.assertTrue(provisioning_scope(self.proposal, campaign)["provisioning_authorized"])

    def test_13_public_market_endpoints_only(self):
        self.assertTrue(classify_public_endpoint("GET", "fapi.binance.com", "/fapi/v1/exchangeInfo")["allowed"])
        self.assertTrue(classify_public_endpoint("GET", "data.binance.vision", "/data/futures/um/monthly/klines/ETHUSDT/1h/file.zip")["allowed"])

    def test_14_private_endpoints_are_rejected(self):
        for path in ("/fapi/v2/account", "/fapi/v1/order", "/fapi/v2/positionRisk"):
            self.assertFalse(classify_public_endpoint("GET", "fapi.binance.com", path)["allowed"])

    def test_15_new_dataset_cannot_be_development_or_validation(self):
        self.assertEqual(self.requirements["intended_use_if_later_approved"], "cross_pair_readiness")
        self.assertFalse(self.requirements["development_or_validation_label_allowed"])
        self.assertFalse(self.decision["new_dataset_created"])

    def test_16_no_candidate_backtest_ranking_or_hyperopt(self):
        self.assertFalse(self.decision["candidate_created"])
        self.assertFalse(self.decision["backtest_or_ranking_run"])
        self.assertFalse(self.decision["hyperopt_run"])

    def test_17_no_validation_or_holdout_access(self):
        self.assertEqual(self.decision["validation_accesses"], 0)
        self.assertEqual(self.decision["holdout_accesses"], 0)
        self.assertFalse(self.matrix["validation_or_holdout_manifests_inspected"])

    def test_18_campaign_completed_with_scope_blocker(self):
        self.assertTrue(self.decision["campaign_executed"])
        self.assertEqual(self.decision["status"], "human_scope_required_for_provisioning")
        self.assertEqual(len(self.execution["steps"]), 3)
        self.assertTrue(all(item["status"] == "completed_read_only" for item in self.execution["steps"]))

    def test_19_current_research_state_was_updated(self):
        stage = self.state["stage4b1_execution"]
        self.assertEqual(stage["status"], "completed")
        self.assertTrue(stage["campaign_executed"])
        self.assertFalse(stage["new_dataset_created"])
        self.assertEqual(self.state["state_conflicts"], [])

    def test_20_next_director_run_generated_but_not_executed(self):
        ids = [item["proposal_id"] for item in self.next_run["proposals"]]
        self.assertEqual(ids[0], "exit-logic-structure-audit-v1")
        self.assertNotIn("cross-pair-data-readiness-audit-v1", ids)
        self.assertFalse(self.next_run["execution_authorized"])
        self.assertFalse(self.state["stage4b1_execution"]["next_campaign_executed"])

    def test_21_registry_contains_only_one_stage4b1_run(self):
        counts = self.registry_export["counts"]
        self.assertEqual(counts["stage4b1_campaign_runs"], 1)
        self.assertEqual(counts["constitution_approvals"], 1)
        self.assertEqual(counts["proposal_selection_events"], 1)
        self.assertTrue(self.registry_export["execution_results_recorded"])
        self.assertFalse(self.registry_export["fabricated_execution_results_recorded"])

    def test_22_registry_run_records_no_dataset_or_data_access(self):
        rows = self.registry_export["tables"]["stage4b1_campaign_runs"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dataset_created"], 0)
        self.assertEqual(rows[0]["validation_accesses"], 0)
        self.assertEqual(rows[0]["holdout_accesses"], 0)

    def test_23_git_definition_of_done_is_preserved(self):
        required = {"targeted tests pass", "readiness pass", "baseline verifier pass", "logical commit", "clean versioned worktree"}
        self.assertTrue(required.issubset(set(self.campaign["git_completion_requirements"])))

    def test_24_strategy_hash_is_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509")

    def test_25_stage4c_did_not_start(self):
        self.assertFalse(self.execution["stage4c_started"])
        self.assertFalse(self.state["stage4b1_execution"]["stage4c_started"])


if __name__ == "__main__":
    unittest.main()
