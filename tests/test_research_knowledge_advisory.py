from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import research_knowledge_advisory as advisory  # noqa: E402
import open_source_knowledge as knowledge  # noqa: E402
from research_director_common import load_document  # noqa: E402


class ResearchKnowledgeAdvisoryTests(unittest.TestCase):
    def setUp(self):
        self.packet = load_document(ROOT / "reports/audits/open-source-learning-v1/pending-review-packet.json")
        self.advisory = load_document(ROOT / "reports/audits/open-source-learning-v1/review-recommendations.json")
        archive = ROOT / "reports/audits/open-source-learning-v1/review-batches/open-source-learning-v1-review-batch-20260719"
        self.archived_packet = load_document(archive / "packet.json")
        self.archived_advisory = load_document(archive / "recommendations.json")

    def test_recommendations_cover_packet_exactly_without_decision_authority(self):
        summary = advisory.validate_advisory(ROOT, self.packet, self.advisory)
        self.assertEqual(summary, {"approved": 1, "rejected": 0, "total": 1})
        self.assertTrue(self.advisory["human_decision_required"])
        self.assertFalse(self.advisory["automatic_application_authorized"])
        self.assertFalse(self.advisory["execution_authorized"])
        self.assertEqual(
            advisory.validate_advisory(ROOT, self.archived_packet, self.archived_advisory),
            {"approved": 8, "rejected": 3, "total": 11},
        )

    def test_invalidated_attempt_is_rejected_and_recertified_attempt_is_approved(self):
        recommendations = {item["target_id"]: item for item in self.archived_advisory["recommendations"]}
        self.assertEqual(recommendations["regime-conditioned-branch-factorization-v1-recertification-attempt-2"]["recommended_decision"], "rejected")
        self.assertEqual(recommendations["regime-conditioned-branch-factorization-v1-recertification-attempt-3"]["recommended_decision"], "approved")

    def test_stale_or_incomplete_advisory_fails_closed(self):
        stale = copy.deepcopy(self.archived_advisory)
        stale["packet_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "packet fingerprint mismatch"):
            advisory.validate_advisory(ROOT, self.archived_packet, stale)
        incomplete = copy.deepcopy(self.archived_advisory)
        incomplete["recommendations"].pop()
        with self.assertRaisesRegex(ValueError, "cover each pending"):
            advisory.validate_advisory(ROOT, self.archived_packet, incomplete)

    def _strict_fixture(self, reference: str) -> tuple[dict, dict]:
        packet = {
            "schema_version": "knowledge-review-packet-v1",
            "generated_at": "2026-07-20T00:00:00+00:00",
            "items": [{
                "review_key": "lesson_feedback:feedback-1",
                "review_type": "lesson_feedback",
                "target_id": "feedback-1",
                "current_status": "pending_human_review",
                "summary": "test feedback",
                "evidence": ["tests/test_research_knowledge_advisory.py"],
                "allowed_decisions": ["approved", "rejected"],
                "automatic_application_authorized": False,
            }],
            "counts": {"source_updates": 0, "lesson_feedback": 1, "license_reviews": 0, "total": 1},
            "decision_contract": {
                "approval_schema": "research/knowledge/schemas/knowledge-review-event.schema.json",
                "reviewer_type": "human_user",
                "approved_source_update_result": "approved_for_manual_rebuild",
                "approved_lesson_feedback_result": "approved_for_manual_curation",
                "automatic_promotion_authorized": False,
            },
            "execution_authorized": False,
        }
        packet["packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "packet_fingerprint")
        recommendation = {
            "review_key": "lesson_feedback:feedback-1",
            "review_type": "lesson_feedback",
            "target_id": "feedback-1",
            "recommended_decision": "rejected",
            "confidence": "medium",
            "disposition": "reject_invalidated",
            "rationale": "local evidence does not support promotion",
            "references": [reference],
            "constraints": ["human approval required"],
        }
        payload = {
            "schema_version": "knowledge-review-recommendations-v1",
            "advisory_id": f"knowledge-review-advisory-{packet['packet_fingerprint'][:16]}",
            "generated_at": packet["generated_at"],
            "packet_fingerprint": packet["packet_fingerprint"],
            "recommendations": [recommendation],
            "summary": {"approved": 0, "rejected": 1, "total": 1},
            "human_decision_required": True,
            "automatic_application_authorized": False,
            "execution_authorized": False,
        }
        payload["advisory_fingerprint"] = knowledge.semantic_fingerprint(payload, "advisory_fingerprint")
        return packet, payload

    def test_aggregated_advisory_accepts_only_packet_bound_local_evidence(self):
        packet, payload = self._strict_fixture("tests/test_research_knowledge_advisory.py")
        self.assertEqual(
            advisory.validate_aggregated_advisory(ROOT, packet, payload),
            {"approved": 0, "rejected": 1, "total": 1},
        )

        outside = copy.deepcopy(payload)
        outside["recommendations"][0]["references"] = ["https://example.invalid/evidence"]
        outside["advisory_fingerprint"] = knowledge.semantic_fingerprint(outside, "advisory_fingerprint")
        with self.assertRaisesRegex(ValueError, "outside the packet"):
            advisory.validate_aggregated_advisory(ROOT, packet, outside)


if __name__ == "__main__":
    unittest.main()
