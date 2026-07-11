#!/usr/bin/env python3
"""Validate deterministic Strategy-Market contracts before Stage 3A runs."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml


class StrategyMarketContractError(RuntimeError):
    failure_type = "validation_error"
    reason_code = "strategy_market_mode_mismatch"


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_strategy_class(strategy_file: str | Path, strategy_name: str):
    path = Path(strategy_file)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise StrategyMarketContractError(f"cannot load strategy file: {path}")
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.path.insert(0, str(path.parent.resolve()))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(path.parent.resolve()))
        except ValueError:
            pass
    strategy = getattr(module, strategy_name, None)
    if strategy is None:
        raise StrategyMarketContractError(f"strategy class missing: {strategy_name}")
    return strategy


def is_futures_pair(pair: str) -> bool:
    return ":" in pair


def pair_settle(pair: str) -> str | None:
    return pair.split(":", 1)[1] if ":" in pair else None


def dataset_mode(dataset_manifest: str | Path) -> str | None:
    manifest = load_simple_yaml(dataset_manifest)
    return manifest.get("trading_mode")


def dataset_manifest(dataset_manifest_path: str | Path) -> dict:
    return load_simple_yaml(dataset_manifest_path)


def snapshot_manifest(snapshot_dir: str | Path) -> dict:
    return load_simple_yaml(Path(snapshot_dir) / "manifest.yaml")


def validate_contract(
    strategy_file: str | Path,
    strategy_name: str,
    config_path: str | Path,
    dataset_manifest_path: str | Path,
    exchange_snapshot_dir: str | Path,
) -> dict[str, Any]:
    strategy_class = load_strategy_class(strategy_file, strategy_name)
    config = load_json(config_path)
    can_short = bool(getattr(strategy_class, "can_short", False))
    has_leverage_callback = callable(getattr(strategy_class, "leverage", None))
    trading_mode = config.get("trading_mode", "spot")
    margin_mode = config.get("margin_mode")
    stake_currency = config.get("stake_currency")
    pairs = list((config.get("exchange") or {}).get("pair_whitelist") or [])
    d_manifest = dataset_manifest(dataset_manifest_path)
    s_manifest = snapshot_manifest(exchange_snapshot_dir)
    d_mode = d_manifest.get("trading_mode")
    s_mode = s_manifest.get("trading_mode")
    dataset_candle_types = set(d_manifest.get("candle_types") or [])
    funding_model_synthetic = bool(d_manifest.get("funding_model_synthetic"))
    leverage_artifact = s_manifest.get("leverage_tier_artifact") or {}
    issues: list[str] = []

    if can_short and trading_mode == "spot":
        issues.append("can_short=True strategy cannot run with spot trading_mode")
    if trading_mode == "futures" and margin_mode not in {"isolated", "cross"}:
        issues.append("futures trading_mode requires isolated or cross margin_mode")
    if trading_mode == "futures":
        for pair in pairs:
            if not is_futures_pair(pair):
                issues.append(f"futures config uses non-futures pair: {pair}")
            elif pair_settle(pair) != stake_currency:
                issues.append(f"pair settle currency {pair_settle(pair)} does not match stake currency {stake_currency}")
        if d_mode != "futures":
            issues.append(f"futures config cannot use {d_mode or 'unknown'} dataset")
        if s_mode != "futures":
            issues.append(f"futures config cannot use {s_mode or 'unknown'} exchange snapshot")
        if "mark" not in dataset_candle_types:
            issues.append("futures dataset must include mark candles")
        if "funding_rate" not in dataset_candle_types and not funding_model_synthetic:
            issues.append("futures dataset must include funding_rate candles or an explicit synthetic funding contract")
        if s_manifest.get("btc_usdt_usdt_contract_size") is None:
            issues.append("futures exchange snapshot must include BTC/USDT:USDT contractSize")
        if not leverage_artifact.get("sha256") or leverage_artifact.get("network_required") is not False:
            issues.append("futures exchange snapshot must include offline leverage-tier artifact hash")
    if trading_mode == "spot":
        for pair in pairs:
            if is_futures_pair(pair):
                issues.append(f"spot config uses futures contract pair: {pair}")
        if d_mode == "futures":
            issues.append("spot config cannot use futures dataset")
        if s_mode == "futures":
            issues.append("spot config cannot use futures exchange snapshot")

    result = {
        "ok": not issues,
        "failure_type": None if not issues else StrategyMarketContractError.failure_type,
        "reason_code": None if not issues else StrategyMarketContractError.reason_code,
        "strategy": strategy_name,
        "strategy_file": str(strategy_file),
        "can_short": can_short,
        "has_leverage_callback": has_leverage_callback,
        "trading_mode": trading_mode,
        "margin_mode": margin_mode,
        "stake_currency": stake_currency,
        "pairs": pairs,
        "dataset_mode": d_mode,
        "exchange_snapshot_mode": s_mode,
        "dataset_candle_types": sorted(dataset_candle_types),
        "funding_model_synthetic": funding_model_synthetic,
        "issues": issues,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Strategy-Market contract.")
    parser.add_argument("--strategy-file", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset-manifest", required=True)
    parser.add_argument("--exchange-snapshot", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = validate_contract(args.strategy_file, args.strategy, args.config, args.dataset_manifest, args.exchange_snapshot)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
