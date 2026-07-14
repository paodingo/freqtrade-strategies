#!/usr/bin/env python3
"""Freeze four BTC Development-only slices and compile an unexecuted temporal Campaign."""

from __future__ import annotations

import argparse
import ast
import copy
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from research_control import load_campaign
from portable_baseline_fixtures import verify as verify_portable_fixture_pack
from research_director_common import (
    fingerprint,
    load_document,
    proposal_fingerprint,
    sha256_file,
    utc_now,
    write_json,
    write_yaml,
)
from protected_manifest_hash import canonical_text_sha256


PROPOSAL_ID = "ranging-short-branch-decision-review-v1"
PROPOSAL_FINGERPRINT = "e5b01ecdfc922b06a20e8e0c1eb901fd363563da23d246819cfa8e268247c0c3"
OLD_CAMPAIGN_FINGERPRINT = "1bf23890fd3386f7970e46cb74451c7b3696a7f92252faa233fca5f9af36192d"
DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
DATASET_MANIFEST_SHA256 = "e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13"
DATASET_AGGREGATE_SHA256 = "3e86474ba634c3779389d818997d1626357090da7fef6b9f007ad0f9bbcfdd5c"
CANDIDATE_PATH = "research/candidates/branch-contribution-ablation-v1/1/RegimeAware_Ablation_RangingShort_C1.py"
CANDIDATE_MANIFEST = "research/candidates/branch-contribution-ablation-v1/1/candidate-manifest.json"
CANDIDATE_SHA256 = "e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0"
STRATEGY_PATH = "strategies/RegimeAwareV6.py"
STRATEGY_SHA256 = "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
BASE_PATH = "strategies/regime_aware_base.py"
BASE_SHA256 = "8feaebff14b5e8c537ec310b44b2b1d448db20be1388e3aca51da15b306275f9"
ROUTER_PATH = "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"
ROUTER_SHA256 = "bee68e27b345a93a1fe8481275e365829c986f700d2719fdd10ffd907e1dffa1"
CONSTITUTION_PATH = "research/governance/research-constitution.yaml"
CONSTITUTION_SHA256 = "ff0ca1b7f3aa4f7f0a7d6b893095ba618d1ecf50cf7044dfeb3152bd91826722"
POLICY_PATH = "research/evaluation/evaluation-policy.yaml"
POLICY_SHA256 = "ee4769e4c814e209e771c31fa35ff4d8c4719137fffe7291d3ae87d73c8e8b5e"
RUNTIME_PATH = "research/runtime/freqtrade-runtime.yaml"
RUNTIME_SHA256 = "e87e375a8c61d8b7eeae8e53fc0715840956ea617471ad9c7d06275d9726f76d"
EXCHANGE_MANIFEST = "research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml"
EXCHANGE_AGGREGATE_SHA256 = "599d67345bed5b2b3b42669baf460fa336ffde80502cfd1880ea57cd0dc5074d"
LEVERAGE_TIER_PATH = ".venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json"
LEVERAGE_TIER_SHA256 = "3cbdcc23ac57dd40e8664036293947fbe283865ef4a0f87e9265bb441858d981"
PORTABLE_PACK_MANIFEST_SHA256 = "f164b6200dc9a88e582e39806c5781dc7a23959ff15a5feff93f4911c1c38cd5"
APPROVAL_PATH = "research/governance/approvals/ranging-short-branch-decision-review-v1-temporal-recompile-approval.json"
OLD_CAMPAIGN_PATH = "research/director/compiled/ranging-short-branch-decision-review-v1/campaign.yaml"
SLICE_POLICY_PATH = "research/temporal/ranging-short-ablation-temporal-slices-v1.yaml"
OUTPUT_DIR = "research/director/compiled/ranging-short-branch-decision-review-v1-temporal-v2"
STARTUP_CANDLES = 200
INFORMATIVE_TIMEFRAME_HOURS = 4
SLICE_COUNT = 4
EVALUATION_CANDLES_PER_SLICE = 1250
TOTAL_EVALUATION_CANDLES = 5000


class TemporalSliceCompilationError(RuntimeError):
    reason_code = "temporal_slice_compilation_failed"


def fail(reason: str) -> None:
    raise TemporalSliceCompilationError(f"{TemporalSliceCompilationError.reason_code}:{reason}")


def utc(value: Any) -> str:
    return pd.Timestamp(value).tz_convert("UTC").isoformat().replace("+00:00", "Z")


def dates(frame: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(frame["date"], utc=True)


def check_cadence(frame: pd.DataFrame, hours: int, label: str) -> None:
    values = dates(frame)
    if values.isna().any() or values.duplicated().any() or not values.is_monotonic_increasing:
        fail(f"{label}_timestamp_integrity")
    delta_seconds = values.diff().dropna().dt.total_seconds()
    if not delta_seconds.eq(hours * 3600).all():
        fail(f"{label}_timestamp_gap")


def verify_candidate_shape(repo: Path) -> dict[str, Any]:
    tree = ast.parse((repo / CANDIDATE_PATH).read_text(encoding="utf-8"))
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    if [node.name for node in classes] != ["RegimeAware_Ablation_RangingShort_C1"]:
        fail("candidate_class_drift")
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef)]
    if [node.name for node in methods] != ["populate_entry_trend"]:
        fail("candidate_method_surface_drift")
    strings = [node.value for node in ast.walk(methods[0]) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    zero_assignments = [node for node in ast.walk(methods[0]) if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and node.value.value == 0]
    if strings.count("ranging_short") != 1 or strings.count("enter_short") != 2 or len(zero_assignments) != 1:
        fail("candidate_single_gate_drift")
    return {"status": "passed", "class_count": 1, "method_count": 1, "ranging_short_final_zero_gates": 1}


def verify_file_bindings(repo: Path, data_repo: Path, manifest: dict[str, Any]) -> dict[str, pd.DataFrame]:
    current_manifest = repo / "research/data/snapshots" / DATASET_ID / "manifest.yaml"
    source_manifest = data_repo / "research/data/snapshots" / DATASET_ID / "manifest.yaml"
    if sha256_file(current_manifest) != DATASET_MANIFEST_SHA256 or sha256_file(source_manifest) != DATASET_MANIFEST_SHA256:
        fail("dataset_manifest_hash_drift")
    if manifest.get("dataset_id") != DATASET_ID or manifest.get("aggregate_sha256") != DATASET_AGGREGATE_SHA256:
        fail("dataset_identity_or_aggregate_drift")
    if not manifest.get("sealed") or manifest.get("intended_use") != "development":
        fail("dataset_not_sealed_development")
    frames: dict[str, pd.DataFrame] = {}
    expected_names = {
        "BTC_USDT_USDT-1h-futures.feather": 1,
        "BTC_USDT_USDT-4h-futures.feather": 4,
        "BTC_USDT_USDT-8h-mark.feather": 8,
        "BTC_USDT_USDT-8h-funding_rate.feather": 8,
    }
    if {Path(item["path"]).name for item in manifest["files"]} != set(expected_names):
        fail("unexpected_dataset_file_set")
    for item in manifest["files"]:
        relative = Path(item["path"])
        lowered = relative.as_posix().lower()
        if "validation" in lowered or "stage3e1" in lowered or "eth_" in lowered:
            fail("forbidden_dataset_reference")
        path = data_repo / relative
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            fail(f"dataset_file_drift:{relative.name}")
        frame = pd.read_feather(path)
        check_cadence(frame, expected_names[relative.name], relative.name)
        frames[relative.name] = frame
    return frames


def stream_binding(
    manifest_item: dict[str, Any], frame: pd.DataFrame, warmup_start: pd.Timestamp,
    evaluation_end: pd.Timestamp, cadence_hours: int,
) -> dict[str, Any]:
    values = dates(frame)
    eligible_start = values[values <= warmup_start]
    if eligible_start.empty:
        fail(f"warmup_coverage_missing:{Path(manifest_item['path']).name}")
    selection_start = eligible_start.iloc[-1]
    positions = frame.index[(values >= selection_start) & (values < evaluation_end)].tolist()
    if not positions:
        fail(f"stream_selection_empty:{Path(manifest_item['path']).name}")
    selected = values.loc[positions]
    if selected.iloc[-1] + timedelta(hours=cadence_hours) < evaluation_end:
        fail(f"stream_end_coverage_missing:{Path(manifest_item['path']).name}")
    return {
        "path": manifest_item["path"],
        "source_file_bytes": manifest_item["bytes"],
        "source_file_sha256": manifest_item["sha256"],
        "row_start": int(positions[0]),
        "row_end": int(positions[-1]),
        "candle_count": len(positions),
        "first_candle_timestamp": utc(selected.iloc[0]),
        "last_candle_timestamp": utc(selected.iloc[-1]),
        "cadence_hours": cadence_hours,
    }


def validate_slice_policy(policy: dict[str, Any], manifest: dict[str, Any]) -> None:
    slices = policy.get("slices") or []
    if len(slices) != SLICE_COUNT or policy.get("source_dataset") != DATASET_ID:
        fail("slice_count_or_source_dataset")
    if policy.get("validation_data_allowed") is not False:
        fail("validation_data_allowed")
    if any("stage3e1" in json.dumps(item).lower() or item.get("validation_exposure") is not False for item in slices):
        fail("forbidden_slice_reuse_or_validation_exposure")
    # The manifest has 800 warm-up rows followed by the exact 5000-row evaluation region.
    expected_row = 800
    previous_end: str | None = None
    all_rows: list[int] = []
    for index, item in enumerate(slices, start=1):
        if item.get("slice_number") != index or item.get("evaluation_1h_candle_count") != EVALUATION_CANDLES_PER_SLICE:
            fail("slice_order_or_count")
        if item.get("evaluation_row_start") != expected_row or item.get("evaluation_row_end") != expected_row + EVALUATION_CANDLES_PER_SLICE - 1:
            fail("slice_row_gap_or_overlap")
        if previous_end is not None and item.get("evaluation_start") != previous_end:
            fail("slice_timestamp_gap_or_overlap")
        all_rows.extend(range(item["evaluation_row_start"], item["evaluation_row_end"] + 1))
        expected_row += EVALUATION_CANDLES_PER_SLICE
        previous_end = item.get("evaluation_end_exclusive")
    if all_rows != list(range(800, 5800)):
        fail("evaluation_union_not_exact")
    if slices[0]["evaluation_start"] != manifest["evaluation_range"]["start"]:
        fail("evaluation_start_drift")
    expected_end_exclusive = utc(pd.Timestamp(manifest["evaluation_range"]["end"]) + timedelta(hours=1))
    if slices[-1]["evaluation_end_exclusive"] != expected_end_exclusive:
        fail("evaluation_end_drift")


def build_slices(manifest: dict[str, Any], frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    main = frames["BTC_USDT_USDT-1h-futures.feather"]
    main_dates = dates(main)
    evaluation_start = pd.Timestamp(manifest["evaluation_range"]["start"])
    evaluation_end = pd.Timestamp(manifest["evaluation_range"]["end"])
    evaluation_positions = main.index[(main_dates >= evaluation_start) & (main_dates <= evaluation_end)].tolist()
    if len(evaluation_positions) != TOTAL_EVALUATION_CANDLES or evaluation_positions != list(range(800, 5800)):
        fail("development_evaluation_row_set")
    by_name = {Path(item["path"]).name: item for item in manifest["files"]}
    result: list[dict[str, Any]] = []
    for number in range(1, SLICE_COUNT + 1):
        positions = evaluation_positions[(number - 1) * EVALUATION_CANDLES_PER_SLICE:number * EVALUATION_CANDLES_PER_SLICE]
        start = main_dates.loc[positions[0]]
        last = main_dates.loc[positions[-1]]
        end_exclusive = last + timedelta(hours=1)
        last_completed_4h_open = (start - timedelta(hours=INFORMATIVE_TIMEFRAME_HOURS)).floor("4h")
        warmup_start = last_completed_4h_open - timedelta(hours=INFORMATIVE_TIMEFRAME_HOURS * (STARTUP_CANDLES - 1))
        if warmup_start < pd.Timestamp(manifest["start"]):
            fail(f"slice_{number}_warmup_before_development")
        bindings: dict[str, Any] = {}
        for name, cadence in (
            ("BTC_USDT_USDT-1h-futures.feather", 1),
            ("BTC_USDT_USDT-4h-futures.feather", 4),
            ("BTC_USDT_USDT-8h-mark.feather", 8),
            ("BTC_USDT_USDT-8h-funding_rate.feather", 8),
        ):
            bindings[name] = stream_binding(by_name[name], frames[name], warmup_start, end_exclusive, cadence)
        four_h_dates = dates(frames["BTC_USDT_USDT-4h-futures.feather"])
        completed = four_h_dates[(four_h_dates >= warmup_start) & (four_h_dates + timedelta(hours=4) <= start)]
        if len(completed) != STARTUP_CANDLES:
            fail(f"slice_{number}_informative_warmup_count")
        one_h_warmup = main_dates[(main_dates >= warmup_start) & (main_dates < start)]
        if len(one_h_warmup) < STARTUP_CANDLES:
            fail(f"slice_{number}_main_warmup_count")
        item: dict[str, Any] = {
            "slice_number": number,
            "slice_id": f"ranging-short-ablation-s{number:02d}",
            "source_dataset_id": DATASET_ID,
            "source_dataset_aggregate_sha256": DATASET_AGGREGATE_SHA256,
            "pair": "BTC/USDT:USDT",
            "timeframe": "1h",
            "warmup_start": utc(warmup_start),
            "warmup_main_1h_candle_count": len(one_h_warmup),
            "warmup_completed_4h_informative_candle_count": len(completed),
            "evaluation_start": utc(start),
            "evaluation_end": utc(last),
            "evaluation_end_exclusive": utc(end_exclusive),
            "evaluation_first_candle_timestamp": utc(start),
            "evaluation_last_candle_timestamp": utc(last),
            "evaluation_row_start": int(positions[0]),
            "evaluation_row_end": int(positions[-1]),
            "evaluation_1h_candle_count": len(positions),
            "informative_4h_candle_count": bindings["BTC_USDT_USDT-4h-futures.feather"]["candle_count"],
            "mark_8h_candle_count": bindings["BTC_USDT_USDT-8h-mark.feather"]["candle_count"],
            "funding_8h_candle_count": bindings["BTC_USDT_USDT-8h-funding_rate.feather"]["candle_count"],
            "source_file_bindings": bindings,
            "intended_use": "branch_contribution_temporal_review",
            "validation_exposure": False,
        }
        semantic_payload = {key: value for key, value in item.items() if key != "source_file_bindings"}
        item["slice_semantic_fingerprint"] = fingerprint(semantic_payload)
        item["split_fingerprint"] = item["slice_semantic_fingerprint"]
        item["slice_aggregate_sha256"] = fingerprint({
            "slice_semantic_fingerprint": item["slice_semantic_fingerprint"],
            "source_file_bindings": bindings,
        })
        result.append(item)
    return result


def build_execution_matrix(slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for item in slices:
        for role in ("baseline", "candidate"):
            for repetition in ("RUN-A", "RUN-B"):
                row = {
                    "execution_id": f"{item['slice_id']}-{role}-{repetition.lower()}",
                    "slice_id": item["slice_id"],
                    "slice_semantic_fingerprint": item["slice_semantic_fingerprint"],
                    "slice_aggregate_sha256": item["slice_aggregate_sha256"],
                    "role": role,
                    "repetition": repetition,
                    "pair": "BTC/USDT:USDT",
                    "timeframe": "1h",
                    "strategy_class": "RegimeAwareV6" if role == "baseline" else "RegimeAware_Ablation_RangingShort_C1",
                    "strategy_path": STRATEGY_PATH if role == "baseline" else CANDIDATE_PATH,
                    "strategy_sha256": STRATEGY_SHA256 if role == "baseline" else CANDIDATE_SHA256,
                    "fresh_python_process": True,
                    "network_access": "forbidden",
                    "cache": "none",
                    "validation_accesses": 0,
                    "holdout_accesses": 0,
                    "status": "queued_unexecuted",
                    "execution_authorized": False,
                }
                row["execution_fingerprint"] = fingerprint(row)
                matrix.append(row)
    if len(matrix) != 16:
        fail("execution_matrix_count")
    return matrix


def compile_temporal_campaign(repo: Path, data_repo: Path, runtime_repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    proposal = load_document(repo / "research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json")
    approval = load_document(repo / APPROVAL_PATH)
    old_campaign = load_document(repo / OLD_CAMPAIGN_PATH)
    old_computed = fingerprint({key: value for key, value in old_campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
    if proposal_fingerprint(proposal) != proposal.get("semantic_fingerprint") or proposal["semantic_fingerprint"] != PROPOSAL_FINGERPRINT:
        fail("proposal_fingerprint_drift")
    if old_campaign.get("campaign_fingerprint") != OLD_CAMPAIGN_FINGERPRINT or old_computed != OLD_CAMPAIGN_FINGERPRINT:
        fail("old_campaign_fingerprint_drift")
    if approval.get("approval_status") != "approved_for_recompilation_only" or approval.get("execution_authorized") is not False:
        fail("recompilation_authority")
    protected = {
        CANDIDATE_PATH: CANDIDATE_SHA256,
        STRATEGY_PATH: STRATEGY_SHA256,
        BASE_PATH: BASE_SHA256,
        ROUTER_PATH: ROUTER_SHA256,
        CONSTITUTION_PATH: CONSTITUTION_SHA256,
        POLICY_PATH: POLICY_SHA256,
        RUNTIME_PATH: RUNTIME_SHA256,
    }
    for path, expected in protected.items():
        if sha256_file(repo / path) != expected:
            fail(f"protected_hash_drift:{path}")
    candidate_manifest = load_document(repo / CANDIDATE_MANIFEST)
    if candidate_manifest.get("source_sha256") != CANDIDATE_SHA256 or candidate_manifest.get("selected_ablation_unit") != "ranging_short_entry":
        fail("candidate_manifest_drift")
    candidate_shape = verify_candidate_shape(repo)
    exchange = load_document(repo / EXCHANGE_MANIFEST)
    if exchange.get("aggregate_sha256") != EXCHANGE_AGGREGATE_SHA256:
        fail("exchange_snapshot_drift")
    leverage_path = runtime_repo / LEVERAGE_TIER_PATH
    if not leverage_path.is_file() or sha256_file(leverage_path) != LEVERAGE_TIER_SHA256:
        fail("leverage_tier_drift")
    portable = verify_portable_fixture_pack(repo / "research/testing/fixture-packs/portable-baseline-v1")
    if portable.get("manifest_sha256") != PORTABLE_PACK_MANIFEST_SHA256 or portable.get("status") != "passed":
        fail("portable_fixture_pack_drift")
    manifest = load_document(repo / "research/data/snapshots" / DATASET_ID / "manifest.yaml")
    frames = verify_file_bindings(repo, data_repo, manifest)
    slices = build_slices(manifest, frames)
    slice_policy: dict[str, Any] = {
        "schema_version": "ranging-short-ablation-temporal-slice-policy-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "source_dataset": DATASET_ID,
        "source_dataset_manifest_sha256": DATASET_MANIFEST_SHA256,
        "source_dataset_aggregate_sha256": DATASET_AGGREGATE_SHA256,
        "source_region": "evaluation_only",
        "slice_count": SLICE_COUNT,
        "selection_mode": "sequential_equal_candle_count",
        "evaluation_1h_candles_per_slice": EVALUATION_CANDLES_PER_SLICE,
        "total_evaluation_1h_candles": TOTAL_EVALUATION_CANDLES,
        "allow_overlap": False,
        "allow_gaps": False,
        "allow_reordering": False,
        "validation_data_allowed": False,
        "warmup_policy": {
            "strategy_startup_candle_count": STARTUP_CANDLES,
            "main_timeframe": "1h",
            "informative_timeframe": "4h",
            "required_completed_informative_candles": STARTUP_CANDLES,
            "selection_rule": "earliest of the 200 completed 4h candles immediately preceding evaluation_start",
            "warmup_excluded_from_evaluation_count": True,
            "same_rule_for_every_slice": True,
        },
        "integrity": {
            "evaluation_rows": {"start": 800, "end": 5799, "count": 5000},
            "timestamp_gaps": 0,
            "duplicate_timestamps": 0,
            "slice_union_exact": True,
            "validation_exposure": False,
            "stage3e1_slice_reused": False,
        },
        "slices": slices,
    }
    validate_slice_policy(slice_policy, manifest)
    slice_policy["slice_policy_fingerprint"] = fingerprint(slice_policy)
    matrix = build_execution_matrix(slices)
    supersession = {
        "schema_version": "compiled-campaign-supersession-v1",
        "proposal_id": PROPOSAL_ID,
        "old_campaign_path": OLD_CAMPAIGN_PATH,
        "old_campaign_fingerprint": OLD_CAMPAIGN_FINGERPRINT,
        "execution_status": "superseded_before_execution",
        "reason": "exact_temporal_boundaries_not_frozen",
        "backtests_consumed": 0,
        "replacement_campaign_id": "stage4a-ranging-short-branch-decision-review-v1-temporal-v2",
        "old_campaign_artifact_sha256": sha256_file(repo / OLD_CAMPAIGN_PATH),
    }
    campaign = copy.deepcopy(old_campaign)
    campaign.update({
        "schema_version": "compiled-temporal-branch-contribution-campaign-v1",
        "campaign_id": supersession["replacement_campaign_id"],
        "compile_mode": "dry_run",
        "mode": "dry_run",
        "runner_type": "frozen_temporal_branch_contribution_review",
        "execution_authorized": False,
        "approval_granted": False,
        "current_authority": "compile_and_review_only",
        "scope": {
            "allowed_paths": [OUTPUT_DIR + "/**", SLICE_POLICY_PATH, APPROVAL_PATH, "scripts/compile_ranging_short_temporal_campaign.py", "tests/test_ranging_short_temporal_campaign_compilation.py"],
            "blocked_paths": ["strategies/**", "research/candidates/**", "research/data/holdout/**", "research/data/snapshots/futures-validation-*/**", "research/temporal/stage3e1-*/**", ".env", "secrets/**", "deploy/**"],
        },
        "frozen_inputs": {
            "proposal": {"path": "research/director/next-after-branch-ablation/proposals/ranging-short-branch-decision-review-v1.json", "fingerprint": PROPOSAL_FINGERPRINT},
            "recompilation_approval": {"path": APPROVAL_PATH, "sha256": canonical_text_sha256(repo / APPROVAL_PATH), "execution_authorized": False},
            "candidate": {"path": CANDIDATE_PATH, "class_name": "RegimeAware_Ablation_RangingShort_C1", "source_sha256": CANDIDATE_SHA256, "manifest_path": CANDIDATE_MANIFEST, "manifest_sha256": sha256_file(repo / CANDIDATE_MANIFEST), "ast_validation": candidate_shape, "modification_allowed": False},
            "formal_strategy": {"path": STRATEGY_PATH, "sha256": STRATEGY_SHA256, "modification_allowed": False},
            "formal_base": {"path": BASE_PATH, "sha256": BASE_SHA256, "modification_allowed": False},
            "router_contract": {"path": ROUTER_PATH, "sha256": ROUTER_SHA256},
            "constitution": {"path": CONSTITUTION_PATH, "sha256": CONSTITUTION_SHA256},
            "evaluation_policy": {"path": POLICY_PATH, "sha256": POLICY_SHA256, "modification_allowed": False},
            "runtime": {"path": RUNTIME_PATH, "sha256": RUNTIME_SHA256},
            "exchange_snapshot": {"path": EXCHANGE_MANIFEST, "manifest_sha256": canonical_text_sha256(repo / EXCHANGE_MANIFEST), "aggregate_sha256": EXCHANGE_AGGREGATE_SHA256},
            "leverage_tiers": {"path": LEVERAGE_TIER_PATH, "sha256": LEVERAGE_TIER_SHA256},
            "dataset": {"dataset_id": DATASET_ID, "manifest_path": f"research/data/snapshots/{DATASET_ID}/manifest.yaml", "manifest_sha256": DATASET_MANIFEST_SHA256, "aggregate_sha256": DATASET_AGGREGATE_SHA256, "access": "development_only"},
            "slice_policy": {"path": SLICE_POLICY_PATH, "fingerprint": slice_policy["slice_policy_fingerprint"]},
            "portable_fixture_pack": {"status": portable["status"], "file_count": portable["file_count"], "manifest_sha256": PORTABLE_PACK_MANIFEST_SHA256},
        },
        "budget": {
            "max_campaigns": 1,
            "max_experiments": 16,
            "max_total_attempts": 16,
            "max_consecutive_failures": 1,
            "max_retries_per_experiment": 0,
            "max_wall_clock_minutes": 240,
            "max_backtest_calls": 16,
            "max_candidates": 0,
            "max_validation_accesses": 0,
            "max_holdout_accesses": 0,
        },
        "experiment_queue": matrix,
        "stop_conditions": ["temporal_slice_compilation_failed", "temporal_ablation_reproducibility_failed", "proposal_or_campaign_fingerprint_drift", "protected_hash_drift", "Validation_or_Holdout_access", "Candidate_or_strategy_modification", "any_execution_failure", "human_stop"],
        "escalation_conditions": ["any boundary drift", "any fifth slice or ETH access", "Validation or Holdout request", "Candidate or strategy modification", "budget breach", "human_stop"],
        "artifact_requirements": ["per-slice reproducibility reports", "per-slice contribution reports", "cross-slice summary", "Registry event", "pending-human-review next Proposal"],
        "test_requirements": ["slice partition integrity", "stream coverage", "stable hashes", "supersession", "16-item unexecuted matrix", "Portable baseline", "readiness"],
        "acceptance_criteria": ["four exact Development-only slices are frozen", "4 x 1250 rows exactly cover Development evaluation", "16 executions remain queued_unexecuted", "no Backtest is run during compilation", "old Campaign is superseded before execution", "Candidate and formal strategy remain immutable"],
        "human_escalation_conditions": ["new Campaign fingerprint requires explicit human execution approval", "any slice boundary change", "any Validation/Holdout access", "any Candidate/formal strategy change"],
        "compiled_at": utc_now(),
        "supersedes": supersession,
        "temporal_branch_contribution_review_plan": {
            "research_unit": "ranging_short_entry",
            "pair": "BTC/USDT:USDT",
            "data_scope": "development_only",
            "slice_policy": slice_policy,
            "execution_matrix": matrix,
            "execution_matrix_count": 16,
            "delta_direction": "candidate_minus_baseline",
            "classification_taxonomy": ["branch_negative_contributor_temporally_consistent", "branch_positive_contributor_temporally_consistent", "branch_mixed_temporal_dependency", "branch_redundant_temporally_consistent", "branch_contribution_temporally_inconclusive", "temporal_ablation_execution_invalid"],
            "execution_boundary": {"campaign_executed": False, "backtests_consumed": 0, "candidate_created": False, "validation_accesses": 0, "holdout_accesses": 0, "automatic_followup": False},
        },
    })
    campaign.pop("ranging_short_branch_decision_review_plan", None)
    campaign["campaign_fingerprint"] = fingerprint({key: value for key, value in campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
    supersession_record = {
        **supersession,
        "replacement_campaign_fingerprint": campaign["campaign_fingerprint"],
    }
    metadata = {
        "schema_version": "temporal-campaign-compilation-metadata-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "campaign_id": campaign["campaign_id"],
        "campaign_fingerprint": campaign["campaign_fingerprint"],
        "compile_mode": "dry_run",
        "execution_authorized": False,
        "campaign_executed": False,
        "backtests_consumed": 0,
        "source_dataset_resolution": "read_only_external_worktree_with_exact_manifest_and_file_hashes",
        "slice_policy_fingerprint": slice_policy["slice_policy_fingerprint"],
        "old_campaign_superseded": supersession_record,
    }
    return campaign, slice_policy, metadata


def write_outputs(repo: Path, campaign: dict[str, Any], slice_policy: dict[str, Any], metadata: dict[str, Any]) -> None:
    output = repo / OUTPUT_DIR
    write_yaml(repo / SLICE_POLICY_PATH, slice_policy)
    write_yaml(output / "campaign.yaml", campaign)
    write_json(output / "experiment-queue.json", campaign["experiment_queue"])
    write_json(output / "compilation-metadata.json", metadata)
    write_json(output / "superseded-campaign.json", metadata["old_campaign_superseded"])
    write_json(output / "slice-integrity-audit.json", slice_policy["integrity"])
    write_json(output / "human-approval-summary.json", {
        "schema_version": "temporal-campaign-human-approval-summary-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "compiled_campaign_fingerprint": campaign["campaign_fingerprint"],
        "approval_status": "pending_human_execution_approval",
        "execution_authorized": False,
        "required_approval": {"exact_campaign_fingerprint": campaign["campaign_fingerprint"], "exact_slice_policy_fingerprint": slice_policy["slice_policy_fingerprint"], "backtest_calls": 16, "max_wall_clock_minutes": 240, "max_retries": 0, "validation_accesses": 0, "holdout_accesses": 0},
        "candidate_or_strategy_change_authorized": False,
    })
    lines = [
        "# Temporal Branch Contribution Campaign — Compilation Brief", "",
        f"- Proposal: `{PROPOSAL_ID}`", f"- Campaign fingerprint: `{campaign['campaign_fingerprint']}`",
        "- Compile mode: `dry_run`", "- Execution authorized: `false`", "- Backtests consumed: `0`", "",
        "## Frozen slices", "",
    ]
    for item in slice_policy["slices"]:
        lines.append(f"- `{item['slice_id']}`: warm-up `{item['warmup_start']}`; evaluation `{item['evaluation_start']}` to `{item['evaluation_end_exclusive']}`; rows `{item['evaluation_row_start']}..{item['evaluation_row_end']}`; hash `{item['slice_aggregate_sha256']}`")
    lines += ["", "## Human approval required", "", "Approve the exact new Campaign fingerprint and its 16-item matrix before any execution. Validation, Holdout, ETH, Candidate changes and formal-strategy changes remain forbidden.", ""]
    (output / "implementation-brief.md").write_text("\n".join(lines), encoding="utf-8")
    load_campaign(output / "campaign.yaml")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-repo", required=True, help="Read-only worktree containing the exact sealed BTC Development bytes")
    parser.add_argument("--runtime-repo", required=True, help="Read-only worktree containing the pinned Runtime leverage-tier asset")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    campaign, slice_policy, metadata = compile_temporal_campaign(repo, Path(args.data_repo), Path(args.runtime_repo))
    write_outputs(repo, campaign, slice_policy, metadata)
    print(json.dumps({"status": "compiled_unexecuted", "campaign_fingerprint": campaign["campaign_fingerprint"], "slice_policy_fingerprint": slice_policy["slice_policy_fingerprint"], "slice_count": len(slice_policy["slices"]), "execution_matrix_count": len(campaign["experiment_queue"]), "backtests_consumed": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
