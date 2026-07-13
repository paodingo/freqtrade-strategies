#!/usr/bin/env python3
"""Execute the approved ranging-short branch contribution ablation Campaign."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import run_router_extraction_semantic_equivalence_campaign as harness
from protected_manifest_hash import validate_protected_manifests
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    proposal_fingerprint,
    sha256_file,
    utc_now,
    write_json,
)
from run_stage3a5_acceptance import locate_trades


PROPOSAL_ID = "branch-contribution-ablation-v1"
CAMPAIGN_ID = "stage4a-branch-contribution-ablation-v1"
RESEARCH_UNIT = "ranging_short_entry"
APPROVED_PROPOSAL_FINGERPRINT = "8f7211ad73d4a3528da6fd92e0b7e958e2aebf6159fc2773bc8be8740f9e55cc"
APPROVED_CAMPAIGN_FINGERPRINT = "a3db3e0e2d52f6caf700732150a396acee1fa7accc9f054eaef2cbab43e6490f"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
BASE_SHA256 = "8feaebff14b5e8c537ec310b44b2b1d448db20be1388e3aca51da15b306275f9"
ROUTER_SHA256 = "bee68e27b345a93a1fe8481275e365829c986f700d2719fdd10ffd907e1dffa1"
CANDIDATE_SHA256 = "e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0"
CANDIDATE_SOURCE = "research/candidates/branch-contribution-ablation-v1/1/RegimeAware_Ablation_RangingShort_C1.py"
CANDIDATE_MANIFEST = "research/candidates/branch-contribution-ablation-v1/1/candidate-manifest.json"
ROUTER_SOURCE = "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"
COMPILED_DIR = Path("research/director/compiled/branch-contribution-ablation-v1")
APPROVAL = Path("research/governance/approvals/branch-contribution-ablation-v1-execution-approval.json")
AUTHORIZATION = COMPILED_DIR / "execution-authorization.json"
ATTEMPT_ID = "execution-attempt-1"
RESULT_ROOT = Path("research/results/branch-contribution-ablation-v1/ranging-short-entry/execution-attempt-1")
ANALYSIS_ROOT = Path("research/analysis/branch-contribution-ablation-v1")
REPORT_ROOT = Path("reports/audits/branch-contribution-ablation-v1")
NEXT_ROOT = Path("research/director/next-after-branch-ablation/proposals")
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
RUNTIME_LEVERAGE_TIER = Path(".venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json")
RUNTIME_LEVERAGE_TIER_SHA256 = "3cbdcc23ac57dd40e8664036293947fbe283865ef4a0f87e9265bb441858d981"
ALLOWED_DIFF = [
    "candidate class identity",
    "call verified router-equivalent populate_entry_trend",
    "capture ranging_short pre-gate mask",
    "gate only ranging_short rows from final enter_short",
]
PAIR_SPECS = {
    "btc": {"pair": "BTC/USDT:USDT", "prefix": "BTC_USDT_USDT", "dataset_id": "futures-dev-btc-usdt-usdt-20240101-20240830-v2", "experiment_id": 1},
    "eth": {"pair": "ETH/USDT:USDT", "prefix": "ETH_USDT_USDT", "dataset_id": "futures-dev-eth-usdt-usdt-20240101-20240830-v1", "experiment_id": 1},
}


class AblationExecutionInvalid(RuntimeError):
    reason_code = "ablation_execution_invalid"


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def configure_harness() -> None:
    harness.PROPOSAL_ID = PROPOSAL_ID
    harness.CAMPAIGN_ID = CAMPAIGN_ID
    harness.RESEARCH_UNIT = RESEARCH_UNIT
    harness.APPROVED_CAMPAIGN_FINGERPRINT = APPROVED_CAMPAIGN_FINGERPRINT
    harness.STRATEGY_SHA256 = STRATEGY_SHA256
    harness.BASE_SHA256 = BASE_SHA256
    harness.CANDIDATE_SHA256 = CANDIDATE_SHA256
    harness.CANDIDATE_SOURCE = CANDIDATE_SOURCE
    harness.CANDIDATE_MANIFEST = CANDIDATE_MANIFEST
    harness.COMPILED_DIR = COMPILED_DIR.as_posix()
    harness.RECERTIFICATION_ATTEMPT = ATTEMPT_ID
    harness.CAMPAIGN_PATH_ID = "branch-contribution-ablation-v1"
    harness.RESEARCH_UNIT_PATH_ID = "ranging-short-entry"
    harness.RESULT_ROOT = RESULT_ROOT
    harness.ANALYSIS_ROOT = ANALYSIS_ROOT
    harness.REPORT_ROOT = REPORT_ROOT
    harness.PAIR_SPECS = PAIR_SPECS
    harness.CONTAMINATED_ROOTS = (
        Path("research/results/regime-branch-factorization-v1"),
        Path("research/results/stage4a-regime-conditioned-branch-factorization-v1"),
    )


def validate_candidate_ast(repo: Path) -> dict[str, Any]:
    source = (repo / CANDIDATE_SOURCE).read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if [node.name for node in classes] != ["RegimeAware_Ablation_RangingShort_C1"]:
        raise AblationExecutionInvalid("unauthorized_branch_ablation_diff: candidate class identity")
    methods = [node for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if [node.name for node in methods] != ["populate_entry_trend"]:
        raise AblationExecutionInvalid("unauthorized_branch_ablation_diff: unexpected method surface")
    method = methods[0]
    calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
    super_calls = [node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "populate_entry_trend"]
    if len(super_calls) != 1:
        raise AblationExecutionInvalid("unauthorized_branch_ablation_diff: router call count")
    signal_strings = [node.value for node in ast.walk(method) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    forbidden = {"enter_long", "exit_long", "exit_short"} & set(signal_strings)
    if forbidden or signal_strings.count("enter_short") != 2 or signal_strings.count("ranging_short") != 1:
        raise AblationExecutionInvalid("unauthorized_branch_ablation_diff: signal surface")
    zero_gates = [node for node in ast.walk(method) if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value == 0]
    if len(zero_gates) != 1:
        raise AblationExecutionInvalid("unauthorized_branch_ablation_diff: final gate count")
    return {"status": "passed", "class_count": 1, "method_count": 1, "router_calls": 1, "final_zero_gates": 1, "forbidden_signal_fields": []}


def validate_authority(repo: Path) -> dict[str, Any]:
    campaign = load_document(repo / COMPILED_DIR / "campaign.yaml")
    proposal = load_document(repo / "research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json")
    approval = load_document(repo / APPROVAL)
    authorization = load_document(repo / AUTHORIZATION)
    candidate = load_document(repo / CANDIDATE_MANIFEST)
    computed = fingerprint({key: value for key, value in campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
    checks: dict[str, Any] = {
        "proposal_fingerprint": proposal_fingerprint(proposal) == approval["proposal_fingerprint"] == APPROVED_PROPOSAL_FINGERPRINT,
        "campaign_fingerprint": computed == campaign["campaign_fingerprint"] == approval["compiled_campaign_fingerprint"] == authorization["approved_compiled_fingerprint"] == APPROVED_CAMPAIGN_FINGERPRINT,
        "human_execution_approval": approval["approval_status"] == "approved" and approval["approver_type"] == "human_user" and approval["execution_authorized"] is True,
        "research_unit": approval["research_unit"] == authorization["research_unit"] == candidate["selected_ablation_unit"] == RESEARCH_UNIT,
        "candidate_identity": approval["candidate"]["class_name"] == candidate["class_name"] == "RegimeAware_Ablation_RangingShort_C1" and approval["candidate"]["path"] == authorization["candidate_source_path"] == candidate["source_path"] == CANDIDATE_SOURCE,
        "candidate_source_hash": sha256_file(repo / CANDIDATE_SOURCE) == candidate["source_sha256"] == CANDIDATE_SHA256,
        "candidate_count": approval["budget"]["max_candidates"] == authorization["candidate_count_authorized"] == candidate["candidate_count"] == 1,
        "backtest_budget": approval["budget"]["max_backtest_calls"] == authorization["max_backtest_calls"] == campaign["budget"]["max_backtest_calls"] == 8,
        "wall_clock_budget": approval["budget"]["max_wall_clock_minutes"] == authorization["max_wall_clock_minutes"] == 120,
        "validation_holdout_zero": authorization["validation_accesses_authorized"] == authorization["holdout_accesses_authorized"] == campaign["budget"]["max_validation_accesses"] == campaign["budget"]["max_holdout_accesses"] == 0,
        "formal_strategy_hash": sha256_file(repo / "strategies/RegimeAwareV6.py") == candidate["formal_strategy_sha256"] == STRATEGY_SHA256,
        "formal_base_hash": sha256_file(repo / "strategies/regime_aware_base.py") == candidate["formal_base_sha256"] == BASE_SHA256,
        "router_hash": sha256_file(repo / ROUTER_SOURCE) == candidate["router_reference_sha256"] == ROUTER_SHA256,
        "constitution_hash": sha256_file(repo / campaign["frozen_inputs"]["constitution"]["path"]) == campaign["frozen_inputs"]["constitution"]["sha256"],
        "runtime_hash": sha256_file(repo / campaign["frozen_inputs"]["runtime"]["path"]) == campaign["frozen_inputs"]["runtime"]["sha256"],
        "policy_hash": sha256_file(repo / campaign["frozen_inputs"]["policy"]["path"]) == campaign["frozen_inputs"]["policy"]["sha256"],
        "diff_allowlist": authorization["single_variable_diff_allowlist"] == candidate["single_variable_diff_allowlist"] == ALLOWED_DIFF,
        "condition_inventory": candidate["condition_count"] == 29 and candidate["signal_group_count"] == 5 and candidate["conditions_changed"] == candidate["thresholds_changed"] == candidate["signal_groups_changed"] == 0,
        "protected_manifests": validate_protected_manifests(repo)["passed"],
        "candidate_ast": validate_candidate_ast(repo)["status"] == "passed",
        "runtime_leverage_tier": (repo / RUNTIME_LEVERAGE_TIER).is_file()
        and (repo / RUNTIME_LEVERAGE_TIER).stat().st_size == 2176158
        and sha256_file(repo / RUNTIME_LEVERAGE_TIER) == RUNTIME_LEVERAGE_TIER_SHA256,
    }
    for dataset in campaign["frozen_inputs"]["datasets"]:
        manifest_path = repo / "research/data/snapshots" / dataset["dataset_id"] / "manifest.yaml"
        manifest = load_document(manifest_path)
        checks[f"manifest:{dataset['dataset_id']}"] = sha256_file(manifest_path) == dataset["manifest_sha256"]
        checks[f"dataset:{dataset['dataset_id']}"] = all(
            (repo / item["path"]).is_file()
            and (repo / item["path"]).stat().st_size == item["bytes"]
            and sha256_file(repo / item["path"]) == item["sha256"]
            for item in manifest["files"]
        )
    if not all(checks.values()):
        raise AblationExecutionInvalid("execution_authority_validation_failed:" + json.dumps(checks, sort_keys=True))
    return checks


def load_strategy(repo: Path, role: str):
    if role == "baseline":
        module_dir, module_name, class_name = repo / "strategies", "RegimeAwareV6", "RegimeAwareV6"
        source = repo / "strategies/RegimeAwareV6.py"
    else:
        module_dir = repo / Path(CANDIDATE_SOURCE).parent
        module_name = class_name = "RegimeAware_Ablation_RangingShort_C1"
        source = repo / CANDIDATE_SOURCE
    sys.path.insert(0, str(module_dir))
    module = importlib.import_module(module_name)
    return getattr(module, class_name), module, source


_router_signal_mask = harness.signal_mask


def signal_mask(repo: Path, role: str, pair_key: str, run_id: str, output: Path) -> dict[str, Any]:
    result = _router_signal_mask(repo, role, pair_key, run_id, output)
    payload = load_document(output)
    rows = payload["rows"]
    branch_rows = [row for row in rows if row.get("enter_tag") == "ranging_short"]
    projection = {
        "unit_id": RESEARCH_UNIT,
        "pre_gate_signal_count": len(branch_rows),
        "final_enter_short_count_for_tag": sum(int(row.get("enter_short") or 0) for row in branch_rows),
        "tag_preserved_count": len(branch_rows),
        "pre_gate_rows_sha256": canonical_hash([{"date": row["date"], "enter_tag": row["enter_tag"]} for row in branch_rows]),
    }
    payload["branch_contribution_projection"] = projection
    write_json(output, payload)
    result["branch_contribution_projection"] = projection
    return result


def backtest_campaign(pair_key: str, role: str) -> dict[str, Any]:
    spec = PAIR_SPECS[pair_key]
    strategy = "RegimeAwareV6" if role == "baseline" else "RegimeAware_Ablation_RangingShort_C1"
    strategy_file = "strategies/RegimeAwareV6.py" if role == "baseline" else CANDIDATE_SOURCE
    strategy_path = "strategies" if role == "baseline" else Path(CANDIDATE_SOURCE).parent.as_posix()
    return {"campaign_id": CAMPAIGN_ID, "fixed_backtest": {
        "strategy": strategy, "strategy_file": strategy_file, "strategy_path": strategy_path,
        "config": "research/runtime/demo-futures-backtest-config.json",
        "dataset_id": spec["dataset_id"], "dataset_manifest": f"research/data/snapshots/{spec['dataset_id']}/manifest.yaml",
        "datadir": f"research/data/snapshots/{spec['dataset_id']}/data", "timerange": "20240203-20240830",
        "timeframe": "1h", "pairs": [spec["pair"]], "fee": "0.0004", "acceptance_gate": {},
    }}


def run_fresh(repo: Path, pair_key: str, role: str, repetition: str) -> dict[str, Any]:
    execution_id = uuid.uuid4().hex[:12]
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", "--pair", pair_key, "--role", role, "--repetition", repetition, "--execution-id", execution_id],
        cwd=repo, text=True, capture_output=True, check=False, timeout=1800,
        env={**os.environ, "PORTABLE_BASELINE_NETWORK": "forbidden"},
    )
    if completed.returncode != 0:
        raise AblationExecutionInvalid(f"fresh_worker_failed:{pair_key}:{role}:{repetition}:{completed.stderr[-2500:]}:{completed.stdout[-2500:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    write_json(repo / payload["output_root"] / "worker-launch.json", {"returncode": 0, "stdout": completed.stdout, "stderr": completed.stderr, "shell": False, "execution_id": execution_id})
    return payload


def _load_normalized(repo: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    return load_document(repo / run["normalized_trades_path"])["rows"]


def _fee_summary(repo: Path, run: dict[str, Any]) -> dict[str, float]:
    raw = load_document(repo / run["raw_result_path"])
    trades = locate_trades(raw, run["strategy"])
    trading_fees = 0.0
    funding = 0.0
    for trade in trades:
        orders = trade.get("orders") or []
        if orders:
            trading_fees += float(orders[0].get("cost") or 0) * float(trade.get("fee_open") or 0)
            trading_fees += float(orders[-1].get("cost") or 0) * float(trade.get("fee_close") or 0)
        funding += float(trade.get("funding_fees") or 0)
    return {"trading_fee_cost": trading_fees, "funding_fees": funding}


def _rolling_28_day(rows: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, float] = defaultdict(float)
    for row in rows:
        timestamp = str(row["close_date"])[:10]
        from datetime import datetime, timezone, timedelta
        moment = datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc)
        origin = datetime(2024, 2, 3, tzinfo=timezone.utc)
        start = origin + timedelta(days=28 * max(0, (moment - origin).days // 28))
        buckets[start.date().isoformat()] += float(row.get("profit_abs") or 0)
    return {key: round(value, 12) for key, value in sorted(buckets.items())}


def _trade_counter(rows: list[dict[str, Any]]) -> Counter[str]:
    fields = ("pair", "open_date", "close_date", "is_short", "enter_tag", "exit_reason", "open_rate", "close_rate")
    return Counter(canonical_hash({field: row.get(field) for field in fields}) for row in rows)


def compare_pair(repo: Path, pair_key: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(run["role"], run["repetition"]): run for run in runs}
    reproducibility = {}
    for role in ("baseline", "candidate"):
        left, right = by_key[(role, "A")], by_key[(role, "B")]
        identity = harness.audit_runtime_identity(left, right, role)
        semantic = harness.compare_signal_semantics(left["signal_mask"], right["signal_mask"])
        differences = {field: [left[field], right[field]] for field in ("summary", "normalized_trade_hash", "normalized_trade_count") if left[field] != right[field]}
        if not semantic["passed"]:
            differences["signal_semantics"] = semantic["differences"]
        reproducibility[role] = {"passed": not differences, "identity": identity, "signal_semantics": semantic, "differences": differences, "pids": [left["pid"], right["pid"]]}
    if not all(item["passed"] for item in reproducibility.values()):
        raise AblationExecutionInvalid(f"run_reproducibility_failure:{pair_key}")
    baseline, candidate = by_key[("baseline", "A")], by_key[("candidate", "A")]
    harness.audit_cross_role_identity(baseline, candidate)
    baseline_rows, candidate_rows = _load_normalized(repo, baseline), _load_normalized(repo, candidate)
    baseline_counter, candidate_counter = _trade_counter(baseline_rows), _trade_counter(candidate_rows)
    removed = sum((baseline_counter - candidate_counter).values())
    added = sum((candidate_counter - baseline_counter).values())
    base_core, cand_core = baseline["summary"]["core"], candidate["summary"]["core"]
    metric_fields = ("total_profit", "total_profit_pct", "profit_factor", "max_drawdown", "total_trades", "long_trade_count", "short_trade_count")
    metric_delta = {field: (None if base_core.get(field) is None or cand_core.get(field) is None else cand_core[field] - base_core[field]) for field in metric_fields}
    base_fees, cand_fees = _fee_summary(repo, baseline), _fee_summary(repo, candidate)
    fee_delta = {key: cand_fees[key] - base_fees[key] for key in base_fees}
    base_remaining = [row for row in baseline_rows if row.get("enter_tag") != "ranging_short"]
    cand_remaining = [row for row in candidate_rows if row.get("enter_tag") != "ranging_short"]
    direction = "branch_negative" if metric_delta["total_profit"] > 0 else "branch_positive" if metric_delta["total_profit"] < 0 else "neutral"
    return {
        "schema_version": "branch-contribution-pair-comparison-v1", "pair_key": pair_key, "pair": PAIR_SPECS[pair_key]["pair"],
        "reproducibility": reproducibility, "runs": runs,
        "signals": {"baseline_pre_gate": baseline["signal_mask"]["branch_contribution_projection"]["pre_gate_signal_count"], "candidate_pre_gate": candidate["signal_mask"]["branch_contribution_projection"]["pre_gate_signal_count"], "candidate_final_ranging_short_enter_short": candidate["signal_mask"]["branch_contribution_projection"]["final_enter_short_count_for_tag"]},
        "trades": {"baseline": len(baseline_rows), "candidate": len(candidate_rows), "removed": removed, "added_or_shifted": added, "baseline_normalized_hash": baseline["normalized_trade_hash"], "candidate_normalized_hash": candidate["normalized_trade_hash"]},
        "baseline_metrics": base_core, "candidate_metrics": cand_core, "candidate_minus_baseline": metric_delta,
        "baseline_costs": base_fees, "candidate_costs": cand_fees, "candidate_minus_baseline_costs": fee_delta,
        "rolling_28_day_profit_abs": {"baseline": _rolling_28_day(baseline_rows), "candidate": _rolling_28_day(candidate_rows)},
        "tags": {"baseline": baseline["summary"]["enter_tag_counts"], "candidate": candidate["summary"]["enter_tag_counts"]},
        "exit_reasons": {"baseline": baseline["summary"]["exit_reason_counts"], "candidate": candidate["summary"]["exit_reason_counts"]},
        "remaining_branch_behavior": {"baseline_count": len(base_remaining), "candidate_count": len(cand_remaining), "baseline_hash": canonical_hash(base_remaining), "candidate_hash": canonical_hash(cand_remaining)},
        "contribution_direction": direction,
    }


def classify(pair_results: dict[str, dict[str, Any]]) -> str:
    if any(result["signals"]["baseline_pre_gate"] == 0 for result in pair_results.values()):
        return "branch_contribution_inconclusive"
    if all(result["trades"]["removed"] == 0 and result["trades"]["added_or_shifted"] == 0 for result in pair_results.values()):
        return "branch_redundant"
    directions = {result["contribution_direction"] for result in pair_results.values()}
    if directions == {"branch_negative"}:
        return "branch_negative_contributor"
    if directions == {"branch_positive"}:
        return "branch_positive_contributor"
    if "branch_negative" in directions and "branch_positive" in directions:
        return "branch_mixed_regime_dependent"
    return "branch_contribution_inconclusive"


def next_proposal(result: str, pair_results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    proposal = {
        "proposal_id": "ranging-short-branch-decision-review-v1",
        "research_question": "Should the ranging-short entry branch remain active research structure after the development-only contribution ablation?",
        "referenced_variables": [], "referenced_mechanisms": ["ranging_short_entry"],
        "market_scope": {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "timeframe": "1h"},
        "data_scope": {"development_only": True, "validation": False, "holdout": False},
        "proposed_method": {"type": "human_decision_review", "campaign_result": result, "execute_automatically": False},
        "risk_class": "medium", "status": "pending_human_review",
        "evidence": [f"research/analysis/branch-contribution-ablation-v1/{key}-contribution-comparison.json" for key in pair_results],
    }
    proposal["semantic_fingerprint"] = proposal_fingerprint(proposal)
    return proposal


def record_registry(repo: Path, final: dict[str, Any], assets: list[str]) -> None:
    connection = open_director_registry(repo / "research/registry/stage4a-director.db")
    completed = utc_now()
    run_id = "branch-contribution-ablation-v1-execution-attempt-1"
    connection.execute("INSERT OR REPLACE INTO proposal_selection_events(proposal_id,proposal_fingerprint,approval_status,approver_type,approved_at,payload_json) VALUES(?,?,?,?,?,?)", (PROPOSAL_ID, APPROVED_PROPOSAL_FINGERPRINT, "approved", "human_user", completed, json.dumps(load_document(repo / APPROVAL), sort_keys=True)))
    connection.execute("INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id,campaign_id,approved_compiled_fingerprint,proposal_id,execution_authorized,payload_json,authorized_at) VALUES(?,?,?,?,?,?,?)", (load_document(repo / AUTHORIZATION)["authorization_id"], CAMPAIGN_ID, APPROVED_CAMPAIGN_FINGERPRINT, PROPOSAL_ID, 1, json.dumps(load_document(repo / AUTHORIZATION), sort_keys=True), completed))
    connection.execute("INSERT OR REPLACE INTO research_campaign_runs(run_id,campaign_id,proposal_id,status,result_code,campaign_executed,candidate_created,strategy_modified,validation_accesses,holdout_accesses,payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (run_id, CAMPAIGN_ID, PROPOSAL_ID, "completed", final["classification"], 1, 1, 0, 0, 0, json.dumps(final, sort_keys=True), completed))
    for path in assets:
        connection.execute("INSERT OR REPLACE INTO research_campaign_assets(asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)", (f"{run_id}:{path}", run_id, "campaign_evidence", path, sha256_file(repo / path), completed))
    connection.commit(); connection.close()


def run_campaign(repo: Path) -> dict[str, Any]:
    started = time.monotonic()
    checks = validate_authority(repo)
    all_runs: dict[str, list[dict[str, Any]]] = {"btc": [], "eth": []}
    calls = 0
    order = [("btc", "baseline", "A"), ("btc", "baseline", "B"), ("btc", "candidate", "A"), ("btc", "candidate", "B"), ("eth", "baseline", "A"), ("eth", "baseline", "B"), ("eth", "candidate", "A"), ("eth", "candidate", "B")]
    for pair_key, role, repetition in order:
        validate_authority(repo)
        run = run_fresh(repo, pair_key, role, repetition)
        calls += 1
        forbidden_network = [attempt for attempt in run["network_attempts"] if attempt.get("blocked") or not attempt.get("loopback")]
        if calls > 8 or forbidden_network:
            raise AblationExecutionInvalid("budget_or_network_contract_violation")
        all_runs[pair_key].append(run)
    pids = [run["pid"] for runs in all_runs.values() for run in runs]
    if calls != 8 or len(pids) != len(set(pids)):
        raise AblationExecutionInvalid("fresh_process_or_budget_mismatch")
    pair_results = {key: compare_pair(repo, key, runs) for key, runs in all_runs.items()}
    for key, result in pair_results.items():
        write_json(repo / ANALYSIS_ROOT / f"{key}-contribution-comparison.json", result)
    classification = classify(pair_results)
    proposal = next_proposal(classification, pair_results)
    write_json(repo / NEXT_ROOT / f"{proposal['proposal_id']}.json", proposal)
    final = {
        "schema_version": "branch-contribution-ablation-result-v1", "proposal_id": PROPOSAL_ID,
        "campaign_id": CAMPAIGN_ID, "research_unit": RESEARCH_UNIT, "campaign_fingerprint": APPROVED_CAMPAIGN_FINGERPRINT,
        "status": "completed", "classification": classification, "authority_checks": checks,
        "pair_results": {key: {field: value[field] for field in ("signals", "trades", "baseline_metrics", "candidate_metrics", "candidate_minus_baseline", "baseline_costs", "candidate_costs", "candidate_minus_baseline_costs", "contribution_direction")} for key, value in pair_results.items()},
        "backtest_calls": calls, "worker_pids": pids, "all_worker_pids_unique": True,
        "budget": {"max_candidates": 1, "max_backtest_calls": 8, "max_wall_clock_minutes": 120},
        "budget_used": {"candidates": 1, "backtest_calls": calls, "wall_clock_seconds": round(time.monotonic() - started, 3)},
        "strategy_modified": False, "base_modified": False, "router_modified": False, "candidate_count": 1,
        "validation_accesses": 0, "holdout_accesses": 0, "temporal_slices_run": 0, "hyperopt_run": False,
        "next_proposal": {"proposal_id": proposal["proposal_id"], "risk_class": proposal["risk_class"], "status": proposal["status"], "fingerprint": proposal["semantic_fingerprint"]},
        "automatic_followup_executed": False,
    }
    analysis = ANALYSIS_ROOT / "contribution-result.json"
    execution = COMPILED_DIR / "execution/campaign-execution.json"
    report_json = REPORT_ROOT / "branch-contribution-ablation-final-report.json"
    report_md = REPORT_ROOT / "branch-contribution-ablation-final-report.md"
    for path in (analysis, execution, report_json): write_json(repo / path, final)
    lines = ["# Branch Contribution Ablation Final Report", "", f"- Classification: `{classification}`", "- Candidate: `RegimeAware_Ablation_RangingShort_C1`", "- Backtest calls: `8`", "- Validation/Holdout: `0 / 0`", "- Formal strategy modified: `false`", ""]
    for key, result in pair_results.items():
        delta = result["candidate_minus_baseline"]
        lines.extend([f"## {key.upper()}", "", f"- Removed signals: `{result['signals']['baseline_pre_gate']}`", f"- Removed/shifted trades: `{result['trades']['removed']} / {result['trades']['added_or_shifted']}`", f"- Return delta: `{delta['total_profit']}`", f"- Profit Factor delta: `{delta['profit_factor']}`", f"- Max drawdown delta: `{delta['max_drawdown']}`", ""])
    lines.extend(["## Next Proposal", "", f"`{proposal['proposal_id']}` is `{proposal['status']}` and was not executed.", ""])
    (repo / report_md).parent.mkdir(parents=True, exist_ok=True); (repo / report_md).write_text("\n".join(lines), encoding="utf-8")
    assets = [CANDIDATE_SOURCE, CANDIDATE_MANIFEST, APPROVAL.as_posix(), AUTHORIZATION.as_posix(), analysis.as_posix(), execution.as_posix(), report_json.as_posix(), report_md.as_posix(), *(f"{ANALYSIS_ROOT.as_posix()}/{key}-contribution-comparison.json" for key in pair_results), (NEXT_ROOT / f"{proposal['proposal_id']}.json").as_posix()]
    record_registry(repo, final, list(assets))
    return final


def main() -> int:
    configure_harness()
    harness.load_strategy = load_strategy
    harness.signal_mask = signal_mask
    harness.backtest_campaign = backtest_campaign
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--pair", choices=sorted(PAIR_SPECS))
    parser.add_argument("--role", choices=("baseline", "candidate"))
    parser.add_argument("--repetition", choices=("A", "B"))
    parser.add_argument("--execution-id")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        if args.worker:
            if not all((args.pair, args.role, args.repetition, args.execution_id)):
                parser.error("worker arguments incomplete")
            result = harness.worker(repo, args.pair, args.role, args.repetition, args.execution_id)
        else:
            result = run_campaign(repo)
    except AblationExecutionInvalid as exc:
        print(json.dumps({"status": exc.reason_code, "detail": str(exc)}, indent=2)); return 2
    print(json.dumps(result, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
