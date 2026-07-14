#!/usr/bin/env python3
"""Deterministic helpers for research discovery artifacts and ranking."""

from __future__ import annotations

from pathlib import Path

import jsonschema

from research_director_common import fingerprint, load_document, write_json


class DiscoveryError(RuntimeError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def artifact_fingerprint(payload: dict[str, object], fingerprint_field: str) -> str:
    excluded = {fingerprint_field, "created_at", "decided_at"}
    return fingerprint({key: value for key, value in payload.items() if key not in excluded})


def validate_artifact(repo: Path, schema_filename: str, payload: dict[str, object]) -> None:
    schema = load_document(repo / "research/discovery/schemas" / schema_filename)
    jsonschema.Draft202012Validator(schema).validate(payload)


def assert_fixed_scope(scope: dict[str, object]) -> None:
    expected = {
        "exchange": "binance",
        "market": "USD-M Futures",
        "margin_mode": "isolated",
        "primary_timeframe": "1h",
        "informative_timeframes": ["4h"],
        "development_only": True,
        "risk_parameters_unchanged": True,
        "new_dataset": False,
        "validation_access": False,
        "holdout_access": False,
    }
    for key, value in expected.items():
        if scope.get(key) != value:
            reason = "validation_forbidden" if key == "validation_access" else "fixed_scope_violation"
            raise DiscoveryError(reason, f"{key} must equal {value!r}")


def validate_sources(source_refs: list[dict[str, object]], repo: Path) -> str:
    classes = {str(item.get("source_class")) for item in source_refs}
    if not classes.intersection({"A", "B"}):
        raise DiscoveryError("class_c_only", "at least one Class A or B source is required")
    required_external = {"canonical_url", "publisher_type", "retrieved_at", "claim", "content_fingerprint", "staleness_assessment", "licensing_constraints"}
    for item in source_refs:
        source_class = str(item.get("source_class"))
        if source_class == "A" and item.get("path"):
            path = (repo / str(item["path"])).resolve()
            if not path.is_relative_to(repo.resolve()) or not path.is_file():
                raise DiscoveryError("source_missing", str(item["path"]))
        elif not required_external.issubset(item):
            raise DiscoveryError("external_source_metadata_incomplete", str(item.get("canonical_url")))
    return "includes_A" if "A" in classes else "B_without_A"


def score_idea(idea: dict[str, object], critique: dict[str, object], policy: dict[str, object]) -> float:
    if critique["verdict"] != "pass":
        raise DiscoveryError("critic_not_passed", str(idea["idea_id"]))
    ranking_inputs = critique["ranking_inputs"]
    base = sum(float(policy["weights"][key]) * float(ranking_inputs[key]) for key in policy["weights"])
    source_key = critique["source_verification"]["highest_class"]
    source_penalty_key = "includes_A" if source_key == "A" else "B_without_A" if source_key == "B" else "C_only"
    penalty_values = (
        policy["penalties"]["risk"][idea["risk_class"]],
        policy["penalties"]["cost"][idea["estimated_cost"]["compute_class"]],
        policy["penalties"]["contamination"][idea["contamination_risk"]],
        policy["penalties"]["sources"][source_penalty_key],
    )
    if "reject" in penalty_values:
        raise DiscoveryError("ranking_policy_reject", str(idea["idea_id"]))
    return round(base - sum(float(value) for value in penalty_values), 6)


def rank_eligible(items: list[tuple[dict[str, object], dict[str, object]]], policy: dict[str, object]) -> list[dict[str, object]]:
    risk_order = {"low": 0, "medium": 1, "high": 2, "forbidden": 3}
    cost_order = {"low": 0, "medium": 1, "high": 2}
    ranked = []
    for idea, critique in items:
        if critique["verdict"] != "pass":
            continue
        try:
            final_score = score_idea(idea, critique, policy)
        except DiscoveryError:
            continue
        if final_score >= float(policy["shortlist_threshold"]):
            ranked.append({"idea_id": idea["idea_id"], "idea_fingerprint": idea["semantic_fingerprint"], "critique_fingerprint": critique["critic_fingerprint"], "strategy_family": idea["strategy_family"], "risk_class": idea["risk_class"], "cost_class": idea["estimated_cost"]["compute_class"], "final_score": final_score})
    ranked.sort(key=lambda item: (-item["final_score"], risk_order[item["risk_class"]], cost_order[item["cost_class"]], item["idea_fingerprint"]))
    return ranked[: int(policy["max_shortlist"])]


TRANSITIONS = {
    "discovered": {"critic_rejected", "criticized", "revision_exhausted", "out_of_v1_scope", "insufficient_source_evidence", "data_readiness_required"},
    "criticized": {"shortlisted", "critic_rejected"},
    "shortlisted": {"human_approved", "rejected", "deferred", "no_research_recommended", "fingerprint_invalidated"},
    "human_approved": {"handed_to_director", "fingerprint_invalidated"},
    "handed_to_director": {"converted", "director_rejected"},
}


def validate_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise DiscoveryError("illegal_transition", f"{current} -> {target}")


def write_immutable_json(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        existing = load_document(path)
        if fingerprint(existing) != fingerprint(payload):
            raise DiscoveryError("immutable_artifact_conflict", path.as_posix())
        return
    write_json(path, payload)
