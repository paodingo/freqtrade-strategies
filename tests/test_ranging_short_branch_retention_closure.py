from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_current_research_state as state_builder
import close_ranging_short_branch_retention as closure_script
from research_director_common import proposal_fingerprint

CLOSURE = ROOT / "research/closures/ranging-short-branch-retention-review-v1.json"
APPROVAL = ROOT / closure_script.APPROVAL
FINAL_JSON = ROOT / closure_script.FINAL_JSON
FINAL_MD = ROOT / closure_script.FINAL_MD
STATE = ROOT / closure_script.STATE
PROPOSAL = ROOT / closure_script.PROPOSAL
REGISTRY_EXPORT = ROOT / closure_script.REGISTRY_EXPORT


class RangingShortBranchRetentionClosureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
        cls.approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
        cls.final = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
        cls.state = json.loads(STATE.read_text(encoding="utf-8"))
        cls.proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
        cls.registry = json.loads(REGISTRY_EXPORT.read_text(encoding="utf-8"))

    def test_approved_retention_closure_exists(self):
        self.assertTrue(CLOSURE.is_file(), "approved retention closure has not been recorded")
        self.assertEqual(self.closure["status"], "closed_mixed_temporal_dependency")

    def test_proposal_fingerprint_and_human_decision_are_exact(self):
        self.assertEqual(proposal_fingerprint(self.proposal), closure_script.PROPOSAL_FINGERPRINT)
        self.assertEqual(self.approval["proposal_fingerprint"], closure_script.PROPOSAL_FINGERPRINT)
        self.assertEqual(self.approval["decision"], "retain_current_branch")
        self.assertEqual(self.approval["approval_status"], "approved")
        self.assertEqual(self.approval["approver_type"], "human_user")
        self.assertEqual(
            self.approval["approval_fingerprint"],
            closure_script.self_fingerprint(self.approval, "approval_fingerprint"),
        )

    def test_all_execution_authorizations_are_false(self):
        self.assertTrue(all(value is False for value in self.approval["authorization"].values()))
        self.assertTrue(all(value is False for value in self.closure["execution_boundaries"].values()))

    def test_frozen_slice_conclusions_and_mixed_temporal_closure(self):
        self.assertEqual(self.closure["slice_conclusions"], closure_script.SLICE_CONCLUSIONS)
        self.assertFalse(self.closure["temporally_stable_deletion_evidence"])
        self.assertEqual(self.closure["formal_branch_action"], "retained_unchanged")
        self.assertEqual(
            self.closure["closure_fingerprint"],
            closure_script.self_fingerprint(self.closure, "closure_fingerprint"),
        )

    def test_reopen_boundary_is_narrow_and_nonautomatic(self):
        self.assertEqual(self.closure["reopen_conditions"], closure_script.REOPEN_CONDITIONS)
        self.assertEqual(self.closure["insufficient_reopen_reasons"], closure_script.INSUFFICIENT_REOPEN_REASONS)
        self.assertEqual(
            self.closure["future_evidence_reference"]["allowed_only_for"],
            "new_human_approved_regime_conditioned_routing_research",
        )
        self.assertFalse(self.closure["future_evidence_reference"]["automatic_reopen_allowed"])

    def test_formal_strategy_and_frozen_candidate_hashes_are_preserved(self):
        protected = self.closure["protected_identity"]
        self.assertEqual(closure_script.sha256_file(ROOT / closure_script.STRATEGY), protected["formal_strategy_sha256"])
        self.assertEqual(closure_script.sha256_file(ROOT / closure_script.CANDIDATE), protected["candidate_sha256"])

    def test_state_records_closure_and_resolves_pending_review(self):
        closure = next(item for item in self.state["closed_branches"] if item["closure_id"] == closure_script.PROPOSAL_ID)
        self.assertEqual(closure["status"], "closed_mixed_temporal_dependency")
        self.assertEqual(
            self.state["ranging_short_temporal_branch_contribution_review"]["next_proposal_status"],
            "resolved_human_retain_current_branch",
        )
        self.assertFalse(self.state["ranging_short_branch_retention_review"]["next_campaign_generated"])
        prior = next(
            item for item in self.state["proposal_history"]
            if item["proposal_id"] == "ranging-short-branch-decision-review-v1"
        )
        self.assertEqual(prior["historical_status"], "completed")
        self.assertEqual(prior["resolved_by"], "branch_mixed_temporal_dependency")
        self.assertNotIn(
            "ranging_short",
            " ".join(str(item.get("direction", "")) for item in self.state["possible_next_directions"]),
        )

    def test_registry_records_governance_only_closure(self):
        selection = next(
            row for row in self.registry["tables"]["proposal_selection_events"]
            if row["proposal_id"] == closure_script.PROPOSAL_ID
        )
        run = next(
            row for row in self.registry["tables"]["research_campaign_runs"]
            if row["run_id"] == closure_script.RUN_ID
        )
        self.assertEqual(selection["approval_status"], "approved")
        self.assertEqual(run["result_code"], "closed_mixed_temporal_dependency")
        self.assertEqual(run["campaign_executed"], 0)
        self.assertEqual((run["candidate_created"], run["strategy_modified"]), (0, 0))
        self.assertEqual((run["validation_accesses"], run["holdout_accesses"]), (0, 0))

    def test_final_report_is_complete_and_self_fingerprinted(self):
        self.assertTrue(FINAL_MD.is_file())
        self.assertEqual(self.final["decision"], "retain_current_branch")
        self.assertTrue(self.final["no_next_campaign_generated"])
        self.assertTrue(self.final["no_research_execution_performed"])
        self.assertEqual(
            self.final["final_report_fingerprint"],
            closure_script.self_fingerprint(self.final, "final_report_fingerprint"),
        )

    def test_future_state_rebuild_preserves_closure(self):
        rebuilt = state_builder.build_state(ROOT, None)
        closure_ids = {item["closure_id"] for item in rebuilt["closed_branches"]}
        self.assertIn(closure_script.PROPOSAL_ID, closure_ids)
        self.assertEqual(
            rebuilt["ranging_short_branch_retention_review"]["closure_status"],
            "closed_mixed_temporal_dependency",
        )


if __name__ == "__main__":
    unittest.main()
