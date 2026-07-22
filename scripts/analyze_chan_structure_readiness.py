#!/usr/bin/env python3
"""Audit causal swing-structure event coverage on development-only OHLCV data.

This is a descriptive readiness audit.  It does not create a strategy candidate,
run a backtest, calculate profit metrics, or access validation/holdout data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = Path("research/analysis/chan-structure-readiness-v1")
OUTPUT_JSON = OUTPUT_DIR / "event-coverage-report.json"
OUTPUT_MD = OUTPUT_DIR / "event-coverage-report.md"

EVALUATION_START = pd.Timestamp("2024-02-03T08:00:00Z")
EVALUATION_END_EXCLUSIVE = pd.Timestamp("2024-08-11T00:00:00Z")


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    dataset_id: str
    source_role: str


@dataclass(frozen=True)
class StructurePolicy:
    pivot_radius: int = 2
    breakout_horizon_bars: int = 24
    retest_horizon_bars: int = 12
    minimum_signals_per_side_per_pair: int = 10


POLICY = StructurePolicy()

BTC_CANONICAL = SourceFile(
    path=(
        "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/"
        "data/futures/BTC_USDT_USDT-1h-futures.feather"
    ),
    sha256="b5d2dd9cb7a34115ccdb2fd8b2044c1dc160f4d1e03af345387beb08452d0491",
    dataset_id="futures-dev-btc-usdt-usdt-20240101-20240830-v2",
    source_role="canonical_development_snapshot",
)

BTC_DEVELOPMENT_FALLBACK = tuple(
    SourceFile(
        path=(
            f"research/temporal/snapshots/temporal-stage3e1-s0{number}-btc-usdt-usdt-1h/"
            "data/futures/BTC_USDT_USDT-1h-futures.feather"
        ),
        sha256=sha256,
        dataset_id=f"temporal-stage3e1-s0{number}-btc-usdt-usdt-1h",
        source_role="development_v2_derived_temporal_snapshot",
    )
    for number, sha256 in (
        (1, "6447a43bdc57e7c3e9012cc3d421724eb4acb7f4314475b91283d3e5aab280f1"),
        (2, "33eaf92d8bb1aaefe9599a16378963eb539a0a1de5b4ddf34d04be77add14211"),
        (3, "efb2f12fabc8c1731f33cee8f3cb313121ce9efc19228ecffbaf36d4eec5bc60"),
    )
)

ETH_DEVELOPMENT = SourceFile(
    path=(
        "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/"
        "data/futures/ETH_USDT_USDT-1h-futures.feather"
    ),
    sha256="cc4d8387fe95727f1d46ae9c69380f250a3af39da5e232cb93baaaff6d3ed94f",
    dataset_id="futures-dev-eth-usdt-usdt-20240101-20240830-v1",
    source_role="canonical_development_snapshot",
)

REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_verified_files(root: Path, sources: Iterable[SourceFile]) -> tuple[pd.DataFrame, list[dict]]:
    frames: list[pd.DataFrame] = []
    evidence: list[dict] = []
    for source in sources:
        path = root / source.path
        if not path.is_file():
            raise FileNotFoundError(source.path)
        actual_sha256 = sha256_file(path)
        if actual_sha256 != source.sha256:
            raise ValueError(f"source hash mismatch: {source.path}")
        frame = pd.read_feather(path)
        missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
        if missing:
            raise ValueError(f"missing OHLCV columns in {source.path}: {missing}")
        frames.append(frame.loc[:, REQUIRED_COLUMNS].copy())
        evidence.append(
            {
                "dataset_id": source.dataset_id,
                "path": source.path,
                "source_role": source.source_role,
                "expected_sha256": source.sha256,
                "actual_sha256": actual_sha256,
                "hash_verified": True,
                "rows_read": int(len(frame)),
            }
        )
    return pd.concat(frames, ignore_index=True), evidence


def _normalize_ohlcv(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], utc=True)
    normalized = normalized.sort_values("date", kind="stable")
    duplicate_rows_removed = int(normalized.duplicated("date", keep="first").sum())
    normalized = normalized.drop_duplicates("date", keep="first").reset_index(drop=True)
    normalized = normalized[
        (normalized["date"] >= EVALUATION_START)
        & (normalized["date"] < EVALUATION_END_EXCLUSIVE)
    ].reset_index(drop=True)
    if normalized.empty:
        raise ValueError("evaluation window contains no candles")
    invalid_ohlc = (
        (normalized["high"] < normalized[["open", "close", "low"]].max(axis=1))
        | (normalized["low"] > normalized[["open", "close", "high"]].min(axis=1))
    )
    if bool(invalid_ohlc.any()):
        raise ValueError("invalid OHLC ordering")
    deltas = normalized["date"].diff().dropna().dt.total_seconds()
    non_hourly_gaps = int((deltas != 3600.0).sum())
    return normalized, {
        "duplicate_rows_removed": duplicate_rows_removed,
        "non_hourly_gaps": non_hourly_gaps,
        "rows_in_common_evaluation_window": int(len(normalized)),
        "start": normalized.iloc[0]["date"].isoformat(),
        "end": normalized.iloc[-1]["date"].isoformat(),
    }


def load_development_data(root: Path = ROOT) -> dict[str, dict]:
    canonical_path = root / BTC_CANONICAL.path
    if canonical_path.is_file():
        btc_sources = (BTC_CANONICAL,)
        btc_mode = "canonical_development_snapshot"
    else:
        btc_sources = BTC_DEVELOPMENT_FALLBACK
        btc_mode = "development_only_fallback_s01_s03"

    btc_raw, btc_evidence = _read_verified_files(root, btc_sources)
    eth_raw, eth_evidence = _read_verified_files(root, (ETH_DEVELOPMENT,))
    btc, btc_quality = _normalize_ohlcv(btc_raw)
    eth, eth_quality = _normalize_ohlcv(eth_raw)
    return {
        "BTC/USDT:USDT": {
            "dataframe": btc,
            "source_mode": btc_mode,
            "source_dataset_lineage": BTC_CANONICAL.dataset_id,
            "source_files": btc_evidence,
            "data_quality": btc_quality,
        },
        "ETH/USDT:USDT": {
            "dataframe": eth,
            "source_mode": "canonical_development_snapshot",
            "source_dataset_lineage": ETH_DEVELOPMENT.dataset_id,
            "source_files": eth_evidence,
            "data_quality": eth_quality,
        },
    }


def confirmed_pivots(frame: pd.DataFrame, radius: int = POLICY.pivot_radius) -> list[dict]:
    """Return unique local extrema, emitted only after ``radius`` right bars close."""
    if radius < 1:
        raise ValueError("pivot radius must be positive")
    highs = frame["high"].astype(float).to_numpy()
    lows = frame["low"].astype(float).to_numpy()
    dates = frame["date"].tolist()
    pivots: list[dict] = []
    for pivot_index in range(radius, len(frame) - radius):
        start = pivot_index - radius
        stop = pivot_index + radius + 1
        low_window = lows[start:stop]
        high_window = highs[start:stop]
        confirmation_index = pivot_index + radius
        if lows[pivot_index] == low_window.min() and int((low_window == lows[pivot_index]).sum()) == 1:
            pivots.append(
                {
                    "kind": "bottom",
                    "pivot_index": pivot_index,
                    "confirmation_index": confirmation_index,
                    "pivot_time": dates[pivot_index],
                    "confirmation_time": dates[confirmation_index],
                    "price": float(lows[pivot_index]),
                }
            )
        if highs[pivot_index] == high_window.max() and int((high_window == highs[pivot_index]).sum()) == 1:
            pivots.append(
                {
                    "kind": "top",
                    "pivot_index": pivot_index,
                    "confirmation_index": confirmation_index,
                    "pivot_time": dates[pivot_index],
                    "confirmation_time": dates[confirmation_index],
                    "price": float(highs[pivot_index]),
                }
            )
    return sorted(pivots, key=lambda item: (item["confirmation_index"], item["kind"]))


def _first_close_break(
    frame: pd.DataFrame,
    start_index: int,
    horizon: int,
    level: float,
    side: str,
) -> int | None:
    stop = min(len(frame), start_index + horizon + 1)
    closes = frame["close"].astype(float).to_numpy()
    for index in range(start_index, stop):
        if (side == "long" and closes[index] > level) or (side == "short" and closes[index] < level):
            return index
    return None


def structure_sequences(frame: pd.DataFrame, policy: StructurePolicy = POLICY) -> dict:
    pivots = confirmed_pivots(frame, policy.pivot_radius)
    bottoms = [item for item in pivots if item["kind"] == "bottom"]
    tops = [item for item in pivots if item["kind"] == "top"]
    sequences: dict[str, list[dict]] = {"long": [], "short": []}

    for bottom in bottoms:
        reference = next(
            (item for item in reversed(tops) if item["pivot_index"] < bottom["pivot_index"]),
            None,
        )
        if reference is None:
            continue
        breakout_index = _first_close_break(
            frame,
            bottom["confirmation_index"] + 1,
            policy.breakout_horizon_bars,
            reference["price"],
            "long",
        )
        if breakout_index is None:
            continue
        retest = next(
            (
                item
                for item in bottoms
                if item["pivot_index"] > breakout_index
                and item["confirmation_index"] <= breakout_index + policy.retest_horizon_bars
                and item["price"] > bottom["price"]
            ),
            None,
        )
        sequences["long"].append(
            _sequence_record(frame, bottom, reference, breakout_index, retest, "long")
        )

    for top in tops:
        reference = next(
            (item for item in reversed(bottoms) if item["pivot_index"] < top["pivot_index"]),
            None,
        )
        if reference is None:
            continue
        breakout_index = _first_close_break(
            frame,
            top["confirmation_index"] + 1,
            policy.breakout_horizon_bars,
            reference["price"],
            "short",
        )
        if breakout_index is None:
            continue
        retest = next(
            (
                item
                for item in tops
                if item["pivot_index"] > breakout_index
                and item["confirmation_index"] <= breakout_index + policy.retest_horizon_bars
                and item["price"] < top["price"]
            ),
            None,
        )
        sequences["short"].append(
            _sequence_record(frame, top, reference, breakout_index, retest, "short")
        )

    for side in ("long", "short"):
        unique: dict[int, dict] = {}
        for sequence in sequences[side]:
            signal_index = sequence.get("signal_confirmation_index")
            if signal_index is None:
                continue
            unique[signal_index] = sequence
        sequences[f"{side}_unique_signals"] = [unique[index] for index in sorted(unique)]
    sequences["pivots"] = pivots
    return sequences


def _sequence_record(
    frame: pd.DataFrame,
    initial: dict,
    reference: dict,
    breakout_index: int,
    retest: dict | None,
    side: str,
) -> dict:
    record = {
        "side": side,
        "initial_pivot_index": initial["pivot_index"],
        "initial_pivot_time": initial["pivot_time"].isoformat(),
        "initial_confirmation_index": initial["confirmation_index"],
        "initial_confirmation_time": initial["confirmation_time"].isoformat(),
        "initial_price": initial["price"],
        "reference_pivot_index": reference["pivot_index"],
        "reference_pivot_time": reference["pivot_time"].isoformat(),
        "breakout_level": reference["price"],
        "breakout_index": breakout_index,
        "breakout_time": frame.iloc[breakout_index]["date"].isoformat(),
        "breakout_close": float(frame.iloc[breakout_index]["close"]),
        "signal_confirmation_index": None,
        "signal_confirmation_time": None,
        "retest_price": None,
    }
    if retest is not None:
        record.update(
            {
                "signal_confirmation_index": retest["confirmation_index"],
                "signal_confirmation_time": retest["confirmation_time"].isoformat(),
                "retest_price": retest["price"],
            }
        )
    return record


def _signal_signatures(sequences: dict, before_index: int | None = None) -> set[tuple]:
    signatures: set[tuple] = set()
    for side in ("long", "short"):
        for item in sequences[f"{side}_unique_signals"]:
            signal_index = item["signal_confirmation_index"]
            if before_index is None or signal_index < before_index:
                signatures.add(
                    (
                        side,
                        signal_index,
                        item["initial_pivot_time"],
                        item["breakout_time"],
                        item["signal_confirmation_time"],
                    )
                )
    return signatures


def prefix_causality_audit(frame: pd.DataFrame, policy: StructurePolicy = POLICY) -> dict:
    full = structure_sequences(frame, policy)
    cutoffs = sorted({len(frame) // 4, len(frame) // 2, 3 * len(frame) // 4, len(frame) - 1})
    checks = []
    for cutoff in cutoffs:
        prefix = structure_sequences(frame.iloc[:cutoff].reset_index(drop=True), policy)
        prefix_signatures = _signal_signatures(prefix)
        full_before_cutoff = _signal_signatures(full, before_index=cutoff)
        checks.append(
            {
                "prefix_rows": cutoff,
                "prefix_signal_count": len(prefix_signatures),
                "full_signal_count_before_prefix_end": len(full_before_cutoff),
                "match": prefix_signatures == full_before_cutoff,
            }
        )
    return {
        "method": "prefix_recomputation_at_25_50_75_percent_and_final_minus_one_row",
        "checks": checks,
        "all_checks_passed": all(item["match"] for item in checks),
        "signal_timestamp_semantics": "confirmation_candle_close_only",
        "pivot_backdating_used": False,
    }


def _median(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def summarize_pair(frame: pd.DataFrame, policy: StructurePolicy = POLICY) -> tuple[dict, dict]:
    sequences = structure_sequences(frame, policy)
    pivots = sequences["pivots"]
    long_breakouts = sequences["long"]
    short_breakdowns = sequences["short"]
    long_signals = sequences["long_unique_signals"]
    short_signals = sequences["short_unique_signals"]
    causality = prefix_causality_audit(frame, policy)
    count = len(frame)
    metrics = {
        "candles": count,
        "confirmed_bottom_fractals": sum(item["kind"] == "bottom" for item in pivots),
        "confirmed_top_fractals": sum(item["kind"] == "top" for item in pivots),
        "long_breakouts_after_bottom": len(long_breakouts),
        "short_breakdowns_after_top": len(short_breakdowns),
        "long_higher_low_retest_signals": len(long_signals),
        "short_lower_high_retest_signals": len(short_signals),
        "long_signals_per_1000_candles": round(len(long_signals) * 1000 / count, 4),
        "short_signals_per_1000_candles": round(len(short_signals) * 1000 / count, 4),
        "median_long_bars_initial_confirmation_to_signal": _median(
            [item["signal_confirmation_index"] - item["initial_confirmation_index"] for item in long_signals]
        ),
        "median_short_bars_initial_confirmation_to_signal": _median(
            [item["signal_confirmation_index"] - item["initial_confirmation_index"] for item in short_signals]
        ),
    }
    samples = {
        "long": long_signals[:3],
        "short": short_signals[:3],
    }
    return {"metrics": metrics, "causality_audit": causality, "samples": samples}, sequences


def build_report(root: Path = ROOT, policy: StructurePolicy = POLICY) -> dict:
    loaded = load_development_data(root)
    pair_reports: dict[str, dict] = {}
    pair_gate_results: dict[str, dict] = {}
    for pair, details in loaded.items():
        summary, _ = summarize_pair(details["dataframe"], policy)
        metrics = summary["metrics"]
        long_pass = metrics["long_higher_low_retest_signals"] >= policy.minimum_signals_per_side_per_pair
        short_pass = metrics["short_lower_high_retest_signals"] >= policy.minimum_signals_per_side_per_pair
        causal_pass = summary["causality_audit"]["all_checks_passed"]
        quality_pass = details["data_quality"]["non_hourly_gaps"] == 0
        pair_gate_results[pair] = {
            "long_coverage_pass": long_pass,
            "short_coverage_pass": short_pass,
            "causality_pass": causal_pass,
            "data_quality_pass": quality_pass,
            "pass": long_pass and short_pass and causal_pass and quality_pass,
        }
        pair_reports[pair] = {
            "source_mode": details["source_mode"],
            "source_dataset_lineage": details["source_dataset_lineage"],
            "source_files": details["source_files"],
            "data_quality": details["data_quality"],
            **summary,
        }

    all_passed = all(item["pass"] for item in pair_gate_results.values())
    verdict = "ready_for_candidate_design_review" if all_passed else "insufficient_structure_event_coverage"
    return {
        "schema_version": "chan-structure-readiness-v1",
        "objective": "development-only causal structure event coverage audit",
        "policy": asdict(policy),
        "frozen_event_definitions": {
            "confirmed_fractal": (
                "unique high/low within a five-candle window; emitted two bars after the pivot candle"
            ),
            "long_breakout": (
                "first close above the latest confirmed swing high preceding a confirmed bottom, within 24 bars"
            ),
            "long_retest_signal": (
                "next confirmed bottom after breakout is above the initial bottom and confirms within 12 bars"
            ),
            "short_breakdown": (
                "first close below the latest confirmed swing low preceding a confirmed top, within 24 bars"
            ),
            "short_retest_signal": (
                "next confirmed top after breakdown is below the initial top and confirms within 12 bars"
            ),
        },
        "evaluation_window": {
            "timeframe": "1h",
            "start": EVALUATION_START.isoformat(),
            "end_exclusive": EVALUATION_END_EXCLUSIVE.isoformat(),
            "reason": "common BTC/ETH development-only coverage available in this worktree",
            "v1130_15m_claim_allowed": False,
        },
        "pairs": pair_reports,
        "readiness_gate": {
            "minimum_signals_per_side_per_pair": policy.minimum_signals_per_side_per_pair,
            "pair_results": pair_gate_results,
            "all_pairs_passed": all_passed,
        },
        "verdict": verdict,
        "next_step": (
            "human review of one structure-branch candidate design; separate authorization required"
            if all_passed
            else "do not create a strategy candidate; obtain broader development-only coverage or revise the hypothesis"
        ),
        "safety": {
            "descriptive_coverage_only": True,
            "strategy_modified": False,
            "candidate_created": False,
            "backtest_run": False,
            "profit_metrics_used": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "live_or_dry_run_bot_touched": False,
        },
    }


def format_markdown(report: dict) -> str:
    rows = []
    for pair, details in report["pairs"].items():
        metrics = details["metrics"]
        gate = report["readiness_gate"]["pair_results"][pair]
        rows.append(
            "| {pair} | {candles} | {bottoms} | {tops} | {long_breaks} | {long_signals} | "
            "{short_breaks} | {short_signals} | {causal} | {gate} |".format(
                pair=pair,
                candles=metrics["candles"],
                bottoms=metrics["confirmed_bottom_fractals"],
                tops=metrics["confirmed_top_fractals"],
                long_breaks=metrics["long_breakouts_after_bottom"],
                long_signals=metrics["long_higher_low_retest_signals"],
                short_breaks=metrics["short_breakdowns_after_top"],
                short_signals=metrics["short_lower_high_retest_signals"],
                causal="pass" if details["causality_audit"]["all_checks_passed"] else "fail",
                gate="pass" if gate["pass"] else "fail",
            )
        )
    source_lines = []
    for pair, details in report["pairs"].items():
        source_lines.append(f"- `{pair}` mode: `{details['source_mode']}`")
        source_lines.extend(
            f"  - `{item['path']}` (`sha256={item['actual_sha256']}`, verified)"
            for item in details["source_files"]
        )
    verdict = report["verdict"]
    return f"""# Causal Structure Event Coverage Audit

## Result

Verdict: `{verdict}`

This is a development-only, descriptive coverage audit. It is not a backtest and does not establish a 15m V11.30 edge.

| Pair | Candles | Bottoms | Tops | Long breaks | Long retests | Short breaks | Short retests | Causality | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
{chr(10).join(rows)}

The frozen readiness gate requires at least `{report['policy']['minimum_signals_per_side_per_pair']}` unique confirmed retest signals per side and pair, zero hourly gaps, and prefix-invariance causality checks.

## Frozen semantics

- Pivot radius: `{report['policy']['pivot_radius']}` bars. A pivot at `t` is emitted only at the close of `t+2`.
- Break window: `{report['policy']['breakout_horizon_bars']}` bars after initial pivot confirmation.
- Retest window: `{report['policy']['retest_horizon_bars']}` bars after the break.
- Long: confirmed bottom -> close above the preceding swing high -> confirmed higher low.
- Short: confirmed top -> close below the preceding swing low -> confirmed lower high.
- Signal timestamps are confirmation-candle close timestamps. No signal is backdated to the pivot candle.

## Data boundary

- Common evaluation window: `{report['evaluation_window']['start']}` to `{report['evaluation_window']['end_exclusive']}`.
- Timeframe: `1h`; no sealed development-only `15m` dataset is available in the repository.
- Validation and Holdout accesses: `0 / 0`.

{chr(10).join(source_lines)}

## Decision boundary

Next step: {report['next_step']}.

No strategy was modified, no Candidate was created, no Backtest was run, and no live/dry-run bot was touched.
"""


def write_report(report: dict, root: Path = ROOT) -> None:
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    (root / OUTPUT_JSON).write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    (root / OUTPUT_MD).write_text(format_markdown(report), encoding="utf-8")


def main() -> int:
    report = build_report(ROOT)
    write_report(report, ROOT)
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "all_pairs_passed": report["readiness_gate"]["all_pairs_passed"],
                "pair_metrics": {
                    pair: details["metrics"] for pair, details in report["pairs"].items()
                },
                "outputs": [str(OUTPUT_JSON), str(OUTPUT_MD)],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
