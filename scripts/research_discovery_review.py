#!/usr/bin/env python3
"""Ingest immutable discovery reviews and render deterministic human packets."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from html import escape
from pathlib import Path

import argparse
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile

import jsonschema

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
    write_json,
)
from research_discovery_common import (
    DiscoveryError,
    artifact_fingerprint,
    assert_fixed_scope,
    rank_eligible,
    score_idea,
    validate_artifact,
    validate_sources,
)
import research_discovery_trigger as trigger_support


_RUN_ID = re.compile(r"^discovery-run-[a-f0-9]{16}$")
_ARTIFACT_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_DISCLAIMER = "批准研究方向不代表盈利判断，也不授权创建 Candidate 或执行 Campaign。"
_MARKDOWN_SOURCE = "human-review.zh-CN.md"
_DIRECTOR_RESULT_ROOT = Path("research/director/discovery-handoff")
_DIRECTOR_RUN_ID = re.compile(r"^director-discovery-[a-f0-9]{16}$")
_DIRECTOR_RUN_FIELDS = {
    "schema_version",
    "run_id",
    "created_at",
    "state_fingerprint",
    "constitution_status",
    "objective",
    "budget",
    "risk_tolerance",
    "recommendation",
    "recommendation_reason",
    "proposals",
    "rejected_proposals",
    "ranking_factors",
    "model_preference_used",
    "execution_authorized",
    "discovery_handoff_fingerprint",
}
_DIRECTOR_BUDGET_FIELDS = {
    "max_campaigns",
    "max_experiments",
    "max_wall_clock_minutes",
    "max_validation_accesses",
}
_FINAL_AUDIT_FIELDS = (
    "schema_version",
    "run_id",
    "trigger_fingerprint",
    "idea_count",
    "critique_count",
    "shortlist_count",
    "recommendation",
    "human_decision",
    "handoff_created",
    "director_result",
    "candidate_created",
    "campaign_started",
    "strategy_modified",
    "risk_modified",
    "validation_accesses",
    "holdout_accesses",
    "artifact_hashes",
    "registry_integrity",
)


def _require_identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or _ARTIFACT_ID.fullmatch(value) is None:
        raise DiscoveryError("artifact_id_invalid", field)
    return value


def _require_regular_file(path: Path, reason_code: str) -> None:
    if trigger_support._is_reparse_point(path):
        raise DiscoveryError(reason_code, path.name)
    try:
        metadata = path.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError) as exc:
        raise DiscoveryError(reason_code, path.name) from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise DiscoveryError(reason_code, path.name)


def _require_plain_directory(path: Path, reason_code: str) -> None:
    if trigger_support._is_reparse_point(path):
        raise DiscoveryError(reason_code, path.name)
    try:
        metadata = path.stat(follow_symlinks=False)
    except (FileNotFoundError, OSError) as exc:
        raise DiscoveryError(reason_code, path.name) from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise DiscoveryError(reason_code, path.name)


def _load_json_mapping(path: Path, reason_code: str) -> dict[str, object]:
    _require_regular_file(path, reason_code)
    try:
        return load_document(path)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(
            reason_code, f"{path.name}: {type(exc).__name__}"
        ) from exc


def _canonical_run_context(
    repo: Path,
    run_id: str,
    registry_path: Path | None = None,
) -> dict[str, object]:
    repo = trigger_support._lexical_absolute(repo)
    if _RUN_ID.fullmatch(run_id) is None:
        raise DiscoveryError("run_path_invalid", run_id)
    run_path = Path("research/discovery/runs") / run_id
    expected_researcher = (
        trigger_support._lexical_absolute(tempfile.gettempdir())
        / "freqtrade-research-discovery"
        / trigger_support._repo_identity_namespace(repo)
        / run_id
        / "researcher"
    )
    run_root, researcher_inbox = trigger_support._validate_run_paths(
        repo, run_path, expected_researcher
    )
    _require_plain_directory(run_root, "run_artifact_missing")
    base_entries = {
        "trigger.json",
        "researcher-task.md",
    }
    present = {path.name for path in run_root.iterdir()}
    if "critic-task.md" in present and "ideas" not in present:
        raise DiscoveryError("run_artifact_conflict", "critic-task.md before ideas")
    human = {"human-review.zh-CN.md", "human-review.zh-CN.html"}
    if present & human and (present & human) != human:
        raise DiscoveryError("run_artifact_conflict", "partial human review")
    if present & human and "shortlist.json" not in present:
        raise DiscoveryError("run_artifact_conflict", "human review before shortlist")
    if "critiques" in present and "ideas" not in present:
        raise DiscoveryError("run_artifact_conflict", "critiques before ideas")
    if "shortlist.json" in present and not {"ideas", "critiques"}.issubset(present):
        raise DiscoveryError("run_artifact_conflict", "shortlist before reviews")
    if "approval.json" in present and "shortlist.json" not in present:
        raise DiscoveryError("run_artifact_conflict", "approval before shortlist")
    if "handoff.json" in present and "approval.json" not in present:
        raise DiscoveryError("run_artifact_conflict", "handoff before approval")
    allowed_entries = set(base_entries)
    if "ideas" in present:
        allowed_entries.update({"ideas", "critic-task.md"})
    if "critiques" in present:
        allowed_entries.add("critiques")
    if "shortlist.json" in present:
        allowed_entries.update({"shortlist.json", *human})
    if "approval.json" in present:
        allowed_entries.add("approval.json")
    if "handoff.json" in present:
        allowed_entries.add("handoff.json")
    unexpected = sorted(path.name for path in run_root.iterdir() if path.name not in allowed_entries)
    if unexpected:
        raise DiscoveryError("run_artifact_conflict", json.dumps(unexpected))
    trigger_path = run_root / "trigger.json"
    packet_path = run_root / "researcher-task.md"
    trigger = _load_json_mapping(trigger_path, "run_artifact_missing")
    _require_regular_file(packet_path, "run_artifact_missing")
    validate_artifact(repo, "research-trigger.schema.json", trigger)
    state, allowed_sources = trigger_support._bound_context(repo, trigger)
    expected = trigger_support._expected_result(trigger, repo)
    if expected["run_id"] != run_id or expected["run_path"] != run_path.as_posix():
        raise DiscoveryError("run_artifact_conflict", run_id)

    context: dict[str, object] = {
        "repo": repo,
        "run_id": run_id,
        "run_path": run_path,
        "run_root": run_root,
        "researcher_inbox": researcher_inbox,
        "critic_inbox": researcher_inbox.parent / "critic",
        "trigger": trigger,
        "state": state,
        "allowed_sources": set(allowed_sources),
    }
    if registry_path is not None:
        registry_path = Path(registry_path)
        if not registry_path.is_file():
            raise DiscoveryError("registry_missing", registry_path.name)
        connection = open_director_registry(registry_path)
        try:
            rows = connection.execute(
                "SELECT run_id, trigger_fingerprint, status, state_fingerprint, "
                "payload_json, created_at FROM research_discovery_runs WHERE run_id=?",
                (run_id,),
            ).fetchall()
            if len(rows) != 1:
                raise DiscoveryError("registry_run_conflict", run_id)
            row = rows[0]
            try:
                payload = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise DiscoveryError("registry_run_conflict", run_id) from exc
            if (
                row["run_id"] != run_id
                or row["trigger_fingerprint"] != trigger["trigger_fingerprint"]
                or row["status"] != "awaiting_researcher"
                or row["state_fingerprint"]
                != trigger["research_state_fingerprint"]
                or row["created_at"] != trigger["created_at"]
                or payload != expected
            ):
                raise DiscoveryError("registry_run_conflict", run_id)
        finally:
            connection.close()
    return context


def _validated_inbox(
    context: dict[str, object], inbox: Path, role: str
) -> list[Path]:
    expected_key = "researcher_inbox" if role == "researcher" else "critic_inbox"
    expected = trigger_support._lexical_absolute(context[expected_key])
    supplied = Path(inbox)
    supplied_absolute = supplied if supplied.is_absolute() else Path.cwd() / supplied
    actual = trigger_support._lexical_absolute(supplied_absolute)
    if os.path.normcase(str(supplied_absolute)) != os.path.normcase(str(actual)):
        raise DiscoveryError("temp_inbox_invalid", role)
    if os.path.normcase(str(actual)) != os.path.normcase(str(expected)):
        raise DiscoveryError("temp_inbox_invalid", role)
    temp_root = trigger_support._lexical_absolute(tempfile.gettempdir())
    trigger_support._assert_no_reparse_components(
        temp_root, actual, "temp_reparse_forbidden"
    )
    repo = trigger_support._lexical_absolute(context["repo"])
    if actual.is_relative_to(repo) or actual.resolve(strict=False).is_relative_to(
        repo.resolve(strict=True)
    ):
        raise DiscoveryError("temp_inbox_invalid", role)
    _require_plain_directory(actual, "temp_inbox_invalid")
    paths = sorted(actual.iterdir(), key=lambda item: item.name)
    for path in paths:
        if path.suffix.lower() != ".json":
            raise DiscoveryError("temp_inbox_entry_invalid", path.name)
        _require_regular_file(path, "temp_inbox_entry_invalid")
    return paths


def _validated_director_result_path(repo: Path, supplied: str | Path) -> Path:
    repo = trigger_support._lexical_absolute(repo)
    raw = Path(supplied)
    joined = raw if raw.is_absolute() else repo / raw
    normalized = trigger_support._lexical_absolute(joined)
    allowed_root = trigger_support._lexical_absolute(repo / _DIRECTOR_RESULT_ROOT)
    if (
        ".." in raw.parts
        or normalized.suffix.lower() != ".json"
        or not normalized.is_relative_to(allowed_root)
    ):
        raise DiscoveryError("director_result_path_invalid", normalized.name)
    trigger_support._assert_no_reparse_components(
        repo, normalized, "director_result_path_invalid"
    )
    return normalized


def _ranking_policy(repo: Path) -> dict[str, object]:
    path = trigger_support._repo_regular_file(
        repo,
        Path("research/discovery/policy/ranking-policy.yaml"),
        "ranking_policy_missing",
        "ranking_policy_invalid",
    )
    try:
        policy = load_document(path)
    except Exception as exc:
        raise DiscoveryError("ranking_policy_invalid", type(exc).__name__) from exc
    expected = {
        "schema_version": "research-ranking-policy-v1",
        "weights": {
            "expected_information_gain": 0.30,
            "falsifiability_and_mechanism_clarity": 0.20,
            "feasibility_with_existing_data": 0.20,
            "novelty_and_non_duplication": 0.15,
            "robustness_relevance": 0.15,
        },
        "penalties": {
            "risk": {"low": 0.00, "medium": 0.05, "high": 0.15, "forbidden": "reject"},
            "cost": {"low": 0.00, "medium": 0.03, "high": 0.08},
            "contamination": {"none": 0.00, "low": 0.02, "medium": 0.08, "high": "reject"},
            "sources": {"includes_A": 0.00, "B_without_A": 0.02, "C_only": "reject"},
        },
        "shortlist_threshold": 0.55,
        "max_shortlist": 3,
        "initial_idea_min": 6,
        "initial_idea_max": 10,
        "max_ideas_per_family": 2,
        "max_revisions_per_cycle": 1,
        "tie_breakers": ["lower_risk", "lower_cost", "semantic_fingerprint"],
        "return_metrics_are_ranking_inputs": False,
    }
    if policy != expected:
        raise DiscoveryError("ranking_policy_invalid", "frozen policy mismatch")
    return policy


def _approved_dataset_ids(state: dict[str, object]) -> set[str]:
    approved: set[str] = set()
    datasets = state.get("datasets")
    if not isinstance(datasets, list):
        raise DiscoveryError("data_readiness_invalid", "datasets")
    for item in datasets:
        if not isinstance(item, dict):
            continue
        intended = item.get("intended_use")
        dataset_id = item.get("dataset_id")
        if (
            isinstance(dataset_id, str)
            and isinstance(intended, str)
            and intended.startswith("development")
            and item.get("sealed") is True
        ):
            approved.add(dataset_id)
    return approved


def _validate_idea_payload(
    context: dict[str, object], raw: dict[str, object]
) -> dict[str, object]:
    if "semantic_fingerprint" in raw:
        raise DiscoveryError(
            "managed_fingerprint_forbidden", "semantic_fingerprint"
        )
    scope = raw.get("fixed_scope_confirmation")
    if isinstance(scope, dict):
        assert_fixed_scope(scope)
    payload = dict(raw)
    payload["semantic_fingerprint"] = artifact_fingerprint(
        payload, "semantic_fingerprint"
    )
    validate_artifact(context["repo"], "research-idea.schema.json", payload)
    _require_identifier(payload["idea_id"], "idea_id")
    trigger = context["trigger"]
    if payload["research_state_fingerprint"] != trigger["research_state_fingerprint"]:
        raise DiscoveryError("research_state_conflict", str(payload["idea_id"]))

    validate_sources(payload["source_refs"], context["repo"])
    source_policy = load_document(
        context["repo"] / "research/discovery/policy/source-policy.yaml"
    )
    forbidden = trigger_support._forbidden_path_parts(source_policy)
    for source in payload["source_refs"]:
        if source["source_class"] != "A":
            continue
        safe = trigger_support._safe_repo_source(
            context["repo"], source.get("path"), forbidden
        )
        if safe is None:
            raise DiscoveryError("source_forbidden", str(source.get("path")))
        if safe not in context["allowed_sources"]:
            raise DiscoveryError("source_not_allowlisted", safe)

    required_datasets = payload["required_datasets"]
    if payload["data_readiness"] == "ready":
        approved = _approved_dataset_ids(context["state"])
        if not required_datasets or not set(required_datasets).issubset(approved):
            raise DiscoveryError(
                "data_readiness_invalid", str(payload["idea_id"])
            )
    return payload


def _read_idea_artifact(
    repo: Path, path: Path, expected: dict[str, object] | None = None
) -> dict[str, object]:
    payload = _load_json_mapping(path, "idea_artifact_conflict")
    validate_artifact(repo, "research-idea.schema.json", payload)
    if payload.get("semantic_fingerprint") != artifact_fingerprint(
        payload, "semantic_fingerprint"
    ):
        raise DiscoveryError("idea_artifact_conflict", path.name)
    if expected is not None and payload != expected:
        raise DiscoveryError("idea_artifact_conflict", path.name)
    return payload


def _revalidate_stored_idea(
    context: dict[str, object], payload: dict[str, object]
) -> None:
    draft = dict(payload)
    draft.pop("semantic_fingerprint", None)
    if _validate_idea_payload(context, draft) != payload:
        raise DiscoveryError(
            "idea_artifact_conflict", str(payload.get("idea_id"))
        )


def _load_latest_ideas(
    connection: sqlite3.Connection, context: dict[str, object]
) -> tuple[dict[str, dict[str, object]], dict[str, Path]]:
    rows = connection.execute(
        "SELECT idea_key, run_id, idea_id, idea_version, semantic_fingerprint, "
        "strategy_family, status, payload_json FROM research_discovery_ideas "
        "WHERE run_id=? ORDER BY idea_id, idea_version",
        (context["run_id"],),
    ).fetchall()
    by_id: dict[str, list[dict[str, object]]] = {}
    expected_paths: dict[str, Path] = {}
    root = context["run_root"] / "ideas"
    if rows:
        _require_plain_directory(root, "idea_artifact_conflict")
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiscoveryError("registry_idea_conflict", row["idea_key"]) from exc
        idea_id = _require_identifier(payload.get("idea_id"), "idea_id")
        version = payload.get("idea_version")
        key = f"{context['run_id']}:{idea_id}:v{version}"
        if (
            row["idea_key"] != key
            or row["run_id"] != context["run_id"]
            or row["idea_id"] != idea_id
            or row["idea_version"] != version
            or row["semantic_fingerprint"] != payload.get("semantic_fingerprint")
            or row["strategy_family"] != payload.get("strategy_family")
            or row["status"] != "discovered"
        ):
            raise DiscoveryError("registry_idea_conflict", key)
        validate_artifact(context["repo"], "research-idea.schema.json", payload)
        _revalidate_stored_idea(context, payload)
        path = root / f"{idea_id}-v{version}.json"
        _read_idea_artifact(context["repo"], path, payload)
        expected_paths[path.name] = path
        by_id.setdefault(idea_id, []).append(payload)
    if rows:
        actual = {path.name for path in root.iterdir()}
        if actual != set(expected_paths):
            raise DiscoveryError("idea_artifact_conflict", "ideas layout")
    latest: dict[str, dict[str, object]] = {}
    for idea_id, versions in by_id.items():
        numbers = [int(item["idea_version"]) for item in versions]
        if len(numbers) != len(set(numbers)):
            raise DiscoveryError("registry_idea_conflict", idea_id)
        latest[idea_id] = max(versions, key=lambda item: int(item["idea_version"]))
    return latest, expected_paths


def _event_row(
    connection: sqlite3.Connection,
    run_id: str,
    event_type: str,
    payload: dict[str, object],
) -> None:
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    event_id = f"discovery-event-{fingerprint({'run_id': run_id, 'event_type': event_type, 'payload': payload})[:24]}"
    row = connection.execute(
        "SELECT run_id, event_type, reason_code, payload_json "
        "FROM research_discovery_events WHERE event_id=?",
        (event_id,),
    ).fetchone()
    if row is not None:
        if (
            row["run_id"] != run_id
            or row["event_type"] != event_type
            or row["reason_code"] is not None
            or row["payload_json"] != payload_json
        ):
            raise DiscoveryError("registry_event_conflict", event_id)
        return
    connection.execute(
        "INSERT INTO research_discovery_events("
        "event_id, run_id, event_type, reason_code, payload_json, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (event_id, run_id, event_type, None, payload_json, utc_now()),
    )


def _latest_event(
    connection: sqlite3.Connection, run_id: str
) -> tuple[int, str, dict[str, object]] | None:
    row = connection.execute(
        "SELECT rowid, event_type, payload_json FROM research_discovery_events "
        "WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiscoveryError("registry_event_conflict", run_id) from exc
    if not isinstance(payload, dict):
        raise DiscoveryError("registry_event_conflict", run_id)
    return int(row["rowid"]), str(row["event_type"]), payload


def _require_not_completed(
    connection: sqlite3.Connection, run_id: str
) -> tuple[int, str, dict[str, object]] | None:
    latest = _latest_event(connection, run_id)
    if latest is not None and latest[1] == "completed":
        raise DiscoveryError("run_completed", run_id)
    return latest


def _reject_completed_preflight(registry_path: Path, run_id: str) -> None:
    connection = open_director_registry(registry_path)
    try:
        _require_not_completed(connection, run_id)
    finally:
        connection.close()


def _guard_transaction_lifecycle(
    connection: sqlite3.Connection,
    run_id: str,
    expected: tuple[int, str, dict[str, object]] | None,
    event_type: str,
    event_payload: dict[str, object],
) -> bool:
    current = _latest_event(connection, run_id)
    exact_target = (
        current is not None
        and current[1] == event_type
        and current[2] == event_payload
    )
    if current is not None and current[1] == "completed":
        if event_type == "completed" and exact_target:
            return True
        raise DiscoveryError("run_completed", run_id)
    if current == expected:
        return exact_target
    if exact_target:
        return True
    raise DiscoveryError(
        "lifecycle_order_invalid",
        json.dumps(
            {
                "expected_rowid": expected[0] if expected is not None else None,
                "expected_event": expected[1] if expected is not None else None,
                "actual_rowid": current[0] if current is not None else None,
                "actual_event": current[1] if current is not None else None,
            },
            sort_keys=True,
        ),
    )


def _publish_batch(
    context: dict[str, object],
    connection: sqlite3.Connection,
    artifacts: list[tuple[Path, dict[str, object]]],
    record: Callable[
        [sqlite3.Connection, Path, dict[str, object], bool], bool
    ],
    event_type: str,
    event_payload: dict[str, object],
    integrity_check: Callable[[], None] | None = None,
    transaction_guard: Callable[[sqlite3.Connection], bool] | None = None,
) -> None:
    run_root = context["run_root"]
    runs_root = run_root.parent
    _require_plain_directory(runs_root, "run_artifact_conflict")
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".review-staging-{context['run_id']}-", dir=runs_root
        )
    )
    staged: dict[Path, Path] = {}
    published: dict[Path, tuple[int, int]] = {}
    created_parents: list[Path] = []
    try:
        trigger_support._assert_no_reparse_components(
            runs_root, staging, "run_reparse_forbidden"
        )
        for destination, payload in artifacts:
            trigger_support._assert_no_reparse_components(
                run_root, destination, "run_reparse_forbidden"
            )
            exists = os.path.lexists(destination)
            if exists:
                if (
                    _load_json_mapping(
                        destination, "immutable_artifact_conflict"
                    )
                    != payload
                ):
                    raise DiscoveryError(
                        "immutable_artifact_conflict", destination.name
                    )
                continue
            stage_path = staging / destination.name
            write_json(stage_path, payload)
            if load_document(stage_path) != payload:
                raise DiscoveryError(
                    "artifact_staging_conflict", destination.name
                )
            staged[destination] = stage_path
        if integrity_check is not None:
            integrity_check()
        connection.execute("BEGIN IMMEDIATE")
        exact_replay = (
            transaction_guard(connection)
            if transaction_guard is not None
            else False
        )
        current_artifacts: dict[Path, bool] = {}
        current_rows: dict[Path, bool] = {}
        for destination, payload in artifacts:
            artifact_exists = os.path.lexists(destination)
            current_artifacts[destination] = artifact_exists
            if artifact_exists and (
                _load_json_mapping(destination, "immutable_artifact_conflict")
                != payload
            ):
                raise DiscoveryError(
                    "immutable_artifact_conflict", destination.name
                )
            row_exists = record(connection, destination, payload, False)
            current_rows[destination] = row_exists
            if row_exists != artifact_exists:
                raise DiscoveryError(
                    "registry_artifact_conflict", destination.name
                )
        if exact_replay:
            if not all(current_rows.values()) or not all(
                current_artifacts.values()
            ):
                raise DiscoveryError(
                    "registry_artifact_conflict", str(context["run_id"])
                )
            if integrity_check is not None:
                integrity_check()
            try:
                shutil.rmtree(staging)
            except OSError as exc:
                raise DiscoveryError(
                    "artifact_staging_cleanup_failed",
                    f"{staging.name}: {type(exc).__name__}",
                ) from exc
            if integrity_check is not None:
                integrity_check()
            connection.commit()
            return
        if artifacts and all(current_rows.values()) and all(
            current_artifacts.values()
        ):
            raise DiscoveryError(
                "registry_artifact_conflict", str(context["run_id"])
            )
        for destination, payload in artifacts:
            if current_rows[destination]:
                continue
            if destination not in staged:
                raise DiscoveryError(
                    "immutable_artifact_conflict", destination.name
                )
            if record(connection, destination, payload, True):
                raise DiscoveryError(
                    "registry_artifact_conflict", destination.name
                )
        _event_row(
            connection,
            str(context["run_id"]),
            event_type,
            event_payload,
        )
        if integrity_check is not None:
            integrity_check()
        for destination, stage_path in staged.items():
            if not destination.parent.exists():
                destination.parent.mkdir()
                created_parents.append(destination.parent)
            _require_plain_directory(
                destination.parent, "run_artifact_conflict"
            )
            staged_metadata = stage_path.stat(follow_symlinks=False)
            staged_identity = (staged_metadata.st_dev, staged_metadata.st_ino)
            try:
                os.link(stage_path, destination)
            except FileExistsError as exc:
                raise DiscoveryError(
                    "immutable_artifact_conflict", destination.name
                ) from exc
            except OSError as exc:
                raise DiscoveryError(
                    "artifact_publish_failed",
                    f"{destination.name}: {type(exc).__name__}",
                ) from exc
            metadata = destination.stat(follow_symlinks=False)
            if (metadata.st_dev, metadata.st_ino) != staged_identity:
                raise DiscoveryError(
                    "immutable_artifact_conflict", destination.name
                )
            published[destination] = staged_identity
        if integrity_check is not None:
            integrity_check()
        try:
            shutil.rmtree(staging)
        except OSError as exc:
            raise DiscoveryError(
                "artifact_staging_cleanup_failed",
                f"{staging.name}: {type(exc).__name__}",
            ) from exc
        if integrity_check is not None:
            integrity_check()
        connection.commit()
    except Exception as original:
        cleanup_failures: list[str] = []
        try:
            connection.rollback()
        except Exception as exc:
            cleanup_failures.append(f"rollback: {type(exc).__name__}: {exc}")
        for path, identity in reversed(list(published.items())):
            try:
                metadata = path.stat(follow_symlinks=False)
                if (metadata.st_dev, metadata.st_ino) == identity:
                    path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                cleanup_failures.append(
                    f"unlink {path.name}: {type(exc).__name__}: {exc}"
                )
        for path in reversed(created_parents):
            try:
                path.rmdir()
            except FileNotFoundError:
                pass
            except OSError as exc:
                if not path.is_dir() or not any(path.iterdir()):
                    cleanup_failures.append(
                        f"rmdir {path.name}: {type(exc).__name__}: {exc}"
                    )
        if os.path.lexists(staging):
            try:
                shutil.rmtree(staging)
            except OSError as exc:
                cleanup_failures.append(
                    f"rmtree {staging.name}: {type(exc).__name__}: {exc}"
                )
        if cleanup_failures:
            raise DiscoveryError(
                "rollback_cleanup_failed",
                f"{type(original).__name__}: {original}; "
                + "; ".join(cleanup_failures),
            ) from original
        raise


def ingest_ideas(
    repo: Path,
    run_id: str,
    inbox: Path,
    registry_path: Path,
) -> list[dict[str, object]]:
    context = _canonical_run_context(repo, run_id, registry_path)
    _reject_completed_preflight(registry_path, run_id)
    policy = _ranking_policy(context["repo"])
    paths = _validated_inbox(context, inbox, "researcher")
    raw_payloads = [_load_json_mapping(path, "inbox_document_invalid") for path in paths]
    ids = [item.get("idea_id") for item in raw_payloads]
    if any(not isinstance(idea_id, str) for idea_id in ids):
        raise DiscoveryError("artifact_validation_failed", "idea_id")
    if len(ids) != len(set(ids)):
        raise DiscoveryError("idea_id_duplicate", json.dumps(ids))

    connection = open_director_registry(registry_path)
    try:
        latest, _ = _load_latest_ideas(connection, context)
        lifecycle = _require_not_completed(connection, run_id)
        if not latest and lifecycle is not None:
            raise DiscoveryError("lifecycle_order_invalid", lifecycle[1])
        if latest and lifecycle is None:
            raise DiscoveryError("lifecycle_order_invalid", "missing event")
        if not latest:
            if not int(policy["initial_idea_min"]) <= len(raw_payloads) <= int(
                policy["initial_idea_max"]
            ):
                raise DiscoveryError(
                    "idea_count_out_of_bounds", str(len(raw_payloads))
                )
        elif not raw_payloads:
            raise DiscoveryError("revision_batch_empty", run_id)

        payloads = [_validate_idea_payload(context, raw) for raw in raw_payloads]
        family_counts = Counter(str(item["strategy_family"]) for item in payloads)
        if not latest and max(family_counts.values(), default=0) > int(
            policy["max_ideas_per_family"]
        ):
            raise DiscoveryError(
                "strategy_family_cap_exceeded",
                json.dumps(family_counts, sort_keys=True),
            )

        def idea_event_payload(revision: bool) -> dict[str, object]:
            ordered = sorted(payloads, key=lambda value: str(value["idea_id"]))
            return {
                "idea_fingerprints": [
                    item["semantic_fingerprint"] for item in ordered
                ],
                "idea_ids": [str(item["idea_id"]) for item in ordered],
                "revision": revision,
            }

        revision_mode = False
        if latest:
            submitted_versions = {
                str(item["idea_id"]): int(item["idea_version"]) for item in payloads
            }
            same_versions = all(
                idea_id in latest
                and version == int(latest[idea_id]["idea_version"])
                for idea_id, version in submitted_versions.items()
            )
            if not same_versions:
                revision_mode = True
                for payload in payloads:
                    idea_id = str(payload["idea_id"])
                    prior = latest.get(idea_id)
                    if int(payload["idea_version"]) > 2 or (
                        prior is not None and int(prior["idea_version"]) >= 2
                    ):
                        raise DiscoveryError("revision_limit_exceeded", idea_id)
                if lifecycle is None or lifecycle[1] != "critiques_ingested":
                    raise DiscoveryError(
                        "lifecycle_order_invalid",
                        "revision requires latest critiques_ingested event",
                    )
                critiques = _load_latest_critiques(connection, context, latest)
                pending_revision_ids = {
                    idea_id
                    for idea_id, idea in latest.items()
                    if int(idea["idea_version"]) == 1
                    and critiques[idea_id]["verdict"] == "revise"
                }
                if {str(item["idea_id"]) for item in payloads} != pending_revision_ids:
                    raise DiscoveryError(
                        "revision_id_set_mismatch",
                        json.dumps(
                            {
                                "expected": sorted(pending_revision_ids),
                                "actual": sorted(
                                    str(item["idea_id"]) for item in payloads
                                ),
                            },
                            sort_keys=True,
                        ),
                    )
                projected = dict(latest)
                for payload in payloads:
                    idea_id = str(payload["idea_id"])
                    version = int(payload["idea_version"])
                    if version > 2:
                        raise DiscoveryError("revision_limit_exceeded", idea_id)
                    prior = latest.get(idea_id)
                    if prior is None or version != int(prior["idea_version"]) + 1:
                        raise DiscoveryError("revision_version_invalid", idea_id)
                    if int(prior["idea_version"]) >= 2:
                        raise DiscoveryError("revision_limit_exceeded", idea_id)
                    if prior["strategy_family"] != payload["strategy_family"]:
                        raise DiscoveryError("revision_family_conflict", idea_id)
                    if idea_id not in pending_revision_ids:
                        raise DiscoveryError("revision_not_requested", idea_id)
                    projected[idea_id] = payload
                projected_counts = Counter(
                    str(item["strategy_family"]) for item in projected.values()
                )
                if max(projected_counts.values(), default=0) > int(
                    policy["max_ideas_per_family"]
                ):
                    raise DiscoveryError(
                        "strategy_family_cap_exceeded",
                        json.dumps(projected_counts, sort_keys=True),
                    )
            else:
                if lifecycle is None or lifecycle[1] != "ideas_ingested":
                    raise DiscoveryError(
                        "lifecycle_order_invalid",
                        "idea replay requires latest ideas_ingested event",
                    )
                if lifecycle[2].get("revision") is True:
                    revision_mode = True
                    expected_replay = idea_event_payload(True)
                    if lifecycle[2] != expected_replay or any(
                        latest.get(str(item["idea_id"]), {}).get(
                            "semantic_fingerprint"
                        )
                        != item["semantic_fingerprint"]
                        for item in payloads
                    ):
                        raise DiscoveryError(
                            "revision_replay_mismatch",
                            json.dumps(
                                {
                                    "expected": lifecycle[2],
                                    "actual": expected_replay,
                                },
                                sort_keys=True,
                            ),
                        )
                elif set(submitted_versions) != set(latest):
                    raise DiscoveryError(
                        "idea_id_set_mismatch",
                        json.dumps(
                            {
                                "expected": sorted(latest),
                                "actual": sorted(submitted_versions),
                            },
                            sort_keys=True,
                        ),
                    )
        else:
            for payload in payloads:
                if payload["idea_version"] != 1:
                    raise DiscoveryError(
                        "initial_idea_version_invalid", str(payload["idea_id"])
                    )

        artifacts = [
            (
                context["run_root"]
                / "ideas"
                / f"{item['idea_id']}-v{item['idea_version']}.json",
                item,
            )
            for item in payloads
        ]

        def record(
            db: sqlite3.Connection,
            destination: Path,
            idea: dict[str, object],
            allow_insert: bool,
        ) -> bool:
            idea_key = f"{run_id}:{idea['idea_id']}:v{idea['idea_version']}"
            rows = db.execute(
                "SELECT idea_key, run_id, idea_id, idea_version, semantic_fingerprint, "
                "strategy_family, status, payload_json FROM research_discovery_ideas "
                "WHERE idea_key=? OR semantic_fingerprint=?",
                (idea_key, idea["semantic_fingerprint"]),
            ).fetchall()
            if len(rows) > 1:
                raise DiscoveryError("registry_idea_conflict", idea_key)
            payload_json = json.dumps(idea, ensure_ascii=False, sort_keys=True)
            if rows:
                row = rows[0]
                if (
                    row["idea_key"] != idea_key
                    or row["run_id"] != run_id
                    or row["idea_id"] != idea["idea_id"]
                    or row["idea_version"] != idea["idea_version"]
                    or row["semantic_fingerprint"] != idea["semantic_fingerprint"]
                    or row["strategy_family"] != idea["strategy_family"]
                    or row["status"] != "discovered"
                    or row["payload_json"] != payload_json
                ):
                    raise DiscoveryError("registry_idea_conflict", idea_key)
                return True
            if not allow_insert:
                return False
            db.execute(
                "INSERT INTO research_discovery_ideas("
                "idea_key, run_id, idea_id, idea_version, semantic_fingerprint, "
                "strategy_family, status, payload_json, created_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    idea_key,
                    run_id,
                    idea["idea_id"],
                    idea["idea_version"],
                    idea["semantic_fingerprint"],
                    idea["strategy_family"],
                    "discovered",
                    payload_json,
                    utc_now(),
                ),
            )
            return False

        event_payload = idea_event_payload(revision_mode)

        def transaction_guard(db: sqlite3.Connection) -> bool:
            return _guard_transaction_lifecycle(
                db,
                run_id,
                lifecycle,
                "ideas_ingested",
                event_payload,
            )

        _publish_batch(
            context,
            connection,
            artifacts,
            record,
            "ideas_ingested",
            event_payload,
            transaction_guard=transaction_guard,
        )
        return payloads
    finally:
        connection.close()


def _latest_idea_files(context: dict[str, object]) -> list[dict[str, object]]:
    root = context["run_root"] / "ideas"
    _require_plain_directory(root, "idea_artifact_missing")
    latest: dict[str, dict[str, object]] = {}
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        payload = _read_idea_artifact(context["repo"], path)
        _revalidate_stored_idea(context, payload)
        idea_id = _require_identifier(payload["idea_id"], "idea_id")
        expected_name = f"{idea_id}-v{payload['idea_version']}.json"
        if path.name != expected_name:
            raise DiscoveryError("idea_artifact_conflict", path.name)
        current = latest.get(idea_id)
        if current is None or int(payload["idea_version"]) > int(
            current["idea_version"]
        ):
            latest[idea_id] = payload
    if not latest:
        raise DiscoveryError("idea_artifact_missing", "ideas")
    return [latest[key] for key in sorted(latest)]


def render_critic_packet(repo: Path, run_id: str) -> str:
    context = _canonical_run_context(repo, run_id)
    ideas = _latest_idea_files(context)
    prompt_path = trigger_support._repo_regular_file(
        context["repo"],
        Path("research/discovery/prompts/critic.md"),
        "critic_prompt_missing",
        "critic_prompt_invalid",
    )
    prompt = prompt_path.read_text(encoding="utf-8")
    if "Do not edit" not in prompt:
        raise DiscoveryError("critic_prompt_invalid", "Do not edit")
    idea_lines = "\n".join(
        "- `{idea_id}` v{version}: `{fingerprint}` (`{path}`)".format(
            idea_id=item["idea_id"],
            version=item["idea_version"],
            fingerprint=item["semantic_fingerprint"],
            path=(
                Path("research/discovery/runs")
                / run_id
                / "ideas"
                / f"{item['idea_id']}-v{item['idea_version']}.json"
            ).as_posix(),
        )
        for item in ideas
    )
    return (
        "# Critic Task Packet / 批评者任务包\n\n"
        "## Immutable ideas / 不可变研究想法\n\n"
        f"{idea_lines}\n\n"
        "Do not edit, replace, rename, or rewrite any idea artifact. Compare each "
        "fingerprint exactly and emit one critique per latest immutable idea.\n\n"
        "## Output / 输出\n\n"
        f"Write JSON only to this system TEMP Critic inbox: `{context['critic_inbox']}`. "
        "Do not write to the governed run directory.\n\n"
        "## Role contract / 角色合同\n\n"
        f"{prompt.rstrip()}\n"
    )


def _idea_source_highest(idea: dict[str, object]) -> str:
    classes = {str(item["source_class"]) for item in idea["source_refs"]}
    for value in ("A", "B", "C"):
        if value in classes:
            return value
    raise DiscoveryError("source_class_invalid", str(idea["idea_id"]))


def _validate_critique_payload(
    context: dict[str, object],
    raw: dict[str, object],
    idea: dict[str, object],
) -> dict[str, object]:
    if "critic_fingerprint" in raw:
        raise DiscoveryError("managed_fingerprint_forbidden", "critic_fingerprint")
    payload = dict(raw)
    payload["critic_fingerprint"] = artifact_fingerprint(
        payload, "critic_fingerprint"
    )
    validate_artifact(context["repo"], "research-critique.schema.json", payload)
    _require_identifier(payload["critique_id"], "critique_id")
    _validate_critique_binding(payload, idea)
    return payload


def _validate_critique_binding(
    payload: dict[str, object], idea: dict[str, object]
) -> None:
    if (
        payload["idea_id"] != idea["idea_id"]
        or payload["idea_semantic_fingerprint"]
        != idea["semantic_fingerprint"]
    ):
        raise DiscoveryError("critic_binding_mismatch", str(payload["idea_id"]))
    highest = _idea_source_highest(idea)
    if payload["source_verification"]["highest_class"] != highest:
        raise DiscoveryError("critic_source_mismatch", str(payload["idea_id"]))
    if payload["verdict"] == "pass" and (
        highest == "C" or idea["data_readiness"] != "ready"
    ):
        raise DiscoveryError("critic_pass_forbidden", str(payload["idea_id"]))


def _read_critique_artifact(
    repo: Path, path: Path, expected: dict[str, object] | None = None
) -> dict[str, object]:
    payload = _load_json_mapping(path, "critique_artifact_conflict")
    validate_artifact(repo, "research-critique.schema.json", payload)
    if payload.get("critic_fingerprint") != artifact_fingerprint(
        payload, "critic_fingerprint"
    ):
        raise DiscoveryError("critique_artifact_conflict", path.name)
    if expected is not None and payload != expected:
        raise DiscoveryError("critique_artifact_conflict", path.name)
    return payload


def ingest_critiques(
    repo: Path,
    run_id: str,
    inbox: Path,
    registry_path: Path,
) -> list[dict[str, object]]:
    context = _canonical_run_context(repo, run_id, registry_path)
    _reject_completed_preflight(registry_path, run_id)
    paths = _validated_inbox(context, inbox, "critic")
    raw_payloads = [_load_json_mapping(path, "inbox_document_invalid") for path in paths]
    idea_ids = [item.get("idea_id") for item in raw_payloads]
    if any(not isinstance(idea_id, str) for idea_id in idea_ids):
        raise DiscoveryError("artifact_validation_failed", "idea_id")
    if len(idea_ids) != len(set(idea_ids)):
        raise DiscoveryError("critique_idea_duplicate", json.dumps(idea_ids))
    critique_ids = [item.get("critique_id") for item in raw_payloads]
    if any(not isinstance(critique_id, str) for critique_id in critique_ids):
        raise DiscoveryError("artifact_validation_failed", "critique_id")
    if len(critique_ids) != len(set(critique_ids)):
        raise DiscoveryError("critique_id_duplicate", json.dumps(critique_ids))

    connection = open_director_registry(registry_path)
    try:
        latest, idea_paths = _load_latest_ideas(connection, context)
        lifecycle = _require_not_completed(connection, run_id)
        if lifecycle is None or lifecycle[1] not in {
            "ideas_ingested",
            "critiques_ingested",
        }:
            raise DiscoveryError(
                "lifecycle_order_invalid",
                "critique requires latest ideas_ingested event",
            )
        if set(idea_ids) != set(latest):
            raise DiscoveryError(
                "critique_id_set_mismatch",
                json.dumps(
                    {
                        "expected": sorted(latest),
                        "actual": sorted(str(value) for value in idea_ids),
                    },
                    sort_keys=True,
                ),
            )
        before_hashes = {
            name: sha256_file(path) for name, path in idea_paths.items()
        }

        def idea_integrity() -> None:
            after = {name: sha256_file(path) for name, path in idea_paths.items()}
            if after != before_hashes:
                raise DiscoveryError("idea_artifact_changed", run_id)
            _load_latest_ideas(connection, context)

        payloads = [
            _validate_critique_payload(context, raw, latest[str(raw["idea_id"])])
            for raw in raw_payloads
        ]
        artifacts = [
            (
                context["run_root"]
                / "critiques"
                / f"{item['critique_id']}.json",
                item,
            )
            for item in payloads
        ]

        def record(
            db: sqlite3.Connection,
            destination: Path,
            critique: dict[str, object],
            allow_insert: bool,
        ) -> bool:
            idea = latest[str(critique["idea_id"])]
            idea_key = f"{run_id}:{idea['idea_id']}:v{idea['idea_version']}"
            rows = db.execute(
                "SELECT critique_id, run_id, idea_key, verdict, critic_fingerprint, "
                "payload_json FROM research_discovery_critiques "
                "WHERE critique_id=? OR critic_fingerprint=? OR idea_key=?",
                (
                    critique["critique_id"],
                    critique["critic_fingerprint"],
                    idea_key,
                ),
            ).fetchall()
            if len(rows) > 1:
                raise DiscoveryError("registry_critique_conflict", idea_key)
            payload_json = json.dumps(critique, ensure_ascii=False, sort_keys=True)
            if rows:
                row = rows[0]
                if (
                    row["critique_id"] != critique["critique_id"]
                    or row["run_id"] != run_id
                    or row["idea_key"] != idea_key
                    or row["verdict"] != critique["verdict"]
                    or row["critic_fingerprint"] != critique["critic_fingerprint"]
                    or row["payload_json"] != payload_json
                ):
                    raise DiscoveryError("registry_critique_conflict", idea_key)
                return True
            if not allow_insert:
                return False
            db.execute(
                "INSERT INTO research_discovery_critiques("
                "critique_id, run_id, idea_key, verdict, critic_fingerprint, "
                "payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    critique["critique_id"],
                    run_id,
                    idea_key,
                    critique["verdict"],
                    critique["critic_fingerprint"],
                    payload_json,
                    utc_now(),
                ),
            )
            return False

        event_payload = {
            "critic_fingerprints": [
                item["critic_fingerprint"]
                for item in sorted(payloads, key=lambda value: str(value["idea_id"]))
            ],
            "idea_ids": sorted(str(item["idea_id"]) for item in payloads),
        }

        def transaction_guard(db: sqlite3.Connection) -> bool:
            return _guard_transaction_lifecycle(
                db,
                run_id,
                lifecycle,
                "critiques_ingested",
                event_payload,
            )

        _publish_batch(
            context,
            connection,
            artifacts,
            record,
            "critiques_ingested",
            event_payload,
            idea_integrity,
            transaction_guard=transaction_guard,
        )
        return payloads
    finally:
        connection.close()


def _load_latest_critiques(
    connection: sqlite3.Connection,
    context: dict[str, object],
    latest: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    root = context["run_root"] / "critiques"
    _require_plain_directory(root, "critique_artifact_missing")
    result: dict[str, dict[str, object]] = {}
    expected_names: set[str] = set()
    for idea_id, idea in latest.items():
        idea_key = f"{context['run_id']}:{idea_id}:v{idea['idea_version']}"
        rows = connection.execute(
            "SELECT critique_id, run_id, idea_key, verdict, critic_fingerprint, "
            "payload_json FROM research_discovery_critiques WHERE idea_key=?",
            (idea_key,),
        ).fetchall()
        if len(rows) != 1:
            raise DiscoveryError("critique_coverage_incomplete", idea_id)
        row = rows[0]
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiscoveryError("registry_critique_conflict", idea_id) from exc
        if (
            row["run_id"] != context["run_id"]
            or row["idea_key"] != idea_key
            or row["critique_id"] != payload.get("critique_id")
            or row["verdict"] != payload.get("verdict")
            or row["critic_fingerprint"] != payload.get("critic_fingerprint")
        ):
            raise DiscoveryError("registry_critique_conflict", idea_id)
        path = root / f"{row['critique_id']}.json"
        stored = _read_critique_artifact(context["repo"], path, payload)
        _require_identifier(stored["critique_id"], "critique_id")
        _validate_critique_binding(stored, idea)
        expected_names.add(path.name)
        result[idea_id] = payload
    registry_names = {
        f"{row['critique_id']}.json"
        for row in connection.execute(
            "SELECT critique_id FROM research_discovery_critiques WHERE run_id=?",
            (context["run_id"],),
        )
    }
    actual_names = {path.name for path in root.iterdir()}
    if actual_names != registry_names or not expected_names.issubset(actual_names):
        raise DiscoveryError("critique_artifact_conflict", "critiques layout")
    return result


def build_shortlist(
    repo: Path, run_id: str, registry_path: Path
) -> dict[str, object]:
    context = _canonical_run_context(repo, run_id, registry_path)
    policy = _ranking_policy(context["repo"])
    connection = open_director_registry(registry_path)
    try:
        latest, _ = _load_latest_ideas(connection, context)
        lifecycle = _latest_event(connection, run_id)
        if lifecycle is None or lifecycle[1] not in {
            "critiques_ingested",
            "completed",
        }:
            raise DiscoveryError(
                "lifecycle_order_invalid",
                "shortlist requires latest critiques_ingested event",
            )
        critiques = _load_latest_critiques(connection, context, latest)
        pending_revision_ids = sorted(
            idea_id
            for idea_id, idea in latest.items()
            if int(idea["idea_version"]) == 1
            and critiques[idea_id]["verdict"] == "revise"
        )
        if pending_revision_ids:
            raise DiscoveryError(
                "revision_pending", json.dumps(pending_revision_ids)
            )
        pairs = [(latest[key], critiques[key]) for key in sorted(latest)]
        ranked = rank_eligible(pairs, policy)
        eligible_count = 0
        for idea, critique in pairs:
            if critique["verdict"] != "pass":
                continue
            try:
                score = score_idea(idea, critique, policy)
            except DiscoveryError:
                continue
            if score >= float(policy["shortlist_threshold"]):
                eligible_count += 1
        recommended = ranked[0]["idea_id"] if ranked else None
        shortlist: dict[str, object] = {
            "schema_version": "research-shortlist-v1",
            "discovery_run_id": run_id,
            "eligible_idea_count": eligible_count,
            "ranking_policy_version": policy["schema_version"],
            "ranked_ideas": ranked,
            "recommended_idea_id": recommended,
            "recommendation": (
                "research_recommended" if ranked else "no_research_recommended"
            ),
            "recommendation_reason_zh": (
                "依据冻结评分政策，建议优先评审排名最高的最小研究测试；评分仅表示研究优先级。"
                if ranked
                else "没有想法同时满足 Critic 通过与固定评分阈值，正常结束本轮研究发现。"
            ),
            "research_state_fingerprint": context["trigger"][
                "research_state_fingerprint"
            ],
        }
        shortlist["shortlist_fingerprint"] = artifact_fingerprint(
            shortlist, "shortlist_fingerprint"
        )
        validate_artifact(context["repo"], "research-shortlist.schema.json", shortlist)
        destination = context["run_root"] / "shortlist.json"

        def record(
            db: sqlite3.Connection,
            artifact_path: Path,
            payload: dict[str, object],
            allow_insert: bool,
        ) -> bool:
            rows = db.execute(
                "SELECT run_id, shortlist_fingerprint, recommendation, payload_json "
                "FROM research_discovery_shortlists WHERE run_id=? OR shortlist_fingerprint=?",
                (run_id, payload["shortlist_fingerprint"]),
            ).fetchall()
            if len(rows) > 1:
                raise DiscoveryError("registry_shortlist_conflict", run_id)
            payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if rows:
                row = rows[0]
                if (
                    row["run_id"] != run_id
                    or row["shortlist_fingerprint"]
                    != payload["shortlist_fingerprint"]
                    or row["recommendation"] != payload["recommendation"]
                    or row["payload_json"] != payload_json
                ):
                    raise DiscoveryError("registry_shortlist_conflict", run_id)
                return True
            if not allow_insert:
                return False
            db.execute(
                "INSERT INTO research_discovery_shortlists("
                "run_id, shortlist_fingerprint, recommendation, payload_json, created_at"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    run_id,
                    payload["shortlist_fingerprint"],
                    payload["recommendation"],
                    payload_json,
                    utc_now(),
                ),
            )
            return False

        completed = {
            "recommendation": shortlist["recommendation"],
            "recommended_idea_id": shortlist["recommended_idea_id"],
            "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
            "status": "completed",
        }

        def transaction_guard(db: sqlite3.Connection) -> bool:
            return _guard_transaction_lifecycle(
                db,
                run_id,
                lifecycle,
                "completed",
                completed,
            )

        _publish_batch(
            context,
            connection,
            [(destination, shortlist)],
            record,
            "completed",
            completed,
            transaction_guard=transaction_guard,
        )
        return shortlist
    finally:
        connection.close()


def _load_shortlist(
    connection: sqlite3.Connection, context: dict[str, object]
) -> dict[str, object]:
    rows = connection.execute(
        "SELECT run_id, shortlist_fingerprint, recommendation, payload_json "
        "FROM research_discovery_shortlists WHERE run_id=?",
        (context["run_id"],),
    ).fetchall()
    if len(rows) != 1:
        raise DiscoveryError("shortlist_missing", str(context["run_id"]))
    row = rows[0]
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiscoveryError("registry_shortlist_conflict", str(context["run_id"])) from exc
    validate_artifact(context["repo"], "research-shortlist.schema.json", payload)
    if (
        row["shortlist_fingerprint"] != payload["shortlist_fingerprint"]
        or row["recommendation"] != payload["recommendation"]
        or payload["shortlist_fingerprint"]
        != artifact_fingerprint(payload, "shortlist_fingerprint")
    ):
        raise DiscoveryError("registry_shortlist_conflict", str(context["run_id"]))
    stored = _load_json_mapping(
        context["run_root"] / "shortlist.json", "shortlist_artifact_conflict"
    )
    if stored != payload:
        raise DiscoveryError("shortlist_artifact_conflict", str(context["run_id"]))
    return payload


def _require_exact_completed_event(
    connection: sqlite3.Connection,
    run_id: str,
    shortlist: dict[str, object],
) -> None:
    expected = {
        "recommendation": shortlist["recommendation"],
        "recommended_idea_id": shortlist["recommended_idea_id"],
        "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
        "status": "completed",
    }
    rows = connection.execute(
        "SELECT reason_code, payload_json FROM research_discovery_events "
        "WHERE run_id=? AND event_type='completed'",
        (run_id,),
    ).fetchall()
    if len(rows) != 1:
        raise DiscoveryError("registry_event_conflict", "completed")
    try:
        payload = json.loads(rows[0]["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiscoveryError("registry_event_conflict", "completed") from exc
    if rows[0]["reason_code"] is not None or payload != expected:
        raise DiscoveryError("registry_event_conflict", "completed")


def _require_exact_critic_packet(context: dict[str, object]) -> None:
    path = context["run_root"] / "critic-task.md"
    _require_regular_file(path, "critic_packet_missing")
    expected = render_critic_packet(context["repo"], str(context["run_id"]))
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DiscoveryError("critic_packet_conflict", path.name) from exc
    if actual != expected:
        raise DiscoveryError("critic_packet_conflict", path.name)


def _decoded_exact_event(
    row: sqlite3.Row,
    run_id: str,
    expected_type: str,
) -> dict[str, object]:
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise DiscoveryError("registry_event_conflict", expected_type) from exc
    if not isinstance(payload, dict):
        raise DiscoveryError("registry_event_conflict", expected_type)
    expected_id = (
        "discovery-event-"
        + fingerprint(
            {"run_id": run_id, "event_type": expected_type, "payload": payload}
        )[:24]
    )
    if (
        row["event_id"] != expected_id
        or row["run_id"] != run_id
        or row["event_type"] != expected_type
        or row["reason_code"] is not None
        or row["payload_json"]
        != json.dumps(payload, ensure_ascii=False, sort_keys=True)
        or not isinstance(row["created_at"], str)
        or not row["created_at"]
    ):
        raise DiscoveryError("registry_event_conflict", expected_type)
    return payload


def _require_exact_review_event_chain(
    connection: sqlite3.Connection,
    context: dict[str, object],
    latest: dict[str, dict[str, object]],
    critiques: dict[str, dict[str, object]],
    shortlist: dict[str, object],
) -> list[str]:
    run_id = str(context["run_id"])
    rows = connection.execute(
        "SELECT rowid, event_id, run_id, event_type, reason_code, payload_json, "
        "created_at FROM research_discovery_events WHERE run_id=? AND event_type "
        "IN ('ideas_ingested','critiques_ingested','completed') ORDER BY rowid",
        (run_id,),
    ).fetchall()
    types = [str(row["event_type"]) for row in rows]
    if (
        len(types) < 3
        or types[-1] != "completed"
        or types[:-1]
        != [
            item
            for _ in range((len(types) - 1) // 2)
            for item in ("ideas_ingested", "critiques_ingested")
        ]
    ):
        raise DiscoveryError("registry_event_conflict", "review event sequence")

    idea_rows = connection.execute(
        "SELECT idea_id, idea_version, semantic_fingerprint, payload_json FROM "
        "research_discovery_ideas WHERE run_id=? ORDER BY idea_id, idea_version",
        (run_id,),
    ).fetchall()
    idea_by_fingerprint: dict[str, dict[str, object]] = {}
    for row in idea_rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiscoveryError("registry_idea_conflict", run_id) from exc
        if (
            not isinstance(payload, dict)
            or row["idea_id"] != payload.get("idea_id")
            or row["idea_version"] != payload.get("idea_version")
            or row["semantic_fingerprint"] != payload.get("semantic_fingerprint")
        ):
            raise DiscoveryError("registry_idea_conflict", run_id)
        idea_by_fingerprint[str(row["semantic_fingerprint"])] = payload
    if len(idea_by_fingerprint) != len(idea_rows):
        raise DiscoveryError("registry_idea_conflict", run_id)

    critique_rows = connection.execute(
        "SELECT critic_fingerprint, payload_json FROM research_discovery_critiques "
        "WHERE run_id=? ORDER BY critique_id",
        (run_id,),
    ).fetchall()
    critique_by_fingerprint: dict[str, dict[str, object]] = {}
    for row in critique_rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiscoveryError("registry_critique_conflict", run_id) from exc
        if (
            not isinstance(payload, dict)
            or row["critic_fingerprint"] != payload.get("critic_fingerprint")
        ):
            raise DiscoveryError("registry_critique_conflict", run_id)
        critique_by_fingerprint[str(row["critic_fingerprint"])] = payload
    if len(critique_by_fingerprint) != len(critique_rows):
        raise DiscoveryError("registry_critique_conflict", run_id)

    current: dict[str, dict[str, object]] = {}
    seen_ideas: set[str] = set()
    seen_critiques: set[str] = set()
    pair_count = (len(rows) - 1) // 2
    for pair_index in range(pair_count):
        idea_row = rows[pair_index * 2]
        idea_event = _decoded_exact_event(idea_row, run_id, "ideas_ingested")
        if set(idea_event) != {"idea_fingerprints", "idea_ids", "revision"}:
            raise DiscoveryError("registry_event_conflict", "ideas_ingested")
        ids = idea_event["idea_ids"]
        fingerprints = idea_event["idea_fingerprints"]
        if (
            not isinstance(ids, list)
            or not isinstance(fingerprints, list)
            or ids != sorted(ids)
            or len(ids) != len(fingerprints)
            or idea_event["revision"] is not (pair_index > 0)
        ):
            raise DiscoveryError("registry_event_conflict", "ideas_ingested")
        for idea_id, idea_fingerprint in zip(ids, fingerprints):
            payload = idea_by_fingerprint.get(str(idea_fingerprint))
            if (
                payload is None
                or payload.get("idea_id") != idea_id
                or (int(payload["idea_version"]) == 1) != (pair_index == 0)
                or str(idea_fingerprint) in seen_ideas
            ):
                raise DiscoveryError("registry_event_conflict", "ideas_ingested")
            current[str(idea_id)] = payload
            seen_ideas.add(str(idea_fingerprint))

        critique_row = rows[pair_index * 2 + 1]
        critique_event = _decoded_exact_event(
            critique_row, run_id, "critiques_ingested"
        )
        if set(critique_event) != {"critic_fingerprints", "idea_ids"}:
            raise DiscoveryError("registry_event_conflict", "critiques_ingested")
        critique_ids = critique_event["idea_ids"]
        critic_fingerprints = critique_event["critic_fingerprints"]
        if (
            not isinstance(critique_ids, list)
            or not isinstance(critic_fingerprints, list)
            or critique_ids != sorted(current)
            or len(critique_ids) != len(critic_fingerprints)
        ):
            raise DiscoveryError("registry_event_conflict", "critiques_ingested")
        for idea_id, critic_fingerprint in zip(
            critique_ids, critic_fingerprints
        ):
            payload = critique_by_fingerprint.get(str(critic_fingerprint))
            if (
                payload is None
                or payload.get("idea_id") != idea_id
                or payload.get("idea_semantic_fingerprint")
                != current[str(idea_id)]["semantic_fingerprint"]
                or str(critic_fingerprint) in seen_critiques
            ):
                raise DiscoveryError(
                    "registry_event_conflict", "critiques_ingested"
                )
            seen_critiques.add(str(critic_fingerprint))

    completed = _decoded_exact_event(rows[-1], run_id, "completed")
    expected_completed = {
        "recommendation": shortlist["recommendation"],
        "recommended_idea_id": shortlist["recommended_idea_id"],
        "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
        "status": "completed",
    }
    if completed != expected_completed:
        raise DiscoveryError("registry_event_conflict", "completed")
    if seen_ideas != set(idea_by_fingerprint) or seen_critiques != set(
        critique_by_fingerprint
    ):
        raise DiscoveryError("registry_event_conflict", "review event coverage")
    if current != latest:
        raise DiscoveryError("registry_event_conflict", "latest ideas")
    for idea_id, critique in critiques.items():
        if critique.get("critic_fingerprint") not in seen_critiques:
            raise DiscoveryError("registry_event_conflict", idea_id)
    return types


def _md(value: object) -> str:
    text = (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    return re.sub(r"([\\`*_{}\[\]()#+\-.!|])", r"\\\1", text)


def _md_code(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    return f"<code>{escape(text, quote=False)}</code>"


def _joined(values: list[object]) -> str:
    return "；".join(str(value) for value in values)


def render_human_review_zh(
    repo: Path, run_id: str, registry_path: Path
) -> tuple[str, str]:
    context = _canonical_run_context(repo, run_id, registry_path)
    connection = open_director_registry(registry_path)
    try:
        latest, _ = _load_latest_ideas(connection, context)
        critiques = _load_latest_critiques(connection, context, latest)
        shortlist = _load_shortlist(connection, context)
        _require_exact_completed_event(connection, run_id, shortlist)
        lifecycle = _latest_event(connection, run_id)
        if lifecycle is None or lifecycle[1] not in {
            "completed",
            "human_direction_decision",
            "handed_to_director",
            "director_handoff_result",
        }:
            raise DiscoveryError(
                "lifecycle_order_invalid", "human review requires completed event"
            )
    finally:
        connection.close()

    markdown_lines = [
        "# 研究发现人工评审简报",
        "",
        f"- Discovery run: {_md_code(run_id)}",
        f"- Shortlist fingerprint: {_md_code(shortlist['shortlist_fingerprint'])}",
        f"- 结论: {_md_code(shortlist['recommendation'])}",
        f"- 说明: {_md(shortlist['recommendation_reason_zh'])}",
        "",
    ]
    html_sections: list[str] = []
    for rank, ranked in enumerate(shortlist["ranked_ideas"], start=1):
        idea_id = str(ranked["idea_id"])
        idea = latest[idea_id]
        critique = critiques[idea_id]
        sources_md = "；".join(
            f"Class {_md(source['source_class'])} {_md_code(source.get('path') or source.get('canonical_url'))} — {_md(source['claim'])}"
            for source in idea["source_refs"]
        )
        uncertainty = list(idea["known_limitations"]) + list(
            critique["alternative_explanations"]
        )
        cost = idea["estimated_cost"]
        markdown_lines.extend(
            [
                f"## {rank}. {_md(idea['title'])}",
                "",
                f"- 研究问题: {_md(idea['falsifiable_hypothesis'])}",
                f"- 当前理由: {_md(idea['plain_language_summary_zh'])}",
                f"- 机制: {_md(idea['proposed_market_mechanism'])}",
                f"- 最强反证: {_md(critique['strongest_counterevidence'])}",
                f"- 数据准备度: {_md_code(idea['data_readiness'])}；{_md(_joined(idea['required_datasets']))}",
                f"- 最小测试: {_md(idea['minimal_test_method'])}",
                f"- 成本: experiments={_md(cost['experiments'])}, wall_clock_minutes={_md(cost['wall_clock_minutes'])}, compute_class={_md_code(cost['compute_class'])}",
                f"- 停止条件: {_md(_joined(idea['stop_conditions']))}",
                f"- Critic 结论: {_md_code(critique['verdict'])}",
                f"- 评分: {_md_code('{:.6f}'.format(float(ranked['final_score'])))}",
                f"- 不确定性: {_md(_joined(uncertainty))}",
                f"- 来源溯源: {sources_md}",
                "",
            ]
        )

        source_items = "".join(
            "<li><strong>Class {source_class}</strong> <code>{location}</code> — {claim}</li>".format(
                source_class=escape(str(source["source_class"]), quote=True),
                location=escape(
                    str(source.get("path") or source.get("canonical_url")),
                    quote=True,
                ),
                claim=escape(str(source["claim"]), quote=True),
            )
            for source in idea["source_refs"]
        )
        html_sections.append(
            """
            <section class="idea" aria-labelledby="idea-{rank}">
              <header><span class="rank">{rank:02d}</span><div><p class="family">{family}</p><h2 id="idea-{rank}">{title}</h2></div></header>
              <dl>
                <div><dt>研究问题</dt><dd>{question}</dd></div>
                <div><dt>当前理由</dt><dd>{why}</dd></div>
                <div><dt>机制</dt><dd>{mechanism}</dd></div>
                <div><dt>最强反证</dt><dd>{counter}</dd></div>
                <div><dt>数据准备度</dt><dd><code>{readiness}</code> · {datasets}</dd></div>
                <div><dt>最小测试</dt><dd>{test}</dd></div>
                <div><dt>停止条件</dt><dd>{stop}</dd></div>
                <div><dt>不确定性</dt><dd>{uncertainty}</dd></div>
              </dl>
              <table><caption>成本、Critic 结论与评分</caption><thead><tr><th>成本</th><th>Critic 结论</th><th>评分</th></tr></thead><tbody><tr><td>experiments={experiments}<br>wall_clock_minutes={minutes}<br><code>{compute}</code></td><td><code>{verdict}</code></td><td><strong>{score:.6f}</strong></td></tr></tbody></table>
              <div class="sources"><h3>来源溯源</h3><ul>{sources}</ul></div>
            </section>
            """.format(
                rank=rank,
                family=escape(str(idea["strategy_family"]), quote=True),
                title=escape(str(idea["title"]), quote=True),
                question=escape(str(idea["falsifiable_hypothesis"]), quote=True),
                why=escape(str(idea["plain_language_summary_zh"]), quote=True),
                mechanism=escape(str(idea["proposed_market_mechanism"]), quote=True),
                counter=escape(str(critique["strongest_counterevidence"]), quote=True),
                readiness=escape(str(idea["data_readiness"]), quote=True),
                datasets=escape(_joined(idea["required_datasets"]), quote=True),
                test=escape(str(idea["minimal_test_method"]), quote=True),
                stop=escape(_joined(idea["stop_conditions"]), quote=True),
                uncertainty=escape(_joined(uncertainty), quote=True),
                experiments=escape(str(cost["experiments"]), quote=True),
                minutes=escape(str(cost["wall_clock_minutes"]), quote=True),
                compute=escape(str(cost["compute_class"]), quote=True),
                verdict=escape(str(critique["verdict"]), quote=True),
                score=float(ranked["final_score"]),
                sources=source_items,
            )
        )

    markdown_lines.append(_DISCLAIMER)
    markdown = "\n".join(markdown_lines)
    html = """<!DOCTYPE html>
<html lang="zh-CN" data-markdown-source="{source}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:,">
  <title>研究发现人工评审简报</title>
  <style>
    :root {{ --paper:#f4f0e8; --sheet:#fffdf8; --ink:#29251f; --muted:#70685c; --line:#d7cdbd; --accent:#7a4f2f; --soft:#ece3d5; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font-family:"Microsoft YaHei","PingFang SC",sans-serif; font-size:16px; line-height:1.7; text-wrap:pretty; }}
    main {{ width:min(1040px,calc(100% - 32px)); margin:40px auto; background:var(--sheet); border:1px solid var(--line); padding:clamp(24px,5vw,64px); }}
    .eyebrow,.family {{ color:var(--accent); font-size:.75rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
    h1,h2,h3 {{ font-family:"Noto Serif CJK SC","Source Han Serif SC","Songti SC",SimSun,serif; line-height:1.25; margin-top:0; }}
    h1 {{ font-size:clamp(2rem,5vw,3.6rem); max-width:12ch; }}
    .summary {{ display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--line); margin:32px 0 48px; border:1px solid var(--line); }}
    .summary div {{ background:var(--sheet); padding:16px; }} .summary dt {{ color:var(--muted); font-size:.78rem; }} .summary dd {{ margin:4px 0 0; font-weight:700; overflow-wrap:anywhere; }}
    .idea {{ border-top:2px solid var(--ink); padding:32px 0 48px; break-inside:avoid; }}
    .idea header {{ display:grid; grid-template-columns:64px 1fr; gap:20px; align-items:start; }} .rank {{ font-family:"Cascadia Code",Consolas,monospace; color:var(--accent); font-size:1.4rem; }}
    dl {{ margin:24px 0; }} dl div {{ display:grid; grid-template-columns:130px 1fr; gap:20px; padding:11px 0; border-bottom:1px solid var(--line); }} dt {{ color:var(--muted); font-weight:700; }} dd {{ margin:0; min-width:0; }}
    table {{ width:100%; border-collapse:collapse; margin:28px 0; }} caption {{ text-align:left; font-weight:700; margin-bottom:8px; }} th,td {{ border:1px solid var(--line); padding:12px; text-align:left; vertical-align:top; }} th {{ background:var(--soft); }}
    code {{ font-family:"Cascadia Code",Consolas,monospace; font-size:.9em; overflow-wrap:anywhere; }} .sources ul {{ padding-left:20px; }} .provenance {{ color:var(--muted); }}
    .disclaimer {{ margin:24px 0 0; padding:20px; border:1px solid var(--accent); font-weight:700; }}
    .reason {{ margin:-24px 0 48px; padding:16px 18px; background:var(--soft); }}
    @media (max-width:720px) {{ main {{ width:100%; margin:0; border:0; }} .summary {{ grid-template-columns:1fr; }} dl div {{ grid-template-columns:1fr; gap:4px; }} .idea header {{ grid-template-columns:44px 1fr; }} table {{ display:block; overflow-x:auto; }} }}
    @media print {{ @page {{ margin:18mm; }} body {{ background:#fff; font-size:11pt; }} main {{ width:100%; margin:0; border:0; padding:0; }} .idea {{ break-inside:auto; }} table, .sources {{ break-inside:avoid; }} }}
  </style>
</head>
<body>
  <main>
    <header><p class="eyebrow">Research Discovery · Human Review</p><h1>研究发现人工评审简报</h1><p class="provenance">权威 Markdown 来源：<code>{source}</code>；本页与其由同一组已验证 artifact 字段生成。</p></header>
    <dl class="summary"><div><dt>Discovery run</dt><dd><code>{run_id}</code></dd></div><div><dt>结论</dt><dd><code>{recommendation}</code></dd></div><div><dt>Shortlist fingerprint</dt><dd><code>{shortlist_fp}</code></dd></div></dl>
    <p class="reason"><strong>说明：</strong>{recommendation_reason}</p>
    {sections}
    <p class="disclaimer">{disclaimer}</p>
  </main>
</body>
</html>
""".format(
        source=escape(_MARKDOWN_SOURCE, quote=True),
        run_id=escape(run_id, quote=True),
        recommendation=escape(str(shortlist["recommendation"]), quote=True),
        recommendation_reason=escape(
            str(shortlist["recommendation_reason_zh"]), quote=True
        ),
        shortlist_fp=escape(str(shortlist["shortlist_fingerprint"]), quote=True),
        sections="".join(html_sections),
        disclaimer=escape(_DISCLAIMER, quote=True),
    )
    return markdown, html


def _atomic_text_set(
    repo: Path,
    artifacts: dict[Path, bytes],
    *,
    conflict_code: str,
) -> None:
    """Publish an immutable same-content replay set and preserve other writers."""
    if not artifacts:
        raise DiscoveryError(conflict_code, "empty artifact set")
    repo = trigger_support._lexical_absolute(repo)
    destinations = sorted(artifacts, key=lambda path: path.as_posix())
    parents = {path.parent for path in destinations}
    if len(parents) != 1:
        raise DiscoveryError(conflict_code, "artifact parent mismatch")
    parent = next(iter(parents))
    if not parent.is_relative_to(repo):
        raise DiscoveryError(conflict_code, "artifact path outside repository")
    created_parents: list[Path] = []
    cursor = parent
    missing: list[Path] = []
    while cursor != repo and not os.path.lexists(cursor):
        missing.append(cursor)
        cursor = cursor.parent
    if cursor == repo and not repo.is_dir():
        raise DiscoveryError(conflict_code, "repository root missing")
    for path in reversed(missing):
        path.mkdir()
        created_parents.append(path)
    trigger_support._assert_no_reparse_components(
        repo, parent, "run_reparse_forbidden"
    )
    _require_plain_directory(parent, conflict_code)

    existing = {path: os.path.lexists(path) for path in destinations}
    if any(existing.values()):
        if not all(existing.values()):
            raise DiscoveryError(conflict_code, "partial immutable artifact set")
        for path in destinations:
            _require_regular_file(path, conflict_code)
            if path.read_bytes() != artifacts[path]:
                raise DiscoveryError(conflict_code, path.name)
        return

    staging = Path(tempfile.mkdtemp(prefix=".discovery-text-staging-", dir=parent))
    published: dict[Path, tuple[int, int]] = {}
    try:
        trigger_support._assert_no_reparse_components(
            parent, staging, "run_reparse_forbidden"
        )
        staged: dict[Path, Path] = {}
        for index, destination in enumerate(destinations):
            stage = staging / f"{index:02d}-{destination.name}"
            with stage.open("xb") as handle:
                handle.write(artifacts[destination])
                handle.flush()
                os.fsync(handle.fileno())
            if stage.read_bytes() != artifacts[destination]:
                raise DiscoveryError(conflict_code, f"staging {destination.name}")
            staged[destination] = stage
        for destination in destinations:
            stage = staged[destination]
            metadata = stage.stat(follow_symlinks=False)
            identity = (metadata.st_dev, metadata.st_ino)
            try:
                os.link(stage, destination)
            except FileExistsError as exc:
                raise DiscoveryError(conflict_code, destination.name) from exc
            except OSError as exc:
                raise DiscoveryError(
                    "artifact_publish_failed",
                    f"{destination.name}: {type(exc).__name__}",
                ) from exc
            current = destination.stat(follow_symlinks=False)
            if (current.st_dev, current.st_ino) != identity:
                raise DiscoveryError(conflict_code, destination.name)
            if destination.read_bytes() != artifacts[destination]:
                raise DiscoveryError(conflict_code, destination.name)
            published[destination] = identity
        shutil.rmtree(staging)
    except Exception as original:
        cleanup: list[str] = []
        for path, identity in reversed(list(published.items())):
            try:
                metadata = path.stat(follow_symlinks=False)
                if (metadata.st_dev, metadata.st_ino) == identity:
                    path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                cleanup.append(f"unlink {path.name}: {type(exc).__name__}")
        if os.path.lexists(staging):
            try:
                shutil.rmtree(staging)
            except OSError as exc:
                cleanup.append(f"rmtree {staging.name}: {type(exc).__name__}")
        for path in reversed(created_parents):
            try:
                path.rmdir()
            except (FileNotFoundError, OSError):
                pass
        if cleanup:
            raise DiscoveryError(
                "rollback_cleanup_failed",
                f"{type(original).__name__}; {'; '.join(cleanup)}",
            ) from original
        raise


def prepare_critic_run(
    repo: Path, run_id: str, registry_path: Path
) -> dict[str, object]:
    context = _canonical_run_context(repo, run_id, registry_path)
    connection = open_director_registry(registry_path)
    try:
        latest, _ = _load_latest_ideas(connection, context)
        lifecycle = _latest_event(connection, run_id)
        if not latest or lifecycle is None or lifecycle[1] != "ideas_ingested":
            raise DiscoveryError(
                "lifecycle_order_invalid", "Critic packet requires ideas_ingested"
            )
    finally:
        connection.close()
    packet = render_critic_packet(context["repo"], run_id)
    destination = context["run_root"] / "critic-task.md"
    inbox = trigger_support._lexical_absolute(context["critic_inbox"])
    actor_root = inbox.parent
    trigger_support._assert_no_reparse_components(
        trigger_support._lexical_absolute(tempfile.gettempdir()),
        actor_root,
        "temp_reparse_forbidden",
    )
    created = False
    if os.path.lexists(inbox):
        _require_plain_directory(inbox, "temp_inbox_invalid")
        if any(inbox.iterdir()):
            raise DiscoveryError("temp_inbox_not_empty", "critic")
    else:
        _require_plain_directory(actor_root, "temp_inbox_invalid")
        inbox.mkdir()
        created = True
    try:
        _atomic_text_set(
            context["repo"],
            {destination: packet.encode("utf-8")},
            conflict_code="critic_packet_conflict",
        )
    except Exception:
        if created:
            try:
                inbox.rmdir()
            except OSError:
                pass
        raise
    return {
        "run_id": run_id,
        "status": "awaiting_critic",
        "critic_inbox": str(inbox),
        "critic_task": destination.relative_to(context["repo"]).as_posix(),
        "idea_count": len(latest),
        "candidate_created": False,
        "campaign_started": False,
    }


def persist_human_review(
    repo: Path, run_id: str, registry_path: Path
) -> dict[str, str]:
    context = _canonical_run_context(repo, run_id, registry_path)
    markdown, html = render_human_review_zh(context["repo"], run_id, registry_path)
    outputs = {
        context["run_root"] / "human-review.zh-CN.md": markdown.encode("utf-8"),
        context["run_root"] / "human-review.zh-CN.html": html.encode("utf-8"),
    }
    _atomic_text_set(
        context["repo"], outputs, conflict_code="human_review_output_set_conflict"
    )
    return {
        "markdown": (context["run_root"] / "human-review.zh-CN.md")
        .relative_to(context["repo"])
        .as_posix(),
        "html": (context["run_root"] / "human-review.zh-CN.html")
        .relative_to(context["repo"])
        .as_posix(),
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _director_claims_forbidden(value: object, path: str = "") -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            nested_path = f"{path}.{key}" if path else str(key)
            if (
                any(token in lowered for token in ("candidate_created", "campaign_started", "campaign_executed"))
                and nested not in (False, 0, None, [], {})
            ):
                return True
            if lowered == "execution_authorized" and nested is not False:
                return True
            if _director_claims_forbidden(nested, nested_path):
                return True
    elif isinstance(value, list):
        return any(_director_claims_forbidden(item, path) for item in value)
    return False


def _validate_director_result(
    connection: sqlite3.Connection,
    context: dict[str, object],
    latest: dict[str, dict[str, object]],
    handoff: dict[str, object] | None,
    director_result: dict[str, object] | None,
) -> None:
    if director_result is None:
        return
    run_id = str(context["run_id"])
    if handoff is None:
        raise DiscoveryError("director_result_binding_conflict", "handoff missing")
    if not isinstance(director_result, dict) or set(director_result) != _DIRECTOR_RUN_FIELDS:
        raise DiscoveryError("director_result_binding_conflict", "result exact fields")
    budget = director_result.get("budget")
    proposals = director_result.get("proposals")
    rejections = director_result.get("rejected_proposals")
    if (
        director_result.get("schema_version") != "research-director-run-v1"
        or not isinstance(director_result.get("run_id"), str)
        or _DIRECTOR_RUN_ID.fullmatch(str(director_result["run_id"])) is None
        or director_result["run_id"]
        != f"director-discovery-{str(handoff['handoff_fingerprint'])[:16]}"
        or not isinstance(director_result.get("created_at"), str)
        or not director_result["created_at"]
        or director_result.get("state_fingerprint")
        != handoff["research_state_fingerprint"]
        or director_result.get("constitution_status") != "approved"
        or not isinstance(budget, dict)
        or set(budget) != _DIRECTOR_BUDGET_FIELDS
        or budget.get("max_campaigns") != 0
        or budget.get("max_validation_accesses") != 0
        or not isinstance(proposals, list)
        or not isinstance(rejections, list)
        or director_result.get("model_preference_used") is not False
        or director_result.get("execution_authorized") is not False
        or director_result.get("discovery_handoff_fingerprint")
        != handoff["handoff_fingerprint"]
        or _director_claims_forbidden(director_result)
    ):
        raise DiscoveryError("director_result_binding_conflict", "result structure")
    director_run_id = str(director_result["run_id"])

    selected_id = Path(str(handoff["idea_ref"])).stem.rsplit("-v", 1)[0]
    selected = latest.get(selected_id)
    if (
        selected is None
        or selected.get("semantic_fingerprint") != handoff["idea_fingerprint"]
        or director_result.get("objective") != handoff["research_question"]
        or director_result.get("risk_tolerance") != selected["risk_class"]
    ):
        raise DiscoveryError("director_result_binding_conflict", "selected idea")

    proposal: dict[str, object] | None = None
    rejection: dict[str, object] | None = None
    if proposals:
        if (
            len(proposals) != 1
            or rejections
            or not isinstance(proposals[0], dict)
            or director_result.get("recommendation") != "research_recommended"
            or director_result.get("recommendation_reason")
            != "one governed discovery handoff converted without execution authority"
            or director_result.get("ranking_factors")
            != ["human_selected_discovery_direction"]
        ):
            raise DiscoveryError("director_result_binding_conflict", "proposal branch")
        proposal = proposals[0]
        schema_path = trigger_support._repo_regular_file(
            context["repo"],
            Path("research/director/research-proposal.schema.json"),
            "director_result_binding_conflict",
            "director_result_binding_conflict",
        )
        try:
            jsonschema.Draft202012Validator(load_document(schema_path)).validate(
                proposal
            )
        except Exception as exc:
            raise DiscoveryError(
                "director_result_binding_conflict", "proposal schema"
            ) from exc
        if (
            proposal.get("research_question") != handoff["research_question"]
            or proposal.get("risk_class") != selected["risk_class"]
            or proposal.get("discovery_handoff_fingerprint")
            != handoff["handoff_fingerprint"]
            or proposal.get("discovery_approval_fingerprint")
            != handoff["approval_fingerprint"]
            or proposal.get("discovery_critique_fingerprint")
            != handoff["critique_fingerprint"]
            or proposal.get("execution_authorized") is not False
            or budget.get("max_experiments")
            != proposal.get("estimated_experiments")
            or budget.get("max_wall_clock_minutes")
            != proposal.get("estimated_wall_clock_minutes")
        ):
            raise DiscoveryError("director_result_binding_conflict", "proposal binding")
        status = "director_proposed"
        result_code = "proposal_created"
    else:
        if (
            len(rejections) != 1
            or not isinstance(rejections[0], dict)
            or set(rejections[0]) != {"proposal_key", "reason_code", "details"}
            or director_result.get("recommendation") != "no_research_recommended"
            or director_result.get("recommendation_reason")
            != rejections[0].get("reason_code")
            or director_result.get("ranking_factors")
            != ["governed_discovery_handoff_gates"]
            or budget.get("max_experiments") != 0
            or budget.get("max_wall_clock_minutes") != 0
        ):
            raise DiscoveryError("director_result_binding_conflict", "rejection branch")
        rejection = rejections[0]
        expected_details = {
            "discovery_run_id": run_id,
            "handoff_fingerprint": handoff["handoff_fingerprint"],
        }
        if (
            rejection.get("proposal_key") != selected_id
            or not isinstance(rejection.get("reason_code"), str)
            or not rejection["reason_code"]
            or rejection.get("details") != expected_details
        ):
            raise DiscoveryError("director_result_binding_conflict", "rejection binding")
        status = "director_rejected"
        result_code = str(rejection["reason_code"])

    run_rows = connection.execute(
        "SELECT run_id, state_fingerprint, objective, risk_tolerance, budget_json, "
        "recommendation, payload_json, created_at FROM director_runs WHERE run_id=?",
        (director_run_id,),
    ).fetchall()
    if len(run_rows) != 1:
        raise DiscoveryError("director_result_binding_conflict", "Director Registry row")
    expected_run = {
        "run_id": director_run_id,
        "state_fingerprint": director_result["state_fingerprint"],
        "objective": director_result["objective"],
        "risk_tolerance": director_result["risk_tolerance"],
        "budget_json": json.dumps(budget, sort_keys=True),
        "recommendation": director_result["recommendation"],
        "payload_json": json.dumps(director_result, sort_keys=True),
        "created_at": director_result["created_at"],
    }
    if any(run_rows[0][key] != value for key, value in expected_run.items()):
        raise DiscoveryError("director_result_binding_conflict", "Director payload")

    proposal_rows = connection.execute(
        "SELECT proposal_id, run_id, semantic_fingerprint, risk_class, "
        "information_gain, status, payload_json, created_at FROM director_proposals "
        "WHERE run_id=?",
        (director_run_id,),
    ).fetchall()
    rejection_rows = connection.execute(
        "SELECT run_id, proposal_key, reason_code, details_json, created_at FROM "
        "director_rejections WHERE run_id=?",
        (director_run_id,),
    ).fetchall()
    if proposal is not None:
        expected_proposal = {
            "proposal_id": proposal["proposal_id"],
            "run_id": director_run_id,
            "semantic_fingerprint": proposal["semantic_fingerprint"],
            "risk_class": proposal["risk_class"],
            "information_gain": proposal["expected_information_gain"]["score"],
            "status": "proposed_unapproved",
            "payload_json": json.dumps(proposal, sort_keys=True),
            "created_at": director_result["created_at"],
        }
        if (
            len(proposal_rows) != 1
            or rejection_rows
            or any(
                proposal_rows[0][key] != value
                for key, value in expected_proposal.items()
            )
        ):
            raise DiscoveryError("director_result_binding_conflict", "proposal Registry row")
    else:
        assert rejection is not None
        expected_rejection = {
            "run_id": director_run_id,
            "proposal_key": rejection["proposal_key"],
            "reason_code": rejection["reason_code"],
            "details_json": json.dumps(rejection["details"], sort_keys=True),
            "created_at": director_result["created_at"],
        }
        if (
            proposal_rows
            or len(rejection_rows) != 1
            or any(
                rejection_rows[0][key] != value
                for key, value in expected_rejection.items()
            )
        ):
            raise DiscoveryError("director_result_binding_conflict", "rejection Registry row")

    handoff_rows = connection.execute(
        "SELECT handoff_fingerprint, run_id, idea_id, status, director_result_code, "
        "payload_json, created_at FROM "
        "research_discovery_handoffs WHERE run_id=?",
        (run_id,),
    ).fetchall()
    expected_handoff = {
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "run_id": run_id,
        "idea_id": selected_id,
        "status": status,
        "director_result_code": result_code,
        "payload_json": json.dumps(handoff, ensure_ascii=False, sort_keys=True),
        "created_at": director_result["created_at"],
    }
    if (
        len(handoff_rows) != 1
        or any(
            handoff_rows[0][key] != value for key, value in expected_handoff.items()
        )
    ):
        raise DiscoveryError("director_result_binding_conflict", "handoff Registry row")

    import research_discovery_route as route_support

    route_support._require_exact_event(
        connection,
        run_id,
        "handed_to_director",
        route_support._handoff_event(handoff),
    )
    event_payload: dict[str, object] = {
        "director_run_id": director_run_id,
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "result_code": result_code,
        "status": status,
    }
    if proposal is not None:
        event_payload["proposal_fingerprint"] = proposal["semantic_fingerprint"]
    event_id = route_support._event_id(
        run_id, "director_handoff_result", event_payload
    )
    events = connection.execute(
        "SELECT event_id, run_id, event_type, reason_code, payload_json, created_at "
        "FROM research_discovery_events "
        "WHERE run_id=? AND event_type='director_handoff_result'",
        (run_id,),
    ).fetchall()
    if len(events) != 1:
        raise DiscoveryError("director_result_binding_conflict", "Director event")
    expected_event = {
        "event_id": event_id,
        "run_id": run_id,
        "event_type": "director_handoff_result",
        "reason_code": None if proposal is not None else result_code,
        "payload_json": json.dumps(
            event_payload, ensure_ascii=False, sort_keys=True
        ),
        "created_at": director_result["created_at"],
    }
    if any(events[0][key] != value for key, value in expected_event.items()):
        raise DiscoveryError("director_result_binding_conflict", "Director event")


def _artifact_hashes(
    context: dict[str, object],
    human_markdown: str,
    human_html: str,
) -> dict[str, str]:
    repo: Path = context["repo"]
    run_root: Path = context["run_root"]
    human_expected = {
        run_root / "human-review.zh-CN.md": human_markdown.encode("utf-8"),
        run_root / "human-review.zh-CN.html": human_html.encode("utf-8"),
    }
    for path, expected in human_expected.items():
        _require_regular_file(path, "human_review_artifact_conflict")
        if path.read_bytes() != expected:
            raise DiscoveryError("human_review_artifact_conflict", path.name)
    paths: set[Path] = set()
    for path in run_root.rglob("*"):
        if path.is_file():
            _require_regular_file(path, "run_artifact_conflict")
            paths.add(path)
    fixed = (
        "research/director/current-research-state.json",
        "research/governance/research-constitution.yaml",
        "research/discovery/policy/source-policy.yaml",
        "research/discovery/policy/ranking-policy.yaml",
        "research/discovery/prompts/researcher.md",
        "research/discovery/prompts/critic.md",
        "research/discovery/schemas/research-trigger.schema.json",
        "research/discovery/schemas/research-idea.schema.json",
        "research/discovery/schemas/research-critique.schema.json",
        "research/discovery/schemas/research-shortlist.schema.json",
        "research/discovery/schemas/research-direction-approval.schema.json",
        "research/discovery/schemas/research-direction-handoff.schema.json",
    )
    for relative in fixed:
        path = repo / relative
        _require_regular_file(path, "audit_input_missing")
        paths.add(path)
    for relative in context["allowed_sources"]:
        path = repo / str(relative)
        _require_regular_file(path, "audit_input_missing")
        paths.add(path)
    return {
        path.relative_to(repo).as_posix(): sha256_file(path)
        for path in sorted(paths, key=lambda item: item.relative_to(repo).as_posix())
    }


def _registry_integrity(
    connection: sqlite3.Connection,
    run_id: str,
    trigger: dict[str, object],
    shortlist: dict[str, object],
    approval: dict[str, object] | None,
    handoff: dict[str, object] | None,
) -> dict[str, object]:
    tables = (
        "research_discovery_runs",
        "research_discovery_ideas",
        "research_discovery_critiques",
        "research_discovery_shortlists",
        "research_discovery_approvals",
        "research_discovery_handoffs",
        "research_discovery_events",
    )
    counts = {
        table: int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE run_id=?', (run_id,)
            ).fetchone()[0]
        )
        for table in tables
    }
    event_counts = {
        str(row["event_type"]): int(row["event_count"])
        for row in connection.execute(
            "SELECT event_type, COUNT(*) AS event_count FROM "
            "research_discovery_events WHERE run_id=? GROUP BY event_type "
            "ORDER BY event_type",
            (run_id,),
        )
    }
    return {
        "row_counts": counts,
        "event_counts": event_counts,
        "trigger_fingerprint": trigger["trigger_fingerprint"],
        "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
        "approval_fingerprint": approval["approval_fingerprint"] if approval else None,
        "handoff_fingerprint": handoff["handoff_fingerprint"] if handoff else None,
    }


def _require_exact_event_sequence(
    connection: sqlite3.Connection,
    run_id: str,
    review_event_types: list[str],
    approval: dict[str, object] | None,
    handoff: dict[str, object] | None,
    director_result: dict[str, object] | None,
) -> None:
    expected = list(review_event_types)
    if approval is not None:
        expected.append("human_direction_decision")
    if handoff is not None:
        expected.append("handed_to_director")
    if director_result is not None:
        expected.append("director_handoff_result")
    actual = [
        str(row["event_type"])
        for row in connection.execute(
            "SELECT event_type FROM research_discovery_events WHERE run_id=? "
            "ORDER BY rowid",
            (run_id,),
        )
    ]
    if actual != expected:
        raise DiscoveryError(
            "registry_event_conflict",
            json.dumps({"expected": expected, "actual": actual}, sort_keys=True),
        )


def _render_final_audit_zh(
    audit: dict[str, object], run_id: str
) -> tuple[str, str]:
    source = f"{run_id}-final-report.md"
    markdown = [
        "# 研究发现最终审计报告",
        "",
        f"- 权威 Markdown：{_md_code(source)}",
        f"- Critic 异议参考：{_md_code(f'research/discovery/runs/{run_id}/human-review.zh-CN.md')}",
        "",
        "## 机器审计字段",
        "",
    ]
    for key in _FINAL_AUDIT_FIELDS:
        markdown.append(f"- {_md_code(key)}: {_md_code(_canonical_json(audit[key]))}")
    markdown.extend(["", _DISCLAIMER])
    long_values = {"director_result", "artifact_hashes", "registry_integrity"}
    rows = "".join(
        "<tr{row_class}><th><code>{key}</code></th><td><code>{value}</code></td></tr>".format(
            row_class=' class="long-value"' if key in long_values else "",
            key=escape(key, quote=True),
            value=escape(_canonical_json(audit[key]), quote=True),
        )
        for key in _FINAL_AUDIT_FIELDS
    )
    html = f'''<!DOCTYPE html>
<html lang="zh-CN" data-markdown-source="{escape(source, quote=True)}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="icon" href="data:,">
  <title>研究发现最终审计报告</title>
  <style>
    :root {{ --paper:#f4f0e8; --sheet:#fffdf8; --ink:#29251f; --muted:#70685c; --line:#d7cdbd; --accent:#7a4f2f; --soft:#ece3d5; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:var(--paper); font-family:"Microsoft YaHei","PingFang SC",sans-serif; font-size:16px; line-height:1.7; text-wrap:pretty; }}
    main {{ width:min(1120px,calc(100% - 32px)); margin:40px auto; padding:clamp(24px,5vw,64px); background:var(--sheet); border:1px solid var(--line); }}
    .eyebrow {{ color:var(--accent); font-size:.75rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; }}
    h1,h2 {{ font-family:"Noto Serif CJK SC","Source Han Serif SC","Songti SC",SimSun,serif; line-height:1.25; }}
    h1 {{ max-width:12ch; font-size:clamp(2rem,5vw,3.6rem); }}
    .provenance {{ color:var(--muted); }} .table-wrap {{ overflow-x:auto; margin:32px 0; }}
    table {{ width:100%; border-collapse:collapse; }} th,td {{ border:1px solid var(--line); padding:12px; text-align:left; vertical-align:top; }} th {{ width:240px; background:var(--soft); }}
    code {{ font-family:"Cascadia Code",Consolas,monospace; font-size:.88em; overflow-wrap:anywhere; white-space:normal; }}
    .disclaimer {{ margin-top:28px; padding:20px; border:1px solid var(--accent); font-weight:700; }}
    @media (max-width:720px) {{ main {{ width:100%; margin:0; border:0; }} th {{ width:180px; }} .table-wrap {{ max-width:100%; }} }}
    @media print {{ @page {{ size:A4; margin:16mm; }} body {{ background:#fff; font-size:11pt; }} main {{ width:100%; margin:0; border:0; padding:0; }} tr {{ break-inside:avoid; }} .long-value {{ break-inside:auto; }} .table-wrap {{ overflow:visible; }} }}
  </style>
</head>
<body><main><header><p class="eyebrow">Research Discovery · Final Audit</p><h1>研究发现最终审计报告</h1><p class="provenance">权威 Markdown 来源：<code>{escape(source, quote=True)}</code>；Critic 异议见 <code>research/discovery/runs/{escape(run_id, quote=True)}/human-review.zh-CN.md</code>。</p></header><section><h2>机器审计字段</h2><div class="table-wrap"><table><tbody>{rows}</tbody></table></div></section><p class="disclaimer">{escape(_DISCLAIMER, quote=True)}</p></main></body>
</html>
'''
    return "\n".join(markdown), html


def build_final_audit(
    repo: Path,
    run_id: str,
    registry_path: Path,
    director_result: dict[str, object] | None = None,
) -> tuple[dict[str, object], str, str]:
    context = _canonical_run_context(repo, run_id, registry_path)
    _require_exact_critic_packet(context)
    connection = open_director_registry(registry_path)
    try:
        latest, _ = _load_latest_ideas(connection, context)
        critiques = _load_latest_critiques(connection, context, latest)
        shortlist = _load_shortlist(connection, context)
        review_event_types = _require_exact_review_event_chain(
            connection, context, latest, critiques, shortlist
        )
        lifecycle = _latest_event(connection, run_id)
        if lifecycle is None or lifecycle[1] not in {
            "completed",
            "human_direction_decision",
            "handed_to_director",
            "director_handoff_result",
        }:
            raise DiscoveryError("lifecycle_order_invalid", "final audit stage")
        import research_discovery_route as route_support

        approval = route_support._load_existing_approval(connection, context)
        if director_result is None:
            handoff = route_support._load_existing_handoff(connection, context)
        else:
            handoff_path = context["run_root"] / "handoff.json"
            handoff = _load_json_mapping(
                handoff_path, "handoff_artifact_conflict"
            )
            validate_artifact(
                context["repo"], "research-direction-handoff.schema.json", handoff
            )
            if (
                handoff.get("discovery_run_id") != run_id
                or handoff.get("handoff_fingerprint")
                != artifact_fingerprint(handoff, "handoff_fingerprint")
                or handoff.get("execution_authorized") is not False
            ):
                raise DiscoveryError(
                    "handoff_artifact_conflict", "terminal handoff binding"
                )
        if approval is None and handoff is not None:
            raise DiscoveryError("handoff_stage_conflict", "handoff without approval")
        if approval is not None and approval["decision"] != "approved_for_director_handoff" and handoff is not None:
            raise DiscoveryError("handoff_stage_conflict", "handoff for terminal rejection")
        _validate_director_result(
            connection, context, latest, handoff, director_result
        )
        _require_exact_event_sequence(
            connection,
            run_id,
            review_event_types,
            approval,
            handoff,
            director_result,
        )
        human_markdown, human_html = render_human_review_zh(
            context["repo"], run_id, registry_path
        )
        artifact_hashes = _artifact_hashes(context, human_markdown, human_html)
        registry_integrity = _registry_integrity(
            connection,
            run_id,
            context["trigger"],
            shortlist,
            approval,
            handoff,
        )
    finally:
        connection.close()
    audit = {
        "schema_version": "research-discovery-final-audit-v1",
        "run_id": run_id,
        "trigger_fingerprint": context["trigger"]["trigger_fingerprint"],
        "idea_count": len(latest),
        "critique_count": len(critiques),
        "shortlist_count": len(shortlist["ranked_ideas"]),
        "recommendation": shortlist["recommendation"],
        "human_decision": approval["decision"] if approval else "pending_human_review",
        "handoff_created": handoff is not None,
        "director_result": director_result,
        "candidate_created": False,
        "campaign_started": False,
        "strategy_modified": False,
        "risk_modified": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "artifact_hashes": artifact_hashes,
        "registry_integrity": registry_integrity,
    }
    if tuple(audit) != _FINAL_AUDIT_FIELDS:
        raise DiscoveryError("audit_structure_invalid", "field order")
    markdown, html = _render_final_audit_zh(audit, run_id)
    return audit, markdown, html


def publish_final_audit(
    repo: Path,
    run_id: str,
    registry_path: Path,
    director_result: dict[str, object] | None = None,
) -> dict[str, str]:
    repo = trigger_support._lexical_absolute(repo)
    if _RUN_ID.fullmatch(run_id) is None:
        raise DiscoveryError("run_path_invalid", run_id)
    root = repo / "reports/audits/research-discovery"
    paths = {
        "json": root / f"{run_id}-final-report.json",
        "markdown": root / f"{run_id}-final-report.md",
        "html": root / f"{run_id}-final-report.zh-CN.html",
    }
    existence = [os.path.lexists(path) for path in paths.values()]
    if any(existence) and not all(existence):
        raise DiscoveryError("audit_output_set_conflict", "partial audit output set")
    audit, markdown, html = build_final_audit(
        repo, run_id, registry_path, director_result
    )
    artifacts = {
        paths["json"]: (
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        paths["markdown"]: markdown.encode("utf-8"),
        paths["html"]: html.encode("utf-8"),
    }
    _atomic_text_set(repo, artifacts, conflict_code="audit_output_set_conflict")
    return {key: str(path) for key, path in paths.items()}


def _capture_inbox(paths: list[Path]) -> dict[Path, tuple[int, int, str]]:
    return {
        path: (
            path.stat(follow_symlinks=False).st_dev,
            path.stat(follow_symlinks=False).st_ino,
            sha256_file(path),
        )
        for path in paths
    }


def _cleanup_inbox(inbox: Path, snapshot: dict[Path, tuple[int, int, str]]) -> None:
    current = sorted(inbox.iterdir(), key=lambda path: path.name)
    if set(current) != set(snapshot):
        raise DiscoveryError("temp_inbox_cleanup_blocked", "unowned content present")
    for path in current:
        _require_regular_file(path, "temp_inbox_cleanup_blocked")
        metadata = path.stat(follow_symlinks=False)
        identity = (metadata.st_dev, metadata.st_ino, sha256_file(path))
        if identity != snapshot[path]:
            raise DiscoveryError("temp_inbox_cleanup_blocked", path.name)
    for path in current:
        path.unlink()
    try:
        inbox.rmdir()
    except OSError as exc:
        raise DiscoveryError(
            "temp_inbox_cleanup_blocked", f"{inbox.name}: {type(exc).__name__}"
        ) from exc


class _DiscoveryArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise DiscoveryError("cli_argument_error", "invalid CLI arguments")


def _print_cli_error(reason_code: str) -> int:
    payload = {
        "status": "error",
        "reason_code": reason_code,
        "detail": "request rejected",
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
    return 2


def _add_common_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--director-registry", required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))


def main(argv: list[str] | None = None) -> int:
    try:
        parser = _DiscoveryArgumentParser(description=__doc__)
        commands = parser.add_subparsers(dest="command", required=True)
        ingest_idea_parser = commands.add_parser("ingest-ideas")
        _add_common_cli(ingest_idea_parser)
        ingest_idea_parser.add_argument("--inbox", required=True)
        critic_parser = commands.add_parser("prepare-critic")
        _add_common_cli(critic_parser)
        ingest_critic_parser = commands.add_parser("ingest-critiques")
        _add_common_cli(ingest_critic_parser)
        ingest_critic_parser.add_argument("--inbox", required=True)
        shortlist_parser = commands.add_parser("build-shortlist")
        _add_common_cli(shortlist_parser)
        audit_parser = commands.add_parser("audit")
        _add_common_cli(audit_parser)
        audit_parser.add_argument("--director-result")
        args = parser.parse_args(argv)
        repo = trigger_support._lexical_absolute(args.repo_root)
        registry = Path(args.director_registry)
        if not registry.is_absolute():
            registry = repo / registry
        if args.command == "ingest-ideas":
            context = _canonical_run_context(repo, args.run_id, registry)
            inbox = Path(args.inbox)
            paths = _validated_inbox(context, inbox, "researcher")
            inbox = trigger_support._lexical_absolute(inbox)
            snapshot = _capture_inbox(paths)
            ideas = ingest_ideas(repo, args.run_id, inbox, registry)
            _cleanup_inbox(inbox, snapshot)
            result = {
                "run_id": args.run_id,
                "status": "awaiting_critic",
                "idea_count": len(ideas),
                "candidate_created": False,
                "campaign_started": False,
            }
        elif args.command == "prepare-critic":
            result = prepare_critic_run(repo, args.run_id, registry)
        elif args.command == "ingest-critiques":
            context = _canonical_run_context(repo, args.run_id, registry)
            critic_packet = context["run_root"] / "critic-task.md"
            _require_regular_file(critic_packet, "critic_packet_missing")
            if critic_packet.read_text(encoding="utf-8") != render_critic_packet(
                repo, args.run_id
            ):
                raise DiscoveryError("critic_packet_conflict", args.run_id)
            inbox = Path(args.inbox)
            paths = _validated_inbox(context, inbox, "critic")
            inbox = trigger_support._lexical_absolute(inbox)
            snapshot = _capture_inbox(paths)
            critiques = ingest_critiques(repo, args.run_id, inbox, registry)
            _cleanup_inbox(inbox, snapshot)
            result = {
                "run_id": args.run_id,
                "status": "ready_for_shortlist",
                "critique_count": len(critiques),
                "candidate_created": False,
                "campaign_started": False,
            }
        elif args.command == "build-shortlist":
            context = _canonical_run_context(repo, args.run_id, registry)
            critic_packet = context["run_root"] / "critic-task.md"
            _require_regular_file(critic_packet, "critic_packet_missing")
            if critic_packet.read_text(encoding="utf-8") != render_critic_packet(
                repo, args.run_id
            ):
                raise DiscoveryError("critic_packet_conflict", args.run_id)
            shortlist = build_shortlist(repo, args.run_id, registry)
            outputs = persist_human_review(repo, args.run_id, registry)
            result = {
                "run_id": args.run_id,
                "status": "awaiting_human_review",
                "shortlist_count": len(shortlist["ranked_ideas"]),
                "recommendation": shortlist["recommendation"],
                "human_review": outputs,
                "candidate_created": False,
                "campaign_started": False,
            }
        else:
            director_result = None
            if args.director_result:
                path = _validated_director_result_path(repo, args.director_result)
                director_result = _load_json_mapping(path, "director_result_invalid")
            outputs = publish_final_audit(
                repo, args.run_id, registry, director_result
            )
            result = {
                "run_id": args.run_id,
                "status": "audit_published",
                "outputs": outputs,
                "candidate_created": False,
                "campaign_started": False,
            }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0
    except DiscoveryError as exc:
        return _print_cli_error(exc.reason_code)
    except Exception:
        return _print_cli_error("internal_error")


if __name__ == "__main__":
    raise SystemExit(main())
