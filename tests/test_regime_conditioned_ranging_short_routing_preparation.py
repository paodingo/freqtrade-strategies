from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import research_director  # noqa: E402
import compile_research_campaign  # noqa: E402
from research_director_common import load_document, proposal_fingerprint  # noqa: E402


PROPOSAL_ID = "regime-conditioned-ranging-short-routing-v1"


class RegimeConditionedRangingShortRoutingPreparationTest(unittest.TestCase):
    def generated(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        run = research_director.generate(
            state,
            constitution,
            "regime-conditioned ranging-short routing",
            {"max_campaigns": 1, "max_wall_clock_minutes": 30},
            "medium",
            10,
        )
        proposal = next(item for item in run["proposals"] if item["proposal_id"] == PROPOSAL_ID)
        return state, constitution, proposal

    def test_director_generates_medium_risk_routing_proposal_after_retention_closure(self):
        _, _, proposal = self.generated()
        self.assertEqual(proposal["risk_class"], "medium")
        self.assertEqual(proposal_fingerprint(proposal), proposal["semantic_fingerprint"])
        self.assertFalse(proposal["branch_closure_reopen_check"]["reopen_requested"])

    def test_compiler_freezes_read_only_routing_plan_and_zero_execution_budget(self):
        state, constitution, proposal = self.generated()
        campaign, metadata, _ = compile_research_campaign.compile_campaign(
            ROOT, proposal, state, constitution
        )
        self.assertIn("regime_conditioned_routing_plan", campaign)
        plan = campaign["regime_conditioned_routing_plan"]
        self.assertEqual(plan["research_unit"], "regime_conditioned_routing_evidence_matrix_v1")
        self.assertEqual(plan["compilation_approval"]["approval_status"], "approved_for_compilation_only")
        self.assertFalse(plan["compilation_approval"]["execution_authorized"])
        self.assertEqual(plan["slice_conclusions"], {
            "s01": "inconclusive",
            "s02": "positive_contributor",
            "s03": "negative_contributor",
            "s04": "negative_contributor",
        })
        self.assertEqual(campaign["budget"]["max_candidates"], 0)
        self.assertEqual(campaign["budget"]["max_backtest_calls"], 0)
        self.assertEqual(campaign["budget"]["max_validation_accesses"], 0)
        self.assertEqual(campaign["budget"]["max_holdout_accesses"], 0)
        self.assertFalse(campaign["execution_authorized"])
        self.assertFalse(metadata["campaign_executed"])
        self.assertEqual(plan["future_separate_approval_envelope"]["max_candidates"], 1)
        self.assertEqual(plan["future_separate_approval_envelope"]["max_backtest_calls"], 16)

    def test_preparation_artifacts_are_chinese_offline_and_registry_bound(self):
        compiled = ROOT / "research/director/compiled" / PROPOSAL_ID
        report = ROOT / "reports/research" / f"{PROPOSAL_ID}-decision-report.html"
        packet = load_document(compiled / "human-decision-packet.json")
        campaign = load_document(compiled / "campaign.yaml")
        html = report.read_text(encoding="utf-8")
        self.assertIn('<html lang="zh-CN">', html)
        self.assertIn("人工决策", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertIn(campaign["campaign_fingerprint"], html)
        self.assertEqual(packet["recommendation"], "insufficient_router_context_evidence")
        self.assertFalse(packet["execution_authorized"])
        self.assertFalse(packet["candidate_created"])
        self.assertEqual(packet["backtest_calls"], 0)
        registry = load_document(ROOT / "research/director/registry-records.json")
        rows = registry["tables"]["compiled_campaigns"]
        row = next(item for item in rows if item["proposal_id"] == PROPOSAL_ID)
        self.assertEqual(row["campaign_fingerprint"], campaign["campaign_fingerprint"])
        self.assertEqual(row["execution_authorized"], 0)
        runs = registry["tables"]["research_campaign_runs"]
        self.assertFalse(any(item["proposal_id"] == PROPOSAL_ID for item in runs))


if __name__ == "__main__":
    unittest.main()
