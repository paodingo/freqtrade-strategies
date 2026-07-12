import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document  # noqa: E402
from stage4c1_portfolio import (  # noqa: E402
    eligible_proposals,
    portfolio_decision,
    validate_portfolio_approval,
)


class Stage4C1PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approval = load_document(ROOT / "research/governance/approvals/stage4c1-portfolio-approval.json")
        cls.cycle1 = load_document(ROOT / "research/director/stage4c1/cycle-1/proposals/director-run.json")
        cls.cycle2 = load_document(ROOT / "research/director/stage4c1/cycle-2/proposals/director-run.json")

    def test_human_portfolio_approval_and_constitution_hash_are_valid(self):
        result = validate_portfolio_approval(ROOT, self.approval)
        self.assertTrue(result["passed"])
        self.assertTrue(all(result["checks"].values()))

    def test_cycle1_selects_only_the_ranked_low_risk_proposal(self):
        result = portfolio_decision(self.approval, self.cycle1, [])
        self.assertEqual(result["action"], "execute")
        self.assertEqual(result["selected_proposal_id"], "regime-branch-structure-audit-v1")

    def test_completed_proposal_cannot_be_selected_again(self):
        eligible, excluded = eligible_proposals(self.cycle1, ["regime-branch-structure-audit-v1"])
        self.assertEqual(eligible, [])
        self.assertIn("duplicate_research_question", excluded[0]["reason_codes"])

    def test_medium_risk_requires_human_approval(self):
        run = copy.deepcopy(self.cycle1)
        run["proposals"][0]["risk_class"] = "medium"
        result = portfolio_decision(self.approval, run, [])
        self.assertEqual(result["action"], "stop")
        self.assertIn("human_approval_required_for_risk", result["excluded"][0]["reason_codes"])

    def test_validation_or_holdout_requirement_is_rejected(self):
        for field in ("validation_requirement", "holdout_requirement"):
            run = copy.deepcopy(self.cycle1)
            run["proposals"][0][field] = "required"
            result = portfolio_decision(self.approval, run, [])
            self.assertIn("forbidden_data_access_required", result["excluded"][0]["reason_codes"])

    def test_closed_branch_is_rejected(self):
        run = copy.deepcopy(self.cycle1)
        run["proposals"][0]["branch_closure_reopen_check"]["blocked"] = True
        result = portfolio_decision(self.approval, run, [])
        self.assertIn("closed_branch_no_reopen_evidence", result["excluded"][0]["reason_codes"])

    def test_portfolio_budget_is_fail_closed(self):
        result = portfolio_decision(self.approval, self.cycle1, ["one", "two"])
        self.assertEqual(result["stop_reason"], "portfolio_max_campaigns_reached")

    def test_infrastructure_failure_limit_is_fail_closed(self):
        result = portfolio_decision(self.approval, self.cycle1, [], infrastructure_failures=2)
        self.assertEqual(result["stop_reason"], "max_consecutive_infrastructure_failures_reached")

    def test_cycle2_stops_when_director_has_no_eligible_research(self):
        result = portfolio_decision(self.approval, self.cycle2, ["regime-branch-structure-audit-v1"])
        self.assertEqual(result["action"], "stop")
        self.assertEqual(result["stop_reason"], "no_eligible_low_risk_proposal")
        self.assertIsNone(result["selected_proposal_id"])

    def test_frozen_cycle2_decision_matches_deterministic_selector(self):
        frozen = load_document(ROOT / "research/director/stage4c1/cycle-2/portfolio-decision.json")
        expected = portfolio_decision(self.approval, self.cycle2, ["regime-branch-structure-audit-v1"])
        for key in ("action", "stop_reason", "selected_proposal_id", "eligible", "excluded"):
            self.assertEqual(frozen[key], expected[key])
        self.assertTrue(frozen["approval_validation"]["passed"])

    def test_formal_campaign_outputs_preserve_forbidden_boundaries(self):
        execution = load_document(ROOT / "research/director/compiled/regime-branch-structure-audit-v1/execution/campaign-execution.json")
        decision = execution["decision"]
        self.assertFalse(decision["strategy_modified"])
        self.assertFalse(decision["candidate_created"])
        self.assertFalse(decision["backtest_or_parameter_search_run"])
        self.assertFalse(decision["hyperopt_run"])
        self.assertEqual(decision["validation_accesses"], 0)
        self.assertEqual(decision["holdout_accesses"], 0)
        self.assertFalse(execution["stage4c2_started"])

    def test_selector_can_write_only_to_caller_owned_temporary_path(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "decision.json"
            payload = portfolio_decision(self.approval, self.cycle2, ["regime-branch-structure-audit-v1"])
            output.write_text(json.dumps(payload), encoding="utf-8")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["action"], "stop")


if __name__ == "__main__":
    unittest.main()
