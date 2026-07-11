from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("stage3d4b", ROOT / "scripts/close_stage3d4b_research_branch.py")
s = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(s)


class Stage3D4BClosureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proposal = s.load_simple_yaml(ROOT / s.PROPOSAL)
        cls.closure = s.load_simple_yaml(ROOT / s.CLOSURE)
        cls.final = json.loads((ROOT / s.FINAL_JSON).read_text(encoding="utf-8"))
        cls.approval = json.loads((ROOT / s.APPROVAL_EVENT).read_text(encoding="utf-8"))

    def test_proposal_is_human_approved_no_change(self):
        self.assertEqual(self.proposal["status"], "approved_no_change")
        self.assertEqual(self.proposal["approver_type"], "human_user")
        self.assertEqual(self.proposal["decision"], "A_keep_current")

    def test_proposal_hash_change_is_explicit(self):
        self.assertEqual(self.proposal["preapproval_proposal_sha256"], s.PREAPPROVAL_HASH)
        self.assertEqual(self.proposal["proposal_sha256"], s.self_hash(self.proposal, "proposal_sha256"))
        old = s.load_simple_yaml(ROOT / s.PREAPPROVAL)
        self.assertEqual(old["proposal_sha256"], s.PREAPPROVAL_HASH)

    def test_approval_authorizes_no_code_or_candidate(self):
        for field in ("code_change_authorized", "candidate_creation_authorized", "search_continuation_authorized", "mechanism_change_authorized"):
            self.assertFalse(self.proposal[field])

    def test_branch_is_closed_by_exhausted_evidence(self):
        self.assertEqual(self.closure["status"], "closed_evidence_exhausted")
        self.assertNotIn(self.closure["status"], {"failed", "abandoned", "champion_rejected"})

    def test_closed_variables_cannot_enter_threshold_queue(self):
        self.assertEqual(set(self.closure["variables"]), set(s.VARIABLES))
        for value in self.closure["variables"].values():
            self.assertEqual(value["research_status"], "closed_for_current_scope")
            self.assertFalse(value["single_threshold_search_allowed"])

    def test_historical_artifacts_are_preserved(self):
        for path, expected in self.closure["historical_artifact_integrity"].items():
            self.assertEqual(s.sha256_file(ROOT / path).lower(), expected)
        self.assertFalse(self.closure["historical_artifacts_modified"])

    def test_reopen_conditions_are_exact(self):
        self.assertEqual(tuple(self.closure["reopen_conditions"]), s.REOPEN_CONDITIONS)

    def test_unsupported_reopen_reasons_are_rejected(self):
        self.assertEqual(tuple(self.closure["insufficient_reopen_reasons"]), s.INSUFFICIENT_REOPEN_REASONS)
        self.assertIn("llm_hunch", self.closure["insufficient_reopen_reasons"])

    def test_registry_preserves_approval_and_closure_events(self):
        conn = sqlite3.connect(ROOT / s.REGISTRY)
        try:
            approval = conn.execute("SELECT COUNT(*) FROM stage3d4b_mechanism_approval_events WHERE event_id=?", (self.approval["event_id"],)).fetchone()[0]
            closure = conn.execute("SELECT COUNT(*) FROM stage3d4b_branch_closure_events WHERE closure_id=?", (self.closure["closure_id"],)).fetchone()[0]
            variables = conn.execute("SELECT COUNT(*) FROM stage3d4b_variable_governance_events WHERE closure_id=?", (self.closure["closure_id"],)).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual((approval, closure, variables), (1, 1, 4))

    def test_mechanism_decision_keeps_current_semantics(self):
        self.assertEqual(self.closure["mechanism_decision"], "keep_current")
        self.assertEqual(self.closure["approved_mechanism"], "A_keep_current")

    def test_engineering_validity_is_separate_from_research_closure(self):
        self.assertEqual(self.closure["engineering_validity"], "verified")
        self.assertEqual(self.closure["research_status"], "closed_evidence_exhausted")
        self.assertEqual(self.closure["code_change_status"], "not_required")

    def test_strategy_hash_is_unchanged(self):
        self.assertEqual(s.sha256_file(ROOT / s.STRATEGY).lower(), s.BASE_STRATEGY_HASH)

    def test_no_candidate_created_or_modified(self):
        self.assertFalse(self.closure["forbidden_actions"]["candidate_created"])
        self.assertFalse(self.closure["forbidden_actions"]["candidate_modified"])

    def test_no_backtest_or_hyperopt_was_run(self):
        self.assertFalse(self.closure["forbidden_actions"]["backtest_run"])
        self.assertFalse(self.closure["forbidden_actions"]["hyperopt_run"])

    def test_no_validation_or_holdout_access(self):
        self.assertFalse(self.closure["forbidden_actions"]["validation_accessed"])
        self.assertFalse(self.closure["forbidden_actions"]["holdout_accessed"])

    def test_invalidation_and_recertification_lineage_is_complete(self):
        lineage = self.closure["experiment_lineage"]
        self.assertEqual(lineage["invalidated_original_experiment_ids"], list(range(2, 11)))
        self.assertEqual(lineage["recertified_experiment_ids"], list(range(1, 11)))

    def test_trade_and_development_conclusions_are_frozen(self):
        conclusions = self.closure["conclusions"]
        self.assertEqual(conclusions["trade_changed_experiment_ids"], [6, 7, 8])
        self.assertEqual(conclusions["development_eligible_experiment_ids"], [])

    def test_duplicate_signal_lifecycle_supports_no_change(self):
        conclusions = self.closure["conclusions"]
        self.assertEqual(conclusions["duplicate_same_direction_signal_count"], 12)
        self.assertEqual(conclusions["missed_post_exit_reentry_opportunity_count"], 0)
        self.assertEqual(conclusions["later_independent_setup_reappearance_count"], 2)
        self.assertEqual(conclusions["expired_before_flat_count"], 10)

    def test_final_report_is_complete_and_self_hashed(self):
        self.assertEqual(self.final["status"], "completed")
        self.assertEqual(self.final["final_sha256"], s.self_hash(self.final, "final_sha256"))
        self.assertTrue((ROOT / s.FINAL_MD).is_file())


if __name__ == "__main__":
    unittest.main()
