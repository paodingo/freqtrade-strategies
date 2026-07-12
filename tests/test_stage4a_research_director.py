import copy
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_current_research_state import build_state  # noqa: E402
from compile_research_campaign import compile_campaign  # noqa: E402
from export_director_registry import export_registry  # noqa: E402
from research_director import branch_closure_check, generate  # noqa: E402
from research_director_common import (  # noqa: E402
    load_document,
    open_director_registry,
    proposal_fingerprint,
    sha256_file,
    worktree_preflight,
)
from route_research_approval import route_proposal  # noqa: E402


SOURCE_REGISTRY = Path(r"D:\code\freqtrade-strategies-clean\research\registry\research.db")
SOURCE_LINEAGE = Path(r"D:\code\freqtrade-strategies-clean\research\data\data-lineage.sqlite")


class Stage4AResearchDirectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        cls.state = build_state(ROOT, SOURCE_REGISTRY, SOURCE_LINEAGE)
        cls.director_run = generate(cls.state, cls.constitution, None, {"max_experiments": 20}, "low")
        cls.proposal = cls.director_run["proposals"][0] if cls.director_run["proposals"] else load_document(ROOT / "research/director/proposals/cross-pair-data-readiness-audit-v1.json")
        cls.campaign, cls.metadata, cls.brief = compile_campaign(ROOT, cls.proposal, cls.state, cls.constitution)

    def test_clean_worktree_preflight_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-b", "stage4a/research-director"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "stage4a@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Stage4A Test"], cwd=repo, check=True)
            (repo / "seed.txt").write_text("sealed\n", encoding="utf-8")
            subprocess.run(["git", "add", "seed.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            self.assertTrue(worktree_preflight(repo, "stage4a/research-director", head)["passed"])
            (repo / "unexpected.txt").write_text("dirty\n", encoding="utf-8")
            result = worktree_preflight(repo, "stage4a/research-director", head)
            self.assertFalse(result["passed"])
            self.assertEqual(result["untracked"], ["unexpected.txt"])

    def test_constitution_is_human_approved_and_contains_required_prohibitions(self):
        self.assertEqual(self.constitution["status"], "approved")
        self.assertEqual(self.constitution["approval_status"], "approved")
        self.assertEqual(self.constitution["approver_type"], "human_user")
        self.assertFalse(self.constitution["agent_mutable"])
        required = {"live_trading", "private_api", "secret_access", "automatic_holdout", "unapproved_hyperopt", "automatic_closed_branch_reopen", "validation_feedback_mutation", "sealed_dataset_change"}
        self.assertTrue(required.issubset(set(self.constitution["permanent_prohibitions"])))
        self.assertFalse(self.constitution["approval"]["stage4a_auto_execution"])

    def test_state_builder_requires_no_chat_context_and_links_evidence(self):
        rebuilt = build_state(ROOT, SOURCE_REGISTRY, SOURCE_LINEAGE)
        self.assertEqual(rebuilt["formal_strategy"]["sha256"], "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509")
        self.assertEqual(rebuilt["closed_branches"][0]["status"], "closed_evidence_exhausted")
        self.assertFalse(rebuilt["stage4a_boundaries"]["validation_accessed"])
        for item in rebuilt["unresolved_research_questions"]:
            self.assertTrue(item["evidence"])

    def test_registry_closure_conflict_is_not_silently_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "conflict.db"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE stage3d4b_branch_closure_events (closure_id TEXT, research_status TEXT, mechanism_decision TEXT, engineering_validity TEXT, code_change_status TEXT, closure_artifact TEXT)")
            connection.execute("INSERT INTO stage3d4b_branch_closure_events VALUES (?, ?, ?, ?, ?, ?)", ("regime-aware-ranging-thresholds-v1", "open", "change", "unverified", "required", "conflict"))
            connection.commit()
            connection.close()
            state = build_state(ROOT, db)
            self.assertEqual(state["state_conflicts"][0]["status"], "state_conflict")
            self.assertEqual(state["state_conflicts"][0]["conflict_type"], "closure_registry_mismatch")

    def test_closed_branch_and_recorded_reopen_condition(self):
        blocked = branch_closure_check("adjacent-threshold ranging-threshold search", self.state)
        allowed = branch_closure_check("ranging-threshold structural followup", self.state, ["human_approved_strategy_structural_change"])
        self.assertTrue(blocked["blocked"])
        self.assertEqual(blocked["reason_code"], "closed_branch_no_reopen_evidence")
        self.assertFalse(allowed["blocked"])
        self.assertEqual(allowed["recorded_reopen_conditions_met"], ["human_approved_strategy_structural_change"])

    def test_director_rejects_neighbor_threshold_duplicate_and_missing_data(self):
        reasons = {item["proposal_key"]: item["reason_code"] for item in self.director_run["rejected_proposals"]}
        self.assertEqual(reasons["ranging-threshold-neighbor-search"], "closed_branch_no_reopen_evidence")
        self.assertEqual(reasons["repeat-temporal-generalization-profile"], "duplicate_research_question")
        self.assertEqual(reasons["direct-cross-pair-backtest"], "insufficient_data")

    def test_director_can_recommend_no_research(self):
        conflict_state = copy.deepcopy(self.state)
        conflict_state["state_conflicts"] = [{"status": "state_conflict"}]
        result = generate(conflict_state, self.constitution, None, {"max_experiments": 20}, "low")
        self.assertEqual(result["recommendation"], "no_research_recommended")
        self.assertEqual(result["proposals"], [])

    def test_proposals_are_ranked_deterministically_by_information_and_quality(self):
        scores = [item["ranking_score"] for item in self.director_run["proposals"]]
        self.assertLessEqual(len(scores), 5)
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(self.director_run["recommendation"], "no_research_recommended")
        self.assertEqual(self.director_run["proposals"], [])
        self.assertFalse(self.director_run["model_preference_used"])

    def test_proposal_schema_and_real_evidence(self):
        schema = load_document(ROOT / "research/director/research-proposal.schema.json")
        jsonschema.Draft202012Validator(schema).validate(self.proposal)
        for item in self.proposal["supporting_evidence"]:
            self.assertTrue((ROOT / item["path"]).is_file(), item["path"])
        self.assertTrue(self.proposal["quality_checks"]["verifiable"])
        self.assertTrue(self.proposal["quality_checks"]["lower_risk_alternative_used"])

    def test_semantic_fingerprint_ignores_title_only_changes(self):
        renamed = copy.deepcopy(self.proposal)
        renamed["title"] = "Same question with a new title"
        self.assertEqual(proposal_fingerprint(self.proposal), proposal_fingerprint(renamed))

    def test_risk_classification_low_medium_high_forbidden(self):
        low = route_proposal(self.proposal, self.constitution)
        medium_proposal = copy.deepcopy(self.proposal)
        medium_proposal["risk_class"] = "medium"
        high_proposal = copy.deepcopy(self.proposal)
        high_proposal["risk_class"] = "high"
        forbidden_proposal = copy.deepcopy(self.proposal)
        forbidden_proposal["risk_class"] = "forbidden"
        self.assertEqual(low["decision"], "auto_approvable_future")
        self.assertEqual(route_proposal(medium_proposal, self.constitution)["decision"], "human_approval_required")
        self.assertEqual(route_proposal(high_proposal, self.constitution)["decision"], "human_approval_required")
        self.assertEqual(route_proposal(forbidden_proposal, self.constitution)["decision"], "forbidden")
        self.assertFalse(low["approval_granted"])

    def test_risk_terms_detect_requested_scope_not_prohibition_text(self):
        medium = copy.deepcopy(self.proposal)
        medium["allowed_changes"] = ["research/new_pair/**"]
        high = copy.deepcopy(self.proposal)
        high["allowed_changes"] = ["research/holdout/**"]
        forbidden = copy.deepcopy(self.proposal)
        forbidden["allowed_changes"] = ["private_api"]
        self.assertEqual(route_proposal(medium, self.constitution)["decision"], "human_approval_required")
        self.assertEqual(route_proposal(high, self.constitution)["decision"], "human_approval_required")
        self.assertEqual(route_proposal(forbidden, self.constitution)["decision"], "forbidden")

    def test_forbidden_proposal_cannot_compile(self):
        proposal = copy.deepcopy(self.proposal)
        proposal["risk_class"] = "forbidden"
        with self.assertRaisesRegex(ValueError, "forbidden proposal"):
            compile_campaign(ROOT, proposal, self.state, self.constitution)

    def test_compiler_freezes_inputs_budget_and_campaign_fingerprint(self):
        campaign, metadata, brief = compile_campaign(ROOT, self.proposal, self.state, self.constitution, {"max_experiments": 2, "max_wall_clock_minutes": 10})
        self.assertEqual(campaign["compile_mode"], "dry_run")
        self.assertFalse(campaign["execution_authorized"])
        self.assertEqual(campaign["budget"]["max_experiments"], 2)
        self.assertEqual(campaign["budget"]["max_wall_clock_minutes"], 10)
        self.assertEqual(campaign["frozen_inputs"]["strategy"]["sha256"], sha256_file(ROOT / "strategies/RegimeAwareV6.py"))
        self.assertEqual(len(campaign["campaign_fingerprint"]), 64)
        self.assertFalse(metadata["campaign_executed"])
        self.assertIn("Machine authority", brief)

    def test_compiled_campaign_has_complete_control_plane(self):
        required = {"scope", "frozen_inputs", "budget", "stop_conditions", "state_machine", "failure_taxonomy", "retry_policy", "artifact_requirements", "registry_events", "test_requirements", "acceptance_criteria", "human_escalation_conditions", "git_completion_requirements", "campaign_fingerprint"}
        self.assertTrue(required.issubset(self.campaign))
        self.assertIn("clean versioned worktree", self.campaign["git_completion_requirements"])
        self.assertIn("guard_violation", self.campaign["failure_taxonomy"])
        self.assertEqual(self.campaign["budget"]["max_validation_accesses"], 0)

    def test_dry_run_outputs_record_no_execution_or_candidate(self):
        self.assertFalse(self.campaign["execution_authorized"])
        self.assertFalse(self.campaign["approval_granted"])
        self.assertFalse(self.metadata["campaign_executed"])
        self.assertFalse(self.metadata["candidate_created"])
        self.assertFalse(self.state["stage4a_boundaries"]["backtest_run"])
        self.assertFalse(self.state["stage4a_boundaries"]["stage4b_started"])
        self.assertFalse(self.state["stage4a_boundaries"]["validation_accessed"])
        self.assertFalse(self.state["stage4a_boundaries"]["holdout_accessed"])

    def test_all_approval_routes_are_rule_by_rule_and_unapproved(self):
        for proposal in self.director_run["proposals"]:
            route = route_proposal(proposal, self.constitution)
            self.assertTrue(route["rule_decisions"])
            self.assertFalse(route["approval_granted"])
            self.assertFalse(route["stage4a_execution_authorized"])

    def test_registry_export_has_no_fake_execution_results(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "director.db"
            connection = open_director_registry(db)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            connection.close()
            exported = export_registry(str(db))
            self.assertEqual(exported["integrity"], "ok")
            self.assertFalse(exported["execution_results_recorded"])
            self.assertIn("compiled_campaigns", exported["tables"])


if __name__ == "__main__":
    unittest.main()
