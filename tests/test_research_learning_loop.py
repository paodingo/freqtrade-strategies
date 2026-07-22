import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import open_source_knowledge as knowledge  # noqa: E402
import research_discovery_review as review  # noqa: E402
import research_discovery_trigger as trigger_support  # noqa: E402
import research_lesson_feedback as feedback  # noqa: E402
import research_director  # noqa: E402
import research_worker_queue as worker_queue  # noqa: E402
from research_director_common import load_document, open_director_registry  # noqa: E402
from research_discovery_common import DiscoveryError  # noqa: E402


class ResearchLearningLoopTests(unittest.TestCase):
    def setUp(self):
        self.state = load_document(ROOT / "research/director/current-research-state.json")
        constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        policy = load_document(ROOT / "research/discovery/policy/source-policy.yaml")
        self.trigger = trigger_support.create_trigger(
            "manual_request",
            "confirmed-higher-low",
            self.state,
            constitution,
            policy,
            created_at="2026-07-19T13:00:00+08:00",
        )
        self.selection = knowledge.broker_selection(
            ROOT,
            "manual_request",
            "confirmed-higher-low",
            self.trigger["trigger_fingerprint"],
            self.state,
        )
        self.context = {
            "repo": ROOT,
            "trigger": self.trigger,
            "state": self.state,
            "allowed_sources": set(trigger_support._allowed_source_paths(ROOT, self.state, policy)),
        }

    def _idea(self):
        idea = load_document(
            ROOT / "tests/fixtures/research-discovery/ideas/mean-reversion-v1.json"
        )
        idea["research_state_fingerprint"] = self.trigger["research_state_fingerprint"]
        idea["required_datasets"] = [
            "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
            "futures-dev-eth-usdt-usdt-20240101-20240830-v1",
        ]
        lesson_ids = [item["lesson_id"] for item in self.selection["selected_lessons"]]
        idea["knowledge_use"] = {
            "selection_id": self.selection["selection_id"],
            "selection_fingerprint": self.selection["selection_fingerprint"],
            "used_pattern_ids": [self.selection["selected_patterns"][0]["pattern_id"]],
            "considered_lesson_ids": lesson_ids,
            "material_difference_from_lessons": [
                {
                    "lesson_id": lesson_id,
                    "explanation": "The proposed mechanism is materially distinct and will retain the cited stop condition.",
                }
                for lesson_id in lesson_ids
            ],
            "rationale": "The selected mechanism is relevant while all negative lessons constrain duplication.",
        }
        return idea

    def test_broker_enabled_idea_requires_exact_selection_and_all_lessons(self):
        validated = review._validate_idea_payload(self.context, self._idea())
        self.assertEqual(
            validated["knowledge_use"]["selection_fingerprint"],
            self.selection["selection_fingerprint"],
        )

        missing = self._idea()
        missing.pop("knowledge_use")
        with self.assertRaisesRegex(DiscoveryError, "knowledge_binding_missing"):
            review._validate_idea_payload(self.context, missing)

        incomplete = self._idea()
        incomplete["knowledge_use"]["considered_lesson_ids"].pop()
        with self.assertRaisesRegex(DiscoveryError, "knowledge_lesson_coverage_incomplete"):
            review._validate_idea_payload(self.context, incomplete)

    def test_critic_verifies_binding_and_cannot_pass_semantic_duplicate(self):
        idea = review._validate_idea_payload(self.context, self._idea())
        critique = load_document(
            ROOT / "tests/fixtures/research-discovery/critiques/mean-reversion-v1.json"
        )
        critique["idea_semantic_fingerprint"] = idea["semantic_fingerprint"]
        lesson_ids = idea["knowledge_use"]["considered_lesson_ids"]
        critique["knowledge_verification"] = {
            "selection_id": self.selection["selection_id"],
            "selection_fingerprint": self.selection["selection_fingerprint"],
            "idea_knowledge_use_verified": True,
            "lesson_checks": [
                {"lesson_id": lesson_id, "result": "confirmed_distinct"}
                for lesson_id in lesson_ids
            ],
            "status": "verified",
            "notes": "All selected lessons were checked against the immutable idea.",
        }
        validated = review._validate_critique_payload(self.context, critique, idea)
        self.assertEqual(validated["knowledge_verification"]["status"], "verified")
        self.assertEqual(
            research_director._require_knowledge_verification(idea, validated),
            idea["knowledge_use"],
        )

        duplicate = dict(critique)
        duplicate["knowledge_verification"] = dict(critique["knowledge_verification"])
        duplicate["knowledge_verification"]["lesson_checks"] = [
            dict(item) for item in critique["knowledge_verification"]["lesson_checks"]
        ]
        duplicate["knowledge_verification"]["lesson_checks"][0]["result"] = "semantic_duplicate"
        duplicate["knowledge_verification"]["status"] = "semantic_duplicate"
        with self.assertRaisesRegex(DiscoveryError, "critic_knowledge_pass_forbidden"):
            review._validate_critique_payload(self.context, duplicate, idea)
        with self.assertRaisesRegex(DiscoveryError, "director_knowledge_verification_required"):
            research_director._require_knowledge_verification(idea, duplicate)

    def test_worker_queue_is_idempotent_lease_based_and_provider_neutral(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            connection = open_director_registry(registry)
            first = worker_queue.enqueue_worker_job(
                connection,
                run_id="run-1",
                stage="researcher",
                round_number=1,
                task_path="research/discovery/runs/run-1/researcher-task.md",
                inbox_path=str(Path(temporary) / "inbox"),
                created_at="2026-07-19T05:00:00+00:00",
            )
            second = worker_queue.enqueue_worker_job(
                connection,
                run_id="run-1",
                stage="researcher",
                round_number=1,
                task_path="research/discovery/runs/run-1/researcher-task.md",
                inbox_path=str(Path(temporary) / "inbox"),
                created_at="2026-07-19T05:00:00+00:00",
            )
            connection.commit()
            connection.close()

            claimed = worker_queue.claim_next_job(
                registry,
                "worker-a",
                lease_seconds=60,
                now="2026-07-19T05:00:01+00:00",
            )
            finished = worker_queue.finish_job(
                registry,
                claimed["job_id"],
                "worker-a",
                "completed",
                updated_at="2026-07-19T05:00:02+00:00",
            )

        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(claimed["attempt_count"], 1)
        self.assertTrue(json.loads(claimed["payload_json"])["provider_neutral"])
        self.assertEqual(finished["status"], "completed")
        self.assertIsNone(finished["lease_owner"])

    def test_worker_queue_can_atomically_defer_an_untouched_discovery_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            connection = open_director_registry(registry)
            run_payload = {
                "run_id": "run-defer",
                "status": "awaiting_researcher",
            }
            connection.execute(
                "INSERT INTO research_discovery_runs("
                "run_id,trigger_fingerprint,status,state_fingerprint,payload_json,created_at"
                ") VALUES(?,?,?,?,?,?)",
                (
                    "run-defer",
                    "trigger-defer",
                    "awaiting_researcher",
                    "state-defer",
                    json.dumps(run_payload, sort_keys=True),
                    "2026-07-20T10:00:00+00:00",
                ),
            )
            worker_queue.enqueue_worker_job(
                connection,
                run_id="run-defer",
                stage="researcher",
                round_number=1,
                task_path="research/discovery/runs/run-defer/researcher-task.md",
                inbox_path=str(Path(temporary) / "inbox"),
                created_at="2026-07-20T10:00:00+00:00",
            )
            connection.commit()
            connection.close()

            first = worker_queue.defer_run_before_research(
                registry,
                "run-defer",
                "pair_scope_superseded",
                "治理范围更新后重新触发。",
                updated_at="2026-07-20T10:01:00+00:00",
            )
            replay = worker_queue.defer_run_before_research(
                registry,
                "run-defer",
                "pair_scope_superseded",
                "治理范围更新后重新触发。",
                updated_at="2026-07-20T10:02:00+00:00",
            )
            claimed = worker_queue.claim_next_job(
                registry,
                "worker-a",
                now="2026-07-20T10:03:00+00:00",
            )
            connection = open_director_registry(registry)
            run_status = connection.execute(
                "SELECT status FROM research_discovery_runs WHERE run_id='run-defer'"
            ).fetchone()[0]
            job_status = connection.execute(
                "SELECT status FROM research_worker_jobs WHERE run_id='run-defer'"
            ).fetchone()[0]
            event_count = connection.execute(
                "SELECT COUNT(*) FROM research_discovery_events "
                "WHERE run_id='run-defer' AND event_type='pre_research_deferred'"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(first, replay)
        self.assertEqual(run_status, "deferred")
        self.assertEqual(job_status, "deferred")
        self.assertEqual(event_count, 1)
        self.assertIsNone(claimed)

    def test_completed_campaign_automatically_creates_review_only_lesson_draft(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            connection = open_director_registry(registry)
            connection.execute(
                "INSERT INTO research_campaign_runs("
                "run_id,campaign_id,proposal_id,status,result_code,campaign_executed,"
                "candidate_created,strategy_modified,validation_accesses,holdout_accesses,"
                "payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "campaign-run-1",
                    "campaign-1",
                    "proposal-1",
                    "completed",
                    "rejected_degradation",
                    1,
                    0,
                    0,
                    0,
                    0,
                    json.dumps({"classification": "rejected_degradation"}),
                    "2026-07-19T05:00:00+00:00",
                ),
            )
            connection.execute(
                "INSERT INTO research_campaign_assets(asset_id,run_id,artifact_type,path,sha256,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (
                    "asset-1",
                    "campaign-run-1",
                    "campaign_evidence",
                    "reports/audits/example.json",
                    "a" * 64,
                    "2026-07-19T05:00:00+00:00",
                ),
            )
            connection.commit()
            queued = connection.execute(
                "SELECT COUNT(*) FROM research_lesson_feedback_drafts"
            ).fetchone()[0]
            connection.close()
            drafts = feedback.pending_feedback_drafts(ROOT, registry)

        self.assertEqual(queued, 1)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["outcome_class"], "negative")
        self.assertFalse(drafts[0]["automatic_promotion_authorized"])
        self.assertFalse(drafts[0]["candidate_creation_authorized"])
        self.assertEqual(drafts[0]["evidence_paths"], ["reports/audits/example.json"])

    def test_authoritative_registry_export_preserves_reviewed_and_pending_historical_feedback(self):
        export_path = ROOT / "research/director/registry-records.json"
        registry_export = load_document(export_path)
        drafts = feedback.pending_feedback_drafts_from_export(ROOT, export_path)

        rows = registry_export["tables"]["research_lesson_feedback_drafts"]
        self.assertEqual(len(rows), registry_export["counts"]["research_lesson_feedback_drafts"])
        self.assertEqual(len(rows), 14)
        self.assertEqual(len(drafts), 1)
        self.assertEqual(sum(row["review_status"] == "approved_for_manual_curation" for row in rows), 11)
        self.assertEqual(sum(row["review_status"] == "rejected" for row in rows), 2)
        self.assertEqual(sum(row["review_status"] == "pending_human_review" for row in rows), 1)
        self.assertEqual(
            sum(
                draft["source_kind"] == "historical_manual_descriptive_analysis"
                for draft in drafts
            ),
            0,
        )
        self.assertEqual(
            sum(draft["source_kind"] == "descriptive_execution" for draft in drafts),
            1,
        )


if __name__ == "__main__":
    unittest.main()
