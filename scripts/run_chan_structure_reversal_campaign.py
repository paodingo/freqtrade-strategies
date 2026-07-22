#!/usr/bin/env python3
"""Run one user-approved causal structure-reversal Candidate Campaign."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_PATH = ROOT / "research/director/compiled/chan-structure-reversal-v1/campaign.yaml"
APPROVAL_PATH = ROOT / "research/governance/approvals/chan-structure-reversal-v1-execution-approval.json"
MANIFEST_PATH = ROOT / "research/candidates/chan-structure-reversal-v1/candidate-manifest.json"
ANALYSIS_PATH = ROOT / "research/analysis/chan-structure-reversal-v1/development-comparison.json"
REPORT_JSON = ROOT / "reports/audits/chan-structure-reversal-v1/final-report.json"
REPORT_MD = ROOT / "reports/audits/chan-structure-reversal-v1/final-report.md"
EXCHANGE_SNAPSHOT = ROOT / "research/exchange_snapshots/binance-usdm-futures-2025-8-demo"

PAIR_SPECS = {
    "btc": {
        "pair": "BTC/USDT:USDT",
        "dataset_id": "temporal-stage3e1-s03-btc-usdt-usdt-1h",
        "manifest": "research/temporal/snapshots/temporal-stage3e1-s03-btc-usdt-usdt-1h/manifest.yaml",
        "datadir": "research/temporal/snapshots/temporal-stage3e1-s03-btc-usdt-usdt-1h/data",
    },
    "eth": {
        "pair": "ETH/USDT:USDT",
        "dataset_id": "futures-dev-eth-usdt-usdt-20240101-20240830-v1",
        "manifest": "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml",
        "datadir": "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/data",
    },
}

ROLE_SPECS = {
    "baseline": {
        "strategy": "RegimeAwareV6",
        "strategy_file": "strategies/RegimeAwareV6.py",
        "strategy_path": "strategies",
    },
    "candidate": {
        "strategy": "RegimeAwareChanStructureLongV1",
        "strategy_file": "research/candidates/chan-structure-reversal-v1/RegimeAwareChanStructureLongV1.py",
        "strategy_path": "research/candidates/chan-structure-reversal-v1",
    },
}

RUN_ORDER = [
    (pair_key, role, repetition)
    for pair_key in ("btc", "eth")
    for role in ("baseline", "candidate")
    for repetition in ("A", "B")
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def campaign_fingerprint(campaign: dict[str, Any]) -> str:
    payload = {key: value for key, value in campaign.items() if key != "campaign_fingerprint"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_candidate_ast(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    candidate = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "RegimeAwareChanStructureLongV1"
    )
    methods = {node.name for node in candidate.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    forbidden = {
        "populate_exit_trend",
        "custom_exit",
        "custom_stoploss",
        "custom_stake_amount",
        "leverage",
        "confirm_trade_entry",
        "confirm_trade_exit",
        "adjust_trade_position",
    }
    assignments = {
        target.id
        for node in candidate.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets if isinstance(node, ast.Assign) else [node.target]
        )
        if isinstance(target, ast.Name)
    }
    forbidden_assignments = assignments & {
        "minimal_roi",
        "stoploss",
        "trailing_stop",
        "position_adjustment_enable",
        "max_entry_position_adjustment",
        "can_short",
    }
    if methods & forbidden or forbidden_assignments:
        raise ValueError(
            f"candidate forbidden surface: methods={sorted(methods & forbidden)} assignments={sorted(forbidden_assignments)}"
        )
    expected = {"causal_structure_long_mask", "populate_indicators", "populate_entry_trend"}
    if methods != expected:
        raise ValueError(f"candidate method surface drift: {sorted(methods)}")
    return {
        "status": "passed",
        "methods": sorted(methods),
        "forbidden_methods": [],
        "forbidden_risk_assignments": [],
    }


def validate_authority() -> dict[str, Any]:
    campaign = load_json(CAMPAIGN_PATH)
    approval = load_json(APPROVAL_PATH)
    manifest = load_json(MANIFEST_PATH)
    checks = {
        "campaign_fingerprint": campaign_fingerprint(campaign) == campaign["campaign_fingerprint"],
        "approval_fingerprint": approval["compiled_campaign_fingerprint"] == campaign["campaign_fingerprint"],
        "direct_human_approval": approval["approval_status"] == "approved"
        and approval["approver_type"] == "human_user"
        and approval["approval_source"] == "user_message_continue"
        and approval["execution_authorized"] is True,
        "candidate_budget": approval["budget"]["max_candidates"] == campaign["budget"]["max_candidates"] == 1,
        "backtest_budget": approval["budget"]["max_backtest_calls"] == campaign["budget"]["max_backtest_calls"] == 8,
        "candidate_hash": sha256_file(ROOT / manifest["source_path"])
        == manifest["source_sha256"]
        == approval["candidate"]["source_sha256"],
        "formal_strategy_hash": sha256_file(ROOT / manifest["formal_strategy_path"])
        == manifest["formal_strategy_sha256"]
        == campaign["frozen_contracts"]["formal_strategy_sha256"],
        "formal_base_hash": sha256_file(ROOT / manifest["formal_base_path"])
        == manifest["formal_base_sha256"]
        == campaign["frozen_contracts"]["formal_base_sha256"],
        "router_hash": sha256_file(ROOT / manifest["router_reference_path"])
        == manifest["router_reference_sha256"]
        == campaign["frozen_contracts"]["router_reference_sha256"],
        "readiness_hash": sha256_file(ROOT / manifest["readiness_semantics_path"])
        == manifest["readiness_semantics_sha256"]
        == campaign["frozen_contracts"]["readiness_semantics_sha256"],
        "constitution_hash": sha256_file(ROOT / "research/governance/research-constitution.yaml")
        == campaign["frozen_contracts"]["constitution_sha256"],
        "evaluation_policy_hash": sha256_file(ROOT / "research/evaluation/evaluation-policy.yaml")
        == campaign["frozen_contracts"]["evaluation_policy_sha256"],
        "single_signal_group": manifest["candidate_count"] == manifest["new_signal_groups"] == 1
        and manifest["new_sides"] == ["long"],
        "protected_access_zero": approval["validation_accesses_authorized"]
        == approval["holdout_accesses_authorized"]
        == campaign["budget"]["max_validation_accesses"]
        == campaign["budget"]["max_holdout_accesses"]
        == 0,
        "candidate_ast": validate_candidate_ast(ROOT / manifest["source_path"])["status"] == "passed",
    }
    for pair_key, spec in PAIR_SPECS.items():
        expected = campaign["datasets"][pair_key]
        checks[f"{pair_key}_manifest_hash"] = (
            sha256_file(ROOT / spec["manifest"])
            == expected["manifest_sha256"]
            and spec["dataset_id"] == expected["dataset_id"]
        )
    if not all(checks.values()):
        raise ValueError("authority validation failed: " + json.dumps(checks, sort_keys=True))
    return checks


def build_spec(pair_key: str, role: str) -> dict[str, Any]:
    pair = PAIR_SPECS[pair_key]
    strategy = ROLE_SPECS[role]
    return {
        "campaign_id": "chan-structure-reversal-v1",
        "fixed_backtest": {
            **strategy,
            "config": "research/runtime/demo-futures-backtest-config.json",
            "dataset_id": pair["dataset_id"],
            "dataset_manifest": pair["manifest"],
            "datadir": pair["datadir"],
            "timerange": "20240609-20240811",
            "timeframe": "1h",
            "pairs": [pair["pair"]],
            "fee": "0.0004",
            "acceptance_gate": {},
        },
    }


def worker(pair_key: str, role: str, repetition: str, experiment_id: int) -> int:
    scripts_root = str(ROOT / "scripts")
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    from run_offline_backtest import run_offline_backtest

    run_id = f"CHAN-{pair_key.upper()}-{role.upper()}-{repetition}-20260719"
    result = run_offline_backtest(
        ROOT,
        build_spec(pair_key, role),
        experiment_id,
        run_id,
        EXCHANGE_SNAPSHOT,
    )
    print(json.dumps({"pid": os.getpid(), "pair_key": pair_key, "role": role, "repetition": repetition, **result}))
    return 0 if result["status"] in {"accepted", "rejected"} else 1


def run_fresh(pair_key: str, role: str, repetition: str, experiment_id: int) -> dict[str, Any]:
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--pair-key",
            pair_key,
            "--role",
            role,
            "--repetition",
            repetition,
            "--experiment-id",
            str(experiment_id),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"fresh process failed: {pair_key}/{role}/{repetition}\n{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def load_run_summary(result: dict[str, Any]) -> dict[str, Any]:
    runner_report_path = ROOT / result["report_path"]
    runner = load_json(runner_report_path)
    metrics = load_json(runner_report_path.parent / runner["metrics_path"])["normalized"]
    raw_result = load_json(runner_report_path.parent / runner["raw_result_path"])
    strategy = next(iter(raw_result["strategy"].values()))
    trades = strategy.get("trades") or []
    tag_counts = Counter(str(trade.get("enter_tag") or "") for trade in trades)
    structure_trades = [trade for trade in trades if str(trade.get("enter_tag") or "").startswith("chan_structure_long_")]
    core = {
        "total_trades": int(metrics.get("total_trades") or 0),
        "long_trade_count": int(metrics.get("long_trade_count") or 0),
        "short_trade_count": int(metrics.get("short_trade_count") or 0),
        "total_profit": float(metrics.get("total_profit") or 0.0),
        "total_profit_pct": float(metrics.get("total_profit_pct") or 0.0),
        "profit_factor": float(metrics.get("profit_factor") or 0.0),
        "winrate": float(metrics.get("winrate") or 0.0),
        "max_drawdown_account": float(strategy.get("max_drawdown_account") or 0.0),
        "funding_fees": float(metrics.get("funding_fees") or 0.0),
    }
    return {
        "pid": result["pid"],
        "status": result["status"],
        "report_path": result["report_path"],
        "network_attempts": runner.get("network_attempts") or [],
        "core_metrics_signature": runner["core_metrics_signature"],
        "core": core,
        "trade_detail_sha256": metrics.get("trade_detail_sha256"),
        "enter_tag_counts": dict(sorted(tag_counts.items())),
        "structure_trade_count": len(structure_trades),
        "structure_trade_profit_abs": round(sum(float(trade.get("profit_abs") or 0.0) for trade in structure_trades), 12),
        "structure_trade_profit_ratio_sum": round(sum(float(trade.get("profit_ratio") or 0.0) for trade in structure_trades), 12),
    }


def metric_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    base = baseline["core"]
    current = candidate["core"]
    return {
        "total_trades": current["total_trades"] - base["total_trades"],
        "long_trade_count": current["long_trade_count"] - base["long_trade_count"],
        "short_trade_count": current["short_trade_count"] - base["short_trade_count"],
        "total_profit": round(current["total_profit"] - base["total_profit"], 12),
        "total_return_percentage_points": round((current["total_profit_pct"] - base["total_profit_pct"]) * 100, 8),
        "profit_factor": round(current["profit_factor"] - base["profit_factor"], 8),
        "winrate_percentage_points": round((current["winrate"] - base["winrate"]) * 100, 8),
        "max_drawdown_percentage_points": round(
            (current["max_drawdown_account"] - base["max_drawdown_account"]) * 100,
            8,
        ),
        "funding_fees": round(current["funding_fees"] - base["funding_fees"], 12),
    }


def forbidden_network_attempts(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return external or blocked attempts; runner loopback IPC is allowed."""
    return [attempt for attempt in attempts if attempt.get("blocked") or not attempt.get("loopback")]


def classify(pair_results: dict[str, dict[str, Any]], reproducible: bool, network_clean: bool) -> tuple[str, dict]:
    btc = pair_results["btc"]
    eth = pair_results["eth"]

    def no_material_degradation(item: dict[str, Any]) -> bool:
        delta = item["candidate_minus_baseline"]
        return (
            delta["max_drawdown_percentage_points"] <= 2.0
            and delta["profit_factor"] >= -0.05
            and delta["total_return_percentage_points"] >= -0.5
        )

    btc_delta = btc["candidate_minus_baseline"]
    material_improvement = (
        btc_delta["max_drawdown_percentage_points"] <= -2.0
        or btc_delta["profit_factor"] >= 0.1
        or btc_delta["total_return_percentage_points"] >= 1.0
    )
    coverage = (
        btc["candidate"]["core"]["total_trades"] >= 20
        and btc["candidate"]["structure_trade_count"] >= 5
        and eth["candidate"]["structure_trade_count"] >= 5
    )
    checks = {
        "fresh_process_reproducibility": reproducible,
        "network_clean": network_clean,
        "btc_coverage": coverage,
        "btc_no_material_degradation": no_material_degradation(btc),
        "btc_material_improvement_any": material_improvement,
        "eth_descriptive_no_material_degradation": no_material_degradation(eth),
        "structure_trades_observed_both_pairs": btc["candidate"]["structure_trade_count"] > 0
        and eth["candidate"]["structure_trade_count"] > 0,
    }
    if not reproducible or not network_clean:
        return "development_execution_invalid", checks
    if not checks["structure_trades_observed_both_pairs"]:
        return "development_inconclusive_no_executed_structure_trades", checks
    if not checks["btc_no_material_degradation"] or not checks["eth_descriptive_no_material_degradation"]:
        return "development_rejected_material_degradation", checks
    if coverage and material_improvement:
        return "development_promising_requires_separate_validation_decision", checks
    return "development_inconclusive", checks


def format_markdown(report: dict[str, Any]) -> str:
    rows = []
    for pair_key, pair_result in report["pair_results"].items():
        pair = PAIR_SPECS[pair_key]["pair"]
        base = pair_result["baseline"]["core"]
        candidate = pair_result["candidate"]["core"]
        delta = pair_result["candidate_minus_baseline"]
        rows.append(
            f"| {pair} | {base['total_trades']} | {candidate['total_trades']} | "
            f"{pair_result['candidate']['structure_trade_count']} | {base['total_profit_pct'] * 100:.3f}% | "
            f"{candidate['total_profit_pct'] * 100:.3f}% | {delta['total_return_percentage_points']:+.3f}pp | "
            f"{base['profit_factor']:.3f} | {candidate['profit_factor']:.3f} | "
            f"{base['max_drawdown_account'] * 100:.3f}% | {candidate['max_drawdown_account'] * 100:.3f}% |"
        )
    return f"""# Chan Structure Reversal Candidate Development Report

## Result

Classification: `{report['classification']}`

| Pair | Baseline trades | Candidate trades | Structure trades | Baseline return | Candidate return | Return delta | Baseline PF | Candidate PF | Baseline DD | Candidate DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Candidate boundary

- One isolated Candidate: `RegimeAwareChanStructureLongV1`.
- One new signal group, long side only.
- Signal: confirmed bottom -> close above preceding swing high -> confirmed higher low.
- Signal is emitted on the retest confirmation candle; it is never backdated.
- Existing entries, exits, ROI, stoploss, leverage, stake, protections and execution configuration are unchanged.

## Execution boundary

- Matrix: BTC/ETH x Baseline/Candidate x RUN-A/RUN-B = `{report['budget_used']['backtest_calls']}` calls.
- Timerange/timeframe: `20240609-20240811` / `1h`.
- Fee: `0.0004`; sealed offline exchange adapter; allowed loopback IPC / forbidden network attempts: `{report['budget_used']['allowed_loopback_network_attempt_count']} / {report['budget_used']['forbidden_network_attempt_count']}`.
- Fresh-process reproducibility: `{str(report['reproducible']).lower()}`.
- Validation/Holdout accesses: `0 / 0`.

## Decision

This development result cannot promote or replace the formal strategy. Validation, forward dry-run, live trading, and any follow-up Candidate require separate decisions.
"""


def run_campaign() -> dict[str, Any]:
    started = time.monotonic()
    authority_checks = validate_authority()
    runs: dict[tuple[str, str, str], dict[str, Any]] = {}
    for experiment_id, (pair_key, role, repetition) in enumerate(RUN_ORDER, start=1):
        raw = run_fresh(pair_key, role, repetition, experiment_id)
        runs[(pair_key, role, repetition)] = load_run_summary(raw)

    reproducible = True
    pair_results: dict[str, dict[str, Any]] = {}
    all_network_attempts = []
    for pair_key in ("btc", "eth"):
        role_summaries = {}
        for role in ("baseline", "candidate"):
            run_a = runs[(pair_key, role, "A")]
            run_b = runs[(pair_key, role, "B")]
            role_reproducible = (
                run_a["pid"] != run_b["pid"]
                and run_a["core_metrics_signature"] == run_b["core_metrics_signature"]
                and run_a["core"] == run_b["core"]
                and run_a["enter_tag_counts"] == run_b["enter_tag_counts"]
            )
            reproducible = reproducible and role_reproducible
            role_summaries[role] = {**run_a, "run_b_pid": run_b["pid"], "reproducible": role_reproducible}
            all_network_attempts.extend(run_a["network_attempts"])
            all_network_attempts.extend(run_b["network_attempts"])
        pair_results[pair_key] = {
            **role_summaries,
            "candidate_minus_baseline": metric_delta(role_summaries["candidate"], role_summaries["baseline"]),
        }

    forbidden_attempts = forbidden_network_attempts(all_network_attempts)
    network_clean = len(forbidden_attempts) == 0
    classification, gate_checks = classify(pair_results, reproducible, network_clean)
    report = {
        "schema_version": "chan-structure-reversal-development-comparison-v1",
        "campaign_id": "chan-structure-reversal-v1",
        "campaign_fingerprint": load_json(CAMPAIGN_PATH)["campaign_fingerprint"],
        "classification": classification,
        "authority_checks": authority_checks,
        "pair_results": pair_results,
        "gate_checks": gate_checks,
        "reproducible": reproducible,
        "budget": load_json(CAMPAIGN_PATH)["budget"],
        "budget_used": {
            "candidates": 1,
            "backtest_calls": len(RUN_ORDER),
            "wall_clock_seconds": round(time.monotonic() - started, 3),
            "network_attempt_count": len(all_network_attempts),
            "allowed_loopback_network_attempt_count": len(all_network_attempts) - len(forbidden_attempts),
            "forbidden_network_attempt_count": len(forbidden_attempts),
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "retries": 0,
        },
        "formal_strategy_modified": False,
        "formal_base_modified": False,
        "candidate_promoted": False,
        "validation_authorized": False,
        "forward_dry_run_authorized": False,
        "live_trading_authorized": False,
        "network_policy": {
            "allowed": "runner loopback IPC only",
            "forbidden": "blocked or non-loopback network attempts",
        },
    }
    write_json(ANALYSIS_PATH, report)
    write_json(REPORT_JSON, report)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(format_markdown(report), encoding="utf-8")
    return report


def finalize_existing_campaign() -> dict[str, Any]:
    """Rebuild the decision from the eight completed reports without new Backtests."""
    started = time.monotonic()
    authority_checks = validate_authority()
    report = load_json(REPORT_JSON)
    campaign = load_json(CAMPAIGN_PATH)
    if report.get("campaign_fingerprint") != campaign["campaign_fingerprint"]:
        raise ValueError("existing report campaign fingerprint mismatch")
    if report.get("budget_used", {}).get("backtest_calls") != len(RUN_ORDER):
        raise ValueError("existing report does not contain the authorized eight Backtests")

    all_network_attempts: list[dict[str, Any]] = []
    observed_signatures: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for experiment_id, (pair_key, role, repetition) in enumerate(RUN_ORDER, start=1):
        run_id = f"CHAN-{pair_key.upper()}-{role.upper()}-{repetition}-20260719"
        runner_path = (
            ROOT
            / "research/results/chan-structure-reversal-v1"
            / str(experiment_id)
            / run_id
            / "runner-report.json"
        )
        if not runner_path.is_file():
            raise ValueError(f"completed runner report missing: {runner_path.relative_to(ROOT)}")
        runner = load_json(runner_path)
        if runner.get("status") not in {"accepted", "rejected"}:
            raise ValueError(f"completed runner status invalid: {runner_path.relative_to(ROOT)}")
        all_network_attempts.extend(runner.get("network_attempts") or [])
        observed_signatures.setdefault((pair_key, role), []).append(runner["core_metrics_signature"])

    for (pair_key, role), signatures in observed_signatures.items():
        if len(signatures) != 2 or signatures[0] != signatures[1]:
            raise ValueError(f"completed A/B signature mismatch: {pair_key}/{role}")
        if report["pair_results"][pair_key][role]["core_metrics_signature"] != signatures[0]:
            raise ValueError(f"existing comparison signature mismatch: {pair_key}/{role}")

    forbidden_attempts = forbidden_network_attempts(all_network_attempts)
    network_clean = len(forbidden_attempts) == 0
    classification, gate_checks = classify(report["pair_results"], report["reproducible"], network_clean)
    report["classification"] = classification
    report["authority_checks"] = authority_checks
    report["gate_checks"] = gate_checks
    report["budget_used"].update(
        {
            "network_attempt_count": len(all_network_attempts),
            "allowed_loopback_network_attempt_count": len(all_network_attempts) - len(forbidden_attempts),
            "forbidden_network_attempt_count": len(forbidden_attempts),
            "report_only_backtest_calls": 0,
            "report_finalization_wall_clock_seconds": round(time.monotonic() - started, 3),
        }
    )
    report["network_policy"] = {
        "allowed": "runner loopback IPC only",
        "forbidden": "blocked or non-loopback network attempts",
    }
    report["finalization_mode"] = "existing_completed_runs_no_new_backtests"
    write_json(ANALYSIS_PATH, report)
    write_json(REPORT_JSON, report)
    REPORT_MD.write_text(format_markdown(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--pair-key", choices=tuple(PAIR_SPECS))
    parser.add_argument("--role", choices=tuple(ROLE_SPECS))
    parser.add_argument("--repetition", choices=("A", "B"))
    parser.add_argument("--experiment-id", type=int)
    parser.add_argument("--finalize-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.worker:
        if not all((args.pair_key, args.role, args.repetition, args.experiment_id)):
            parser.error("worker arguments are required")
        return worker(args.pair_key, args.role, args.repetition, args.experiment_id)
    report = finalize_existing_campaign() if args.finalize_existing else run_campaign()
    print(
        json.dumps(
            {
                "classification": report["classification"],
                "reproducible": report["reproducible"],
                "budget_used": report["budget_used"],
                "outputs": [str(ANALYSIS_PATH.relative_to(ROOT)), str(REPORT_JSON.relative_to(ROOT)), str(REPORT_MD.relative_to(ROOT))],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
