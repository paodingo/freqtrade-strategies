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


REAL_SQLITE_CONNECT = sqlite3.connect


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


class CloseTrackingConnection(sqlite3.Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.close_called = False

    def close(self):
        self.close_called = True
        super().close()


class ObservedConnection:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.closed = False
        self.statements: list[str] = []

    @property
    def row_factory(self):
        return self.connection.row_factory

    @row_factory.setter
    def row_factory(self, value):
        self.connection.row_factory = value

    def execute(self, sql, parameters=()):
        self.statements.append(" ".join(sql.split()))
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

MALFORMED_DISCOVERY_TABLES = (
    (
        "missing-column.db",
        "research_discovery_runs",
        "column_names",
        """CREATE TABLE research_discovery_runs (
          run_id TEXT PRIMARY KEY,
          trigger_fingerprint TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL,
          state_fingerprint TEXT NOT NULL,
          payload_json TEXT NOT NULL
        )""",
    ),
    (
        "wrong-primary-key.db",
        "research_discovery_approvals",
        "primary_key",
        """CREATE TABLE research_discovery_approvals (
          approval_fingerprint TEXT,
          run_id TEXT NOT NULL,
          decision TEXT NOT NULL,
          selected_idea_id TEXT,
          payload_json TEXT NOT NULL,
          decided_at TEXT NOT NULL
        )""",
    ),
    (
        "missing-unique.db",
        "research_discovery_critiques",
        "unique_constraints",
        """CREATE TABLE research_discovery_critiques (
          critique_id TEXT PRIMARY KEY,
          run_id TEXT NOT NULL,
          idea_key TEXT NOT NULL,
          verdict TEXT NOT NULL,
          critic_fingerprint TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        )""",
    ),
)


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

    def test_public_open_rejects_malformed_discovery_schema_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            for filename, malformed_table, category, malformed_ddl in MALFORMED_DISCOVERY_TABLES:
                with self.subTest(category=category):
                    database = Path(directory) / filename
                    create_v4_registry(database)
                    setup = REAL_SQLITE_CONNECT(database)
                    setup.execute(malformed_ddl)
                    setup.commit()
                    setup.close()
                    observed_connections: list[CloseTrackingConnection] = []

                    def tracked_connect(*args, **kwargs):
                        kwargs["factory"] = CloseTrackingConnection
                        connection = REAL_SQLITE_CONNECT(*args, **kwargs)
                        observed_connections.append(connection)
                        return connection

                    try:
                        with mock.patch.object(
                            research_director_common.sqlite3,
                            "connect",
                            side_effect=tracked_connect,
                        ):
                            with self.assertRaisesRegex(
                                RuntimeError,
                                rf"research discovery schema mismatch: table={malformed_table} category={category}",
                            ) as raised:
                                open_director_registry(database)

                        self.assertEqual(
                            type(raised.exception).__name__,
                            "DirectorSchemaMismatchError",
                        )
                        self.assertEqual(len(observed_connections), 1)
                        self.assertTrue(observed_connections[0].close_called)
                        with self.assertRaises(sqlite3.ProgrammingError):
                            observed_connections[0].execute("SELECT 1")

                        with closing(REAL_SQLITE_CONNECT(database)) as check:
                            self.assertEqual(
                                discovery_table_names(check),
                                {malformed_table},
                            )
                            self.assertEqual(
                                [row[0] for row in check.execute(
                                    "SELECT version FROM director_schema_migrations ORDER BY version"
                                )],
                                [4],
                            )
                            self.assertEqual(
                                check.execute(
                                    "SELECT recommendation FROM director_runs WHERE run_id='legacy-run'"
                                ).fetchone()[0],
                                "no_research_recommended",
                            )
                        database.unlink()
                        self.assertFalse(database.exists())
                    finally:
                        for connection in observed_connections:
                            if not connection.close_called:
                                connection.close()

    def test_public_open_rejects_partial_unique_index_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "partial-unique.db"
            create_v4_registry(database)
            setup = REAL_SQLITE_CONNECT(database)
            setup.executescript(
                """
                CREATE TABLE research_discovery_critiques (
                  critique_id TEXT PRIMARY KEY,
                  run_id TEXT NOT NULL,
                  idea_key TEXT NOT NULL,
                  verdict TEXT NOT NULL,
                  critic_fingerprint TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX partial_critic_fingerprint
                ON research_discovery_critiques(critic_fingerprint)
                WHERE verdict='accept';
                """
            )
            duplicate_rows = (
                ("critique-1", "run-1", "idea-1", "revise", "same-fingerprint", "{}", "2026-07-14T01:00:00+00:00"),
                ("critique-2", "run-2", "idea-2", "revise", "same-fingerprint", "{}", "2026-07-14T01:01:00+00:00"),
            )
            setup.executemany(
                "INSERT INTO research_discovery_critiques VALUES (?, ?, ?, ?, ?, ?, ?)",
                duplicate_rows,
            )
            setup.commit()
            self.assertEqual(
                setup.execute(
                    "SELECT COUNT(*) FROM research_discovery_critiques "
                    "WHERE critic_fingerprint='same-fingerprint'"
                ).fetchone()[0],
                2,
            )
            setup.close()
            observed_connections: list[CloseTrackingConnection] = []

            def tracked_connect(*args, **kwargs):
                kwargs["factory"] = CloseTrackingConnection
                connection = REAL_SQLITE_CONNECT(*args, **kwargs)
                observed_connections.append(connection)
                return connection

            try:
                with mock.patch.object(
                    research_director_common.sqlite3,
                    "connect",
                    side_effect=tracked_connect,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "research discovery schema mismatch: "
                        "table=research_discovery_critiques category=unique_constraints",
                    ) as raised:
                        open_director_registry(database)

                self.assertEqual(
                    type(raised.exception).__name__,
                    "DirectorSchemaMismatchError",
                )
                self.assertEqual(len(observed_connections), 1)
                self.assertTrue(observed_connections[0].close_called)
                with self.assertRaises(sqlite3.ProgrammingError):
                    observed_connections[0].execute("SELECT 1")

                with closing(REAL_SQLITE_CONNECT(database)) as check:
                    self.assertEqual(
                        discovery_table_names(check),
                        {"research_discovery_critiques"},
                    )
                    self.assertEqual(
                        [row[0] for row in check.execute(
                            "SELECT version FROM director_schema_migrations ORDER BY version"
                        )],
                        [4],
                    )
                    self.assertEqual(
                        check.execute(
                            "SELECT recommendation FROM director_runs WHERE run_id='legacy-run'"
                        ).fetchone()[0],
                        "no_research_recommended",
                    )
                    self.assertEqual(
                        check.execute(
                            "SELECT COUNT(*) FROM research_discovery_critiques "
                            "WHERE critic_fingerprint='same-fingerprint'"
                        ).fetchone()[0],
                        2,
                    )
                database.unlink()
                self.assertFalse(database.exists())
            finally:
                for connection in observed_connections:
                    if not connection.close_called:
                        connection.close()

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
                    ("handoff-1", "discovery-run-1", "idea-z", "director_rejected", "duplicate_research_question", '{"discovery_run_id":"discovery-run-1","handoff_fingerprint":"handoff-1","idea_ref":"research/discovery/runs/discovery-run-1/ideas/idea-z-v2.json","idea_fingerprint":"semantic-z"}', "2026-07-14T00:05:00+00:00"),
                    ("handoff-2", "discovery-run-2", "idea-a", "accepted", None, '{"discovery_run_id":"discovery-run-2","handoff_fingerprint":"handoff-2","idea_ref":"research/discovery/runs/discovery-run-2/ideas/idea-a-v1.json","idea_fingerprint":"semantic-a"}', "2026-07-14T00:05:00+00:00"),
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

    def test_discovery_summary_projects_append_only_lifecycle_without_double_counting(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            connection.executemany(
                "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    ("run-live", "trigger-live", "awaiting_researcher", "state-live", "{}", "2026-07-15T00:00:00+00:00"),
                    ("run-legacy", "trigger-legacy", "completed", "state-legacy", "{}", "2026-07-14T00:00:00+00:00"),
                    ("run-status-only", "trigger-status-only", "no_research_recommended", "state-status-only", "{}", "2026-07-13T12:00:00+00:00"),
                    ("run-rejected", "trigger-rejected", "awaiting_researcher", "state-rejected", "{}", "2026-07-13T00:00:00+00:00"),
                    ("run-deferred", "trigger-deferred", "awaiting_researcher", "state-deferred", "{}", "2026-07-12T00:00:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ("live-a-v2", "run-live", "live-a", 2, "semantic-live-a-v2", "family-a", "discovered", '{"idea_id":"live-a","idea_version":2}', "2026-07-15T00:04:00+00:00"),
                    ("live-a-v1", "run-live", "live-a", 1, "semantic-live-a-v1", "family-a", "discovered", '{"idea_id":"live-a","idea_version":1}', "2026-07-15T00:03:30+00:00"),
                    ("live-b-v1", "run-live", "live-b", 1, "semantic-live-b", "family-b", "discovered", '{"idea_id":"live-b"}', "2026-07-15T00:03:00+00:00"),
                    ("live-c-v1", "run-live", "live-c", 1, "semantic-live-c", "family-c", "discovered", '{"idea_id":"live-c"}', "2026-07-15T00:02:00+00:00"),
                    ("reject-v1", "run-rejected", "reject-me", 1, "semantic-reject", "family-r", "discovered", '{"idea_id":"reject-me"}', "2026-07-13T00:02:00+00:00"),
                    ("defer-v1", "run-deferred", "defer-me", 1, "semantic-defer", "family-d", "discovered", '{"idea_id":"defer-me"}', "2026-07-12T00:02:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_critiques VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ("crit-live-a-v2", "run-live", "live-a-v2", "pass", "critic-live-a-v2", '{"idea_semantic_fingerprint":"semantic-live-a-v2","verdict":"pass"}', "2026-07-15T00:05:30+00:00"),
                    ("crit-live-a-v1", "run-live", "live-a-v1", "pass", "critic-live-a-v1", '{"idea_semantic_fingerprint":"semantic-live-a-v1","verdict":"pass"}', "2026-07-15T00:05:00+00:00"),
                    ("crit-live-b", "run-live", "live-b-v1", "reject", "critic-live-b", '{"idea_semantic_fingerprint":"semantic-live-b","verdict":"reject"}', "2026-07-15T00:05:00+00:00"),
                    ("crit-live-c", "run-live", "live-c-v1", "pass", "critic-live-c", '{"idea_semantic_fingerprint":"semantic-live-c","verdict":"pass"}', "2026-07-15T00:05:00+00:00"),
                    ("crit-reject", "run-rejected", "reject-v1", "pass", "critic-reject", '{"idea_semantic_fingerprint":"semantic-reject","verdict":"pass"}', "2026-07-13T00:03:00+00:00"),
                    ("crit-defer", "run-deferred", "defer-v1", "pass", "critic-defer", '{"idea_semantic_fingerprint":"semantic-defer","verdict":"pass"}', "2026-07-12T00:03:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_shortlists VALUES (?, ?, ?, ?, ?)",
                (
                    ("run-live", "short-live", "research_recommended", '{"shortlist_fingerprint":"short-live","ranked_ideas":[{"idea_id":"live-a","idea_fingerprint":"semantic-live-a-v2","critique_fingerprint":"critic-live-a-v2"},{"idea_id":"live-c","idea_fingerprint":"semantic-live-c","critique_fingerprint":"critic-live-c"}]}', "2026-07-15T00:06:00+00:00"),
                    ("run-rejected", "short-reject", "research_recommended", '{"shortlist_fingerprint":"short-reject","ranked_ideas":[{"idea_id":"reject-me","idea_fingerprint":"semantic-reject","critique_fingerprint":"critic-reject"}]}', "2026-07-13T00:04:00+00:00"),
                    ("run-deferred", "short-defer", "research_recommended", '{"shortlist_fingerprint":"short-defer","ranked_ideas":[{"idea_id":"defer-me","idea_fingerprint":"semantic-defer","critique_fingerprint":"critic-defer"}]}', "2026-07-12T00:04:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_approvals VALUES (?, ?, ?, ?, ?, ?)",
                (
                    ("approval-live", "run-live", "approved_for_director_handoff", "live-a", '{"approval_fingerprint":"approval-live","decision":"approved_for_director_handoff","selected_idea_id":"live-a","selected_idea_fingerprint":"semantic-live-a-v2","selected_critique_fingerprint":"critic-live-a-v2","shortlist_fingerprint":"short-live"}', "2026-07-15T00:07:00+00:00"),
                    ("approval-reject", "run-rejected", "approved_for_director_handoff", "reject-me", '{"approval_fingerprint":"approval-reject","decision":"approved_for_director_handoff","selected_idea_id":"reject-me","selected_idea_fingerprint":"semantic-reject","selected_critique_fingerprint":"critic-reject","shortlist_fingerprint":"short-reject"}', "2026-07-13T00:05:00+00:00"),
                    ("approval-defer", "run-deferred", "deferred", None, '{"approval_fingerprint":"approval-defer","decision":"deferred","selected_idea_id":null,"selected_idea_fingerprint":null,"selected_critique_fingerprint":null,"shortlist_fingerprint":"short-defer"}', "2026-07-12T00:05:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_handoffs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    ("handoff-live", "run-live", "live-a", "director_proposed", "proposal_created", '{"discovery_run_id":"run-live","handoff_fingerprint":"handoff-live","idea_ref":"research/discovery/runs/run-live/ideas/live-a-v2.json","idea_fingerprint":"semantic-live-a-v2","critique_fingerprint":"critic-live-a-v2","approval_fingerprint":"approval-live","shortlist_fingerprint":"short-live"}', "2026-07-15T00:08:00+00:00"),
                    ("handoff-rejected", "run-rejected", "reject-me", "director_rejected", "closed_branch_no_reopen_evidence", '{"discovery_run_id":"run-rejected","handoff_fingerprint":"handoff-rejected","idea_ref":"research/discovery/runs/run-rejected/ideas/reject-me-v1.json","idea_fingerprint":"semantic-reject","critique_fingerprint":"critic-reject","approval_fingerprint":"approval-reject","shortlist_fingerprint":"short-reject"}', "2026-07-13T00:06:00+00:00"),
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    ("completed-live", "run-live", "completed", None, "{}", "2026-07-15T00:09:00+00:00"),
                    ("completed-legacy", "run-legacy", "completed", None, "{}", "2026-07-14T00:09:00+00:00"),
                ),
            )
            connection.commit()
            connection.close()

            state = build_state(ROOT, director_registry=database)
            summary = state["research_discovery"]
            self.assertEqual(summary["completed_runs"], 3)
            statuses = {
                (idea["idea_id"], idea["idea_version"]): idea["status"]
                for idea in summary["recent_ideas"]
            }
            self.assertEqual(
                statuses,
                {
                    ("live-a", 2): "converted",
                    ("live-a", 1): "criticized",
                    ("live-b", 1): "critic_rejected",
                    ("live-c", 1): "shortlisted",
                    ("reject-me", 1): "director_rejected",
                    ("defer-me", 1): "deferred",
                },
            )

    def test_discovery_summary_rejects_duplicate_completed_events_for_one_run(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            connection.execute(
                "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "run-duplicate-completed",
                    "trigger-duplicate-completed",
                    "awaiting_researcher",
                    "state-duplicate-completed",
                    "{}",
                    "2026-07-15T00:00:00+00:00",
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    ("completed-1", "run-duplicate-completed", "completed", None, "{}", "2026-07-15T00:01:00+00:00"),
                    ("completed-2", "run-duplicate-completed", "completed", None, "{}", "2026-07-15T00:02:00+00:00"),
                ),
            )
            connection.commit()
            connection.close()

            with self.assertRaisesRegex(ValueError, "duplicate completed event"):
                research_director_common.discovery_registry_summary(database)

    def test_discovery_summary_never_skips_exact_selection_chain(self):
        cases = (
            ("wrong_critique_fingerprint", ["idea-a"], "idea-a", {"idea-a": "criticized", "idea-b": "criticized"}),
            ("handoff_nonranked", ["idea-a"], "idea-b", {"idea-a": "human_approved", "idea-b": "criticized"}),
            ("handoff_different_selected", ["idea-a", "idea-b"], "idea-b", {"idea-a": "human_approved", "idea-b": "shortlisted"}),
            ("wrong_approval_critique", ["idea-a"], "idea-a", {"idea-a": "shortlisted", "idea-b": "criticized"}),
            ("wrong_approval_shortlist", ["idea-a"], "idea-a", {"idea-a": "shortlisted", "idea-b": "criticized"}),
            ("wrong_handoff_approval", ["idea-a"], "idea-a", {"idea-a": "human_approved", "idea-b": "criticized"}),
            ("wrong_handoff_shortlist", ["idea-a"], "idea-a", {"idea-a": "human_approved", "idea-b": "criticized"}),
            ("wrong_handoff_critique", ["idea-a"], "idea-a", {"idea-a": "human_approved", "idea-b": "criticized"}),
            ("rejected_with_selection", ["idea-a"], "idea-a", {"idea-a": "shortlisted", "idea-b": "criticized"}),
            ("deferred_with_selection", ["idea-a"], "idea-a", {"idea-a": "shortlisted", "idea-b": "criticized"}),
        )
        for case, ranked_ids, handoff_idea, expected in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                database = Path(directory) / "director.db"
                connection = open_director_registry(database)
                connection.execute(
                    "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                    ("run-chain", "trigger-chain", "awaiting_researcher", "state-chain", "{}", "2026-07-15T00:00:00+00:00"),
                )
                connection.executemany(
                    "INSERT INTO research_discovery_ideas VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        ("idea-a-v1", "run-chain", "idea-a", 1, "semantic-a", "family-a", "discovered", '{"idea_id":"idea-a"}', "2026-07-15T00:02:00+00:00"),
                        ("idea-b-v1", "run-chain", "idea-b", 1, "semantic-b", "family-b", "discovered", '{"idea_id":"idea-b"}', "2026-07-15T00:01:00+00:00"),
                    ),
                )
                connection.executemany(
                    "INSERT INTO research_discovery_critiques VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        ("crit-a", "run-chain", "idea-a-v1", "pass", "critic-a", '{"idea_semantic_fingerprint":"semantic-a","verdict":"pass"}', "2026-07-15T00:03:00+00:00"),
                        ("crit-b", "run-chain", "idea-b-v1", "pass", "critic-b", '{"idea_semantic_fingerprint":"semantic-b","verdict":"pass"}', "2026-07-15T00:03:00+00:00"),
                    ),
                )
                ranked = [
                    {
                        "idea_id": idea_id,
                        "idea_fingerprint": "semantic-a" if idea_id == "idea-a" else "semantic-b",
                        "critique_fingerprint": "critic-a" if idea_id == "idea-a" else "critic-b",
                    }
                    for idea_id in ranked_ids
                ]
                if case == "wrong_critique_fingerprint":
                    ranked[0]["critique_fingerprint"] = "wrong-critic"
                shortlist_payload = {
                    "shortlist_fingerprint": "shortlist-fp",
                    "ranked_ideas": ranked,
                }
                connection.execute(
                    "INSERT INTO research_discovery_shortlists VALUES (?, ?, ?, ?, ?)",
                    ("run-chain", "shortlist-fp", "research_recommended", json.dumps(shortlist_payload, sort_keys=True), "2026-07-15T00:04:00+00:00"),
                )
                approval_payload = {
                    "approval_fingerprint": "approval-fp",
                    "decision": "approved_for_director_handoff",
                    "selected_idea_id": "idea-a",
                    "selected_idea_fingerprint": "semantic-a",
                    "selected_critique_fingerprint": "critic-a",
                    "shortlist_fingerprint": "shortlist-fp",
                }
                approval_decision = "approved_for_director_handoff"
                if case in {"rejected_with_selection", "deferred_with_selection"}:
                    approval_decision = (
                        "rejected" if case == "rejected_with_selection" else "deferred"
                    )
                    approval_payload["decision"] = approval_decision
                if case == "wrong_approval_critique":
                    approval_payload["selected_critique_fingerprint"] = "wrong-critic"
                if case == "wrong_approval_shortlist":
                    approval_payload["shortlist_fingerprint"] = "wrong-shortlist"
                connection.execute(
                    "INSERT INTO research_discovery_approvals VALUES (?, ?, ?, ?, ?, ?)",
                    ("approval-fp", "run-chain", approval_decision, "idea-a", json.dumps(approval_payload, sort_keys=True), "2026-07-15T00:05:00+00:00"),
                )
                handoff_payload = {
                    "discovery_run_id": "run-chain",
                    "handoff_fingerprint": "handoff-fp",
                    "idea_ref": f"research/discovery/runs/run-chain/ideas/{handoff_idea}-v1.json",
                    "idea_fingerprint": "semantic-a" if handoff_idea == "idea-a" else "semantic-b",
                    "critique_fingerprint": "critic-a" if handoff_idea == "idea-a" else "critic-b",
                    "approval_fingerprint": "approval-fp",
                    "shortlist_fingerprint": "shortlist-fp",
                }
                if case == "wrong_handoff_approval":
                    handoff_payload["approval_fingerprint"] = "wrong-approval"
                if case == "wrong_handoff_shortlist":
                    handoff_payload["shortlist_fingerprint"] = "wrong-shortlist"
                if case == "wrong_handoff_critique":
                    handoff_payload["critique_fingerprint"] = "wrong-critic"
                connection.execute(
                    "INSERT INTO research_discovery_handoffs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("handoff-fp", "run-chain", handoff_idea, "director_proposed", "proposal_created", json.dumps(handoff_payload, sort_keys=True), "2026-07-15T00:06:00+00:00"),
                )
                connection.commit()
                connection.close()

                summary = research_director_common.discovery_registry_summary(database)
                self.assertEqual(
                    {idea["idea_id"]: idea["status"] for idea in summary["recent_ideas"]},
                    expected,
                )

    def test_discovery_summary_uses_sql_aggregation_for_large_completion_history(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "director.db"
            connection = open_director_registry(database)
            connection.executemany(
                "INSERT INTO research_discovery_runs VALUES (?, ?, ?, ?, ?, ?)",
                (
                    (
                        f"run-{index:03d}",
                        f"trigger-{index:03d}",
                        "completed" if index % 2 else "awaiting_researcher",
                        f"state-{index:03d}",
                        "{}",
                        f"2026-07-15T00:{index % 60:02d}:00+00:00",
                    )
                    for index in range(300)
                ),
            )
            connection.executemany(
                "INSERT INTO research_discovery_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    (
                        f"completed-{index:03d}",
                        f"run-{index:03d}",
                        "completed",
                        None,
                        "{}",
                        f"2026-07-15T01:{index % 60:02d}:00+00:00",
                    )
                    for index in range(0, 300, 2)
                ),
            )
            connection.commit()
            connection.close()
            observed = ObservedConnection(sqlite3.connect(database))
            with mock.patch.object(
                research_director_common.sqlite3,
                "connect",
                return_value=observed,
            ):
                summary = research_director_common.discovery_registry_summary(database)

            self.assertEqual(summary["completed_runs"], 300)
            sql = "\n".join(observed.statements).lower()
            self.assertIn("union", sql)
            self.assertIn("count(*)", sql)
            self.assertIn("having count(*) != 1", sql)
            self.assertIn("limit 1", sql)
            self.assertIn("json_valid", sql)
            self.assertNotIn("select run_id, status from research_discovery_runs", sql)

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
