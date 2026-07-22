import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import research_control_migration_manifest as migration  # noqa: E402


class ResearchControlMigrationManifestTests(unittest.TestCase):
    def _checkout(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
        (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)

    def test_exact_inventory_verifies_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._checkout(root)
            (root / "research").mkdir()
            evidence = root / "research" / "evidence.json"
            evidence.write_text("{}\n", encoding="utf-8")
            manifest = root / migration.DEFAULT_MANIFEST
            created = migration.create_manifest(root, manifest, "migration-test")
            verified = migration.verify_manifest(root, manifest)
            evidence.write_text('{"tampered":true}\n', encoding="utf-8")
            with self.assertRaises(migration.MigrationManifestError):
                migration.verify_manifest(root, manifest)

        self.assertEqual(created["file_count"], 2)
        self.assertEqual(verified["status"], "verified")

    def test_symlink_is_rejected_when_platform_supports_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._checkout(root)
            link = root / "linked.txt"
            try:
                link.symlink_to(root / "tracked.txt")
            except OSError:
                self.skipTest("symlink creation is unavailable")
            with self.assertRaises(migration.MigrationManifestError):
                migration.create_manifest(root, root / migration.DEFAULT_MANIFEST, "migration-test")


if __name__ == "__main__":
    unittest.main()
