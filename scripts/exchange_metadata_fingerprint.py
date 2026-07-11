#!/usr/bin/env python3
"""Canonical exchange metadata fingerprints for Stage 3A acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from research_control import load_simple_yaml
from run_experiment import sha256_file
from validate_exchange_snapshot import aggregate_hash


HASH_ALGORITHM = "sha256"
FULL_SCHEMA_VERSION = "ccxt-full-metadata-v1"
SCOPE_SCHEMA_VERSION = "ccxt-research-scope-v1"
FUTURES_SCOPE_SCHEMA_VERSION = "ccxt-futures-research-scope-v1"
ARTIFACT_SCHEMA_VERSION = "snapshot-artifact-integrity-v1"
MARKET_FIELDS = (
    "id",
    "symbol",
    "base",
    "quote",
    "settle",
    "type",
    "spot",
    "margin",
    "swap",
    "future",
    "option",
    "active",
    "contract",
    "linear",
    "inverse",
    "contractSize",
    "precision",
    "limits",
    "maker",
    "taker",
)
CURRENCY_FIELDS = (
    "id",
    "code",
    "numericId",
    "precision",
    "active",
    "deposit",
    "withdraw",
    "limits",
)
OPTION_FIELDS = (
    "defaultType",
    "defaultSubType",
    "fetchMarkets",
    "defaultNetwork",
)
EXCLUDED_FIELDS = (
    "info",
    "timestamp",
    "datetime",
    "serverTime",
    "headers",
    "httpProxy",
    "httpsProxy",
    "socksProxy",
    "apiKey",
    "secret",
    "password",
)


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, list):
        items = [canonicalize(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return value
    if isinstance(value, float) or isinstance(value, Decimal):
        return decimal_string(value)
    if isinstance(value, str):
        try:
            Decimal(value)
        except InvalidOperation:
            return value
        return decimal_string(value)
    return str(value)


def decimal_string(value: Any) -> str:
    number = Decimal(str(value))
    if number.is_nan() or number.is_infinite():
        return str(value)
    return format(number.normalize(), "f")


def canonical_json(payload: Any) -> str:
    return json.dumps(canonicalize(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def domain_metadata(hash_domain: str, schema_version: str, included_sections: list[str]) -> dict[str, Any]:
    return {
        "hash_domain": hash_domain,
        "normalization_schema_version": schema_version,
        "hash_algorithm": HASH_ALGORITHM,
        "included_sections": included_sections,
        "excluded_fields": list(EXCLUDED_FIELDS),
        "canonicalization_rules": {
            "dict_order": "sort keys lexicographically",
            "list_order": "sort canonical JSON representation unless projected by explicit key",
            "market_order": "sort by unified symbol",
            "currency_order": "sort by code",
            "number_format": "Decimal(str(value)).normalize() string",
            "null_handling": "missing whitelisted fields are explicit null",
            "json": "UTF-8 canonical JSON with sorted keys and compact separators",
        },
    }


def project_market(market: dict[str, Any] | None) -> dict[str, Any]:
    market = market if isinstance(market, dict) else {}
    return {field: canonicalize(market.get(field)) for field in MARKET_FIELDS}


def project_currency(currency: dict[str, Any] | None) -> dict[str, Any]:
    currency = currency if isinstance(currency, dict) else {}
    return {field: canonicalize(currency.get(field)) for field in CURRENCY_FIELDS}


def project_options(options: dict[str, Any] | None) -> dict[str, Any]:
    options = options if isinstance(options, dict) else {}
    return {field: canonicalize(options.get(field)) for field in OPTION_FIELDS}


def exchange_level(options: dict[str, Any] | None, precision_mode: Any = None, padding_mode: Any = None) -> dict[str, Any]:
    return {
        "precisionMode": canonicalize(precision_mode),
        "paddingMode": canonicalize(padding_mode),
        "options": project_options(options),
    }


def build_full_fingerprint(metadata: dict[str, Any]) -> dict[str, Any]:
    markets = metadata.get("markets") or {}
    currencies = metadata.get("currencies") or {}
    options = metadata.get("options") or {}
    payload = {
        "metadata": domain_metadata(
            "ccxt_full_metadata_v1",
            FULL_SCHEMA_VERSION,
            ["markets", "currencies", "exchange_level"],
        ),
        "markets": [
            {"symbol": symbol, "projection": project_market(markets.get(symbol))}
            for symbol in sorted(markets)
        ],
        "currencies": [
            {"code": code, "projection": project_currency(currencies.get(code))}
            for code in sorted(currencies)
        ],
        "exchange_level": exchange_level(
            options,
            metadata.get("precisionMode"),
            metadata.get("paddingMode"),
        ),
    }
    return {
        **payload["metadata"],
        "markets_count": len(markets),
        "currencies_count": len(currencies),
        "payload_sha256": payload_hash(payload),
        "canonical_payload": canonicalize(payload),
    }


def build_scope_fingerprint(
    metadata: dict[str, Any],
    pair: str = "BTC/USDT",
    currencies: tuple[str, str] = ("BTC", "USDT"),
    fee_contract: Any = None,
) -> dict[str, Any]:
    markets = metadata.get("markets") or {}
    currency_map = metadata.get("currencies") or {}
    options = metadata.get("options") or {}
    selected_currencies = {
        code: project_currency(currency_map.get(code))
        for code in currencies
    }
    payload = {
        "metadata": domain_metadata(
            "ccxt_research_scope_v1",
            SCOPE_SCHEMA_VERSION,
            ["selected_market", "selected_currencies", "exchange_level", "fee_contract"],
        ),
        "selected_pair": pair,
        "selected_pair_projection": project_market(markets.get(pair)),
        "selected_currencies": selected_currencies,
        "exchange_level": exchange_level(
            options,
            metadata.get("precisionMode"),
            metadata.get("paddingMode"),
        ),
        "fee_contract": canonicalize(fee_contract),
    }
    return {
        **payload["metadata"],
        "markets_count": len(markets),
        "currencies_count": len(currency_map),
        "selected_pair_projection": payload["selected_pair_projection"],
        "selected_currency_projections": selected_currencies,
        "payload_sha256": payload_hash(payload),
        "canonical_payload": canonicalize(payload),
    }


def build_futures_scope_fingerprint(
    metadata: dict[str, Any],
    pair: str = "BTC/USDT:USDT",
    assets: tuple[str, str] = ("BTC", "USDT"),
    leverage_tier_artifact: dict[str, Any] | None = None,
    fee_contract: Any = None,
    funding_model_contract: Any = None,
) -> dict[str, Any]:
    markets = metadata.get("markets") or {}
    currency_map = metadata.get("currencies") or {}
    options = metadata.get("options") or {}
    selected_assets = {
        code: project_currency(currency_map.get(code))
        for code in assets
    }
    market = project_market(markets.get(pair))
    payload = {
        "metadata": domain_metadata(
            "ccxt_futures_research_scope_v1",
            FUTURES_SCOPE_SCHEMA_VERSION,
            [
                "selected_contract",
                "selected_assets",
                "exchange_level",
                "margin_modes",
                "leverage_tier_artifact",
                "fee_contract",
                "funding_model_contract",
            ],
        ),
        "selected_pair": pair,
        "selected_contract_projection": market,
        "selected_assets": selected_assets,
        "exchange_level": exchange_level(
            options,
            metadata.get("precisionMode"),
            metadata.get("paddingMode"),
        ),
        "margin_modes": canonicalize((options or {}).get("marginModes") or ["isolated"]),
        "leverage_tier_artifact": canonicalize(leverage_tier_artifact or {}),
        "fee_contract": canonicalize(fee_contract),
        "funding_model_contract": canonicalize(funding_model_contract),
    }
    return {
        **payload["metadata"],
        "markets_count": len(markets),
        "currencies_count": len(currency_map),
        "selected_contract_projection": payload["selected_contract_projection"],
        "selected_asset_projections": selected_assets,
        "payload_sha256": payload_hash(payload),
        "canonical_payload": canonicalize(payload),
    }


def snapshot_artifact_integrity(snapshot_dir: str | Path) -> dict[str, Any]:
    snapshot = Path(snapshot_dir)
    manifest = load_simple_yaml(snapshot / "manifest.yaml")
    entries = manifest.get("files") or []
    checked = []
    for item in entries:
        name = Path(item["path"]).name
        path = snapshot / name
        checked.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    aggregate = aggregate_hash(checked)
    payload = {
        "metadata": domain_metadata(
            "snapshot_artifact_integrity_v1",
            ARTIFACT_SCHEMA_VERSION,
            ["manifest.files", "artifact bytes", "artifact sha256"],
        ),
        "snapshot_id": manifest.get("snapshot_id"),
        "manifest_aggregate_sha256": manifest.get("aggregate_sha256"),
        "computed_aggregate_sha256": aggregate,
        "artifacts": checked,
    }
    return {
        **payload["metadata"],
        "snapshot_id": manifest.get("snapshot_id"),
        "artifact_aggregate_complete": aggregate == manifest.get("aggregate_sha256"),
        "manifest_aggregate_sha256": manifest.get("aggregate_sha256"),
        "computed_aggregate_sha256": aggregate,
        "payload_sha256": payload_hash(payload),
        "canonical_payload": canonicalize(payload),
    }


def compare_domains(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    comparable = (
        first.get("hash_domain") == second.get("hash_domain")
        and first.get("normalization_schema_version") == second.get("normalization_schema_version")
        and first.get("hash_algorithm") == second.get("hash_algorithm")
    )
    return {
        "comparable": comparable,
        "reason_code": None if comparable else "metadata_hash_domain_mismatch",
        "first_domain": first.get("hash_domain"),
        "second_domain": second.get("hash_domain"),
        "first_schema": first.get("normalization_schema_version"),
        "second_schema": second.get("normalization_schema_version"),
    }


def diff_values(first: Any, second: Any, path: str = "$") -> list[dict[str, Any]]:
    if first == second:
        return []
    if isinstance(first, dict) and isinstance(second, dict):
        diffs = []
        for key in sorted(set(first) | set(second)):
            diffs.extend(diff_values(first.get(key), second.get(key), f"{path}.{key}"))
        return diffs
    if isinstance(first, list) and isinstance(second, list):
        diffs = []
        max_len = max(len(first), len(second))
        for index in range(max_len):
            left = first[index] if index < len(first) else None
            right = second[index] if index < len(second) else None
            diffs.extend(diff_values(left, right, f"{path}[{index}]"))
        return diffs
    return [{"path": path, "sealed": first, "online": second}]


def symbol_diff(sealed_markets: dict[str, Any], online_markets: dict[str, Any]) -> dict[str, Any]:
    sealed_symbols = set(sealed_markets)
    online_symbols = set(online_markets)
    added = sorted(online_symbols - sealed_symbols)
    removed = sorted(sealed_symbols - online_symbols)
    modified = []
    for symbol in sorted(sealed_symbols & online_symbols):
        if project_market(sealed_markets[symbol]) != project_market(online_markets[symbol]):
            modified.append(symbol)
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "modified_count": len(modified),
        "added_symbols": added,
        "removed_symbols": removed,
        "modified_symbols": modified,
    }


def classify_equivalence(full_equal: bool, scope_equal: bool, scope_comparable: bool = True) -> dict[str, Any]:
    if not scope_comparable:
        return {
            "severity": "error",
            "failure_type": "implementation_error",
            "reason_code": "metadata_hash_domain_mismatch",
            "continue_acceptance": False,
        }
    if scope_equal and full_equal:
        return {
            "severity": "info",
            "failure_type": None,
            "reason_code": "exchange_metadata_equivalent",
            "continue_acceptance": True,
        }
    if scope_equal and not full_equal:
        return {
            "severity": "warning",
            "failure_type": "warning",
            "reason_code": "exchange_metadata_unrelated_drift",
            "continue_acceptance": True,
        }
    return {
        "severity": "error",
        "failure_type": "validation_error",
        "reason_code": "exchange_metadata_scope_drift",
        "continue_acceptance": False,
    }


def load_snapshot_metadata(snapshot_dir: str | Path, precision_mode: Any = None, padding_mode: Any = None) -> dict[str, Any]:
    snapshot = Path(snapshot_dir)
    return {
        "markets": json.loads((snapshot / "markets.raw.json").read_text(encoding="utf-8")),
        "currencies": json.loads((snapshot / "currencies.json").read_text(encoding="utf-8")),
        "options": json.loads((snapshot / "options.json").read_text(encoding="utf-8")),
        "precisionMode": precision_mode,
        "paddingMode": padding_mode,
    }


def build_equivalence_report(
    sealed_metadata: dict[str, Any],
    online_metadata: dict[str, Any],
    snapshot_dir: str | Path,
    pair: str = "BTC/USDT",
    fee_contract: Any = None,
) -> dict[str, Any]:
    sealed_full = build_full_fingerprint(sealed_metadata)
    online_full = build_full_fingerprint(online_metadata)
    sealed_scope = build_scope_fingerprint(sealed_metadata, pair=pair, fee_contract=fee_contract)
    online_scope = build_scope_fingerprint(online_metadata, pair=pair, fee_contract=fee_contract)
    full_compare = compare_domains(sealed_full, online_full)
    scope_compare = compare_domains(sealed_scope, online_scope)
    full_equal = full_compare["comparable"] and sealed_full["payload_sha256"] == online_full["payload_sha256"]
    scope_equal = scope_compare["comparable"] and sealed_scope["payload_sha256"] == online_scope["payload_sha256"]
    symbols = symbol_diff(sealed_metadata.get("markets") or {}, online_metadata.get("markets") or {})
    classification = classify_equivalence(full_equal, scope_equal, scope_compare["comparable"])
    artifact = snapshot_artifact_integrity(snapshot_dir)
    return {
        "hash_domains": {
            "artifact": {
                "hash_domain": artifact["hash_domain"],
                "normalization_schema_version": artifact["normalization_schema_version"],
                "payload_sha256": artifact["payload_sha256"],
            },
            "sealed_full": {
                "hash_domain": sealed_full["hash_domain"],
                "normalization_schema_version": sealed_full["normalization_schema_version"],
                "payload_sha256": sealed_full["payload_sha256"],
            },
            "online_full": {
                "hash_domain": online_full["hash_domain"],
                "normalization_schema_version": online_full["normalization_schema_version"],
                "payload_sha256": online_full["payload_sha256"],
            },
            "sealed_scope": {
                "hash_domain": sealed_scope["hash_domain"],
                "normalization_schema_version": sealed_scope["normalization_schema_version"],
                "payload_sha256": sealed_scope["payload_sha256"],
            },
            "online_scope": {
                "hash_domain": online_scope["hash_domain"],
                "normalization_schema_version": online_scope["normalization_schema_version"],
                "payload_sha256": online_scope["payload_sha256"],
            },
        },
        "artifact_integrity": artifact,
        "artifact_vs_content_comparison": compare_domains(artifact, online_full),
        "full_metadata_comparison": {
            **full_compare,
            "equal": full_equal,
            "sealed_markets_count": sealed_full["markets_count"],
            "online_markets_count": online_full["markets_count"],
            "sealed_currencies_count": sealed_full["currencies_count"],
            "online_currencies_count": online_full["currencies_count"],
        },
        "research_scope_comparison": {
            **scope_compare,
            "equal": scope_equal,
            "selected_pair": pair,
            "sealed_hash": sealed_scope["payload_sha256"],
            "online_hash": online_scope["payload_sha256"],
        },
        "symbol_diff": symbols,
        "btcusdt_field_diff": diff_values(
            sealed_scope["selected_pair_projection"],
            online_scope["selected_pair_projection"],
            "$.BTC/USDT",
        ),
        "btc_currency_field_diff": diff_values(
            sealed_scope["selected_currency_projections"]["BTC"],
            online_scope["selected_currency_projections"]["BTC"],
            "$.BTC",
        ),
        "usdt_currency_field_diff": diff_values(
            sealed_scope["selected_currency_projections"]["USDT"],
            online_scope["selected_currency_projections"]["USDT"],
            "$.USDT",
        ),
        "exchange_level_field_diff": diff_values(
            sealed_scope["canonical_payload"]["exchange_level"],
            online_scope["canonical_payload"]["exchange_level"],
            "$.exchange_level",
        ),
        "classification": classification,
        "sealed_scope_fingerprint": sealed_scope,
        "online_scope_fingerprint": online_scope,
        "sealed_full_fingerprint": {k: v for k, v in sealed_full.items() if k != "canonical_payload"},
        "online_full_fingerprint": {k: v for k, v in online_full.items() if k != "canonical_payload"},
    }


def write_equivalence_markdown(path: str | Path, report: dict[str, Any]) -> None:
    symbol_diff = report["symbol_diff"]
    lines = [
        "# Exchange Metadata Equivalence Report",
        "",
        f"- artifact aggregate complete: {report['artifact_integrity']['artifact_aggregate_complete']}",
        f"- artifact/content comparable: {report['artifact_vs_content_comparison']['comparable']}",
        f"- full metadata equal: {report['full_metadata_comparison']['equal']}",
        f"- research scope equal: {report['research_scope_comparison']['equal']}",
        f"- classification: {report['classification']['severity']} / {report['classification']['reason_code']}",
        f"- sealed full hash: `{report['hash_domains']['sealed_full']['payload_sha256']}`",
        f"- online full hash: `{report['hash_domains']['online_full']['payload_sha256']}`",
        f"- sealed scope hash: `{report['hash_domains']['sealed_scope']['payload_sha256']}`",
        f"- online scope hash: `{report['hash_domains']['online_scope']['payload_sha256']}`",
        f"- added symbols: {symbol_diff['added_count']}",
        f"- removed symbols: {symbol_diff['removed_count']}",
        f"- modified symbols: {symbol_diff['modified_count']}",
        f"- BTC/USDT field diffs: {len(report['btcusdt_field_diff'])}",
        f"- BTC currency field diffs: {len(report['btc_currency_field_diff'])}",
        f"- USDT currency field diffs: {len(report['usdt_currency_field_diff'])}",
        f"- exchange-level field diffs: {len(report['exchange_level_field_diff'])}",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fingerprint sealed exchange metadata.")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    metadata = load_snapshot_metadata(args.snapshot)
    result = {
        "artifact": snapshot_artifact_integrity(args.snapshot),
        "full": build_full_fingerprint(metadata),
        "scope": build_scope_fingerprint(metadata),
    }
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
