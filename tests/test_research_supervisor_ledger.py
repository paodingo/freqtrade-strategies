import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_director_common import fingerprint, open_director_registry  # noqa: E402
import research_supervisor_ledger as ledger  # noqa: E402


GOVERNANCE = {
    "config_fingerprint": "c" * 64,
    "approval_fingerprint": "a" * 64,
}


class ResearchSupervisorLedgerTests(unittest.TestCase):
    def test_active_lease_skips_second_run_and_records_all_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            first = ledger.acquire(
                registry,
                supervisor_id="supervisor-test",
                lock_name="supervisor-test-lock",
                lease_seconds=120,
                governance_binding=GOVERNANCE,
                started_at="2026-07-21T00:00:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-first",
            )
            second = ledger.acquire(
                registry,
                supervisor_id="supervisor-test",
                lock_name="supervisor-test-lock",
                lease_seconds=120,
                governance_binding=GOVERNANCE,
                started_at="2026-07-21T00:01:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-second",
            )
            result = {"status": "idle", "completed_jobs": 0}
            result_fingerprint = ledger.complete(
                registry,
                first,
                result,
                completed_at="2026-07-21T00:01:30Z",
            )

            connection = open_director_registry(registry)
            runs = {
                row["supervisor_run_id"]: dict(row)
                for row in connection.execute(
                    "SELECT * FROM research_supervisor_runs ORDER BY supervisor_run_id"
                )
            }
            events = [
                (row["supervisor_run_id"], row["event_type"])
                for row in connection.execute(
                    "SELECT supervisor_run_id,event_type "
                    "FROM research_supervisor_run_events ORDER BY created_at,event_type"
                )
            ]
            lock_count = connection.execute(
                "SELECT COUNT(*) FROM research_supervisor_locks"
            ).fetchone()[0]
            connection.close()

        self.assertTrue(first["acquired"])
        self.assertFalse(second["acquired"])
        self.assertEqual(second["status"], "skipped_lock_held")
        self.assertEqual(runs["supervisor-run-first"]["status"], "completed")
        self.assertEqual(
            runs["supervisor-run-first"]["result_fingerprint"], fingerprint(result)
        )
        self.assertEqual(result_fingerprint, fingerprint(result))
        self.assertEqual(
            runs["supervisor-run-second"]["status"], "skipped_lock_held"
        )
        self.assertEqual(
            events,
            [
                ("supervisor-run-first", "started"),
                ("supervisor-run-second", "skipped_lock_held"),
                ("supervisor-run-first", "completed"),
            ],
        )
        self.assertEqual(lock_count, 0)

    def test_expired_lease_fails_stale_run_and_increments_fencing_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            stale = ledger.acquire(
                registry,
                supervisor_id="supervisor-test",
                lock_name="supervisor-test-lock",
                lease_seconds=60,
                governance_binding=GOVERNANCE,
                started_at="2026-07-21T00:00:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-stale",
            )
            recovered = ledger.acquire(
                registry,
                supervisor_id="supervisor-test",
                lock_name="supervisor-test-lock",
                lease_seconds=60,
                governance_binding=GOVERNANCE,
                started_at="2026-07-21T00:02:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-recovered",
            )

            with self.assertRaisesRegex(ValueError, "ownership lost"):
                ledger.heartbeat(
                    registry,
                    stale,
                    60,
                    renewed_at="2026-07-21T00:02:01Z",
                )
            ledger.complete(
                registry,
                recovered,
                {"status": "idle"},
                completed_at="2026-07-21T00:02:02Z",
            )
            connection = open_director_registry(registry)
            stale_row = connection.execute(
                "SELECT status,payload_json FROM research_supervisor_runs "
                "WHERE supervisor_run_id='supervisor-run-stale'"
            ).fetchone()
            failed_events = connection.execute(
                "SELECT COUNT(*) FROM research_supervisor_run_events "
                "WHERE supervisor_run_id='supervisor-run-stale' AND event_type='failed'"
            ).fetchone()[0]
            connection.close()

        self.assertTrue(recovered["acquired"])
        self.assertEqual(recovered["lock_fencing_token"], 2)
        self.assertEqual(recovered["recovered_stale_run_id"], stale["supervisor_run_id"])
        self.assertEqual(stale_row["status"], "failed")
        self.assertIn("lock_lease_expired_before_completion", stale_row["payload_json"])
        self.assertEqual(failed_events, 1)

    def test_failure_records_terminal_event_and_releases_owned_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = Path(temporary) / "director.db"
            acquired = ledger.acquire(
                registry,
                supervisor_id="supervisor-test",
                lock_name="supervisor-test-lock",
                lease_seconds=60,
                governance_binding=GOVERNANCE,
                started_at="2026-07-21T00:00:00Z",
                trigger_source="test",
                invocation_id="supervisor-run-failed",
            )
            recorded = ledger.fail(
                registry,
                acquired,
                RuntimeError("fixture failure"),
                failed_at="2026-07-21T00:00:01Z",
            )
            replay = ledger.fail(
                registry,
                acquired,
                RuntimeError("duplicate"),
                failed_at="2026-07-21T00:00:02Z",
            )
            connection = open_director_registry(registry)
            status = connection.execute(
                "SELECT status FROM research_supervisor_runs"
            ).fetchone()[0]
            failed_events = connection.execute(
                "SELECT COUNT(*) FROM research_supervisor_run_events "
                "WHERE event_type='failed'"
            ).fetchone()[0]
            lock_count = connection.execute(
                "SELECT COUNT(*) FROM research_supervisor_locks"
            ).fetchone()[0]
            connection.close()

        self.assertTrue(recorded)
        self.assertFalse(replay)
        self.assertEqual((status, failed_events, lock_count), ("failed", 1, 0))


if __name__ == "__main__":
    unittest.main()
