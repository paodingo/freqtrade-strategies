from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import portable_runtime_assets as runtime
import run_ranging_short_temporal_campaign as campaign


class PortableRuntimeHydrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = runtime.load_manifest(ROOT)

    def test_manifest_fingerprint_versions_and_inventory(self):
        self.assertEqual(self.manifest["manifest_fingerprint"], "fa9bb13132dad44344e91d262c5fd38473e2cbed7a930e72f677eb7a0ce11f64")
        self.assertEqual(self.manifest["versions"], {"python": "3.12.13", "freqtrade": "2025.8", "ccxt": "4.5.64"})
        self.assertEqual(self.manifest["file_count"], 9550)
        self.assertEqual(self.manifest["total_bytes"], 277929435)
        self.assertEqual(len(self.manifest["files"]), self.manifest["file_count"])
        self.assertEqual(sum(item["bytes"] for item in self.manifest["files"]), self.manifest["total_bytes"])

    def test_manifest_covers_python_freqtrade_ccxt_and_package_data(self):
        components = {item["component"] for item in self.manifest["files"]}
        content_types = {item["content_type"] for item in self.manifest["files"]}
        self.assertTrue({"python_runtime_bootstrap", "freqtrade", "ccxt", "runtime_dependency_or_package_data"} <= components)
        self.assertTrue({"python_executable", "python_source", "native_runtime_binary", "package_metadata", "non_python_package_data"} <= content_types)
        targets = {item["repo_relative_target"] for item in self.manifest["files"]}
        self.assertIn(".venv-freqtrade/Scripts/python.exe", targets)
        self.assertIn(".venv-freqtrade/Lib/site-packages/freqtrade/__init__.py", targets)
        self.assertIn(".venv-freqtrade/Lib/site-packages/ccxt/__init__.py", targets)
        self.assertFalse(any("/__pycache__/" in target or target.endswith((".pyc", ".pyo")) for target in targets))

    def test_leverage_tier_source_and_hash_are_frozen(self):
        tier = self.manifest["leverage_tiers"]
        self.assertEqual(tier["source"], "D:/code/freqtrade-strategies-clean/.venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json")
        self.assertEqual(tier["repo_relative_target"], ".venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json")
        self.assertEqual(tier["bytes"], 2176158)
        self.assertEqual(tier["sha256"], runtime.LEVERAGE_TIER_SHA256)

    def _synthetic_manifest(self, repo: Path) -> dict:
        python_data = b"python"
        tier_data = b"tiers"
        files = [
            (Path("Scripts/python.exe"), python_data),
            (runtime.LEVERAGE_TIER_RELATIVE, tier_data),
        ]
        entries = []
        directories = set()
        for relative, data in files:
            path = repo / runtime.TARGET_ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            parent = relative.parent
            while parent != Path("."):
                directories.add(parent.as_posix())
                parent = parent.parent
            entries.append({"repo_relative_target": (runtime.TARGET_ROOT / relative).as_posix(), "source_relative_path": relative.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return {"manifest_fingerprint": "synthetic", "file_count": 2, "total_bytes": len(python_data) + len(tier_data), "directories": sorted(directories), "files": entries}

    def test_every_missing_asset_and_extra_file_fail_closed(self):
        for missing_index in range(2):
            with self.subTest(missing_index=missing_index), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                manifest = self._synthetic_manifest(repo)
                missing = repo / manifest["files"][missing_index]["repo_relative_target"]
                missing.unlink()
                with mock.patch.object(runtime, "LEVERAGE_TIER_BYTES", 5), mock.patch.object(runtime, "LEVERAGE_TIER_SHA256", hashlib.sha256(b"tiers").hexdigest()):
                    with self.assertRaisesRegex(runtime.PortableRuntimeError, "portable_runtime_file_set_mismatch"):
                        runtime.verify_runtime_files(repo, manifest)
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            manifest = self._synthetic_manifest(repo)
            (repo / runtime.TARGET_ROOT / "extra.txt").write_text("extra", encoding="utf-8")
            with mock.patch.object(runtime, "LEVERAGE_TIER_BYTES", 5), mock.patch.object(runtime, "LEVERAGE_TIER_SHA256", hashlib.sha256(b"tiers").hexdigest()):
                with self.assertRaisesRegex(runtime.PortableRuntimeError, "portable_runtime_file_set_mismatch"):
                    runtime.verify_runtime_files(repo, manifest)

    def test_unapproved_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(runtime.PortableRuntimeError, "unapproved_runtime_source"):
                runtime.verify_source(self.manifest, Path(temp))

    def test_campaign_preflight_stops_before_candidate_when_runtime_is_incomplete(self):
        with mock.patch.object(campaign, "require_portable_runtime", side_effect=campaign.TemporalExecutionInvalid("portable_runtime_preflight_failed:missing")), mock.patch.object(campaign.branch, "validate_candidate_ast") as candidate_ast:
            with self.assertRaisesRegex(campaign.TemporalExecutionInvalid, "portable_runtime_preflight_failed"):
                campaign.validate_authority(ROOT)
            candidate_ast.assert_not_called()

    def test_hydrated_runtime_file_closure_passes_when_present(self):
        if not (ROOT / runtime.TARGET_ROOT).is_dir():
            self.skipTest("ignored portable Runtime is not hydrated in this checkout")
        result = runtime.verify_runtime_files(ROOT, self.manifest)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["manifest_fingerprint"], self.manifest["manifest_fingerprint"])

    def test_original_stop_and_campaign_fingerprint_remain_unchanged(self):
        stopped = json.loads((ROOT / "research/analysis/ranging-short-temporal-review-v1/campaign-stopped.json").read_text(encoding="utf-8"))
        compiled = campaign.load_document(ROOT / campaign.CAMPAIGN_PATH)
        self.assertEqual((stopped["status"], stopped["reason_code"]), ("temporal_ablation_execution_invalid", "runtime_execution_asset_missing"))
        self.assertEqual(stopped["campaign_fingerprint"], campaign.CAMPAIGN_FINGERPRINT)
        self.assertEqual(compiled["campaign_fingerprint"], campaign.CAMPAIGN_FINGERPRINT)


if __name__ == "__main__":
    unittest.main()
