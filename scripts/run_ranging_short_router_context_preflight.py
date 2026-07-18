#!/usr/bin/env python3
"""Run the mandatory Development-only coverage gate before router-context Backtests."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from export_director_registry import export_registry
from protected_manifest_hash import validate_protected_manifests
from ranging_short_router_context import (
    build_context_contract,
    context_contract_fingerprint,
)
from research_director_common import (
    load_document,
    open_director_registry,
    sha256_file,
    write_json,
)


PROPOSAL_ID = "ranging-short-router-carry-context-review-v1"
CAMPAIGN_ID = "stage4a-ranging-short-router-carry-context-review-v1"
PROPOSAL_FINGERPRINT = (
    "0def1fcab8671e6f43c6f66d1e84716ea0d76fd54e995825a1b066548a34bd3d"
)
CAMPAIGN_FINGERPRINT = (
    "26ad2ab3e756b8a0b9f7c63bc269d5a9c3028d87a3659b7bfa797fcf08f93330"
)
CONTEXT_FINGERPRINT = (
    "77f0cc0f52818fde63cb9e9bdd8b2703fc0d79e38ce0ec0d39bcc3a5d5b5ec7c"
)
SLICE_POLICY_FINGERPRINT = (
    "bdd0944e67f62a5fd6b70b1d66fc2c373ee8ecd42d3a84ea410f6337612856d4"
)
DATASET_ID = "futures-dev-btc-usdt-usdt-20240101-20240830-v2"
PAIR = "BTC/USDT:USDT"
PREFIX = "BTC_USDT_USDT"
CANDIDATE_CLASS = "RegimeAware_RouterCarryContext_C1"
CANDIDATE_SOURCE = Path(
    "research/candidates/ranging-short-router-carry-context-review-v1/1/"
    "RegimeAware_RouterCarryContext_C1.py"
)
CANDIDATE_SHA256 = (
    "1e680538152cb0dd73626ca0e5e6e27be83d09aeec0d7b99f13ed00a1e80382b"
)
CANDIDATE_MANIFEST = Path(
    "research/candidates/ranging-short-router-carry-context-review-v1/1/"
    "candidate-manifest.json"
)
CANDIDATE_MANIFEST_SHA256 = (
    "d539e6d8a8d0e734739d6a49e279ed9430b4676ace954d94317a0de92242a013"
)
CAMPAIGN_PATH = Path(
    "research/director/compiled/ranging-short-router-carry-context-review-v1/"
    "campaign.yaml"
)
SLICE_POLICY_PATH = Path(
    "research/temporal/ranging-short-ablation-temporal-slices-v1.yaml"
)
APPROVAL_PATH = Path(
    "research/governance/approvals/"
    "ranging-short-router-carry-context-review-v1-execution-approval.json"
)
REQUEST_PATH = Path(
    "research/governance/approvals/"
    "ranging-short-router-carry-context-review-v1-execution-request.json"
)
OUTPUT_PATH = Path(
    "research/analysis/ranging-short-router-carry-context-review-v1/"
    "context-coverage-preflight.json"
)
AUTHORIZATION_PATH = Path(
    "research/director/compiled/ranging-short-router-carry-context-review-v1/"
    "execution/router-context-execution-authorization.json"
)
STOP_PATH = Path(
    "research/analysis/ranging-short-router-carry-context-review-v1/"
    "campaign-stopped.json"
)
STOP_REPORT_PATH = Path(
    "research/analysis/ranging-short-router-carry-context-review-v1/"
    "coverage-stop-report.md"
)
REGISTRY_PATH = Path("research/registry/stage4a-director.db")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
FORMAL_HASHES = {
    "strategies/RegimeAwareV6.py": (
        "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509"
    ),
    "strategies/regime_aware_base.py": (
        "8feaebff14b5e8c537ec310b44b2b1d448db20be1388e3aca51da15b306275f9"
    ),
    "strategies/regime_detector.py": (
        "c5ba98011ebe1ab5a7378d41be2b0ed4b0aaae693b05ca3cc8e5b535274890f3"
    ),
}


class RouterContextPreflightInvalid(RuntimeError):
    """Raised when immutable authority or input bindings drift."""


def write_json_lf(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    )


def _in_window(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    timestamps = pd.to_datetime(frame["date"], utc=True)
    return frame.loc[
        (timestamps >= pd.Timestamp(start)) & (timestamps < pd.Timestamp(end))
    ].copy()


def _load_candidate(repo: Path):
    source = repo / CANDIDATE_SOURCE
    spec = importlib.util.spec_from_file_location("router_context_candidate", source)
    if spec is None or spec.loader is None:
        raise RouterContextPreflightInvalid("candidate_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, CANDIDATE_CLASS)


def validate_authority(repo: Path) -> dict[str, bool]:
    campaign = load_document(repo / CAMPAIGN_PATH)
    approval = load_document(repo / APPROVAL_PATH)
    request = load_document(repo / REQUEST_PATH)
    manifest = load_document(repo / CANDIDATE_MANIFEST)
    contract = build_context_contract(repo)
    checks = {
        "proposal_identity": (
            campaign["proposal_id"] == approval["proposal_id"] == PROPOSAL_ID
            and campaign["proposal_fingerprint"]
            == approval["proposal_fingerprint"]
            == PROPOSAL_FINGERPRINT
        ),
        "campaign_identity": (
            campaign["campaign_id"] == CAMPAIGN_ID
            and campaign["campaign_fingerprint"]
            == approval["compiled_campaign_fingerprint"]
            == CAMPAIGN_FINGERPRINT
        ),
        "conditional_human_approval": (
            approval["approval_status"] == "approved_conditionally"
            and approval["approver_type"] == "human_user"
            and approval["candidate_creation_authorized"] is True
            and approval["coverage_preflight_authorized"] is True
            and approval["backtest_execution_authorized_only_if_coverage_passes"]
            is True
        ),
        "request_binding": (
            approval["request_id"] == request["request_id"]
            and sha256_file(repo / REQUEST_PATH) == approval["request_sha256"]
        ),
        "development_only": (
            approval["data_access"]
            == {
                "development_only": True,
                "validation": "forbidden",
                "holdout": "forbidden",
            }
        ),
        "budget": (
            approval["budget"]
            == {
                "max_candidates": 1,
                "max_backtest_calls": 16,
                "max_wall_clock_minutes": 240,
                "max_retries": 0,
            }
        ),
        "context_contract": (
            context_contract_fingerprint(contract)
            == approval["context_contract_fingerprint"]
            == CONTEXT_FINGERPRINT
        ),
        "slice_policy": (
            load_document(repo / SLICE_POLICY_PATH)["slice_policy_fingerprint"]
            == SLICE_POLICY_FINGERPRINT
        ),
        "candidate_source": (
            sha256_file(repo / CANDIDATE_SOURCE)
            == manifest["source_sha256"]
            == approval["candidate"]["source_sha256"]
            == CANDIDATE_SHA256
        ),
        "candidate_manifest": (
            sha256_file(repo / CANDIDATE_MANIFEST)
            == approval["candidate"]["manifest_sha256"]
            == CANDIDATE_MANIFEST_SHA256
            and manifest["candidate_count"] == 1
            and manifest["context_contract_fingerprint"] == CONTEXT_FINGERPRINT
        ),
        "formal_sources": all(
            sha256_file(repo / path) == expected
            for path, expected in FORMAL_HASHES.items()
        ),
        "protected_manifests": validate_protected_manifests(repo)["passed"],
        "no_threshold_or_router_change": (
            approval["threshold_search_allowed"] is False
            and approval["router_modification_allowed"] is False
            and approval["formal_strategy_modification_allowed"] is False
        ),
    }
    if not all(checks.values()):
        raise RouterContextPreflightInvalid(
            "router_context_preflight_authority_invalid:"
            + json.dumps(checks, sort_keys=True)
        )
    return checks


def evaluate_slice(
    repo: Path, candidate_class: type, slice_spec: dict[str, Any]
) -> dict[str, Any]:
    data_root = repo / "research/data/snapshots" / DATASET_ID / "data/futures"

    class DataProvider:
        def current_whitelist(self) -> list[str]:
            return [PAIR]

        def get_pair_dataframe(
            self, pair: str, timeframe: str, candle_type: str = "futures"
        ) -> pd.DataFrame:
            if pair != PAIR or timeframe != "4h" or candle_type != "futures":
                raise RouterContextPreflightInvalid(
                    "unauthorized_coverage_instrumentation_input"
                )
            informative = pd.read_feather(
                data_root / f"{PREFIX}-4h-futures.feather"
            )
            return _in_window(
                informative,
                slice_spec["warmup_start"],
                slice_spec["evaluation_end_exclusive"],
            )

    raw = pd.read_feather(data_root / f"{PREFIX}-1h-futures.feather")
    raw = _in_window(
        raw,
        slice_spec["warmup_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    strategy = candidate_class({})
    strategy.dp = DataProvider()
    frame = strategy.populate_indicators(raw.copy(), {"pair": PAIR})
    frame = strategy.populate_entry_trend(frame, {"pair": PAIR})
    frame = _in_window(
        frame,
        slice_spec["evaluation_start"],
        slice_spec["evaluation_end_exclusive"],
    )
    if len(frame) != slice_spec["evaluation_1h_candle_count"]:
        raise RouterContextPreflightInvalid(
            f"coverage_slice_row_count_mismatch:{slice_spec['slice_id']}:{len(frame)}"
        )
    context = frame["research_router_context"].astype(bool)
    pre_gate = frame["research_ranging_short_entry_pre_gate"].astype(bool)
    intersection = frame[
        "research_router_context_pre_gate_intersection"
    ].astype(bool)
    return {
        "slice_id": slice_spec["slice_id"],
        "split_fingerprint": slice_spec["split_fingerprint"],
        "evaluation_start": slice_spec["evaluation_start"],
        "evaluation_end_exclusive": slice_spec["evaluation_end_exclusive"],
        "evaluation_rows": len(frame),
        "raw_ranging_signal_true": int(
            frame["research_router_context_raw_ranging_signal"].sum()
        ),
        "context_true": int(context.sum()),
        "context_false": int((~context).sum()),
        "ranging_short_pre_gate": int(pre_gate.sum()),
        "context_pre_gate_intersection": int(intersection.sum()),
        "candidate_remaining_ranging_short": int((pre_gate & ~context).sum()),
    }


def run_preflight(repo: Path) -> dict[str, Any]:
    checks = validate_authority(repo)
    policy = load_document(repo / SLICE_POLICY_PATH)
    candidate_class = _load_candidate(repo)
    slices = [evaluate_slice(repo, candidate_class, item) for item in policy["slices"]]
    totals = {
        field: sum(item[field] for item in slices)
        for field in (
            "evaluation_rows",
            "raw_ranging_signal_true",
            "context_true",
            "context_false",
            "ranging_short_pre_gate",
            "context_pre_gate_intersection",
            "candidate_remaining_ranging_short",
        )
    }
    both_context_states = totals["context_true"] > 0 and totals["context_false"] > 0
    intersection_sufficient = totals["context_pre_gate_intersection"] >= 1
    passed = both_context_states and intersection_sufficient
    return {
        "schema_version": "ranging-short-router-context-coverage-preflight-v1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "campaign_id": CAMPAIGN_ID,
        "compiled_campaign_fingerprint": CAMPAIGN_FINGERPRINT,
        "context_contract_fingerprint": CONTEXT_FINGERPRINT,
        "slice_policy_fingerprint": SLICE_POLICY_FINGERPRINT,
        "dataset_id": DATASET_ID,
        "data_access": {
            "development_only": True,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        },
        "candidate": {
            "class_name": CANDIDATE_CLASS,
            "path": CANDIDATE_SOURCE.as_posix(),
            "source_sha256": CANDIDATE_SHA256,
            "manifest_path": CANDIDATE_MANIFEST.as_posix(),
            "manifest_sha256": CANDIDATE_MANIFEST_SHA256,
        },
        "authority_checks": checks,
        "gate": {
            "both_context_states_required": True,
            "context_pre_gate_intersection_min": 1,
            "both_context_states_observed": both_context_states,
            "intersection_sufficient": intersection_sufficient,
            "passed": passed,
            "failure_code": None if passed else "router_context_coverage_insufficient",
        },
        "slices": slices,
        "totals": totals,
        "backtest_execution_authorized": passed,
        "backtest_calls": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "formal_strategy_modified": False,
        "router_modified": False,
        "threshold_search_run": False,
    }


def execution_authorization(preflight: dict[str, Any]) -> dict[str, Any]:
    passed = preflight["gate"]["passed"]
    return {
        "schema_version": "router-context-execution-authorization-v1",
        "authorization_id": "ranging-short-router-carry-context-review-v1-execution-1",
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "approved_compiled_fingerprint": CAMPAIGN_FINGERPRINT,
        "context_contract_fingerprint": CONTEXT_FINGERPRINT,
        "candidate_source_path": CANDIDATE_SOURCE.as_posix(),
        "candidate_source_sha256": CANDIDATE_SHA256,
        "coverage_preflight_path": OUTPUT_PATH.as_posix(),
        "coverage_gate_passed": passed,
        "execution_authorized": passed,
        "status": "authorized" if passed else "stopped_pre_backtest",
        "reason_code": None if passed else "router_context_coverage_insufficient",
        "max_backtest_calls": 16 if passed else 0,
        "max_retries": 0,
        "validation_accesses_authorized": 0,
        "holdout_accesses_authorized": 0,
        "automatic_followup_execution_allowed": False,
    }


def record_registry(repo: Path, preflight: dict[str, Any]) -> None:
    completed_at = "2026-07-18T10:16:54+00:00"
    approval = load_document(repo / APPROVAL_PATH)
    authorization = load_document(repo / AUTHORIZATION_PATH)
    stopped = load_document(repo / STOP_PATH)
    run_id = "ranging-short-router-carry-context-review-v1-coverage-preflight-1"
    connection = open_director_registry(repo / REGISTRY_PATH)
    connection.execute(
        "INSERT OR REPLACE INTO proposal_selection_events("
        "proposal_id,proposal_fingerprint,approval_status,approver_type,approved_at,payload_json"
        ") VALUES(?,?,?,?,?,?)",
        (
            PROPOSAL_ID,
            PROPOSAL_FINGERPRINT,
            approval["approval_status"],
            approval["approver_type"],
            completed_at,
            json.dumps(approval, sort_keys=True),
        ),
    )
    connection.execute(
        "INSERT OR REPLACE INTO campaign_execution_authorizations("
        "authorization_id,campaign_id,approved_compiled_fingerprint,proposal_id,"
        "execution_authorized,payload_json,authorized_at) VALUES(?,?,?,?,?,?,?)",
        (
            authorization["authorization_id"],
            CAMPAIGN_ID,
            CAMPAIGN_FINGERPRINT,
            PROPOSAL_ID,
            0,
            json.dumps(authorization, sort_keys=True),
            completed_at,
        ),
    )
    connection.execute(
        "INSERT OR REPLACE INTO research_campaign_runs("
        "run_id,campaign_id,proposal_id,status,result_code,campaign_executed,"
        "candidate_created,strategy_modified,validation_accesses,holdout_accesses,"
        "payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            CAMPAIGN_ID,
            PROPOSAL_ID,
            stopped["status"],
            stopped["reason_code"],
            0,
            1,
            0,
            0,
            0,
            json.dumps(stopped, sort_keys=True),
            completed_at,
        ),
    )
    assets = (
        CANDIDATE_SOURCE,
        CANDIDATE_MANIFEST,
        REQUEST_PATH,
        APPROVAL_PATH,
        OUTPUT_PATH,
        AUTHORIZATION_PATH,
        STOP_PATH,
        STOP_REPORT_PATH,
    )
    for path in assets:
        connection.execute(
            "INSERT OR REPLACE INTO research_campaign_assets("
            "asset_id,run_id,artifact_type,path,sha256,created_at) VALUES(?,?,?,?,?,?)",
            (
                f"{run_id}:{path.as_posix()}",
                run_id,
                "campaign_evidence",
                path.as_posix(),
                sha256_file(repo / path),
                completed_at,
            ),
        )
    connection.commit()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    connection.close()
    if integrity != "ok":
        raise RouterContextPreflightInvalid("registry_integrity_failed")
    write_json(repo / REGISTRY_EXPORT_PATH, export_registry(str(repo / REGISTRY_PATH)))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--record-registry", action="store_true")
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        result = run_preflight(repo)
        if args.write:
            write_json_lf(repo / OUTPUT_PATH, result)
            write_json_lf(
                repo / AUTHORIZATION_PATH, execution_authorization(result)
            )
        if args.record_registry:
            record_registry(repo, result)
    except RouterContextPreflightInvalid as exc:
        print(json.dumps({"status": "router_context_execution_invalid", "detail": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    if args.require_pass and not result["gate"]["passed"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
