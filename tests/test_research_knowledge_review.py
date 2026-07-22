from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_director_registry as registry_exporter  # noqa: E402
import research_knowledge_review as review  # noqa: E402
from research_director_common import open_director_registry  # noqa: E402


class ResearchKnowledgeReviewTests(unittest.TestCase):
    def _seed_registry(self, path: Path) -> None:
        connection = open_director_registry(path)
        try:
            connection.execute(
                "INSERT INTO research_knowledge_update_proposals VALUES(?,?,?,?,?,?,?)",
                ("update-1", "qlib", "a" * 40, "b" * 40, "pending_human_approval", "{}", "2026-07-19T00:00:00Z"),
            )
            connection.execute(
                "INSERT INTO research_lesson_feedback_drafts VALUES(?,?,?,?,?,?,?,?)",
                ("feedback-1", "run-1", "campaign-1", "proposal-1", "negative", "pending_human_review", "{}", "2026-07-19T00:00:00Z"),
            )
            connection.execute(
                "INSERT INTO research_knowledge_lifecycle VALUES(?,?,?,?,?,?,?,?,?)",
                ("source:jesse@abc", "source", "jesse-snapshot", "c" * 64, "review_required", None, "license", "{}", "2026-07-19T00:00:00Z"),
            )
            connection.commit()
        finally:
            connection.close()

    def _intent(self, packet: dict, review_type: str, target_id: str, decision: str = "approved") -> dict:
        return {
            "review_type": review_type,
            "target_id": target_id,
            "decision": decision,
            "reviewer_type": "human_user",
            "reviewer_id": "test-human",
            "reason": "explicit test review",
            "decided_at": "2026-07-19T01:00:00Z",
            "source_packet_fingerprint": packet["packet_fingerprint"],
        }

    def test_packet_unifies_all_pending_review_types_without_execution_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed_registry(registry)
            payload = registry_exporter.export_registry(str(registry))
            packet = review.build_review_packet(ROOT, payload, "2026-07-19T00:30:00Z")

        self.assertEqual(packet["counts"], {"source_updates": 1, "lesson_feedback": 1, "license_reviews": 1, "total": 3})
        self.assertFalse(packet["execution_authorized"])
        self.assertTrue(all(not item["automatic_application_authorized"] for item in packet["items"]))

    def test_explicit_human_decisions_are_audited_but_only_reach_manual_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed_registry(registry)
            packet = review.build_review_packet(
                ROOT, registry_exporter.export_registry(str(registry)), "2026-07-19T00:30:00Z"
            )
            events = [
                review.build_review_event(ROOT, packet, self._intent(packet, "source_update", "update-1")),
                review.build_review_event(ROOT, packet, self._intent(packet, "lesson_feedback", "feedback-1")),
                review.build_review_event(ROOT, packet, self._intent(packet, "license_review", "source:jesse@abc")),
            ]
            for event in events:
                review.apply_review_event(registry, event)
                review.apply_review_event(registry, event)
            connection = sqlite3.connect(registry)
            try:
                self.assertEqual(connection.execute("SELECT status FROM research_knowledge_update_proposals").fetchone()[0], "approved_for_manual_rebuild")
                self.assertEqual(connection.execute("SELECT review_status FROM research_lesson_feedback_drafts").fetchone()[0], "approved_for_manual_curation")
                self.assertEqual(connection.execute("SELECT lifecycle_status FROM research_knowledge_lifecycle").fetchone()[0], "active_pinned")
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM research_knowledge_review_events").fetchone()[0], 3)
            finally:
                connection.close()
        self.assertTrue(all(not event["automatic_source_update_authorized"] for event in events))
        self.assertTrue(all(not event["automatic_lesson_promotion_authorized"] for event in events))

    def test_non_human_or_stale_packet_decision_is_rejected(self):
        packet = {
            "packet_fingerprint": "a" * 64,
            "items": [{"review_type": "source_update", "target_id": "update-1"}],
        }
        intent = self._intent(packet, "source_update", "update-1")
        intent["reviewer_type"] = "agent"
        with self.assertRaisesRegex(ValueError, "explicit human"):
            review.build_review_event(ROOT, packet, intent)
        intent["reviewer_type"] = "human_user"
        intent["source_packet_fingerprint"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            review.build_review_event(ROOT, packet, intent)

    def test_advisory_batch_is_count_bound_and_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed_registry(registry)
            packet = review.build_review_packet(
                ROOT, registry_exporter.export_registry(str(registry)), "2026-07-19T00:30:00Z"
            )
            recommendations = []
            for index, item in enumerate(packet["items"]):
                recommendations.append({
                    "review_key": item["review_key"],
                    "review_type": item["review_type"],
                    "target_id": item["target_id"],
                    "recommended_decision": "rejected" if index == 0 else "approved",
                    "confidence": "high",
                    "disposition": "keep_current_pin" if item["review_type"] == "source_update" else "curate_standalone",
                    "rationale": "test recommendation",
                    "references": ["test:evidence"],
                    "constraints": ["no automatic action"],
                })
            advisory = {
                "schema_version": "knowledge-review-recommendations-v1",
                "advisory_id": "test-advisory",
                "generated_at": "2026-07-19T00:40:00Z",
                "packet_fingerprint": packet["packet_fingerprint"],
                "recommendations": recommendations,
                "summary": {"approved": 2, "rejected": 1, "total": 3},
                "human_decision_required": True,
                "automatic_application_authorized": False,
                "execution_authorized": False,
            }
            advisory["advisory_fingerprint"] = review.knowledge.semantic_fingerprint(advisory, "advisory_fingerprint")
            approval = {
                "schema_version": "knowledge-review-batch-approval-v1",
                "approval_id": "test-approval",
                "reviewer_type": "human_user",
                "reviewer_id": "test-human",
                "decision": "approve_recommendations",
                "statement": "approve test advisory",
                "decided_at": "2026-07-19T01:00:00Z",
                "packet_fingerprint": packet["packet_fingerprint"],
                "advisory_fingerprint": advisory["advisory_fingerprint"],
                "approved_count": 2,
                "rejected_count": 1,
                "automatic_source_update_authorized": False,
                "automatic_lesson_promotion_authorized": False,
                "execution_authorized": False,
            }
            approval["approval_fingerprint"] = review.knowledge.semantic_fingerprint(approval, "approval_fingerprint")
            events = review.apply_advisory_batch(ROOT, registry, packet, advisory, approval)
            replay = review.apply_advisory_batch(ROOT, registry, packet, advisory, approval)
            connection = sqlite3.connect(registry)
            try:
                event_count = connection.execute("SELECT COUNT(*) FROM research_knowledge_review_events").fetchone()[0]
            finally:
                connection.close()
        self.assertEqual(len(events), 3)
        self.assertEqual(events, replay)
        self.assertEqual(event_count, 3)

    def test_authoritative_export_preserves_reviewed_feedback_status(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "director.db"
            self._seed_registry(registry)
            local = registry_exporter.export_registry(str(registry))
            local["tables"]["research_lesson_feedback_drafts"][0]["review_status"] = "approved_for_manual_curation"
            base = json.loads(json.dumps(local))
            base["tables"]["research_campaign_runs"] = [{
                "run_id": "run-1", "campaign_id": "campaign-1", "proposal_id": "proposal-1",
                "status": "completed", "result_code": "negative", "payload_json": "{}",
                "completed_at": "2026-07-19T00:00:00Z"
            }]
            merged = registry_exporter.merge_knowledge_tables(base, local)
            merged_status = merged["tables"]["research_lesson_feedback_drafts"][0]["review_status"]

            second_registry = Path(directory) / "review.db"
            review.sync_feedback_backlog(second_registry, merged)
            connection = sqlite3.connect(second_registry)
            try:
                connection.execute(
                    "UPDATE research_lesson_feedback_drafts SET review_status='rejected' WHERE feedback_id='feedback-1'"
                )
                connection.commit()
            finally:
                connection.close()
            merged["tables"]["research_lesson_feedback_drafts"][0]["review_status"] = "pending_human_review"
            review.sync_feedback_backlog(second_registry, merged)
            connection = sqlite3.connect(second_registry)
            try:
                synced_status = connection.execute(
                    "SELECT review_status FROM research_lesson_feedback_drafts WHERE feedback_id='feedback-1'"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(
            merged_status,
            "approved_for_manual_curation",
        )
        self.assertEqual(synced_status, "rejected")


if __name__ == "__main__":
    unittest.main()
