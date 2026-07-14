import inspect
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import research_director_common  # noqa: E402
from build_current_research_state import build_state  # noqa: E402
from export_director_registry import export_registry  # noqa: E402
from research_director_common import director_registry_export, open_director_registry  # noqa: E402


DISCOVERY_TABLES = {
    "research_discovery_runs",
    "research_discovery_ideas",
    "research_discovery_critiques",
    "research_discovery_shortlists",
    "research_discovery_approvals",
    "research_discovery_handoffs",
    "research_discovery_events",
}

DISCOVERY_COLUMNS = {
    "research_discovery_runs": (
        "run_id",
        "trigger_fingerprint",
        "status",
        "state_fingerprint",
        "payload_json",
        "created_at",
    ),
    "research_discovery_ideas": (
        "idea_key",
        "run_id",
        "idea_id",
        "idea_version",
        "semantic_fingerprint",
        "strategy_family",
        "status",
        "payload_json",
        "created_at",
    ),
    "research_discovery_critiques": (
        "critique_id",
        "run_id",
        "idea_key",
        "verdict",
        "critic_fingerprint",
        "payload_json",
        "created_at",
    ),
    "research_discovery_shortlists": (
        "run_id",
        "shortlist_fingerprint",
        "recommendation",
        "payload_json",
        "created_at",
    ),
    "research_discovery_approvals": (
        "approval_fingerprint",
        "run_id",
        "decision",
        "selected_idea_id",
        "payload_json",
        "decided_at",
    ),
    "research_discovery_handoffs": (
        "handoff_fingerprint",
        "run_id",
        "idea_id",
        "status",
        "director_result_code",
        "payload_json",
        "created_at",
    ),
    "research_discovery_events": (
        "event_id",
        "run_id",
        "event_type",
        "reason_code",
        "payload_json",
        "created_at",
    ),
}


def create_v4_registry(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE director_schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE director_runs (
          run_id TEXT PRIMARY KEY,
          state_fingerprint TEXT NOT NULL,
          objective TEXT,
          risk_tolerance TEXT NOT NULL,
          budget_json TEXT NOT NULL,
          recommendation TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        INSERT INTO director_schema_migrations(version, applied_at)
        VALUES (4, '2026-07-13T00:00:00+00:00');
        INSERT INTO director_runs(
          run_id, state_fingerprint, objective, risk_tolerance, budget_json,
          recommendation, payload_json, created_at
        ) VALUES (
          'legacy-run', 'legacy-state', NULL, 'low', '{}',
          'no_research_recommended', '{}', '2026-07-13T00:00:00+00:00'
        );
        """
    )
    connection.commit()
    connection.close()


class ResearchDiscoveryRegistryTests(unittest.TestCase):
    def test_v4_registry_migrates_to_v5_without_losing_existing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            create_v4_registry(database)

            with closing(open_director_registry(database)) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }

                self.assertEqual(research_director_common.DIRECTOR_SCHEMA_VERSION, 5)
                self.assertTrue(DISCOVERY_TABLES.issubset(tables))
                self.assertEqual(
                    [row[0] for row in connection.execute(
                        "SELECT version FROM director_schema_migrations ORDER BY version"
                    )],
                    [4, 5],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT recommendation FROM director_runs WHERE run_id='legacy-run'"
                    ).fetchone()[0],
                    "no_research_recommended",
                )
                for table, expected_columns in DISCOVERY_COLUMNS.items():
                    actual_columns = tuple(
                        row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
                    )
                    self.assertEqual(actual_columns, expected_columns, table)

    def test_schema_migration_is_idempotent_and_trigger_conflicts_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            first = open_director_registry(database)
            first.close()
            with closing(open_director_registry(database)) as connection:
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM director_schema_migrations WHERE version=5"
                    ).fetchone()[0],
                    1,
                )
                original = (
                    "discovery-run-1",
                    "trigger-fingerprint-1",
                    "completed",
                    "state-fingerprint-1",
                    json.dumps({"source": "test"}),
                    "2026-07-14T00:00:00+00:00",
                )
                connection.execute(
                    "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                    original,
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            "discovery-run-2",
                            "trigger-fingerprint-1",
                            "failed",
                            "state-fingerprint-2",
                            "{}",
                            "2026-07-14T00:01:00+00:00",
                        ),
                    )
                stored = connection.execute(
                    "SELECT run_id, status, state_fingerprint, payload_json "
                    "FROM research_discovery_runs WHERE trigger_fingerprint=?",
                    ("trigger-fingerprint-1",),
                ).fetchone()
                self.assertEqual(tuple(stored), (original[0], original[2], original[3], original[4]))

    def test_both_registry_exports_include_empty_discovery_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            connection.close()

            public_export = export_registry(str(database))
            helper_export = director_registry_export(database)

            for table in DISCOVERY_TABLES:
                self.assertIn(table, public_export["tables"])
                self.assertEqual(public_export["tables"][table], [], table)
                self.assertEqual(public_export["counts"][table], 0, table)
                self.assertIn(table, helper_export)
                self.assertEqual(helper_export[table], [], table)

    def test_completed_discovery_run_is_included_in_current_state_summary(self):
        parameters = inspect.signature(build_state).parameters
        self.assertIn("director_registry", parameters)
        self.assertIsNone(parameters["source_registry"].default)
        self.assertIsNone(parameters["data_lineage"].default)
        self.assertIsNone(parameters["director_registry"].default)

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            connection.execute(
                "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "discovery-run-1",
                    "trigger-fingerprint-1",
                    "completed",
                    "state-fingerprint-1",
                    "{}",
                    "2026-07-14T00:00:00+00:00",
                ),
            )
            connection.commit()
            connection.close()

            state = build_state(ROOT, director_registry=database)
            self.assertEqual(state["research_discovery"]["completed_runs"], 1)
            self.assertEqual(state["research_discovery"]["director_rejections"], 0)
            self.assertEqual(state["research_discovery"]["recent_ideas"], [])

            unavailable_state = build_state(ROOT)
            self.assertFalse(unavailable_state["research_discovery"]["available"])


if __name__ == "__main__":
    unittest.main()
