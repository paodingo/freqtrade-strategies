import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from exchange_metadata_fingerprint import (  # noqa: E402
    build_equivalence_report,
    build_full_fingerprint,
    build_futures_scope_fingerprint,
    build_scope_fingerprint,
    compare_domains,
    diff_values,
    snapshot_artifact_integrity,
)
from run_experiment import sha256_file  # noqa: E402
from validate_exchange_snapshot import aggregate_hash  # noqa: E402


def market(symbol="BTC/USDT", precision_price="0.01", active=True):
    base, quote = symbol.split("/")
    return {
        "id": symbol.replace("/", ""),
        "symbol": symbol,
        "base": base,
        "quote": quote,
        "settle": None,
        "type": "spot",
        "spot": True,
        "margin": True,
        "swap": False,
        "future": False,
        "option": False,
        "active": active,
        "contract": False,
        "linear": None,
        "inverse": None,
        "contractSize": None,
        "precision": {"amount": 0.00001, "price": precision_price},
        "limits": {"amount": {"min": "0.00001", "max": "9000"}, "cost": {"min": 5}},
        "maker": "0.0010",
        "taker": 0.001,
        "info": {"ignored": "raw"},
    }


def currency(code="BTC", precision="0.00000001"):
    return {
        "id": code,
        "code": code,
        "numericId": None,
        "precision": precision,
        "active": True,
        "deposit": True,
        "withdraw": True,
        "limits": {"withdraw": {"min": "0.0"}},
        "info": {"ignored": "raw"},
    }


def metadata(extra_symbol=False):
    markets = {"BTC/USDT": market("BTC/USDT")}
    if extra_symbol:
        markets["ETH/USDT"] = market("ETH/USDT")
    return {
        "markets": markets,
        "currencies": {"BTC": currency("BTC"), "USDT": currency("USDT", "0.000001")},
        "options": {"defaultType": "spot", "fetchMarkets": {"types": ["spot"]}},
        "precisionMode": 4,
        "paddingMode": None,
    }


def create_snapshot(tmp: Path, meta: dict):
    snapshot = tmp / "snapshot"
    snapshot.mkdir()
    for name, payload in (
        ("markets.raw.json", meta["markets"]),
        ("currencies.json", meta["currencies"]),
        ("options.json", meta["options"]),
    ):
        (snapshot / name).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    entries = []
    for name in ("markets.raw.json", "currencies.json", "options.json"):
        path = snapshot / name
        entries.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    aggregate = aggregate_hash(entries)
    (snapshot / "manifest.yaml").write_text(
        "snapshot_id: test\nfiles: " + json.dumps(entries, sort_keys=True) + f"\naggregate_sha256: {json.dumps(aggregate)}\n",
        encoding="utf-8",
    )
    return snapshot


class ExchangeMetadataFingerprintTest(unittest.TestCase):
    def test_artifact_hash_and_content_hash_are_not_comparable(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = create_snapshot(Path(tmp), metadata())
            artifact = snapshot_artifact_integrity(snapshot)
        full = build_full_fingerprint(metadata())
        comparison = compare_domains(artifact, full)
        self.assertFalse(comparison["comparable"])
        self.assertEqual(comparison["reason_code"], "metadata_hash_domain_mismatch")

    def test_same_scope_hash_with_different_dict_order(self):
        first = metadata()
        second = {
            "paddingMode": None,
            "precisionMode": 4,
            "options": {"fetchMarkets": {"types": ["spot"]}, "defaultType": "spot"},
            "currencies": {"USDT": first["currencies"]["USDT"], "BTC": first["currencies"]["BTC"]},
            "markets": {"BTC/USDT": first["markets"]["BTC/USDT"]},
        }
        self.assertEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_market_order_and_unrelated_symbol_do_not_change_scope(self):
        first = metadata()
        second = metadata(extra_symbol=True)
        self.assertNotEqual(build_full_fingerprint(first)["payload_sha256"], build_full_fingerprint(second)["payload_sha256"])
        self.assertEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_float_representation_is_canonical(self):
        first = metadata()
        second = metadata()
        second["markets"]["BTC/USDT"]["maker"] = 0.0010
        second["markets"]["BTC/USDT"]["taker"] = "0.001"
        self.assertEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_btcusdt_precision_change_changes_scope(self):
        first = metadata()
        second = metadata()
        second["markets"]["BTC/USDT"] = market("BTC/USDT", precision_price="0.02")
        self.assertNotEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_btcusdt_limits_change_changes_scope(self):
        first = metadata()
        second = metadata()
        second["markets"]["BTC/USDT"]["limits"]["cost"]["min"] = "6"
        self.assertNotEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_btcusdt_active_change_changes_scope(self):
        first = metadata()
        second = metadata()
        second["markets"]["BTC/USDT"] = market("BTC/USDT", active=False)
        self.assertNotEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_btc_currency_precision_change_changes_scope(self):
        first = metadata()
        second = metadata()
        second["currencies"]["BTC"] = currency("BTC", "0.0001")
        self.assertNotEqual(build_scope_fingerprint(first)["payload_sha256"], build_scope_fingerprint(second)["payload_sha256"])

    def test_field_level_diff(self):
        diffs = diff_values({"a": {"b": 1}}, {"a": {"b": 2}}, "$")
        self.assertEqual(diffs, [{"path": "$.a.b", "sealed": 1, "online": 2}])

    def test_full_drift_scope_equivalent_allows_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = create_snapshot(Path(tmp), metadata())
            report = build_equivalence_report(metadata(), metadata(extra_symbol=True), snapshot)
        self.assertFalse(report["full_metadata_comparison"]["equal"])
        self.assertTrue(report["research_scope_comparison"]["equal"])
        self.assertEqual(report["classification"]["reason_code"], "exchange_metadata_unrelated_drift")
        self.assertTrue(report["classification"]["continue_acceptance"])

    def test_scope_drift_blocks(self):
        changed = metadata()
        changed["markets"]["BTC/USDT"]["active"] = False
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = create_snapshot(Path(tmp), metadata())
            report = build_equivalence_report(metadata(), changed, snapshot)
        self.assertFalse(report["research_scope_comparison"]["equal"])
        self.assertEqual(report["classification"]["reason_code"], "exchange_metadata_scope_drift")
        self.assertFalse(report["classification"]["continue_acceptance"])

    def test_snapshot_files_not_modified_by_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = create_snapshot(Path(tmp), metadata())
            before = {path.name: sha256_file(path) for path in snapshot.iterdir() if path.is_file()}
            build_equivalence_report(metadata(), metadata(extra_symbol=True), snapshot)
            after = {path.name: sha256_file(path) for path in snapshot.iterdir() if path.is_file()}
        self.assertEqual(before, after)

    def test_futures_metadata_scope(self):
        meta = metadata()
        meta["markets"] = {"BTC/USDT:USDT": {**market("BTC/USDT"), "symbol": "BTC/USDT:USDT", "settle": "USDT", "type": "swap", "spot": False, "swap": True, "linear": True, "contract": True, "contractSize": 1}}
        fp = build_futures_scope_fingerprint(meta)
        self.assertEqual(fp["hash_domain"], "ccxt_futures_research_scope_v1")
        self.assertEqual(fp["selected_contract_projection"]["contractSize"], 1)

    def test_futures_contract_size_change_changes_scope(self):
        first = metadata()
        second = metadata()
        for meta, size in ((first, 1), (second, 2)):
            meta["markets"] = {"BTC/USDT:USDT": {**market("BTC/USDT"), "symbol": "BTC/USDT:USDT", "settle": "USDT", "type": "swap", "spot": False, "swap": True, "linear": True, "contract": True, "contractSize": size}}
        self.assertNotEqual(build_futures_scope_fingerprint(first)["payload_sha256"], build_futures_scope_fingerprint(second)["payload_sha256"])

    def test_futures_linear_inverse_change_changes_scope(self):
        first = metadata()
        second = metadata()
        for meta, inverse in ((first, False), (second, True)):
            meta["markets"] = {"BTC/USDT:USDT": {**market("BTC/USDT"), "symbol": "BTC/USDT:USDT", "settle": "USDT", "type": "swap", "spot": False, "swap": True, "linear": not inverse, "inverse": inverse, "contract": True, "contractSize": 1}}
        self.assertNotEqual(build_futures_scope_fingerprint(first)["payload_sha256"], build_futures_scope_fingerprint(second)["payload_sha256"])


if __name__ == "__main__":
    unittest.main()
