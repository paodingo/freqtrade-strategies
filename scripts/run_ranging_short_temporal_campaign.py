#!/usr/bin/env python3
"""Execute the approved frozen ranging-short temporal contribution review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import run_branch_contribution_ablation_campaign as branch
import run_router_extraction_semantic_equivalence_campaign as harness
from compile_ranging_short_temporal_campaign import compile_temporal_campaign
from export_director_registry import export_registry
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
from portable_baseline_fixtures import verify as verify_portable_fixture_pack
from portable_runtime_assets import PortableRuntimeError, verify_runtime_files
from run_stage3a5_acceptance import locate_trades
from windows_execution_paths import create_execution_namespace as create_short_execution_namespace
from windows_execution_paths import load_contract as load_path_budget_contract
from windows_execution_paths import plan_execution as plan_short_namespace


PROPOSAL_ID = "ranging-short-branch-decision-review-v1"
CAMPAIGN_ID = "stage4a-ranging-short-branch-decision-review-v1-temporal-v2"
RESEARCH_UNIT = "ranging_short_entry"
ATTEMPT_THREE_ID = "temporal-ablation-execution-attempt-3"
ATTEMPT_ID = ATTEMPT_THREE_ID
ORIGINAL_ATTEMPT_ID = "temporal-branch-contribution-review-v1"
RUN_ID = "ranging-short-temporal-review-v1-attempt-3"
PROPOSAL_FINGERPRINT = "e5b01ecdfc922b06a20e8e0c1eb901fd363563da23d246819cfa8e268247c0c3"
CAMPAIGN_FINGERPRINT = "ce25aae5d98b52f57e5fa793e2d1259022a803ad08c394bf793d67e52ab3b2f1"
SLICE_POLICY_FINGERPRINT = "bdd0944e67f62a5fd6b70b1d66fc2c373ee8ecd42d3a84ea410f6337612856d4"
COMPILED_DIR = Path("research/director/compiled/ranging-short-branch-decision-review-v1-temporal-v2")
CAMPAIGN_PATH = COMPILED_DIR / "campaign.yaml"
QUEUE_PATH = COMPILED_DIR / "experiment-queue.json"
AUTHORIZATION_PATH = COMPILED_DIR / "execution-authorization.json"
APPROVAL_PATH = Path("research/governance/approvals/ranging-short-branch-decision-review-v1-temporal-execution-approval.json")
ATTEMPT_REQUEST_PATH = Path("research/governance/approvals/ranging-short-branch-decision-review-v1-temporal-attempt-3-request.json")
ATTEMPT_APPROVAL_PATH = Path("research/governance/approvals/ranging-short-branch-decision-review-v1-temporal-attempt-3-approval.json")
SLICE_POLICY_PATH = Path("research/temporal/ranging-short-ablation-temporal-slices-v1.yaml")
PROPOSAL_PATH = Path("research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json")
RESULT_ROOT = Path("research/results/ranging-short-temporal-review-v1")
ANALYSIS_ROOT = Path("research/analysis/ranging-short-temporal-review-v1")
REPORT_ROOT = Path("reports/audits/ranging-short-temporal-review-v1")
NEXT_ROOT = Path("research/director/next-after-ranging-short-temporal/proposals")
STATE_PATH = Path("research/director/current-research-state.json")
REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
DATA_ROOT = Path("research/data/snapshots") / DATASET_ID / "data/futures"
PAIR = "BTC/USDT:USDT"
PREFIX = "BTC_USDT_USDT"
MAX_BACKTEST_CALLS = 16
MAX_WALL_CLOCK_SECONDS = 240 * 60
SLICE_IDS = tuple(f"ranging-short-ablation-s0{number}" for number in range(1, 5))
LOCAL_LEVERAGE_TIER_PATH = Path(".venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json")
RUNTIME_ASSET_MANIFEST_FINGERPRINT = "fa9bb13132dad44344e91d262c5fd38473e2cbed7a930e72f677eb7a0ce11f64"
PATH_BUDGET_CONTRACT_FINGERPRINT = "b7d580480bf828117461e18dc34dd592726839f862655eed1e6ea443b12e21d6"


class TemporalExecutionInvalid(RuntimeError):
    reason_code = "temporal_ablation_execution_invalid"


def canonical_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def slice_map(repo: Path) -> dict[str, dict[str, Any]]:
    policy = load_document(repo / SLICE_POLICY_PATH)
    return {item["slice_id"]: item for item in policy["slices"]}


def _runtime_root() -> Path:
    return Path(sys.executable).resolve().parents[2]


def _campaign_fingerprint(campaign: dict[str, Any]) -> str:
    return fingerprint({key: value for key, value in campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})


def require_portable_runtime(repo: Path) -> dict[str, Any]:
    try:
        return verify_runtime_files(repo)
    except PortableRuntimeError as exc:
        raise TemporalExecutionInvalid(f"portable_runtime_preflight_failed:{exc}") from exc


def validate_authority(repo: Path) -> dict[str, Any]:
    runtime_assets = require_portable_runtime(repo)
    campaign = load_document(repo / CAMPAIGN_PATH)
    policy = load_document(repo / SLICE_POLICY_PATH)
    proposal = load_document(repo / PROPOSAL_PATH)
    approval = load_document(repo / APPROVAL_PATH)
    attempt_request = load_document(repo / ATTEMPT_REQUEST_PATH)
    attempt_approval = load_document(repo / ATTEMPT_APPROVAL_PATH)
    path_budget_contract = load_path_budget_contract(repo)
    authorization = load_document(repo / AUTHORIZATION_PATH)
    queue = json.loads((repo / QUEUE_PATH).read_text(encoding="utf-8-sig"))
    candidate = load_document(repo / branch.CANDIDATE_MANIFEST)
    replay_campaign, replay_policy, _ = compile_temporal_campaign(repo, repo, _runtime_root())
    expected_order = [
        (slice_id, role, repetition)
        for slice_id in (f"ranging-short-ablation-s0{number}" for number in range(1, 5))
        for role in ("baseline", "candidate")
        for repetition in ("RUN-A", "RUN-B")
    ]
    actual_order = [(item["slice_id"], item["role"], item["repetition"]) for item in queue]
    checks: dict[str, Any] = {
        "proposal_fingerprint": proposal_fingerprint(proposal) == proposal.get("semantic_fingerprint") == approval["proposal_fingerprint"] == authorization["proposal_fingerprint"] == PROPOSAL_FINGERPRINT,
        "portable_runtime_assets": runtime_assets["status"] == "passed",
        "attempt_three_authorization": (
            attempt_approval["execution_attempt_id"] == ATTEMPT_ID
            and attempt_approval["campaign_fingerprint"] == CAMPAIGN_FINGERPRINT
            and attempt_approval["path_budget_contract_fingerprint"]
            == path_budget_contract["contract_fingerprint"]
            == PATH_BUDGET_CONTRACT_FINGERPRINT
            and attempt_approval["runtime_asset_manifest_fingerprint"]
            == runtime_assets["manifest_fingerprint"]
            == RUNTIME_ASSET_MANIFEST_FINGERPRINT
            and attempt_approval["approval_status"] == "approved"
            and attempt_approval["approver_type"] == "human_user"
            and attempt_approval["execution_authorized"] is True
            and attempt_approval["budget"]
            == {"max_backtest_calls": 16, "max_wall_clock_minutes": 240, "max_retries": 0}
            and attempt_approval["data_access"]
            == {"development_only": True, "validation": "forbidden", "holdout": "forbidden"}
            and attempt_approval["candidate_creation_allowed"] is False
            and attempt_approval["historical_execution_results_access"] == "forbidden"
            and attempt_approval["automatic_retry_allowed"] is False
            and attempt_approval["automatic_followup_execution_allowed"] is False
            and attempt_approval["request_id"] == attempt_request["request_id"]
            and attempt_approval["request_sha256"] == sha256_file(repo / ATTEMPT_REQUEST_PATH)
        ),
        "attempt_three_request_preserved": (
            attempt_request["approval_status"] == "pending_human_review"
            and attempt_request["execution_authorized"] is False
            and attempt_request["campaign_fingerprint"] == CAMPAIGN_FINGERPRINT
            and attempt_request["path_budget_contract_fingerprint"] == PATH_BUDGET_CONTRACT_FINGERPRINT
            and len(attempt_request["planned_executions"]) == MAX_BACKTEST_CALLS
        ),
        "campaign_fingerprint": _campaign_fingerprint(campaign) == campaign.get("campaign_fingerprint") == approval["compiled_campaign_fingerprint"] == authorization["approved_compiled_fingerprint"] == CAMPAIGN_FINGERPRINT,
        "slice_policy_fingerprint": fingerprint({key: value for key, value in policy.items() if key != "slice_policy_fingerprint"}) == policy.get("slice_policy_fingerprint") == approval["slice_policy_fingerprint"] == authorization["approved_slice_policy_fingerprint"] == SLICE_POLICY_FINGERPRINT,
        "read_only_recompile_replay": _campaign_fingerprint(replay_campaign) == CAMPAIGN_FINGERPRINT and replay_policy == policy,
        "human_execution_approval": approval["approval_status"] == "approved" and approval["approver_type"] == "human_user" and approval["execution_authorized"] is True and authorization["execution_authorized"] is True,
        "budget": approval["budget"] == {"temporal_slices": 4, "max_backtest_calls": 16, "max_wall_clock_minutes": 240, "max_retries": 0} and authorization["max_backtest_calls"] == 16 and authorization["max_wall_clock_minutes"] == 240 and authorization["max_retries"] == 0,
        "development_only": approval["data_access"] == {"development_only": True, "validation": "forbidden", "holdout": "forbidden"},
        "sealed_access_zero": authorization["validation_accesses_authorized"] == authorization["holdout_accesses_authorized"] == campaign["budget"]["max_validation_accesses"] == campaign["budget"]["max_holdout_accesses"] == 0,
        "candidate_immutable": approval["candidate_creation_allowed"] is False and authorization["candidate_creation_allowed"] is False and authorization["candidate_source_sha256"] == candidate["source_sha256"] == branch.CANDIDATE_SHA256 and sha256_file(repo / branch.CANDIDATE_SOURCE) == branch.CANDIDATE_SHA256,
        "candidate_manifest": candidate["selected_ablation_unit"] == RESEARCH_UNIT and candidate["conditions_changed"] == candidate["thresholds_changed"] == candidate["signal_groups_changed"] == 0,
        "candidate_ast": branch.validate_candidate_ast(repo)["status"] == "passed",
        "formal_strategy": sha256_file(repo / "strategies/RegimeAwareV6.py") == branch.STRATEGY_SHA256,
        "formal_base": sha256_file(repo / "strategies/regime_aware_base.py") == branch.BASE_SHA256,
        "router_contract": sha256_file(repo / branch.ROUTER_SOURCE) == branch.ROUTER_SHA256,
        "queue_exact": len(queue) == MAX_BACKTEST_CALLS and actual_order == expected_order and all(item["status"] == "queued_unexecuted" and item["execution_authorized"] is False and item["cache"] == "none" and item["network_access"] == "forbidden" and item["validation_accesses"] == item["holdout_accesses"] == 0 for item in queue),
        "slice_order": authorization["approved_slice_ids"] == [item["slice_id"] for item in policy["slices"]],
        "slice_integrity": policy["slice_count"] == 4 and policy["total_evaluation_1h_candles"] == 5000 and policy["integrity"]["slice_union_exact"] is True and policy["integrity"]["validation_exposure"] is False,
        "protected_manifests": validate_protected_manifests(repo)["passed"],
        "portable_fixture_pack": verify_portable_fixture_pack(repo / "research/testing/fixture-packs/portable-baseline-v1")["manifest_sha256"] == campaign["frozen_inputs"]["portable_fixture_pack"]["manifest_sha256"],
        "registry_available": (repo / REGISTRY_PATH).is_file(),
        "registry_integrity": False,
    }
    connection = open_director_registry(repo / REGISTRY_PATH)
    checks["registry_integrity"] = connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.close()
    for field in ("constitution", "evaluation_policy", "runtime", "formal_strategy", "formal_base", "router_contract"):
        frozen = campaign["frozen_inputs"][field]
        checks[f"frozen:{field}"] = sha256_file(repo / frozen["path"]) == frozen["sha256"]
    leverage = repo / LOCAL_LEVERAGE_TIER_PATH
    checks["frozen:leverage_tiers"] = leverage.is_file() and sha256_file(leverage) == campaign["frozen_inputs"]["leverage_tiers"]["sha256"]
    dataset_manifest = load_document(repo / campaign["frozen_inputs"]["dataset"]["manifest_path"])
    checks["frozen:dataset_manifest"] = sha256_file(repo / campaign["frozen_inputs"]["dataset"]["manifest_path"]) == campaign["frozen_inputs"]["dataset"]["manifest_sha256"]
    checks["frozen:dataset_files"] = all((repo / item["path"]).is_file() and (repo / item["path"]).stat().st_size == item["bytes"] and sha256_file(repo / item["path"]) == item["sha256"] for item in dataset_manifest["files"])
    exchange = load_document(repo / campaign["frozen_inputs"]["exchange_snapshot"]["path"])
    checks["frozen:exchange_snapshot"] = sha256_file(repo / campaign["frozen_inputs"]["exchange_snapshot"]["path"]) == campaign["frozen_inputs"]["exchange_snapshot"]["manifest_sha256"] and exchange["aggregate_sha256"] == campaign["frozen_inputs"]["exchange_snapshot"]["aggregate_sha256"]
    if not all(checks.values()):
        raise TemporalExecutionInvalid("execution_authority_validation_failed:" + json.dumps(checks, sort_keys=True))
    return checks


def configure_harness(repo: Path, slice_id: str) -> None:
    spec = slice_map(repo)[slice_id]
    harness.PROPOSAL_ID = PROPOSAL_ID
    harness.CAMPAIGN_ID = CAMPAIGN_ID
    harness.RESEARCH_UNIT = RESEARCH_UNIT
    harness.APPROVED_CAMPAIGN_FINGERPRINT = CAMPAIGN_FINGERPRINT
    harness.STRATEGY_SHA256 = branch.STRATEGY_SHA256
    harness.BASE_SHA256 = branch.BASE_SHA256
    harness.CANDIDATE_SHA256 = branch.CANDIDATE_SHA256
    harness.CANDIDATE_SOURCE = branch.CANDIDATE_SOURCE
    harness.CANDIDATE_MANIFEST = branch.CANDIDATE_MANIFEST
    harness.COMPILED_DIR = COMPILED_DIR.as_posix()
    harness.RECERTIFICATION_ATTEMPT = ATTEMPT_ID
    harness.CAMPAIGN_PATH_ID = "ranging-short-temporal-review-v1"
    harness.RESEARCH_UNIT_PATH_ID = slice_id
    harness.RESULT_ROOT = RESULT_ROOT / slice_id
    harness.ANALYSIS_ROOT = ANALYSIS_ROOT
    harness.REPORT_ROOT = REPORT_ROOT
    harness.PAIR_SPECS = {slice_id: {"pair": PAIR, "prefix": PREFIX, "dataset_id": DATASET_ID, "experiment_id": spec["slice_number"]}}
    harness.CONTAMINATED_ROOTS = tuple(RESULT_ROOT / other for other in slice_map(repo) if other != slice_id) + tuple(
        RESULT_ROOT / other / ORIGINAL_ATTEMPT_ID for other in SLICE_IDS
    ) + (
        Path("research/results/branch-contribution-ablation-v1"),
        Path("research/results/regime-branch-factorization-v1"),
        Path("research/results/stage4a-regime-conditioned-branch-factorization-v1"),
    )
    harness.load_strategy = branch.load_strategy
    harness.signal_mask = signal_mask
    harness.backtest_campaign = backtest_campaign
    harness.SHORT_NAMESPACE_FACTORY = None
    if ATTEMPT_ID == ATTEMPT_THREE_ID:
        # The short-root attempt is isolated from all historical result trees.
        # Its workers may inspect only their own attempt registry and namespace.
        harness.CONTAMINATED_ROOTS = ()
        harness.SHORT_NAMESPACE_FACTORY = create_short_worker_namespace


def short_execution_identity(
    repo: Path,
    slice_id: str,
    role: str,
    repetition: str,
    execution_id: str | None = None,
) -> dict[str, str]:
    repetition_id = repetition if repetition.startswith("RUN-") else f"RUN-{repetition}"
    campaign = load_document(repo / CAMPAIGN_PATH)
    spec = slice_map(repo)[slice_id]
    frozen = campaign["frozen_inputs"]
    identity = {
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "campaign_id": CAMPAIGN_ID,
        "campaign_fingerprint": CAMPAIGN_FINGERPRINT,
        "attempt_id": ATTEMPT_THREE_ID,
        "slice_id": slice_id,
        "slice_fingerprint": spec["split_fingerprint"],
        "role": role,
        "repetition": repetition_id,
        "candidate_class": frozen["candidate"]["class_name"],
        "candidate_path": frozen["candidate"]["path"],
        "candidate_sha256": frozen["candidate"]["source_sha256"],
        "formal_strategy_sha256": frozen["formal_strategy"]["sha256"],
        "dataset_id": frozen["dataset"]["dataset_id"],
        "dataset_sha256": frozen["dataset"]["aggregate_sha256"],
        "runtime_asset_manifest_fingerprint": RUNTIME_ASSET_MANIFEST_FINGERPRINT,
        "evaluation_policy_sha256": frozen["evaluation_policy"]["sha256"],
        "exchange_snapshot_sha256": frozen["exchange_snapshot"]["aggregate_sha256"],
        "router_sha256": frozen["router_contract"]["sha256"],
    }
    if execution_id is not None:
        identity["execution_id"] = execution_id
    return identity


def plan_short_execution(
    repo: Path,
    slice_id: str,
    role: str,
    repetition: str,
    execution_id: str | None = None,
) -> dict[str, Any]:
    contract = load_path_budget_contract(repo)
    identity = short_execution_identity(repo, slice_id, role, repetition, execution_id)
    return {"plan": plan_short_namespace(repo, contract, identity), "full_identity": identity}


def create_short_worker_namespace(
    repo: Path,
    slice_id: str,
    role: str,
    repetition: str,
    execution_id: str,
) -> dict[str, Any]:
    contract = load_path_budget_contract(repo)
    identity = short_execution_identity(repo, slice_id, role, repetition, execution_id)
    return {"plan": create_short_execution_namespace(repo, contract, identity), "full_identity": identity}


def _in_window(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    timestamps = pd.to_datetime(frame["date"], utc=True)
    return frame.loc[(timestamps >= pd.Timestamp(start)) & (timestamps < pd.Timestamp(end))].copy()


def signal_mask(repo: Path, role: str, slice_id: str, run_id: str, output: Path) -> dict[str, Any]:
    spec = slice_map(repo)[slice_id]
    data_root = repo / DATA_ROOT

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return [PAIR]

        def get_pair_dataframe(self, pair: str, timeframe: str, candle_type: str = "futures") -> pd.DataFrame:
            if pair != PAIR or candle_type != "futures" or timeframe != "4h":
                raise TemporalExecutionInvalid("unauthorized_signal_instrumentation_input")
            frame = pd.read_feather(data_root / f"{PREFIX}-4h-futures.feather")
            return _in_window(frame, spec["warmup_start"], spec["evaluation_end_exclusive"])

    strategy_class, module, source = branch.load_strategy(repo, role)
    raw = pd.read_feather(data_root / f"{PREFIX}-1h-futures.feather")
    raw = _in_window(raw, spec["warmup_start"], spec["evaluation_end_exclusive"])
    strategy = strategy_class({})
    strategy.dp = DataProvider()
    frame = strategy.populate_indicators(raw.copy(), {"pair": PAIR})
    frame = strategy.populate_entry_trend(frame, {"pair": PAIR})
    frame = strategy.populate_exit_trend(frame, {"pair": PAIR})
    frame = _in_window(frame, spec["evaluation_start"], spec["evaluation_end_exclusive"])
    if len(frame) != spec["evaluation_1h_candle_count"]:
        raise TemporalExecutionInvalid(f"slice_signal_row_count_mismatch:{slice_id}:{len(frame)}")
    columns = ("enter_long", "enter_short", "exit_long", "exit_short")
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        item: dict[str, Any] = {"date": pd.Timestamp(row["date"]).isoformat()}
        for column in columns:
            item[column] = int(row[column]) if column in frame and not pd.isna(row[column]) else 0
        for column in ("enter_tag", "exit_tag"):
            value = row.get(column)
            item[column] = None if value is None or pd.isna(value) else str(value)
        rows.append(item)
    branch_rows = [item for item in rows if item.get("enter_tag") == "ranging_short"]
    import ccxt
    import freqtrade
    identity = {
        "schema_version": "runtime_identity_projection_v1",
        "role": role,
        "strategy_class": strategy_class.__name__,
        "module_name": module.__name__,
        "module_path": str(Path(module.__file__ or "").resolve()),
        "source_path": source.relative_to(repo).as_posix(),
        "source_sha256": sha256_file(source),
        "dependency_path": "strategies/regime_aware_base.py",
        "dependency_sha256": sha256_file(repo / "strategies/regime_aware_base.py"),
        "pid": os.getpid(),
        "execution_run_id": run_id,
        "runtime_versions": {"python": sys.version.split()[0], "freqtrade": freqtrade.__version__, "ccxt": ccxt.__version__},
        "experiment_id": spec["slice_number"],
        "slice_id": slice_id,
        "slice_semantic_fingerprint": spec["slice_semantic_fingerprint"],
    }
    payload = {
        "schema_version": "temporal-ablation-signal-mask-v1",
        "slice_id": slice_id,
        "slice_policy_fingerprint": SLICE_POLICY_FINGERPRINT,
        "signal_semantic_projection": harness.signal_semantic_projection_from_rows(PAIR, rows),
        "runtime_identity_projection": identity,
        "formal_strategy_sha256": sha256_file(repo / "strategies/RegimeAwareV6.py"),
        "formal_base_sha256": sha256_file(repo / "strategies/regime_aware_base.py"),
        "branch_contribution_projection": {
            "unit_id": RESEARCH_UNIT,
            "pre_gate_signal_count": len(branch_rows),
            "final_enter_short_count_for_tag": sum(int(item.get("enter_short") or 0) for item in branch_rows),
            "tag_preserved_count": len(branch_rows),
            "pre_gate_rows_sha256": canonical_hash([{"date": item["date"], "enter_tag": item["enter_tag"]} for item in branch_rows]),
        },
        "rows": rows,
    }
    write_json(output, payload)
    return {key: value for key, value in payload.items() if key != "rows"}


def backtest_campaign(slice_id: str, role: str) -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[1]
    spec = slice_map(repo)[slice_id]
    strategy = "RegimeAwareV6" if role == "baseline" else "RegimeAware_Ablation_RangingShort_C1"
    strategy_file = "strategies/RegimeAwareV6.py" if role == "baseline" else branch.CANDIDATE_SOURCE
    strategy_path = "strategies" if role == "baseline" else Path(branch.CANDIDATE_SOURCE).parent.as_posix()
    start = int(pd.Timestamp(spec["evaluation_start"]).timestamp())
    end = int(pd.Timestamp(spec["evaluation_end_exclusive"]).timestamp())
    return {"campaign_id": CAMPAIGN_ID, "fixed_backtest": {
        "strategy": strategy,
        "strategy_file": strategy_file,
        "strategy_path": strategy_path,
        "config": "research/runtime/demo-futures-backtest-config.json",
        "dataset_id": DATASET_ID,
        "dataset_manifest": f"research/data/snapshots/{DATASET_ID}/manifest.yaml",
        "datadir": f"research/data/snapshots/{DATASET_ID}/data",
        "timerange": f"{start}-{end}",
        "timeframe": "1h",
        "pairs": [PAIR],
        "fee": "0.0004",
        "acceptance_gate": {},
    }}


def run_fresh(repo: Path, slice_id: str, role: str, repetition: str) -> dict[str, Any]:
    short_plan = None
    if ATTEMPT_ID == ATTEMPT_THREE_ID:
        short_plan = plan_short_execution(repo, slice_id, role, repetition)
        execution_id = short_plan["plan"]["execution_id"]
    else:
        execution_id = uuid.uuid4().hex[:12]
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--worker", "--slice", slice_id, "--role", role, "--repetition", repetition, "--execution-id", execution_id],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
        timeout=1800,
        env={**os.environ, "PORTABLE_BASELINE_NETWORK": "forbidden"},
    )
    if short_plan is not None:
        run_dir = repo / short_plan["plan"]["namespace"]
        if run_dir.is_dir():
            (run_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
            (run_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise TemporalExecutionInvalid(f"fresh_worker_failed:{slice_id}:{role}:{repetition}:{completed.stderr[-2500:]}:{completed.stdout[-2500:]}")
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    write_json(repo / payload["output_root"] / "worker-launch.json", {"returncode": 0, "stdout": completed.stdout, "stderr": completed.stderr, "shell": False, "execution_id": execution_id})
    if short_plan is not None:
        artifact_index = repo / payload["output_root"] / "artifact-hashes.json"
        artifact_index.unlink(missing_ok=True)
        write_json(artifact_index, harness.artifact_hashes(repo / payload["output_root"]))
    return payload


def _load_normalized(repo: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    return load_document(repo / run["normalized_trades_path"])["rows"]


def _trade_counter(rows: list[dict[str, Any]]) -> Counter[str]:
    fields = ("pair", "open_date", "close_date", "is_short", "enter_tag", "exit_reason", "open_rate", "close_rate")
    return Counter(canonical_hash({field: row.get(field) for field in fields}) for row in rows)


def _raw_metrics(repo: Path, run: dict[str, Any]) -> dict[str, Any]:
    raw = load_document(repo / run["raw_result_path"])
    strategies = raw.get("strategy") or {}
    summary = strategies.get(run["strategy"])
    if summary is None and len(strategies) == 1:
        summary = next(iter(strategies.values()))
    if not isinstance(summary, dict):
        raise TemporalExecutionInvalid("raw_strategy_summary_missing")
    return {
        "total_return_abs": float(summary.get("profit_total_abs") or 0),
        "total_return_ratio": float(summary.get("profit_total") or 0),
        "profit_factor": float(summary.get("profit_factor") or 0),
        "max_drawdown_abs": float(summary.get("max_drawdown_abs") or 0),
        "max_drawdown_ratio": float(summary.get("max_drawdown_account") or 0),
        "average_duration": summary.get("holding_avg"),
    }


def _within_role_reproducibility(role: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    identity = harness.audit_runtime_identity(left, right, role)
    semantic = harness.compare_signal_semantics(left["signal_mask"], right["signal_mask"])
    differences = {field: [left[field], right[field]] for field in ("summary", "normalized_trade_hash", "normalized_trade_count") if left[field] != right[field]}
    if not semantic["passed"]:
        differences["signal_semantics"] = semantic["differences"]
    return {"passed": not differences, "runtime_identity": identity, "signal_semantics": semantic, "differences": differences, "pids": [left["pid"], right["pid"]]}


def classify_slice(signals: int, removed: int, added: int, baseline: dict[str, Any], delta: dict[str, float]) -> str:
    if signals == 0:
        return "branch_contribution_inconclusive"
    if removed == 0 and added == 0:
        return "branch_redundant"
    benefits = [delta["total_return_abs"] > 1e-9, delta["profit_factor"] > 1e-9, delta["max_drawdown_abs"] < -1e-9, delta["max_drawdown_ratio"] < -1e-12]
    harms = [delta["total_return_abs"] < -1e-9, delta["profit_factor"] < -1e-9, delta["max_drawdown_abs"] > 1e-9, delta["max_drawdown_ratio"] > 1e-12]
    risk_reverse = delta["max_drawdown_abs"] > max(1.0, baseline["max_drawdown_abs"] * 0.05) or delta["max_drawdown_ratio"] > 0.0025
    risk_improves = delta["max_drawdown_abs"] < -max(1.0, baseline["max_drawdown_abs"] * 0.05) or delta["max_drawdown_ratio"] < -0.0025
    if (delta["total_return_abs"] > 0 and delta["profit_factor"] >= 0 and not risk_reverse) or sum(benefits) >= 3:
        return "branch_negative_contributor"
    if (delta["total_return_abs"] < 0 and delta["profit_factor"] <= 0 and not risk_improves) or sum(harms) >= 3:
        return "branch_positive_contributor"
    return "branch_mixed_regime_dependent"


def compare_slice(repo: Path, slice_id: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {(run["role"], run["repetition"]): run for run in runs}
    reproducibility = {role: _within_role_reproducibility(role, by_key[(role, "A")], by_key[(role, "B")]) for role in ("baseline", "candidate")}
    if not all(item["passed"] for item in reproducibility.values()):
        raise TemporalExecutionInvalid(f"temporal_ablation_reproducibility_failed:{slice_id}")
    baseline, candidate = by_key[("baseline", "A")], by_key[("candidate", "A")]
    harness.audit_cross_role_identity(baseline, candidate)
    baseline_rows, candidate_rows = _load_normalized(repo, baseline), _load_normalized(repo, candidate)
    baseline_counter, candidate_counter = _trade_counter(baseline_rows), _trade_counter(candidate_rows)
    removed = sum((baseline_counter - candidate_counter).values())
    added = sum((candidate_counter - baseline_counter).values())
    baseline_metrics, candidate_metrics = _raw_metrics(repo, baseline), _raw_metrics(repo, candidate)
    delta = {key: candidate_metrics[key] - baseline_metrics[key] for key in ("total_return_abs", "total_return_ratio", "profit_factor", "max_drawdown_abs", "max_drawdown_ratio")}
    baseline_costs, candidate_costs = branch._fee_summary(repo, baseline), branch._fee_summary(repo, candidate)
    cost_delta = {key: candidate_costs[key] - baseline_costs[key] for key in baseline_costs}
    signals = baseline["signal_mask"]["branch_contribution_projection"]["pre_gate_signal_count"]
    classification = classify_slice(signals, removed, added, baseline_metrics, delta)
    baseline_remaining = [row for row in baseline_rows if row.get("enter_tag") != "ranging_short"]
    candidate_remaining = [row for row in candidate_rows if row.get("enter_tag") != "ranging_short"]
    return {
        "schema_version": "temporal-branch-contribution-slice-comparison-v1",
        "slice_id": slice_id,
        "slice": slice_map(repo)[slice_id],
        "reproducibility": reproducibility,
        "runs": runs,
        "signals": {
            "baseline_pre_gate": signals,
            "candidate_pre_gate": candidate["signal_mask"]["branch_contribution_projection"]["pre_gate_signal_count"],
            "candidate_final_ranging_short_enter_short": candidate["signal_mask"]["branch_contribution_projection"]["final_enter_short_count_for_tag"],
            "removed": signals,
        },
        "trades": {"baseline": len(baseline_rows), "candidate": len(candidate_rows), "removed": removed, "added_or_shifted": added, "baseline_normalized_hash": baseline["normalized_trade_hash"], "candidate_normalized_hash": candidate["normalized_trade_hash"]},
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "candidate_minus_baseline": delta,
        "units": {"total_return_abs": "USDT", "total_return_ratio": "ratio", "profit_factor": "ratio", "max_drawdown_abs": "USDT", "max_drawdown_ratio": "ratio", "max_drawdown_percentage_points": delta["max_drawdown_ratio"] * 100},
        "improvement_direction": {"total_return_abs": "higher_is_better", "total_return_ratio": "higher_is_better", "profit_factor": "higher_is_better", "max_drawdown_abs": "lower_is_better", "max_drawdown_ratio": "lower_is_better", "trading_fee_cost": "lower_is_better", "funding_fees": "reported_signed_no_standalone_verdict"},
        "baseline_costs": baseline_costs,
        "candidate_costs": candidate_costs,
        "candidate_minus_baseline_costs": cost_delta,
        "average_duration": {"baseline": baseline_metrics["average_duration"], "candidate": candidate_metrics["average_duration"]},
        "rolling_28_day_profit_abs": {"baseline": branch._rolling_28_day(baseline_rows), "candidate": branch._rolling_28_day(candidate_rows)},
        "tags": {"baseline": baseline["summary"]["enter_tag_counts"], "candidate": candidate["summary"]["enter_tag_counts"]},
        "exit_reasons": {"baseline": baseline["summary"]["exit_reason_counts"], "candidate": candidate["summary"]["exit_reason_counts"]},
        "remaining_branch_behavior": {"baseline_count": len(baseline_remaining), "candidate_count": len(candidate_remaining), "baseline_hash": canonical_hash(baseline_remaining), "candidate_hash": canonical_hash(candidate_remaining)},
        "classification": classification,
    }


def classify_temporal(results: dict[str, dict[str, Any]]) -> str:
    classes = [item["classification"] for item in results.values()]
    negative = classes.count("branch_negative_contributor")
    positive = classes.count("branch_positive_contributor")
    redundant = classes.count("branch_redundant")
    reverse_risk = any(item["candidate_minus_baseline"]["max_drawdown_abs"] > max(1.0, item["baseline_metrics"]["max_drawdown_abs"] * 0.05) or item["candidate_minus_baseline"]["max_drawdown_ratio"] > 0.0025 for item in results.values())
    if negative >= 3 and positive == 0 and not reverse_risk:
        return "branch_negative_contributor_temporally_consistent"
    if positive >= 3 and negative == 0:
        return "branch_positive_contributor_temporally_consistent"
    if negative and positive:
        return "branch_mixed_temporal_dependency"
    if redundant == len(classes):
        return "branch_redundant_temporally_consistent"
    return "branch_contribution_temporally_inconclusive"


def next_proposal(classification: str, evidence: list[str]) -> dict[str, Any]:
    if classification == "branch_negative_contributor_temporally_consistent":
        proposal = {
            "proposal_id": "ranging-short-btc-validation-authorization-review-v1",
            "research_question": "Should the frozen ranging-short ablation Candidate receive one limited BTC Validation access?",
            "referenced_variables": [],
            "referenced_mechanisms": [RESEARCH_UNIT],
            "market_scope": {"pairs": [PAIR], "timeframe": "1h"},
            "data_scope": {"development_complete": True, "validation_requested": True, "max_validation_accesses_requested": 1, "holdout": False},
            "proposed_method": {"type": "human_validation_authorization_review", "candidate_modification_allowed": False, "execute_automatically": False},
            "risk_class": "high",
            "status": "pending_human_review",
            "evidence": evidence,
        }
    else:
        proposal = {
            "proposal_id": "ranging-short-branch-retention-review-v1",
            "research_question": "Should the formal ranging-short branch remain unchanged because temporal evidence is mixed or insufficient?",
            "referenced_variables": [],
            "referenced_mechanisms": [RESEARCH_UNIT],
            "market_scope": {"pairs": [PAIR], "timeframe": "1h"},
            "data_scope": {"development_only": True, "validation": False, "holdout": False},
            "proposed_method": {"type": "human_retention_record_review", "execute_automatically": False},
            "risk_class": "medium",
            "status": "pending_human_review",
            "evidence": evidence,
        }
    proposal["semantic_fingerprint"] = proposal_fingerprint(proposal)
    return proposal


def update_state(repo: Path, final: dict[str, Any], proposal: dict[str, Any]) -> None:
    state = load_document(repo / STATE_PATH)
    state["ranging_short_temporal_branch_contribution_review"] = {
        "status": "completed",
        "execution_attempt_id": ATTEMPT_ID,
        "classification": final["classification"],
        "slice_count": 4,
        "backtest_calls": 16,
        "candidate_reused": True,
        "candidate_modified": False,
        "formal_strategy_modified": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "next_proposal_id": proposal["proposal_id"],
        "next_proposal_fingerprint": proposal["semantic_fingerprint"],
        "next_proposal_status": "pending_human_review",
        "evidence": [f"{ANALYSIS_ROOT.as_posix()}/temporal-contribution-result.json", f"{REPORT_ROOT.as_posix()}/final-report.json"],
    }
    for question in state.get("unresolved_research_questions", []):
        if question.get("question_id") == "branch-contribution-ablation":
            question["current_answer"] = final["classification"]
            question["evidence"] = [f"{ANALYSIS_ROOT.as_posix()}/temporal-contribution-result.json", (NEXT_ROOT / f"{proposal['proposal_id']}.json").as_posix()]
    write_json(repo / STATE_PATH, state)


def record_registry(repo: Path, final: dict[str, Any], assets: list[str]) -> None:
    connection = open_director_registry(repo / REGISTRY_PATH)
    completed = utc_now()
    authorization = load_document(repo / ATTEMPT_APPROVAL_PATH)
    connection.execute("INSERT OR REPLACE INTO campaign_execution_authorizations(authorization_id,campaign_id,approved_compiled_fingerprint,proposal_id,execution_authorized,payload_json,authorized_at) VALUES(?,?,?,?,?,?,?)", (authorization["execution_attempt_id"], CAMPAIGN_ID, CAMPAIGN_FINGERPRINT, PROPOSAL_ID, 1, json.dumps(authorization, sort_keys=True), completed))
    connection.execute("INSERT OR REPLACE INTO research_campaign_runs(run_id,campaign_id,proposal_id,status,result_code,campaign_executed,candidate_created,strategy_modified,validation_accesses,holdout_accesses,payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (RUN_ID, CAMPAIGN_ID, PROPOSAL_ID, "completed", final["classification"], 1, 0, 0, 0, 0, json.dumps(final, sort_keys=True), completed))
    for path in assets:
        connection.execute("INSERT OR REPLACE INTO research_campaign_assets(asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)", (f"{RUN_ID}:{path}", RUN_ID, "campaign_evidence", path, sha256_file(repo / path), completed))
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise TemporalExecutionInvalid("registry_integrity_failed")
    write_json(repo / REGISTRY_EXPORT_PATH, export_registry(str(repo / REGISTRY_PATH)))


def ensure_attempt_namespace_empty(repo: Path) -> None:
    plans = [
        plan_short_execution(repo, slice_id, role, repetition)["plan"]
        for slice_id in SLICE_IDS
        for role in ("baseline", "candidate")
        for repetition in ("A", "B")
    ]
    attempt_roots = {plan["attempt_root"] for plan in plans}
    if len(attempt_roots) != 1:
        raise TemporalExecutionInvalid("short_execution_namespace_collision")
    attempt_root = next(iter(attempt_roots))
    if (repo / attempt_root).exists():
        raise TemporalExecutionInvalid(f"attempt_output_namespace_not_empty:{attempt_root}")


def run_campaign(repo: Path) -> dict[str, Any]:
    started = time.monotonic()
    checks = validate_authority(repo)
    ensure_attempt_namespace_empty(repo)
    results: dict[str, dict[str, Any]] = {}
    all_runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    calls = 0
    slices = list(slice_map(repo))
    for slice_id in slices:
        for role in ("baseline", "candidate"):
            for repetition in ("A", "B"):
                validate_authority(repo)
                run = run_fresh(repo, slice_id, role, repetition)
                calls += 1
                if calls > MAX_BACKTEST_CALLS or any(item.get("blocked") or not item.get("loopback") for item in run["network_attempts"]):
                    raise TemporalExecutionInvalid("budget_or_network_contract_violation")
                all_runs[slice_id].append(run)
                if time.monotonic() - started > MAX_WALL_CLOCK_SECONDS:
                    raise TemporalExecutionInvalid("wall_clock_budget_exceeded")
        result = compare_slice(repo, slice_id, all_runs[slice_id])
        results[slice_id] = result
        write_json(repo / ANALYSIS_ROOT / f"{slice_id}-contribution-comparison.json", result)
    pids = [run["pid"] for runs in all_runs.values() for run in runs]
    if calls != 16 or len(pids) != len(set(pids)):
        raise TemporalExecutionInvalid("fresh_process_or_budget_mismatch")
    classification = classify_temporal(results)
    evidence = [(ANALYSIS_ROOT / f"{slice_id}-contribution-comparison.json").as_posix() for slice_id in slices]
    proposal = next_proposal(classification, evidence)
    proposal_path = NEXT_ROOT / f"{proposal['proposal_id']}.json"
    write_json(repo / proposal_path, proposal)
    final = {
        "schema_version": "temporal-branch-contribution-result-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "campaign_id": CAMPAIGN_ID,
        "campaign_fingerprint": CAMPAIGN_FINGERPRINT,
        "runtime_asset_manifest_fingerprint": RUNTIME_ASSET_MANIFEST_FINGERPRINT,
        "execution_attempt_id": ATTEMPT_ID,
        "original_attempt": {
            "execution_attempt_id": ORIGINAL_ATTEMPT_ID,
            "status": "temporal_ablation_execution_invalid",
            "reason": "runtime_execution_asset_missing",
        },
        "slice_policy_fingerprint": SLICE_POLICY_FINGERPRINT,
        "status": "completed",
        "classification": classification,
        "authority_checks": checks,
        "slice_results": {key: {field: value[field] for field in ("signals", "trades", "baseline_metrics", "candidate_metrics", "candidate_minus_baseline", "baseline_costs", "candidate_costs", "candidate_minus_baseline_costs", "classification")} for key, value in results.items()},
        "backtest_calls": calls,
        "worker_pids": pids,
        "all_worker_pids_unique": True,
        "budget": {"temporal_slices": 4, "max_backtest_calls": 16, "max_wall_clock_minutes": 240, "max_retries": 0},
        "budget_used": {"temporal_slices": 4, "backtest_calls": calls, "retries": 0, "wall_clock_seconds": round(time.monotonic() - started, 3)},
        "candidate_reused": True,
        "candidate_created": False,
        "candidate_modified": False,
        "strategy_modified": False,
        "base_modified": False,
        "router_modified": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "hyperopt_run": False,
        "next_proposal": {"proposal_id": proposal["proposal_id"], "risk_class": proposal["risk_class"], "status": proposal["status"], "fingerprint": proposal["semantic_fingerprint"]},
        "automatic_followup_executed": False,
    }
    analysis = ANALYSIS_ROOT / "temporal-contribution-result.json"
    execution = COMPILED_DIR / "execution" / "campaign-execution.json"
    report_json = REPORT_ROOT / "final-report.json"
    report_md = REPORT_ROOT / "final-report.md"
    for path in (analysis, execution, report_json):
        write_json(repo / path, final)
    lines = ["# Temporal Branch Contribution Review", "", f"- Execution attempt: `{ATTEMPT_ID}`", f"- Classification: `{classification}`", "- Backtest calls: `16 / 16`", "- Retries: `0`", "- Validation/Holdout: `0 / 0`", "- Candidate reused and unchanged: `true`", "- Formal strategy modified: `false`", ""]
    for slice_id, result in results.items():
        delta = result["candidate_minus_baseline"]
        costs = result["candidate_minus_baseline_costs"]
        lines.extend([f"## {slice_id}", "", f"- Evaluation: `{result['slice']['evaluation_start']}` to `{result['slice']['evaluation_end_exclusive']}`", f"- Signals removed: `{result['signals']['removed']}`", f"- Trades removed / added or shifted: `{result['trades']['removed']} / {result['trades']['added_or_shifted']}`", f"- Return delta (Candidate - Baseline): `{delta['total_return_abs']}` USDT (`{delta['total_return_ratio'] * 100}`%)", f"- Profit Factor delta: `{delta['profit_factor']}`", f"- Max drawdown delta: `{delta['max_drawdown_abs']}` USDT (`{delta['max_drawdown_ratio'] * 100}` percentage points)", f"- Trading fee / funding delta: `{costs['trading_fee_cost']}` / `{costs['funding_fees']}`", f"- Slice classification: `{result['classification']}`", ""])
    lines.extend(["## Next Proposal", "", f"`{proposal['proposal_id']}` is `{proposal['risk_class']}` / `{proposal['status']}` and was not compiled or executed.", ""])
    (repo / report_md).parent.mkdir(parents=True, exist_ok=True)
    (repo / report_md).write_text("\n".join(lines), encoding="utf-8")
    update_state(repo, final, proposal)
    assets = [APPROVAL_PATH.as_posix(), AUTHORIZATION_PATH.as_posix(), ATTEMPT_APPROVAL_PATH.as_posix(), analysis.as_posix(), execution.as_posix(), report_json.as_posix(), report_md.as_posix(), proposal_path.as_posix(), STATE_PATH.as_posix(), *evidence]
    record_registry(repo, final, assets)
    return final


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--slice", choices=sorted(slice_map(repo)))
    parser.add_argument("--role", choices=("baseline", "candidate"))
    parser.add_argument("--repetition", choices=("A", "B"))
    parser.add_argument("--execution-id")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.worker:
            if not all((args.slice, args.role, args.repetition, args.execution_id)):
                parser.error("worker arguments incomplete")
            configure_harness(repo, args.slice)
            result = harness.worker(repo, args.slice, args.role, args.repetition, args.execution_id)
        elif args.preflight_only:
            result = {"status": "passed", "checks": validate_authority(repo)}
        else:
            result = run_campaign(repo)
    except (TemporalExecutionInvalid, branch.AblationExecutionInvalid) as exc:
        print(json.dumps({"status": "temporal_ablation_execution_invalid", "detail": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
