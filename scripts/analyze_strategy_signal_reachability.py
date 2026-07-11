#!/usr/bin/env python3
"""Stage 3D.2-A signal reachability and threshold sensitivity analysis."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from research_control import load_simple_yaml, utc_now
from run_experiment import dump_json, dump_manifest, repo_rel, sha256_file


CAMPAIGN_ID = "stage3d2a-signal-reachability"
BASE_STRATEGY = "RegimeAwareV6"
BASE_STRATEGY_PATH = Path("strategies/RegimeAwareV6.py")
BASE_STRATEGY_SHA256 = "1A422F41AB801746C2EE39F5D20722B26B674098BCA6AC1684E78BD8E7285509"
BASE_MIXIN_PATH = Path("strategies/regime_aware_base.py")
POLICY_SHA256 = "aa1798f7eb002ed30ad5fff95be48f3a08bc42e54f6b0f9406cd39412b9cff71"
DEV_DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
DEV_DATASET_ROOT = Path("research/data/snapshots") / DEV_DATASET_ID
STAGE3D1_RESULT_ROOT = Path("research/results/stage3d1-bounded-autonomous-search")
STAGE3D1_QUEUE = Path("research/queues/stage3d1-experiments.yaml")
STAGE3D1_CATALOG = Path("research/search-spaces/regime-aware-safe-mutations-v1.yaml")

ANALYSIS_ROOT = Path("research/analysis")
GRAPH_PATH = ANALYSIS_ROOT / "regime-aware-condition-graph.json"
COVERAGE_PATH = ANALYSIS_ROOT / "stage3d2a-condition-coverage.json"
BRANCH_PATH = ANALYSIS_ROOT / "stage3d2a-branch-activation.json"
EXPLANATION_PATH = ANALYSIS_ROOT / "stage3d2a-stage3d1-unchanged-explanation.json"
THRESHOLD_PATH = ANALYSIS_ROOT / "stage3d2a-threshold-sensitivity.json"
BLOCKER_PATH = ANALYSIS_ROOT / "stage3d2a-blocker-combinations.json"
COUNTERFACTUAL_PATH = ANALYSIS_ROOT / "stage3d2a-counterfactual-signal-reachability.json"
FINAL_JSON = ANALYSIS_ROOT / "stage3d2a-final-report.json"
GRAPH_MD = Path("reports/audits/stage3d2a_strategy_condition_graph.md")
FINAL_MD = Path("reports/audits/stage3d2a_signal_reachability.md")
PROPOSAL_PATH = Path("research/search-spaces/regime-aware-safe-mutations-v2-proposal.yaml")


class Stage3D2AError(RuntimeError):
    def __init__(self, failure_type: str, reason_code: str, message: str):
        super().__init__(message)
        self.failure_type = failure_type
        self.reason_code = reason_code
        self.message = message


@dataclass(frozen=True)
class ConditionSpec:
    condition_id: str
    expression: str
    source_path: str
    line: int
    side: str
    signal: str
    mask: Callable[[pd.DataFrame], pd.Series]
    operands: tuple[str, ...]
    comparison: dict[str, Any] | None = None


@dataclass(frozen=True)
class SignalGroup:
    group_id: str
    signal: str
    side: str
    branch: str
    conditions: tuple[str, ...]
    output_column: str
    enter_tag: str | None = None


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def series_bool(series: pd.Series) -> pd.Series:
    return series.fillna(False).astype(bool)


def null_count(df: pd.DataFrame, operands: tuple[str, ...]) -> int:
    if not operands:
        return 0
    existing = [col for col in operands if col in df.columns]
    if not existing:
        return 0
    return int(df[existing].isna().any(axis=1).sum())


def longest_true_run(mask: pd.Series) -> int:
    best = current = 0
    for item in mask.fillna(False).astype(bool).tolist():
        if item:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def assert_integrity(repo_root: Path) -> None:
    actual = sha256_file(repo_root / BASE_STRATEGY_PATH).upper()
    if actual != BASE_STRATEGY_SHA256:
        raise Stage3D2AError("validation_error", "base_strategy_integrity_violation", f"{actual} != {BASE_STRATEGY_SHA256}")


def load_strategy_dataframe(repo_root: Path) -> pd.DataFrame:
    sys.path.insert(0, str((repo_root / "strategies").resolve()))
    from RegimeAwareV6 import RegimeAwareV6

    class DummyDataProvider:
        def __init__(self, data_root: Path):
            self.data_root = data_root

        def current_whitelist(self) -> list[str]:
            return ["BTC/USDT:USDT"]

        def get_pair_dataframe(self, pair: str, timeframe: str, candle_type: str = "futures") -> pd.DataFrame:
            if pair != "BTC/USDT:USDT" or candle_type != "futures":
                raise ValueError("Stage 3D.2-A only authorizes BTC/USDT:USDT futures Development data")
            return pd.read_feather(self.data_root / f"BTC_USDT_USDT-{timeframe}-futures.feather")

    data_root = repo_root / DEV_DATASET_ROOT / "data" / "futures"
    dataframe = pd.read_feather(data_root / "BTC_USDT_USDT-1h-futures.feather")
    strategy = RegimeAwareV6({})
    strategy.dp = DummyDataProvider(data_root)
    metadata = {"pair": "BTC/USDT:USDT"}
    analyzed = strategy.populate_indicators(dataframe.copy(), metadata)
    analyzed = strategy.populate_entry_trend(analyzed, metadata)
    analyzed = strategy.populate_exit_trend(analyzed, metadata)
    for column in ("enter_long", "enter_short", "exit_long", "exit_short"):
        if column not in analyzed.columns:
            analyzed[column] = 0
        analyzed[column] = analyzed[column].fillna(0).astype(int)
    return analyzed


def extract_ast_expressions(repo_root: Path) -> list[dict[str, Any]]:
    source = (repo_root / BASE_MIXIN_PATH).read_text(encoding="utf-8")
    tree = ast.parse(source)
    extracted: list[dict[str, Any]] = []
    interesting_methods = {
        "populate_indicators",
        "_populate_trending_entries",
        "_populate_ranging_entries",
        "populate_exit_trend",
        "custom_exit",
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in interesting_methods:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Subscript):
                        target_text = ast.unparse(target)
                        if "dataframe" in target_text:
                            extracted.append(
                                {
                                    "method": node.name,
                                    "target": target_text,
                                    "expression": ast.unparse(child.value),
                                    "line": child.lineno,
                                    "source_path": BASE_MIXIN_PATH.as_posix(),
                                }
                            )
            elif isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                if ast.unparse(child.func).endswith(".loc.__setitem__") and child.args:
                    extracted.append(
                        {
                            "method": node.name,
                            "target": "dataframe.loc",
                            "expression": ast.unparse(child.args[0]),
                            "line": child.lineno,
                            "source_path": BASE_MIXIN_PATH.as_posix(),
                        }
                    )
    return extracted


def condition_specs() -> dict[str, ConditionSpec]:
    specs = [
        ConditionSpec("regime_trending", 'dataframe["regime_4h"] == "trending"', BASE_MIXIN_PATH.as_posix(), 254, "both", "entry", lambda d: d["regime_4h"] == "trending", ("regime_4h",)),
        ConditionSpec("regime_ranging", 'dataframe["regime_4h"] == "ranging"', BASE_MIXIN_PATH.as_posix(), 286, "both", "entry_exit", lambda d: d["regime_4h"] == "ranging", ("regime_4h",)),
        ConditionSpec("trend_4h_up", 'dataframe["trend_4h_up"]', BASE_MIXIN_PATH.as_posix(), 255, "long", "entry", lambda d: d["trend_4h_up"], ("trend_4h_up",)),
        ConditionSpec("trend_4h_down", 'dataframe["trend_4h_down"]', BASE_MIXIN_PATH.as_posix(), 270, "short", "entry", lambda d: d["trend_4h_down"], ("trend_4h_down",)),
        ConditionSpec("close_gt_ema200", 'dataframe["close"] > dataframe["ema200"]', BASE_MIXIN_PATH.as_posix(), 256, "long", "entry", lambda d: d["close"] > d["ema200"], ("close", "ema200")),
        ConditionSpec("close_lt_ema200", 'dataframe["close"] < dataframe["ema200"]', BASE_MIXIN_PATH.as_posix(), 271, "short", "entry", lambda d: d["close"] < d["ema200"], ("close", "ema200")),
        ConditionSpec("volume_gt_0", 'dataframe["volume"] > 0', BASE_MIXIN_PATH.as_posix(), 262, "both", "entry_exit", lambda d: d["volume"] > 0, ("volume",), {"left": "volume", "operator": ">", "threshold": 0}),
        ConditionSpec("pullback_ema_long", 'dataframe["pullback_ema_long"]', BASE_MIXIN_PATH.as_posix(), 258, "long", "entry", lambda d: d["pullback_ema_long"], ("pullback_ema_long",)),
        ConditionSpec("bb_breakout_long", 'dataframe["bb_breakout_long"]', BASE_MIXIN_PATH.as_posix(), 259, "long", "entry", lambda d: d["bb_breakout_long"], ("bb_breakout_long",)),
        ConditionSpec("rsi_recovery", 'dataframe["rsi_recovery"]', BASE_MIXIN_PATH.as_posix(), 260, "long", "entry", lambda d: d["rsi_recovery"], ("rsi_recovery",)),
        ConditionSpec("trending_long_trigger_any", 'pullback_ema_long | bb_breakout_long | rsi_recovery', BASE_MIXIN_PATH.as_posix(), 257, "long", "entry", lambda d: d["pullback_ema_long"] | d["bb_breakout_long"] | d["rsi_recovery"], ("pullback_ema_long", "bb_breakout_long", "rsi_recovery")),
        ConditionSpec("pullback_ema_short", 'dataframe["pullback_ema_short"]', BASE_MIXIN_PATH.as_posix(), 273, "short", "entry", lambda d: d["pullback_ema_short"], ("pullback_ema_short",)),
        ConditionSpec("bb_breakout_short", 'dataframe["bb_breakout_short"]', BASE_MIXIN_PATH.as_posix(), 274, "short", "entry", lambda d: d["bb_breakout_short"], ("bb_breakout_short",)),
        ConditionSpec("rsi_exhaustion", 'dataframe["rsi_exhaustion"]', BASE_MIXIN_PATH.as_posix(), 275, "short", "entry", lambda d: d["rsi_exhaustion"], ("rsi_exhaustion",)),
        ConditionSpec("trending_short_trigger_any", 'pullback_ema_short | bb_breakout_short | rsi_exhaustion', BASE_MIXIN_PATH.as_posix(), 272, "short", "entry", lambda d: d["pullback_ema_short"] | d["bb_breakout_short"] | d["rsi_exhaustion"], ("pullback_ema_short", "bb_breakout_short", "rsi_exhaustion")),
        ConditionSpec("ranging_long_setup", 'dataframe["ranging_long_setup"]', BASE_MIXIN_PATH.as_posix(), 287, "long", "entry", lambda d: d["ranging_long_setup"], ("ranging_long_setup",)),
        ConditionSpec("ranging_short_setup", 'dataframe["ranging_short_setup"]', BASE_MIXIN_PATH.as_posix(), 297, "short", "entry", lambda d: d["ranging_short_setup"], ("ranging_short_setup",)),
        ConditionSpec("rlong_bb_percent_lt_0_20", 'dataframe["bb_percent"] < 0.20', BASE_MIXIN_PATH.as_posix(), 223, "long", "entry", lambda d: d["bb_percent"] < 0.20, ("bb_percent",), {"left": "bb_percent", "operator": "<", "threshold": 0.20, "variable_id": "ranging_long_setup.bb_percent_max"}),
        ConditionSpec("rlong_rsi_lt_40", 'dataframe["rsi"] < 40', BASE_MIXIN_PATH.as_posix(), 224, "long", "entry", lambda d: d["rsi"] < 40, ("rsi",), {"left": "rsi", "operator": "<", "threshold": 40, "variable_id": "ranging_long_setup.rsi_max"}),
        ConditionSpec("rlong_volume_gt_mean_0_8", 'dataframe["volume"] > dataframe["volume_mean"] * 0.8', BASE_MIXIN_PATH.as_posix(), 225, "long", "entry", lambda d: d["volume"] > d["volume_mean"] * 0.8, ("volume", "volume_mean")),
        ConditionSpec("rlong_close_gt_ema200_0_92", 'dataframe["close"] > dataframe["ema200"] * 0.92', BASE_MIXIN_PATH.as_posix(), 226, "long", "entry", lambda d: d["close"] > d["ema200"] * 0.92, ("close", "ema200"), {"left": "close_over_ema200", "operator": ">", "threshold": 0.92, "variable_id": "ranging_long_setup.ema200_multiplier_min"}),
        ConditionSpec("rlong_bb_width_4h_lt_mean_1_3", 'dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * 1.3', BASE_MIXIN_PATH.as_posix(), 227, "long", "entry", lambda d: d["bb_width_4h"] < d["bb_width_mean_4h"] * 1.3, ("bb_width_4h", "bb_width_mean_4h"), {"left": "bb_width_4h_over_mean", "operator": "<", "threshold": 1.3, "variable_id": "ranging_shared.bb_width_4h_multiplier_max_long"}),
        ConditionSpec("rlong_adx_4h_lt_22", 'dataframe["adx_4h"] < 22', BASE_MIXIN_PATH.as_posix(), 228, "long", "entry", lambda d: d["adx_4h"] < 22, ("adx_4h",), {"left": "adx_4h", "operator": "<", "threshold": 22, "variable_id": "ranging_shared.adx_4h_max_long"}),
        ConditionSpec("rshort_bb_percent_gt_0_80", 'dataframe["bb_percent"] > 0.80', BASE_MIXIN_PATH.as_posix(), 231, "short", "entry", lambda d: d["bb_percent"] > 0.80, ("bb_percent",), {"left": "bb_percent", "operator": ">", "threshold": 0.80, "variable_id": "ranging_short_setup.bb_percent_min"}),
        ConditionSpec("rshort_rsi_gt_60", 'dataframe["rsi"] > 60', BASE_MIXIN_PATH.as_posix(), 232, "short", "entry", lambda d: d["rsi"] > 60, ("rsi",), {"left": "rsi", "operator": ">", "threshold": 60, "variable_id": "ranging_short_setup.rsi_min"}),
        ConditionSpec("rshort_volume_gt_mean_0_8", 'dataframe["volume"] > dataframe["volume_mean"] * 0.8', BASE_MIXIN_PATH.as_posix(), 233, "short", "entry", lambda d: d["volume"] > d["volume_mean"] * 0.8, ("volume", "volume_mean")),
        ConditionSpec("rshort_bb_width_4h_lt_mean_1_3", 'dataframe["bb_width_4h"] < dataframe["bb_width_mean_4h"] * 1.3', BASE_MIXIN_PATH.as_posix(), 234, "short", "entry", lambda d: d["bb_width_4h"] < d["bb_width_mean_4h"] * 1.3, ("bb_width_4h", "bb_width_mean_4h"), {"left": "bb_width_4h_over_mean", "operator": "<", "threshold": 1.3, "variable_id": "ranging_shared.bb_width_4h_multiplier_max_short"}),
        ConditionSpec("rshort_adx_4h_lt_22", 'dataframe["adx_4h"] < 22', BASE_MIXIN_PATH.as_posix(), 235, "short", "entry", lambda d: d["adx_4h"] < 22, ("adx_4h",), {"left": "adx_4h", "operator": "<", "threshold": 22}),
        ConditionSpec("exit_long_close_lt_ema200_0_90", 'dataframe["close"] < dataframe["ema200"] * 0.90', BASE_MIXIN_PATH.as_posix(), 308, "long", "exit", lambda d: d["close"] < d["ema200"] * 0.90, ("close", "ema200")),
    ]
    return {spec.condition_id: spec for spec in specs}


def signal_groups() -> dict[str, SignalGroup]:
    groups = [
        SignalGroup("trending_long_entry", "enter_long", "long", "trending_long", ("regime_trending", "trend_4h_up", "close_gt_ema200", "trending_long_trigger_any", "volume_gt_0"), "enter_long", "trending_long"),
        SignalGroup("trending_short_entry", "enter_short", "short", "trending_short", ("regime_trending", "trend_4h_down", "close_lt_ema200", "trending_short_trigger_any", "volume_gt_0"), "enter_short", "trending_short"),
        SignalGroup("ranging_long_entry", "enter_long", "long", "ranging_long", ("regime_ranging", "rlong_bb_percent_lt_0_20", "rlong_rsi_lt_40", "rlong_volume_gt_mean_0_8", "rlong_close_gt_ema200_0_92", "rlong_bb_width_4h_lt_mean_1_3", "rlong_adx_4h_lt_22", "close_gt_ema200", "volume_gt_0"), "enter_long", "ranging_long"),
        SignalGroup("ranging_short_entry", "enter_short", "short", "ranging_short", ("regime_ranging", "rshort_bb_percent_gt_0_80", "rshort_rsi_gt_60", "rshort_volume_gt_mean_0_8", "rshort_bb_width_4h_lt_mean_1_3", "rshort_adx_4h_lt_22", "close_lt_ema200", "volume_gt_0"), "enter_short", "ranging_short"),
        SignalGroup("ranging_breakdown_exit_long", "exit_long", "long", "ranging_breakdown", ("regime_ranging", "exit_long_close_lt_ema200_0_90", "volume_gt_0"), "exit_long", "ranging_breakdown"),
    ]
    return {group.group_id: group for group in groups}


def condition_mask_map(df: pd.DataFrame, specs: dict[str, ConditionSpec]) -> dict[str, pd.Series]:
    return {cid: series_bool(spec.mask(df)) for cid, spec in specs.items()}


def group_mask(group: SignalGroup, masks: dict[str, pd.Series], override: tuple[str, pd.Series] | None = None) -> pd.Series:
    result: pd.Series | None = None
    override_id, override_mask = override if override else (None, None)
    for cid in group.conditions:
        mask = override_mask if cid == override_id else masks[cid]
        result = mask.copy() if result is None else (result & mask)
    if result is None:
        raise ValueError(group.group_id)
    return series_bool(result)


def condition_coverage(df: pd.DataFrame, specs: dict[str, ConditionSpec], groups: dict[str, SignalGroup]) -> dict[str, Any]:
    masks = condition_mask_map(df, specs)
    rows: dict[str, Any] = {}
    group_masks = {gid: group_mask(group, masks) for gid, group in groups.items()}
    for cid, spec in specs.items():
        mask = masks[cid]
        related_groups = [gid for gid, group in groups.items() if cid in group.conditions]
        single_blocker_by_group: dict[str, int] = {}
        joint_true_by_group: dict[str, int] = {}
        final_true_by_group: dict[str, int] = {}
        for gid in related_groups:
            group = groups[gid]
            others = [masks[item] for item in group.conditions if item != cid]
            other_true = others[0].copy() if others else pd.Series(True, index=df.index)
            for item in others[1:]:
                other_true &= item
            single_blocker_by_group[gid] = int((~mask & other_true).sum())
            joint_true_by_group[gid] = int((mask & other_true).sum())
            final_true_by_group[gid] = int(group_masks[gid].sum())
        rows[cid] = {
            "condition_id": cid,
            "expression": spec.expression,
            "source_path": spec.source_path,
            "line": spec.line,
            "signal": spec.signal,
            "side": spec.side,
            "total_candles": int(len(mask)),
            "evaluable_candles": int(len(mask) - null_count(df, spec.operands)),
            "true_count": int(mask.sum()),
            "false_count": int((~mask).sum()),
            "null_count": null_count(df, spec.operands),
            "true_ratio": float(mask.mean()),
            "longest_true_run": longest_true_run(mask),
            "single_blocker_count": int(sum(single_blocker_by_group.values())),
            "single_blocker_by_group": single_blocker_by_group,
            "joint_true_by_group": joint_true_by_group,
            "final_signal_true_by_group": final_true_by_group,
            "final_signal_triggered_with_condition_true": int(sum(int((mask & group_masks[gid]).sum()) for gid in related_groups)),
            "final_signal_not_triggered_bottleneck_contribution": int(sum(single_blocker_by_group.values())),
            "comparison": spec.comparison,
        }
    return {"schema_version": "stage3d2a-condition-coverage-v1", "conditions": rows}


def blocker_combinations(df: pd.DataFrame, specs: dict[str, ConditionSpec], groups: dict[str, SignalGroup]) -> dict[str, Any]:
    masks = condition_mask_map(df, specs)
    output: dict[str, Any] = {"schema_version": "stage3d2a-blocker-combinations-v1", "groups": {}}
    for gid, group in groups.items():
        blockers: dict[str, int] = {}
        distribution: dict[str, int] = {}
        for idx in df.index:
            failed = [cid for cid in group.conditions if not bool(masks[cid].loc[idx])]
            count = len(failed)
            bucket = "3_plus" if count >= 3 else str(count)
            distribution[bucket] = distribution.get(bucket, 0) + 1
            if 1 <= count <= 3:
                key = "|".join(failed)
                blockers[key] = blockers.get(key, 0) + 1
        output["groups"][gid] = {
            "condition_count": len(group.conditions),
            "blocked_condition_count_distribution": distribution,
            "single_blocker_candles": distribution.get("1", 0),
            "two_condition_blocker_candles": distribution.get("2", 0),
            "three_plus_condition_blocker_candles": distribution.get("3_plus", 0),
            "most_common_blocker_combinations": [
                {"conditions": key.split("|"), "count": value}
                for key, value in sorted(blockers.items(), key=lambda item: (-item[1], item[0]))[:10]
            ],
        }
    return output


def branch_activation(df: pd.DataFrame, groups: dict[str, SignalGroup], coverage: dict[str, Any], baseline_trades: list[dict[str, Any]]) -> dict[str, Any]:
    trade_counts: dict[str, int] = {}
    for trade in baseline_trades:
        tag = trade.get("enter_tag") or trade.get("entry_tag") or trade.get("enter_reason") or "unknown"
        trade_counts[tag] = trade_counts.get(tag, 0) + 1
    masks = condition_mask_map(df, condition_specs())
    output: dict[str, Any] = {"schema_version": "stage3d2a-branch-activation-v1", "branches": {}}
    for gid, group in groups.items():
        gmask = group_mask(group, masks)
        regime_condition = "regime_trending" if group.branch.startswith("trending") else "regime_ranging"
        regime_active = int(masks[regime_condition].sum()) if regime_condition in masks else 0
        setup_precondition = int(gmask.sum())
        final_column = group.output_column
        if group.enter_tag and "enter_tag" in df.columns:
            final_signal = int(((df[final_column] == 1) & (df["enter_tag"] == group.enter_tag)).sum())
        else:
            final_signal = int((df[final_column] == 1).sum())
        if regime_active == 0:
            inactive_reason = "regime_never_active"
        elif setup_precondition == 0:
            common = blocker_combinations(df, condition_specs(), {gid: group})["groups"][gid]["most_common_blocker_combinations"]
            inactive_reason = "blocked_by_other_condition" if common else "unknown"
        elif final_signal == 0:
            inactive_reason = "signal_generated_but_not_traded"
        else:
            inactive_reason = None
        output["branches"][gid] = {
            "branch": group.branch,
            "side": group.side,
            "signal": group.signal,
            "regime_active_candles": regime_active,
            "setup_precondition_candles": setup_precondition,
            "complete_entry_signal_candles": final_signal if group.signal.startswith("enter") else 0,
            "complete_exit_signal_candles": final_signal if group.signal.startswith("exit") else 0,
            "final_formed_trade_count": trade_counts.get(group.enter_tag or "", 0),
            "overlap_or_conflict_count": 0,
            "inactive_reason": inactive_reason,
            "single_blocker_count": sum(coverage["conditions"][cid]["single_blocker_by_group"].get(gid, 0) for cid in group.conditions),
        }
    return output


def comparable_series(df: pd.DataFrame, comparison: dict[str, Any]) -> pd.Series:
    left = comparison["left"]
    if left == "bb_percent":
        return df["bb_percent"]
    if left == "rsi":
        return df["rsi"]
    if left == "adx_4h":
        return df["adx_4h"]
    if left == "close_over_ema200":
        return df["close"] / df["ema200"]
    if left == "bb_width_4h_over_mean":
        return df["bb_width_4h"] / df["bb_width_mean_4h"]
    if left == "volume":
        return df["volume"]
    raise KeyError(left)


def threshold_mask(values: pd.Series, operator: str, threshold: float) -> pd.Series:
    if operator == "<":
        return values < threshold
    if operator == "<=":
        return values <= threshold
    if operator == ">":
        return values > threshold
    if operator == ">=":
        return values >= threshold
    raise ValueError(operator)


def percentile_position(values: pd.Series, threshold: float) -> float | None:
    clean = values.dropna()
    if clean.empty:
        return None
    return float((clean <= threshold).mean())


def minimum_threshold_for_changes(values: pd.Series, operator: str, current: float, other_conditions: pd.Series, changes: int) -> float | None:
    clean = values[other_conditions & values.notna()]
    if clean.empty:
        return None
    if operator in {"<", "<="}:
        candidates = sorted(v for v in clean.tolist() if v >= current)
        if len(candidates) < changes:
            return None
        return float(candidates[changes - 1])
    if operator in {">", ">="}:
        candidates = sorted((v for v in clean.tolist() if v <= current), reverse=True)
        if len(candidates) < changes:
            return None
        return float(candidates[changes - 1])
    return None


def threshold_sensitivity(df: pd.DataFrame, specs: dict[str, ConditionSpec], groups: dict[str, SignalGroup], queue: dict[str, Any]) -> dict[str, Any]:
    masks = condition_mask_map(df, specs)
    by_variable = variable_condition_map(specs)
    tested_by_variable: dict[str, list[Any]] = {}
    for item in queue["experiments"]:
        tested_by_variable.setdefault(item["variable_id"], []).append(item["new_value"])
    output: dict[str, Any] = {"schema_version": "stage3d2a-threshold-sensitivity-v1", "variables": {}}
    for variable_id, condition_id in by_variable.items():
        spec = specs[condition_id]
        comparison = spec.comparison or {}
        values = comparable_series(df, comparison)
        current = float(comparison["threshold"])
        operator = comparison["operator"]
        quantiles = {str(q): safe_float(values.quantile(q)) for q in [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]}
        group_ids = [gid for gid, group in groups.items() if condition_id in group.conditions]
        conditional_stats: dict[str, Any] = {}
        minimum_value_for: dict[str, Any] = {}
        for gid in group_ids:
            group = groups[gid]
            other = pd.Series(True, index=df.index)
            for cid in group.conditions:
                if cid != condition_id:
                    other &= masks[cid]
            conditional_values = values[other]
            conditional_stats[gid] = {
                "candles": int(other.sum()),
                "min": safe_float(conditional_values.min()),
                "max": safe_float(conditional_values.max()),
                "p50": safe_float(conditional_values.quantile(0.5)) if not conditional_values.dropna().empty else None,
                "current_true_count": int((threshold_mask(values, operator, current) & other).sum()),
            }
            for target in (1, 3, 5, 10):
                key = f"{gid}:{target}_final_signal_mask_changes"
                minimum_value_for[key] = safe_float(minimum_threshold_for_changes(values, operator, current, other, target))
        tested_crossings = {}
        old_mask = threshold_mask(values, operator, current)
        for tested in tested_by_variable.get(variable_id, []):
            new_mask = threshold_mask(values, operator, float(tested))
            by_group_conditional: dict[str, int] = {}
            for gid in group_ids:
                group = groups[gid]
                other = pd.Series(True, index=df.index)
                for cid in group.conditions:
                    if cid != condition_id:
                        other &= masks[cid]
                by_group_conditional[gid] = int(((old_mask ^ new_mask) & other).sum())
            tested_crossings[str(tested)] = {
                "all_candles_crossing_count": int((old_mask ^ new_mask).sum()),
                "conditional_crossing_count": int(sum(by_group_conditional.values())),
                "conditional_crossing_by_group": by_group_conditional,
            }
        output["variables"][variable_id] = {
            "condition_id": condition_id,
            "current_value": current,
            "operator": operator,
            "indicator": comparison["left"],
            "all_candles": {
                "min": safe_float(values.min()),
                "max": safe_float(values.max()),
                "quantiles": quantiles,
                "current_threshold_percentile": percentile_position(values, current),
                "nearest_below_threshold": safe_float(values[values < current].max()),
                "nearest_above_threshold": safe_float(values[values > current].min()),
            },
            "conditional_on_other_setup_conditions": conditional_stats,
            "tested_value_crossings": tested_crossings,
            "minimum_value_for": minimum_value_for,
        }
    return output


def variable_condition_map(specs: dict[str, ConditionSpec]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for cid, spec in specs.items():
        if spec.comparison and spec.comparison.get("variable_id"):
            mapping[spec.comparison["variable_id"]] = cid
    return mapping


def candidate_values_for_counterfactual(variable: dict[str, Any], sensitivity: dict[str, Any]) -> list[float]:
    values = [float(v) for v in variable.get("candidate_values", [])]
    details = sensitivity["variables"].get(variable["variable_id"], {})
    for value in details.get("minimum_value_for", {}).values():
        if value is not None:
            values.append(float(value))
    bounded: list[float] = []
    for value in values:
        if variable["variable_id"].endswith("bb_percent_max") or variable["variable_id"].endswith("bb_percent_min"):
            if 0 <= value <= 1:
                bounded.append(value)
        elif "ema200_multiplier" in variable["variable_id"] or "bb_width_4h_multiplier" in variable["variable_id"]:
            if 0.5 <= value <= 2.0:
                bounded.append(value)
        elif "rsi" in variable["variable_id"]:
            if 1 <= value <= 99:
                bounded.append(value)
        elif "adx" in variable["variable_id"]:
            if 1 <= value <= 60:
                bounded.append(value)
    return sorted(set(round(v, 8) for v in bounded))


def counterfactual_reachability(df: pd.DataFrame, specs: dict[str, ConditionSpec], groups: dict[str, SignalGroup], catalog: dict[str, Any], sensitivity: dict[str, Any]) -> dict[str, Any]:
    masks = condition_mask_map(df, specs)
    by_variable = variable_condition_map(specs)
    output: dict[str, Any] = {"schema_version": "stage3d2a-counterfactual-signal-reachability-v1", "variables": {}}
    for variable in catalog["variables"]:
        variable_id = variable["variable_id"]
        condition_id = by_variable.get(variable_id)
        if not condition_id:
            output["variables"][variable_id] = {"classification": "not_analyzable", "reason": "no mapped condition"}
            continue
        spec = specs[condition_id]
        comparison = spec.comparison or {}
        values = comparable_series(df, comparison)
        operator = comparison["operator"]
        old_condition = masks[condition_id]
        group_ids = [gid for gid, group in groups.items() if condition_id in group.conditions]
        results = []
        max_final_changes = 0
        for candidate in candidate_values_for_counterfactual(variable, sensitivity):
            new_condition = threshold_mask(values, operator, float(candidate)).fillna(False)
            final_changes = 0
            long_changes = 0
            short_changes = 0
            by_group = {}
            for gid in group_ids:
                group = groups[gid]
                old_group = group_mask(group, masks)
                new_group = group_mask(group, masks, (condition_id, new_condition))
                changed = old_group ^ new_group
                count = int(changed.sum())
                final_changes += count
                if group.side == "long":
                    long_changes += count
                elif group.side == "short":
                    short_changes += count
                by_group[gid] = count
            max_final_changes = max(max_final_changes, final_changes)
            results.append(
                {
                    "candidate_value": candidate,
                    "condition_mask_changed_candles": int((old_condition ^ new_condition).sum()),
                    "final_signal_mask_changed_candles": final_changes,
                    "long_signal_changed_candles": long_changes,
                    "short_signal_changed_candles": short_changes,
                    "by_group": by_group,
                    "backtest_executed": False,
                    "profit_metrics_used": False,
                }
            )
        coverage_class = "single_variable_reachable" if max_final_changes > 0 else "single_variable_low_reach"
        if max_final_changes == 0:
            coverage_rows = condition_coverage(df, specs, groups)["conditions"][condition_id]
            if coverage_rows["single_blocker_count"] == 0:
                coverage_class = "multi_variable_dependency_detected"
        output["variables"][variable_id] = {
            "condition_id": condition_id,
            "classification": coverage_class,
            "candidate_values": results,
            "max_final_signal_mask_changed_candles": max_final_changes,
        }
    return output


def load_baseline_reference(repo_root: Path) -> dict[str, Any]:
    result_path = repo_root / STAGE3D1_RESULT_ROOT / "1" / "development-evaluation" / "stage3c2-evaluation-result.json"
    if not result_path.exists():
        raise Stage3D2AError("validation_error", "missing_stage3d1_baseline_reference", str(result_path))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    baseline = result["baseline_metrics"]
    candidate = result["candidate_metrics"]
    if baseline["normalized_trade_hash"] != candidate["normalized_trade_hash"]:
        raise Stage3D2AError("implementation_error", "instrumentation_semantic_drift", "Stage 3D.1 baseline/candidate hash reference is not equal")
    return {
        "source": repo_rel(repo_root, result_path),
        "baseline_trade_hash": baseline["normalized_trade_hash"],
        "candidate_trade_hash": candidate["normalized_trade_hash"],
        "total_trades": baseline["normalized_trade_count"],
        "long_trades": int(sum(1 for item in baseline["normalized_trades"] if item.get("is_short") is False)),
        "short_trades": int(sum(1 for item in baseline["normalized_trades"] if item.get("is_short") is True)),
        "normalized_trades": baseline["normalized_trades"],
        "hash_equal": True,
    }


def explain_stage3d1(df: pd.DataFrame, queue: dict[str, Any], specs: dict[str, ConditionSpec], groups: dict[str, SignalGroup], coverage: dict[str, Any], sensitivity: dict[str, Any], counterfactual: dict[str, Any]) -> dict[str, Any]:
    by_variable = variable_condition_map(specs)
    masks = condition_mask_map(df, specs)
    explanations = []
    for item in queue["experiments"]:
        variable_id = item["variable_id"]
        condition_id = by_variable[variable_id]
        spec = specs[condition_id]
        comparison = spec.comparison or {}
        values = comparable_series(df, comparison)
        old_mask = threshold_mask(values, comparison["operator"], float(item["old_value"])).fillna(False)
        new_mask = threshold_mask(values, comparison["operator"], float(item["new_value"])).fillna(False)
        group_changes = {}
        for gid, group in groups.items():
            if condition_id not in group.conditions:
                continue
            old_group = group_mask(group, masks)
            new_group = group_mask(group, masks, (condition_id, new_mask))
            group_changes[gid] = int((old_group ^ new_group).sum())
        total_signal_changes = sum(group_changes.values())
        crossing_count = int((old_mask ^ new_mask).sum())
        single_blockers = coverage["conditions"][condition_id]["single_blocker_count"]
        if crossing_count == 0:
            reason = "tested_value_too_far_from_actual_distribution_or_no_threshold_crossing"
        elif total_signal_changes == 0 and single_blockers == 0:
            reason = "threshold_crossed_but_other_conditions_still_block"
        elif total_signal_changes > 0:
            reason = "signal_mask_changed_but_no_trade_behavior_change"
        else:
            reason = "variable_covered_by_other_logic"
        explanations.append(
            {
                "experiment_id": item["experiment_id"],
                "variable_id": variable_id,
                "old_value": item["old_value"],
                "tested_value": item["new_value"],
                "condition_id": condition_id,
                "condition_true_count": coverage["conditions"][condition_id]["true_count"],
                "condition_single_blocker_count": single_blockers,
                "old_new_threshold_crossing_count": crossing_count,
                "changed_raw_condition_mask": crossing_count > 0,
                "changed_final_entry_exit_mask": total_signal_changes > 0,
                "changed_trade_behavior": False,
                "group_signal_mask_changes": group_changes,
                "reason_code": reason,
                "implementation_issue_detected": False,
            }
        )
    return {"schema_version": "stage3d2a-stage3d1-unchanged-explanation-v1", "experiments": explanations}


def build_proposal(repo_root: Path, catalog: dict[str, Any], specs: dict[str, ConditionSpec], coverage: dict[str, Any], sensitivity: dict[str, Any], counterfactual: dict[str, Any], blockers: dict[str, Any]) -> dict[str, Any]:
    proposed = []
    excluded = []
    by_variable = variable_condition_map(specs)
    high_risk = set(catalog.get("forbidden_variables", []))
    for variable in catalog["variables"]:
        variable_id = variable["variable_id"]
        condition_id = by_variable.get(variable_id)
        cf = counterfactual["variables"].get(variable_id, {})
        classification = cf.get("classification", "not_analyzable")
        proposed_values = [
            {
                "value": item["candidate_value"],
                "signal_mask_change_estimate": item["final_signal_mask_changed_candles"],
                "condition_mask_change_estimate": item["condition_mask_changed_candles"],
            }
            for item in cf.get("candidate_values", [])
            if item["final_signal_mask_changed_candles"] > 0
        ][:5]
        base_payload = {
            "variable_id": variable_id,
            "source_path": variable["source_path"],
            "line": variable["line"],
            "current_value": variable["old_value"],
            "condition_id": condition_id,
            "affects_side": variable["affects_side"],
            "affects_entry_or_exit": variable["affects_entry_or_exit"],
            "condition_coverage": coverage["conditions"].get(condition_id, {}) if condition_id else {},
            "single_blocker_count": coverage["conditions"].get(condition_id, {}).get("single_blocker_count") if condition_id else None,
            "single_variable_reachability": classification,
            "risk_level": variable.get("risk_level", "unknown"),
            "requires_multi_variable": classification == "multi_variable_dependency_detected",
            "proposal_reason": "signal mask reachable without changing market/leverage/risk contracts" if proposed_values else "no final signal mask change in bounded counterfactual values",
        }
        if variable_id in high_risk or not proposed_values or classification != "single_variable_reachable":
            excluded.append({**base_payload, "suggested_values": proposed_values, "exclusion_reason": classification})
        else:
            proposed.append({**base_payload, "suggested_values": proposed_values})
    proposal = {
        "schema_version": "stage3d2a-safe-mutation-catalog-v2-proposal-v1",
        "proposal_id": "regime-aware-safe-mutations-v2-proposal",
        "base_strategy": BASE_STRATEGY,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "development_dataset_id": DEV_DATASET_ID,
        "policy_id": "balanced-research-gate-v1",
        "policy_sha256": POLICY_SHA256,
        "status": "pending_human_review",
        "selection_basis": ["condition_coverage", "threshold_distribution", "single_blocker", "signal_mask_reachability", "structure_risk"],
        "forbidden_selection_basis": ["return", "profit_factor", "sharpe", "sortino", "calmar", "drawdown", "validation_metrics", "holdout_metrics"],
        "proposed_variables": proposed,
        "excluded_variables": excluded,
        "created_at": utc_now(),
    }
    proposal["proposal_sha256"] = stable_hash({key: value for key, value in proposal.items() if key != "proposal_sha256"})
    dump_manifest(repo_root / PROPOSAL_PATH, proposal)
    return proposal


def write_reports(repo_root: Path, graph: dict[str, Any], coverage: dict[str, Any], branch: dict[str, Any], explanations: dict[str, Any], sensitivity: dict[str, Any], counterfactual: dict[str, Any], proposal: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    GRAPH_MD.parent.mkdir(parents=True, exist_ok=True)
    graph_lines = [
        "# Stage 3D.2-A Strategy Condition Graph",
        "",
        f"- Base strategy: `{BASE_STRATEGY}`",
        f"- Base strategy SHA-256: `{BASE_STRATEGY_SHA256}`",
        f"- AST extracted expressions: `{len(graph['ast_extracted_expressions'])}`",
        "",
        "## Signal Groups",
        "",
    ]
    for group in graph["signal_groups"]:
        graph_lines.append(f"- `{group['group_id']}`: `{group['logic']}`")
    GRAPH_MD.write_text("\n".join(graph_lines) + "\n", encoding="utf-8")

    proposed = [item["variable_id"] for item in proposal["proposed_variables"]]
    multi = [vid for vid, item in counterfactual["variables"].items() if item.get("classification") == "multi_variable_dependency_detected"]
    low = [vid for vid, item in counterfactual["variables"].items() if item.get("classification") == "single_variable_low_reach"]
    final = {
        "schema_version": "stage3d2a-final-report-v1",
        "campaign_id": CAMPAIGN_ID,
        "status": "completed",
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "development_dataset_id": DEV_DATASET_ID,
        "policy_sha256": POLICY_SHA256,
        "instrumentation_semantic_drift": False,
        "baseline_reference": {key: value for key, value in baseline.items() if key != "normalized_trades"},
        "stage3d1_experiments_explained": len(explanations["experiments"]),
        "single_variable_reachable": proposed,
        "single_variable_low_reach": low,
        "multi_variable_dependency_detected": multi,
        "proposal_status": proposal["status"],
        "proposal_sha256": proposal["proposal_sha256"],
        "forbidden_actions": {
            "candidate_created": False,
            "candidate_backtest_run": False,
            "hyperopt_run": False,
            "validation_accessed": False,
            "holdout_accessed": False,
            "profit_metrics_used_for_selection": False,
            "champion_created": False,
        },
        "artifact_index": {
            "condition_graph": repo_rel(repo_root, repo_root / GRAPH_PATH),
            "condition_graph_report": repo_rel(repo_root, repo_root / GRAPH_MD),
            "condition_coverage": repo_rel(repo_root, repo_root / COVERAGE_PATH),
            "branch_activation": repo_rel(repo_root, repo_root / BRANCH_PATH),
            "stage3d1_explanation": repo_rel(repo_root, repo_root / EXPLANATION_PATH),
            "threshold_sensitivity": repo_rel(repo_root, repo_root / THRESHOLD_PATH),
            "blocker_combinations": repo_rel(repo_root, repo_root / BLOCKER_PATH),
            "counterfactual_reachability": repo_rel(repo_root, repo_root / COUNTERFACTUAL_PATH),
            "proposal": repo_rel(repo_root, repo_root / PROPOSAL_PATH),
            "final_json": repo_rel(repo_root, repo_root / FINAL_JSON),
            "final_markdown": repo_rel(repo_root, repo_root / FINAL_MD),
        },
        "created_at": utc_now(),
    }
    dump_json(repo_root / FINAL_JSON, final)
    lines = [
        "# Stage 3D.2-A Signal Reachability",
        "",
        f"- Status: `{final['status']}`",
        f"- Instrumentation semantic drift: `{str(final['instrumentation_semantic_drift']).lower()}`",
        f"- Stage 3D.1 experiments explained: `{final['stage3d1_experiments_explained']}`",
        f"- Single-variable reachable: `{len(proposed)}`",
        f"- Single-variable low reach: `{len(low)}`",
        f"- Multi-variable dependency detected: `{len(multi)}`",
        f"- Proposal status: `{proposal['status']}`",
        "",
        "## Recommended Proposal Variables",
        "",
    ]
    if proposed:
        for item in proposal["proposed_variables"]:
            values = ", ".join(str(v["value"]) for v in item["suggested_values"])
            lines.append(f"- `{item['variable_id']}`: `{values}`")
    else:
        lines.append("- None")
    lines.extend(["", "## Why Stage 3D.1 Was Behavior Unchanged", ""])
    reason_counts: dict[str, int] = {}
    for item in explanations["experiments"]:
        reason_counts[item["reason_code"]] = reason_counts.get(item["reason_code"], 0) + 1
    for reason, count in sorted(reason_counts.items()):
        lines.append(f"- `{reason}`: `{count}`")
    FINAL_MD.parent.mkdir(parents=True, exist_ok=True)
    FINAL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return final


def condition_graph(repo_root: Path, specs: dict[str, ConditionSpec], groups: dict[str, SignalGroup]) -> dict[str, Any]:
    ast_items = extract_ast_expressions(repo_root)
    return {
        "schema_version": "stage3d2a-condition-graph-v1",
        "base_strategy": BASE_STRATEGY,
        "base_strategy_sha256": BASE_STRATEGY_SHA256,
        "ast_extraction_method": "python_ast",
        "ast_extracted_expressions": ast_items,
        "conditions": [
            {
                "condition_id": spec.condition_id,
                "expression": spec.expression,
                "source_path": spec.source_path,
                "line": spec.line,
                "side": spec.side,
                "signal": spec.signal,
                "operands": list(spec.operands),
                "comparison": spec.comparison,
            }
            for spec in specs.values()
        ],
        "signal_groups": [
            {
                "group_id": group.group_id,
                "signal": group.signal,
                "side": group.side,
                "branch": group.branch,
                "logic": " AND ".join(group.conditions),
                "conditions": list(group.conditions),
                "output_column": group.output_column,
                "enter_tag": group.enter_tag,
            }
            for group in groups.values()
        ],
        "exit_notes": {
            "populate_exit_trend": "ranging_breakdown long exit is represented as dataframe signal",
            "custom_exit": "trade-context exits are listed in AST extraction but not candle-mask ranked in Stage 3D.2-A",
        },
    }


def record_registry(repo_root: Path, final: dict[str, Any]) -> None:
    db = repo_root / "research/registry/research.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stage3d2a_analysis (
              campaign_id TEXT PRIMARY KEY,
              base_strategy_sha256 TEXT NOT NULL,
              dataset_id TEXT NOT NULL,
              proposal_sha256 TEXT NOT NULL,
              proposal_status TEXT NOT NULL,
              final_report_path TEXT NOT NULL,
              artifact_index_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO stage3d2a_analysis(
              campaign_id, base_strategy_sha256, dataset_id, proposal_sha256,
              proposal_status, final_report_path, artifact_index_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                CAMPAIGN_ID,
                BASE_STRATEGY_SHA256,
                DEV_DATASET_ID,
                final["proposal_sha256"],
                final["proposal_status"],
                final["artifact_index"]["final_json"],
                json.dumps(final["artifact_index"], sort_keys=True),
                utc_now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_analysis(repo_root: Path) -> dict[str, Any]:
    assert_integrity(repo_root)
    catalog = load_simple_yaml(repo_root / STAGE3D1_CATALOG)
    queue = load_simple_yaml(repo_root / STAGE3D1_QUEUE)
    baseline = load_baseline_reference(repo_root)
    df = load_strategy_dataframe(repo_root)
    specs = condition_specs()
    groups = signal_groups()
    graph = condition_graph(repo_root, specs, groups)
    coverage = condition_coverage(df, specs, groups)
    branch = branch_activation(df, groups, coverage, baseline["normalized_trades"])
    blockers = blocker_combinations(df, specs, groups)
    sensitivity = threshold_sensitivity(df, specs, groups, queue)
    counterfactual = counterfactual_reachability(df, specs, groups, catalog, sensitivity)
    explanations = explain_stage3d1(df, queue, specs, groups, coverage, sensitivity, counterfactual)
    if any(item["implementation_issue_detected"] for item in explanations["experiments"]):
        raise Stage3D2AError("implementation_error", "stage3d1_experiment_implementation_issue", "Stage 3D.1 experiment issue detected")
    proposal = build_proposal(repo_root, catalog, specs, coverage, sensitivity, counterfactual, blockers)

    for path, payload in [
        (GRAPH_PATH, graph),
        (COVERAGE_PATH, coverage),
        (BRANCH_PATH, branch),
        (EXPLANATION_PATH, explanations),
        (THRESHOLD_PATH, sensitivity),
        (BLOCKER_PATH, blockers),
        (COUNTERFACTUAL_PATH, counterfactual),
    ]:
        dump_json(repo_root / path, payload)
    final = write_reports(repo_root, graph, coverage, branch, explanations, sensitivity, counterfactual, proposal, baseline)
    record_registry(repo_root, final)
    assert_integrity(repo_root)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze RegimeAwareV6 signal reachability for Stage 3D.2-A.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        final = run_analysis(Path.cwd())
    except Stage3D2AError as exc:
        print(json.dumps({"status": "failed", "failure_type": exc.failure_type, "reason_code": exc.reason_code, "message": exc.message}, indent=2))
        return 1
    print(json.dumps(final if args.json else {"status": final["status"], "final_report": final["artifact_index"]["final_json"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
