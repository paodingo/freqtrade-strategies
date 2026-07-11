#!/usr/bin/env python3
"""Provision a fixed Binance USD-M futures dataset from public monthly archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


OFFICIAL_HOST = "data.binance.vision"
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_PAIR = "BTC/USDT:USDT"
DEFAULT_TIMEFRAME = "1h"
DEFAULT_FUNDING_TIMEFRAME = "8h"
DEFAULT_MONTH = "2024-01"


@dataclass(frozen=True)
class SourceArchive:
    candle_type: str
    timeframe: str
    url: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def pair_to_filename(pair: str) -> str:
    for ch in ["/", " ", ".", "@", "$", "+", ":"]:
        pair = pair.replace(ch, "_")
    return pair


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_public_archive_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != OFFICIAL_HOST:
        raise ValueError(f"only https://{OFFICIAL_HOST}/ public archives are allowed")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("archive URL must not contain credentials, query, or fragment")
    if not parsed.path.startswith("/data/futures/um/monthly/"):
        raise ValueError("only Binance USD-M futures monthly public archives are allowed")


def source_archives(
    symbol: str,
    month: str,
    timeframes: list[str] | None = None,
    mark_timeframes: list[str] | None = None,
) -> list[SourceArchive]:
    root = f"https://{OFFICIAL_HOST}/data/futures/um/monthly"
    archives: list[SourceArchive] = []
    for timeframe in timeframes or [DEFAULT_TIMEFRAME]:
        archives.append(
            SourceArchive(
                "futures",
                timeframe,
                f"{root}/klines/{symbol}/{timeframe}/{symbol}-{timeframe}-{month}.zip",
            )
        )
    for timeframe in mark_timeframes or [DEFAULT_FUNDING_TIMEFRAME]:
        archives.append(
            SourceArchive(
                "mark",
                timeframe,
                f"{root}/markPriceKlines/{symbol}/{timeframe}/{symbol}-{timeframe}-{month}.zip",
            )
        )
    archives.append(
        SourceArchive(
            "funding_rate",
            DEFAULT_FUNDING_TIMEFRAME,
            f"{root}/fundingRate/{symbol}/{symbol}-fundingRate-{month}.zip",
        )
    )
    return archives


def download_archive(archive: SourceArchive, target_dir: Path, timeout: int) -> tuple[Path, str, int]:
    validate_public_archive_url(archive.url)
    target = target_dir / f"{archive.candle_type}-{Path(urlparse(archive.url).path).name}"
    with urllib.request.urlopen(archive.url, timeout=timeout) as response:
        payload = response.read()
    target.write_bytes(payload)
    return target, sha256_bytes(payload), len(payload)


def read_single_csv_from_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"expected exactly one csv member in {path.name}, found {names}")
        with archive.open(names[0]) as handle:
            return pd.read_csv(handle)


def kline_to_freqtrade(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"open_time", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"kline archive missing columns: {missing}")
    result = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["open_time"], unit="ms", utc=True),
            "open": frame["open"].astype(float),
            "high": frame["high"].astype(float),
            "low": frame["low"].astype(float),
            "close": frame["close"].astype(float),
            "volume": frame["volume"].astype(float),
        }
    )
    return result


def funding_to_freqtrade(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"calc_time", "last_funding_rate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"funding archive missing columns: {missing}")
    rates = frame["last_funding_rate"].astype(float)
    result = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["calc_time"], unit="ms", utc=True),
            "open": rates,
            "high": 0.0,
            "low": 0.0,
            "close": 0.0,
            "volume": 0.0,
        }
    )
    return result


def write_feather(frame: pd.DataFrame, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.reset_index(drop=True).to_feather(target, compression_level=9, compression="lz4")


def provision_dataset(
    staging_dir: str | Path,
    symbol: str = DEFAULT_SYMBOL,
    pair: str = DEFAULT_PAIR,
    timeframe: str = DEFAULT_TIMEFRAME,
    month: str = DEFAULT_MONTH,
    months: list[str] | None = None,
    timeframes: list[str] | None = None,
    mark_timeframes: list[str] | None = None,
    timeout: int = 60,
) -> dict:
    staging = Path(staging_dir).resolve()
    if staging.exists():
        shutil.rmtree(staging)
    download_dir = staging / "_downloads"
    data_dir = staging / "futures"
    download_dir.mkdir(parents=True, exist_ok=True)

    stem = pair_to_filename(pair)
    files = []
    sources = []
    frames: dict[tuple[str, str], list[pd.DataFrame]] = {}
    selected_months = months or [month]
    selected_timeframes = timeframes or [timeframe]
    selected_mark_timeframes = mark_timeframes or [DEFAULT_FUNDING_TIMEFRAME]
    for selected_month in selected_months:
        for archive in source_archives(symbol, selected_month, selected_timeframes, selected_mark_timeframes):
            zip_path, digest, size = download_archive(archive, download_dir, timeout)
            raw = read_single_csv_from_zip(zip_path)
            if archive.candle_type == "funding_rate":
                frame = funding_to_freqtrade(raw)
            else:
                frame = kline_to_freqtrade(raw)
            frames.setdefault((archive.candle_type, archive.timeframe), []).append(frame)
            sources.append(
                {
                    "candle_type": archive.candle_type,
                    "timeframe": archive.timeframe,
                    "url": archive.url,
                    "zip_bytes": size,
                    "zip_sha256": digest,
                }
            )

    for (candle_type, archive_timeframe), pieces in sorted(frames.items()):
        frame = pd.concat(pieces, ignore_index=True)
        frame = frame.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        output = data_dir / f"{stem}-{archive_timeframe}-{candle_type}.feather"
        write_feather(frame, output)
        files.append(
            {
                "path": output.relative_to(staging).as_posix(),
                "rows": int(len(frame)),
                "start": str(frame["date"].min()),
                "end": str(frame["date"].max()),
                "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "candle_type": candle_type,
                "timeframe": archive_timeframe,
            }
        )
    manifest = {
        "provisioned_at": utc_now(),
        "source": "binance_public_data_vision_usdm_monthly",
        "exchange": "binance",
        "trading_mode": "futures",
        "margin_mode": "isolated",
        "symbol": symbol,
        "pair": pair,
        "timeframe": timeframe,
        "timeframes": selected_timeframes,
        "mark_timeframes": selected_mark_timeframes,
        "funding_timeframe": DEFAULT_FUNDING_TIMEFRAME,
        "month": month,
        "months": selected_months,
        "files": files,
        "sources": sources,
    }
    (staging / "provisioning-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision fixed Binance USD-M futures research data.")
    parser.add_argument("--staging", default="research/data/staging/demo-btc-usdt-usdt-futures-1h-202401")
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--pair", default=DEFAULT_PAIR)
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME)
    parser.add_argument("--month", default=DEFAULT_MONTH)
    parser.add_argument("--months", nargs="*")
    parser.add_argument("--timeframes", nargs="*")
    parser.add_argument("--mark-timeframes", nargs="*")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    manifest = provision_dataset(
        args.staging,
        args.symbol,
        args.pair,
        args.timeframe,
        args.month,
        months=args.months,
        timeframes=args.timeframes,
        mark_timeframes=args.mark_timeframes,
        timeout=args.timeout,
    )
    print(json.dumps({"ok": True, "manifest": manifest}, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
