#!/usr/bin/env python3
"""Seal an offline Freqtrade dataset snapshot from a staging directory."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_experiment import sha256_file


FORBIDDEN_NAMES = {".env", "config_live.json", "monitor.env"}
FORBIDDEN_PARTS = {"secrets", "deploy", ".git"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pair_stems(pair: str) -> list[str]:
    return [
        pair.replace("/", "_").replace(":", "_"),
        pair.replace("/", "_"),
        pair.replace("/", ""),
    ]


def reject_forbidden(path: Path) -> None:
    lowered_parts = {part.casefold() for part in path.parts}
    if lowered_parts & FORBIDDEN_PARTS:
        raise ValueError(f"forbidden path component in dataset: {path}")
    if path.name.casefold() in {name.casefold() for name in FORBIDDEN_NAMES}:
        raise ValueError(f"forbidden file in dataset: {path}")
    if path.is_symlink():
        raise ValueError(f"symlink is not allowed in dataset: {path}")


def discover_files(staging: Path, pair: str, timeframe: str, additional_timeframes: list[str] | None = None) -> list[Path]:
    stems = pair_stems(pair)
    accepted_timeframes = {timeframe, *(additional_timeframes or [])}
    files = []
    for path in sorted(staging.rglob("*")):
        reject_forbidden(path)
        if path.is_file():
            if path.stat().st_size <= 0:
                raise ValueError(f"empty dataset file: {path}")
            name = path.name
            is_requested_timeframe = any(tf in name for tf in accepted_timeframes)
            is_funding_rate = "funding_rate" in name and "8h" in name
            if any(stem in name for stem in stems) and (is_requested_timeframe or is_funding_rate):
                files.append(path)
    if not files:
        raise ValueError(f"no data file found for pair={pair} timeframe={timeframe}")
    return files


def parse_timerange(value: str) -> tuple[str, str]:
    if "-" not in value:
        raise ValueError(f"timerange must use YYYYMMDD-YYYYMMDD: {value}")
    start, end = value.split("-", 1)
    if len(start) != 8 or len(end) != 8 or not start.isdigit() or not end.isdigit():
        raise ValueError(f"timerange must use YYYYMMDD-YYYYMMDD: {value}")
    return start, end


def read_data_bounds(path: Path) -> tuple[str | None, str | None, int]:
    if path.suffix.lower() == ".feather":
        import pandas as pd  # type: ignore

        frame = pd.read_feather(path, columns=["date"])
        if frame.empty or "date" not in frame:
            return None, None, 0
        return str(frame["date"].min()), str(frame["date"].max()), int(len(frame))
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows: list[Any]
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            rows = payload.get("data") or payload.get("candles") or []
        else:
            rows = []
        dates = []
        for row in rows:
            if isinstance(row, dict) and row.get("date"):
                dates.append(str(row["date"]))
            elif isinstance(row, list) and row:
                dates.append(str(row[0]))
        if not dates:
            return None, None, len(rows)
        return min(dates), max(dates), len(rows)
    raise ValueError(f"unsupported dataset file format: {path.suffix}")


def yyyymmdd(value: str) -> str:
    return value[:10].replace("-", "")


def validate_timerange_coverage(files: list[Path], timerange: str) -> list[dict]:
    requested_start, requested_end = parse_timerange(timerange)
    coverage = []
    covered = False
    for path in files:
        start, end, rows = read_data_bounds(path)
        coverage.append({"file": path.name, "start": start, "end": end, "rows": rows})
        if start and end and yyyymmdd(start) <= requested_start and requested_end <= yyyymmdd(end):
            covered = True
    if not covered:
        raise ValueError(f"dataset files do not cover requested timerange: {timerange}")
    return coverage


def copy_files(files: list[Path], staging: Path, target_data: Path) -> list[Path]:
    if target_data.exists():
        def make_writable(function, path, _exc_info):
            os.chmod(path, stat.S_IWRITE)
            function(path)

        shutil.rmtree(target_data, onerror=make_writable)
    target_data.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in files:
        rel = src.relative_to(staging)
        dst = target_data / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        os.chmod(dst, 0o444)
        copied.append(dst)
    return copied


def aggregate_hash(entries: list[dict]) -> str:
    import hashlib

    payload = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_manifest(path: Path, manifest: dict) -> None:
    lines = []
    for key, value in manifest.items():
        if isinstance(value, (list, dict)):
            lines.append(f"{key}: {json.dumps(value, sort_keys=True)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def seal_snapshot(
    repo_root: str | Path,
    staging_dir: str | Path,
    dataset_id: str,
    exchange: str,
    trading_mode: str,
    pair: str,
    timeframe: str,
    timerange: str,
    source: str,
    margin_mode: str | None = None,
    candle_types: list[str] | None = None,
    execution_baseline_only: bool = False,
    suitable_for_strategy_ranking: bool = True,
    funding_model_synthetic: bool = False,
    additional_timeframes: list[str] | None = None,
) -> dict:
    repo_root = Path(repo_root).resolve()
    staging = Path(staging_dir).resolve()
    if not staging.exists() or not staging.is_dir():
        raise ValueError(f"staging directory missing: {staging}")
    snapshot_root = repo_root / "research" / "data" / "snapshots" / dataset_id
    target_data = snapshot_root / "data"
    files = discover_files(staging, pair, timeframe, additional_timeframes=additional_timeframes)
    coverage = validate_timerange_coverage(files, timerange)
    copied = copy_files(files, staging, target_data)
    entries = []
    for path in copied:
        rel = path.relative_to(repo_root).as_posix()
        entries.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    digest = aggregate_hash(entries)
    manifest = {
        "dataset_id": dataset_id,
        "exchange": exchange,
        "trading_mode": trading_mode,
        "margin_mode": margin_mode,
        "timerange": timerange,
        "timeframes": sorted({timeframe, *(additional_timeframes or [])}),
        "pairs": [pair],
        "candle_types": candle_types or ["ohlcv"],
        "data_path": target_data.relative_to(repo_root).as_posix(),
        "files": entries,
        "coverage": coverage,
        "aggregate_sha256": digest,
        "source": source,
        "created_at": utc_now(),
        "campaign_mutable": False,
        "network_accessed_during_campaign": False,
        "execution_baseline_only": execution_baseline_only,
        "suitable_for_strategy_ranking": suitable_for_strategy_ranking,
        "funding_model_synthetic": funding_model_synthetic,
        "sealed": True,
        "sealed_at": utc_now(),
        "sealed_by": "scripts/seal_dataset_snapshot.py",
        "tool_version": 1,
    }
    snapshot_root.mkdir(parents=True, exist_ok=True)
    write_manifest(snapshot_root / "manifest.yaml", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Seal a fixed Freqtrade dataset snapshot.")
    parser.add_argument("--staging", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--exchange", required=True)
    parser.add_argument("--trading-mode", required=True)
    parser.add_argument("--pair", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--timerange", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--margin-mode")
    parser.add_argument("--candle-types", nargs="*", default=["ohlcv"])
    parser.add_argument("--execution-baseline-only", action="store_true")
    parser.add_argument("--suitable-for-strategy-ranking", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--funding-model-synthetic", action="store_true")
    parser.add_argument("--additional-timeframes", nargs="*")
    args = parser.parse_args()
    manifest = seal_snapshot(
        Path.cwd(),
        args.staging,
        args.dataset_id,
        args.exchange,
        args.trading_mode,
        args.pair,
        args.timeframe,
        args.timerange,
        args.source,
        margin_mode=args.margin_mode,
        candle_types=args.candle_types,
        execution_baseline_only=args.execution_baseline_only,
        suitable_for_strategy_ranking=args.suitable_for_strategy_ranking,
        funding_model_synthetic=args.funding_model_synthetic,
        additional_timeframes=args.additional_timeframes,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
