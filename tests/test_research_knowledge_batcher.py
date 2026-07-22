from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_director_registry as registry_exporter  # noqa: E402
import research_knowledge_batcher as batcher  # noqa: E402
from research_director_common import open_director_registry  # noqa: E402


class ResearchKnowledgeBatcherTests(unittest.TestCase):
    def _policy(self, count_threshold: int = 5, max_wait_hours: int = 168) -> dict:
        policy = {
            "schema_version": "knowledge-review-batch-policy-v1",
            "policy_id": "development-knowledge-review-batch-policy-v1",
            "status": "active",
            "count_threshold": count_threshold,
            "max_wait_hours": max_wait_hours,
            "included_review_types": ["source_update", "lesson_feedback", "license_review"],
            "output_root": "reports/audits/open-source-learning-v1/review-batches/aggregated",
            "idle_behavior": "silent_no_write",
            "triggered_behavior": "immutable_human_review_handoff",
            "advisory_drafting_authorized": True,
            "automatic_decision_authorized": False,
            "automatic_application_authorized": False,
            "automatic_lesson_promotion_authorized": False,
            "execution_authorized": False,
        }
        policy["policy_fingerprint"] = batcher.knowledge.semantic_fingerprint(policy, "policy_fingerprint")
        return policy

    def _seed_feedback(self, registry: Path, count: int, created_at: str, start: int = 0) -> None:
        connection = open_director_registry(registry)
        try:
            for index in range(start, start + count):
                connection.execute(
                    "INSERT INTO research_lesson_feedback_drafts VALUES(?,?,?,?,?,?,?,?)",
                    (
                        f"feedback-{index}", f"run-{index}", f"campaign-{index}", f"proposal-{index}",
                        "negative", "pending_human_review", "{}", created_at,
                    ),
                )
            connection.commit()
        finally:
            connection.close()

    def test_below_both_thresholds_is_silent_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            registry = repo / "director.db"
            self._seed_feedback(registry, 4, "2026-07-20T00:00:00+00:00")
            result = batcher.build_batch(
                ROOT,
                registry_exporter.export_registry(str(registry)),
                self._policy(),
                "2026-07-20T01:00:00+00:00",
            )
            batcher.publish_batch(repo, result)
            self.assertFalse((repo / "reports").exists())
        self.assertEqual(result["status"], "idle")
        self.assertFalse(result["notification_required"])
        self.assertEqual(result["count_threshold_remaining"], 1)
        self.assertEqual(
            result["next_age_trigger_at"], "2026-07-27T00:00:00+00:00"
        )
        self.assertEqual(result["remaining_wait_hours"], 167.0)

    def test_idle_schedule_normalizes_timezone_and_preserves_zero_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            registry = repo / "director.db"
            self._seed_feedback(registry, 1, "2026-07-20T08:00:00+08:00")
            result = batcher.build_batch(
                ROOT,
                registry_exporter.export_registry(str(registry)),
                self._policy(),
                "2026-07-20T12:00:00+08:00",
            )
            batcher.publish_batch(repo, result)
            self.assertFalse((repo / "reports").exists())
        self.assertEqual(result["oldest_pending_at"], "2026-07-20T00:00:00+00:00")
        self.assertEqual(result["next_age_trigger_at"], "2026-07-27T00:00:00+00:00")
        self.assertEqual(result["remaining_wait_hours"], 164.0)
        self.assertEqual(result["count_threshold_remaining"], 4)

    def test_count_threshold_creates_an_immutable_human_only_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            registry = repo / "director.db"
            self._seed_feedback(registry, 5, "2026-07-20T00:00:00Z")
            export = registry_exporter.export_registry(str(registry))
            result = batcher.build_batch(ROOT, export, self._policy(), "2026-07-20T01:00:00Z")
            first_publish = batcher.publish_batch(repo, result)
            replay = batcher.build_batch(ROOT, export, self._policy(), "2026-07-21T01:00:00Z")
            replay_publish = batcher.publish_batch(repo, replay)
            packet_path, handoff_path = [repo / item for item in result["artifacts_written"]]
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "batch_ready")
        self.assertTrue(first_publish)
        self.assertFalse(replay_publish)
        replay_status = batcher.public_result(replay, replay_publish)
        self.assertEqual(replay_status["status"], "awaiting_human_review")
        self.assertFalse(replay_status["notification_required"])
        self.assertEqual(replay_status["artifacts_written"], [])
        self.assertEqual(result["trigger_reason"], "count_threshold")
        self.assertEqual(result["batch_id"], replay["batch_id"])
        self.assertEqual(packet["counts"]["total"], 5)
        self.assertTrue(handoff["human_decision_required"])
        self.assertFalse(handoff["automatic_decision_authorized"])
        self.assertFalse(handoff["automatic_application_authorized"])
        self.assertFalse(handoff["automatic_lesson_promotion_authorized"])
        self.assertFalse(handoff["execution_authorized"])
        self.assertEqual(
            handoff["planned_advisory_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/recommendations.json",
        )
        self.assertEqual(
            handoff["planned_human_intent_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/human-intent.json",
        )
        self.assertEqual(
            handoff["planned_approval_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/batch-approval.json",
        )
        self.assertEqual(
            handoff["planned_review_events_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/review-events.json",
        )
        self.assertEqual(
            handoff["planned_post_approval_plan_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/post-approval-plan.json",
        )
        self.assertEqual(
            handoff["planned_curation_draft_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/curation-draft-packet.json",
        )
        self.assertEqual(
            handoff["planned_curation_candidate_root"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/lesson-candidates",
        )
        self.assertEqual(
            handoff["planned_promotion_review_packet_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/promotion-review-packet.json",
        )
        self.assertEqual(
            handoff["planned_promotion_base_context_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/promotion-base-context.json",
        )
        self.assertEqual(
            handoff["planned_promotion_base_manifest_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/promotion-base-manifest.json",
        )
        self.assertEqual(
            handoff["planned_promotion_human_intent_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/promotion-human-intent.json",
        )
        self.assertEqual(
            handoff["planned_promotion_approval_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/promotion-approval.json",
        )
        self.assertEqual(
            handoff["planned_promotion_events_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/promotion-events.json",
        )
        self.assertEqual(
            handoff["planned_published_manifest_path"],
            f"reports/audits/open-source-learning-v1/review-batches/aggregated/{result['batch_id']}/published-knowledge-manifest.json",
        )

    def test_age_threshold_triggers_a_single_old_item(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            created = datetime(2026, 7, 1, tzinfo=timezone.utc)
            self._seed_feedback(registry, 1, created.isoformat())
            result = batcher.build_batch(
                ROOT,
                registry_exporter.export_registry(str(registry)),
                self._policy(),
                (created + timedelta(hours=168)).isoformat(),
            )
        self.assertEqual(result["status"], "batch_ready")
        self.assertEqual(result["trigger_reason"], "max_wait_threshold")

    def test_changed_pending_set_gets_a_new_batch_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed_feedback(registry, 5, "2026-07-20T00:00:00Z")
            first = batcher.build_batch(
                ROOT, registry_exporter.export_registry(str(registry)), self._policy(), "2026-07-20T01:00:00Z"
            )
            self._seed_feedback(registry, 1, "2026-07-20T02:00:00Z", start=5)
            second = batcher.build_batch(
                ROOT, registry_exporter.export_registry(str(registry)), self._policy(), "2026-07-20T03:00:00Z"
            )
        self.assertNotEqual(first["batch_id"], second["batch_id"])


if __name__ == "__main__":
    unittest.main()
