#!/usr/bin/env python3
"""Deterministic helpers for research discovery artifacts and ranking."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import jsonschema

from research_director_common import fingerprint, load_document, write_json


SCHEMA_VERSIONS = {
    "research-trigger.schema.json": "research-trigger-v1",
    "research-idea.schema.json": "research-idea-v1",
    "research-critique.schema.json": "research-critique-v1",
    "research-shortlist.schema.json": "research-shortlist-v1",
    "research-direction-approval.schema.json": "research-direction-approval-v1",
    "research-direction-handoff.schema.json": "research-direction-handoff-v1",
}

FINGERPRINT_EXCLUSIONS = {
    "trigger_fingerprint": frozenset({"trigger_fingerprint", "created_at", "decided_at"}),
    "semantic_fingerprint": frozenset({"semantic_fingerprint", "title", "created_at", "decided_at"}),
    "critic_fingerprint": frozenset({"critic_fingerprint", "created_at", "decided_at"}),
    "shortlist_fingerprint": frozenset({"shortlist_fingerprint", "created_at", "decided_at"}),
    "approval_fingerprint": frozenset({"approval_fingerprint", "created_at", "decided_at"}),
    "handoff_fingerprint": frozenset({"handoff_fingerprint", "created_at", "decided_at"}),
}


class DiscoveryError(RuntimeError):
    def __init__(self, reason_code: str, detail: str):
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code


def artifact_fingerprint(payload: dict[str, object], fingerprint_field: str) -> str:
    excluded = FINGERPRINT_EXCLUSIONS.get(fingerprint_field)
    if excluded is None:
        raise DiscoveryError(
            "fingerprint_field_invalid",
            f"unsupported fingerprint field: {fingerprint_field}",
        )
    return fingerprint({key: value for key, value in payload.items() if key not in excluded})


def validate_artifact(repo: Path, schema_filename: str, payload: dict[str, object]) -> None:
    expected_version = SCHEMA_VERSIONS.get(schema_filename)
    if expected_version is None:
        raise DiscoveryError(
            "schema_not_allowed",
            f"schema filename is not allowlisted: {schema_filename}",
        )

    schema_path = repo / "research/discovery/schemas" / schema_filename
    try:
        schema = load_document(schema_path)
    except Exception as exc:
        message = str(exc).replace(str(schema_path), schema_filename)
        message = message.replace(schema_path.as_posix(), schema_filename)
        raise DiscoveryError(
            "schema_load_failed",
            f"{schema_filename}: {type(exc).__name__}: {message}",
        ) from exc

    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        path = _json_path(exc.absolute_schema_path)
        raise DiscoveryError(
            "schema_invalid",
            f"{schema_filename} path={path}: {exc.message}",
        ) from exc

    properties = schema.get("properties")
    version_schema = properties.get("schema_version") if isinstance(properties, dict) else None
    actual_version = version_schema.get("const") if isinstance(version_schema, dict) else None
    if actual_version != expected_version:
        raise DiscoveryError(
            "schema_version_mismatch",
            f"{schema_filename}: expected {expected_version!r}, got {actual_version!r}",
        )

    try:
        jsonschema.Draft202012Validator(schema).validate(payload)
    except jsonschema.ValidationError as exc:
        path = _json_path(exc.absolute_path)
        raise DiscoveryError(
            "artifact_validation_failed",
            f"{schema_filename} path={path}: {exc.message}",
        ) from exc
    except Exception as exc:
        raise DiscoveryError(
            "artifact_validation_failed",
            f"{schema_filename} path=$: {type(exc).__name__}: {exc}",
        ) from exc


def _json_path(parts: Iterable[object]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


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
    actual_keys = set(scope)
    expected_keys = set(expected)
    if actual_keys != expected_keys:
        missing = sorted(str(key) for key in expected_keys - actual_keys)
        extra = sorted(str(key) for key in actual_keys - expected_keys)
        raise DiscoveryError(
            "fixed_scope_violation",
            f"scope keys must match exactly; missing={missing!r}, extra={extra!r}",
        )
    for key, value in expected.items():
        if type(scope.get(key)) is not type(value) or scope.get(key) != value:
            reason = "validation_forbidden" if key == "validation_access" else "fixed_scope_violation"
            raise DiscoveryError(reason, f"{key} must equal {value!r}")


def validate_sources(source_refs: list[dict[str, object]], repo: Path) -> str:
    allowed_classes = {"A", "B", "C"}
    required_external = {
        "canonical_url",
        "publisher_type",
        "retrieved_at",
        "content_fingerprint",
        "staleness_assessment",
        "licensing_constraints",
    }
    classes: set[str] = set()
    repo_root = repo.resolve()
    for index, item in enumerate(source_refs):
        if not isinstance(item, dict):
            raise DiscoveryError(
                "source_class_invalid",
                f"source_refs[{index}] must be a source mapping",
            )
        source_class = item.get("source_class")
        if not isinstance(source_class, str) or source_class not in allowed_classes:
            raise DiscoveryError(
                "source_class_invalid",
                f"source_refs[{index}].source_class must be A, B, or C",
            )
        classes.add(source_class)

        claim = item.get("claim")
        if not isinstance(claim, str) or not claim.strip():
            raise DiscoveryError(
                "source_claim_missing",
                f"source_refs[{index}].claim must be a non-empty string",
            )

        if source_class == "A":
            raw_path = item.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise DiscoveryError("source_missing", f"source_refs[{index}].path")
            relative_path = Path(raw_path)
            if relative_path.is_absolute() or ".." in relative_path.parts:
                raise DiscoveryError("source_missing", raw_path)
            path = (repo_root / relative_path).resolve()
            if not path.is_relative_to(repo_root) or not path.is_file():
                raise DiscoveryError("source_missing", raw_path)
        else:
            incomplete = sorted(
                field
                for field in required_external
                if not isinstance(item.get(field), str) or not str(item[field]).strip()
            )
            if incomplete:
                raise DiscoveryError(
                    "external_source_metadata_incomplete",
                    f"source_refs[{index}] missing or empty: {', '.join(incomplete)}",
                )

    if not classes.intersection({"A", "B"}):
        raise DiscoveryError("class_c_only", "at least one Class A or B source is required")
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
