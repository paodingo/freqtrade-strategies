#!/usr/bin/env python3
"""Provision the human-approved BNB/XRP Development snapshots from public archives only."""

from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from build_stage3c2p_provisioning import (
    ArchiveSpec,
    download_archive,
    iso,
    stable_hash,
    timeframe_delta,
    validate_public_archive_url,
)
from research_control import utc_now
from run_experiment import dump_json, dump_manifest, repo_rel, sha256_file


AUTHORIZATION = (
    "批准数据准备范围为 BNB/USDT:USDT 与 XRP/USDT:USDT；仅使用 Binance 公共 "
    "USD-M 接口，按 20240101-20240830 窗口准备 1h futures、4h futures、8h mark、"
    "8h funding_rate，先进入 staging，校验零缺口后再封存 Development manifest；"
    "禁止私有 API、Validation/Holdout、回测、Candidate 和策略修改；任一必需数据流"
    "不完整立即停止，不自动替换币种。"
)
BASELINE_DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
BASELINE_MANIFEST = Path(
    "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml"
)
BASELINE_MANIFEST_SHA256 = "e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13"
STAGING_ROOT = Path("research/data/staging/additional-pairs-bnb-xrp-20240101-20240830-v1")
ARCHIVE_ROOT = "https://data.binance.vision/data/futures/um/monthly"
MONTHS = tuple(f"2024-{month:02d}" for month in range(1, 9))
WINDOW_START = pd.Timestamp("2024-01-01T00:00:00Z")
WARMUP_END = pd.Timestamp("2024-02-03T07:00:00Z")
EVALUATION_START = pd.Timestamp("2024-02-03T08:00:00Z")
EVALUATION_END = pd.Timestamp("2024-08-29T15:00:00Z")


@dataclass(frozen=True)
class PairScope:
    pair: str
    symbol: str
    stem: str
    dataset_id: str


@dataclass(frozen=True)
class StreamScope:
    key: str
    candle_type: str
    timeframe: str
    end: pd.Timestamp


PAIR_SCOPES = (
    PairScope(
        pair="BNB/USDT:USDT",
        symbol="BNBUSDT",
        stem="BNB_USDT_USDT",
        dataset_id="futures-dev-bnb-usdt-usdt-20240101-20240830-v1",
    ),
    PairScope(
        pair="XRP/USDT:USDT",
        symbol="XRPUSDT",
        stem="XRP_USDT_USDT",
        dataset_id="futures-dev-xrp-usdt-usdt-20240101-20240830-v1",
    ),
)
STREAM_SCOPES = (
    StreamScope("futures_1h", "futures", "1h", pd.Timestamp("2024-08-29T15:00:00Z")),
    StreamScope("futures_4h", "futures", "4h", pd.Timestamp("2024-08-29T12:00:00Z")),
    StreamScope("mark_8h", "mark", "8h", pd.Timestamp("2024-08-29T08:00:00Z")),
    StreamScope(
        "funding_rate_8h",
        "funding_rate",
        "8h",
        pd.Timestamp("2024-08-29T08:00:00Z"),
    ),
)


def archive_url(pair: PairScope, stream: StreamScope, month: str) -> str:
    if stream.candle_type == "futures":
        return (
            f"{ARCHIVE_ROOT}/klines/{pair.symbol}/{stream.timeframe}/"
            f"{pair.symbol}-{stream.timeframe}-{month}.zip"
        )
    if stream.candle_type == "mark":
        return (
            f"{ARCHIVE_ROOT}/markPriceKlines/{pair.symbol}/{stream.timeframe}/"
            f"{pair.symbol}-{stream.timeframe}-{month}.zip"
        )
    if stream.candle_type == "funding_rate":
        return (
            f"{ARCHIVE_ROOT}/fundingRate/{pair.symbol}/"
            f"{pair.symbol}-fundingRate-{month}.zip"
        )
    raise ValueError(f"unsupported candle type: {stream.candle_type}")


def planned_archives() -> list[tuple[PairScope, StreamScope, str, str]]:
    rows = []
    for pair in PAIR_SCOPES:
        for stream in STREAM_SCOPES:
            for month in MONTHS:
                url = archive_url(pair, stream, month)
                if validate_public_archive_url(url).get("allowed") is not True:
                    raise RuntimeError(f"public archive policy rejected: {url}")
                rows.append((pair, stream, month, url))
    return rows


def expected_rows(stream: StreamScope) -> int:
    return int((stream.end - WINDOW_START) / timeframe_delta(stream.timeframe)) + 1


def validate_window(frame: pd.DataFrame, stream: StreamScope) -> tuple[pd.DataFrame, dict[str, Any]]:
    current = frame.copy()
    current["date"] = pd.to_datetime(current["date"], utc=True)
    if stream.candle_type == "funding_rate":
        current["date"] = current["date"].dt.round("s")
    current = current[
        (current["date"] >= WINDOW_START) & (current["date"] <= stream.end)
    ].sort_values("date").reset_index(drop=True)
    dates = current["date"]
    duplicates = int(dates.duplicated().sum())
    expected_delta = timeframe_delta(stream.timeframe)
    missing_intervals = int((dates.diff().dropna() != expected_delta).sum())
    invalid_ohlc = 0
    if stream.candle_type in {"futures", "mark"} and not current.empty:
        invalid_ohlc = int(
            (
                (current["high"] < current[["open", "close"]].max(axis=1))
                | (current["low"] > current[["open", "close"]].min(axis=1))
            ).sum()
        )
    negative_volume = int((current["volume"].astype(float) < 0).sum()) if not current.empty else 0
    target_rows = expected_rows(stream)
    exact_start = bool(not current.empty and dates.iloc[0] == WINDOW_START)
    exact_end = bool(not current.empty and dates.iloc[-1] == stream.end)
    ok = bool(
        len(current) == target_rows
        and exact_start
        and exact_end
        and duplicates == 0
        and missing_intervals == 0
        and invalid_ohlc == 0
        and negative_volume == 0
    )
    check = {
        "ok": ok,
        "rows": int(len(current)),
        "expected_rows": target_rows,
        "start": iso(dates.iloc[0]) if not current.empty else None,
        "required_start": iso(WINDOW_START),
        "end": iso(dates.iloc[-1]) if not current.empty else None,
        "required_end": iso(stream.end),
        "duplicates": duplicates,
        "missing_intervals": missing_intervals,
        "invalid_ohlc": invalid_ohlc,
        "negative_volume": negative_volume,
        "timeframe": stream.timeframe,
        "candle_type": stream.candle_type,
        "timezone": "UTC",
        "format": "feather",
    }
    return current, check


def write_exact_feather(frame: pd.DataFrame, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.reset_index(drop=True).to_feather(destination, compression="lz4", compression_level=9)


def aggregate_hash(entries: list[dict[str, Any]]) -> str:
    return stable_hash(
        [{key: item[key] for key in ("path", "bytes", "sha256")} for item in entries]
    )


def ensure_new_roots(repo: Path) -> Path:
    staging = (repo / STAGING_ROOT).resolve()
    allowed = (repo / "research/data/staging").resolve()
    if allowed not in staging.parents:
        raise RuntimeError("staging path escaped authorized root")
    if staging.exists():
        raise RuntimeError(f"staging path already exists: {STAGING_ROOT.as_posix()}")
    for pair in PAIR_SCOPES:
        snapshot = (repo / "research/data/snapshots" / pair.dataset_id).resolve()
        snapshot_parent = (repo / "research/data/snapshots").resolve()
        if snapshot_parent not in snapshot.parents:
            raise RuntimeError("snapshot path escaped authorized root")
        if snapshot.exists():
            raise RuntimeError(f"snapshot already exists: {pair.dataset_id}")
    staging.mkdir(parents=True)
    return staging


def _download_one(
    staging: Path,
    pair: PairScope,
    stream: StreamScope,
    month: str,
    url: str,
) -> tuple[str, str, pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    audit = {
        "requests": [],
        "summary": {"request_count": 0},
    }
    frame, source = download_archive(
        ArchiveSpec(stream.candle_type, stream.timeframe, url),
        staging / pair.symbol / "_downloads",
        audit,
        timeout=120,
    )
    source.update(
        {
            "pair": pair.pair,
            "symbol": pair.symbol,
            "stream_key": stream.key,
            "month": month,
        }
    )
    return pair.pair, stream.key, frame, source, list(audit["requests"])


def download_all(staging: Path, workers: int) -> tuple[dict[tuple[str, str], list[pd.DataFrame]], list[dict[str, Any]], list[dict[str, Any]]]:
    frames: dict[tuple[str, str], list[pd.DataFrame]] = {}
    sources: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    tasks = planned_archives()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_download_one, staging, pair, stream, month, url): (
                pair,
                stream,
                month,
            )
            for pair, stream, month, url in tasks
        }
        completed = 0
        for future in as_completed(futures):
            pair, stream, month = futures[future]
            try:
                pair_name, stream_key, frame, source, audit_rows = future.result()
            except Exception as exc:
                raise RuntimeError(
                    f"required_archive_failed:{pair.pair}:{stream.key}:{month}:{type(exc).__name__}"
                ) from exc
            frames.setdefault((pair_name, stream_key), []).append(frame)
            sources.append(source)
            requests.extend(audit_rows)
            completed += 1
            print(
                f"downloaded {completed}/{len(tasks)} {pair.symbol} {stream.key} {month}",
                flush=True,
            )
    return frames, sources, requests


def build_staging_files(
    staging: Path,
    frames: dict[tuple[str, str], list[pd.DataFrame]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[tuple[str, str], Path]]:
    checks: dict[str, dict[str, dict[str, Any]]] = {}
    paths: dict[tuple[str, str], Path] = {}
    failures = []
    for pair in PAIR_SCOPES:
        checks[pair.pair] = {}
        for stream in STREAM_SCOPES:
            pieces = frames.get((pair.pair, stream.key), [])
            if len(pieces) != len(MONTHS):
                failures.append(f"{pair.pair}:{stream.key}:archive_count")
                continue
            combined = pd.concat(pieces, ignore_index=True)
            window, check = validate_window(combined, stream)
            checks[pair.pair][stream.key] = check
            if not check["ok"]:
                failures.append(f"{pair.pair}:{stream.key}:integrity")
                continue
            destination = staging / pair.symbol / "futures" / (
                f"{pair.stem}-{stream.timeframe}-{stream.candle_type}.feather"
            )
            write_exact_feather(window, destination)
            check["bytes"] = destination.stat().st_size
            check["sha256"] = sha256_file(destination)
            check["staging_path"] = destination.relative_to(staging).as_posix()
            paths[(pair.pair, stream.key)] = destination
    if failures:
        raise RuntimeError("required_stream_incomplete:" + ",".join(sorted(failures)))
    return checks, paths


def seal_snapshots(
    repo: Path,
    staging: Path,
    checks: dict[str, dict[str, dict[str, Any]]],
    paths: dict[tuple[str, str], Path],
    sources: list[dict[str, Any]],
    requests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    manifests = []
    created_at = utc_now()
    for pair in PAIR_SCOPES:
        snapshot_root = repo / "research/data/snapshots" / pair.dataset_id
        data_root = snapshot_root / "data/futures"
        entries = []
        coverage = []
        pair_checks = checks[pair.pair]
        for stream in STREAM_SCOPES:
            source = paths[(pair.pair, stream.key)]
            destination = data_root / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            entry = {
                "path": repo_rel(repo, destination),
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
            entries.append(entry)
            check = pair_checks[stream.key]
            coverage.append(
                {
                    "file": destination.name,
                    "rows": check["rows"],
                    "start": check["start"],
                    "end": check["end"],
                    "candle_type": stream.candle_type,
                    "timeframe": stream.timeframe,
                }
            )
        pair_sources = sorted(
            (source for source in sources if source["pair"] == pair.pair),
            key=lambda item: (item["stream_key"], item["month"]),
        )
        pair_requests = [
            request
            for request in requests
            if f"/{pair.symbol}/" in str(request.get("path", ""))
        ]
        manifest = {
            "schema_version": "cross-pair-development-snapshot-v1",
            "dataset_id": pair.dataset_id,
            "parent_boundary_dataset": BASELINE_DATASET_ID,
            "parent_boundary_manifest": BASELINE_MANIFEST.as_posix(),
            "parent_boundary_manifest_sha256": BASELINE_MANIFEST_SHA256,
            "exchange": "binance",
            "trading_mode": "futures",
            "margin_mode": "isolated",
            "pairs": [pair.pair],
            "timeframes": ["1h", "4h", "8h"],
            "candle_types": ["futures", "mark", "funding_rate"],
            "data_path": repo_rel(repo, snapshot_root / "data"),
            "files": entries,
            "coverage": coverage,
            "validation_checks": pair_checks,
            "aggregate_sha256": aggregate_hash(entries),
            "start": iso(WINDOW_START),
            "end": iso(EVALUATION_END),
            "warmup_range": {"start": iso(WINDOW_START), "end": iso(WARMUP_END)},
            "evaluation_range": {
                "start": iso(EVALUATION_START),
                "end": iso(EVALUATION_END),
                "main_1h_candles": 5000,
            },
            "source_lineage": pair_sources,
            "source_access": "binance_public_data_vision_usdm_monthly",
            "network_policy": {
                "allowed_hosts": ["data.binance.vision"],
                "public_only": True,
                "private_api_used": False,
                "request_count": len(pair_requests),
            },
            "human_authorization": AUTHORIZATION,
            "network_accessed_during_provisioning": True,
            "validation_or_holdout": False,
            "backtest_calls": 0,
            "candidate_created": False,
            "strategy_modified": False,
            "intended_use": "development_descriptive_cross_pair_generalization_only",
            "suitable_for_strategy_iteration": False,
            "suitable_for_strategy_ranking": False,
            "suitable_for_stage_promotion": False,
            "campaign_mutable": False,
            "sealed": True,
            "sealed_at": created_at,
            "sealed_by": "scripts/provision_additional_pair_development_data.py",
        }
        dump_manifest(snapshot_root / "manifest.yaml", manifest)
        manifests.append(manifest)
    return manifests


def provision(repo: Path, workers: int) -> dict[str, Any]:
    repo = repo.resolve()
    baseline = repo / BASELINE_MANIFEST
    if not baseline.is_file() or sha256_file(baseline) != BASELINE_MANIFEST_SHA256:
        raise RuntimeError("baseline_manifest_fingerprint_mismatch")
    staging = ensure_new_roots(repo)
    frames, sources, requests = download_all(staging, workers)
    checks, paths = build_staging_files(staging, frames)
    staging_manifest = {
        "schema_version": "additional-pair-staging-manifest-v1",
        "created_at": utc_now(),
        "authorization": AUTHORIZATION,
        "pairs": [pair.pair for pair in PAIR_SCOPES],
        "months": list(MONTHS),
        "required_streams": [stream.key for stream in STREAM_SCOPES],
        "checks": checks,
        "sources": sorted(
            sources,
            key=lambda item: (item["pair"], item["stream_key"], item["month"]),
        ),
        "network_audit": {
            "allowed_hosts": ["data.binance.vision"],
            "public_only": True,
            "private_api_used": False,
            "request_count": len(requests),
            "requests": sorted(requests, key=lambda item: str(item.get("path", ""))),
        },
        "forbidden_actions": {
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "backtest_calls": 0,
            "candidate_created": False,
            "strategy_modified": False,
            "automatic_pair_substitution": False,
        },
    }
    dump_json(staging / "provisioning-manifest.json", staging_manifest)
    manifests = seal_snapshots(repo, staging, checks, paths, sources, requests)
    return {
        "status": "sealed",
        "pairs": [pair.pair for pair in PAIR_SCOPES],
        "dataset_ids": [manifest["dataset_id"] for manifest in manifests],
        "network_request_count": len(requests),
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "backtest_calls": 0,
        "candidate_created": False,
        "strategy_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 8:
        parser.error("--workers must be between 1 and 8")
    result = provision(Path(args.repo_root), args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
