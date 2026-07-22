import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_director_common import open_director_registry  # noqa: E402
import research_registry_backup as backup  # noqa: E402


class ResearchRegistryBackupTests(unittest.TestCase):
    def _registry(self, root: Path) -> Path:
        path = root / "stage4a-director.db"
        connection = open_director_registry(path)
        connection.execute(
            "INSERT INTO research_state_snapshots VALUES(?,?,?,?,?,?)",
            ("snapshot-1", "f" * 64, "a" * 40, "ready", "{}", "2026-07-21T00:00:00Z"),
        )
        connection.commit()
        connection.close()
        return path

    def test_online_backup_manifest_and_restore_drill_are_verified(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._registry(root)
            result = backup.create_backup(
                source,
                root / "backups",
                now=datetime(2026, 7, 21, tzinfo=timezone.utc),
            )
            manifest = Path(result["manifest_path"])
            verified = backup.verify_manifest(manifest)
            restored = root / "drill" / "restored.db"
            drill = backup.restore_drill(manifest, restored)

            connection = sqlite3.connect(restored)
            count = connection.execute("SELECT COUNT(*) FROM research_state_snapshots").fetchone()[0]
            connection.close()

        self.assertEqual(verified["status"], "verified")
        self.assertEqual(drill["status"], "restore_drill_passed")
        self.assertFalse(drill["live_registry_overwritten"])
        self.assertEqual(count, 1)

    def test_missing_source_fails_without_creating_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "missing.db"
            with self.assertRaises(backup.RegistryBackupError):
                backup.create_backup(source, Path(temporary) / "backups")
            self.assertFalse(source.exists())

    def test_tampered_backup_is_rejected_before_restore(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = backup.create_backup(self._registry(root), root / "backups")
            manifest = Path(result["manifest_path"])
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            backup_file = manifest.parent / payload["backup_file"]
            with backup_file.open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaises(backup.RegistryBackupError):
                backup.verify_manifest(manifest)

    def test_restore_drill_refuses_existing_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = backup.create_backup(self._registry(root), root / "backups")
            target = root / "existing.db"
            target.write_bytes(b"do-not-replace")
            with self.assertRaises(backup.RegistryBackupError):
                backup.restore_drill(Path(result["manifest_path"]), target)
            self.assertEqual(target.read_bytes(), b"do-not-replace")

    def test_prune_keeps_minimum_and_only_deletes_old_verified_pairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self._registry(root)
            backup_root = root / "backups"
            now = datetime(2026, 7, 21, tzinfo=timezone.utc)
            created = []
            for days_old in (60, 50, 40, 2):
                created.append(
                    backup.create_backup(
                        source,
                        backup_root,
                        now=now - timedelta(days=days_old),
                    )
                )
            unknown = backup_root / "operator-note.txt"
            unknown.write_text("keep", encoding="utf-8")
            result = backup.prune_backups(
                backup_root,
                keep_last=2,
                maximum_age_days=30,
                now=now,
            )

            remaining = list(backup_root.glob("*.manifest.json"))
            unknown_preserved = unknown.exists()

        self.assertEqual(len(result["deleted_backup_ids"]), 2)
        self.assertEqual(len(remaining), 2)
        self.assertTrue(result["unknown_files_deleted"] is False)
        self.assertTrue(unknown_preserved)


if __name__ == "__main__":
    unittest.main()
