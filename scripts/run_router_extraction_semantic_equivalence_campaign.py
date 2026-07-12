#!/usr/bin/env python3
"""Execute the approved router-extraction semantic-equivalence Campaign."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from protected_manifest_hash import canonical_text_sha256, validate_protected_manifests
from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, utc_now, write_json, write_yaml
from run_experiment import artifact_hashes, find_result_json
from run_offline_backtest import run_offline_backtest
from run_stage3a5_acceptance import metric_summary, write_normalized_trades


PROPOSAL_ID = "regime-conditioned-branch-factorization-v1"
CAMPAIGN_ID = "stage4a-regime-conditioned-branch-factorization-v1"
RESEARCH_UNIT = "router-extraction-semantic-equivalence-v1"
APPROVED_CAMPAIGN_FINGERPRINT = "5f759a309a23e684bbd3277a3aff1de3b075c01ddd22e2d3f67e57e00c7c8fe3"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
BASE_SHA256 = "8feaebff14b5e8c537ec310b44b2b1d448db20be1388e3aca51da15b306275f9"
CANDIDATE_SOURCE = "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"
CANDIDATE_MANIFEST = "research/candidates/regime-conditioned-branch-factorization-v1/candidate-manifest.json"
COMPILED_DIR = "research/director/compiled/regime-conditioned-branch-factorization-v1"
RESULT_ROOT = Path("research/results") / CAMPAIGN_ID
ANALYSIS_ROOT = Path("research/analysis/regime-conditioned-branch-factorization")
REPORT_ROOT = Path("reports/audits/regime-conditioned-branch-factorization")
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
PAIR_SPECS = {
    "btc": {
        "pair": "BTC/USDT:USDT",
        "prefix": "BTC_USDT_USDT",
        "dataset_id": "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
        "experiment_id": 2,
    },
    "eth": {
        "pair": "ETH/USDT:USDT",
        "prefix": "ETH_USDT_USDT",
        "dataset_id": "futures-dev-eth-usdt-usdt-20240101-20240830-v1",
        "experiment_id": 3,
    },
}


class SemanticMismatch(RuntimeError):
    reason_code = "router_extraction_semantic_mismatch"


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def validate_authority(repo: Path) -> dict[str, Any]:
    campaign = load_document(repo / COMPILED_DIR / "campaign.yaml")
    approval = load_document(repo / "research/governance/approvals/regime-conditioned-branch-factorization-v1-execution-approval.json")
    authorization = load_document(repo / COMPILED_DIR / "execution-authorization.json")
    candidate = load_document(repo / CANDIDATE_MANIFEST)
    computed = fingerprint({key: value for key, value in campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
    protected = validate_protected_manifests(repo)
    checks = {
        "proposal_id": campaign["proposal_id"] == approval["proposal_id"] == authorization["proposal_id"] == PROPOSAL_ID,
        "research_unit": approval["research_unit"] == authorization["research_unit"] == RESEARCH_UNIT,
        "campaign_fingerprint": computed == campaign["campaign_fingerprint"] == approval["compiled_campaign_fingerprint"] == authorization["approved_compiled_fingerprint"] == APPROVED_CAMPAIGN_FINGERPRINT,
        "human_approval": approval["approval_status"] == "approved" and approval["approver_type"] == "human_user",
        "execution_authorized": approval["execution_authorized"] is True and authorization["execution_authorized"] is True,
        "candidate_path": authorization["candidate_source_path"] == candidate["source_path"] == CANDIDATE_SOURCE,
        "candidate_manifest_path": authorization["candidate_manifest_path"] == CANDIDATE_MANIFEST,
        "candidate_source_hash": sha256_file(repo / CANDIDATE_SOURCE) == candidate["source_sha256"],
        "candidate_count": approval["budget"]["max_candidates"] == authorization["candidate_count_authorized"] == candidate["candidate_count"] == 1,
        "backtest_budget": approval["budget"]["max_backtest_calls"] == authorization["max_backtest_calls"] == 8,
        "wall_clock_budget": approval["budget"]["max_wall_clock_minutes"] == authorization["max_wall_clock_minutes"] == 120,
        "strategy_hash": sha256_file(repo / "strategies/RegimeAwareV6.py") == candidate["formal_strategy_sha256"] == STRATEGY_SHA256,
        "base_hash": sha256_file(repo / "strategies/regime_aware_base.py") == candidate["formal_base_sha256"] == BASE_SHA256,
        "constitution_hash": sha256_file(repo / campaign["frozen_inputs"]["constitution"]["path"]) == campaign["frozen_inputs"]["constitution"]["sha256"],
        "runtime_hash": sha256_file(repo / campaign["frozen_inputs"]["runtime"]["path"]) == campaign["frozen_inputs"]["runtime"]["sha256"],
        "policy_hash": sha256_file(repo / campaign["frozen_inputs"]["policy"]["path"]) == campaign["frozen_inputs"]["policy"]["sha256"],
        "protected_manifests": protected["passed"],
        "condition_inventory": candidate["condition_count"] == 29 and candidate["signal_group_count"] == 5 and candidate["conditions_changed"] == candidate["thresholds_changed"] == candidate["signal_groups_changed"] == 0,
        "single_structural_variable": candidate["single_structural_variable"] == "location_and_interface_of_regime_dispatch_only",
        "diff_allowlist": authorization["router_extraction_diff_allowlist"] == candidate["allowed_diff"],
        "validation_zero": approval["validation_accesses_authorized"] == authorization["validation_accesses_authorized"] == campaign["budget"]["max_validation_accesses"] == 0,
        "holdout_zero": approval["holdout_accesses_authorized"] == authorization["holdout_accesses_authorized"] == 0 and campaign["autonomy"]["access_sealed_holdout"] is False,
        "ablation_forbidden": authorization["branch_contribution_ablation_authorized"] is False,
        "followup_forbidden": authorization["automatic_followup_campaign_authorized"] is False,
    }
    for dataset in campaign["frozen_inputs"]["datasets"]:
        manifest_path = repo / "research/data/snapshots" / dataset["dataset_id"] / "manifest.yaml"
        checks[f"manifest:{dataset['dataset_id']}"] = canonical_text_sha256(manifest_path) == dataset["manifest_sha256"]
        manifest = load_document(manifest_path)
        checks[f"dataset:{dataset['dataset_id']}"] = all(
            (repo / item["path"]).is_file()
            and (repo / item["path"]).stat().st_size == item["bytes"]
            and sha256_file(repo / item["path"]) == item["sha256"]
            for item in manifest["files"]
        )
    if not all(checks.values()):
        raise ValueError("execution_authority_validation_failed:" + json.dumps(checks, sort_keys=True))
    return checks


def load_strategy(repo: Path, role: str):
    if role == "baseline":
        module_dir = repo / "strategies"
        module_name = "RegimeAwareV6"
        class_name = "RegimeAwareV6"
        source = repo / "strategies/RegimeAwareV6.py"
    else:
        module_dir = repo / Path(CANDIDATE_SOURCE).parent
        module_name = "RegimeAwareRouterEquivalentV1"
        class_name = "RegimeAwareRouterEquivalentV1"
        source = repo / CANDIDATE_SOURCE
    sys.path.insert(0, str(module_dir))
    module = importlib.import_module(module_name)
    strategy_class = getattr(module, class_name)
    return strategy_class, module, source


def signal_mask(repo: Path, role: str, pair_key: str, output: Path) -> dict[str, Any]:
    spec = PAIR_SPECS[pair_key]
    data_root = repo / "research/data/snapshots" / spec["dataset_id"] / "data/futures"

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return [spec["pair"]]

        def get_pair_dataframe(self, pair: str, timeframe: str, candle_type: str = "futures") -> pd.DataFrame:
            if pair != spec["pair"] or candle_type != "futures" or timeframe != "4h":
                raise ValueError("unauthorized_signal_instrumentation_input")
            return pd.read_feather(data_root / f"{spec['prefix']}-4h-futures.feather")

    strategy_class, module, source = load_strategy(repo, role)
    raw = pd.read_feather(data_root / f"{spec['prefix']}-1h-futures.feather")
    strategy = strategy_class({})
    strategy.dp = DataProvider()
    frame = strategy.populate_indicators(raw.copy(), {"pair": spec["pair"]})
    frame = strategy.populate_entry_trend(frame, {"pair": spec["pair"]})
    frame = strategy.populate_exit_trend(frame, {"pair": spec["pair"]})
    columns = ["enter_long", "enter_short", "exit_long", "exit_short"]
    rows = []
    counts = {}
    for column in columns:
        series = frame[column].fillna(0).astype(int) if column in frame else pd.Series(0, index=frame.index)
        counts[column] = int(series.sum())
    for index, row in frame.iterrows():
        item: dict[str, Any] = {"date": pd.Timestamp(row["date"]).isoformat()}
        for column in columns:
            item[column] = int(row[column]) if column in frame and not pd.isna(row[column]) else 0
        for column in ("enter_tag", "exit_tag"):
            value = row.get(column)
            item[column] = None if value is None or pd.isna(value) else str(value)
        rows.append(item)
    payload = {
        "schema_version": "router-equivalence-signal-mask-v1",
        "role": role,
        "pair": spec["pair"],
        "strategy_class": strategy_class.__name__,
        "strategy_module": module.__name__,
        "strategy_module_path": str(Path(module.__file__ or "").resolve()),
        "strategy_source_sha256": sha256_file(source),
        "formal_strategy_sha256": sha256_file(repo / "strategies/RegimeAwareV6.py"),
        "formal_base_sha256": sha256_file(repo / "strategies/regime_aware_base.py"),
        "row_count": len(rows),
        "signal_counts": counts,
        "rows_sha256": canonical_hash(rows),
        "rows": rows,
    }
    write_json(output, payload)
    return {key: value for key, value in payload.items() if key != "rows"}


def backtest_campaign(pair_key: str, role: str) -> dict[str, Any]:
    spec = PAIR_SPECS[pair_key]
    strategy = "RegimeAwareV6" if role == "baseline" else "RegimeAwareRouterEquivalentV1"
    strategy_file = "strategies/RegimeAwareV6.py" if role == "baseline" else CANDIDATE_SOURCE
    strategy_path = "strategies" if role == "baseline" else str(Path(CANDIDATE_SOURCE).parent).replace("\\", "/")
    return {
        "campaign_id": CAMPAIGN_ID,
        "fixed_backtest": {
            "strategy": strategy,
            "strategy_file": strategy_file,
            "strategy_path": strategy_path,
            "config": "research/runtime/demo-futures-backtest-config.json",
            "dataset_id": spec["dataset_id"],
            "dataset_manifest": f"research/data/snapshots/{spec['dataset_id']}/manifest.yaml",
            "datadir": f"research/data/snapshots/{spec['dataset_id']}/data",
            "timerange": "20240203-20240830",
            "timeframe": "1h",
            "pairs": [spec["pair"]],
            "fee": "0.0004",
            "acceptance_gate": {},
        },
    }


def worker(repo: Path, pair_key: str, role: str, repetition: str) -> dict[str, Any]:
    spec = PAIR_SPECS[pair_key]
    run_id = f"{pair_key.upper()}-{role.upper()}-RUN-{repetition}"
    run_dir = repo / RESULT_ROOT / str(spec["experiment_id"]) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    mask = signal_mask(repo, role, pair_key, run_dir / "signal-mask.json")
    campaign = backtest_campaign(pair_key, role)
    result = run_offline_backtest(repo, campaign, spec["experiment_id"], run_id, repo / EXCHANGE_SNAPSHOT)
    if result["status"] not in {"accepted", "rejected"}:
        raise RuntimeError(f"backtest_failed:{run_id}:{result}")
    report_path = repo / result["report_path"]
    runner_report = load_document(report_path)
    metrics = load_document(report_path.parent / runner_report["metrics_path"])
    result_path = find_result_json(run_dir)
    normalized = write_normalized_trades(run_dir, result_path, campaign["fixed_backtest"]["strategy"])
    summary = metric_summary(metrics, normalized)
    payload = {
        "schema_version": "router-equivalence-worker-result-v1",
        "run_id": run_id,
        "pid": os.getpid(),
        "pair_key": pair_key,
        "pair": spec["pair"],
        "role": role,
        "repetition": repetition,
        "status": result["status"],
        "strategy": campaign["fixed_backtest"]["strategy"],
        "strategy_source_sha256": mask["strategy_source_sha256"],
        "formal_strategy_sha256": mask["formal_strategy_sha256"],
        "formal_base_sha256": mask["formal_base_sha256"],
        "signal_mask": mask,
        "summary": summary,
        "normalized_trade_hash": normalized["sha256"],
        "normalized_trade_count": normalized["count"],
        "normalized_trades_path": str((run_dir / "normalized-trades.json").relative_to(repo)).replace("\\", "/"),
        "runner_report": result["report_path"],
        "network_attempts": runner_report["network_attempts"],
    }
    write_json(run_dir / "worker-result.json", payload)
    write_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return payload


def run_fresh(repo: Path, pair_key: str, role: str, repetition: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", "--pair", pair_key, "--role", role, "--repetition", repetition],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        timeout=1800,
    )
    log_path = repo / RESULT_ROOT / "launch-logs" / f"{pair_key}-{role}-{repetition}.json"
    write_json(log_path, {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "shell": False})
    if completed.returncode != 0:
        raise RuntimeError(f"fresh_worker_failed:{pair_key}:{role}:{repetition}:{completed.stderr[-2000:]}:{completed.stdout[-2000:]}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def compare_runs(pair_key: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(item["role"], item["repetition"]): item for item in runs}
    comparisons = {}
    differences = []
    fields = ["signal_mask", "summary", "normalized_trade_hash", "normalized_trade_count"]
    for role in ("baseline", "candidate"):
        left, right = by_key[(role, "A")], by_key[(role, "B")]
        diff = {field: {"a": left[field], "b": right[field]} for field in fields if left[field] != right[field]}
        comparisons[f"{role}_run_a_b"] = {"passed": not diff, "differences": diff, "pids": [left["pid"], right["pid"]]}
        if diff:
            differences.append({"comparison": f"{role}_run_a_b", "differences": diff})
    for repetition in ("A", "B"):
        left, right = by_key[("baseline", repetition)], by_key[("candidate", repetition)]
        semantic_fields = ["signal_mask", "summary", "normalized_trade_hash", "normalized_trade_count"]
        diff = {field: {"baseline": left[field], "candidate": right[field]} for field in semantic_fields if left[field] != right[field]}
        comparisons[f"baseline_candidate_run_{repetition.lower()}"] = {"passed": not diff, "differences": diff}
        if diff:
            differences.append({"comparison": f"baseline_candidate_run_{repetition.lower()}", "differences": diff})
    pids = [item["pid"] for item in runs]
    all_unique = len(pids) == len(set(pids))
    if not all_unique:
        differences.append({"comparison": "fresh_process_identity", "pids": pids})
    return {
        "schema_version": "router-extraction-pair-comparison-v1",
        "pair_key": pair_key,
        "pair": PAIR_SPECS[pair_key]["pair"],
        "runs": runs,
        "comparisons": comparisons,
        "distinct_fresh_processes": all_unique,
        "passed": not differences,
        "differences": differences,
    }


def record_registry(repo: Path, final: dict[str, Any], assets: list[str]) -> None:
    approval = load_document(repo / "research/governance/approvals/regime-conditioned-branch-factorization-v1-execution-approval.json")
    authorization = load_document(repo / COMPILED_DIR / "execution-authorization.json")
    proposal = load_document(repo / "research/director/next-after-strategy-family/proposals/regime-conditioned-branch-factorization-v1.json")
    completed_at = utc_now()
    run_id = "regime-conditioned-branch-factorization-v1-run"
    connection = open_director_registry(repo / "research/registry/stage4a-director.db")
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events(proposal_id, proposal_fingerprint, approval_status, approver_type, approved_at, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (PROPOSAL_ID, proposal["semantic_fingerprint"], "approved", "human_user", completed_at, json.dumps(approval, sort_keys=True)),
    )
    connection.execute(
        "INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id, campaign_id, approved_compiled_fingerprint, proposal_id, execution_authorized, payload_json, authorized_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (authorization["authorization_id"], CAMPAIGN_ID, APPROVED_CAMPAIGN_FINGERPRINT, PROPOSAL_ID, 1, json.dumps(authorization, sort_keys=True), completed_at),
    )
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs(run_id, campaign_id, proposal_id, status, result_code, campaign_executed, candidate_created, strategy_modified, validation_accesses, holdout_accesses, payload_json, completed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, CAMPAIGN_ID, PROPOSAL_ID, "completed", final["status"], 1, 1, 0, 0, 0, json.dumps(final, sort_keys=True), completed_at),
    )
    for path in assets:
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets(asset_id, run_id, artifact_type, path, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{run_id}:{path}", run_id, "campaign_evidence", path, sha256_file(repo / path), completed_at),
        )
    connection.commit()
    connection.close()


def write_failure(repo: Path, checks: dict[str, Any], comparisons: dict[str, Any], calls: int, started: float) -> None:
    final = {
        "schema_version": "router-extraction-semantic-equivalence-result-v1",
        "proposal_id": PROPOSAL_ID,
        "campaign_id": CAMPAIGN_ID,
        "research_unit": RESEARCH_UNIT,
        "campaign_fingerprint": APPROVED_CAMPAIGN_FINGERPRINT,
        "status": SemanticMismatch.reason_code,
        "authority_checks": checks,
        "comparisons": comparisons,
        "backtest_calls": calls,
        "wall_clock_seconds": round(time.monotonic() - started, 3),
        "strategy_modified": False,
        "base_modified": False,
        "candidate_count": 1,
        "branch_ablation_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
    write_json(repo / ANALYSIS_ROOT / "semantic-equivalence-result.json", final)
    write_json(repo / COMPILED_DIR / "execution/campaign-execution.json", final)


def run_campaign(repo: Path) -> dict[str, Any]:
    started = time.monotonic()
    checks = validate_authority(repo)
    comparisons: dict[str, Any] = {}
    calls = 0
    all_pids = []
    for pair_key in ("btc", "eth"):
        runs = []
        for role in ("baseline", "candidate"):
            for repetition in ("A", "B"):
                checks = validate_authority(repo)
                result = run_fresh(repo, pair_key, role, repetition)
                calls += 1
                all_pids.append(result["pid"])
                if calls > 8:
                    raise RuntimeError("backtest_budget_exceeded")
                runs.append(result)
        comparison = compare_runs(pair_key, runs)
        comparisons[pair_key] = comparison
        write_json(repo / ANALYSIS_ROOT / f"{pair_key}-semantic-equivalence-comparison.json", comparison)
        if not comparison["passed"]:
            write_failure(repo, checks, comparisons, calls, started)
            raise SemanticMismatch(pair_key)
    if calls != 8 or len(all_pids) != len(set(all_pids)):
        write_failure(repo, checks, comparisons, calls, started)
        raise SemanticMismatch("fresh_process_or_budget_mismatch")
    final = {
        "schema_version": "router-extraction-semantic-equivalence-result-v1",
        "proposal_id": PROPOSAL_ID,
        "campaign_id": CAMPAIGN_ID,
        "research_unit": RESEARCH_UNIT,
        "campaign_fingerprint": APPROVED_CAMPAIGN_FINGERPRINT,
        "status": "router_extraction_semantic_equivalence_verified",
        "authority_checks": checks,
        "pair_results": {key: {"passed": value["passed"], "distinct_fresh_processes": value["distinct_fresh_processes"]} for key, value in comparisons.items()},
        "all_worker_pids_unique": True,
        "worker_pids": all_pids,
        "backtest_calls": calls,
        "budget": {"max_candidates": 1, "max_backtest_calls": 8, "max_wall_clock_minutes": 120},
        "budget_used": {"candidates": 1, "backtest_calls": calls, "wall_clock_seconds": round(time.monotonic() - started, 3)},
        "condition_count": 29,
        "signal_group_count": 5,
        "conditions_changed": 0,
        "thresholds_changed": 0,
        "signal_groups_changed": 0,
        "strategy_modified": False,
        "base_modified": False,
        "candidate_count": 1,
        "branch_ablation_run": False,
        "threshold_research_reopened": False,
        "hyperopt_run": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "automatic_followup_executed": False,
        "comparisons": {
            key: {
                "path": f"research/analysis/regime-conditioned-branch-factorization/{key}-semantic-equivalence-comparison.json",
                "normalized_trade_hash": value["runs"][0]["normalized_trade_hash"],
                "signal_mask_hash": value["runs"][0]["signal_mask"]["rows_sha256"],
                "total_trades": value["runs"][0]["summary"]["core"]["total_trades"],
                "long_trades": value["runs"][0]["summary"]["core"]["long_trade_count"],
                "short_trades": value["runs"][0]["summary"]["core"]["short_trade_count"],
            }
            for key, value in comparisons.items()
        },
    }
    analysis_path = ANALYSIS_ROOT / "semantic-equivalence-result.json"
    execution_path = Path(COMPILED_DIR) / "execution/campaign-execution.json"
    report_json = REPORT_ROOT / "router-extraction-semantic-equivalence-final-report.json"
    report_md = REPORT_ROOT / "router-extraction-semantic-equivalence-final-report.md"
    for path in (analysis_path, execution_path, report_json):
        write_json(repo / path, final)
    markdown = f"""# Router Extraction Semantic Equivalence Final Report

- Status: `router_extraction_semantic_equivalence_verified`
- Campaign fingerprint: `{APPROVED_CAMPAIGN_FINGERPRINT}`
- Candidate count: `1`
- Backtest calls: `8`
- BTC: `passed`
- ETH: `passed`
- All worker PIDs unique: `true`
- Conditions / signal groups changed: `0 / 0`
- Formal strategy/base modified: `false / false`
- Validation/Holdout: `0 / 0`
- Branch contribution ablation: `not_run`

The isolated router interface is semantically equivalent on both approved development pairs. The formal strategy remains the execution baseline.
"""
    (repo / report_md).parent.mkdir(parents=True, exist_ok=True)
    (repo / report_md).write_text(markdown, encoding="utf-8")
    assets = [
        CANDIDATE_MANIFEST,
        CANDIDATE_SOURCE,
        analysis_path.as_posix(),
        f"{ANALYSIS_ROOT.as_posix()}/btc-semantic-equivalence-comparison.json",
        f"{ANALYSIS_ROOT.as_posix()}/eth-semantic-equivalence-comparison.json",
        execution_path.as_posix(),
        report_json.as_posix(),
        report_md.as_posix(),
    ]
    record_registry(repo, final, assets)
    return final


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--pair", choices=sorted(PAIR_SPECS))
    parser.add_argument("--role", choices=["baseline", "candidate"])
    parser.add_argument("--repetition", choices=["A", "B"])
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    if args.worker:
        if not args.pair or not args.role or not args.repetition:
            parser.error("--worker requires --pair, --role and --repetition")
        result = worker(repo, args.pair, args.role, args.repetition)
        print(json.dumps(result, sort_keys=True))
        return 0
    try:
        result = run_campaign(repo)
    except SemanticMismatch as exc:
        print(json.dumps({"status": SemanticMismatch.reason_code, "detail": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
