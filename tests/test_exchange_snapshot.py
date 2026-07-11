import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from capture_exchange_snapshot import capture_snapshot, override_spot_public_api_urls  # noqa: E402
from validate_exchange_snapshot import SnapshotValidationError, aggregate_hash, validate_snapshot  # noqa: E402
from run_experiment import sha256_file  # noqa: E402


def make_capture_payload():
    return {
        "python_version": "3.12.13",
        "freqtrade_version": "2025.8",
        "ccxt_version": "4.5.64",
        "markets": {
            "BTC/USDT": {
                "id": "BTCUSDT",
                "symbol": "BTC/USDT",
                "base": "BTC",
                "quote": "USDT",
                "spot": True,
                "active": True,
                "precision": {"amount": 0.00001, "price": 0.01},
                "limits": {"amount": {"min": 0.00001}, "price": {"min": 0.01}},
                "maker": 0.001,
                "taker": 0.001,
            }
        },
        "currencies": {"BTC": {"code": "BTC"}, "USDT": {"code": "USDT"}},
        "options": {"defaultType": "spot", "fetchMarkets": {"types": ["spot"]}},
    }


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_yaml(path: Path, payload):
    lines = []
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{key}: {json.dumps(value, sort_keys=True)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ExchangeSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="exchange-snapshot-test-"))
        (self.tmp / ".venv-freqtrade" / "Scripts").mkdir(parents=True)
        self.python = self.tmp / ".venv-freqtrade" / "Scripts" / "python.exe"
        self.python.write_text("placeholder\n", encoding="utf-8")

    def tearDown(self):
        for path in self.tmp.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o666)
        shutil.rmtree(self.tmp)

    def test_capture_success_path(self):
        payload = make_capture_payload()
        with mock.patch("capture_exchange_snapshot.choose_endpoint", return_value=("https://api1.binance.com", {"ok": True, "selected_base_url": "https://api1.binance.com", "endpoints": []})), mock.patch("capture_exchange_snapshot.capture_with_runtime", return_value=(0, json.dumps(payload), "")):
            manifest = capture_snapshot(self.tmp, "demo", self.python)
        snapshot = self.tmp / "research" / "exchange_snapshots" / "demo"
        self.assertTrue((snapshot / "manifest.yaml").exists())
        self.assertEqual(manifest["markets_count"], 1)
        self.assertTrue(manifest["btc_usdt_exists"])
        validation = validate_snapshot(snapshot, "2025.8", "4.5.64", "3.12")
        self.assertTrue(validation["ok"], validation["issues"])

    def test_capture_network_failure_does_not_seal(self):
        with mock.patch("capture_exchange_snapshot.choose_endpoint", return_value=("https://api1.binance.com", {"ok": True, "selected_base_url": "https://api1.binance.com", "endpoints": []})), mock.patch("capture_exchange_snapshot.capture_with_runtime", return_value=(1, "", "timeout")):
            with self.assertRaisesRegex(RuntimeError, "load_markets failed"):
                capture_snapshot(self.tmp, "demo", self.python)
        snapshot = self.tmp / "research" / "exchange_snapshots" / "demo"
        self.assertTrue((snapshot / "capture.log").exists())
        self.assertFalse((snapshot / "manifest.yaml").exists())

    def test_secret_scan_rejects_snapshot(self):
        payload = make_capture_payload()
        payload["options"]["headers"] = {"Authorization": "secret"}
        with mock.patch("capture_exchange_snapshot.choose_endpoint", return_value=("https://api1.binance.com", {"ok": True, "selected_base_url": "https://api1.binance.com", "endpoints": []})), mock.patch("capture_exchange_snapshot.capture_with_runtime", return_value=(0, json.dumps(payload), "")):
            capture_snapshot(self.tmp, "demo", self.python)
        validation = validate_snapshot(self.tmp / "research" / "exchange_snapshots" / "demo", "2025.8", "4.5.64", "3.12")
        self.assertFalse(validation["ok"])
        self.assertIn("secret-like fields", "\n".join(validation["issues"]))

    def test_runtime_version_mismatch(self):
        payload = make_capture_payload()
        payload["ccxt_version"] = "0.0.0"
        with mock.patch("capture_exchange_snapshot.choose_endpoint", return_value=("https://api1.binance.com", {"ok": True, "selected_base_url": "https://api1.binance.com", "endpoints": []})), mock.patch("capture_exchange_snapshot.capture_with_runtime", return_value=(0, json.dumps(payload), "")):
            capture_snapshot(self.tmp, "demo", self.python)
        validation = validate_snapshot(self.tmp / "research" / "exchange_snapshots" / "demo", "2025.8", "4.5.64", "3.12")
        self.assertFalse(validation["ok"])
        self.assertIn("ccxt version mismatch", validation["issues"])

    def test_btc_usdt_missing_rejected(self):
        payload = make_capture_payload()
        payload["markets"] = {}
        with mock.patch("capture_exchange_snapshot.choose_endpoint", return_value=("https://api1.binance.com", {"ok": True, "selected_base_url": "https://api1.binance.com", "endpoints": []})), mock.patch("capture_exchange_snapshot.capture_with_runtime", return_value=(0, json.dumps(payload), "")):
            capture_snapshot(self.tmp, "demo", self.python)
        validation = validate_snapshot(self.tmp / "research" / "exchange_snapshots" / "demo", "2025.8", "4.5.64", "3.12")
        self.assertFalse(validation["ok"])
        self.assertIn("BTC/USDT market missing", validation["issues"])

    def test_futures_snapshot_validation_success(self):
        snapshot = self.tmp / "research" / "exchange_snapshots" / "futures"
        snapshot.mkdir(parents=True)
        market = {
            "id": "BTCUSDT",
            "symbol": "BTC/USDT:USDT",
            "base": "BTC",
            "quote": "USDT",
            "settle": "USDT",
            "spot": False,
            "swap": True,
            "linear": True,
            "contract": True,
            "contractSize": 1.0,
            "active": True,
            "precision": {"amount": 0.001, "price": 0.1},
            "limits": {"amount": {"min": 0.001}, "price": {"min": 0.1}},
        }
        write_json(snapshot / "markets.raw.json", {"BTC/USDT:USDT": market})
        write_json(snapshot / "markets.normalized.json", {"BTC/USDT:USDT": market})
        write_json(snapshot / "currencies.json", {"BTC": {"code": "BTC"}, "USDT": {"code": "USDT"}})
        write_json(snapshot / "options.json", {"defaultType": "swap"})
        write_json(snapshot / "artifact-hashes.json", {})
        write_json(snapshot / "fapi.exchangeInfo.raw.json", {"symbols": [{"symbol": "BTCUSDT"}]})
        write_json(snapshot / "leverage-tiers-contract.json", {"sha256": "abc123", "network_required": False})
        write_json(snapshot / "futures-scope-fingerprint.json", {"hash_domain": "ccxt_futures_research_scope_v1"})
        entries = []
        for path in sorted(snapshot.iterdir()):
            if path.is_file() and path.name != "manifest.yaml":
                entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        write_json(snapshot / "artifact-hashes.json", {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]} for item in entries})
        entries = []
        for path in sorted(snapshot.iterdir()):
            if path.is_file() and path.name != "manifest.yaml":
                entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        write_yaml(
            snapshot / "manifest.yaml",
            {
                "snapshot_id": "futures-unit",
                "exchange": "binance",
                "trading_mode": "futures",
                "python_version": "3.12.13",
                "ccxt_version": "4.5.64",
                "files": entries,
                "aggregate_sha256": aggregate_hash(entries),
                "sealed": True,
                "leverage_tier_artifact": {"sha256": "abc123", "network_required": False},
            },
        )
        validation = validate_snapshot(snapshot, None, "4.5.64", "3.12")
        self.assertTrue(validation["ok"], validation["issues"])

    def test_ccxt_public_url_override_preserves_private_urls(self):
        before = {
            "public": "https://api.binance.com/api/v3",
            "private": "https://api.binance.com/api/v3",
            "sapi": "https://api.binance.com/sapi/v1",
            "fapiPublic": "https://fapi.binance.com/fapi/v1",
        }
        original, after = override_spot_public_api_urls(before, "https://data-api.binance.vision")
        self.assertEqual(after["public"], "https://data-api.binance.vision/api/v3")
        self.assertEqual(after["private"], original["private"])
        self.assertEqual(after["sapi"], original["sapi"])
        self.assertEqual(after["fapiPublic"], original["fapiPublic"])


if __name__ == "__main__":
    unittest.main()
