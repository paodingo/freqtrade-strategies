#!/usr/bin/env python3
"""Ingest immutable discovery reviews and render deterministic human packets."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from html import escape
from pathlib import Path

import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile

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
    allowed_entries = {
        "trigger.json",
        "researcher-task.md",
        "ideas",
        "critiques",
        "shortlist.json",
    }
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
    actual = trigger_support._lexical_absolute(inbox)
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


def _publish_batch(
    context: dict[str, object],
    connection: sqlite3.Connection,
    artifacts: list[tuple[Path, dict[str, object]]],
    record: Callable[[sqlite3.Connection, Path, dict[str, object]], bool],
    event_type: str,
    event_payload: dict[str, object],
    integrity_check: Callable[[], None] | None = None,
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
    destination_exists: dict[Path, bool] = {}
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
            destination_exists[destination] = exists
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
        for destination, payload in artifacts:
            row_exists = record(connection, destination, payload)
            if row_exists != destination_exists[destination]:
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
            elif lifecycle is None or lifecycle[1] != "ideas_ingested":
                raise DiscoveryError(
                    "lifecycle_order_invalid",
                    "idea replay requires latest ideas_ingested event",
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

        event_payload = {
            "idea_fingerprints": [
                item["semantic_fingerprint"]
                for item in sorted(payloads, key=lambda value: str(value["idea_id"]))
            ],
            "idea_ids": sorted(str(item["idea_id"]) for item in payloads),
            "revision": revision_mode,
        }
        _publish_batch(
            context,
            connection,
            artifacts,
            record,
            "ideas_ingested",
            event_payload,
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
        _publish_batch(
            context,
            connection,
            artifacts,
            record,
            "critiques_ingested",
            event_payload,
            idea_integrity,
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
        _publish_batch(
            context,
            connection,
            [(destination, shortlist)],
            record,
            "completed",
            completed,
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


def _md(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


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
        lifecycle = _latest_event(connection, run_id)
        if lifecycle is None or lifecycle[1] != "completed":
            raise DiscoveryError(
                "lifecycle_order_invalid", "human review requires completed event"
            )
    finally:
        connection.close()

    markdown_lines = [
        "# 研究发现人工评审简报",
        "",
        f"- Discovery run: `{_md(run_id)}`",
        f"- Shortlist fingerprint: `{_md(shortlist['shortlist_fingerprint'])}`",
        f"- 结论: `{_md(shortlist['recommendation'])}`",
        f"- 说明: {_md(shortlist['recommendation_reason_zh'])}",
        "",
    ]
    html_sections: list[str] = []
    for rank, ranked in enumerate(shortlist["ranked_ideas"], start=1):
        idea_id = str(ranked["idea_id"])
        idea = latest[idea_id]
        critique = critiques[idea_id]
        sources_md = "；".join(
            f"Class {_md(source['source_class'])} `{_md(source.get('path') or source.get('canonical_url'))}` — {_md(source['claim'])}"
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
                f"- 数据准备度: `{_md(idea['data_readiness'])}`；{_md(_joined(idea['required_datasets']))}",
                f"- 最小测试: {_md(idea['minimal_test_method'])}",
                f"- 成本: experiments={_md(cost['experiments'])}, wall_clock_minutes={_md(cost['wall_clock_minutes'])}, compute_class=`{_md(cost['compute_class'])}`",
                f"- 停止条件: {_md(_joined(idea['stop_conditions']))}",
                f"- Critic 结论: `{_md(critique['verdict'])}`",
                f"- 评分: `{float(ranked['final_score']):.6f}`",
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
    @media print {{ @page {{ margin:18mm; }} body {{ background:#fff; font-size:11pt; }} main {{ width:100%; margin:0; border:0; padding:0; }} .idea {{ break-inside:avoid; }} table, .sources {{ break-inside:avoid; }} }}
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
