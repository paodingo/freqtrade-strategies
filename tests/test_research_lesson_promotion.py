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
import research_lesson_curation as curation  # noqa: E402
import research_lesson_promotion as promotion  # noqa: E402
from research_director_common import load_document, open_director_registry  # noqa: E402


class ResearchLessonPromotionTests(unittest.TestCase):
    def setUp(self):
        self.approval = load_document(ROOT / knowledge.PROMOTION_APPROVAL)
        self.packet = load_document(ROOT / knowledge.PROMOTION_PACKET)

    def test_human_approval_is_exactly_bound_to_six_candidates(self):
        cards = promotion.validate_approval(ROOT, self.approval, self.packet)
        events = promotion.build_events(ROOT, self.approval, self.packet)

        self.assertEqual(len(cards), 6)
        self.assertEqual(len(events), 6)
        self.assertTrue(all(event["decision"] == "approved" for event in events))
        self.assertTrue(all(event["review_type"] == "lesson_promotion" for event in events))
        self.assertTrue(all(not event["automatic_lesson_promotion_authorized"] for event in events))
        self.assertTrue(all(not event["execution_authorized"] for event in events))

    def test_formal_catalog_replaces_one_old_card_and_adds_six_promoted_cards(self):
        lessons = knowledge.lesson_cards(ROOT)
        ids = {item["lesson_id"] for item in lessons}

        self.assertEqual(len(lessons), 9)
        self.assertNotIn("ranging-short-branch-negative-contributor-v1", ids)
        self.assertIn("ranging-short-temporal-retention-v1", ids)
        self.assertEqual(len(ids.intersection({item["proposed_lesson_id"] for item in self.packet["candidates"]})), 6)

    def test_registry_application_is_atomic_and_idempotent(self):
        events = promotion.build_events(ROOT, self.approval, self.packet)
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            connection = open_director_registry(registry)
            for packet_item in self.packet["candidates"]:
                candidate = load_document(ROOT / packet_item["path"])
                connection.execute(
                    "INSERT INTO research_lesson_curation_candidates(candidate_id,proposed_lesson_id,candidate_fingerprint,status,source_feedback_ids_json,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                    (candidate["candidate_id"], candidate["proposed_card"]["lesson_id"], candidate["candidate_fingerprint"], candidate["status"], json.dumps(candidate["source_feedback_ids"], sort_keys=True), json.dumps(candidate, sort_keys=True), "2026-07-19T19:00:00+08:00"),
                )
            connection.execute(
                "INSERT INTO open_source_research_lessons(lesson_id,lesson_fingerprint,outcome,mechanism_keys_json,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                ("ranging-short-branch-negative-contributor-v1", "d" * 64, "negative_contributor", "[]", "{}", "2026-07-19T00:00:00+08:00"),
            )
            connection.execute(
                "INSERT INTO research_knowledge_lifecycle(item_key,item_type,item_id,snapshot_fingerprint,lifecycle_status,superseded_by,reason,payload_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                ("lesson:old", "lesson", "ranging-short-branch-negative-contributor-v1", "d" * 64, "active", None, "initial", "{}", "2026-07-19T00:00:00+08:00"),
            )
            connection.commit()
            connection.close()

            first = promotion.apply_registry_promotion(registry, self.approval, events)
            second = promotion.apply_registry_promotion(registry, self.approval, events)
            connection = open_director_registry(registry)
            statuses = [row[0] for row in connection.execute("SELECT status FROM research_lesson_curation_candidates")]
            old_count = connection.execute("SELECT COUNT(*) FROM open_source_research_lessons WHERE lesson_id='ranging-short-branch-negative-contributor-v1'").fetchone()[0]
            lifecycle = connection.execute("SELECT lifecycle_status,superseded_by FROM research_knowledge_lifecycle WHERE item_key='lesson:old'").fetchone()
            connection.close()

        self.assertEqual(first, second)
        self.assertEqual(first["promoted"], 6)
        self.assertEqual(first["promotion_events"], 6)
        self.assertEqual(first["formal_lessons"], 0)
        self.assertEqual(set(statuses), {"promoted"})
        self.assertEqual(old_count, 0)
        self.assertEqual(tuple(lifecycle), ("superseded", "ranging-short-temporal-retention-v1"))

    def test_tampered_approval_is_rejected(self):
        tampered = json.loads(json.dumps(self.approval))
        tampered["approved_count"] = 5
        with self.assertRaisesRegex(ValueError, "governed workspace approval"):
            promotion.validate_approval(ROOT, tampered, self.packet)

    def test_promoted_curation_batch_cannot_be_regenerated(self):
        with self.assertRaisesRegex(ValueError, "curation batch is closed"):
            curation.main(["--repo-root", str(ROOT)])


if __name__ == "__main__":
    unittest.main()
