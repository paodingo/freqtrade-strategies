import copy
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_knowledge_feedback_backfill as backfill  # noqa: E402
from research_director_common import load_document  # noqa: E402


class ResearchKnowledgeFeedbackBackfillTests(unittest.TestCase):
    def _health(self):
        return load_document(ROOT / backfill.HEALTH_PATH)

    def _registry(self):
        return load_document(ROOT / backfill.REGISTRY_EXPORT_PATH)

    def _packet(self):
        root = ROOT / backfill.OUTPUT_ROOT
        path = next(root.glob("knowledge-result-feedback-backfill-*/packet.json"))
        return load_document(path)

    def _legacy_health(self):
        health = self._health()
        chain = health["knowledge_impact"]["result_feedback_chain"]
        completed = [
            item
            for item in chain["runs"]
            if item["analysis_completed"]
            and any(
                result_id.startswith("historical-descriptive-result-")
                for result_id in item["registered_result_ids"]
            )
        ]
        for item in completed:
            item["classification"] = "analysis_completed_feedback_unregistered"
            item["registered_result_ids"] = []
            item["feedback_ids"] = []
            item["feedback_review_statuses"] = []
        chain["registered_result_run_count"] = 0
        chain["feedback_draft_run_count"] = 0
        chain["feedback_reviewed_run_count"] = 0
        chain["legacy_unregistered_run_count"] = len(completed)
        health["health_fingerprint"] = backfill.knowledge.semantic_fingerprint(
            health, "health_fingerprint"
        )
        return health

    def _copy_apply_fixture(self, repo: Path, packet: dict):
        paths = [
            backfill.REGISTRY_EXPORT_PATH,
            backfill.HEALTH_PATH,
            backfill.SCHEMA_PATH,
            backfill.INTENT_SCHEMA_PATH,
            backfill.APPROVAL_SCHEMA_PATH,
            Path("research/knowledge/schemas/research-learning-loop-health.schema.json"),
            Path("research/knowledge/open-source-v1/current-context.json"),
            Path("reports/audits/open-source-learning-v1/source-refresh-report.json"),
            Path("reports/audits/open-source-learning-v1/retrieval-evaluation.json"),
        ]
        for item in packet["items"]:
            paths.extend(Path(artifact["path"]) for artifact in item["evidence_artifacts"])
        paths.append(
            backfill.OUTPUT_ROOT / packet["packet_id"] / "packet.json"
        )
        for relative in paths:
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        registry = repo / "research/registry/stage4a-director.db"
        registry.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "research/registry/stage4a-director.db", registry)
        connection = sqlite3.connect(registry)
        connection.execute(
            "DELETE FROM research_lesson_feedback_drafts WHERE campaign_id='historical_manual_descriptive_analysis'"
        )
        connection.execute(
            "DELETE FROM research_descriptive_execution_results WHERE job_id LIKE 'historical-manual-%'"
        )
        connection.commit()
        connection.close()
        return registry

    def test_current_legacy_results_compile_to_one_nonexecuting_batch(self):
        packet = backfill.build_packet(ROOT, self._legacy_health(), self._registry())

        self.assertEqual(packet["item_count"], 2)
        self.assertEqual(
            {item["proposal_id"] for item in packet["items"]},
            {
                "discovery-additional-pair-manifest-inventory-v1-v2",
                "discovery-bnb-xrp-distribution-shift-profile-v1-v1",
            },
        )
        self.assertTrue(all(item["outcome_class"] == "inconclusive" for item in packet["items"]))
        self.assertTrue(all(
            item["registration_mode"] == "historical_manual_descriptive_analysis"
            for item in packet["items"]
        ))
        self.assertTrue(all(
            item["proposed_feedback_review_status"] == "pending_human_review"
            for item in packet["items"]
        ))
        self.assertFalse(packet["automatic_application_authorized"])
        self.assertFalse(packet["automatic_lesson_promotion_authorized"])
        self.assertFalse(packet["execution_authorized"])

    def test_artifact_fingerprint_drift_fails_closed(self):
        health = self._legacy_health()
        health["knowledge_impact"]["result_feedback_chain"]["runs"][0]["artifacts"][0]["sha256"] = "0" * 64
        health["health_fingerprint"] = backfill.knowledge.semantic_fingerprint(
            health, "health_fingerprint"
        )
        with self.assertRaisesRegex(ValueError, "artifact fingerprint drift"):
            backfill.build_packet(ROOT, health, self._registry())

    def test_no_legacy_items_is_idle(self):
        health = self._health()
        chain = health["knowledge_impact"]["result_feedback_chain"]
        chain["runs"] = []
        chain["legacy_unregistered_run_count"] = 0
        health["health_fingerprint"] = backfill.knowledge.semantic_fingerprint(
            health, "health_fingerprint"
        )
        result = backfill.build_packet(ROOT, health, self._registry())
        self.assertEqual(result["status"], "idle")
        self.assertFalse(result["packet_modified"])

    def test_publish_is_immutable_and_does_not_touch_registry(self):
        packet = backfill.build_packet(ROOT, self._legacy_health(), self._registry())
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            registry = repo / backfill.REGISTRY_EXPORT_PATH
            registry.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / backfill.REGISTRY_EXPORT_PATH, registry)
            before = registry.read_bytes()

            path, first = backfill.publish_packet(repo, packet)
            _, replay = backfill.publish_packet(repo, packet)
            self.assertTrue(first)
            self.assertFalse(replay)
            self.assertEqual(load_document(path), packet)
            self.assertEqual(registry.read_bytes(), before)

            changed = copy.deepcopy(packet)
            changed["items"][0]["result_code"] = "tampered"
            with self.assertRaisesRegex(ValueError, "immutable backfill review packet conflict"):
                backfill.publish_packet(repo, changed)

    def test_explicit_approval_registers_results_and_pending_feedback_atomically(self):
        packet = self._packet()
        statement = packet["decision_contract"]["approve_all_statement_zh"]
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            registry = self._copy_apply_fixture(repo, packet)
            intent = backfill.build_human_intent(
                repo, packet, statement, "2026-07-21T12:00:00Z"
            )
            result = backfill.apply_approved_backfill(
                repo,
                registry,
                repo / backfill.REGISTRY_EXPORT_PATH,
                repo / backfill.HEALTH_PATH,
                packet,
                intent,
            )
            replay = backfill.apply_approved_backfill(
                repo,
                registry,
                repo / backfill.REGISTRY_EXPORT_PATH,
                repo / backfill.HEALTH_PATH,
                packet,
                intent,
            )
            connection = sqlite3.connect(registry)
            result_count = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results"
            ).fetchone()[0]
            feedback_rows = connection.execute(
                "SELECT review_status,payload_json FROM research_lesson_feedback_drafts "
                "WHERE campaign_id='historical_manual_descriptive_analysis' ORDER BY feedback_id"
            ).fetchall()
            connection.close()
            health = load_document(repo / backfill.HEALTH_PATH)

        self.assertEqual(result["status"], "historical_feedback_backfill_applied")
        self.assertEqual(result["registered_results"], 2)
        self.assertEqual(result["pending_feedback"], 2)
        self.assertEqual(result["result_feedback_broken"], 0)
        self.assertEqual(replay["status"], "historical_feedback_backfill_already_applied")
        self.assertFalse(replay["registry_modified"])
        self.assertEqual(result_count, 3)
        self.assertEqual(len(feedback_rows), 2)
        self.assertTrue(all(row[0] == "pending_human_review" for row in feedback_rows))
        self.assertTrue(all(
            json.loads(row[1])["registration_mode"] == "historical_manual_descriptive_analysis"
            for row in feedback_rows
        ))
        chain = health["knowledge_impact"]["result_feedback_chain"]
        self.assertEqual(chain["legacy_unregistered_run_count"], 0)
        self.assertEqual(chain["feedback_draft_run_count"], 3)
        self.assertEqual(chain["broken_chain_run_count"], 0)

    def test_wrong_human_statement_is_rejected(self):
        packet = self._packet()
        with self.assertRaisesRegex(ValueError, "does not exactly match"):
            backfill.build_human_intent(
                ROOT, packet, "批准但扩大范围", "2026-07-21T12:00:00Z"
            )


if __name__ == "__main__":
    unittest.main()
