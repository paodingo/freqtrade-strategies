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
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from protected_manifest_hash import canonical_text_sha256, validate_protected_manifests
from research_director_common import fingerprint, load_document, open_director_registry, sha256_file, utc_now, write_json, write_yaml
from backtest_execution_namespace import (
    NamespaceContractError,
    assert_tree_unchanged,
    create_execution_namespace,
    tree_inventory,
    tree_inventory_excluding,
    validate_report_bindings,
    validate_trade_counts,
)
from windows_execution_paths import build_execution_manifest as build_short_execution_manifest
from run_experiment import artifact_hashes
from run_offline_backtest import run_offline_backtest
from run_stage3a5_acceptance import locate_trades, metric_summary, normalize_trades


PROPOSAL_ID = "regime-conditioned-branch-factorization-v1"
CAMPAIGN_ID = "stage4a-regime-conditioned-branch-factorization-v1"
RESEARCH_UNIT = "router-extraction-semantic-equivalence-v1"
APPROVED_CAMPAIGN_FINGERPRINT = "5f759a309a23e684bbd3277a3aff1de3b075c01ddd22e2d3f67e57e00c7c8fe3"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
BASE_SHA256 = "8feaebff14b5e8c537ec310b44b2b1d448db20be1388e3aca51da15b306275f9"
CANDIDATE_SHA256 = "bee68e27b345a93a1fe8481275e365829c986f700d2719fdd10ffd907e1dffa1"
CANDIDATE_SOURCE = "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"
CANDIDATE_MANIFEST = "research/candidates/regime-conditioned-branch-factorization-v1/candidate-manifest.json"
COMPILED_DIR = "research/director/compiled/regime-conditioned-branch-factorization-v1"
COMPARISON_CONTRACT = "research/governance/signal-mask-comparison-contract.yaml"
RECERTIFICATION_ATTEMPT = "recertification-attempt-3"
CAMPAIGN_PATH_ID = "regime-branch-factorization-v1"
RESEARCH_UNIT_PATH_ID = "router-equivalence-v1"
RESULT_ROOT = Path("research/results") / CAMPAIGN_PATH_ID / RESEARCH_UNIT_PATH_ID / RECERTIFICATION_ATTEMPT
ANALYSIS_ROOT = Path("research/analysis/regime-conditioned-branch-factorization")
REPORT_ROOT = Path("reports/audits/regime-conditioned-branch-factorization")
EXCHANGE_SNAPSHOT = Path("research/exchange_snapshots/binance-usdm-futures-2025-8-demo")
CONTAMINATED_ROOTS = (
    Path("research/results") / CAMPAIGN_ID / "2",
    Path("research/results") / CAMPAIGN_ID / "3",
)
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
SHORT_NAMESPACE_FACTORY = None


class SemanticMismatch(RuntimeError):
    reason_code = "router_extraction_semantic_mismatch"


class ComparatorContractViolation(RuntimeError):
    reason_code = "signal_mask_comparator_contract_violation"


class RuntimeIdentityFailure(RuntimeError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(detail)
        self.reason_code = reason_code


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


SEMANTIC_FIELDS = ("pair", "row_count", "signal_counts", "rows_sha256")
IDENTITY_FIELDS = (
    "role",
    "strategy_class",
    "module_name",
    "module_path",
    "source_path",
    "source_sha256",
    "dependency_path",
    "dependency_sha256",
    "pid",
    "execution_run_id",
    "runtime_versions",
    "experiment_id",
)


def signal_semantic_projection(mask: dict[str, Any]) -> dict[str, Any]:
    source = mask.get("signal_semantic_projection") or mask
    missing = [field for field in SEMANTIC_FIELDS if field not in source]
    if missing:
        raise ComparatorContractViolation("missing semantic fields: " + ",".join(missing))
    projection = {"schema_version": "signal_semantic_projection_v1"}
    projection.update({field: source[field] for field in SEMANTIC_FIELDS})
    projection["semantic_sha256"] = canonical_hash({field: projection[field] for field in ("schema_version", *SEMANTIC_FIELDS)})
    known = {"schema_version", "semantic_sha256", *SEMANTIC_FIELDS}
    projection["excluded_unknown_fields"] = sorted(set(source) - known)
    return projection


def signal_semantic_projection_from_rows(pair: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    row_fields = ("date", "enter_long", "enter_short", "exit_long", "exit_short", "enter_tag", "exit_tag")
    normalized = [{field: row.get(field) for field in row_fields} for row in rows]
    counts = {
        field: sum(int(row.get(field) or 0) for row in normalized)
        for field in ("enter_long", "enter_short", "exit_long", "exit_short")
    }
    semantic = {
        "schema_version": "signal_semantic_projection_v1",
        "pair": pair,
        "row_count": len(normalized),
        "signal_counts": counts,
        "rows_sha256": canonical_hash(normalized),
    }
    semantic["semantic_sha256"] = canonical_hash({field: semantic[field] for field in ("schema_version", *SEMANTIC_FIELDS)})
    return semantic


def runtime_identity_projection(run: dict[str, Any]) -> dict[str, Any]:
    recorded = run.get("runtime_identity_projection") or {}
    mask = run.get("signal_mask") or {}
    legacy = {
        "role": run.get("role") or mask.get("role"),
        "strategy_class": run.get("strategy") or mask.get("strategy_class"),
        "module_name": mask.get("strategy_module"),
        "module_path": mask.get("strategy_module_path"),
        "source_path": run.get("strategy_source_path") or mask.get("strategy_module_path"),
        "source_sha256": run.get("strategy_source_sha256") or mask.get("strategy_source_sha256"),
        "dependency_path": run.get("dependency_path") or "strategies/regime_aware_base.py",
        "dependency_sha256": run.get("formal_base_sha256") or mask.get("formal_base_sha256"),
        "pid": run.get("pid"),
        "execution_run_id": run.get("run_id"),
        "runtime_versions": run.get("runtime_versions") or {},
        "experiment_id": run.get("experiment_id") or PAIR_SPECS.get(run.get("pair_key"), {}).get("experiment_id"),
    }
    values = {field: recorded.get(field, legacy.get(field)) for field in IDENTITY_FIELDS}
    missing = [field for field, value in values.items() if value is None]
    if missing:
        raise ComparatorContractViolation("missing runtime identity fields: " + ",".join(missing))
    return {"schema_version": "runtime_identity_projection_v1", **values}


def compare_signal_semantics(first_mask: dict[str, Any], second_mask: dict[str, Any]) -> dict[str, Any]:
    first = signal_semantic_projection(first_mask)
    second = signal_semantic_projection(second_mask)
    differences = {
        field: {"first": first[field], "second": second[field]}
        for field in SEMANTIC_FIELDS
        if first[field] != second[field]
    }
    return {
        "schema_version": "signal-semantic-comparison-v1",
        "passed": not differences,
        "first": first,
        "second": second,
        "differences": differences,
    }


def audit_runtime_identity(first_run: dict[str, Any], second_run: dict[str, Any], expected_role: str) -> dict[str, Any]:
    first = runtime_identity_projection(first_run)
    second = runtime_identity_projection(second_run)
    if first["role"] != expected_role or second["role"] != expected_role:
        raise RuntimeIdentityFailure("runtime_candidate_identity_mismatch", "role does not match expected identity")
    same_fields = ("strategy_class", "module_name", "module_path", "source_path", "source_sha256", "dependency_path", "dependency_sha256", "runtime_versions")
    differences = {field: {"run_a": first[field], "run_b": second[field]} for field in same_fields if first[field] != second[field]}
    if differences:
        reason = "runtime_dependency_identity_mismatch" if any(field.startswith("dependency") for field in differences) else "runtime_identity_reproducibility_mismatch"
        raise RuntimeIdentityFailure(reason, json.dumps(differences, sort_keys=True))
    if first["pid"] == second["pid"]:
        raise RuntimeIdentityFailure("runtime_identity_reproducibility_mismatch", "fresh processes reused a PID")
    expected_source_path = "strategies/RegimeAwareV6.py" if expected_role == "baseline" else CANDIDATE_SOURCE
    expected_source_sha256 = STRATEGY_SHA256 if expected_role == "baseline" else CANDIDATE_SHA256
    for identity in (first, second):
        if identity["source_path"] != expected_source_path or identity["source_sha256"] != expected_source_sha256:
            raise RuntimeIdentityFailure("runtime_candidate_identity_mismatch", "loaded source path/hash differs from approved identity")
        if identity["dependency_path"] != "strategies/regime_aware_base.py" or identity["dependency_sha256"] != BASE_SHA256:
            raise RuntimeIdentityFailure("runtime_dependency_identity_mismatch", "loaded dependency path/hash differs from approved identity")
    return {"schema_version": "runtime-identity-audit-v1", "passed": True, "run_a": first, "run_b": second, "differences": {}}


def audit_cross_role_identity(baseline_run: dict[str, Any], candidate_run: dict[str, Any]) -> dict[str, Any]:
    baseline = runtime_identity_projection(baseline_run)
    candidate = runtime_identity_projection(candidate_run)
    expected_different = ("role", "strategy_class", "module_name", "module_path", "source_path", "source_sha256")
    missing_differences = [field for field in expected_different if baseline[field] == candidate[field]]
    if missing_differences:
        raise RuntimeIdentityFailure("runtime_candidate_identity_mismatch", "expected cross-role identity differences missing: " + ",".join(missing_differences))
    if baseline["dependency_path"] != candidate["dependency_path"] or baseline["dependency_sha256"] != candidate["dependency_sha256"]:
        raise RuntimeIdentityFailure("runtime_dependency_identity_mismatch", "cross-role dependency identity differs")
    return {
        "schema_version": "cross-role-runtime-identity-audit-v1",
        "passed": True,
        "baseline": baseline,
        "candidate": candidate,
        "expected_differences": {field: {"baseline": baseline[field], "candidate": candidate[field]} for field in expected_different},
        "shared_dependency": {"path": baseline["dependency_path"], "sha256": baseline["dependency_sha256"]},
    }


def validate_authority(repo: Path) -> dict[str, Any]:
    campaign = load_document(repo / COMPILED_DIR / "campaign.yaml")
    approval = load_document(repo / "research/governance/approvals/regime-conditioned-branch-factorization-v1-execution-approval.json")
    authorization = load_document(repo / COMPILED_DIR / "execution-authorization.json")
    candidate = load_document(repo / CANDIDATE_MANIFEST)
    comparison_contract = load_document(repo / COMPARISON_CONTRACT)
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
        "comparison_contract": comparison_contract["signal_semantic_projection"]["scheme_id"] == "signal_semantic_projection_v1" and comparison_contract["runtime_identity_projection"]["scheme_id"] == "runtime_identity_projection_v1",
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


def signal_mask(repo: Path, role: str, pair_key: str, run_id: str, output: Path) -> dict[str, Any]:
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
    semantic = signal_semantic_projection_from_rows(spec["pair"], rows)
    import ccxt
    import freqtrade
    identity = {
        "schema_version": "runtime_identity_projection_v1",
        "role": role,
        "strategy_class": strategy_class.__name__,
        "module_name": module.__name__,
        "module_path": str(Path(module.__file__ or "").resolve()),
        "source_path": str(source.relative_to(repo)).replace("\\", "/"),
        "source_sha256": sha256_file(source),
        "dependency_path": "strategies/regime_aware_base.py",
        "dependency_sha256": sha256_file(repo / "strategies/regime_aware_base.py"),
        "pid": os.getpid(),
        "execution_run_id": run_id,
        "runtime_versions": {"python": sys.version.split()[0], "freqtrade": freqtrade.__version__, "ccxt": ccxt.__version__},
        "experiment_id": spec["experiment_id"],
    }
    payload = {
        "schema_version": "router-equivalence-signal-mask-v1",
        "signal_semantic_projection": semantic,
        "runtime_identity_projection": identity,
        "formal_strategy_sha256": sha256_file(repo / "strategies/RegimeAwareV6.py"),
        "formal_base_sha256": sha256_file(repo / "strategies/regime_aware_base.py"),
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


def worker(repo: Path, pair_key: str, role: str, repetition: str, execution_id: str) -> dict[str, Any]:
    spec = PAIR_SPECS[pair_key]
    run_id = f"{pair_key.upper()}-{role.upper()}-RUN-{repetition}"
    pair_id = spec["pair"].lower().replace("/", "-").replace(":", "-")
    namespace_fields = {
        "campaign_id": CAMPAIGN_ID,
        "proposal_id": PROPOSAL_ID,
        "research_unit": RESEARCH_UNIT,
        "attempt_id": RECERTIFICATION_ATTEMPT,
        "pair_id": pair_id,
        "role": role,
        "repetition": f"run-{repetition.lower()}",
        "execution_id": execution_id,
        "campaign_path_id": CAMPAIGN_PATH_ID,
        "research_unit_path_id": RESEARCH_UNIT_PATH_ID,
    }
    expected_archive = f"backtest-result-{execution_id}.zip"
    expected_result = f"backtest-result-{execution_id}.json"
    paths = {
        "execution_manifest": "execution-manifest.json",
        "output_root_audit": "output-root-audit.json",
        "runner_report": "runner-report.json",
        "raw_result": expected_result,
        "metrics": "metrics.json",
        "normalized_trades": "normalized-trades.json",
        "runtime_identity": "runtime-identity.json",
        "signal_mask": "signal-mask.json",
        "worker_result": "worker-result.json",
        "filesystem_write_audit": "filesystem-write-audit.json",
    }
    attempt_root = repo / RESULT_ROOT
    contaminated_before = {path.as_posix(): tree_inventory(repo / path) for path in CONTAMINATED_ROOTS}
    short_context = None
    if SHORT_NAMESPACE_FACTORY is None:
        run_dir, output_audit = create_execution_namespace(repo, attempt_root, namespace_fields)
    else:
        short_context = SHORT_NAMESPACE_FACTORY(repo, pair_key, role, repetition, execution_id)
        short_plan = short_context["plan"]
        run_dir = repo / short_plan["namespace"]
        output_audit = {
            "schema_version": "backtest-output-root-audit-v2",
            "validation_verdict": "approved",
            "repo_relative_path": short_plan["namespace"],
            "namespace_fields": namespace_fields,
            "short_namespace_mapping": short_plan["aliases"],
            "execution_short_id": short_plan["execution_short_id"],
            "path_budget": short_plan["path_budget"],
        }
        short_paths = short_plan["path_budget"]["relative_outputs"]
        paths.update(
            {
                "execution_manifest": short_paths["execution_manifest"],
                "output_root_audit": short_paths["output_root_audit"],
                "runner_report": short_paths["runner_report"],
                "raw_result": short_paths["raw_result"],
                "metrics": short_paths["metrics"],
                "normalized_trades": short_paths["normalized_trades"],
                "runtime_identity": short_paths["runtime_identity"],
                "signal_mask": short_paths["signal_masks"],
                "worker_result": short_paths["worker_result"],
                "filesystem_write_audit": short_paths["filesystem_write_audit"],
            }
        )
        expected_archive = short_paths["raw_result_archive"]
        expected_result = short_paths["raw_result"]
        attempt_root = repo / short_plan["attempt_root"]
    sibling_before = tree_inventory_excluding(attempt_root, [run_dir])
    started_ns = time.time_ns()
    strategy = "RegimeAwareV6" if role == "baseline" else "RegimeAwareRouterEquivalentV1"
    strategy_hash = STRATEGY_SHA256 if role == "baseline" else CANDIDATE_SHA256
    execution_manifest = {
        "schema_version": "router-equivalence-execution-manifest-v1",
        **namespace_fields,
        "pair": spec["pair"],
        "strategy": strategy,
        "strategy_source_sha256": strategy_hash,
        "output_root": run_dir.relative_to(repo).as_posix(),
        "expected_raw_archive_filename": expected_archive,
        "expected_raw_result_filename": expected_result,
        "expected_paths": paths,
        "started_at_epoch_ns": started_ns,
    }
    if short_context is not None:
        execution_manifest["full_identity"] = {**short_context["full_identity"], "execution_id": execution_id}
        execution_manifest["short_namespace_mapping"] = {
            **short_context["plan"]["aliases"],
            "execution_short_id": short_context["plan"]["execution_short_id"],
            "namespace": short_context["plan"]["namespace"],
            "alias_registry": short_context["plan"]["alias_registry"],
        }
        execution_manifest["path_budget"] = short_context["plan"]["path_budget"]
    write_json(run_dir / paths["output_root_audit"], output_audit)
    write_json(run_dir / paths["execution_manifest"], execution_manifest)
    mask = signal_mask(repo, role, pair_key, run_id, run_dir / paths["signal_mask"])
    write_json(run_dir / paths["runtime_identity"], mask["runtime_identity_projection"])
    campaign = backtest_campaign(pair_key, role)
    execution_context = {
        **namespace_fields,
        "started_ns": started_ns,
        "expected_output_root": run_dir.relative_to(repo).as_posix(),
        "expected_raw_archive_filename": expected_archive,
        "expected_raw_result_filename": expected_result,
    }
    result = run_offline_backtest(
        repo,
        campaign,
        spec["experiment_id"],
        execution_id,
        repo / EXCHANGE_SNAPSHOT,
        output_root=run_dir,
        execution_context=execution_context,
    )
    if result["status"] not in {"accepted", "rejected"}:
        raise RuntimeError(f"backtest_failed:{run_id}:{result}")
    report_path = repo / result["report_path"]
    runner_report = load_document(report_path)
    if runner_report.get("attempt_id") != RECERTIFICATION_ATTEMPT or runner_report.get("execution_id") != execution_id:
        raise NamespaceContractError("stale_runner_report_reference", run_id)
    if report_path.parent.resolve() != run_dir.resolve():
        raise NamespaceContractError("stale_runner_report_reference", "runner report is outside current execution")
    metrics = load_document(report_path.parent / runner_report["metrics_path"])
    result_path = run_dir / runner_report["raw_result_path"]
    raw_payload = load_document(result_path)
    raw_trade_count = len(locate_trades(raw_payload, strategy))
    normalized = normalize_trades(result_path, strategy)
    runner_trade_count = int(metrics["normalized"]["total_trades"])
    validate_trade_counts(raw_trade_count, normalized["count"], runner_trade_count)
    normalized_payload = {
        "schema_version": normalized["schema_version"],
        "parser_version": "normalized-trades-v1",
        "attempt_id": RECERTIFICATION_ATTEMPT,
        "execution_id": execution_id,
        "raw_result_path": result_path.relative_to(repo).as_posix(),
        "raw_result_sha256": sha256_file(result_path),
        "raw_trade_count": raw_trade_count,
        "normalized_trade_count": normalized["count"],
        "runner_total_trade_count": runner_trade_count,
        "normalized_trade_hash": normalized["sha256"],
        "rows": normalized["rows"],
    }
    write_json(run_dir / paths["normalized_trades"], normalized_payload)
    summary = metric_summary(metrics, normalized)
    runner_report.update(
        {
            "attempt_id": RECERTIFICATION_ATTEMPT,
            "execution_id": execution_id,
            "output_root": run_dir.relative_to(repo).as_posix(),
            "raw_result_path": result_path.name,
            "metrics_path": paths["metrics"],
            "normalized_trades_path": paths["normalized_trades"],
            "runtime_identity_path": paths["runtime_identity"],
            "signal_mask_path": paths["signal_mask"],
            "raw_result_sha256": sha256_file(result_path),
            "normalized_trades_sha256": sha256_file(run_dir / paths["normalized_trades"]),
            "runtime_identity_sha256": sha256_file(run_dir / paths["runtime_identity"]),
            "signal_mask_sha256": sha256_file(run_dir / paths["signal_mask"]),
        }
    )
    write_json(report_path, runner_report)
    report_binding_audit = validate_report_bindings(runner_report, run_dir, RECERTIFICATION_ATTEMPT, execution_id)
    write_json(run_dir / "runner-report-binding-audit.json", report_binding_audit)
    payload = {
        "schema_version": "router-equivalence-worker-result-v1",
        "run_id": run_id,
        "attempt_id": RECERTIFICATION_ATTEMPT,
        "execution_id": execution_id,
        "output_root": run_dir.relative_to(repo).as_posix(),
        "pid": os.getpid(),
        "pair_key": pair_key,
        "pair": spec["pair"],
        "role": role,
        "repetition": repetition,
        "status": result["status"],
        "strategy": campaign["fixed_backtest"]["strategy"],
        "strategy_source_path": mask["runtime_identity_projection"]["source_path"],
        "strategy_source_sha256": mask["runtime_identity_projection"]["source_sha256"],
        "formal_strategy_sha256": mask["formal_strategy_sha256"],
        "formal_base_sha256": mask["formal_base_sha256"],
        "dependency_path": mask["runtime_identity_projection"]["dependency_path"],
        "runtime_versions": mask["runtime_identity_projection"]["runtime_versions"],
        "experiment_id": spec["experiment_id"],
        "runtime_identity_projection": mask["runtime_identity_projection"],
        "signal_mask": mask,
        "summary": summary,
        "normalized_trade_hash": normalized["sha256"],
        "normalized_trade_count": normalized["count"],
        "raw_result_path": result_path.relative_to(repo).as_posix(),
        "raw_result_sha256": sha256_file(result_path),
        "metrics_path": (run_dir / paths["metrics"]).relative_to(repo).as_posix(),
        "normalized_trades_path": (run_dir / paths["normalized_trades"]).relative_to(repo).as_posix(),
        "runtime_identity_path": (run_dir / paths["runtime_identity"]).relative_to(repo).as_posix(),
        "signal_mask_path": (run_dir / paths["signal_mask"]).relative_to(repo).as_posix(),
        "runner_report": result["report_path"],
        "network_attempts": runner_report["network_attempts"],
    }
    write_json(run_dir / paths["worker_result"], payload)
    contaminated_after = {path.as_posix(): tree_inventory(repo / path) for path in CONTAMINATED_ROOTS}
    for key in contaminated_before:
        assert_tree_unchanged(contaminated_before[key], contaminated_after[key])
    sibling_after = tree_inventory_excluding(attempt_root, [run_dir])
    assert_tree_unchanged(sibling_before, sibling_after)
    filesystem_audit = {
        "schema_version": "backtest-filesystem-write-audit-v1",
        "attempt_id": RECERTIFICATION_ATTEMPT,
        "execution_id": execution_id,
        "current_execution_root": run_dir.relative_to(repo).as_posix(),
        "current_execution_only_write": True,
        "contaminated_roots_before": contaminated_before,
        "contaminated_roots_after": contaminated_after,
        "other_execution_roots_before": sibling_before,
        "other_execution_roots_after": sibling_after,
        "formal_strategy_sha256": sha256_file(repo / "strategies/RegimeAwareV6.py"),
        "formal_base_sha256": sha256_file(repo / "strategies/regime_aware_base.py"),
        "candidate_sha256": sha256_file(repo / CANDIDATE_SOURCE),
        "verdict": "passed",
    }
    write_json(run_dir / paths["filesystem_write_audit"], filesystem_audit)
    if short_context is not None:
        bound_manifest = build_short_execution_manifest(repo, short_context["plan"], short_context["full_identity"])
        bound_manifest["execution_projection"] = execution_manifest
        write_json(run_dir / paths["execution_manifest"], bound_manifest)
    write_json(run_dir / "artifact-hashes.json", artifact_hashes(run_dir))
    return payload


def run_fresh(repo: Path, pair_key: str, role: str, repetition: str) -> dict[str, Any]:
    execution_id = uuid.uuid4().hex[:12]
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", "--pair", pair_key, "--role", role, "--repetition", repetition, "--execution-id", execution_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        timeout=1800,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"fresh_worker_failed:{pair_key}:{role}:{repetition}:{completed.stderr[-2000:]}:{completed.stdout[-2000:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    run_dir = repo / payload["output_root"]
    write_json(run_dir / "worker-launch.json", {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "shell": False, "execution_id": execution_id})
    return payload


def compare_runs(pair_key: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(item["role"], item["repetition"]): item for item in runs}
    comparisons = {}
    differences = []
    for role in ("baseline", "candidate"):
        left, right = by_key[(role, "A")], by_key[(role, "B")]
        semantic = compare_signal_semantics(left["signal_mask"], right["signal_mask"])
        identity = audit_runtime_identity(left, right, role)
        diff = {
            field: {"a": left[field], "b": right[field]}
            for field in ("summary", "normalized_trade_hash", "normalized_trade_count")
            if left[field] != right[field]
        }
        if not semantic["passed"]:
            diff["signal_semantics"] = semantic["differences"]
        comparisons[f"{role}_run_a_b"] = {
            "passed": not diff,
            "semantic_comparison": semantic,
            "runtime_identity_audit": identity,
            "differences": diff,
            "pids": [left["pid"], right["pid"]],
        }
        if diff:
            differences.append({"comparison": f"{role}_run_a_b", "differences": diff})
    for repetition in ("A", "B"):
        left, right = by_key[("baseline", repetition)], by_key[("candidate", repetition)]
        semantic = compare_signal_semantics(left["signal_mask"], right["signal_mask"])
        identity = audit_cross_role_identity(left, right)
        diff = {
            field: {"baseline": left[field], "candidate": right[field]}
            for field in ("summary", "normalized_trade_hash", "normalized_trade_count")
            if left[field] != right[field]
        }
        if not semantic["passed"]:
            diff["signal_semantics"] = semantic["differences"]
        comparisons[f"baseline_candidate_run_{repetition.lower()}"] = {
            "passed": not diff,
            "semantic_comparison": semantic,
            "runtime_identity_audit": identity,
            "differences": diff,
        }
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
        "comparison_contract": COMPARISON_CONTRACT,
        "semantic_projection_scheme": "signal_semantic_projection_v1",
        "runtime_identity_projection_scheme": "runtime_identity_projection_v1",
        "distinct_fresh_processes": all_unique,
        "passed": not differences,
        "differences": differences,
    }


def record_registry(repo: Path, final: dict[str, Any], assets: list[str]) -> None:
    approval = load_document(repo / "research/governance/approvals/regime-conditioned-branch-factorization-v1-execution-approval.json")
    authorization = load_document(repo / COMPILED_DIR / "execution-authorization.json")
    proposal = load_document(repo / "research/director/next-after-strategy-family/proposals/regime-conditioned-branch-factorization-v1.json")
    completed_at = utc_now()
    run_id = "regime-conditioned-branch-factorization-v1-recertification-attempt-3"
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
        "attempt_id": RECERTIFICATION_ATTEMPT,
        "execution_harness": {"comparison_contract": COMPARISON_CONTRACT, "comparison_contract_sha256": sha256_file(repo / COMPARISON_CONTRACT)},
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
    write_json(repo / ANALYSIS_ROOT / "recertification-attempt-3-semantic-equivalence-result.json", final)
    write_json(repo / COMPILED_DIR / "execution/recertification-attempt-3-campaign-execution.json", final)


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
        write_json(repo / ANALYSIS_ROOT / f"recertification-attempt-3-{pair_key}-semantic-equivalence-comparison.json", comparison)
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
        "attempt_id": RECERTIFICATION_ATTEMPT,
        "execution_harness": {"comparison_contract": COMPARISON_CONTRACT, "comparison_contract_sha256": sha256_file(repo / COMPARISON_CONTRACT)},
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
                "path": f"research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-{key}-semantic-equivalence-comparison.json",
                "normalized_trade_hash": value["runs"][0]["normalized_trade_hash"],
                "signal_mask_hash": signal_semantic_projection(value["runs"][0]["signal_mask"])["semantic_sha256"],
                "total_trades": value["runs"][0]["summary"]["core"]["total_trades"],
                "long_trades": value["runs"][0]["summary"]["core"]["long_trade_count"],
                "short_trades": value["runs"][0]["summary"]["core"]["short_trade_count"],
            }
            for key, value in comparisons.items()
        },
    }
    analysis_path = ANALYSIS_ROOT / "recertification-attempt-3-semantic-equivalence-result.json"
    execution_path = Path(COMPILED_DIR) / "execution/recertification-attempt-3-campaign-execution.json"
    report_json = REPORT_ROOT / "router-extraction-semantic-equivalence-recertification-attempt-3-final-report.json"
    report_md = REPORT_ROOT / "router-extraction-semantic-equivalence-recertification-attempt-3-final-report.md"
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
        f"{ANALYSIS_ROOT.as_posix()}/recertification-attempt-3-btc-semantic-equivalence-comparison.json",
        f"{ANALYSIS_ROOT.as_posix()}/recertification-attempt-3-eth-semantic-equivalence-comparison.json",
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
    parser.add_argument("--execution-id")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    if args.worker:
        if not args.pair or not args.role or not args.repetition or not args.execution_id:
            parser.error("--worker requires --pair, --role, --repetition and --execution-id")
        result = worker(repo, args.pair, args.role, args.repetition, args.execution_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    try:
        result = run_campaign(repo)
    except SemanticMismatch as exc:
        print(json.dumps({"status": SemanticMismatch.reason_code, "detail": str(exc)}, indent=2))
        return 2
    except ComparatorContractViolation as exc:
        print(json.dumps({"status": ComparatorContractViolation.reason_code, "detail": str(exc)}, indent=2))
        return 3
    except RuntimeIdentityFailure as exc:
        print(json.dumps({"status": exc.reason_code, "detail": str(exc)}, indent=2))
        return 4
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
