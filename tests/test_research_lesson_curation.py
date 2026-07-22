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
import research_lesson_curation as curation  # noqa: E402
from research_director_common import load_document, open_director_registry  # noqa: E402


class ResearchLessonCurationTests(unittest.TestCase):
    def _temporary_repo(self, root: Path) -> Path:
        for relative in (
            curation.CANDIDATE_SCHEMA,
            curation.LESSON_SCHEMA,
            curation.PACKET_SCHEMA,
            knowledge.OUTPUT_ROOT / "current-context.json",
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def test_seven_approved_feedback_items_become_six_deduplicated_candidates(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        context_before = load_document(ROOT / knowledge.OUTPUT_ROOT / "current-context.json")
        with tempfile.TemporaryDirectory() as temporary:
            repo = self._temporary_repo(Path(temporary))
            candidates, packet = curation.build_candidates(repo, registry_export)

        covered = [
            feedback_id
            for candidate in candidates
            for feedback_id in candidate["source_feedback_ids"]
        ]
        self.assertEqual(len(candidates), 6)
        self.assertEqual(packet["approved_feedback_count"], 7)
        self.assertEqual(packet["candidate_count"], 6)
        self.assertEqual(packet["coverage"]["duplicate_feedback_merged"], 1)
        self.assertEqual(packet["coverage"]["uncovered_feedback_ids"], [])
        self.assertEqual(sorted(covered), packet["coverage"]["approved_feedback_ids"])
        self.assertEqual(len(covered), len(set(covered)))
        self.assertTrue(all(candidate["status"] == "pending_human_promotion_review" for candidate in candidates))
        self.assertTrue(all(not candidate["automatic_promotion_authorized"] for candidate in candidates))
        self.assertFalse(packet["automatic_promotion_authorized"])
        self.assertFalse(packet["execution_authorized"])
        self.assertTrue(packet["human_approval_required"])
        self.assertEqual(packet["formal_lesson_count_before"], len(context_before["lessons"]))
        self.assertEqual(
            context_before["knowledge_snapshot_fingerprint"],
            packet["knowledge_snapshot_fingerprint"],
        )

    def test_temporal_retention_candidate_merges_two_feedback_items_and_supersedes_only_after_promotion(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        with tempfile.TemporaryDirectory() as temporary:
            repo = self._temporary_repo(Path(temporary))
            candidates, _ = curation.build_candidates(repo, registry_export)

        candidate = next(
            item
            for item in candidates
            if item["proposed_card"]["lesson_id"] == "ranging-short-temporal-retention-v1"
        )
        self.assertEqual(len(candidate["source_feedback_ids"]), 2)
        self.assertEqual(candidate["merge_disposition"], "replace_existing_lesson")
        self.assertEqual(
            candidate["supersedes_lesson_ids"],
            ["ranging-short-branch-negative-contributor-v1"],
        )
        self.assertEqual(candidate["status"], "pending_human_promotion_review")

    def test_candidate_registry_registration_is_idempotent(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            repo = self._temporary_repo(temporary_root / "repo")
            candidates, _ = curation.build_candidates(repo, registry_export)
            registry = temporary_root / "director.db"
            first = curation.register_candidates(registry, candidates)
            second = curation.register_candidates(registry, candidates)
            connection = open_director_registry(registry)
            rows = connection.execute(
                "SELECT status, payload_json FROM research_lesson_curation_candidates ORDER BY candidate_id"
            ).fetchall()
            connection.close()

        self.assertEqual(first, 6)
        self.assertEqual(second, 6)
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(row["status"] == "pending_human_promotion_review" for row in rows))
        self.assertTrue(all(not json.loads(row["payload_json"])["automatic_promotion_authorized"] for row in rows))

    def test_formal_knowledge_context_is_not_modified_by_curation(self):
        registry_export = load_document(ROOT / "research/director/registry-records.json")
        context_before = load_document(ROOT / knowledge.OUTPUT_ROOT / "current-context.json")
        with tempfile.TemporaryDirectory() as temporary:
            repo = self._temporary_repo(Path(temporary))
            curation.build_candidates(repo, registry_export)
        context_after = load_document(ROOT / knowledge.OUTPUT_ROOT / "current-context.json")

        self.assertEqual(context_before, context_after)
        self.assertEqual(len(context_after["lessons"]), len(context_before["lessons"]))


if __name__ == "__main__":
    unittest.main()
