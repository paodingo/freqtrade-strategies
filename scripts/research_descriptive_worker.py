#!/usr/bin/env python3
"""Execute one allowlisted Development-only descriptive Worker job."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

import research_worker_queue as worker_queue
from research_director_common import fingerprint, load_document, sha256_file


ROOT = Path(__file__).resolve().parents[1]
HANDLER_CONTRACT_PATH = Path(
    "research/governance/descriptive-worker-handler-contract-v1.json"
)
HANDLER_APPROVAL_PATH = Path(
    "research/governance/approvals/descriptive-worker-handler-v1-approval.json"
)
LEGACY_MANIFEST_CONTRACT_PATH = Path(
    "research/governance/legacy-development-manifest-compatibility-v1.json"
)
LEGACY_MANIFEST_APPROVAL_PATH = Path(
    "research/governance/approvals/legacy-development-manifest-compatibility-v1-approval.json"
)
QUANTILES = (0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99)


def _inside(repo: Path, relative: str, *, must_exist: bool = True) -> Path:
    if not relative or "\\" in relative or Path(relative).is_absolute():
        raise ValueError("worker path is not canonical repo-relative")
    target = (repo / relative).resolve(strict=must_exist)
    try:
        target.relative_to(repo)
    except ValueError as exc:
        raise ValueError("worker path escapes repository") from exc
    return target


def load_handler_authority(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = repo / HANDLER_CONTRACT_PATH
    approval_path = repo / HANDLER_APPROVAL_PATH
    contract = load_document(contract_path)
    approval = load_document(approval_path)
    false_fields = (
        "arbitrary_command_execution_authorized",
        "dynamic_handler_import_authorized",
        "network_access_authorized",
        "backtest_authorized",
        "candidate_creation_authorized",
        "strategy_mutation_authorized",
        "trading_execution_authorized",
        "automatic_lesson_promotion_authorized",
        "silent_contract_amendment_allowed",
    )
    if (
        contract.get("schema_version") != "descriptive-worker-handler-contract-v1"
        or contract.get("status") != "active"
        or contract.get("approval_authority") != HANDLER_APPROVAL_PATH.as_posix()
        or approval.get("approval_status") != "approved"
        or approval.get("approver_type") != "human_user"
        or approval.get("approved_contract_path") != HANDLER_CONTRACT_PATH.as_posix()
        or approval.get("approved_contract_sha256") != sha256_file(contract_path)
        or approval.get("validation_accesses_authorized") != 0
        or approval.get("holdout_accesses_authorized") != 0
        or any(approval.get(field) is not False for field in false_fields)
        or contract.get("prohibited_capabilities")
        != [
            "arbitrary_command_execution",
            "dynamic_handler_import",
            "network_access",
            "backtest",
            "signal_generation",
            "trade_generation",
            "candidate_creation",
            "strategy_mutation",
            "validation_access",
            "holdout_access",
            "promotion",
        ]
    ):
        raise ValueError("descriptive worker authority is invalid or drifted")
    handlers = contract.get("supported_handlers")
    if not isinstance(handlers, list) or len(handlers) != 1:
        raise ValueError("descriptive worker handler allowlist is invalid")
    return contract, approval


def load_legacy_manifest_compatibility(repo: Path) -> dict[str, dict[str, Any]]:
    contract_path = repo / LEGACY_MANIFEST_CONTRACT_PATH
    approval_path = repo / LEGACY_MANIFEST_APPROVAL_PATH
    contract = load_document(contract_path)
    approval = load_document(approval_path)
    manifests = contract.get("exact_legacy_manifests")
    if not isinstance(manifests, list) or len(manifests) != 2:
        raise ValueError("legacy manifest compatibility allowlist is invalid")
    by_path = {str(item.get("manifest_path")): item for item in manifests}
    approved_bindings = [
        {
            "manifest_path": item.get("manifest_path"),
            "manifest_sha256": item.get("manifest_sha256"),
        }
        for item in manifests
    ]
    prohibited = {
        "modify_legacy_manifest",
        "expand_to_other_manifest",
        "network_access",
        "backtest",
        "candidate_creation",
        "strategy_mutation",
        "validation_access",
        "holdout_access",
        "promotion",
    }
    if (
        contract.get("schema_version")
        != "legacy-development-manifest-compatibility-v1"
        or contract.get("status") != "active"
        or contract.get("approval_authority")
        != LEGACY_MANIFEST_APPROVAL_PATH.as_posix()
        or set(by_path) != {
            "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml",
            "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml",
        }
        or any(
            set(item.get("allowed_missing_fields") or [])
            - {
                "validation_or_holdout",
                "backtest_calls",
                "candidate_created",
                "strategy_modified",
            }
            for item in manifests
        )
        or contract.get("missing_field_semantics", {}).get(
            "historical_fact_inferred"
        )
        is not False
        or contract.get("missing_field_semantics", {}).get(
            "default_value_assigned"
        )
        is not False
        or set(contract.get("prohibited_actions") or []) != prohibited
        or approval.get("approval_status") != "approved"
        or approval.get("approver_type") != "human_user"
        or approval.get("approved_contract_path")
        != LEGACY_MANIFEST_CONTRACT_PATH.as_posix()
        or approval.get("approved_contract_sha256") != sha256_file(contract_path)
        or approval.get("approved_manifest_bindings") != approved_bindings
        or approval.get("legacy_manifest_modification_authorized") is not False
        or approval.get("missing_historical_fact_inference_authorized") is not False
        or approval.get("scope_expansion_authorized") is not False
        or approval.get("network_access_authorized") is not False
        or approval.get("backtest_authorized") is not False
        or approval.get("candidate_creation_authorized") is not False
        or approval.get("strategy_mutation_authorized") is not False
        or approval.get("validation_accesses_authorized") != 0
        or approval.get("holdout_accesses_authorized") != 0
        or approval.get("promotion_authorized") is not False
        or approval.get("single_successor_descriptive_job_authorized") is not True
        or approval.get("failed_job_revival_authorized") is not False
    ):
        raise ValueError("legacy manifest compatibility authority is invalid or drifted")
    return by_path


def _proposal_for_job(repo: Path, job: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(job["payload_json"])
    task = load_document(_inside(repo, str(job["task_path"])))
    proposals = task.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("descriptive worker task has no proposal list")
    matches = [item for item in proposals if item.get("proposal_id") == payload.get("proposal_id")]
    if (
        len(matches) != 1
        or fingerprint(matches[0]) != payload.get("proposal_payload_fingerprint")
        or matches[0].get("descriptive_execution_authorized") is not True
        or matches[0].get("execution_authorized") is not False
        or matches[0].get("descriptive_execution_authorization") != payload.get("authorization")
    ):
        raise ValueError("descriptive worker proposal binding mismatch")
    return matches[0], payload


def _handler_for_proposal(contract: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    method_type = (proposal.get("proposed_method") or {}).get("type")
    handlers = [
        item
        for item in contract["supported_handlers"]
        if item.get("proposal_method_type") == method_type
    ]
    if len(handlers) != 1 or handlers[0].get("handler_id") != "cross_pair_distribution_profile_v1":
        raise ValueError("descriptive worker proposal method is not allowlisted")
    return handlers[0]


def _quantiles(values: pd.Series) -> dict[str, float]:
    result = values.quantile(list(QUANTILES))
    return {f"p{int(level * 100):02d}": round(float(result.loc[level]), 12) for level in QUANTILES}


def _read_datasets(
    repo: Path,
    proposal: dict[str, Any],
    handler: dict[str, Any],
) -> tuple[dict[str, dict[str, pd.DataFrame]], list[dict[str, Any]]]:
    required = proposal.get("required_datasets")
    if (
        not isinstance(required, list)
        or not handler["minimum_dataset_count"] <= len(required) <= handler["maximum_dataset_count"]
    ):
        raise ValueError("descriptive worker dataset count is outside the handler contract")
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    integrity_rows: list[dict[str, Any]] = []
    legacy_compatibility: dict[str, dict[str, Any]] | None = None
    for binding in required:
        if not isinstance(binding, dict) or binding.get("access") != "development_only":
            raise ValueError("descriptive worker dataset access is not Development-only")
        manifest_relative = str(binding.get("manifest_path", ""))
        manifest_path = _inside(repo, manifest_relative)
        if sha256_file(manifest_path) != binding.get("manifest_sha256"):
            raise ValueError("descriptive worker manifest hash mismatch")
        manifest = load_document(manifest_path)
        pairs = manifest.get("pairs")
        expected_attestations = {
            "validation_or_holdout": False,
            "backtest_calls": 0,
            "candidate_created": False,
            "strategy_modified": False,
        }
        missing_attestations = {
            field for field in expected_attestations if field not in manifest
        }
        if missing_attestations and legacy_compatibility is None:
            legacy_compatibility = load_legacy_manifest_compatibility(repo)
        compatibility = (
            legacy_compatibility.get(manifest_relative)
            if legacy_compatibility is not None
            else None
        )
        if compatibility is not None and (
            compatibility.get("dataset_id") != binding.get("dataset_id")
            or compatibility.get("manifest_sha256") != binding.get("manifest_sha256")
        ):
            raise ValueError("legacy manifest compatibility binding mismatch")
        allowed_missing = set(
            (compatibility or {}).get("allowed_missing_fields") or []
        )
        attestations_ok = all(
            (
                manifest.get(field) == expected
                if field in manifest
                else field in allowed_missing
            )
            for field, expected in expected_attestations.items()
        )
        if (
            manifest.get("dataset_id") != binding.get("dataset_id")
            or manifest.get("sealed") is not True
            or manifest.get("campaign_mutable") is not False
            or not str(manifest.get("intended_use", "")).startswith("development")
            or not attestations_ok
            or not isinstance(pairs, list)
            or len(pairs) != 1
        ):
            raise ValueError("descriptive worker manifest boundary check failed")
        symbol = str(pairs[0]).split("/", 1)[0]
        if not symbol or symbol in frames:
            raise ValueError("descriptive worker dataset symbol identity conflict")
        files = manifest.get("files")
        if not isinstance(files, list):
            raise ValueError("descriptive worker manifest files are missing")
        frames[symbol] = {}
        stream_rows = []
        for timeframe in handler["required_timeframes"]:
            suffix = f"-{timeframe}-futures.feather"
            matches = [item for item in files if str(item.get("path", "")).endswith(suffix)]
            if len(matches) != 1:
                raise ValueError("descriptive worker required stream identity conflict")
            file_row = matches[0]
            data_path = _inside(repo, str(file_row["path"]))
            if data_path.stat().st_size != file_row.get("bytes") or sha256_file(data_path) != file_row.get("sha256"):
                raise ValueError("descriptive worker data file integrity mismatch")
            frame = pd.read_feather(data_path)
            if list(frame.columns) != ["date", "open", "high", "low", "close", "volume"]:
                raise ValueError("descriptive worker OHLCV schema mismatch")
            frame = frame.copy()
            frame["date"] = pd.to_datetime(frame["date"], utc=True)
            cadence = pd.to_timedelta(int(timeframe[:-1]), unit="h")
            if (
                frame.empty
                or frame["date"].duplicated().any()
                or not frame["date"].is_monotonic_increasing
                or not (frame["date"].diff().dropna() == cadence).all()
                or not np.isfinite(frame[["open", "high", "low", "close", "volume"]].to_numpy()).all()
                or (frame[["open", "high", "low", "close"]] <= 0).any().any()
                or (frame["volume"] < 0).any()
            ):
                raise ValueError("descriptive worker OHLCV continuity check failed")
            frames[symbol][timeframe] = frame
            stream_rows.append(
                {
                    "timeframe": timeframe,
                    "path": str(file_row["path"]),
                    "bytes": int(file_row["bytes"]),
                    "sha256": str(file_row["sha256"]),
                    "rows": len(frame),
                    "start": frame["date"].iloc[0].isoformat().replace("+00:00", "Z"),
                    "end": frame["date"].iloc[-1].isoformat().replace("+00:00", "Z"),
                    "duplicates": 0,
                    "missing_intervals": 0,
                    "ok": True,
                }
            )
        integrity_rows.append(
            {
                "symbol": symbol,
                "dataset_id": manifest["dataset_id"],
                "manifest_path": manifest_relative,
                "manifest_sha256": binding["manifest_sha256"],
                "manifest_sha256_match": True,
                "sealed": True,
                "intended_use": manifest.get("intended_use"),
                "validation_or_holdout": manifest.get("validation_or_holdout"),
                "legacy_manifest_compatibility": (
                    {
                        "contract_path": LEGACY_MANIFEST_CONTRACT_PATH.as_posix(),
                        "manifest_exactly_allowlisted": True,
                        "allowed_missing_fields": sorted(allowed_missing),
                        "historical_fact_inferred": False,
                        "default_value_assigned": False,
                    }
                    if compatibility is not None
                    else None
                ),
                "streams": stream_rows,
                "ok": True,
            }
        )
    return frames, integrity_rows


def _windows(repo: Path, handler: dict[str, Any], frames: dict[str, dict[str, pd.DataFrame]]) -> tuple[list[dict[str, Any]], str]:
    policy_relative = str(handler["slice_policy_path"])
    policy_path = _inside(repo, policy_relative)
    if sha256_file(policy_path) != handler["slice_policy_sha256"]:
        raise ValueError("descriptive worker slice policy hash mismatch")
    policy = load_document(policy_path)
    if policy.get("validation_data_allowed") is not False or policy.get("slice_count") != 4:
        raise ValueError("descriptive worker slice policy boundary failed")
    starts = [frame["date"].iloc[0] for by_tf in frames.values() for frame in by_tf.values()]
    ends = [
        frame["date"].iloc[-1] + pd.to_timedelta(int(timeframe[:-1]), unit="h")
        for by_tf in frames.values()
        for timeframe, frame in by_tf.items()
    ]
    full_start = max(starts)
    full_end = min(ends)
    windows = [
        {
            "window_id": "full_development",
            "kind": "full_sealed_development",
            "start": full_start.isoformat().replace("+00:00", "Z"),
            "end_exclusive": full_end.isoformat().replace("+00:00", "Z"),
        }
    ]
    for item in policy["slices"]:
        start = pd.Timestamp(item["evaluation_start"])
        end = pd.Timestamp(item["evaluation_end_exclusive"])
        if start < full_start or end > full_end or start >= end:
            raise ValueError("descriptive worker frozen slice is outside the common Development window")
        windows.append(
            {
                "window_id": str(item["slice_id"]),
                "kind": "frozen_evaluation_slice",
                "start": start.isoformat().replace("+00:00", "Z"),
                "end_exclusive": end.isoformat().replace("+00:00", "Z"),
                "expected_1h_candles": int(item["evaluation_1h_candle_count"]),
                "slice_semantic_fingerprint": str(item["slice_semantic_fingerprint"]),
            }
        )
    return windows, policy_relative


def _asset_metrics(frame: pd.DataFrame, timeframe: str) -> dict[str, Any]:
    close = frame["close"].astype(float)
    simple_returns = close.pct_change().dropna()
    log_returns = np.log(close).diff().dropna()
    if len(simple_returns) < 2:
        raise ValueError("descriptive worker window has insufficient return observations")
    return_q = _quantiles(simple_returns)
    volume_q = _quantiles(frame["volume"].astype(float))
    quote_q = _quantiles((frame["close"] * frame["volume"]).astype(float))
    periods = 8760 / int(timeframe[:-1])
    per_period_volatility = float(log_returns.std(ddof=1))
    return {
        "candles": len(frame),
        "return_observations": len(simple_returns),
        "start": frame["date"].iloc[0].isoformat().replace("+00:00", "Z"),
        "end": frame["date"].iloc[-1].isoformat().replace("+00:00", "Z"),
        "cumulative_return": round(float(close.iloc[-1] / close.iloc[0] - 1), 12),
        "arithmetic_return_mean": round(float(simple_returns.mean()), 12),
        "return_quantiles": return_q,
        "realized_volatility_per_period": round(per_period_volatility, 12),
        "annualized_realized_volatility": round(per_period_volatility * math.sqrt(periods), 12),
        "tail_amplitude_p01_p99": round(return_q["p99"] - return_q["p01"], 12),
        "volume_quantiles_base_units": volume_q,
        "quote_volume_proxy_quantiles": quote_q,
    }


def _four_hour_bar_coherence(
    one_hour: pd.DataFrame,
    four_hour: pd.DataFrame,
) -> dict[str, Any]:
    aggregated = (
        one_hour.set_index("date")
        .resample("4h", origin="epoch", closed="left", label="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .reset_index()
    )
    bucket_sizes = (
        one_hour.set_index("date")["close"]
        .resample("4h", origin="epoch", closed="left", label="left")
        .count()
    )
    complete_dates = bucket_sizes[bucket_sizes == 4].index
    boundary_partial_buckets_ignored = int((bucket_sizes != 4).sum())
    aggregated = aggregated[aggregated["date"].isin(complete_dates)].reset_index(
        drop=True
    )
    stored_comparable = four_hour[
        four_hour["date"].isin(complete_dates)
    ].reset_index(drop=True)
    timestamps_exact = bool(
        not aggregated.empty
        and len(aggregated) == len(stored_comparable)
        and aggregated["date"].equals(stored_comparable["date"])
    )
    matched = aggregated.merge(
        stored_comparable,
        on="date",
        how="inner",
        suffixes=("_aggregated", "_stored"),
    )
    if matched.empty:
        return {
            "aggregated_4h_buckets": len(aggregated),
            "stored_4h_buckets": len(stored_comparable),
            "matched_4h_buckets": 0,
            "one_hour_candles_per_bucket": 4,
            "boundary_partial_buckets_ignored": boundary_partial_buckets_ignored,
            "all_comparable_buckets_complete": bool(len(aggregated)),
            "timestamps_exact": timestamps_exact,
            "price_fields_exact": False,
            "max_absolute_price_delta": {},
            "volume_within_floating_tolerance": False,
            "max_absolute_volume_delta": None,
            "all_ok": False,
        }
    price_fields = ["open", "high", "low", "close"]
    price_deltas = {
        field: float(
            np.max(
                np.abs(
                    matched[f"{field}_aggregated"].to_numpy(dtype=float)
                    - matched[f"{field}_stored"].to_numpy(dtype=float)
                )
            )
        )
        for field in price_fields
    }
    volume_delta = np.abs(
        matched["volume_aggregated"].to_numpy(dtype=float)
        - matched["volume_stored"].to_numpy(dtype=float)
    )
    prices_exact = all(delta == 0.0 for delta in price_deltas.values())
    volume_close = bool(
        np.isclose(
            matched["volume_aggregated"].to_numpy(dtype=float),
            matched["volume_stored"].to_numpy(dtype=float),
            rtol=1e-12,
            atol=1e-6,
        ).all()
    )
    return {
        "aggregated_4h_buckets": len(aggregated),
        "stored_4h_buckets": len(stored_comparable),
        "matched_4h_buckets": len(matched),
        "one_hour_candles_per_bucket": 4,
        "boundary_partial_buckets_ignored": boundary_partial_buckets_ignored,
        "all_comparable_buckets_complete": True,
        "timestamps_exact": timestamps_exact,
        "price_fields_exact": prices_exact,
        "max_absolute_price_delta": {
            field: round(delta, 12) for field, delta in price_deltas.items()
        },
        "volume_within_floating_tolerance": volume_close,
        "max_absolute_volume_delta": round(float(np.max(volume_delta)), 12),
        "all_ok": timestamps_exact and prices_exact and volume_close,
    }


def _ranking_coherence(timeframe_results: dict[str, Any]) -> dict[str, Any]:
    one_hour = timeframe_results["1h"]["rankings"]
    four_hour = timeframe_results["4h"]["rankings"]
    metrics = {}
    for metric in sorted(one_hour):
        order_1h = list(one_hour[metric])
        order_4h = list(four_hour[metric])
        if set(order_1h) != set(order_4h) or len(order_1h) < 2:
            raise ValueError("descriptive worker timeframe ranking identity mismatch")
        positions_1h = {symbol: index for index, symbol in enumerate(order_1h)}
        positions_4h = {symbol: index for index, symbol in enumerate(order_4h)}
        symbols = sorted(order_1h)
        pair_count = 0
        concordant = 0
        for left_index, left in enumerate(symbols):
            for right in symbols[left_index + 1 :]:
                pair_count += 1
                direction_1h = positions_1h[left] - positions_1h[right]
                direction_4h = positions_4h[left] - positions_4h[right]
                if direction_1h * direction_4h > 0:
                    concordant += 1
        discordant = pair_count - concordant
        metrics[metric] = {
            "order_1h": order_1h,
            "order_4h": order_4h,
            "exact_order_match": order_1h == order_4h,
            "pairwise_concordant": concordant,
            "pairwise_discordant": discordant,
            "pairwise_total": pair_count,
            "kendall_tau_no_ties": round(
                (concordant - discordant) / pair_count, 12
            ),
        }
    return {
        "metrics": metrics,
        "exact_order_match_count": sum(
            item["exact_order_match"] for item in metrics.values()
        ),
        "metric_count": len(metrics),
        "mean_kendall_tau_no_ties": round(
            float(
                np.mean(
                    [item["kendall_tau_no_ties"] for item in metrics.values()]
                )
            ),
            12,
        ),
    }


def build_distribution_profile(
    repo: Path,
    job: dict[str, Any],
    proposal: dict[str, Any],
    handler: dict[str, Any],
) -> tuple[dict[str, Any], str, str]:
    frames, integrity_rows = _read_datasets(repo, proposal, handler)
    windows, slice_policy_path = _windows(repo, handler, frames)
    result_windows = []
    for window in windows:
        start = pd.Timestamp(window["start"])
        end = pd.Timestamp(window["end_exclusive"])
        timeframe_results = {}
        selected_by_symbol: dict[str, dict[str, pd.DataFrame]] = {}
        for timeframe in handler["required_timeframes"]:
            assets = {}
            for symbol, by_timeframe in sorted(frames.items()):
                selected = by_timeframe[timeframe]
                selected = selected[(selected["date"] >= start) & (selected["date"] < end)].copy()
                if timeframe == "1h" and "expected_1h_candles" in window and len(selected) != window["expected_1h_candles"]:
                    raise ValueError("descriptive worker frozen slice candle count mismatch")
                assets[symbol] = _asset_metrics(selected, timeframe)
                selected_by_symbol.setdefault(symbol, {})[timeframe] = selected
            ranking_fields = {
                "cumulative_return": lambda value: value["cumulative_return"],
                "annualized_realized_volatility": lambda value: value["annualized_realized_volatility"],
                "tail_amplitude_p01_p99": lambda value: value["tail_amplitude_p01_p99"],
                "quote_volume_proxy_p50": lambda value: value["quote_volume_proxy_quantiles"]["p50"],
            }
            rankings = {
                name: [
                    symbol
                    for symbol, _ in sorted(
                        assets.items(), key=lambda item: (-selector(item[1]), item[0])
                    )
                ]
                for name, selector in ranking_fields.items()
            }
            timeframe_results[timeframe] = {"assets": assets, "rankings": rankings}
        bar_coherence = {
            symbol: _four_hour_bar_coherence(
                selected_by_symbol[symbol]["1h"],
                selected_by_symbol[symbol]["4h"],
            )
            for symbol in sorted(selected_by_symbol)
        }
        result_windows.append(
            {
                **window,
                "timeframes": timeframe_results,
                "timeframe_coherence": {
                    "aggregation_1h_to_4h": bar_coherence,
                    "all_aggregated_bars_match": all(
                        item["all_ok"] for item in bar_coherence.values()
                    ),
                    "relative_ranking_coherence": _ranking_coherence(
                        timeframe_results
                    ),
                },
            }
        )
    analysis = {
        "schema_version": "discovery-cross-pair-descriptive-analysis-v1",
        "proposal_id": proposal["proposal_id"],
        "generated_at": str(job["created_at"]),
        "handler": {
            "handler_id": handler["handler_id"],
            "handler_contract_sha256": sha256_file(repo / HANDLER_CONTRACT_PATH),
            "proposal_payload_fingerprint": fingerprint(proposal),
        },
        "execution_scope": {
            "development_only": True,
            "pairs": [row["symbol"] for row in integrity_rows],
            "timeframes": list(handler["required_timeframes"]),
            "network_accessed": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "backtests": 0,
            "signals_or_trades_generated": 0,
            "candidates_created": 0,
            "strategy_changes": 0,
            "promotions": 0,
        },
        "source_integrity": {
            "all_ok": True,
            "datasets": integrity_rows,
            "slice_policy_path": slice_policy_path,
            "slice_policy_sha256": handler["slice_policy_sha256"],
            "slice_policy_validation_exposure": False,
        },
        "methodology": {
            "windows": windows,
            "return_definition": "simple close-to-close returns computed inside each frozen window",
            "realized_volatility_definition": "sample standard deviation of log returns annualized by timeframe",
            "tail_amplitude_definition": "p99(simple return) - p01(simple return)",
            "volume_definition": "base-unit volume and close*volume quote-notional proxy quantiles",
            "ranking_definition": "descending metric value with deterministic alphabetical tie break",
            "timeframe_coherence_definition": "exact UTC 4h OHLC aggregation from four 1h candles, volume within floating tolerance, plus no-tie Kendall rank concordance across 1h and 4h",
        },
        "results": {"windows": result_windows},
        "summary": {
            "window_count": len(result_windows),
            "asset_count": len(frames),
            "all_windows_1h_to_4h_aggregation_match": all(
                window["timeframe_coherence"]["all_aggregated_bars_match"]
                for window in result_windows
            ),
            "full_window_mean_timeframe_rank_tau": result_windows[0][
                "timeframe_coherence"
            ]["relative_ranking_coherence"]["mean_kendall_tau_no_ties"],
            "interpretation": "descriptive_only_no_strategy_generalization_or_promotion_claim",
        },
        "attestation": {
            "generated_artifacts_only": list(proposal["required_artifacts"]),
            "prohibited_activities_performed": False,
        },
    }
    report_lines = [
        f"# Development-only descriptive profile: {proposal['proposal_id']}",
        "",
        f"- Handler: `{handler['handler_id']}`",
        f"- Datasets: {len(frames)} sealed Development manifests",
        f"- Windows: {len(result_windows)} (full window plus four frozen slices)",
        "- Network, backtest, signals, trades, Candidate, strategy changes, Validation and Holdout: `0`",
        "",
        "## Full-window rankings",
        "",
        "| Timeframe | Return | Realized volatility | Tail amplitude | Quote-volume proxy p50 |",
        "|---|---|---|---|---|",
    ]
    full = result_windows[0]["timeframes"]
    for timeframe in handler["required_timeframes"]:
        rankings = full[timeframe]["rankings"]
        report_lines.append(
            "| " + timeframe + " | " + " > ".join(rankings["cumulative_return"])
            + " | " + " > ".join(rankings["annualized_realized_volatility"])
            + " | " + " > ".join(rankings["tail_amplitude_p01_p99"])
            + " | " + " > ".join(rankings["quote_volume_proxy_p50"]) + " |"
        )
    full_coherence = result_windows[0]["timeframe_coherence"]
    report_lines.extend(
        [
            "",
            "## 1h—4h timeframe coherence",
            "",
            f"- Exact UTC 1h→4h OHLCV aggregation check across all assets: `{str(full_coherence['all_aggregated_bars_match']).lower()}`",
            f"- Mean no-tie Kendall rank concordance across four descriptive metrics: `{full_coherence['relative_ranking_coherence']['mean_kendall_tau_no_ties']}`",
            "",
            "| Metric | Exact order match | Kendall tau |",
            "|---|---:|---:|",
        ]
    )
    for metric, coherence in full_coherence["relative_ranking_coherence"][
        "metrics"
    ].items():
        report_lines.append(
            f"| {metric} | {str(coherence['exact_order_match']).lower()} | {coherence['kendall_tau_no_ties']} |"
        )
    report_lines.extend(
        [
            "",
            "## Governance conclusion",
            "",
            "This artifact is descriptive evidence only. It does not authorize strategy generalization, backtesting, Candidate creation, promotion, or trading.",
            "",
        ]
    )
    return analysis, "\n".join(report_lines), str(handler["result_code"])


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _publish(path: Path, content: bytes) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
        return True
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError("descriptive worker output conflicts with existing artifact")
        return False


def execute_claimed_job(
    repo_root: str | Path,
    registry_path: str | Path,
    job: dict[str, Any],
    worker_id: str,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    contract, _ = load_handler_authority(repo)
    proposal, _ = _proposal_for_job(repo, job)
    handler = _handler_for_proposal(contract, proposal)
    expected_artifacts = [
        f"research/analysis/{proposal['proposal_id']}/analysis.json",
        f"reports/audits/{proposal['proposal_id']}/report.md",
    ]
    if proposal.get("required_artifacts") != expected_artifacts or proposal.get("allowed_changes") != expected_artifacts:
        raise ValueError("descriptive worker output scope mismatch")
    analysis, report, result_code = build_distribution_profile(repo, job, proposal, handler)
    contents = [_json_bytes(analysis), report.encode("utf-8")]
    paths = [_inside(repo, relative, must_exist=False) for relative in expected_artifacts]
    created: list[tuple[Path, bytes]] = []
    try:
        for path, content in zip(paths, contents):
            if _publish(path, content):
                created.append((path, content))
        return worker_queue.finish_descriptive_execution_job(
            repo,
            registry_path,
            str(job["job_id"]),
            worker_id,
            result_code,
        )
    except Exception:
        for path, content in reversed(created):
            if path.is_file() and path.read_bytes() == content:
                path.unlink()
        raise


def run_once(
    repo_root: str | Path,
    registry_path: str | Path,
    worker_id: str,
    *,
    lease_seconds: int = 900,
) -> dict[str, Any] | None:
    repo = Path(repo_root).resolve()
    load_handler_authority(repo)
    job = worker_queue.claim_next_job(
        registry_path,
        worker_id,
        lease_seconds=lease_seconds,
        stages={"descriptive_execution"},
    )
    if job is None:
        return None
    try:
        return execute_claimed_job(repo, registry_path, job, worker_id)
    except Exception as exc:
        if isinstance(exc, ValueError):
            reason_code = "descriptive_worker_contract_or_input_failed"
        elif isinstance(exc, OSError):
            reason_code = "descriptive_worker_io_failed"
        else:
            reason_code = "descriptive_worker_internal_failed"
        worker_queue.fail_descriptive_execution_job(
            registry_path,
            str(job["job_id"]),
            worker_id,
            reason_code,
        )
        raise


def drain(
    repo_root: str | Path,
    registry_path: str | Path,
    worker_id: str,
    *,
    max_jobs: int = 16,
    lease_seconds: int = 900,
    progress_callback: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Process a bounded batch and stop immediately on the first failed job."""
    if max_jobs < 1 or max_jobs > 100:
        raise ValueError("descriptive worker drain bound is invalid")
    results = []
    for _ in range(max_jobs):
        if progress_callback is not None:
            progress_callback()
        result = run_once(
            repo_root,
            registry_path,
            worker_id,
            lease_seconds=lease_seconds,
        )
        if result is None:
            break
        results.append(result)
        if progress_callback is not None:
            progress_callback()
    return {
        "schema_version": "research-descriptive-worker-drain-v1",
        "worker_id": worker_id,
        "completed_jobs": len(results),
        "max_jobs": max_jobs,
        "queue_empty_for_stage": len(results) < max_jobs,
        "result_ids": [item["result_id"] for item in results],
        "candidate_created": False,
        "strategy_modified": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--lease-seconds", type=int, default=900)
    parser.add_argument("--max-jobs", type=int, default=1)
    args = parser.parse_args(argv)
    result = drain(
        args.repo_root,
        args.registry,
        args.worker_id,
        max_jobs=args.max_jobs,
        lease_seconds=args.lease_seconds,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
