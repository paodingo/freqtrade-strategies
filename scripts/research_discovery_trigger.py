#!/usr/bin/env python3
"""Prepare an idempotent, provider-neutral research discovery run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
from pathlib import Path

import jsonschema

from research_director_common import (
    ensure_director_schema,
    fingerprint,
    load_document,
    utc_now,
)
from research_discovery_common import (
    DiscoveryError,
    validate_artifact,
    write_immutable_json,
)


ALLOWED_EVENTS = {
    "campaign_completed",
    "branch_closed",
    "director_no_research",
    "manual_request",
}

STATE_PATH = Path("research/director/current-research-state.json")
CONSTITUTION_PATH = Path("research/governance/research-constitution.yaml")
SOURCE_POLICY_PATH = Path("research/discovery/policy/source-policy.yaml")
IDEA_SCHEMA_PATH = Path("research/discovery/schemas/research-idea.schema.json")
TRIGGER_SCHEMA_PATH = Path("research/discovery/schemas/research-trigger.schema.json")
RESEARCHER_PROMPT_PATH = Path("research/discovery/prompts/researcher.md")
BASELINE_PAIR = "BTC/USDT:USDT"
SUPPORTED_ADDITIONAL_PAIRS = (
    "ETH/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
)
ADDITIONAL_PAIR_APPROVAL_PATHS = {
    "ETH/USDT:USDT": (
        "research/governance/approvals/"
        "eth-cross-pair-generalization-v1-approval.json"
    ),
    "BNB/USDT:USDT": (
        "research/governance/approvals/"
        "bnb-xrp-development-descriptive-research-scope-v1-approval.json"
    ),
    "XRP/USDT:USDT": (
        "research/governance/approvals/"
        "bnb-xrp-development-descriptive-research-scope-v1-approval.json"
    ),
}

EVIDENCE_SECTIONS = (
    "allowed_research_scope",
    "closed_branches",
    "evaluation_policy",
    "fixed_harness_defects",
    "harness_capabilities",
    "invalidated_research",
    "possible_next_directions",
    "proposal_history",
    "unresolved_research_questions",
    "open_source_knowledge",
)

FORBIDDEN_PATH_PARTS = {
    "candidate",
    "candidates",
    "execution",
    "holdout",
    "live",
    "private",
    "runner",
    "runners",
    "secret",
    "secrets",
    "strategies",
    "validation",
}

EXPECTED_SOURCE_POLICY = {
    "schema_version": "research-source-policy-v1",
    "classes": {
        "A": [
            "repository_frozen_data",
            "completed_research_artifact",
            "research_registry",
            "branch_closure",
            "approved_governance",
            "official_exchange_documentation",
        ],
        "B": [
            "peer_reviewed_paper",
            "reputable_preprint",
            "textbook",
            "institutional_research_report",
        ],
        "C": [
            "public_strategy_repository",
            "blog",
            "forum",
            "social_media",
            "video",
            "ranking",
            "commercial_claim",
        ],
    },
    "pass_requirement": "at_least_one_A_or_B",
    "class_c_only_result": "reject",
    "external_required_fields": [
        "canonical_url",
        "source_class",
        "publisher_type",
        "retrieved_at",
        "claim",
        "content_fingerprint",
        "staleness_assessment",
        "licensing_constraints",
    ],
    "forbidden_inputs": [
        "validation_result",
        "holdout",
        "private_api",
        "secret",
        "live_account",
        "unapproved_dataset",
    ],
    "store_full_copyrighted_source": False,
}

REQUIRED_STATE_SCOPE_KEYS = {
    "approved_market",
    "baseline_pair",
    "baseline_timeframe",
    "campaign_compilation_only",
    "candidate_creation",
    "evidence",
    "human_approved_additional_pairs",
    "ranging_short_evidence_reuse",
    "read_only_analysis",
    "strategy_mutation",
}

REQUIRED_RESEARCHER_PROMPT_CLAUSES = (
    "# Researcher Role Contract",
    "Generate 6-10 distinct `research-idea-v1` JSON objects.",
    "Use at most two ideas per `strategy_family`.",
    "Read only sources listed in the task packet.",
    "Do not read Validation results, Holdout, secrets, private APIs, live accounts, strategy mutation paths, Candidate paths, or execution runners.",
    "External sources may inform an idea only when their required provenance metadata are included.",
    "Do not download a market dataset.",
    "Each hypothesis must be falsifiable.",
    "Do not promise return, win rate, or profitability.",
    "Write JSON to the provided inbox only; do not modify governed run artifacts.",
)

REGISTRY_CONNECT_TIMEOUT_SECONDS = 0.05
REGISTRY_RETRY_DEADLINE_SECONDS = 2.0
REGISTRY_RETRY_INTERVAL_SECONDS = 0.02


def _is_fingerprint(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value).issubset(set("0123456789abcdef"))
    )


def _validate_state(state: dict[str, object]) -> str:
    if state.get("schema_version") != "current-research-state-v1":
        raise DiscoveryError(
            "state_schema_invalid", "current-research-state-v1 is required"
        )
    conflicts = state.get("state_conflicts")
    if not isinstance(conflicts, list):
        raise DiscoveryError("state_structure_invalid", "state_conflicts")
    if conflicts:
        raise DiscoveryError(
            "state_conflict", "current research state contains conflicts"
        )

    scope = state.get("allowed_research_scope")
    if not isinstance(scope, dict) or not REQUIRED_STATE_SCOPE_KEYS.issubset(scope):
        raise DiscoveryError("state_structure_invalid", "allowed_research_scope")
    for field in ("datasets", "runtime_contracts", "unresolved_research_questions"):
        if not isinstance(state.get(field), list):
            raise DiscoveryError("state_structure_invalid", field)

    reported = state.get("state_fingerprint")
    if not _is_fingerprint(reported):
        raise DiscoveryError("state_structure_invalid", "state_fingerprint")
    calculated = fingerprint(
        {
            key: value
            for key, value in state.items()
            if key not in {"generated_at", "state_fingerprint", "snapshot_id"}
        }
    )
    if reported != calculated:
        raise DiscoveryError(
            "state_fingerprint_conflict",
            "current research state content does not match its fingerprint",
        )
    if state.get("snapshot_id") != f"research-state-{calculated[:16]}":
        raise DiscoveryError(
            "state_snapshot_conflict", "snapshot_id does not match state fingerprint"
        )

    expected_scope = {
        "approved_market": "Binance USD-M Futures",
        "baseline_pair": BASELINE_PAIR,
        "baseline_timeframe": "1h",
        "campaign_compilation_only": True,
        "candidate_creation": False,
        "read_only_analysis": True,
        "strategy_mutation": False,
    }
    for field, expected in expected_scope.items():
        if type(scope.get(field)) is not type(expected) or scope.get(field) != expected:
            raise DiscoveryError("state_structure_invalid", field)
    _validate_additional_pair_scope(scope)
    if not isinstance(scope.get("ranging_short_evidence_reuse"), str) or not str(
        scope["ranging_short_evidence_reuse"]
    ).strip():
        raise DiscoveryError(
            "state_structure_invalid", "ranging_short_evidence_reuse"
        )
    return calculated


def _validate_constitution(constitution: dict[str, object]) -> str:
    required_values = {
        "schema_version": "research-constitution-v1",
        "status": "approved",
        "approval_status": "approved",
        "approver_type": "human_user",
        "approved_version_immutable": True,
        "amendment_requires_new_version_hash_and_human_approval": True,
        "agent_mutable": False,
    }
    for field, expected in required_values.items():
        if type(constitution.get(field)) is not type(expected) or constitution.get(
            field
        ) != expected:
            reason = (
                "constitution_not_approved"
                if field in {"status", "approval_status"}
                else "constitution_invalid"
            )
            raise DiscoveryError(reason, field)
    if not isinstance(constitution.get("constitution_id"), str) or not str(
        constitution["constitution_id"]
    ).strip():
        raise DiscoveryError("constitution_invalid", "constitution_id")
    if (
        type(constitution.get("approved_version")) is not int
        or int(constitution["approved_version"]) < 1
    ):
        raise DiscoveryError("constitution_invalid", "approved_version")
    for field in ("approved_at", "approval_hash_authority"):
        if not isinstance(constitution.get(field), str) or not str(
            constitution[field]
        ).strip():
            raise DiscoveryError("constitution_invalid", field)
    return fingerprint(constitution)


def _validate_additional_pair_scope(scope: dict[str, object]) -> list[str]:
    evidence = scope.get("evidence")
    additional_pairs = scope.get("human_approved_additional_pairs")
    if (
        not isinstance(evidence, list)
        or not isinstance(additional_pairs, list)
        or not additional_pairs
        or any(not isinstance(pair, str) for pair in additional_pairs)
        or len(additional_pairs) != len(set(additional_pairs))
    ):
        raise DiscoveryError("state_structure_invalid", "allowed_research_scope")
    approved = set(additional_pairs)
    if not approved.issubset(ADDITIONAL_PAIR_APPROVAL_PATHS):
        raise DiscoveryError("state_structure_invalid", "allowed_research_scope")
    canonical = [pair for pair in SUPPORTED_ADDITIONAL_PAIRS if pair in approved]
    if additional_pairs != canonical or any(
        ADDITIONAL_PAIR_APPROVAL_PATHS[pair] not in evidence
        for pair in additional_pairs
    ):
        raise DiscoveryError("state_structure_invalid", "allowed_research_scope")
    return additional_pairs


def _validate_source_policy(source_policy: dict[str, object]) -> str:
    if source_policy != EXPECTED_SOURCE_POLICY:
        raise DiscoveryError(
            "source_policy_invalid", "source policy does not match the frozen contract"
        )
    return fingerprint(source_policy)


def _trigger_fingerprint(
    trigger: dict[str, object], source_policy: dict[str, object]
) -> str:
    semantic_trigger = {
        key: value
        for key, value in trigger.items()
        if key not in {"trigger_fingerprint", "created_at", "decided_at"}
    }
    semantic_trigger["source_policy_fingerprint"] = fingerprint(source_policy)
    return fingerprint(semantic_trigger)


def _forbidden_path_parts(source_policy: dict[str, object]) -> set[str]:
    policy_parts = {
        str(item).split("_", 1)[0].lower()
        for item in source_policy.get("forbidden_inputs", [])
        if isinstance(item, str) and item
    }
    return set(FORBIDDEN_PATH_PARTS) | policy_parts


def _lexical_absolute(path: str | Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except (FileNotFoundError, OSError):
        return False
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & reparse_attribute
    )


def _assert_no_reparse_components(
    root: Path,
    target: Path,
    reason_code: str,
) -> None:
    root = _lexical_absolute(root)
    target = _lexical_absolute(target)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise DiscoveryError(reason_code, "path escapes its controlled root") from exc

    current = root
    candidates = [root]
    for part in relative.parts:
        current = current / part
        candidates.append(current)
    for candidate in candidates:
        if _is_reparse_point(candidate):
            raise DiscoveryError(reason_code, candidate.name or str(candidate))


def _repo_regular_file(
    repo: Path,
    relative_path: Path,
    missing_reason: str,
    invalid_reason: str,
) -> Path:
    repo_lexical = _lexical_absolute(repo)
    candidate = repo_lexical / relative_path
    _assert_no_reparse_components(
        repo_lexical, candidate, f"{invalid_reason}_reparse"
    )
    try:
        repo_resolved = repo_lexical.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DiscoveryError(missing_reason, relative_path.as_posix()) from exc
    if not resolved.is_relative_to(repo_resolved):
        raise DiscoveryError(invalid_reason, "path escapes repository")
    try:
        metadata = resolved.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError) as exc:
        raise DiscoveryError(missing_reason, relative_path.as_posix()) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DiscoveryError(invalid_reason, "regular file required")
    return candidate


def create_trigger(
    event_type: str,
    event_ref: str,
    state: dict[str, object],
    constitution: dict[str, object],
    source_policy: dict[str, object],
    created_at: str | None = None,
) -> dict[str, object]:
    if event_type not in ALLOWED_EVENTS:
        raise DiscoveryError("unsupported_trigger", event_type)
    if not isinstance(event_ref, str) or not event_ref.strip():
        raise DiscoveryError("trigger_input_missing", "event_ref")
    state_fingerprint = _validate_state(state)
    _validate_constitution(constitution)
    _validate_source_policy(source_policy)
    source_policy_version = source_policy["schema_version"]

    trigger = {
        "schema_version": "research-trigger-v1",
        "trigger_id": f"discovery-trigger-{fingerprint({'event_type': event_type, 'event_ref': event_ref, 'state': state_fingerprint})[:16]}",
        "event_type": event_type,
        "event_ref": event_ref,
        "research_state_fingerprint": state_fingerprint,
        "constitution_fingerprint": fingerprint(constitution),
        "source_policy_version": source_policy_version,
        "created_at": created_at or utc_now(),
    }
    trigger["trigger_fingerprint"] = _trigger_fingerprint(trigger, source_policy)
    return trigger


def _load_bound_document(
    repo: Path, relative_path: Path, missing_reason: str
) -> dict[str, object]:
    invalid_reason = f"{missing_reason.removesuffix('_missing')}_invalid"
    path = _repo_regular_file(
        repo, relative_path, missing_reason, invalid_reason
    )
    try:
        return load_document(path)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(
            invalid_reason,
            f"{relative_path.as_posix()}: {type(exc).__name__}: {exc}",
        ) from exc


def _validate_idea_schema(repo: Path) -> None:
    path = _repo_regular_file(
        repo, IDEA_SCHEMA_PATH, "idea_schema_missing", "idea_schema_invalid"
    )
    try:
        schema = load_document(path)
        jsonschema.Draft202012Validator.check_schema(schema)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(
            "idea_schema_invalid", f"{type(exc).__name__}: schema validation failed"
        ) from exc
    properties = schema.get("properties")
    version = properties.get("schema_version") if isinstance(properties, dict) else None
    if (
        schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema"
        or schema.get("additionalProperties") is not False
        or not isinstance(version, dict)
        or version.get("const") != "research-idea-v1"
    ):
        raise DiscoveryError(
            "idea_schema_invalid", "research-idea-v1 frozen schema is required"
        )


def _load_researcher_prompt(repo: Path) -> str:
    path = _repo_regular_file(
        repo,
        RESEARCHER_PROMPT_PATH,
        "researcher_prompt_missing",
        "researcher_prompt_invalid",
    )
    try:
        prompt = path.read_text(encoding="utf-8")
    except Exception as exc:
        raise DiscoveryError(
            "researcher_prompt_invalid", f"{type(exc).__name__}: prompt read failed"
        ) from exc
    missing = [
        clause for clause in REQUIRED_RESEARCHER_PROMPT_CLAUSES if clause not in prompt
    ]
    if missing:
        raise DiscoveryError(
            "researcher_prompt_invalid", "required role-contract clause is missing"
        )
    return prompt


def _path_is_forbidden(
    relative_path: str, forbidden_parts: set[str] | None = None
) -> bool:
    forbidden_parts = forbidden_parts or FORBIDDEN_PATH_PARTS
    parts = [part.lower() for part in Path(relative_path).parts]
    for part in parts:
        stem = part.split(".", 1)[0]
        if stem in forbidden_parts:
            return True
        if any(stem.startswith(f"{prefix}-") for prefix in forbidden_parts):
            return True
        if any(stem.startswith(f"{prefix}_") for prefix in forbidden_parts):
            return True
    return False


def _safe_repo_source(
    repo: Path, raw_path: object, forbidden_parts: set[str] | None = None
) -> str | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    normalized = raw_path.strip().replace("\\", "/")
    if not normalized.startswith(("docs/", "reports/", "research/")):
        return None
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if _path_is_forbidden(normalized, forbidden_parts):
        return None

    repo_lexical = _lexical_absolute(repo)
    candidate_lexical = repo_lexical / relative
    _assert_no_reparse_components(
        repo_lexical, candidate_lexical, "source_reparse_forbidden"
    )
    try:
        repo_resolved = repo_lexical.resolve(strict=True)
        resolved = candidate_lexical.resolve(strict=True)
    except FileNotFoundError as exc:
        raise DiscoveryError("source_missing", relative.as_posix())
    try:
        resolved_relative = resolved.relative_to(repo_resolved)
    except ValueError as exc:
        raise DiscoveryError("source_outside_repo", relative.as_posix()) from exc
    if _path_is_forbidden(resolved_relative.as_posix(), forbidden_parts):
        raise DiscoveryError("source_forbidden", relative.as_posix())
    try:
        metadata = resolved.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError) as exc:
        raise DiscoveryError("source_missing", relative.as_posix()) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DiscoveryError("source_not_regular", relative.as_posix())
    return relative.as_posix()


def _evidence_paths(value: object) -> list[object]:
    if isinstance(value, dict):
        evidence = value.get("evidence")
        return list(evidence) if isinstance(evidence, list) else []
    if isinstance(value, list):
        paths: list[object] = []
        for item in value:
            paths.extend(_evidence_paths(item))
        return paths
    return []


def _approved_dataset_pairs(
    state: dict[str, object],
) -> tuple[str, set[str]]:
    scope = state.get("allowed_research_scope")
    if not isinstance(scope, dict):
        return "", set()
    baseline_pair = scope.get("baseline_pair")
    if baseline_pair != BASELINE_PAIR:
        raise DiscoveryError(
            "state_structure_invalid", "allowed_research_scope dataset pairs"
        )
    additional_pairs = _validate_additional_pair_scope(scope)
    return BASELINE_PAIR, {BASELINE_PAIR, *additional_pairs}


def _allowed_source_paths(
    repo: Path,
    state: dict[str, object],
    source_policy: dict[str, object],
) -> list[str]:
    forbidden_parts = _forbidden_path_parts(source_policy)
    source_paths = {
        STATE_PATH.as_posix(),
        CONSTITUTION_PATH.as_posix(),
        SOURCE_POLICY_PATH.as_posix(),
        IDEA_SCHEMA_PATH.as_posix(),
    }
    baseline_pair, approved_pairs = _approved_dataset_pairs(state)

    datasets = state.get("datasets")
    if isinstance(datasets, list):
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            intended_use = dataset.get("intended_use")
            pairs = dataset.get("pairs")
            timeframes = dataset.get("timeframes")
            visibility = dataset.get("agent_visibility")
            if dataset.get("sealed") is not True:
                continue
            normalized_use = (
                intended_use.strip().lower()
                if isinstance(intended_use, str)
                else ""
            )
            if normalized_use != "development" and not normalized_use.startswith(
                "development_"
            ):
                continue
            if (
                not isinstance(pairs, list)
                or not pairs
                or any(not isinstance(pair, str) or not pair for pair in pairs)
                or not set(pairs).issubset(approved_pairs)
            ):
                continue
            if not isinstance(timeframes, list) or not {"1h", "4h"}.issubset(
                set(timeframes)
            ):
                continue
            if baseline_pair in pairs and visibility != "full":
                continue
            if any(pair != baseline_pair for pair in pairs) and visibility not in {
                None,
                "legacy",
                "full",
            }:
                continue
            source = _safe_repo_source(
                repo, dataset.get("path"), forbidden_parts
            )
            if source:
                source_paths.add(source)

    runtime_contracts = state.get("runtime_contracts")
    if isinstance(runtime_contracts, list):
        for contract in runtime_contracts:
            if not isinstance(contract, dict) or contract.get("exists") is not True:
                continue
            source = _safe_repo_source(
                repo, contract.get("path"), forbidden_parts
            )
            if source:
                source_paths.add(source)

    for section in EVIDENCE_SECTIONS:
        for raw_path in _evidence_paths(state.get(section)):
            source = _safe_repo_source(repo, raw_path, forbidden_parts)
            if source:
                source_paths.add(source)

    for required_path in sorted(source_paths):
        _safe_repo_source(repo, required_path, forbidden_parts)
    return sorted(source_paths)


def _bound_context(
    repo: Path, trigger: dict[str, object]
) -> tuple[dict[str, object], list[str]]:
    state = _load_bound_document(repo, STATE_PATH, "state_missing")
    state_fingerprint = _validate_state(state)
    if state_fingerprint != trigger.get("research_state_fingerprint"):
        raise DiscoveryError(
            "stale_trigger", "current research state fingerprint changed"
        )

    constitution = _load_bound_document(
        repo, CONSTITUTION_PATH, "constitution_missing"
    )
    constitution_fingerprint = _validate_constitution(constitution)
    if constitution_fingerprint != trigger.get("constitution_fingerprint"):
        raise DiscoveryError(
            "constitution_conflict", "approved Constitution fingerprint changed"
        )

    source_policy = _load_bound_document(
        repo, SOURCE_POLICY_PATH, "source_policy_missing"
    )
    if source_policy.get("schema_version") != trigger.get(
        "source_policy_version"
    ):
        raise DiscoveryError(
            "source_policy_conflict", "source policy version changed"
        )
    _validate_source_policy(source_policy)

    _repo_regular_file(
        repo,
        TRIGGER_SCHEMA_PATH,
        "trigger_schema_missing",
        "trigger_schema_invalid",
    )
    validate_artifact(repo, "research-trigger.schema.json", trigger)
    actual_trigger_fingerprint = _trigger_fingerprint(trigger, source_policy)
    if trigger.get("trigger_fingerprint") != actual_trigger_fingerprint:
        raise DiscoveryError(
            "trigger_fingerprint_conflict",
            "trigger content does not match trigger_fingerprint",
        )

    return state, _allowed_source_paths(repo, state, source_policy)


def _validate_run_paths(
    repo: Path, run_path: Path, temp_inbox: Path
) -> tuple[Path, Path]:
    if run_path.is_absolute() or ".." in run_path.parts:
        raise DiscoveryError("run_path_invalid", run_path.as_posix())
    if run_path.parts[:3] != ("research", "discovery", "runs"):
        raise DiscoveryError("run_path_invalid", run_path.as_posix())
    if len(run_path.parts) != 4:
        raise DiscoveryError("run_path_invalid", run_path.as_posix())

    repo_lexical = _lexical_absolute(repo)
    governed_runs = repo_lexical / "research/discovery/runs"
    run_root = repo_lexical / run_path
    _assert_no_reparse_components(
        repo_lexical, run_root, "run_reparse_forbidden"
    )
    repo_resolved = repo_lexical.resolve(strict=True)
    governed_resolved = governed_runs.resolve(strict=False)
    run_resolved = run_root.resolve(strict=False)
    if not governed_resolved.is_relative_to(repo_resolved) or not run_resolved.is_relative_to(
        governed_resolved
    ):
        raise DiscoveryError("run_path_invalid", run_path.as_posix())

    temp_root = _lexical_absolute(tempfile.gettempdir())
    expected_inbox = _lexical_absolute(
        temp_root
        / "freqtrade-research-discovery"
        / _repo_identity_namespace(repo_lexical)
        / run_path.name
        / "researcher"
    )
    actual_inbox = _lexical_absolute(temp_inbox)
    if os.path.normcase(str(actual_inbox)) != os.path.normcase(str(expected_inbox)):
        raise DiscoveryError("temp_inbox_invalid", str(actual_inbox))
    _assert_no_reparse_components(
        temp_root, actual_inbox, "temp_reparse_forbidden"
    )
    if actual_inbox.is_relative_to(repo_lexical) or actual_inbox.resolve(
        strict=False
    ).is_relative_to(repo_resolved):
        raise DiscoveryError("temp_inbox_invalid", "TEMP inbox is inside repo")
    return run_root, actual_inbox


def _repo_identity_namespace(repo: Path) -> str:
    canonical = _lexical_absolute(repo).resolve(strict=True)
    normalized = os.path.normcase(str(canonical))
    return fingerprint({"canonical_repo_path": normalized})[:16]


def _require_plain_directory(path: Path, reason_code: str) -> None:
    if _is_reparse_point(path):
        raise DiscoveryError(reason_code, path.name)
    try:
        metadata = path.lstat()
    except (FileNotFoundError, OSError) as exc:
        raise DiscoveryError(reason_code, path.name) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise DiscoveryError(reason_code, path.name)


def _validate_temp_inbox_preflight(inbox: Path) -> None:
    inbox = _lexical_absolute(inbox)
    run_root = inbox.parent
    namespace_root = run_root.parent
    controlled_root = namespace_root.parent
    if os.path.lexists(controlled_root):
        _require_plain_directory(controlled_root, "temp_inbox_invalid")
    if os.path.lexists(namespace_root):
        _require_plain_directory(namespace_root, "temp_inbox_invalid")
    if os.path.lexists(run_root):
        _require_plain_directory(run_root, "temp_inbox_invalid")
        entries = list(run_root.iterdir())
        if entries and (
            len(entries) != 1
            or os.path.normcase(str(entries[0])) != os.path.normcase(str(inbox))
        ):
            raise DiscoveryError(
                "temp_inbox_not_empty", "controlled run TEMP directory is not empty"
            )
    if os.path.lexists(inbox):
        _require_plain_directory(inbox, "temp_inbox_invalid")
        if any(inbox.iterdir()):
            raise DiscoveryError(
                "temp_inbox_not_empty", "Researcher inbox must be empty"
            )


def _create_temp_inbox(inbox: Path, created: list[Path]) -> None:
    _validate_temp_inbox_preflight(inbox)
    inbox = _lexical_absolute(inbox)
    controlled_root = inbox.parents[2]
    namespace_root = inbox.parents[1]
    for path in (controlled_root, namespace_root, inbox.parent, inbox):
        if not os.path.lexists(path):
            path.mkdir()
            created.append(path)
        _require_plain_directory(path, "temp_reparse_forbidden")
    _validate_temp_inbox_preflight(inbox)


def _cleanup_created_directories(created: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in reversed(created):
        try:
            path.rmdir()
        except FileNotFoundError:
            continue
        except OSError as exc:
            failures.append(
                f"rmdir {path.name}: {type(exc).__name__}: {exc}"
            )
    return failures


def _ensure_runs_root(repo: Path, created: list[Path]) -> Path:
    repo = _lexical_absolute(repo)
    runs_root = repo / "research/discovery/runs"
    if os.path.lexists(runs_root):
        _require_plain_directory(runs_root, "run_path_conflict")
    else:
        runs_root.mkdir()
        created.append(runs_root)
    _assert_no_reparse_components(repo, runs_root, "run_reparse_forbidden")
    return runs_root


def _create_staging_directory(
    runs_root: Path, run_id: str, owned: list[Path]
) -> Path:
    staging = Path(
        tempfile.mkdtemp(prefix=f".{run_id}.staging-", dir=str(runs_root))
    )
    owned.append(staging)
    _assert_no_reparse_components(
        runs_root, staging, "run_reparse_forbidden"
    )
    return staging


def _write_packet_file(path: Path, packet: str) -> None:
    path.write_text(packet, encoding="utf-8")


def _write_and_verify_staging_artifacts(
    repo: Path,
    staging: Path,
    trigger: dict[str, object],
    packet: str,
) -> None:
    trigger_path = staging / "trigger.json"
    packet_path = staging / "researcher-task.md"
    write_immutable_json(trigger_path, trigger)
    _write_packet_file(packet_path, packet)
    if {path.name for path in staging.iterdir()} != {
        "trigger.json",
        "researcher-task.md",
    }:
        raise DiscoveryError("run_artifact_conflict", "staging layout")
    stored_trigger = load_document(trigger_path)
    validate_artifact(repo, "research-trigger.schema.json", stored_trigger)
    if stored_trigger != trigger or packet_path.read_text(encoding="utf-8") != packet:
        raise DiscoveryError("run_artifact_conflict", "staging verification")


def _publish_run_directory(staging: Path, final_run: Path) -> None:
    if os.path.lexists(final_run):
        raise DiscoveryError("run_path_conflict", final_run.name)
    os.rename(staging, final_run)


def _cleanup_owned_run_directory(
    path: Path,
    runs_root: Path,
    run_id: str,
) -> None:
    path = _lexical_absolute(path)
    runs_root = _lexical_absolute(runs_root)
    if path.parent != runs_root or not (
        path.name == run_id or path.name.startswith(f".{run_id}.staging-")
    ):
        raise DiscoveryError("cleanup_path_invalid", path.name)
    if not os.path.lexists(path):
        return
    if _is_reparse_point(path):
        path.unlink()
        return
    shutil.rmtree(path)


def _rollback_and_cleanup(
    connection: sqlite3.Connection,
    original: Exception,
    owned_run_paths: list[Path],
    created_temp_directories: list[Path],
    created_run_directories: list[Path],
    runs_root: Path,
    run_id: str,
) -> None:
    failures: list[str] = []
    try:
        connection.rollback()
    except Exception as exc:
        failures.append(f"rollback: {type(exc).__name__}: {exc}")

    for path in reversed(owned_run_paths):
        try:
            _cleanup_owned_run_directory(path, runs_root, run_id)
        except Exception as exc:
            failures.append(
                f"run cleanup {path.name}: {type(exc).__name__}: {exc}"
            )
    failures.extend(_cleanup_created_directories(created_temp_directories))
    failures.extend(_cleanup_created_directories(created_run_directories))
    if failures:
        original_summary = f"{type(original).__name__}: {original}"
        raise DiscoveryError(
            "rollback_cleanup_failed",
            f"original={original_summary}; cleanup={' | '.join(failures)}",
        ) from original


def _researcher_packet_text(
    repo: Path,
    run_path: Path,
    trigger: dict[str, object],
    temp_inbox: Path,
) -> str:
    _validate_idea_schema(repo)
    state, source_paths = _bound_context(repo, trigger)
    _, inbox = _validate_run_paths(repo, run_path, temp_inbox)
    prompt = _load_researcher_prompt(repo)
    knowledge_selection = _knowledge_broker_selection(repo, trigger, state)

    allowed_scope = state.get("allowed_research_scope")
    if not isinstance(allowed_scope, dict):
        raise DiscoveryError("state_missing", "allowed_research_scope")
    if (
        allowed_scope.get("approved_market") != "Binance USD-M Futures"
        or allowed_scope.get("baseline_timeframe") != "1h"
    ):
        raise DiscoveryError("state_conflict", "fixed market scope changed")

    source_lines = "\n".join(f"- `{path}`" for path in source_paths)
    knowledge_section = ""
    if knowledge_selection is not None:
        knowledge_section = (
            "## Automatic Knowledge Broker / 自动知识召回\n\n"
            "This bounded, deterministic Top-K selection is advisory. Apply negative lessons "
            "before proposing semantic duplicates. Class C patterns are inspiration only and "
            "cannot satisfy the A/B evidence gate.\n\n"
            "```json\n"
            f"{json.dumps(knowledge_selection, ensure_ascii=False, indent=2, sort_keys=True)}\n"
            "```\n\n"
        )
    return (
        "# Researcher Task Packet / 研究员任务包\n\n"
        "## Immutable bindings / 不可变绑定\n\n"
        f"- Trigger fingerprint: `{trigger['trigger_fingerprint']}`\n"
        f"- Research state fingerprint: `{trigger['research_state_fingerprint']}`\n"
        f"- Constitution fingerprint: `{trigger['constitution_fingerprint']}`\n"
        f"- Source policy version: `{trigger['source_policy_version']}`\n\n"
        "## Allowed read-only sources / 允许只读来源\n\n"
        "Read only the exact allowlisted paths below. Do not follow other repository references.\n\n"
        f"{source_lines}\n\n"
        f"{knowledge_section}"
        "## Fixed scope / 固定范围\n\n"
        "Keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, "
        "`1h` primary, `4h` informative, the approved runtime, and all existing risk "
        "parameters unchanged. You may propose data readiness work, but Do not download "
        "market data.\n\n"
        "## Forbidden boundaries / 禁止边界\n\n"
        "Do not access Validation, Holdout, secrets, private APIs, live accounts, strategy "
        "mutation surfaces, Candidate surfaces, or execution surfaces. Do not create or "
        "start a Candidate, Campaign, experiment, backtest, or any execution.\n\n"
        "## Output / 输出\n\n"
        f"Write only `research-idea-v1` JSON objects to this absolute system TEMP inbox: `{inbox}`. "
        "The inbox is untrusted staging and is outside the governed repository. Do not modify "
        "the trigger or task packet.\n\n"
        "## Role contract / 角色合同\n\n"
        f"{prompt.rstrip()}\n"
    )


def _knowledge_broker_selection(
    repo: Path,
    trigger: dict[str, object],
    state: dict[str, object],
) -> dict[str, object] | None:
    knowledge_state = state.get("open_source_knowledge")
    if not isinstance(knowledge_state, dict) or knowledge_state.get("available") is not True:
        return None
    import open_source_knowledge as knowledge_support

    return knowledge_support.broker_selection(
        repo,
        str(trigger["event_type"]),
        str(trigger["event_ref"]),
        str(trigger["trigger_fingerprint"]),
        state,
    )


def _record_knowledge_broker_usage(
    repo: Path,
    trigger: dict[str, object],
    run_id: str,
    connection: sqlite3.Connection,
) -> None:
    state, _ = _bound_context(repo, trigger)
    selection = _knowledge_broker_selection(repo, trigger, state)
    if selection is None:
        return
    import open_source_knowledge as knowledge_support

    knowledge_support.register_broker_usage(
        connection,
        run_id,
        selection,
        str(trigger["created_at"]),
    )


def _enqueue_researcher_worker(
    trigger: dict[str, object],
    result: dict[str, object],
    connection: sqlite3.Connection,
) -> None:
    import research_worker_queue as worker_queue

    worker_queue.enqueue_worker_job(
        connection,
        run_id=str(result["run_id"]),
        stage="researcher",
        round_number=1,
        task_path=(Path(str(result["run_path"])) / "researcher-task.md").as_posix(),
        inbox_path=str(result["researcher_inbox"]),
        created_at=str(trigger["created_at"]),
    )


def render_researcher_packet(
    repo: Path,
    run_path: Path,
    trigger: dict[str, object],
    temp_inbox: Path,
) -> str:
    repo = _lexical_absolute(repo)
    run_path = Path(run_path)
    expected = _expected_result(trigger, repo)
    expected_run_path = Path(str(expected["run_path"]))
    if run_path != expected_run_path:
        raise DiscoveryError("run_path_invalid", run_path.as_posix())
    packet = _researcher_packet_text(repo, run_path, trigger, temp_inbox)
    run_root, inbox = _validate_run_paths(repo, run_path, temp_inbox)
    _validate_temp_inbox_preflight(inbox)
    packet_path = run_root / "researcher-task.md"
    if os.path.lexists(packet_path) and _is_reparse_point(packet_path):
        raise DiscoveryError("run_artifact_conflict", packet_path.name)
    return packet


def _expected_result(
    trigger: dict[str, object], repo: Path
) -> dict[str, object]:
    run_id = f"discovery-run-{trigger['trigger_fingerprint'][:16]}"
    run_path = Path("research/discovery/runs") / run_id
    temp_inbox = _lexical_absolute(
        Path(tempfile.gettempdir())
        / "freqtrade-research-discovery"
        / _repo_identity_namespace(repo)
        / run_id
        / "researcher"
    )
    return {
        "run_id": run_id,
        "run_path": run_path.as_posix(),
        "researcher_inbox": str(temp_inbox),
        "status": "awaiting_researcher",
        "trigger_fingerprint": trigger["trigger_fingerprint"],
    }


def _verify_existing_run(
    repo: Path,
    trigger: dict[str, object],
    result: dict[str, object],
    registry_path: Path,
    connection: sqlite3.Connection,
) -> dict[str, object]:
    run_path = Path(str(result["run_path"]))
    temp_inbox = Path(str(result["researcher_inbox"]))
    # Import lazily so the trigger CLI remains safe when executed as __main__
    # while reusing the single stage-aware layout authority from the review
    # module instead of maintaining a second downstream artifact allowlist.
    import research_discovery_review as review_support

    context = review_support._canonical_run_context(
        repo,
        str(result["run_id"]),
        registry_path,
        _registry_connection=connection,
    )
    run_root = context["run_root"]
    trigger_path = run_root / "trigger.json"
    packet_path = run_root / "researcher-task.md"
    for artifact in (trigger_path, packet_path):
        if _is_reparse_point(artifact):
            raise DiscoveryError("run_artifact_conflict", artifact.name)
        try:
            metadata = artifact.stat(follow_symlinks=False)
        except (FileNotFoundError, OSError) as exc:
            raise DiscoveryError("run_artifact_missing", artifact.name) from exc
        if not stat.S_ISREG(metadata.st_mode):
            raise DiscoveryError("run_artifact_conflict", artifact.name)
    if not trigger_path.is_file() or not packet_path.is_file():
        raise DiscoveryError("run_artifact_missing", result["run_id"])
    existing_trigger = load_document(trigger_path)
    validate_artifact(repo, "research-trigger.schema.json", existing_trigger)
    if (
        existing_trigger.get("trigger_fingerprint")
        != trigger.get("trigger_fingerprint")
    ):
        raise DiscoveryError(
            "immutable_artifact_conflict", trigger_path.as_posix()
        )
    _bound_context(repo, existing_trigger)
    expected_packet = _researcher_packet_text(repo, run_path, trigger, temp_inbox)
    if packet_path.read_text(encoding="utf-8") != expected_packet:
        raise DiscoveryError("immutable_artifact_conflict", packet_path.as_posix())
    if {path.name for path in run_root.iterdir()} == {
        "trigger.json",
        "researcher-task.md",
    }:
        if not os.path.lexists(temp_inbox):
            raise DiscoveryError("run_artifact_missing", "researcher inbox")
        _validate_temp_inbox_preflight(temp_inbox)
    return existing_trigger


def _preflight_run(
    repo: Path,
    trigger: dict[str, object],
    registry_path: Path,
) -> tuple[dict[str, object], Path, Path, str, bool]:
    result = _expected_result(trigger, repo)
    run_path = Path(str(result["run_path"]))
    temp_inbox = Path(str(result["researcher_inbox"]))
    packet = _researcher_packet_text(repo, run_path, trigger, temp_inbox)
    run_root, inbox = _validate_run_paths(repo, run_path, temp_inbox)
    final_present = os.path.lexists(run_root)
    if not final_present:
        _validate_temp_inbox_preflight(inbox)
    if final_present and not os.path.lexists(registry_path):
        raise DiscoveryError("run_path_conflict", str(result["run_id"]))
    return result, run_root, inbox, packet, final_present


def _open_registry_once(registry_path: Path) -> sqlite3.Connection:
    registry_path = Path(registry_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        registry_path,
        timeout=REGISTRY_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        ensure_director_schema(connection)
        connection.execute("PRAGMA busy_timeout=0")
    except Exception:
        connection.close()
        raise
    return connection


def _is_registry_lock_error(exc: sqlite3.OperationalError) -> bool:
    error_code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(error_code, int) and error_code & 0xFF in {
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    }:
        return True
    return str(exc).strip().lower() in {
        "database is busy",
        "database is locked",
        "database table is locked",
    }


def _retry_registry_operation(operation, deadline: float, stage: str):
    while True:
        if deadline - time.monotonic() <= 0:
            raise DiscoveryError(
                "registry_locked", f"Registry deadline exhausted during {stage}"
            )
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if not _is_registry_lock_error(exc):
                raise
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DiscoveryError(
                    "registry_locked",
                    f"Registry remained locked during {stage} until deadline",
                ) from exc
            time.sleep(min(REGISTRY_RETRY_INTERVAL_SECONDS, remaining))


def _open_registry_with_retry(
    registry_path: Path, deadline: float
) -> sqlite3.Connection:
    return _retry_registry_operation(
        lambda: _open_registry_once(registry_path),
        deadline,
        "open/schema",
    )


def prepare_run(
    repo: Path, trigger: dict[str, object], registry_path: Path
) -> dict[str, object]:
    registry_deadline = time.monotonic() + REGISTRY_RETRY_DEADLINE_SECONDS
    repo = _lexical_absolute(repo)
    result, final_run, temp_inbox, packet, final_present = _preflight_run(
        repo, trigger, registry_path
    )
    connection = _open_registry_with_retry(registry_path, registry_deadline)
    runs_root = final_run.parent
    owned_run_paths: list[Path] = []
    created_run_directories: list[Path] = []
    created_temp_directories: list[Path] = []
    try:
        _retry_registry_operation(
            lambda: connection.execute("BEGIN IMMEDIATE"),
            registry_deadline,
            "BEGIN IMMEDIATE",
        )
        matches = connection.execute(
            "SELECT run_id, trigger_fingerprint, status, state_fingerprint, "
            "payload_json, created_at FROM research_discovery_runs "
            "WHERE run_id=? OR trigger_fingerprint=?",
            (result["run_id"], trigger["trigger_fingerprint"]),
        ).fetchall()
        if len(matches) > 1:
            raise DiscoveryError(
                "registry_run_conflict", str(result["run_id"])
            )
        if matches:
            existing = matches[0]
            try:
                existing_result = json.loads(existing["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise DiscoveryError(
                    "registry_run_conflict", str(existing["run_id"])
                ) from exc
            if (
                not isinstance(existing_result, dict)
                or existing["run_id"] != result["run_id"]
                or existing["trigger_fingerprint"]
                != trigger["trigger_fingerprint"]
                or existing["status"] != result["status"]
                or existing["state_fingerprint"]
                != trigger["research_state_fingerprint"]
                or existing_result != result
            ):
                raise DiscoveryError(
                    "registry_run_conflict", str(existing["run_id"])
                )
            stored_trigger = _verify_existing_run(
                repo,
                trigger,
                existing_result,
                registry_path,
                connection,
            )
            if (
                existing["created_at"] != stored_trigger.get("created_at")
                or stored_trigger.get("trigger_fingerprint")
                != existing["trigger_fingerprint"]
                or stored_trigger.get("research_state_fingerprint")
                != existing["state_fingerprint"]
            ):
                raise DiscoveryError(
                    "registry_run_conflict", str(existing["run_id"])
                )
            _record_knowledge_broker_usage(
                repo,
                trigger,
                str(existing["run_id"]),
                connection,
            )
            _enqueue_researcher_worker(stored_trigger, existing_result, connection)
            _retry_registry_operation(
                connection.commit,
                registry_deadline,
                "commit",
            )
            return existing_result

        if final_present or os.path.lexists(final_run):
            raise DiscoveryError("run_path_conflict", result["run_id"])
        runs_root = _ensure_runs_root(repo, created_run_directories)
        staging = _create_staging_directory(
            runs_root, str(result["run_id"]), owned_run_paths
        )
        _write_and_verify_staging_artifacts(
            repo, staging, trigger, packet
        )
        _publish_run_directory(staging, final_run)
        owned_run_paths.append(final_run)
        _create_temp_inbox(temp_inbox, created_temp_directories)
        connection.execute(
            "INSERT INTO research_discovery_runs("
            "run_id, trigger_fingerprint, status, state_fingerprint, payload_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                result["run_id"],
                trigger["trigger_fingerprint"],
                result["status"],
                trigger["research_state_fingerprint"],
                json.dumps(result, sort_keys=True),
                trigger["created_at"],
            ),
        )
        _record_knowledge_broker_usage(
            repo,
            trigger,
            str(result["run_id"]),
            connection,
        )
        _enqueue_researcher_worker(trigger, result, connection)
        _retry_registry_operation(
            connection.commit,
            registry_deadline,
            "commit",
        )
        return result
    except Exception as original:
        _rollback_and_cleanup(
            connection,
            original,
            owned_run_paths,
            created_temp_directories,
            created_run_directories,
            runs_root,
            str(result["run_id"]),
        )
        raise
    finally:
        connection.close()


def _resolve_input(repo: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


class _DiscoveryArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise DiscoveryError("cli_argument_error", "invalid CLI arguments")


def _print_cli_error(reason_code: str) -> int:
    details = {
        "unsupported_trigger": "unsupported trigger event",
        "state_fingerprint_conflict": "research state fingerprint conflict",
        "input_load_failed": "required input could not be loaded",
        "cli_argument_error": "invalid CLI arguments",
        "internal_error": "internal error",
    }
    payload = {
        "status": "error",
        "reason_code": reason_code,
        "detail": details.get(reason_code, "request rejected"),
    }
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _DiscoveryArgumentParser(description=__doc__)
        parser.add_argument("--event-type", required=True)
        parser.add_argument("--event-ref", required=True)
        parser.add_argument("--state", default=STATE_PATH.as_posix())
        parser.add_argument("--constitution", default=CONSTITUTION_PATH.as_posix())
        parser.add_argument("--source-policy", default=SOURCE_POLICY_PATH.as_posix())
        parser.add_argument("--director-registry", required=True)
        parser.add_argument(
            "--repo-root", default=str(Path(__file__).resolve().parents[1])
        )
        args = parser.parse_args(argv)

        repo = _lexical_absolute(args.repo_root)
        try:
            state = load_document(_resolve_input(repo, args.state))
            constitution = load_document(_resolve_input(repo, args.constitution))
            source_policy = load_document(_resolve_input(repo, args.source_policy))
        except Exception as exc:
            raise DiscoveryError(
                "input_load_failed", "required input could not be loaded"
            ) from exc
        registry = _resolve_input(repo, args.director_registry)
        trigger = create_trigger(
            event_type=args.event_type,
            event_ref=args.event_ref,
            state=state,
            constitution=constitution,
            source_policy=source_policy,
        )
        result = prepare_run(repo, trigger, registry)
        public_result = {
            key: result[key]
            for key in ("run_id", "run_path", "status", "trigger_fingerprint")
        }
        print(json.dumps(public_result, sort_keys=True))
        return 0
    except DiscoveryError as exc:
        return _print_cli_error(exc.reason_code)
    except Exception:
        return _print_cli_error("internal_error")


if __name__ == "__main__":
    raise SystemExit(main())
