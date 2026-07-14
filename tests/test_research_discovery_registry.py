import inspect
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock


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

DISCOVERY_SCHEMA = {
    "research_discovery_runs": (
        ("run_id", "TEXT", 0, None, 1),
        ("trigger_fingerprint", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("state_fingerprint", "TEXT", 1, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "research_discovery_ideas": (
        ("idea_key", "TEXT", 0, None, 1),
        ("run_id", "TEXT", 1, None, 0),
        ("idea_id", "TEXT", 1, None, 0),
        ("idea_version", "INTEGER", 1, None, 0),
        ("semantic_fingerprint", "TEXT", 1, None, 0),
        ("strategy_family", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "research_discovery_critiques": (
        ("critique_id", "TEXT", 0, None, 1),
        ("run_id", "TEXT", 1, None, 0),
        ("idea_key", "TEXT", 1, None, 0),
        ("verdict", "TEXT", 1, None, 0),
        ("critic_fingerprint", "TEXT", 1, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "research_discovery_shortlists": (
        ("run_id", "TEXT", 0, None, 1),
        ("shortlist_fingerprint", "TEXT", 1, None, 0),
        ("recommendation", "TEXT", 1, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "research_discovery_approvals": (
        ("approval_fingerprint", "TEXT", 0, None, 1),
        ("run_id", "TEXT", 1, None, 0),
        ("decision", "TEXT", 1, None, 0),
        ("selected_idea_id", "TEXT", 0, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("decided_at", "TEXT", 1, None, 0),
    ),
    "research_discovery_handoffs": (
        ("handoff_fingerprint", "TEXT", 0, None, 1),
        ("run_id", "TEXT", 1, None, 0),
        ("idea_id", "TEXT", 1, None, 0),
        ("status", "TEXT", 1, None, 0),
        ("director_result_code", "TEXT", 0, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
    "research_discovery_events": (
        ("event_id", "TEXT", 0, None, 1),
        ("run_id", "TEXT", 1, None, 0),
        ("event_type", "TEXT", 1, None, 0),
        ("reason_code", "TEXT", 0, None, 0),
        ("payload_json", "TEXT", 1, None, 0),
        ("created_at", "TEXT", 1, None, 0),
    ),
}

DISCOVERY_UNIQUE_INDEXES = {
    "research_discovery_runs": {
        ("run_id",): "pk",
        ("trigger_fingerprint",): "u",
    },
    "research_discovery_ideas": {
        ("idea_key",): "pk",
        ("semantic_fingerprint",): "u",
    },
    "research_discovery_critiques": {
        ("critique_id",): "pk",
        ("critic_fingerprint",): "u",
    },
    "research_discovery_shortlists": {
        ("run_id",): "pk",
        ("shortlist_fingerprint",): "u",
    },
    "research_discovery_approvals": {("approval_fingerprint",): "pk"},
    "research_discovery_handoffs": {("handoff_fingerprint",): "pk"},
    "research_discovery_events": {("event_id",): "pk"},
}


class TrackingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.discovery_ddl_transaction_states: list[bool] = []
        self.fail_migration_insert = False
        self.fail_schema_validation = False

    def execute(self, sql, parameters=(), /):
        normalized = " ".join(sql.split())
        if normalized.startswith("CREATE TABLE IF NOT EXISTS research_discovery_"):
            self.discovery_ddl_transaction_states.append(self.in_transaction)
        if (
            self.fail_migration_insert
            and normalized.startswith("INSERT OR IGNORE INTO director_schema_migrations")
        ):
            raise sqlite3.OperationalError("injected v5 migration insert failure")
        if (
            self.fail_schema_validation
            and normalized.startswith("INSERT OR IGNORE INTO director_schema_migrations")
        ):
            raise RuntimeError("injected schema validation failure")
        return super().execute(sql, parameters)


class ObservedConnection:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.closed = False

    @property
    def row_factory(self):
        return self.connection.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self.connection.row_factory = value

    def execute(self, sql, parameters=()):
        return self.connection.execute(sql, parameters)

    def close(self):
        self.closed = True
        self.connection.close()


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


DISCOVERY_EXPORT_ROWS = {
    "research_discovery_runs": [
        ("run-z", "trigger-z", "completed", "state-z", '{"record":"run-z"}', "2026-07-14T00:02:00+00:00"),
        ("run-a", "trigger-a", "no_research_recommended", "state-a", '{"record":"run-a"}', "2026-07-14T00:01:00+00:00"),
    ],
    "research_discovery_ideas": [
        ("idea-key-z", "run-z", "idea-z", 2, "semantic-z", "family-z", "shortlisted", '{"record":"idea-z"}', "2026-07-14T00:04:00+00:00"),
        ("idea-key-a", "run-a", "idea-a", 1, "semantic-a", "family-a", "proposed", '{"record":"idea-a"}', "2026-07-14T00:03:00+00:00"),
    ],
    "research_discovery_critiques": [
        ("critique-z", "run-z", "idea-key-z", "accept", "critic-z", '{"record":"critique-z"}', "2026-07-14T00:05:00+00:00"),
        ("critique-a", "run-a", "idea-key-a", "revise", "critic-a", '{"record":"critique-a"}', "2026-07-14T00:04:00+00:00"),
    ],
    "research_discovery_shortlists": [
        ("run-z", "shortlist-z", "research_recommended", '{"record":"shortlist-z"}', "2026-07-14T00:06:00+00:00"),
        ("run-a", "shortlist-a", "no_research_recommended", '{"record":"shortlist-a"}', "2026-07-14T00:05:00+00:00"),
    ],
    "research_discovery_approvals": [
        ("approval-z", "run-z", "approved", "idea-z", '{"record":"approval-z"}', "2026-07-14T00:07:00+00:00"),
        ("approval-a", "run-a", "rejected", None, '{"record":"approval-a"}', "2026-07-14T00:06:00+00:00"),
    ],
    "research_discovery_handoffs": [
        ("handoff-z", "run-z", "idea-z", "director_rejected", "duplicate_research_question", '{"record":"handoff-z"}', "2026-07-14T00:08:00+00:00"),
        ("handoff-a", "run-a", "idea-a", "accepted", None, '{"record":"handoff-a"}', "2026-07-14T00:07:00+00:00"),
    ],
    "research_discovery_events": [
        ("event-z", "run-z", "completed", None, '{"record":"event-z"}', "2026-07-14T00:09:00+00:00"),
        ("event-a", "run-a", "started", "manual_trigger", '{"record":"event-a"}', "2026-07-14T00:08:00+00:00"),
    ],
}


def discovery_table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        if row[0] in DISCOVERY_TABLES
    }


def insert_discovery_export_rows(connection: sqlite3.Connection) -> None:
    for table, rows in DISCOVERY_EXPORT_ROWS.items():
        placeholders = ", ".join("?" for _ in rows[0])
        connection.executemany(
            f'INSERT INTO "{table}" VALUES ({placeholders})',
            rows,
        )


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
                for table, expected_schema in DISCOVERY_SCHEMA.items():
                    actual_schema = tuple(
                        (row[1], row[2], row[3], row[4], row[5])
                        for row in connection.execute(f'PRAGMA table_info("{table}")')
                    )
                    self.assertEqual(actual_schema, expected_schema, table)
                    actual_unique_indexes = {}
                    for index in connection.execute(f'PRAGMA index_list("{table}")'):
                        self.assertEqual(index[2], 1, (table, index[1]))
                        columns = tuple(
                            row[2]
                            for row in connection.execute(
                                f'PRAGMA index_info("{index[1]}")'
                            )
                        )
                        actual_unique_indexes[columns] = index[3]
                    self.assertEqual(
                        actual_unique_indexes,
                        DISCOVERY_UNIQUE_INDEXES[table],
                        table,
                    )

    def test_discovery_ddl_executes_inside_the_v5_migration_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            create_v4_registry(database)
            with closing(
                sqlite3.connect(database, factory=TrackingConnection)
            ) as connection:
                research_director_common.ensure_director_schema(connection)
                self.assertEqual(
                    connection.discovery_ddl_transaction_states,
                    [True] * len(DISCOVERY_TABLES),
                )
                self.assertFalse(connection.in_transaction)

    def test_mid_migration_ddl_failure_rolls_back_all_v5_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            create_v4_registry(database)
            with closing(sqlite3.connect(database)) as connection:
                def deny_critique_table(action, argument, _arg2, _database, _source):
                    if (
                        action == sqlite3.SQLITE_CREATE_TABLE
                        and argument == "research_discovery_critiques"
                    ):
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK

                connection.set_authorizer(deny_critique_table)
                with self.assertRaises(sqlite3.DatabaseError):
                    research_director_common.ensure_director_schema(connection)
                connection.set_authorizer(None)

                self.assertFalse(connection.in_transaction)
                self.assertEqual(discovery_table_names(connection), set())
                self.assertEqual(
                    [row[0] for row in connection.execute(
                        "SELECT version FROM director_schema_migrations ORDER BY version"
                    )],
                    [4],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT recommendation FROM director_runs WHERE run_id='legacy-run'"
                    ).fetchone()[0],
                    "no_research_recommended",
                )
                self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)

    def test_v5_migration_row_failure_rolls_back_all_discovery_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            create_v4_registry(database)
            with closing(
                sqlite3.connect(database, factory=TrackingConnection)
            ) as connection:
                connection.fail_migration_insert = True
                with self.assertRaisesRegex(
                    sqlite3.OperationalError,
                    "injected v5 migration insert failure",
                ):
                    research_director_common.ensure_director_schema(connection)

                self.assertFalse(connection.in_transaction)
                self.assertEqual(discovery_table_names(connection), set())
                self.assertEqual(
                    [row[0] for row in connection.execute(
                        "SELECT version FROM director_schema_migrations ORDER BY version"
                    )],
                    [4],
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT recommendation FROM director_runs WHERE run_id='legacy-run'"
                    ).fetchone()[0],
                    "no_research_recommended",
                )
                self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)

    def test_non_sqlite_migration_failure_is_rolled_back_and_propagated(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            create_v4_registry(database)
            with closing(
                sqlite3.connect(database, factory=TrackingConnection)
            ) as connection:
                connection.fail_schema_validation = True
                with self.assertRaisesRegex(
                    RuntimeError,
                    "injected schema validation failure",
                ):
                    research_director_common.ensure_director_schema(connection)

                self.assertFalse(connection.in_transaction)
                self.assertEqual(discovery_table_names(connection), set())
                self.assertEqual(
                    [row[0] for row in connection.execute(
                        "SELECT version FROM director_schema_migrations ORDER BY version"
                    )],
                    [4],
                )

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

    def test_nonempty_registry_exports_are_complete_counted_and_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            insert_discovery_export_rows(connection)
            connection.commit()
            connection.close()

            public_first = export_registry(str(database))
            public_second = export_registry(str(database))
            helper_first = director_registry_export(database)
            helper_second = director_registry_export(database)

            self.assertEqual(public_first, public_second)
            self.assertEqual(helper_first, helper_second)
            self.assertEqual(
                json.dumps(public_first, sort_keys=True, separators=(",", ":")),
                json.dumps(public_second, sort_keys=True, separators=(",", ":")),
            )
            for table, fixture_rows in DISCOVERY_EXPORT_ROWS.items():
                public_rows = public_first["tables"][table]
                helper_rows = helper_first[table]
                expected_columns = [column[0] for column in DISCOVERY_SCHEMA[table]]
                self.assertEqual(public_first["counts"][table], len(public_rows), table)
                self.assertEqual(len(public_rows), len(fixture_rows), table)
                self.assertEqual(
                    [row[expected_columns[0]] for row in public_rows],
                    sorted(row[0] for row in fixture_rows),
                    table,
                )
                self.assertEqual(
                    [row[expected_columns[0]] for row in helper_rows],
                    [row[0] for row in fixture_rows],
                    table,
                )
                for row in public_rows:
                    self.assertEqual(list(row), expected_columns, table)
                    self.assertIsInstance(json.loads(row["payload_json"]), dict, table)

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
            connection.execute(
                "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "discovery-run-2",
                    "trigger-fingerprint-2",
                    "no_research_recommended",
                    "state-fingerprint-2",
                    "{}",
                    "2026-07-14T00:01:00+00:00",
                ),
            )
            connection.execute(
                "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "discovery-run-3",
                    "trigger-fingerprint-3",
                    "running",
                    "state-fingerprint-3",
                    "{}",
                    "2026-07-14T00:02:00+00:00",
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ("idea-key-z", "discovery-run-1", "idea-z", 2, "semantic-z", "family-z", "shortlisted", "{}", "2026-07-14T00:04:00+00:00"),
                    ("idea-key-a", "discovery-run-2", "idea-a", 1, "semantic-a", "family-a", "proposed", "{}", "2026-07-14T00:04:00+00:00"),
                    ("idea-key-m", "discovery-run-3", "idea-m", 1, "semantic-m", "family-m", "rejected", "{}", "2026-07-14T00:03:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_handoffs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ("handoff-1", "discovery-run-1", "idea-z", "director_rejected", "duplicate_research_question", "{}", "2026-07-14T00:05:00+00:00"),
                    ("handoff-2", "discovery-run-2", "idea-a", "accepted", None, "{}", "2026-07-14T00:05:00+00:00"),
                ),
            )
            connection.commit()
            connection.close()

            state = build_state(ROOT, director_registry=database)
            summary = state["research_discovery"]
            self.assertEqual(summary["completed_runs"], 2)
            self.assertEqual(summary["director_rejections"], 1)
            self.assertEqual(
                [idea["idea_id"] for idea in summary["recent_ideas"]],
                ["idea-a", "idea-z", "idea-m"],
            )
            self.assertEqual(
                [idea["semantic_fingerprint"] for idea in summary["recent_ideas"]],
                ["semantic-a", "semantic-z", "semantic-m"],
            )

            unavailable_state = build_state(ROOT)
            self.assertFalse(unavailable_state["research_discovery"]["available"])

    def test_discovery_summary_closes_connection_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            connection.close()
            observed = ObservedConnection(sqlite3.connect(database))

            with mock.patch.object(
                research_director_common.sqlite3,
                "connect",
                return_value=observed,
            ):
                summary = research_director_common.discovery_registry_summary(database)

            self.assertTrue(summary["available"])
            self.assertTrue(observed.closed)
            with self.assertRaises(sqlite3.ProgrammingError):
                observed.execute("SELECT 1")

    def test_discovery_summary_closes_connection_after_partial_schema_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, schema, message in (
                (
                    "missing-column.db",
                    "CREATE TABLE research_discovery_runs (run_id TEXT PRIMARY KEY)",
                    "no such column: status",
                ),
                (
                    "missing-table.db",
                    "CREATE TABLE research_discovery_runs (run_id TEXT PRIMARY KEY, status TEXT)",
                    "no such table: research_discovery_handoffs",
                ),
            ):
                with self.subTest(name=name):
                    database = Path(directory) / name
                    setup = sqlite3.connect(database)
                    setup.execute(schema)
                    setup.commit()
                    setup.close()
                    observed = ObservedConnection(sqlite3.connect(database))
                    try:
                        with mock.patch.object(
                            research_director_common.sqlite3,
                            "connect",
                            return_value=observed,
                        ):
                            with self.assertRaisesRegex(sqlite3.OperationalError, message):
                                research_director_common.discovery_registry_summary(database)

                        self.assertTrue(observed.closed)
                        with self.assertRaises(sqlite3.ProgrammingError):
                            observed.execute("SELECT 1")
                    finally:
                        if not observed.closed:
                            observed.close()


if __name__ == "__main__":
    unittest.main()
