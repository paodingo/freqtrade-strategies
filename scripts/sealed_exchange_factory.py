#!/usr/bin/env python3
"""Create a real Freqtrade Exchange backed by sealed markets metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from run_experiment import sha256_file
from validate_exchange_snapshot import SnapshotValidationError, validate_snapshot


class OfflineContractViolation(RuntimeError):
    reason_code = "offline_contract_violation"
    failure_type = "infra_permanent"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _forbid_reload(*_args, **_kwargs):
    raise OfflineContractViolation("online market reload is forbidden in sealed offline mode")


def _repo_root_from_snapshot(snapshot: Path) -> Path:
    for parent in snapshot.parents:
        if (parent / "research").is_dir() and (parent / "scripts").is_dir():
            return parent
    return snapshot.parents[2]


def inject_offline_leverage_tiers(exchange, snapshot: Path, manifest: dict, pair: str) -> None:
    leverage = manifest.get("leverage_tier_artifact") or {}
    if leverage.get("network_required") is not False:
        raise SnapshotValidationError("offline leverage tier artifact must not require network")
    rel_path = leverage.get("path")
    if not rel_path:
        raise SnapshotValidationError("offline leverage tier artifact path missing")
    path = _repo_root_from_snapshot(snapshot) / rel_path
    if not path.exists():
        raise SnapshotValidationError(f"offline leverage tier artifact missing on disk: {rel_path}")
    if leverage.get("sha256") and sha256_file(path) != leverage.get("sha256"):
        raise SnapshotValidationError("offline leverage tier artifact hash mismatch")
    payload = load_json(path)
    if pair not in payload:
        raise SnapshotValidationError(f"{pair} missing from offline leverage tier artifact")
    exchange._leverage_tiers[pair] = [exchange.parse_leverage_tier(tier) for tier in payload[pair]]


def create_sealed_exchange(
    config: dict,
    snapshot_dir: str | Path,
    expected_freqtrade_version: str = "2025.8",
    expected_ccxt_version: str = "4.5.64",
    expected_python_version: str = "3.12",
):
    from freqtrade.resolvers.exchange_resolver import ExchangeResolver

    snapshot = Path(snapshot_dir).resolve()
    validation = validate_snapshot(
        snapshot,
        expected_freqtrade_version=expected_freqtrade_version,
        expected_ccxt_version=expected_ccxt_version,
        expected_python_version=expected_python_version,
    )
    if not validation["ok"]:
        raise SnapshotValidationError("; ".join(validation["issues"]))
    manifest = validation["manifest"]
    exchange = ExchangeResolver.load_exchange(
        config,
        validate=False,
        load_leverage_tiers=False,
    )
    markets = load_json(snapshot / "markets.raw.json")
    currencies = load_json(snapshot / "currencies.json")
    options = load_json(snapshot / "options.json")
    trading_mode = config.get("trading_mode", "spot")
    pair = ((config.get("exchange") or {}).get("pair_whitelist") or ["BTC/USDT"])[0]
    if not markets or pair not in markets:
        raise SnapshotValidationError(f"{pair} missing from raw markets")
    if "BTC" not in currencies or "USDT" not in currencies:
        raise SnapshotValidationError("BTC and USDT currencies required")

    exchange._api.set_markets(markets, currencies)
    exchange._api_async.set_markets(markets, currencies)
    exchange._api.options = options
    exchange._api_async.options = options
    exchange._markets = markets
    exchange.reload_markets = _forbid_reload
    exchange._load_async_markets = _forbid_reload
    exchange._api_reload_markets = _forbid_reload

    exchange.validate_stakecurrency(config["stake_currency"])
    exchange.validate_timeframes(config.get("timeframe"))
    market = exchange.markets.get(pair)
    if not market:
        raise SnapshotValidationError(f"{pair} missing after injection")
    if market.get("quote") != "USDT":
        raise SnapshotValidationError(f"{pair} is not a USDT market")
    if trading_mode == "spot":
        if market.get("spot") is not True:
            raise SnapshotValidationError(f"{pair} is not a USDT spot market")
    elif trading_mode == "futures":
        if config.get("margin_mode") not in {"isolated", "cross"}:
            raise SnapshotValidationError("futures offline adapter requires isolated or cross margin mode")
        if market.get("settle") != config.get("stake_currency"):
            raise SnapshotValidationError(f"{pair} settle currency does not match stake currency")
        if market.get("swap") is not True or market.get("linear") is not True or market.get("contract") is not True:
            raise SnapshotValidationError(f"{pair} is not a linear futures swap contract")
        if market.get("contractSize") is None:
            raise SnapshotValidationError(f"{pair} contractSize missing")
        inject_offline_leverage_tiers(exchange, snapshot, manifest, pair)
    else:
        raise SnapshotValidationError(f"offline adapter does not allow trading mode: {trading_mode}")
    if config.get("fee") is None:
        raise SnapshotValidationError("fixed fee must be present in config")
    return exchange
