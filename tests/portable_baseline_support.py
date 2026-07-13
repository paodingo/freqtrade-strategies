from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path


ENVIRONMENT_VARIABLE = "PORTABLE_BASELINE_PACK_ROOT"


def active() -> bool:
    return bool(os.environ.get(ENVIRONMENT_VARIABLE))


def pack_root() -> Path:
    raw = os.environ.get(ENVIRONMENT_VARIABLE)
    if not raw:
        raise RuntimeError("portable_baseline_fixture_pack_missing")
    path = Path(raw)
    if not path.is_absolute() or not path.is_dir() or path.is_symlink():
        raise RuntimeError("portable_baseline_fixture_pack_missing")
    return path


def fixture_path(name: str) -> Path:
    path = pack_root() / name
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"portable_baseline_fixture_pack_missing: {name}")
    return path


def fixture_json(name: str):
    return json.loads(fixture_path(name).read_text(encoding="utf-8"))


class TemporaryRegistry:
    def __init__(self):
        self._temp = tempfile.TemporaryDirectory(prefix="portable-baseline-registry-")
        self.path = Path(self._temp.name) / "research.db"
        payload = fixture_json("stage3-registry-minimal.json")
        connection = sqlite3.connect(self.path)
        try:
            for table, record in payload["tables"].items():
                columns = record["columns"]
                connection.execute(record["create_sql"])
                if record["rows"]:
                    placeholders = ",".join("?" for _ in columns)
                    column_list = ",".join(f'"{column}"' for column in columns)
                    connection.executemany(f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})', record["rows"])
            connection.commit()
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            connection.close()

    def cleanup(self) -> None:
        self._temp.cleanup()
