import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seal_dataset_snapshot import aggregate_hash, seal_snapshot  # noqa: E402
from run_experiment import sha256_file  # noqa: E402


class DatasetSnapshotSealingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dataset-seal-test-"))
        self.staging = self.tmp / "staging"
        self.staging.mkdir()

    def tearDown(self):
        for path in self.tmp.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o666)
        shutil.rmtree(self.tmp)

    def write_json_data(self, rows=None):
        rows = rows or [
            {"date": "2024-01-01T00:00:00+00:00", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10},
            {"date": "2024-01-31T00:00:00+00:00", "open": 2, "high": 3, "low": 2, "close": 3, "volume": 11},
        ]
        path = self.staging / "BTC_USDT-1h.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def test_empty_dataset_rejected(self):
        with self.assertRaisesRegex(ValueError, "no data file"):
            seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")

    def test_empty_file_rejected(self):
        (self.staging / "BTC_USDT-1h.json").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "empty dataset file"):
            seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")

    def test_manifest_hashes_and_aggregate(self):
        self.write_json_data()
        manifest = seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")
        self.assertTrue(manifest["sealed"])
        self.assertEqual(len(manifest["files"]), 1)
        copied = self.tmp / manifest["files"][0]["path"]
        self.assertEqual(manifest["files"][0]["sha256"], sha256_file(copied))
        self.assertEqual(manifest["aggregate_sha256"], aggregate_hash(manifest["files"]))
        self.assertEqual(manifest["coverage"][0]["rows"], 2)

    def test_forbidden_file_rejected(self):
        self.write_json_data()
        (self.staging / ".env").write_text("SECRET=x\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")

    def test_timerange_coverage_required(self):
        self.write_json_data(rows=[{"date": "2024-02-01T00:00:00+00:00"}])
        with self.assertRaisesRegex(ValueError, "do not cover"):
            seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")

    def test_futures_mark_and_funding_rate_files_are_sealed(self):
        futures_dir = self.staging / "futures"
        futures_dir.mkdir()
        rows = [
            {"date": "2024-01-01T00:00:00+00:00", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10},
            {"date": "2024-01-31T23:00:00+00:00", "open": 2, "high": 3, "low": 2, "close": 3, "volume": 11},
        ]
        for name in ("BTC_USDT_USDT-1h-futures.json", "BTC_USDT_USDT-1h-mark.json", "BTC_USDT_USDT-8h-funding_rate.json"):
            (futures_dir / name).write_text(json.dumps(rows), encoding="utf-8")
        manifest = seal_snapshot(
            self.tmp,
            self.staging,
            "demo-futures",
            "binance",
            "futures",
            "BTC/USDT:USDT",
            "1h",
            "20240101-20240131",
            "unit",
            margin_mode="isolated",
            candle_types=["futures", "mark", "funding_rate"],
            execution_baseline_only=True,
            suitable_for_strategy_ranking=False,
        )
        self.assertEqual(len(manifest["files"]), 3)
        self.assertEqual(manifest["candle_types"], ["futures", "mark", "funding_rate"])
        self.assertFalse(manifest["suitable_for_strategy_ranking"])

    def test_reseal_removes_readonly_snapshot_files(self):
        self.write_json_data()
        seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")
        manifest = seal_snapshot(self.tmp, self.staging, "demo", "binance", "spot", "BTC/USDT", "1h", "20240101-20240131", "unit")
        self.assertTrue(manifest["sealed"])


if __name__ == "__main__":
    unittest.main()
