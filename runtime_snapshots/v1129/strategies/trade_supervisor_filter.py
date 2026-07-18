"""Trade Supervisor entry filtering helpers for V6.6 dry-run routing."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

BASE_SUPERVISOR_COLUMNS = [
    "sampled_at",
    "mode",
    "system_action",
    "window_type",
    "allowed_playbook",
    "risk_budget_pct",
]
DEFAULT_ACTION_COLUMNS = [
    "max_new_stake_pct",
    "v66_action",
    "v66_allow_fresh_entries",
    "v66_allowed_tags",
    "v66_blocked_tags",
    "v67_action",
    "v67_allow_fresh_entries",
    "v67_allowed_tags",
    "v67_blocked_tags",
]
SUPERVISOR_COLUMNS = [*BASE_SUPERVISOR_COLUMNS, *DEFAULT_ACTION_COLUMNS]


def load_trade_supervisor_decisions(db_path: str | Path) -> pd.DataFrame:
    path = Path(db_path)
    if not path.exists():
        return pd.DataFrame(columns=SUPERVISOR_COLUMNS)

    try:
        with sqlite3.connect(path) as connection:
            rows = connection.execute(
                """
                SELECT sampled_at, mode, system_action, window_type,
                       allowed_playbook, risk_budget_pct, payload
                FROM trade_supervisor_decisions
                ORDER BY sampled_at ASC, id ASC
                """
            ).fetchall()
    except sqlite3.Error:
        return pd.DataFrame(columns=SUPERVISOR_COLUMNS)

    records = []
    for sampled_at, mode, system_action, window_type, allowed_playbook, risk_budget_pct, payload in rows:
        try:
            parsed = json.loads(payload)
        except (TypeError, json.JSONDecodeError):
            parsed = {}

        actions = parsed.get("actions") or {}
        record = {
            "sampled_at": parsed.get("sampledAt") or sampled_at,
            "mode": parsed.get("mode") or mode,
            "system_action": parsed.get("systemAction") or system_action,
            "window_type": parsed.get("windowType") or window_type,
            "allowed_playbook": parsed.get("allowedPlaybook") or allowed_playbook,
            "risk_budget_pct": parsed.get("riskBudgetPct", risk_budget_pct),
            "max_new_stake_pct": parsed.get("maxNewStakePct"),
        }
        for bot_key, action in actions.items():
            if not isinstance(action, dict):
                continue
            prefix = _safe_bot_key(bot_key)
            if not prefix:
                continue
            record[f"{prefix}_action"] = action.get("recommendedAction")
            record[f"{prefix}_allow_fresh_entries"] = bool(action.get("allowFreshEntries", False))
            record[f"{prefix}_allowed_tags"] = _join_tags(action.get("allowedTags"))
            record[f"{prefix}_blocked_tags"] = _join_tags(action.get("blockedTags"))
        records.append(record)

    columns = list(dict.fromkeys([
        *SUPERVISOR_COLUMNS,
        *(column for record in records for column in record.keys()),
    ]))
    return pd.DataFrame.from_records(records, columns=columns)


def apply_trade_supervisor_filter(
    dataframe: pd.DataFrame,
    samples: pd.DataFrame,
    *,
    bot_key: str = "v66",
    mode: str = "latest",
    max_age_minutes: int = 20,
    fail_closed: bool = True,
    soft_allowed_tags=None,
) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe

    result = dataframe.copy()
    result["trade_supervisor_action"] = ""
    result["trade_supervisor_allowed_tags"] = ""
    result["trade_supervisor_block_entry"] = False

    if samples.empty:
        return _fail_closed(result, fail_closed, "missing_supervisor")

    decisions = _prepare_decisions(samples, bot_key)
    if decisions.empty:
        return _fail_closed(result, fail_closed, "missing_supervisor")

    soft_allowed_tags = _split_tags(soft_allowed_tags)
    if mode == "asof":
        return _apply_asof_decisions(result, decisions, max_age_minutes, fail_closed, soft_allowed_tags)

    return _apply_decision(result, decisions.iloc[-1], fail_closed, soft_allowed_tags)


def _apply_asof_decisions(
    dataframe: pd.DataFrame,
    decisions: pd.DataFrame,
    max_age_minutes: int,
    fail_closed: bool,
    soft_allowed_tags: set[str],
) -> pd.DataFrame:
    if "date" not in dataframe:
        return _fail_closed(dataframe, fail_closed, "missing_candle_date")

    ordered = dataframe.reset_index(names="_original_index")
    ordered["_supervisor_date"] = _normalized_utc_timestamp(ordered["date"])
    merged = pd.merge_asof(
        ordered.sort_values("_supervisor_date"),
        decisions,
        left_on="_supervisor_date",
        right_on="sampled_at_dt",
        direction="backward",
        tolerance=pd.Timedelta(minutes=max_age_minutes),
    ).sort_values("_original_index")

    result = dataframe.copy()
    result["trade_supervisor_action"] = merged["action"].fillna("missing_supervisor").to_numpy()
    result["trade_supervisor_allowed_tags"] = merged["allowed_tags"].fillna("").to_numpy()
    result["trade_supervisor_block_entry"] = False

    for index, row in merged.iterrows():
        original_index = row["_original_index"]
        if pd.isna(row.get("sampled_at_dt")):
            if fail_closed:
                _block_row(result, original_index)
            continue
        _apply_row_decision(result, original_index, row, fail_closed, soft_allowed_tags)

    return result


def _apply_decision(
    dataframe: pd.DataFrame,
    decision: pd.Series,
    fail_closed: bool,
    soft_allowed_tags: set[str],
) -> pd.DataFrame:
    result = dataframe.copy()
    result["trade_supervisor_action"] = decision.get("action") or ""
    result["trade_supervisor_allowed_tags"] = decision.get("allowed_tags") or ""
    result["trade_supervisor_block_entry"] = False
    for index in result.index:
        _apply_row_decision(result, index, decision, fail_closed, soft_allowed_tags)
    return result


def _apply_row_decision(
    dataframe: pd.DataFrame,
    index,
    decision: pd.Series,
    fail_closed: bool,
    soft_allowed_tags: set[str],
) -> None:
    if not _has_entry(dataframe, index):
        return

    allow_fresh = bool(decision.get("allow_fresh_entries", False))
    allowed_tags = _split_tags(decision.get("allowed_tags"))
    entry_tag = str(dataframe.at[index, "enter_tag"] if "enter_tag" in dataframe else "")
    if not allow_fresh:
        _block_row(dataframe, index)
    elif allowed_tags and not (
        _entry_tag_allowed(entry_tag, allowed_tags)
        or _entry_tag_allowed(entry_tag, soft_allowed_tags)
    ):
        _block_row(dataframe, index)
    elif not allowed_tags and fail_closed:
        _block_row(dataframe, index)


def _fail_closed(dataframe: pd.DataFrame, fail_closed: bool, action: str) -> pd.DataFrame:
    result = dataframe.copy()
    result["trade_supervisor_action"] = action
    result["trade_supervisor_allowed_tags"] = ""
    result["trade_supervisor_block_entry"] = False
    if fail_closed:
        for index in result.index:
            if _has_entry(result, index):
                _block_row(result, index)
    return result


def _block_row(dataframe: pd.DataFrame, index) -> None:
    if "enter_long" in dataframe:
        dataframe.at[index, "enter_long"] = 0
    if "enter_short" in dataframe:
        dataframe.at[index, "enter_short"] = 0
    dataframe.at[index, "trade_supervisor_block_entry"] = True


def _has_entry(dataframe: pd.DataFrame, index) -> bool:
    enter_long = dataframe.at[index, "enter_long"] if "enter_long" in dataframe else 0
    enter_short = dataframe.at[index, "enter_short"] if "enter_short" in dataframe else 0
    return bool(enter_long == 1 or enter_short == 1)


def _prepare_decisions(samples: pd.DataFrame, bot_key: str) -> pd.DataFrame:
    prepared = samples.copy()
    prepared["sampled_at_dt"] = _normalized_utc_timestamp(prepared["sampled_at"])
    prepared = prepared.dropna(subset=["sampled_at_dt"]).sort_values("sampled_at_dt")
    if prepared.empty:
        return prepared

    action_col = f"{bot_key}_action"
    allow_col = f"{bot_key}_allow_fresh_entries"
    allowed_col = f"{bot_key}_allowed_tags"
    prepared["action"] = prepared[action_col].fillna("") if action_col in prepared else ""
    prepared["allow_fresh_entries"] = prepared[allow_col].fillna(False) if allow_col in prepared else False
    prepared["allowed_tags"] = prepared[allowed_col].fillna("") if allowed_col in prepared else ""
    return prepared


def _safe_bot_key(raw_key) -> str:
    return "".join(char for char in str(raw_key or "") if char.isalnum() or char == "_")


def _entry_tag_allowed(entry_tag: str, allowed_tags: set[str]) -> bool:
    return any(allowed == entry_tag or allowed in entry_tag for allowed in allowed_tags)


def _split_tags(raw_tags) -> set[str]:
    if isinstance(raw_tags, (list, tuple, set)):
        return {str(tag) for tag in raw_tags if tag}
    return {tag for tag in str(raw_tags or "").split(",") if tag}


def _join_tags(raw_tags) -> str:
    return ",".join(sorted(_split_tags(raw_tags)))


def _normalized_utc_timestamp(values) -> pd.Series:
    return pd.to_datetime(values, utc=True, errors="coerce").astype("datetime64[ns, UTC]")
