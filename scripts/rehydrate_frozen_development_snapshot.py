#!/usr/bin/env python3
"""Rehydrate the sealed development snapshot from an explicitly supplied local staging root."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
PAIR_STEM = "BTC_USDT_USDT"
START = pd.Timestamp("2024-01-01T00:00:00Z")
END = pd.Timestamp("2024-08-29T15:00:00Z")
FILES = {
    "1h-futures": {
        "name": f"{PAIR_STEM}-1h-futures.feather",
        "rows": 5800,
        "sha256": "b5d2dd9cb7a34115ccdb2fd8b2044c1dc160f4d1e03af345387beb08452d0491",
        "bytes": 170914,
    },
    "4h-futures": {
        "name": f"{PAIR_STEM}-4h-futures.feather",
        "rows": 1450,
        "sha256": "3f2df1df5332d4e9a06330205da0717a6eaa3fee4b1da4367432db1242fbab60",
        "bytes": 48506,
    },
    "8h-mark": {
        "name": f"{PAIR_STEM}-8h-mark.feather",
        "rows": 725,
        "sha256": "658aa6b5d082a092e7a858744251a8f65f5c330c2ffddd45d570c3c9572f5922",
        "bytes": 28202,
    },
    "8h-funding_rate": {
        "name": f"{PAIR_STEM}-8h-funding_rate.feather",
        "rows": 725,
        "sha256": "c830fdaa85e4ad375210b36bf0cf1e5f96aee426259e3762c5d785947b8fe585",
        "bytes": 22842,
    },
}


class RehydrationInvalid(RuntimeError):
    """Raised when local lineage cannot reproduce the sealed snapshot exactly."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(value: Any) -> str:
    return pd.Timestamp(value).isoformat().replace("+00:00", "Z")


def rehydrate(repo: Path, staging_root: Path) -> dict[str, Any]:
    destination = (
        repo
        / "research/data/snapshots"
        / DATASET_ID
        / "data/futures"
    )
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for key, expected in FILES.items():
        source = staging_root / expected["name"]
        if not source.is_file():
            raise RehydrationInvalid(f"sealed_local_lineage_missing:{source}")
        frame = pd.read_feather(source)
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        selected = (
            frame.loc[(frame["date"] >= START) & (frame["date"] <= END)]
            .sort_values("date")
            .drop_duplicates("date")
            .reset_index(drop=True)
        )
        target = destination / expected["name"]
        selected.to_feather(
            target, compression="lz4", compression_level=9
        )
        actual = {
            "rows": int(len(selected)),
            "start": _iso(selected["date"].min()),
            "end": _iso(selected["date"].max()),
            "bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        }
        checks = {
            "row_count": actual["rows"] == expected["rows"],
            "bytes": actual["bytes"] == expected["bytes"],
            "sha256": actual["sha256"] == expected["sha256"],
            "timestamps_unique": not selected["date"].duplicated().any(),
            "utc": str(selected["date"].dtype) == "datetime64[ns, UTC]",
        }
        results.append(
            {
                "file_id": key,
                "source": f"local_sealed_staging/{expected['name']}",
                "target": target.relative_to(repo).as_posix(),
                "expected": expected,
                "actual": actual,
                "checks": checks,
                "passed": all(checks.values()),
            }
        )
    if not all(item["passed"] for item in results):
        raise RehydrationInvalid(
            "sealed_snapshot_hash_mismatch:"
            + json.dumps(results, sort_keys=True, default=str)
        )
    return {
        "schema_version": "frozen-development-snapshot-rehydration-v1",
        "dataset_id": DATASET_ID,
        "source_type": "explicit_local_sealed_staging_lineage",
        "network_accessed": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "files": results,
        "passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--staging-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = rehydrate(args.repo.resolve(), args.staging_root.resolve())
    if args.report:
        output = args.repo.resolve() / args.report
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
