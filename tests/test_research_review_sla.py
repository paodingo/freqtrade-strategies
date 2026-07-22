import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_director_common import fingerprint, open_director_registry  # noqa: E402
import research_review_sla as review_sla  # noqa: E402


def advisory(generated_at: str = "2026-07-20T01:00:00Z") -> dict:
    payload = {
        "schema_version": "knowledge-review-recommendations-v1",
        "advisory_id": "fixture-advisory",
        "generated_at": generated_at,
        "packet_fingerprint": "p" * 64,
        "recommendations": [],
        "summary": {"approved": 0, "rejected": 0, "total": 0},
        "human_decision_required": True,
        "automatic_application_authorized": False,
        "execution_authorized": False,
    }
    payload["advisory_fingerprint"] = fingerprint(payload)
    return payload


class ResearchReviewSlaTests(unittest.TestCase):
    def evaluate(self, registry: Path, checked_at: str, value: dict | None = None) -> dict:
        return review_sla.evaluate(
            ROOT,
            registry,
            batch_id="knowledge-review-batch-0123456789abcdef",
            advisory=value or advisory(),
            checked_at=checked_at,
        )

    def test_not_due_is_silent_and_writes_no_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            result = self.evaluate(registry, "2026-07-23T00:59:59Z")
            connection = open_director_registry(registry)
            count = connection.execute(
                "SELECT COUNT(*) FROM research_review_sla_events"
            ).fetchone()[0]
            connection.close()

        self.assertEqual(result["status"], "awaiting_human_review")
        self.assertFalse(result["notification_required"])
        self.assertEqual(result["next_notification_at"], "2026-07-23T01:00:00+00:00")
        self.assertEqual(count, 0)

    def test_reminder_and_escalation_are_each_claimed_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            reminder = self.evaluate(registry, "2026-07-23T01:00:00Z")
            reminder_replay = self.evaluate(registry, "2026-07-23T02:00:00Z")
            escalation = self.evaluate(registry, "2026-07-27T01:00:00Z")
            escalation_replay = self.evaluate(registry, "2026-07-27T02:00:00Z")
            connection = open_director_registry(registry)
            levels = [
                row[0]
                for row in connection.execute(
                    "SELECT notification_level FROM research_review_sla_events "
                    "ORDER BY created_at"
                )
            ]
            connection.close()

        self.assertEqual(reminder["status"], "review_reminder_due")
        self.assertTrue(reminder["notification_required"])
        self.assertFalse(reminder_replay["notification_required"])
        self.assertEqual(escalation["status"], "review_escalation_due")
        self.assertTrue(escalation["notification_required"])
        self.assertFalse(escalation_replay["notification_required"])
        self.assertEqual(levels, ["reminder_72h", "escalation_168h"])

    def test_catch_up_claims_only_highest_due_level(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            catch_up = self.evaluate(registry, "2026-07-28T01:00:00Z")
            replay = self.evaluate(registry, "2026-07-29T01:00:00Z")
            connection = open_director_registry(registry)
            levels = [
                row[0]
                for row in connection.execute(
                    "SELECT notification_level FROM research_review_sla_events"
                )
            ]
            connection.close()

        self.assertEqual(catch_up["notification_level"], "escalation_168h")
        self.assertTrue(catch_up["notification_required"])
        self.assertFalse(replay["notification_required"])
        self.assertEqual(levels, ["escalation_168h"])

    def test_due_outside_notification_window_waits_without_claiming(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            value = advisory("2026-07-20T00:00:00Z")
            outside = self.evaluate(registry, "2026-07-23T00:00:00Z", value)
            inside = self.evaluate(registry, "2026-07-23T01:00:00Z", value)

        self.assertEqual(outside["status"], "awaiting_notification_window")
        self.assertFalse(outside["notification_required"])
        self.assertEqual(outside["next_notification_at"], "2026-07-23T01:00:00+00:00")
        self.assertEqual(inside["status"], "review_reminder_due")
        self.assertTrue(inside["notification_required"])


if __name__ == "__main__":
    unittest.main()
