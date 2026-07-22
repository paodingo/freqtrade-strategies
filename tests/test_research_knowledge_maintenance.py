import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import open_source_knowledge as knowledge  # noqa: E402
import research_knowledge_maintenance as maintenance  # noqa: E402
from research_director_common import load_document, open_director_registry, write_json  # noqa: E402


class ResearchKnowledgeMaintenanceTests(unittest.TestCase):
    def _remote_heads(self):
        return {spec["project_id"]: spec["commit_sha"] for spec in knowledge.SOURCE_SPECS}

    def test_refresh_only_proposes_changes_and_never_updates_automatically(self):
        heads = self._remote_heads()
        heads["qlib"] = "f" * 40
        heads["jesse"] = RuntimeError("network")
        report = maintenance.build_refresh_report(
            ROOT, heads, "2026-07-19T06:00:00+00:00"
        )
        by_project = {item["project_id"]: item for item in report["projects"]}

        self.assertEqual(report["summary"]["update_available"], 1)
        self.assertEqual(report["summary"]["check_failed"], 1)
        self.assertFalse(report["automatic_update_authorized"])
        self.assertEqual(by_project["qlib"]["status"], "update_available")
        self.assertTrue(by_project["qlib"]["human_approval_required"])
        self.assertIsNotNone(by_project["qlib"]["proposal_id"])
        self.assertEqual(by_project["jesse"]["license_status"], "asserted")
        self.assertEqual(report["summary"]["license_review_required"], 0)

    def test_lifecycle_and_update_registration_are_idempotent_and_human_gated(self):
        heads = self._remote_heads()
        heads["qlib"] = "f" * 40
        report = maintenance.build_refresh_report(
            ROOT, heads, "2026-07-19T06:00:00+00:00"
        )
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            first = maintenance.register_lifecycle_and_updates(ROOT, registry, report)
            second = maintenance.register_lifecycle_and_updates(ROOT, registry, report)
            connection = open_director_registry(registry)
            item_key = connection.execute(
                "SELECT item_key FROM research_knowledge_lifecycle WHERE item_type='pattern' ORDER BY item_key LIMIT 1"
            ).fetchone()[0]
            with self.assertRaisesRegex(ValueError, "human lifecycle approval"):
                maintenance.apply_lifecycle_decision(
                    connection,
                    item_key,
                    "deprecated",
                    {"reviewer_type": "agent", "decision": "approved", "decided_at": "2026-07-19T06:01:00+00:00"},
                )
            maintenance.apply_lifecycle_decision(
                connection,
                item_key,
                "deprecated",
                {
                    "reviewer_type": "human_user",
                    "decision": "approved",
                    "reason": "superseded research direction",
                    "decided_at": "2026-07-19T06:01:00+00:00",
                },
            )
            status = connection.execute(
                "SELECT lifecycle_status FROM research_knowledge_lifecycle WHERE item_key=?",
                (item_key,),
            ).fetchone()[0]
            connection.close()

        self.assertEqual(first, second)
        self.assertEqual(first["lifecycle"], 27)
        self.assertEqual(first["update_proposals"], 1)
        self.assertEqual(status, "deprecated")

    def test_fixed_retrieval_evaluation_meets_the_frozen_threshold(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        report = maintenance.evaluate_retrieval(ROOT, state)

        self.assertEqual(report["case_count"], 8)
        self.assertEqual(report["status"], "passed")
        self.assertGreaterEqual(report["hit_rate_at_4"], report["threshold"])
        self.assertTrue(all(item["hit"] for item in report["cases"]))

    def test_health_reports_attention_without_granting_execution(self):
        refresh = maintenance.build_refresh_report(
            ROOT, self._remote_heads(), "2026-07-19T06:00:00+00:00"
        )
        evaluation = maintenance.evaluate_retrieval(
            ROOT, load_document(ROOT / "research/director/current-research-state.json")
        )
        registry_export = {
            "tables": {
                "research_worker_jobs": [],
                "research_knowledge_lifecycle": [
                    {"item_key": "source:x", "item_type": "source", "lifecycle_status": "review_required"}
                ],
                "research_knowledge_update_proposals": [],
                "research_lesson_feedback_drafts": [
                    {"review_status": "pending_human_review"}
                ],
                "research_lesson_curation_candidates": [
                    {"status": "pending_human_promotion_review"}
                ],
            }
        }
        health = maintenance.build_health(
            ROOT,
            registry_export,
            refresh,
            evaluation,
            "2026-07-19T06:02:00+00:00",
        )

        self.assertEqual(health["status"], "attention_required")
        self.assertIn("source_license_review_required", health["warnings"])
        self.assertIn("lesson_promotion_review_pending", health["warnings"])
        self.assertIn("knowledge_broker_usage_not_observed", health["warnings"])
        self.assertEqual(health["metrics"]["lesson_curation_candidates_pending_promotion"], 1)
        self.assertEqual(health["knowledge_impact"]["status"], "no_observed_usage")
        self.assertFalse(health["execution_authorized"])
        self.assertEqual(health["failures"], [])

    def test_knowledge_impact_maps_retrieval_coverage_to_discovery_outcomes(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        impact = maintenance.build_knowledge_impact(ROOT, registry_export)

        self.assertEqual(impact["status"], "observed_usage")
        self.assertEqual(impact["observed_discovery_runs"], 4)
        self.assertEqual(impact["retrieval_binding_count"], 32)
        self.assertEqual(impact["pattern_usage"]["formal_count"], 12)
        self.assertEqual(impact["pattern_usage"]["retrieved_count"], 6)
        self.assertEqual(impact["lesson_usage"]["formal_count"], 9)
        self.assertEqual(impact["lesson_usage"]["retrieved_count"], 4)
        self.assertIn(
            "additional-pair-manifest-inventory-v1",
            {item["selected_idea_id"] for item in impact["run_outcomes"]},
        )
        chain = impact["influence_chain"]
        self.assertEqual(chain["observed_run_count"], 4)
        self.assertEqual(chain["retrieved_only_run_count"], 1)
        self.assertEqual(chain["critic_verified_run_count"], 3)
        self.assertEqual(chain["director_handoff_bound_run_count"], 3)
        self.assertEqual(chain["broken_chain_run_count"], 0)
        by_run = {item["run_id"]: item for item in chain["runs"]}
        self.assertEqual(
            by_run["discovery-run-045a763176bbbea2"]["classification"],
            "director_handoff_knowledge_bound",
        )
        self.assertEqual(
            by_run["discovery-run-b3939e7db2a82c12"]["classification"],
            "retrieved_only_no_idea_artifacts",
        )
        self.assertEqual(
            by_run["discovery-run-1ae473d06c0e5610"]["classification"],
            "director_handoff_knowledge_bound",
        )
        self.assertEqual(
            by_run["discovery-run-045a763176bbbea2"]["selected_idea_used_pattern_ids"],
            ["multi-symbol-timeframe-composition"],
        )
        self.assertFalse(impact["causal_performance_attribution_authorized"])
        self.assertFalse(impact["execution_authorized"])
        feedback_chain = impact["result_feedback_chain"]
        self.assertEqual(feedback_chain["director_bound_run_count"], 3)
        self.assertEqual(feedback_chain["proposal_bound_run_count"], 3)
        self.assertEqual(feedback_chain["analysis_completed_run_count"], 3)
        self.assertEqual(feedback_chain["registered_result_run_count"], 3)
        self.assertEqual(feedback_chain["feedback_draft_run_count"], 3)
        self.assertEqual(feedback_chain["legacy_unregistered_run_count"], 0)
        self.assertEqual(feedback_chain["execution_failed_run_count"], 0)
        self.assertEqual(feedback_chain["broken_chain_run_count"], 0)
        feedback_by_run = {item["run_id"]: item for item in feedback_chain["runs"]}
        self.assertEqual(
            feedback_by_run["discovery-run-66c83d41c84027eb"]["classification"],
            "analysis_feedback_pending_human_review",
        )
        self.assertEqual(
            feedback_by_run["discovery-run-66c83d41c84027eb"]["failed_worker_job_ids"],
            ["worker-job-6a281e2aa18ea659"],
        )
        self.assertTrue(all(
            all(artifact["exists"] and artifact["sha256"] for artifact in item["artifacts"])
            for item in feedback_chain["runs"]
        ))
        self.assertEqual(
            knowledge.semantic_fingerprint(impact, "impact_fingerprint"),
            impact["impact_fingerprint"],
        )

    def test_knowledge_impact_detects_an_idea_binding_break(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        broken = copy.deepcopy(registry_export)
        row = next(
            item
            for item in broken["tables"]["research_discovery_ideas"]
            if item["run_id"] == "discovery-run-045a763176bbbea2"
        )
        payload = json.loads(row["payload_json"])
        payload["knowledge_use"]["selection_fingerprint"] = "0" * 64
        row["payload_json"] = json.dumps(payload, sort_keys=True)

        impact = maintenance.build_knowledge_impact(ROOT, broken)
        self.assertEqual(impact["influence_chain"]["broken_chain_run_count"], 1)
        chain = next(
            item
            for item in impact["influence_chain"]["runs"]
            if item["run_id"] == "discovery-run-045a763176bbbea2"
        )
        self.assertEqual(chain["classification"], "broken_knowledge_chain")
        self.assertTrue(
            any(issue.startswith("idea_knowledge_binding_invalid:") for issue in chain["issues"])
        )
        health = maintenance.build_health(
            ROOT,
            broken,
            load_document(ROOT / "reports/audits/open-source-learning-v1/source-refresh-report.json"),
            load_document(ROOT / "reports/audits/open-source-learning-v1/retrieval-evaluation.json"),
            "2026-07-21T07:10:00Z",
        )
        self.assertEqual(health["status"], "failed")
        self.assertIn("knowledge_influence_chain_broken", health["failures"])

    def test_result_feedback_chain_detects_director_proposal_binding_break(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        broken = copy.deepcopy(registry_export)
        row = next(
            item
            for item in broken["tables"]["director_proposals"]
            if item["proposal_id"] == "discovery-bnb-xrp-distribution-shift-profile-v1-v1"
        )
        payload = json.loads(row["payload_json"])
        payload["knowledge_selection_fingerprint"] = "0" * 64
        row["payload_json"] = json.dumps(payload, sort_keys=True)

        impact = maintenance.build_knowledge_impact(ROOT, broken)
        feedback_chain = impact["result_feedback_chain"]
        self.assertEqual(feedback_chain["broken_chain_run_count"], 1)
        chain = next(
            item
            for item in feedback_chain["runs"]
            if item["run_id"] == "discovery-run-1ae473d06c0e5610"
        )
        self.assertEqual(chain["classification"], "broken_result_feedback_chain")
        self.assertIn("director_proposal_knowledge_binding_invalid", chain["issues"])
        health = maintenance.build_health(
            ROOT,
            broken,
            load_document(ROOT / "reports/audits/open-source-learning-v1/source-refresh-report.json"),
            load_document(ROOT / "reports/audits/open-source-learning-v1/retrieval-evaluation.json"),
            "2026-07-21T07:20:00Z",
        )
        self.assertEqual(health["status"], "failed")
        self.assertIn("knowledge_result_feedback_chain_broken", health["failures"])

    def test_impact_refresh_is_idle_until_broker_usage_changes(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            context_target = repo / "research/knowledge/open-source-v1/current-context.json"
            context_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                ROOT / "research/knowledge/open-source-v1/current-context.json",
                context_target,
            )
            shutil.copytree(
                ROOT / "research/knowledge/schemas",
                repo / "research/knowledge/schemas",
            )
            for name in (
                "source-refresh-report.json",
                "retrieval-evaluation.json",
            ):
                target = repo / "reports/audits/open-source-learning-v1" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / "reports/audits/open-source-learning-v1" / name, target)
            health_path = repo / "reports/audits/open-source-learning-v1/learning-loop-health.json"
            write_json(
                health_path,
                maintenance.build_health(
                    repo,
                    registry_export,
                    load_document(repo / "reports/audits/open-source-learning-v1/source-refresh-report.json"),
                    load_document(repo / "reports/audits/open-source-learning-v1/retrieval-evaluation.json"),
                    "2026-07-21T06:59:00Z",
                ),
            )
            before = health_path.read_bytes()
            idle = maintenance.refresh_knowledge_impact(
                repo, registry_export, "2026-07-21T07:00:00Z"
            )
            self.assertEqual(idle["status"], "idle")
            self.assertFalse(idle["report_modified"])
            self.assertEqual(health_path.read_bytes(), before)

            changed_export = copy.deepcopy(registry_export)
            snapshot = load_document(context_target)["knowledge_snapshot_fingerprint"]
            changed_export["tables"]["open_source_knowledge_lineage"].append({
                "lineage_id": "temporary-impact-lineage",
                "source_type": "strategy_pattern",
                "source_id": "causal-indicator-validation",
                "relation": "retrieved_for",
                "target_type": "discovery_run",
                "target_id": "discovery-run-impact-refresh-test",
                "payload_json": json.dumps({
                    "knowledge_snapshot_fingerprint": snapshot,
                    "score": 1,
                    "matched_mechanism_keys": ["causal-signals"],
                }),
                "created_at": "2026-07-21T07:00:00Z",
            })
            updated = maintenance.refresh_knowledge_impact(
                repo, changed_export, "2026-07-21T07:00:00Z"
            )
            self.assertEqual(updated["status"], "knowledge_impact_updated")
            self.assertTrue(updated["report_modified"])
            self.assertNotEqual(health_path.read_bytes(), before)
            refreshed = load_document(health_path)
            self.assertEqual(refreshed["knowledge_impact"]["observed_discovery_runs"], 5)
            self.assertEqual(refreshed["knowledge_impact"]["pattern_usage"]["retrieved_count"], 7)


if __name__ == "__main__":
    unittest.main()
