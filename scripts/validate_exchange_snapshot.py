#!/usr/bin/env python3
"""Validate a sealed exchange markets metadata snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml
from run_experiment import sha256_file


REQUIRED_COMMON_FILES = (
    "markets.raw.json",
    "markets.normalized.json",
    "currencies.json",
    "options.json",
    "artifact-hashes.json",
)
REQUIRED_SPOT_FILES = (
    "capture.log",
)
REQUIRED_FUTURES_FILES = (
    "fapi.exchangeInfo.raw.json",
    "leverage-tiers-contract.json",
    "futures-scope-fingerprint.json",
)
SECRET_TOKENS = ("secret", "api_key", "apikey", "apiKey", "password", "token", "authorization", "cookie", "set-cookie", "headers")


class SnapshotValidationError(RuntimeError):
    pass


def json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate_hash(entries: list[dict]) -> str:
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def scan_for_secret_keys(value: Any, path: str = "$", ignore_root_keys: bool = False) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).casefold()
            if not (ignore_root_keys and path == "$") and any(token.casefold() in lowered for token in SECRET_TOKENS):
                hits.append(f"{path}.{key}")
            hits.extend(scan_for_secret_keys(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(scan_for_secret_keys(item, f"{path}[{index}]"))
    return hits


def validate_snapshot(
    snapshot_dir: str | Path,
    expected_freqtrade_version: str | None = None,
    expected_ccxt_version: str | None = None,
    expected_python_version: str | None = None,
) -> dict:
    snapshot = Path(snapshot_dir).resolve()
    manifest_path = snapshot / "manifest.yaml"
    if not manifest_path.exists():
        raise SnapshotValidationError("manifest.yaml missing")
    manifest = load_simple_yaml(manifest_path)
    if not isinstance(manifest, dict):
        raise SnapshotValidationError("manifest must be a mapping")
    issues: list[str] = []
    if manifest.get("sealed") is not True:
        issues.append("snapshot is not sealed")
    if manifest.get("exchange") != "binance":
        issues.append("exchange must be binance")
    trading_mode = manifest.get("trading_mode")
    if trading_mode not in {"spot", "futures"}:
        issues.append("trading_mode must be spot or futures")
    if expected_freqtrade_version and manifest.get("freqtrade_version") != expected_freqtrade_version:
        issues.append("freqtrade version mismatch")
    if expected_ccxt_version and manifest.get("ccxt_version") != expected_ccxt_version:
        issues.append("ccxt version mismatch")
    if expected_python_version and not str(manifest.get("python_version", "")).startswith(expected_python_version):
        issues.append("python version mismatch")

    artifact_entries = manifest.get("files") or []
    if not isinstance(artifact_entries, list) or not artifact_entries:
        issues.append("manifest files are missing")
    expected_by_name = {Path(item.get("path", "")).name: item for item in artifact_entries if isinstance(item, dict)}
    required_files = list(REQUIRED_COMMON_FILES)
    if trading_mode == "spot":
        required_files.extend(REQUIRED_SPOT_FILES)
    elif trading_mode == "futures":
        required_files.extend(REQUIRED_FUTURES_FILES)
    for name in required_files:
        if name not in expected_by_name:
            issues.append(f"{name} missing from manifest")
        if not (snapshot / name).exists():
            issues.append(f"{name} missing on disk")
    checked_entries = []
    for item in artifact_entries:
        if not isinstance(item, dict) or "path" not in item:
            issues.append("invalid file entry")
            continue
        path = snapshot / Path(item["path"]).name
        if not path.exists():
            continue
        size = path.stat().st_size
        digest = sha256_file(path)
        checked_entries.append({"path": item["path"], "bytes": size, "sha256": digest})
        if item.get("bytes") != size or item.get("sha256") != digest:
            issues.append(f"hash mismatch: {item['path']}")
    aggregate = aggregate_hash(checked_entries)
    if manifest.get("aggregate_sha256") != aggregate:
        issues.append("aggregate hash mismatch")

    raw_markets = json_load(snapshot / "markets.raw.json") if (snapshot / "markets.raw.json").exists() else {}
    normalized = json_load(snapshot / "markets.normalized.json") if (snapshot / "markets.normalized.json").exists() else {}
    currencies = json_load(snapshot / "currencies.json") if (snapshot / "currencies.json").exists() else {}
    options = json_load(snapshot / "options.json") if (snapshot / "options.json").exists() else {}
    secret_hits = []
    for name, payload in (("markets", raw_markets), ("normalized", normalized), ("currencies", currencies), ("options", options), ("manifest", manifest)):
        ignore_root_keys = name in {"markets", "normalized", "currencies"}
        secret_hits.extend(f"{name}:{hit}" for hit in scan_for_secret_keys(payload, ignore_root_keys=ignore_root_keys))
    if secret_hits:
        issues.append(f"secret-like fields present: {', '.join(secret_hits[:10])}")

    market_pair = "BTC/USDT:USDT" if trading_mode == "futures" else "BTC/USDT"
    btc = normalized.get(market_pair) if isinstance(normalized, dict) else None
    if not isinstance(btc, dict):
        issues.append(f"{market_pair} market missing")
    else:
        if btc.get("quote") != "USDT":
            issues.append(f"{market_pair} quote must be USDT")
        if trading_mode == "spot" and btc.get("spot") is not True:
            issues.append(f"{market_pair} must be spot")
        if trading_mode == "futures":
            if btc.get("settle") != "USDT":
                issues.append(f"{market_pair} settle must be USDT")
            if btc.get("swap") is not True or btc.get("linear") is not True or btc.get("contract") is not True:
                issues.append(f"{market_pair} must be a linear swap contract")
            if btc.get("contractSize") is None:
                issues.append(f"{market_pair} contractSize missing")
        if btc.get("active") is not True:
            issues.append(f"{market_pair} must be active")
        if not btc.get("precision"):
            issues.append(f"{market_pair} precision missing")
        if not btc.get("limits"):
            issues.append(f"{market_pair} limits missing")
    if trading_mode == "futures":
        leverage = manifest.get("leverage_tier_artifact") or {}
        if not leverage.get("sha256") or leverage.get("network_required") is not False:
            issues.append("offline leverage tier artifact missing")
    if not isinstance(currencies, dict) or "BTC" not in currencies or "USDT" not in currencies:
        issues.append("BTC and USDT currencies required")

    return {
        "ok": not issues,
        "issues": issues,
        "manifest": manifest,
        "btc_usdt": btc,
        "aggregate_sha256": aggregate,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a sealed exchange snapshot.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--expected-freqtrade-version")
    parser.add_argument("--expected-ccxt-version")
    parser.add_argument("--expected-python-version")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_snapshot(
            args.snapshot,
            expected_freqtrade_version=args.expected_freqtrade_version,
            expected_ccxt_version=args.expected_ccxt_version,
            expected_python_version=args.expected_python_version,
        )
    except SnapshotValidationError as exc:
        result = {"ok": False, "issues": [str(exc)], "manifest": None, "btc_usdt": None, "aggregate_sha256": None}
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(f"snapshot validation: {'pass' if result['ok'] else 'fail'}")
        for issue in result["issues"]:
            print(f"- {issue}")
    return 1 if args.strict and not result["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
