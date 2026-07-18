"""Alpha risk filtering helpers for offline V6.6 audits."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

LONG_HOSTILE_FLAGS = {
    "positiveFunding",
    "longCrowding",
    "topTraderLongCrowding",
    "topTraderAccountLongCrowding",
    "takerBuyPressure",
    "positivePremium",
}
SHORT_HOSTILE_FLAGS = {
    "negativeFunding",
    "shortCrowding",
    "topTraderShortCrowding",
    "takerSellPressure",
    "negativePremium",
}
BLOCK_LEVELS = {"warning", "danger"}


def load_alpha_risk_samples(db_path: str | Path) -> pd.DataFrame:
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=["sampled_at", "risk_level", "risk_score", "risk_flags"])

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            """
            SELECT sampled_at, risk_level, risk_score, payload
            FROM alpha_risk_samples
            ORDER BY sampled_at ASC
            """
        ).fetchall()

    records = []
    for sampled_at, risk_level, risk_score, payload in rows:
        flags = []
        try:
            parsed = json.loads(payload)
            flags = [flag.get("key") for flag in parsed.get("risk", {}).get("flags", []) if flag.get("key")]
            risk_level = risk_level or parsed.get("risk", {}).get("level")
            risk_score = risk_score if risk_score is not None else parsed.get("risk", {}).get("score")
        except (TypeError, json.JSONDecodeError):
            flags = []
        records.append({
            "sampled_at": sampled_at,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_flags": ",".join(flags),
        })

    return pd.DataFrame.from_records(records)


def apply_alpha_filter(
    dataframe: pd.DataFrame,
    samples: pd.DataFrame,
    *,
    mode: str = "directional",
    max_age_minutes: int = 60,
    block_levels: set[str] | None = None,
) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    result = dataframe.copy()
    result["alpha_risk_level"] = None
    result["alpha_risk_score"] = None
    result["alpha_risk_flags"] = ""
    result["alpha_filter_block_long"] = False
    result["alpha_filter_block_short"] = False

    if samples.empty or "date" not in result:
        return result

    block_levels = block_levels or BLOCK_LEVELS
    risk = samples.copy()
    risk["sampled_at"] = _normalized_utc_timestamp(risk["sampled_at"])
    risk = risk.dropna(subset=["sampled_at"]).sort_values("sampled_at")
    if risk.empty:
        return result

    ordered = result.reset_index(names="_original_index")
    ordered["_alpha_date"] = _normalized_utc_timestamp(ordered["date"])
    merged = pd.merge_asof(
        ordered.sort_values("_alpha_date"),
        risk,
        left_on="_alpha_date",
        right_on="sampled_at",
        direction="backward",
        tolerance=pd.Timedelta(minutes=max_age_minutes),
    ).sort_values("_original_index")

    result["alpha_risk_level"] = merged["risk_level"].to_numpy()
    result["alpha_risk_score"] = merged["risk_score"].to_numpy()
    result["alpha_risk_flags"] = merged["risk_flags"].fillna("").to_numpy()

    level = merged["risk_level"].fillna("")
    flags = merged["risk_flags"].fillna("")
    if mode == "level":
        block = level.isin(block_levels)
        result["alpha_filter_block_long"] = block.to_numpy()
        result["alpha_filter_block_short"] = block.to_numpy()
    elif mode == "directional":
        danger = level == "danger"
        result["alpha_filter_block_long"] = (danger | flags.map(lambda value: _has_any(value, LONG_HOSTILE_FLAGS))).to_numpy()
        result["alpha_filter_block_short"] = (danger | flags.map(lambda value: _has_any(value, SHORT_HOSTILE_FLAGS))).to_numpy()
    else:
        return result

    result.loc[(result.get("enter_long", 0) == 1) & result["alpha_filter_block_long"], "enter_long"] = 0
    result.loc[(result.get("enter_short", 0) == 1) & result["alpha_filter_block_short"], "enter_short"] = 0
    return result


def _has_any(raw_flags: str, target_flags: set[str]) -> bool:
    flags = {flag for flag in str(raw_flags or "").split(",") if flag}
    return bool(flags & target_flags)


def _normalized_utc_timestamp(values) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce").astype("datetime64[ns, UTC]")
