from __future__ import annotations

import json
import os
import sqlite3
import stat
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import portable_baseline_fixtures as fixtures
from portable_baseline_support import TemporaryRegistry


class PortableBaselineFixtureTest(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.get("PORTABLE_BASELINE_PACK_ROOT")
        os.environ["PORTABLE_BASELINE_PACK_ROOT"] = str((ROOT / fixtures.HYDRATED_PACK).resolve())

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("PORTABLE_BASELINE_PACK_ROOT", None)
        else:
            os.environ["PORTABLE_BASELINE_PACK_ROOT"] = self.previous

    def test_contract_has_no_absolute_asset_root(self):
        contract = fixtures.load_contract(ROOT)
        self.assertFalse(contract["mutable_during_test"])
        self.assertTrue(contract["absolute_paths_forbidden"])
        self.assertNotIn("authoritative_asset_root", contract)

    def test_committed_pack_manifest_and_semantic_fingerprints(self):
        result = fixtures.verify(ROOT / fixtures.COMMITTED_PACK, require_readonly=False)
        self.assertEqual(result["status"], "passed")
        manifest = json.loads((ROOT / fixtures.COMMITTED_PACK / fixtures.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertTrue(all(row["sha256"] == row["semantic_fingerprint"] for row in manifest["files"]))

    def test_missing_pack_has_explicit_reason_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(fixtures.PortableFixtureError) as caught:
                fixtures.verify(Path(tmp) / "missing")
        self.assertEqual(caught.exception.reason_code, "portable_baseline_fixture_pack_missing")

    def test_hydration_is_readonly_and_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            first = fixtures.hydrate(ROOT, target)
            second = fixtures.hydrate(ROOT, target)
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
            for path in target.rglob("*"):
                if path.is_file():
                    self.assertFalse(path.stat().st_mode & stat.S_IWUSR)

    def test_extra_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pack"
            fixtures.hydrate(ROOT, target)
            (target / "undeclared.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(fixtures.PortableFixtureError) as caught:
                fixtures.verify(target)
        self.assertEqual(caught.exception.reason_code, "portable_baseline_fixture_extra_file")

    def test_symlink_or_junction_is_rejected(self):
        with mock.patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(fixtures.PortableFixtureError) as caught:
                fixtures.verify(ROOT / fixtures.COMMITTED_PACK, require_readonly=False)
        self.assertEqual(caught.exception.reason_code, "portable_baseline_symlink_forbidden")

    def test_parallel_hydration_targets_do_not_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = [Path(tmp) / "a", Path(tmp) / "b"]
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda target: fixtures.hydrate(ROOT, target), targets))
            self.assertEqual(results[0]["manifest_sha256"], results[1]["manifest_sha256"])
            self.assertNotEqual(results[0]["pack"], results[1]["pack"])

    def test_temporary_registry_imports_minimal_rows(self):
        registry = TemporaryRegistry()
        try:
            connection = sqlite3.connect(registry.path)
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM stage3d4b_variable_governance_events").fetchone()[0], 4)
            connection.close()
        finally:
            registry.cleanup()

    def test_fixture_content_has_no_absolute_paths_or_sensitive_material(self):
        result = fixtures.verify(ROOT / fixtures.HYDRATED_PACK)
        self.assertEqual(result["file_count"], 8)

    def test_hydrated_fixture_cannot_be_modified(self):
        path = ROOT / fixtures.HYDRATED_PACK / "stage3c2r-final-report.json"
        self.assertFalse(path.stat().st_mode & stat.S_IWUSR)
        if os.name == "nt":
            with self.assertRaises(PermissionError):
                path.write_text("mutation", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
