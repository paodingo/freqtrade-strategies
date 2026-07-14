#!/usr/bin/env python3
"""Generate a small deterministic, evidence-based Research Proposal set."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

from research_director_common import (
    fingerprint,
    load_document,
    normalized_question,
    open_director_registry,
    proposal_fingerprint,
    sha256_file,
    utc_now,
    write_json,
    write_yaml,
)
from research_discovery_common import (
    DiscoveryError,
    artifact_fingerprint,
    assert_fixed_scope,
    validate_artifact,
)
import research_discovery_route as discovery_route
import research_discovery_trigger as discovery_trigger
from route_research_approval import route_proposal


CLOSED_THRESHOLD_MARKERS = {
    "ranging-threshold", "ranging_threshold", "adjacent-threshold", "adjacent_threshold",
    "rsi_min", "rsi_max", "adx_4h_max_long", "bb_percent_min",
}


def branch_closure_check(
    direction: str,
    state: dict[str, Any],
    satisfied_reopen_conditions: list[str] | None = None,
) -> dict[str, Any]:
    """Apply recorded closure conditions to a proposed research direction."""
    closure = next(
        (item for item in state.get("closed_branches", []) if item.get("closure_id") == "regime-aware-ranging-thresholds-v1"),
        None,
    )
    normalized = direction.lower()
    targets_closed_branch = any(marker in normalized for marker in CLOSED_THRESHOLD_MARKERS)
    if not closure or not targets_closed_branch:
        return {"checked": True, "blocked": False, "reason_code": None, "closure_id": closure.get("closure_id") if closure else None, "reopen_requested": False}
    recorded = set(closure.get("reopen_conditions") or [])
    satisfied = set(satisfied_reopen_conditions or [])
    met = sorted(recorded & satisfied)
    return {
        "checked": True,
        "blocked": not bool(met),
        "reason_code": None if met else "closed_branch_no_reopen_evidence",
        "closure_id": closure["closure_id"],
        "reopen_requested": True,
        "recorded_reopen_conditions_met": met,
    }


def evidence(path: str, claim: str) -> dict[str, str]:
    return {"path": path, "claim": claim}


def proposal_base(
    proposal_id: str,
    title: str,
    question: str,
    uncertainty: str,
    supporting: list[dict[str, str]],
    method: dict[str, Any],
    information_gain: tuple[float, str, str],
    risk_class: str,
    experiments: int,
    minutes: int,
    datasets: list[dict[str, Any]],
    runtime: dict[str, Any],
    policy: dict[str, Any],
    allowed_changes: list[str],
    required_artifacts: list[str],
    required_tests: list[str],
    mechanisms: list[str],
) -> dict[str, Any]:
    proposal: dict[str, Any] = {
        "schema_version": "research-proposal-v1",
        "proposal_id": proposal_id,
        "title": title,
        "research_question": question,
        "current_uncertainty": uncertainty,
        "supporting_evidence": supporting,
        "contradictory_evidence": [],
        "expected_information_gain": {"score": information_gain[0], "level": information_gain[1], "rationale": information_gain[2]},
        "proposed_method": method,
        "immutable_inputs": ["RegimeAwareV6 strategy hash", "Balanced Research Gate v1", "sealed runtime contracts", "branch closures"],
        "allowed_changes": allowed_changes,
        "forbidden_changes": ["strategy_change", "risk_change", "candidate_creation", "validation_access", "holdout_access", "live_or_private_api", "closed_threshold_research"],
        "required_datasets": datasets,
        "required_runtime": runtime,
        "required_policy": policy,
        "estimated_experiments": experiments,
        "estimated_wall_clock_minutes": minutes,
        "estimated_compute_cost": "low" if experiments <= 4 else "medium",
        "risk_class": risk_class,
        "contamination_risk": "none",
        "validation_requirement": "none",
        "holdout_requirement": "none",
        "branch_closure_reopen_check": {"checked": True, "blocked": False, "reason_code": None, "closure_id": "regime-aware-ranging-thresholds-v1", "reopen_requested": False},
        "duplicate_research_check": {"checked": True, "duplicate": False, "reason_code": None},
        "stop_conditions": ["evidence_conflict", "missing_immutable_input", "budget_exhausted", "scope_expansion_required", "information_gain_resolved"],
        "success_criteria": ["all claims trace to evidence", "result is reproducible", "no strategy or risk semantics changed"],
        "failure_does_not_imply": ["strategy_is_unprofitable", "closed_threshold_branch_should_reopen", "promotion_is_allowed"],
        "required_artifacts": required_artifacts,
        "required_tests": required_tests,
        "approval_requirement": "auto_approvable_future" if risk_class == "low" else "human_approval_required",
        "recommendation_confidence": min(0.99, max(0.0, information_gain[0] - 0.04)),
        "recommendation": "research_recommended",
        "referenced_variables": [],
        "referenced_mechanisms": mechanisms,
        "market_scope": {"exchange": "binance", "trading_mode": "futures", "baseline_pair": "BTC/USDT:USDT", "timeframe": "1h"},
        "data_scope": {"validation": False, "holdout": False, "sealed_development_only": True},
        "quality_checks": {"evidence_real": True, "verifiable": True, "budget_executable": True, "lower_risk_alternative_used": True},
    }
    proposal["research_question_fingerprint"] = fingerprint(normalized_question(question))
    proposal["semantic_fingerprint"] = proposal_fingerprint(proposal)
    return proposal


_DIRECTOR_REGISTRY = Path("research/registry/stage4a-director.db")
_DISCOVERY_OUTPUT_ROOT = Path("research/director/discovery-handoff")
_TERMINAL_HANDOFF_STATUSES = {"director_proposed", "director_rejected"}
_GOVERNED_DIRECTOR_REJECTIONS = {
    "closed_branch_no_reopen_evidence",
    "dataset_manifest_conflict",
    "dataset_not_trigger_authorized",
    "dataset_requirement_invalid",
    "director_risk_forbidden",
    "director_route_rejected",
    "duplicate_research_question",
    "evaluation_policy_conflict",
    "runtime_contract_conflict",
    "supporting_evidence_conflict",
    "supporting_evidence_insufficient",
}


def _canonical_repo_file(repo: Path, relative: object, reason_code: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise DiscoveryError(reason_code, "canonical repository path required")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative:
        raise DiscoveryError(reason_code, "canonical repository path required")
    return discovery_trigger._repo_regular_file(repo, path, reason_code, reason_code)


def _load_handoff_chain(
    repo: Path,
    handoff: dict[str, Any],
    state: dict[str, Any],
    constitution: dict[str, Any],
    registry_path: Path,
    connection: sqlite3.Connection | None = None,
) -> tuple[dict[str, object], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], sqlite3.Row]:
    if not isinstance(handoff, dict):
        raise DiscoveryError("handoff_schema_invalid", "object required")
    try:
        validate_artifact(repo, "research-direction-handoff.schema.json", handoff)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError("handoff_schema_invalid", type(exc).__name__) from exc
    if handoff["handoff_fingerprint"] != artifact_fingerprint(
        handoff, "handoff_fingerprint"
    ):
        raise DiscoveryError("handoff_fingerprint_conflict", "fingerprint mismatch")
    if handoff.get("execution_authorized") is not False:
        raise DiscoveryError("execution_authority_forbidden", "direction is not execution")

    run_id = str(handoff["discovery_run_id"])
    context = discovery_route._canonical_context(repo, run_id, registry_path)
    state_fingerprint, constitution_fingerprint = discovery_route._current_bindings(
        context, state, constitution
    )
    own_connection = connection is None
    db = connection or open_director_registry(registry_path)
    try:
        latest, critiques, shortlist = discovery_route._load_review_bindings(db, context)
        approval = discovery_route._load_existing_approval(db, context)
        if (
            approval is None
            or approval.get("decision") != "approved_for_director_handoff"
            or approval.get("reviewer_type") != "human_user"
        ):
            raise DiscoveryError("direction_not_approved", run_id)
        selected, idea, critique = discovery_route._resolve_selection(
            shortlist,
            latest,
            critiques,
            next(
                (
                    index
                    for index, item in enumerate(shortlist["ranked_ideas"], 1)
                    if item["idea_id"] == approval["selected_idea_id"]
                ),
                None,
            ),
        )
        if selected is None or idea is None or critique is None:
            raise DiscoveryError("approval_binding_conflict", run_id)

        canonical_handoff_path = context["run_root"] / "handoff.json"
        stored_handoff = discovery_route._load_json(
            canonical_handoff_path, "handoff_artifact_conflict"
        )
        validate_artifact(repo, "research-direction-handoff.schema.json", stored_handoff)
        if stored_handoff != handoff:
            raise DiscoveryError("handoff_artifact_conflict", "supplied handoff is not canonical")

        rows = db.execute(
            "SELECT handoff_fingerprint, run_id, idea_id, status, director_result_code, "
            "payload_json, created_at FROM research_discovery_handoffs "
            "WHERE run_id=? OR handoff_fingerprint=?",
            (run_id, handoff["handoff_fingerprint"]),
        ).fetchall()
        if len(rows) != 1:
            raise DiscoveryError("registry_handoff_conflict", run_id)
        row = rows[0]
        status = row["status"]
        result_code = row["director_result_code"]
        if status == "handed_to_director":
            if result_code is not None:
                raise DiscoveryError("registry_handoff_conflict", run_id)
        elif status in _TERMINAL_HANDOFF_STATUSES:
            if not isinstance(result_code, str) or not result_code:
                raise DiscoveryError("registry_handoff_conflict", run_id)
        else:
            raise DiscoveryError("registry_handoff_conflict", run_id)
        if (
            row["handoff_fingerprint"] != handoff["handoff_fingerprint"]
            or row["run_id"] != run_id
            or row["idea_id"] != idea["idea_id"]
            or json.loads(row["payload_json"]) != handoff
            or not isinstance(row["created_at"], str)
            or not row["created_at"]
        ):
            raise DiscoveryError("registry_handoff_conflict", run_id)
        discovery_route._require_exact_event(
            db, run_id, "handed_to_director", discovery_route._handoff_event(handoff)
        )

        idea_ref = (
            context["run_root"]
            / "ideas"
            / f"{idea['idea_id']}-v{idea['idea_version']}.json"
        ).relative_to(repo).as_posix()
        critique_ref = (
            context["run_root"] / "critiques" / f"{critique['critique_id']}.json"
        ).relative_to(repo).as_posix()
        approval_ref = (context["run_root"] / "approval.json").relative_to(repo).as_posix()
        exact = {
            "idea_ref": idea_ref,
            "critique_ref": critique_ref,
            "approval_ref": approval_ref,
            "idea_fingerprint": idea["semantic_fingerprint"],
            "critique_fingerprint": critique["critic_fingerprint"],
            "approval_fingerprint": approval["approval_fingerprint"],
            "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
            "research_state_fingerprint": state_fingerprint,
            "constitution_fingerprint": constitution_fingerprint,
            "research_question": idea["falsifiable_hypothesis"],
        }
        mismatches = sorted(key for key, value in exact.items() if handoff.get(key) != value)
        if mismatches:
            raise DiscoveryError("handoff_binding_conflict", ",".join(mismatches))
        if (
            selected.get("risk_class") != idea.get("risk_class")
            or selected.get("strategy_family") != idea.get("strategy_family")
            or selected.get("cost_class") != idea.get("estimated_cost", {}).get("compute_class")
        ):
            raise DiscoveryError("shortlist_binding_conflict", str(idea["idea_id"]))
        assert_fixed_scope(idea["fixed_scope_confirmation"])
        return context, idea, critique, approval, shortlist, row
    finally:
        if own_connection:
            db.close()


def _current_development_datasets(
    repo: Path,
    idea: dict[str, Any],
    state: dict[str, Any],
    context: dict[str, object],
) -> list[dict[str, Any]]:
    aliases = {
        "futures-dev-btc": (
            "BTC/USDT:USDT",
            "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
        ),
        "futures-dev-eth": (
            "ETH/USDT:USDT",
            "futures-dev-eth-usdt-usdt-20240101-20240830-v1",
        ),
    }
    requested = idea.get("required_datasets")
    if not isinstance(requested, list) or not requested or len(set(requested)) != len(requested):
        raise DiscoveryError("dataset_requirement_invalid", str(requested))
    approved_pairs = set(
        (state.get("allowed_research_scope") or {}).get(
            "human_approved_additional_pairs", []
        )
    )
    allowed_paths = set(context["allowed_sources"])
    resolved: list[dict[str, Any]] = []
    for requested_id in requested:
        if not isinstance(requested_id, str):
            raise DiscoveryError("dataset_requirement_invalid", "string id required")
        alias = aliases.get(requested_id)
        pair = alias[0] if alias else None
        exact_ids = {
            str(item.get("dataset_id"))
            for item in state.get("datasets", [])
            if isinstance(item, dict) and item.get("dataset_id") == requested_id
        }
        target_ids = exact_ids or ({alias[1]} if alias else {requested_id})
        matches = [
            item
            for item in state.get("datasets", [])
            if isinstance(item, dict)
            and (
                item.get("dataset_id") in target_ids
            )
            and item.get("sealed") is True
            and str(item.get("intended_use", "")).startswith("development")
            and item.get("agent_visibility") != "controlled"
            and "1h" in (item.get("timeframes") or [])
            and "4h" in (item.get("timeframes") or [])
        ]
        if pair == "BTC/USDT:USDT":
            matches = [item for item in matches if item.get("agent_visibility") == "full"]
        if pair == "ETH/USDT:USDT" and pair not in approved_pairs:
            matches = []
        if len(matches) != 1:
            raise DiscoveryError("dataset_manifest_conflict", requested_id)
        item = matches[0]
        path_value = item.get("path")
        if path_value not in allowed_paths:
            raise DiscoveryError("dataset_not_trigger_authorized", requested_id)
        path = _canonical_repo_file(repo, path_value, "dataset_manifest_conflict")
        if item.get("manifest_sha256") != sha256_file(path):
            raise DiscoveryError("dataset_manifest_conflict", requested_id)
        resolved.append(
            {
                "dataset_id": item["dataset_id"],
                "manifest_path": path_value,
                "manifest_sha256": item["manifest_sha256"],
                "access": "development_only",
            }
        )
    return resolved


def _current_runtime_and_policy(
    repo: Path, state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_rows = [
        item
        for item in state.get("runtime_contracts", [])
        if isinstance(item, dict)
        and item.get("path") == "research/runtime/freqtrade-runtime.yaml"
        and item.get("exists") is True
    ]
    if len(runtime_rows) != 1:
        raise DiscoveryError("runtime_contract_conflict", "freqtrade runtime")
    runtime_row = runtime_rows[0]
    runtime_path = _canonical_repo_file(
        repo, runtime_row.get("path"), "runtime_contract_conflict"
    )
    if runtime_row.get("sha256") != sha256_file(runtime_path):
        raise DiscoveryError("runtime_contract_conflict", "runtime hash")
    policy_row = state.get("evaluation_policy")
    if not isinstance(policy_row, dict) or policy_row.get("approval_status") != "approved":
        raise DiscoveryError("evaluation_policy_conflict", "approved policy required")
    policy_path = _canonical_repo_file(
        repo, policy_row.get("path"), "evaluation_policy_conflict"
    )
    if policy_row.get("file_sha256") != sha256_file(policy_path):
        raise DiscoveryError("evaluation_policy_conflict", "policy hash")
    return (
        {"path": runtime_row["path"], "sha256": runtime_row["sha256"]},
        {
            "path": policy_row["path"],
            "sha256": policy_row["file_sha256"],
            "approval_status": "approved",
        },
    )


def _state_question_fingerprints(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "research_question_fingerprint" and isinstance(item, str):
                found.add(item)
            elif key in {"question", "research_question", "falsifiable_hypothesis"} and isinstance(item, str):
                found.add(fingerprint(normalized_question(item)))
            else:
                found.update(_state_question_fingerprints(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_state_question_fingerprints(item))
    return found


def _reject_duplicate_question(
    question_fingerprint: str,
    state: dict[str, Any],
    registry_path: Path,
    handoff_fingerprint: str,
) -> None:
    if question_fingerprint in _state_question_fingerprints(state):
        raise DiscoveryError("duplicate_research_question", "current state")
    connection = open_director_registry(registry_path)
    try:
        rows = connection.execute(
            "SELECT payload_json FROM director_proposals"
        ).fetchall()
    finally:
        connection.close()
    for row in rows:
        try:
            proposal = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiscoveryError("director_registry_conflict", "proposal payload") from exc
        if (
            proposal.get("research_question_fingerprint") == question_fingerprint
            and proposal.get("discovery_handoff_fingerprint") != handoff_fingerprint
        ):
            raise DiscoveryError("duplicate_research_question", "Director Registry")


def proposal_from_discovery_handoff(
    repo: Path,
    handoff: dict[str, Any],
    state: dict[str, Any],
    constitution: dict[str, Any],
    *,
    registry_path: Path | None = None,
    _connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Convert one canonical governed discovery handoff without execution authority."""
    repo = discovery_trigger._lexical_absolute(repo)
    registry_path = Path(registry_path or (repo / _DIRECTOR_REGISTRY))
    context, idea, critique, approval, _, _ = _load_handoff_chain(
        repo, handoff, state, constitution, registry_path, _connection
    )
    risk_class = idea["risk_class"]
    if risk_class in {"high", "forbidden"}:
        raise DiscoveryError("director_risk_forbidden", str(risk_class))
    closure = branch_closure_check(
        f"{idea['falsifiable_hypothesis']} {idea['proposed_market_mechanism']}", state
    )
    if closure["blocked"]:
        raise DiscoveryError(str(closure["reason_code"]), str(idea["idea_id"]))
    question_fingerprint = fingerprint(normalized_question(idea["falsifiable_hypothesis"]))
    _reject_duplicate_question(
        question_fingerprint, state, registry_path, handoff["handoff_fingerprint"]
    )
    datasets = _current_development_datasets(repo, idea, state, context)
    runtime, policy = _current_runtime_and_policy(repo, state)

    proposal_id = f"discovery-{idea['idea_id']}-v{idea['idea_version']}"
    analysis_path = f"research/analysis/{proposal_id}/analysis.json"
    report_path = f"reports/audits/{proposal_id}/report.md"
    allowed_changes = [analysis_path, report_path]
    required_artifacts = [analysis_path, report_path]
    if risk_class == "medium":
        candidate_path = f"research/candidates/{proposal_id}/candidate-manifest.yaml"
        allowed_changes = ["new_strategy_branch", candidate_path, analysis_path, report_path]
        required_artifacts = [candidate_path, analysis_path, report_path]
    supporting = [
        {"path": ref["path"], "claim": ref["claim"]}
        for ref in idea["source_refs"]
        if isinstance(ref, dict) and "path" in ref
    ]
    if not supporting:
        raise DiscoveryError("supporting_evidence_insufficient", str(idea["idea_id"]))
    for item in supporting:
        _canonical_repo_file(repo, item["path"], "supporting_evidence_conflict")
    cost = idea["estimated_cost"]
    proposal = proposal_base(
        proposal_id,
        idea["title"],
        idea["falsifiable_hypothesis"],
        " ".join(idea["known_limitations"]),
        supporting,
        {
            "type": f"discovery_{idea['strategy_family']}_minimal_test",
            "steps": [idea["minimal_test_method"]],
            "comparison_baseline": idea["comparison_baseline"],
            "execution": "unexecuted_proposal_requires_separate_authorization",
        },
        (
            float(idea["expected_information_gain"]),
            "high" if float(idea["expected_information_gain"]) >= 0.75 else "medium",
            idea["novelty_vs_existing_research"],
        ),
        risk_class,
        int(cost["experiments"]),
        int(cost["wall_clock_minutes"]),
        datasets,
        runtime,
        policy,
        allowed_changes,
        required_artifacts,
        list(idea["falsification_conditions"]),
        [idea["strategy_family"], idea["proposed_market_mechanism"]],
    )
    proposal["contradictory_evidence"] = [
        {"claim": item} for item in idea["contradictory_evidence"]
    ] + [{"claim": critique["strongest_counterevidence"]}]
    proposal["estimated_compute_cost"] = cost["compute_class"]
    proposal["contamination_risk"] = idea["contamination_risk"]
    proposal["branch_closure_reopen_check"] = closure
    proposal["stop_conditions"] = list(idea["stop_conditions"])
    proposal["discovery_handoff_fingerprint"] = handoff["handoff_fingerprint"]
    proposal["discovery_approval_fingerprint"] = approval["approval_fingerprint"]
    proposal["discovery_critique_fingerprint"] = critique["critic_fingerprint"]
    proposal["execution_authorized"] = False
    proposal["semantic_fingerprint"] = proposal_fingerprint(proposal)
    route = route_proposal(proposal, constitution)
    if route["decision"] in {"forbidden", "insufficient_information"}:
        raise DiscoveryError("director_route_rejected", route["decision"])
    proposal["approval_requirement"] = route["decision"]
    proposal["execution_authorized"] = False
    proposal["semantic_fingerprint"] = proposal_fingerprint(proposal)
    try:
        jsonschema.Draft202012Validator(
            load_document(repo / "research/director/research-proposal.schema.json")
        ).validate(proposal)
    except Exception as exc:
        raise DiscoveryError("director_proposal_schema_invalid", type(exc).__name__) from exc
    return proposal


def rank(proposal: dict[str, Any], objective: str | None) -> float:
    information = float(proposal["expected_information_gain"]["score"])
    evidence_strength = min(1.0, len(proposal["supporting_evidence"]) / 3)
    relevance = 1.0 if not objective else (1.0 if any(token in proposal["research_question"].lower() for token in objective.lower().split()) else 0.7)
    feasibility = 1.0 if proposal["quality_checks"]["verifiable"] else 0.0
    risk_penalty = {"low": 0.0, "medium": 0.15, "high": 0.35, "forbidden": 1.0}[proposal["risk_class"]]
    cost_penalty = {"low": 0.0, "medium": 0.08, "high": 0.2}[proposal["estimated_compute_cost"]]
    contamination_penalty = {"none": 0.0, "low": 0.03, "medium": 0.1, "high": 0.25}[proposal["contamination_risk"]]
    return round(0.35 * information + 0.2 * evidence_strength + 0.2 * relevance + 0.15 * feasibility - 0.05 * risk_penalty - 0.03 * cost_penalty - 0.02 * contamination_penalty, 6)


def _discovery_output_path(repo: Path, value: str) -> Path:
    candidate = discovery_trigger._lexical_absolute(
        Path(value) if Path(value).is_absolute() else repo / value
    )
    try:
        relative = candidate.relative_to(repo)
    except ValueError as exc:
        raise DiscoveryError("director_output_invalid", "output must be in repository") from exc
    if (
        relative.parts[:3] != _DISCOVERY_OUTPUT_ROOT.parts
        or candidate.suffix != ".json"
        or any(part.lower() in {"candidate", "candidates", "campaign", "campaigns"} for part in relative.parts)
    ):
        raise DiscoveryError("director_output_invalid", relative.as_posix())
    discovery_trigger._assert_no_reparse_components(
        repo, candidate, "director_output_reparse_forbidden"
    )
    return candidate


def _handoff_director_run(
    handoff: dict[str, Any], proposal: dict[str, Any], created_at: str
) -> dict[str, Any]:
    return {
        "schema_version": "research-director-run-v1",
        "run_id": f"director-discovery-{handoff['handoff_fingerprint'][:16]}",
        "created_at": created_at,
        "state_fingerprint": handoff["research_state_fingerprint"],
        "constitution_status": "approved",
        "objective": proposal["research_question"],
        "budget": {
            "max_campaigns": 0,
            "max_experiments": proposal["estimated_experiments"],
            "max_wall_clock_minutes": proposal["estimated_wall_clock_minutes"],
            "max_validation_accesses": 0,
        },
        "risk_tolerance": proposal["risk_class"],
        "recommendation": "research_recommended",
        "recommendation_reason": "one governed discovery handoff converted without execution authority",
        "proposals": [proposal],
        "rejected_proposals": [],
        "ranking_factors": ["human_selected_discovery_direction"],
        "model_preference_used": False,
        "execution_authorized": False,
        "discovery_handoff_fingerprint": handoff["handoff_fingerprint"],
    }


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _recheck_handoff_files(
    repo: Path,
    handoff: dict[str, Any],
    state: dict[str, Any],
    constitution: dict[str, Any],
    proposal: dict[str, Any] | None = None,
    connection: sqlite3.Connection | None = None,
) -> None:
    current_state = load_document(repo / "research/director/current-research-state.json")
    current_constitution = load_document(
        repo / "research/governance/research-constitution.yaml"
    )
    if current_state != state or current_constitution != constitution:
        raise DiscoveryError("director_transaction_binding_conflict", "authority changed")
    if discovery_trigger._validate_state(current_state) != handoff["research_state_fingerprint"]:
        raise DiscoveryError("director_transaction_binding_conflict", "state fingerprint")
    if discovery_trigger._validate_constitution(current_constitution) != handoff["constitution_fingerprint"]:
        raise DiscoveryError("director_transaction_binding_conflict", "Constitution fingerprint")
    bindings = (
        ("handoff", (repo / "research/discovery/runs" / handoff["discovery_run_id"] / "handoff.json"), "research-direction-handoff.schema.json", "handoff_fingerprint", handoff["handoff_fingerprint"]),
        ("idea", _canonical_repo_file(repo, handoff["idea_ref"], "idea_artifact_conflict"), "research-idea.schema.json", "semantic_fingerprint", handoff["idea_fingerprint"]),
        ("critique", _canonical_repo_file(repo, handoff["critique_ref"], "critique_artifact_conflict"), "research-critique.schema.json", "critic_fingerprint", handoff["critique_fingerprint"]),
        ("approval", _canonical_repo_file(repo, handoff["approval_ref"], "approval_artifact_conflict"), "research-direction-approval.schema.json", "approval_fingerprint", handoff["approval_fingerprint"]),
    )
    for label, path, schema, field, expected in bindings:
        payload = load_document(path)
        validate_artifact(repo, schema, payload)
        if payload.get(field) != expected or payload.get(field) != artifact_fingerprint(payload, field):
            raise DiscoveryError("director_transaction_binding_conflict", label)
        if connection is not None:
            table, column = {
                "idea": ("research_discovery_ideas", "semantic_fingerprint"),
                "critique": ("research_discovery_critiques", "critic_fingerprint"),
                "approval": ("research_discovery_approvals", "approval_fingerprint"),
                "handoff": ("research_discovery_handoffs", "handoff_fingerprint"),
            }[label]
            rows = connection.execute(
                f"SELECT payload_json FROM {table} WHERE run_id=? AND {column}=?",
                (handoff["discovery_run_id"], expected),
            ).fetchall()
            if len(rows) != 1 or json.loads(rows[0]["payload_json"]) != payload:
                raise DiscoveryError("director_transaction_binding_conflict", f"{label} Registry")
    if proposal is None:
        return
    for dataset in proposal["required_datasets"]:
        path = _canonical_repo_file(
            repo, dataset["manifest_path"], "dataset_manifest_conflict"
        )
        if sha256_file(path) != dataset["manifest_sha256"]:
            raise DiscoveryError("director_transaction_binding_conflict", "dataset")
    for binding, reason in (
        (proposal["required_runtime"], "runtime"),
        (proposal["required_policy"], "policy"),
    ):
        path = _canonical_repo_file(repo, binding["path"], f"{reason}_contract_conflict")
        if sha256_file(path) != binding["sha256"]:
            raise DiscoveryError("director_transaction_binding_conflict", reason)


def _record_handoff_success(
    repo: Path,
    registry_path: Path,
    output: Path,
    handoff: dict[str, Any],
    run: dict[str, Any],
    state: dict[str, Any],
    constitution: dict[str, Any],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    discovery_trigger._assert_no_reparse_components(
        repo, output.parent, "director_output_reparse_forbidden"
    )
    payload_bytes = _json_bytes(run)
    staged_fd, staged_name = tempfile.mkstemp(
        prefix=".director-handoff-", suffix=".json", dir=output.parent
    )
    os.close(staged_fd)
    staged = Path(staged_name)
    staged.write_bytes(payload_bytes)
    published = False
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        handoff_rows = connection.execute(
            "SELECT handoff_fingerprint, run_id, status, director_result_code, payload_json "
            "FROM research_discovery_handoffs WHERE handoff_fingerprint=?",
            (handoff["handoff_fingerprint"],),
        ).fetchall()
        if len(handoff_rows) != 1:
            raise DiscoveryError("registry_handoff_conflict", str(handoff["discovery_run_id"]))
        handoff_row = handoff_rows[0]
        if (
            handoff_row["run_id"] != handoff["discovery_run_id"]
            or json.loads(handoff_row["payload_json"]) != handoff
        ):
            raise DiscoveryError("registry_handoff_conflict", str(handoff["discovery_run_id"]))

        run_json = json.dumps(run, sort_keys=True)
        proposal = run["proposals"][0]
        proposal_json = json.dumps(proposal, sort_keys=True)
        run_rows = connection.execute(
            "SELECT run_id, state_fingerprint, objective, risk_tolerance, budget_json, "
            "recommendation, payload_json, created_at FROM director_runs WHERE run_id=?",
            (run["run_id"],),
        ).fetchall()
        proposal_rows = connection.execute(
            "SELECT proposal_id, run_id, semantic_fingerprint, risk_class, information_gain, "
            "status, payload_json, created_at FROM director_proposals "
            "WHERE proposal_id=? OR semantic_fingerprint=?",
            (proposal["proposal_id"], proposal["semantic_fingerprint"]),
        ).fetchall()
        rejection_rows = connection.execute(
            "SELECT rejection_id FROM director_rejections WHERE run_id=?",
            (run["run_id"],),
        ).fetchall()
        event_payload = {
            "director_run_id": run["run_id"],
            "handoff_fingerprint": handoff["handoff_fingerprint"],
            "proposal_fingerprint": proposal["semantic_fingerprint"],
            "result_code": "proposal_created",
            "status": "director_proposed",
        }
        event_id = discovery_route._event_id(
            str(handoff["discovery_run_id"]), "director_handoff_result", event_payload
        )
        event_rows = connection.execute(
            "SELECT event_id, run_id, event_type, reason_code, payload_json, created_at "
            "FROM research_discovery_events WHERE event_id=? OR "
            "(run_id=? AND event_type='director_handoff_result')",
            (event_id, handoff["discovery_run_id"]),
        ).fetchall()

        terminal = handoff_row["status"] in _TERMINAL_HANDOFF_STATUSES
        if terminal:
            if (
                handoff_row["status"] != "director_proposed"
                or handoff_row["director_result_code"] != "proposal_created"
                or len(run_rows) != 1
                or len(proposal_rows) != 1
                or len(event_rows) != 1
                or rejection_rows
                or run_rows[0]["payload_json"] != run_json
                or proposal_rows[0]["payload_json"] != proposal_json
                or proposal_rows[0]["run_id"] != run["run_id"]
                or event_rows[0]["event_id"] != event_id
                or event_rows[0]["run_id"] != handoff["discovery_run_id"]
                or event_rows[0]["event_type"] != "director_handoff_result"
                or event_rows[0]["reason_code"] is not None
                or json.loads(event_rows[0]["payload_json"]) != event_payload
                or not output.is_file()
                or output.read_bytes() != payload_bytes
            ):
                raise DiscoveryError("director_replay_conflict", run["run_id"])
            connection.rollback()
            return
        if (
            handoff_row["status"] != "handed_to_director"
            or handoff_row["director_result_code"] is not None
            or run_rows
            or proposal_rows
            or event_rows
            or rejection_rows
            or os.path.lexists(output)
        ):
            raise DiscoveryError("director_registry_conflict", run["run_id"])

        os.link(staged, output)
        published = True
        _recheck_handoff_files(
            repo, handoff, state, constitution, proposal, connection
        )
        connection.execute(
            "INSERT INTO director_runs(run_id, state_fingerprint, objective, risk_tolerance, "
            "budget_json, recommendation, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run["run_id"], run["state_fingerprint"], run["objective"],
                run["risk_tolerance"], json.dumps(run["budget"], sort_keys=True),
                run["recommendation"], run_json, run["created_at"],
            ),
        )
        connection.execute(
            "INSERT INTO director_proposals(proposal_id, run_id, semantic_fingerprint, "
            "risk_class, information_gain, status, payload_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                proposal["proposal_id"], run["run_id"], proposal["semantic_fingerprint"],
                proposal["risk_class"], proposal["expected_information_gain"]["score"],
                "proposed_unapproved", proposal_json, run["created_at"],
            ),
        )
        updated = connection.execute(
            "UPDATE research_discovery_handoffs SET status='director_proposed', "
            "director_result_code='proposal_created' WHERE handoff_fingerprint=? "
            "AND status='handed_to_director' AND director_result_code IS NULL",
            (handoff["handoff_fingerprint"],),
        ).rowcount
        if updated != 1:
            raise DiscoveryError("registry_handoff_conflict", str(handoff["discovery_run_id"]))
        connection.execute(
            "INSERT INTO research_discovery_events(event_id, run_id, event_type, reason_code, "
            "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_id, handoff["discovery_run_id"], "director_handoff_result", None,
                json.dumps(event_payload, ensure_ascii=False, sort_keys=True), run["created_at"],
            ),
        )
        _recheck_handoff_files(
            repo, handoff, state, constitution, proposal, connection
        )
        connection.commit()
    except Exception:
        connection.rollback()
        if published:
            try:
                output.unlink()
            except OSError as cleanup_exc:
                raise DiscoveryError(
                    "director_output_cleanup_failed", output.name
                ) from cleanup_exc
        raise
    finally:
        connection.close()
        try:
            staged.unlink()
        except FileNotFoundError:
            pass


def _handoff_rejection_run(
    handoff: dict[str, Any], idea: dict[str, Any], reason_code: str, created_at: str
) -> dict[str, Any]:
    rejection = {
        "proposal_key": str(idea["idea_id"]),
        "reason_code": reason_code,
        "details": {
            "discovery_run_id": handoff["discovery_run_id"],
            "handoff_fingerprint": handoff["handoff_fingerprint"],
        },
    }
    return {
        "schema_version": "research-director-run-v1",
        "run_id": f"director-discovery-{handoff['handoff_fingerprint'][:16]}",
        "created_at": created_at,
        "state_fingerprint": handoff["research_state_fingerprint"],
        "constitution_status": "approved",
        "objective": handoff["research_question"],
        "budget": {
            "max_campaigns": 0,
            "max_experiments": 0,
            "max_wall_clock_minutes": 0,
            "max_validation_accesses": 0,
        },
        "risk_tolerance": str(idea["risk_class"]),
        "recommendation": "no_research_recommended",
        "recommendation_reason": reason_code,
        "proposals": [],
        "rejected_proposals": [rejection],
        "ranking_factors": ["governed_discovery_handoff_gates"],
        "model_preference_used": False,
        "execution_authorized": False,
        "discovery_handoff_fingerprint": handoff["handoff_fingerprint"],
    }


def _record_handoff_rejection(
    repo: Path,
    registry_path: Path,
    output: Path,
    handoff: dict[str, Any],
    run: dict[str, Any],
    state: dict[str, Any],
    constitution: dict[str, Any],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    discovery_trigger._assert_no_reparse_components(
        repo, output.parent, "director_output_reparse_forbidden"
    )
    payload_bytes = _json_bytes(run)
    staged_fd, staged_name = tempfile.mkstemp(
        prefix=".director-handoff-", suffix=".json", dir=output.parent
    )
    os.close(staged_fd)
    staged = Path(staged_name)
    staged.write_bytes(payload_bytes)
    published = False
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        handoff_rows = connection.execute(
            "SELECT handoff_fingerprint, run_id, status, director_result_code, payload_json "
            "FROM research_discovery_handoffs WHERE handoff_fingerprint=?",
            (handoff["handoff_fingerprint"],),
        ).fetchall()
        if len(handoff_rows) != 1:
            raise DiscoveryError("registry_handoff_conflict", str(handoff["discovery_run_id"]))
        handoff_row = handoff_rows[0]
        if (
            handoff_row["run_id"] != handoff["discovery_run_id"]
            or json.loads(handoff_row["payload_json"]) != handoff
        ):
            raise DiscoveryError("registry_handoff_conflict", str(handoff["discovery_run_id"]))
        run_json = json.dumps(run, sort_keys=True)
        rejection = run["rejected_proposals"][0]
        details_json = json.dumps(rejection["details"], sort_keys=True)
        run_rows = connection.execute(
            "SELECT run_id, payload_json FROM director_runs WHERE run_id=?",
            (run["run_id"],),
        ).fetchall()
        rejection_rows = connection.execute(
            "SELECT run_id, proposal_key, reason_code, details_json, created_at "
            "FROM director_rejections WHERE run_id=?",
            (run["run_id"],),
        ).fetchall()
        proposal_rows = connection.execute(
            "SELECT proposal_id FROM director_proposals WHERE run_id=?",
            (run["run_id"],),
        ).fetchall()
        event_payload = {
            "director_run_id": run["run_id"],
            "handoff_fingerprint": handoff["handoff_fingerprint"],
            "result_code": rejection["reason_code"],
            "status": "director_rejected",
        }
        event_id = discovery_route._event_id(
            str(handoff["discovery_run_id"]), "director_handoff_result", event_payload
        )
        event_rows = connection.execute(
            "SELECT event_id, run_id, event_type, reason_code, payload_json, created_at "
            "FROM research_discovery_events WHERE event_id=? OR "
            "(run_id=? AND event_type='director_handoff_result')",
            (event_id, handoff["discovery_run_id"]),
        ).fetchall()
        terminal = handoff_row["status"] in _TERMINAL_HANDOFF_STATUSES
        if terminal:
            if (
                handoff_row["status"] != "director_rejected"
                or handoff_row["director_result_code"] != rejection["reason_code"]
                or len(run_rows) != 1
                or len(rejection_rows) != 1
                or len(event_rows) != 1
                or proposal_rows
                or run_rows[0]["payload_json"] != run_json
                or rejection_rows[0]["proposal_key"] != rejection["proposal_key"]
                or rejection_rows[0]["reason_code"] != rejection["reason_code"]
                or rejection_rows[0]["details_json"] != details_json
                or event_rows[0]["event_id"] != event_id
                or event_rows[0]["reason_code"] != rejection["reason_code"]
                or json.loads(event_rows[0]["payload_json"]) != event_payload
                or not output.is_file()
                or output.read_bytes() != payload_bytes
            ):
                raise DiscoveryError("director_replay_conflict", run["run_id"])
            connection.rollback()
            return
        if (
            handoff_row["status"] != "handed_to_director"
            or handoff_row["director_result_code"] is not None
            or run_rows
            or rejection_rows
            or event_rows
            or proposal_rows
            or os.path.lexists(output)
        ):
            raise DiscoveryError("director_registry_conflict", run["run_id"])
        os.link(staged, output)
        published = True
        _recheck_handoff_files(repo, handoff, state, constitution, connection=connection)
        connection.execute(
            "INSERT INTO director_runs(run_id, state_fingerprint, objective, risk_tolerance, "
            "budget_json, recommendation, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run["run_id"], run["state_fingerprint"], run["objective"],
                run["risk_tolerance"], json.dumps(run["budget"], sort_keys=True),
                run["recommendation"], run_json, run["created_at"],
            ),
        )
        connection.execute(
            "INSERT INTO director_rejections(run_id, proposal_key, reason_code, details_json, "
            "created_at) VALUES (?, ?, ?, ?, ?)",
            (
                run["run_id"], rejection["proposal_key"], rejection["reason_code"],
                details_json, run["created_at"],
            ),
        )
        updated = connection.execute(
            "UPDATE research_discovery_handoffs SET status='director_rejected', "
            "director_result_code=? WHERE handoff_fingerprint=? "
            "AND status='handed_to_director' AND director_result_code IS NULL",
            (rejection["reason_code"], handoff["handoff_fingerprint"]),
        ).rowcount
        if updated != 1:
            raise DiscoveryError("registry_handoff_conflict", str(handoff["discovery_run_id"]))
        connection.execute(
            "INSERT INTO research_discovery_events(event_id, run_id, event_type, reason_code, "
            "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                event_id, handoff["discovery_run_id"], "director_handoff_result",
                rejection["reason_code"],
                json.dumps(event_payload, ensure_ascii=False, sort_keys=True), run["created_at"],
            ),
        )
        _recheck_handoff_files(repo, handoff, state, constitution, connection=connection)
        connection.commit()
    except Exception:
        connection.rollback()
        if published:
            try:
                output.unlink()
            except OSError as cleanup_exc:
                raise DiscoveryError(
                    "director_output_cleanup_failed", output.name
                ) from cleanup_exc
        raise
    finally:
        connection.close()
        try:
            staged.unlink()
        except FileNotFoundError:
            pass


def _run_handoff_cli(args: argparse.Namespace) -> int:
    repo = discovery_trigger._lexical_absolute(args.repo_root or Path.cwd())
    if not args.director_registry:
        raise DiscoveryError("director_registry_required", "--director-registry")
    registry_path = discovery_trigger._lexical_absolute(args.director_registry)
    handoff_path = discovery_trigger._lexical_absolute(
        Path(args.handoff) if Path(args.handoff).is_absolute() else repo / args.handoff
    )
    discovery_trigger._assert_no_reparse_components(
        repo, handoff_path, "handoff_path_reparse_forbidden"
    )
    try:
        relative_handoff = handoff_path.relative_to(repo)
    except ValueError as exc:
        raise DiscoveryError("handoff_path_invalid", "canonical handoff path required") from exc
    if (
        len(relative_handoff.parts) != 5
        or relative_handoff.parts[:3] != ("research", "discovery", "runs")
        or relative_handoff.name != "handoff.json"
    ):
        raise DiscoveryError("handoff_path_invalid", "canonical handoff path required")
    handoff = discovery_route._load_json(handoff_path, "handoff_artifact_conflict")
    if handoff.get("discovery_run_id") != relative_handoff.parts[3]:
        raise DiscoveryError("handoff_path_invalid", "run id does not match path")
    state_path = discovery_trigger._lexical_absolute(
        Path(args.state) if Path(args.state).is_absolute() else repo / args.state
    )
    constitution_path = discovery_trigger._lexical_absolute(
        Path(args.constitution)
        if Path(args.constitution).is_absolute()
        else repo / args.constitution
    )
    expected_state = repo / "research/director/current-research-state.json"
    expected_constitution = repo / "research/governance/research-constitution.yaml"
    if os.path.normcase(str(state_path)) != os.path.normcase(str(expected_state)):
        raise DiscoveryError("state_path_invalid", "canonical current state required")
    if os.path.normcase(str(constitution_path)) != os.path.normcase(
        str(expected_constitution)
    ):
        raise DiscoveryError(
            "constitution_path_invalid", "canonical approved Constitution required"
        )
    discovery_trigger._assert_no_reparse_components(
        repo, state_path, "state_path_reparse_forbidden"
    )
    discovery_trigger._assert_no_reparse_components(
        repo, constitution_path, "constitution_path_reparse_forbidden"
    )
    try:
        state = load_document(state_path)
    except Exception as exc:
        raise DiscoveryError("research_state_conflict", type(exc).__name__) from exc
    try:
        constitution = load_document(constitution_path)
    except Exception as exc:
        raise DiscoveryError("constitution_fingerprint_conflict", type(exc).__name__) from exc
    output = _discovery_output_path(repo, args.output)
    try:
        proposal = proposal_from_discovery_handoff(
            repo, handoff, state, constitution, registry_path=registry_path
        )
    except DiscoveryError as exc:
        if exc.reason_code not in _GOVERNED_DIRECTOR_REJECTIONS:
            raise
        _, idea, _, _, _, handoff_row = _load_handoff_chain(
            repo, handoff, state, constitution, registry_path
        )
        run = _handoff_rejection_run(
            handoff, idea, exc.reason_code, handoff_row["created_at"]
        )
        _record_handoff_rejection(
            repo, registry_path, output, handoff, run, state, constitution
        )
        print(json.dumps({
            "run_id": run["run_id"],
            "recommendation": run["recommendation"],
            "proposal_count": 0,
            "rejected_count": 1,
            "output": args.output,
        }, indent=2))
        return 0
    _, _, _, _, _, handoff_row = _load_handoff_chain(
        repo, handoff, state, constitution, registry_path
    )
    run = _handoff_director_run(handoff, proposal, handoff_row["created_at"])
    _record_handoff_success(
        repo, registry_path, output, handoff, run, state, constitution
    )
    print(json.dumps({
        "run_id": run["run_id"],
        "recommendation": run["recommendation"],
        "proposal_count": 1,
        "rejected_count": 0,
        "output": args.output,
    }, indent=2))
    return 0


def generate(state: dict[str, Any], constitution: dict[str, Any], objective: str | None, budget: dict[str, Any], risk_tolerance: str, max_proposals: int = 5) -> dict[str, Any]:
    if state.get("state_conflicts"):
        return {"recommendation": "no_research_recommended", "reason": "state_conflict", "proposals": [], "rejected_proposals": [], "state_fingerprint": state["state_fingerprint"]}
    runtime = {"path": "research/runtime/freqtrade-runtime.yaml", "sha256": next(item["sha256"] for item in state["runtime_contracts"] if item["path"].endswith("freqtrade-runtime.yaml"))}
    policy = {"path": state["evaluation_policy"]["path"], "sha256": state["evaluation_policy"]["file_sha256"], "approval_status": state["evaluation_policy"]["approval_status"]}
    development = next(item for item in state["datasets"] if item.get("dataset_id") == "futures-dev-btc-usdt-usdt-20240101-20240830-v2")
    proposals = [
        proposal_base(
            "cross-pair-data-readiness-audit-v1",
            "Cross-pair generalization data readiness audit",
            "Can the next cross-pair generalization campaign be frozen and validated without acquiring or inspecting Validation/Holdout data?",
            "Temporal consistency is established for BTC, while no sealed non-BTC strategy dataset is currently available.",
            [evidence("research/temporal/stage3e1-temporal-comparison.json", "Classification is temporally_consistent and recommendation is cross_pair_generalization."), evidence("research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml", "Sealed futures market metadata is available for pair eligibility checks."), evidence("research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml", "Current sealed strategy-ranking dataset is BTC-only.")],
            {"type": "read_only_data_scope_audit", "steps": ["derive pair eligibility from sealed metadata", "define frozen data requirements", "produce no-download provisioning decision"], "execution": "no_campaign_run"},
            (0.92, "high", "It resolves the explicit Stage 3E recommendation while preventing premature cross-pair execution."),
            "low", 3, 35,
            [{"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "manifest_only"}, {"dataset_id": "binance-usdm-futures-2025-8-demo", "access": "sealed_metadata_only"}],
            runtime, policy,
            ["research/director/compiled/**", "reports/audits/cross-pair-data-readiness/**"],
            ["pair-eligibility.json", "frozen-data-requirements.yaml", "readiness-decision.json"],
            ["data scope guard", "no network test", "no Validation/Holdout access test"],
            ["cross_pair_generalization", "data_provisioning"],
        ),
        proposal_base(
            "exit-logic-structure-audit-v1",
            "Exit logic structure and attribution audit",
            "Which existing exit mechanisms explain regime-specific loss concentration without changing strategy or risk semantics?",
            "Signal attribution found no exit deltas, while temporal slices show materially different loss and exit-reason distributions.",
            [evidence("research/analysis/stage3d3a-final-report.json", "Recorded exit_count is zero in prior signal-delta attribution."), evidence("research/temporal/stage3e1-temporal-comparison.json", "Temporal slices contain different exit-reason and risk distributions."), evidence("research/runtime/freqtrade-2025-8-signal-execution-contract.yaml", "Execution semantics are frozen and auditable.")],
            {"type": "read_only_exit_attribution", "steps": ["map existing exit reasons to temporal regimes", "audit first-trigger and time-stop semantics", "produce structural findings only"], "execution": "no_backtest"},
            (0.81, "high", "Existing evidence leaves exit-specific attribution unresolved and the audit requires no mutation."),
            "low", 4, 45,
            [{"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "existing_artifacts_only"}],
            runtime, policy,
            ["research/director/compiled/**", "research/analysis/exit-logic-audit/**"],
            ["exit-attribution.json", "exit-structure-audit.md"],
            ["determinism test", "no strategy diff test", "artifact hash test"],
            ["exit_logic", "first_trigger_semantics"],
        ),
        proposal_base(
            "regime-branch-structure-audit-v1",
            "Regime branch structure audit",
            "Are directionality and regime activation imbalances structural rather than addressable by another threshold search?",
            "The threshold branch is closed, but condition-graph and temporal directionality evidence can still support a read-only structural diagnosis.",
            [evidence("research/closures/regime-aware-ranging-thresholds-v1.yaml", "Single-threshold search is closed and may not be reopened."), evidence("research/analysis/regime-aware-condition-graph.json", "A machine-readable branch condition graph exists."), evidence("research/temporal/stage3e1-temporal-comparison.json", "Long/short coverage differs across temporal slices.")],
            {"type": "read_only_condition_graph_audit", "steps": ["compare branch activation by regime", "separate structural gaps from threshold-local effects", "emit no-mutation recommendation"], "execution": "no_backtest"},
            (0.73, "medium", "It distinguishes structural research from prohibited adjacent-threshold work."),
            "low", 3, 30,
            [{"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "existing_analysis_only"}],
            runtime, policy,
            ["research/director/compiled/**", "research/analysis/regime-branch-audit/**"],
            ["regime-branch-structure.json", "structural-vs-threshold-decision.md"],
            ["closed branch guard test", "condition graph integrity test"],
            ["regime_branch_structure"],
        ),
    ]
    if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") is True:
        eth_dataset = next(
            item for item in state["datasets"]
            if item.get("dataset_id") == "futures-dev-eth-usdt-usdt-20240101-20240830-v1"
        )
        proposals.append(
            proposal_base(
                "strategy-family-reassessment-v1",
                "Strategy family reassessment evidence audit",
                "Does the combined BTC temporal evidence and reproducible ETH development result justify reassessing the current regime-aware strategy family before any new Candidate design?",
                "RegimeAwareV6 is temporally consistent on BTC and reproducible on ETH, but ETH development behavior is materially weaker and no approved evidence synthesis has tested whether the current family assumptions remain the best research direction.",
                [
                    evidence("research/temporal/stage3e1-temporal-comparison.json", "BTC behavior is temporally consistent across four frozen slices."),
                    evidence("research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "ETH execution behavior is reproducible but does not prove profitable or policy-qualified generalization."),
                    evidence("research/analysis/regime-branch-audit/regime-branch-structure.json", "Directionality rotates across slices and no current strategy mutation is warranted."),
                ],
                {
                    "type": "strategy_family_reassessment_read_only",
                    "steps": [
                        "build an evidence matrix for the current regime-aware family assumptions",
                        "compare retain, retire, and future-family research directions without implementing any family",
                        "produce a human-review decision packet with explicit no-execution boundaries",
                    ],
                    "execution": "no_backtest_no_candidate_no_strategy_change",
                },
                (0.88, "high", "It resolves whether future research should remain inside the current family before any higher-risk implementation work is authorized."),
                "medium", 3, 60,
                [
                    {"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "existing_analysis_only"},
                    {"dataset_id": eth_dataset["dataset_id"], "manifest_sha256": eth_dataset["manifest_sha256"], "access": "existing_analysis_only"},
                ],
                runtime, policy,
                ["research/director/compiled/strategy-family-reassessment-v1/**", "research/analysis/strategy-family-reassessment/**", "reports/audits/strategy-family-reassessment/**"],
                ["family-evidence-matrix.json", "strategy-family-reassessment-decision.md", "human-review-packet.json"],
                ["evidence traceability test", "no strategy or Candidate diff test", "no backtest or protected-data access test"],
                ["strategy_family_reassessment", "new_strategy_branch"],
            )
        )
    if (state.get("strategy_family_reassessment") or {}).get("decision") == "restructure_family_worth_studying":
        eth_dataset = next(item for item in state["datasets"] if item.get("dataset_id") == "futures-dev-eth-usdt-usdt-20240101-20240830-v1")
        proposals.append(
            proposal_base(
                "regime-conditioned-branch-factorization-v1",
                "Regime-conditioned branch factorization study",
                "Can one explicitly approved structural Candidate isolate shared regime routing from direction-specific entry branches and explain the BTC/ETH behavior gap without reopening closed threshold or exit research?",
                "The family reassessment identified one untested structural hypothesis with high information value, but no Candidate or comparative development evidence exists.",
                [
                    evidence("research/analysis/strategy-family-reassessment/family-evidence-matrix.json", "The evidence matrix identifies unresolved shared-router versus direction-branch contribution."),
                    evidence("research/analysis/strategy-family-reassessment/human-review-packet.json", "Human review packet selects branch factorization as the unique priority structural direction."),
                    evidence("research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json", "ETH behavior is reproducible but materially weaker than the BTC reference."),
                ],
                {
                    "type": "new_strategy_branch_single_structural_candidate",
                    "steps": ["design one branch-factorized Candidate", "run fresh-process development-only BTC and ETH comparisons", "attribute changes by regime and direction branch"],
                    "execution": "future_candidate_and_development_backtest_requires_human_approval",
                },
                (0.91, "high", "It directly tests the only unresolved structural mechanism while holding risk, thresholds, exits, Runtime and data fixed."),
                "medium", 3, 120,
                [
                    {"dataset_id": development["dataset_id"], "manifest_sha256": development["manifest_sha256"], "access": "development_only_after_human_approval"},
                    {"dataset_id": eth_dataset["dataset_id"], "manifest_sha256": eth_dataset["manifest_sha256"], "access": "development_only_after_human_approval"},
                ],
                runtime, policy,
                ["new_strategy_branch", "new_candidate", "research/candidates/regime-conditioned-branch-factorization-v1/**", "research/analysis/regime-conditioned-branch-factorization/**", "reports/audits/regime-conditioned-branch-factorization/**"],
                ["candidate-manifest.yaml", "branch-attribution.json", "btc-eth-development-comparison.json", "human-decision-report.md"],
                ["single Candidate identity test", "fresh-process reproducibility test", "no threshold/exit/risk diff test", "no Validation/Holdout access test"],
                ["new_strategy_branch", "regime_router", "direction_specific_entry_branches"],
            )
        )
    threshold_check = branch_closure_check("ranging-threshold-neighbor-search", state)
    rejected = [
        {"proposal_key": "ranging-threshold-neighbor-search", "reason_code": threshold_check["reason_code"], "details": threshold_check},
        {"proposal_key": "repeat-temporal-generalization-profile", "reason_code": "duplicate_research_question", "details": {"existing_evidence": "research/temporal/stage3e1-temporal-comparison.json"}},
        {"proposal_key": "direct-cross-pair-backtest", "reason_code": "duplicate_research_question" if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") else "insufficient_data", "details": {"completed_dataset": (state.get("eth_cross_pair_generalization") or {}).get("dataset_id"), "missing": None if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") else "sealed non-BTC strategy dataset", "lower_risk_alternative": "cross-pair-data-readiness-audit-v1"}},
        {"proposal_key": "automatic-risk-parameter-search", "reason_code": "forbidden_by_constitution", "details": {"risk_out_of_scope": True}},
    ]
    if (state.get("stage4b1_execution") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "cross-pair-data-readiness-audit-v1"]
        rejected.append({"proposal_key": "cross-pair-data-readiness-audit-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-cross-pair-data-readiness-audit-v1", "result_code": (state.get("stage4b1_execution") or {}).get("result_code")}})
    if (state.get("exit_logic_structure_audit") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "exit-logic-structure-audit-v1"]
        rejected.append({"proposal_key": "exit-logic-structure-audit-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-exit-logic-structure-audit-v1", "result_code": (state.get("exit_logic_structure_audit") or {}).get("result_code")}})
    if (state.get("regime_branch_structure_audit") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "regime-branch-structure-audit-v1"]
        rejected.append({"proposal_key": "regime-branch-structure-audit-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-regime-branch-structure-audit-v1", "result_code": (state.get("regime_branch_structure_audit") or {}).get("result_code")}})
    if (state.get("eth_cross_pair_generalization") or {}).get("campaign_executed") is True:
        rejected.append({"proposal_key": "eth-cross-pair-generalization-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-eth-cross-pair-generalization-v1", "result_code": (state.get("eth_cross_pair_generalization") or {}).get("result_code")}})
    if (state.get("strategy_family_reassessment") or {}).get("campaign_executed") is True:
        proposals = [item for item in proposals if item["proposal_id"] != "strategy-family-reassessment-v1"]
        rejected.append({"proposal_key": "strategy-family-reassessment-v1", "reason_code": "duplicate_research_question", "details": {"completed_campaign": "stage4a-strategy-family-reassessment-v1", "result_code": (state.get("strategy_family_reassessment") or {}).get("decision")}})
    max_experiments = min(int(budget.get("max_experiments", 20)), int(constitution["budget_limits"]["max_experiments"]))
    proposals = [item for item in proposals if item["estimated_experiments"] <= max_experiments]
    if risk_tolerance == "low":
        proposals = [item for item in proposals if item["risk_class"] == "low"]
    for item in proposals:
        item["ranking_score"] = rank(item, objective)
        item["approval_route_preview"] = route_proposal(item, constitution)["decision"]
    proposals.sort(key=lambda item: (-item["ranking_score"], item["semantic_fingerprint"], item["proposal_id"]))
    proposals = proposals[:max_proposals]
    recommendation = "research_recommended" if proposals else "no_research_recommended"
    run = {
        "schema_version": "research-director-run-v1",
        "run_id": f"director-run-{fingerprint({'state': state['state_fingerprint'], 'objective': objective, 'budget': budget, 'risk': risk_tolerance})[:16]}",
        "created_at": utc_now(),
        "state_fingerprint": state["state_fingerprint"],
        "constitution_status": constitution.get("status"),
        "objective": objective,
        "budget": budget,
        "risk_tolerance": risk_tolerance,
        "recommendation": recommendation,
        "recommendation_reason": "ranked evidence-based proposals available" if proposals else "no proposal passed closure, duplication, data, risk and information-gain gates",
        "proposals": proposals,
        "rejected_proposals": rejected,
        "ranking_factors": ["expected_information_gain", "evidence_strength", "objective_relevance", "validation_feasibility", "risk", "cost", "contamination_risk", "duplication_penalty"],
        "model_preference_used": False,
        "execution_authorized": False,
    }
    return run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", default="research/director/current-research-state.json")
    parser.add_argument("--constitution", default="research/governance/research-constitution.yaml")
    parser.add_argument("--objective")
    parser.add_argument("--budget", default='{"max_campaigns": 1, "max_experiments": 20, "max_wall_clock_minutes": 120, "max_validation_accesses": 0}')
    parser.add_argument("--risk-tolerance", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--max-proposals", type=int, default=5)
    parser.add_argument("--output", default="research/director/proposals/director-run.json")
    parser.add_argument("--director-registry")
    parser.add_argument("--handoff")
    parser.add_argument("--repo-root")
    args = parser.parse_args(argv)
    if args.handoff:
        try:
            return _run_handoff_cli(args)
        except DiscoveryError as exc:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "reason_code": exc.reason_code,
                        "detail": "governed discovery handoff rejected",
                    },
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
    state = load_document(args.state)
    constitution = load_document(args.constitution)
    budget = json.loads(args.budget)
    run = generate(state, constitution, args.objective, budget, args.risk_tolerance, args.max_proposals)
    write_json(args.output, run)
    proposal_dir = Path(args.output).parent
    for proposal in run["proposals"]:
        write_json(proposal_dir / f"{proposal['proposal_id']}.json", proposal)
        write_yaml(proposal_dir / f"{proposal['proposal_id']}.yaml", proposal)
    if args.director_registry:
        connection = open_director_registry(args.director_registry)
        connection.execute(
            "INSERT OR REPLACE INTO director_runs(run_id, state_fingerprint, objective, risk_tolerance, budget_json, recommendation, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (run["run_id"], run["state_fingerprint"], run["objective"], run["risk_tolerance"], json.dumps(run["budget"], sort_keys=True), run["recommendation"], json.dumps(run, sort_keys=True), run["created_at"]),
        )
        for proposal in run["proposals"]:
            connection.execute(
                "INSERT OR REPLACE INTO director_proposals(proposal_id, run_id, semantic_fingerprint, risk_class, information_gain, status, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (proposal["proposal_id"], run["run_id"], proposal["semantic_fingerprint"], proposal["risk_class"], proposal["expected_information_gain"]["score"], "proposed_unapproved", json.dumps(proposal, sort_keys=True), run["created_at"]),
            )
        connection.execute("DELETE FROM director_rejections WHERE run_id=?", (run["run_id"],))
        for rejection in run["rejected_proposals"]:
            connection.execute(
                "INSERT INTO director_rejections(run_id, proposal_key, reason_code, details_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (run["run_id"], rejection["proposal_key"], rejection["reason_code"], json.dumps(rejection["details"], sort_keys=True), run["created_at"]),
            )
        connection.commit()
        connection.close()
    print(json.dumps({"run_id": run["run_id"], "recommendation": run["recommendation"], "proposal_count": len(run["proposals"]), "rejected_count": len(run["rejected_proposals"]), "output": args.output}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
