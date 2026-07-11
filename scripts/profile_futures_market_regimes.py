#!/usr/bin/env python3
"""Strategy-independent futures market regime profiling."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


CLASSIFIER_VERSION = "futures-market-regime-profile-v1"
TEMPORAL_CLASSIFIER_VERSION = "temporal-market-regime-profile-v1"


def load_frame(path: str | Path) -> pd.DataFrame:
    frame = pd.read_feather(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    return frame.sort_values("date").reset_index(drop=True)


def slice_frame(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    return frame[(frame["date"] >= start_ts) & (frame["date"] <= end_ts)].copy()


def profile_window(ohlcv: pd.DataFrame, funding: pd.DataFrame | None = None) -> dict[str, Any]:
    if ohlcv.empty:
        return {"rows": 0, "labels": ["no_data"], "stats": {}}
    close = ohlcv["close"].astype(float)
    returns = close.pct_change().dropna()
    total_return = (float(close.iloc[-1]) / float(close.iloc[0]) - 1.0) if len(close) > 1 and float(close.iloc[0]) else 0.0
    realized_vol = float(returns.std() * (24 ** 0.5)) if not returns.empty else 0.0
    max_abs_return = float(returns.abs().max()) if not returns.empty else 0.0
    avg_volume = float(ohlcv["volume"].astype(float).mean()) if "volume" in ohlcv else 0.0
    labels: list[str] = []
    if total_return > 0.03:
        labels.append("upward_trend")
    elif total_return < -0.03:
        labels.append("downward_trend")
    else:
        labels.append("range")
    labels.append("high_volatility" if realized_vol > 0.05 else "low_volatility")
    funding_mean = None
    funding_min = None
    funding_max = None
    if funding is not None and not funding.empty:
        funding_close = funding["close"].astype(float)
        funding_mean = float(funding_close.mean())
        funding_min = float(funding_close.min())
        funding_max = float(funding_close.max())
        if funding_mean > 0:
            labels.append("positive_funding")
        elif funding_mean < 0:
            labels.append("negative_funding")
        if funding_close.abs().max() > 0.0005:
            labels.append("funding_stress")
    return {
        "rows": int(len(ohlcv)),
        "start": str(ohlcv["date"].min()),
        "end": str(ohlcv["date"].max()),
        "labels": labels,
        "stats": {
            "total_return": total_return,
            "realized_volatility": realized_vol,
            "max_abs_period_return": max_abs_return,
            "average_volume": avg_volume,
            "funding_mean": funding_mean,
            "funding_min": funding_min,
            "funding_max": funding_max,
        },
    }


def temporal_regime_timeline(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Classify candles from market data only using a frozen trailing-window rule."""
    frame = ohlcv.copy().sort_values("date").reset_index(drop=True)
    close = frame["close"].astype(float)
    returns = close.pct_change()
    frame["return_24h"] = close.pct_change(24)
    frame["realized_volatility_24h"] = returns.rolling(24, min_periods=12).std() * (24 ** 0.5)
    frame["trend"] = "range"
    frame.loc[frame["return_24h"] > 0.02, "trend"] = "upward"
    frame.loc[frame["return_24h"] < -0.02, "trend"] = "downward"
    valid_vol = frame["realized_volatility_24h"].dropna()
    threshold = float(valid_vol.median()) if not valid_vol.empty else 0.0
    frame["volatility"] = "low_volatility"
    frame.loc[frame["realized_volatility_24h"] > threshold, "volatility"] = "high_volatility"
    frame["regime"] = frame["trend"] + "_" + frame["volatility"]
    return frame


def profile_temporal_slice(
    slice_id: str,
    ohlcv: pd.DataFrame,
    funding: pd.DataFrame | None,
    evaluation_start: str,
    evaluation_end_exclusive: str,
) -> dict[str, Any]:
    start = pd.Timestamp(evaluation_start)
    end = pd.Timestamp(evaluation_end_exclusive)
    evaluation = ohlcv[(ohlcv["date"] >= start) & (ohlcv["date"] < end)].copy()
    funding_eval = None if funding is None else funding[(funding["date"] >= start) & (funding["date"] < end)].copy()
    timeline = temporal_regime_timeline(evaluation)
    close = evaluation["close"].astype(float)
    returns = close.pct_change().dropna()
    counts = Counter(timeline["regime"].tolist())
    trend_counts = Counter(timeline["trend"].tolist())
    vol_counts = Counter(timeline["volatility"].tolist())
    rows = len(evaluation)
    funding_values = pd.Series(dtype=float) if funding_eval is None else funding_eval["close"].astype(float)
    total_return = None if rows < 2 or float(close.iloc[0]) == 0 else float(close.iloc[-1] / close.iloc[0] - 1.0)
    realized_vol = None if returns.empty else float(returns.std() * (24 ** 0.5))
    trend_strength = None if realized_vol in (None, 0.0) or total_return is None else abs(total_return) / realized_vol
    dominant = max(counts, key=counts.get) if counts else "no_data"
    return {
        "schema_version": "stage3e1-market-profile-v1",
        "classifier_version": TEMPORAL_CLASSIFIER_VERSION,
        "slice_id": slice_id,
        "strategy_independent": True,
        "uses_strategy_results": False,
        "evaluation_start": evaluation_start,
        "evaluation_end_exclusive": evaluation_end_exclusive,
        "rows": rows,
        "underlying_price_return": total_return,
        "realized_volatility": realized_vol,
        "trend_strength": trend_strength,
        "trend_proportions": {key: value / rows for key, value in sorted(trend_counts.items())} if rows else {},
        "volatility_proportions": {key: value / rows for key, value in sorted(vol_counts.items())} if rows else {},
        "regime_proportions": {key: value / rows for key, value in sorted(counts.items())} if rows else {},
        "dominant_market_regime": dominant,
        "max_single_period_move": None if returns.empty else float(returns.abs().max()),
        "volume_distribution": {
            "min": None if rows == 0 else float(evaluation["volume"].min()),
            "p25": None if rows == 0 else float(evaluation["volume"].quantile(0.25)),
            "median": None if rows == 0 else float(evaluation["volume"].median()),
            "p75": None if rows == 0 else float(evaluation["volume"].quantile(0.75)),
            "max": None if rows == 0 else float(evaluation["volume"].max()),
        },
        "funding": {
            "rows": int(len(funding_values)),
            "positive_proportion": None if funding_values.empty else float((funding_values > 0).mean()),
            "negative_proportion": None if funding_values.empty else float((funding_values < 0).mean()),
            "zero_proportion": None if funding_values.empty else float((funding_values == 0).mean()),
            "mean": None if funding_values.empty else float(funding_values.mean()),
            "max_abs": None if funding_values.empty else float(funding_values.abs().max()),
            "stress": None if funding_values.empty else bool(funding_values.abs().max() > 0.0005),
        },
        "regime_timeline": [
            {"timestamp": row.date.isoformat(), "regime": row.regime, "trend": row.trend, "volatility": row.volatility}
            for row in timeline.itertuples()
        ],
    }


def write_temporal_markdown(path: Path, profile: dict[str, Any]) -> None:
    lines = [
        f"# Temporal Market Profile {profile['slice_id']}", "",
        f"- Classifier: `{profile['classifier_version']}`",
        "- Strategy results used: `false`",
        f"- Evaluation rows: `{profile['rows']}`",
        f"- Underlying return: `{profile['underlying_price_return']}`",
        f"- Realized volatility: `{profile['realized_volatility']}`",
        f"- Trend strength: `{profile['trend_strength']}`",
        f"- Dominant regime: `{profile['dominant_market_regime']}`", "",
        "## Trend Proportions", "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in profile["trend_proportions"].items())
    lines.extend(["", "## Volatility Proportions", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in profile["volatility_proportions"].items())
    lines.extend(["", "## Funding", "", f"- `{json.dumps(profile['funding'], sort_keys=True)}`", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def build_profile(
    split_id: str,
    ohlcv_path: str | Path,
    funding_path: str | Path,
    windows: dict[str, dict[str, str]],
) -> dict[str, Any]:
    ohlcv = load_frame(ohlcv_path)
    funding = load_frame(funding_path)
    results = {}
    all_labels = set()
    for name, bounds in windows.items():
        o_slice = slice_frame(ohlcv, bounds["start"], bounds["end"])
        f_slice = slice_frame(funding, bounds["start"], bounds["end"])
        results[name] = profile_window(o_slice, f_slice)
        all_labels.update(results[name]["labels"])
    expected = {
        "upward_trend",
        "downward_trend",
        "range",
        "high_volatility",
        "low_volatility",
        "positive_funding",
        "negative_funding",
        "funding_stress",
    }
    return {
        "schema_version": "stage3c1-market-profile-v1",
        "classifier_version": CLASSIFIER_VERSION,
        "split_id": split_id,
        "strategy_independent": True,
        "uses_strategy_results": False,
        "windows": results,
        "coverage_gaps": sorted(expected - all_labels),
    }


def write_markdown(path: Path, profile: dict[str, Any]) -> None:
    lines = [
        f"# Market Profile {profile['split_id']}",
        "",
        f"- Classifier: `{profile['classifier_version']}`",
        "- Strategy results used: `false`",
        "",
    ]
    for name, payload in profile["windows"].items():
        lines.extend(
            [
                f"## {name}",
                "",
                f"- Rows: `{payload['rows']}`",
                f"- Start: `{payload.get('start')}`",
                f"- End: `{payload.get('end')}`",
                f"- Labels: `{', '.join(payload['labels'])}`",
                f"- Total return: `{payload['stats'].get('total_return')}`",
                f"- Realized volatility: `{payload['stats'].get('realized_volatility')}`",
                "",
            ]
        )
    lines.extend(["## Coverage Gaps", ""])
    for item in profile["coverage_gaps"]:
        lines.append(f"- `{item}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile futures market regimes without strategy results.")
    parser.add_argument("--split-id", required=True)
    parser.add_argument("--ohlcv", required=True)
    parser.add_argument("--funding", required=True)
    parser.add_argument("--windows-json", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    windows = json.loads(Path(args.windows_json).read_text(encoding="utf-8"))
    profile = build_profile(args.split_id, args.ohlcv, args.funding, windows)
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(profile, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(Path(args.output_md), profile)
    print(json.dumps({"ok": True, "profile": args.output_json}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
