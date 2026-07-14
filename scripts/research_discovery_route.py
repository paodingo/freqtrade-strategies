#!/usr/bin/env python3
"""Bind one human research-direction decision and create a non-executing handoff."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import tempfile
from pathlib import Path

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    utc_now,
)
from research_discovery_common import (
    DiscoveryError,
    artifact_fingerprint,
    validate_artifact,
)
import research_discovery_review as review_support
import research_discovery_trigger as trigger_support


_RUN_ID = re.compile(r"^discovery-run-[a-f0-9]{16}$")
_REQUEST_FIELDS = {
    "decision",
    "selected_rank",
    "reviewer_type",
    "decision_reason_zh",
}
_DECISIONS = {"approved_for_director_handoff", "rejected", "deferred"}


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


def _load_json(path: Path, reason_code: str) -> dict[str, object]:
    _require_regular_file(path, reason_code)
    try:
        return load_document(path)
    except Exception as exc:
        raise DiscoveryError(reason_code, f"{path.name}: {type(exc).__name__}") from exc


def _canonical_context(
    repo: Path, run_id: str, registry_path: Path
) -> dict[str, object]:
    repo = trigger_support._lexical_absolute(repo)
    if _RUN_ID.fullmatch(run_id) is None:
        raise DiscoveryError("run_path_invalid", run_id)
    run_path = Path("research/discovery/runs") / run_id
    researcher_inbox = (
        trigger_support._lexical_absolute(tempfile.gettempdir())
        / "freqtrade-research-discovery"
        / trigger_support._repo_identity_namespace(repo)
        / run_id
        / "researcher"
    )
    run_root, researcher_inbox = trigger_support._validate_run_paths(
        repo, run_path, researcher_inbox
    )
    _require_plain_directory(run_root, "run_artifact_missing")
    allowed = {
        "trigger.json",
        "researcher-task.md",
        "ideas",
        "critiques",
        "shortlist.json",
        "approval.json",
        "handoff.json",
    }
    unexpected = sorted(path.name for path in run_root.iterdir() if path.name not in allowed)
    if unexpected:
        raise DiscoveryError("run_artifact_conflict", json.dumps(unexpected))

    trigger_path = run_root / "trigger.json"
    packet_path = run_root / "researcher-task.md"
    trigger = _load_json(trigger_path, "run_artifact_missing")
    _require_regular_file(packet_path, "run_artifact_missing")
    validate_artifact(repo, "research-trigger.schema.json", trigger)
    state, allowed_sources = trigger_support._bound_context(repo, trigger)
    expected = trigger_support._expected_result(trigger, repo)
    if expected["run_id"] != run_id or expected["run_path"] != run_path.as_posix():
        raise DiscoveryError("run_artifact_conflict", run_id)

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
            row_payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DiscoveryError("registry_run_conflict", run_id) from exc
        if (
            row["run_id"] != run_id
            or row["trigger_fingerprint"] != trigger["trigger_fingerprint"]
            or row["status"] != "awaiting_researcher"
            or row["state_fingerprint"] != trigger["research_state_fingerprint"]
            or row["created_at"] != trigger["created_at"]
            or row_payload != expected
        ):
            raise DiscoveryError("registry_run_conflict", run_id)
    finally:
        connection.close()
    return {
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


def _current_bindings(
    context: dict[str, object],
    state: dict[str, object],
    constitution: dict[str, object],
) -> tuple[str, str]:
    try:
        state_fingerprint = trigger_support._validate_state(state)
    except DiscoveryError as exc:
        raise DiscoveryError("research_state_conflict", exc.reason_code) from exc
    if (
        state_fingerprint != context["trigger"]["research_state_fingerprint"]
        or state != context["state"]
    ):
        raise DiscoveryError("research_state_conflict", "current state changed")
    try:
        constitution_fingerprint = trigger_support._validate_constitution(constitution)
    except DiscoveryError as exc:
        raise DiscoveryError("constitution_fingerprint_conflict", exc.reason_code) from exc
    if constitution_fingerprint != context["trigger"]["constitution_fingerprint"]:
        raise DiscoveryError(
            "constitution_fingerprint_conflict", "current Constitution changed"
        )
    return state_fingerprint, constitution_fingerprint


def _event_payload_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _event_id(run_id: str, event_type: str, payload: dict[str, object]) -> str:
    return (
        "discovery-event-"
        + fingerprint({"run_id": run_id, "event_type": event_type, "payload": payload})[:24]
    )


def _require_exact_event(
    connection: sqlite3.Connection,
    run_id: str,
    event_type: str,
    payload: dict[str, object],
) -> None:
    expected_id = _event_id(run_id, event_type, payload)
    rows = connection.execute(
        "SELECT event_id, run_id, event_type, reason_code, payload_json, created_at "
        "FROM research_discovery_events WHERE run_id=? AND event_type=?",
        (run_id, event_type),
    ).fetchall()
    if len(rows) != 1:
        raise DiscoveryError("registry_event_conflict", event_type)
    row = rows[0]
    if (
        row["event_id"] != expected_id
        or row["run_id"] != run_id
        or row["event_type"] != event_type
        or row["reason_code"] is not None
        or row["payload_json"] != _event_payload_json(payload)
        or not isinstance(row["created_at"], str)
        or not row["created_at"]
    ):
        raise DiscoveryError("registry_event_conflict", event_type)


def _shortlist_event(shortlist: dict[str, object]) -> dict[str, object]:
    return {
        "recommendation": shortlist["recommendation"],
        "recommended_idea_id": shortlist["recommended_idea_id"],
        "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
        "status": "completed",
    }


def _approval_event(approval: dict[str, object]) -> dict[str, object]:
    return {
        "approval_fingerprint": approval["approval_fingerprint"],
        "decision": approval["decision"],
        "selected_idea_id": approval["selected_idea_id"],
        "status": (
            "human_approved"
            if approval["decision"] == "approved_for_director_handoff"
            else approval["decision"]
        ),
    }


def _handoff_event(handoff: dict[str, object]) -> dict[str, object]:
    return {
        "approval_fingerprint": handoff["approval_fingerprint"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "idea_id": Path(str(handoff["idea_ref"])).stem.rsplit("-v", 1)[0],
        "status": "handed_to_director",
    }


def _load_review_bindings(
    connection: sqlite3.Connection, context: dict[str, object]
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
    dict[str, object],
]:
    latest, _ = review_support._load_latest_ideas(connection, context)
    critiques = review_support._load_latest_critiques(connection, context, latest)
    shortlist = review_support._load_shortlist(connection, context)
    if shortlist["discovery_run_id"] != context["run_id"]:
        raise DiscoveryError("shortlist_artifact_conflict", "discovery run")
    if shortlist["research_state_fingerprint"] != context["trigger"]["research_state_fingerprint"]:
        raise DiscoveryError("shortlist_artifact_conflict", "research state")
    _require_exact_event(connection, str(context["run_id"]), "completed", _shortlist_event(shortlist))
    return latest, critiques, shortlist


def _integrity_checker(
    connection: sqlite3.Connection,
    context: dict[str, object],
    expected_latest: dict[str, dict[str, object]],
    expected_critiques: dict[str, dict[str, object]],
    expected_shortlist: dict[str, object],
    expected_approval: dict[str, object] | None = None,
    allowed_downstream_handoff: dict[str, object] | None = None,
    check_downstream_handoff: bool = False,
):
    def check() -> None:
        try:
            current_state, allowed_sources = trigger_support._bound_context(
                context["repo"], context["trigger"]
            )
        except DiscoveryError as exc:
            if exc.reason_code in {
                "stale_trigger",
                "state_conflict",
                "state_fingerprint_conflict",
                "state_schema_invalid",
                "state_snapshot_conflict",
                "state_structure_invalid",
            }:
                raise DiscoveryError("research_state_conflict", exc.reason_code) from exc
            if exc.reason_code in {
                "constitution_conflict",
                "constitution_invalid",
                "constitution_not_approved",
            }:
                raise DiscoveryError(
                    "constitution_fingerprint_conflict", exc.reason_code
                ) from exc
            raise
        if current_state != context["state"] or set(allowed_sources) != context["allowed_sources"]:
            raise DiscoveryError("research_state_conflict", "bound context changed")
        current_latest, current_critiques, current_shortlist = _load_review_bindings(
            connection, context
        )
        if current_latest != expected_latest:
            raise DiscoveryError("idea_artifact_conflict", str(context["run_id"]))
        if current_critiques != expected_critiques:
            raise DiscoveryError("critique_artifact_conflict", str(context["run_id"]))
        if current_shortlist != expected_shortlist:
            raise DiscoveryError("shortlist_artifact_conflict", str(context["run_id"]))
        if expected_approval is not None:
            current_approval = _load_existing_approval(connection, context)
            if current_approval != expected_approval:
                raise DiscoveryError("approval_binding_conflict", str(context["run_id"]))
        if check_downstream_handoff:
            try:
                current_handoff = _load_existing_handoff(connection, context)
            except DiscoveryError as exc:
                raise DiscoveryError("handoff_stage_conflict", exc.reason_code) from exc
            if current_handoff is not None and current_handoff != allowed_downstream_handoff:
                raise DiscoveryError(
                    "handoff_stage_conflict", "handoff does not bind to this approval"
                )

    return check


def _validate_request(request: dict[str, object]) -> tuple[str, int | None, str]:
    if not isinstance(request, dict):
        raise DiscoveryError("decision_request_fields_invalid", "exact request fields required")
    missing = _REQUEST_FIELDS - set(request)
    extra = set(request) - _REQUEST_FIELDS
    if missing == {"selected_rank"} and not extra:
        raise DiscoveryError("selected_rank_invalid", "selected_rank is required")
    if missing or extra:
        raise DiscoveryError("decision_request_fields_invalid", "exact request fields required")
    if request.get("reviewer_type") != "human_user":
        raise DiscoveryError("reviewer_not_human", "human_user is required")
    decision = request.get("decision")
    if not isinstance(decision, str) or decision not in _DECISIONS:
        raise DiscoveryError("decision_invalid", str(decision))
    reason = request.get("decision_reason_zh")
    if (
        not isinstance(reason, str)
        or not reason.strip()
        or re.search(r"[\u3400-\u9fff]", reason) is None
    ):
        raise DiscoveryError("decision_reason_invalid", "Chinese reason is required")
    rank = request.get("selected_rank")
    if decision == "approved_for_director_handoff":
        if type(rank) is not int or rank < 1 or rank > 3:
            raise DiscoveryError("selected_rank_invalid", str(rank))
        return decision, rank, reason
    if rank is not None:
        raise DiscoveryError("selected_rank_invalid", "selection must be null")
    return decision, None, reason


def _resolve_selection(
    shortlist: dict[str, object],
    latest: dict[str, dict[str, object]],
    critiques: dict[str, dict[str, object]],
    rank: int | None,
) -> tuple[dict[str, object] | None, dict[str, object] | None, dict[str, object] | None]:
    if rank is None:
        return None, None, None
    ranked = shortlist["ranked_ideas"]
    if rank > len(ranked):
        raise DiscoveryError("selected_rank_invalid", str(rank))
    selected = ranked[rank - 1]
    idea_id = str(selected["idea_id"])
    idea = latest.get(idea_id)
    critique = critiques.get(idea_id)
    if idea is None or selected["idea_fingerprint"] != idea["semantic_fingerprint"]:
        raise DiscoveryError("idea_artifact_conflict", idea_id)
    if critique is None or selected["critique_fingerprint"] != critique["critic_fingerprint"]:
        raise DiscoveryError("critique_artifact_conflict", idea_id)
    return selected, idea, critique


def _load_existing_approval(
    connection: sqlite3.Connection,
    context: dict[str, object],
) -> dict[str, object] | None:
    rows = connection.execute(
        "SELECT approval_fingerprint, run_id, decision, selected_idea_id, "
        "payload_json, decided_at FROM research_discovery_approvals WHERE run_id=?",
        (context["run_id"],),
    ).fetchall()
    path = context["run_root"] / "approval.json"
    file_exists = os.path.lexists(path)
    event_count = connection.execute(
        "SELECT COUNT(*) FROM research_discovery_events "
        "WHERE run_id=? AND event_type='human_direction_decision'",
        (context["run_id"],),
    ).fetchone()[0]
    if not rows and not file_exists:
        if event_count:
            raise DiscoveryError("registry_artifact_conflict", "approval event-only")
        return None
    if len(rows) != 1 or not file_exists:
        raise DiscoveryError("registry_artifact_conflict", "approval.json")
    row = rows[0]
    payload = _load_json(path, "approval_artifact_conflict")
    validate_artifact(context["repo"], "research-direction-approval.schema.json", payload)
    if payload["discovery_run_id"] != context["run_id"]:
        raise DiscoveryError("approval_binding_conflict", "discovery run")
    if payload["approval_fingerprint"] != artifact_fingerprint(payload, "approval_fingerprint"):
        raise DiscoveryError("approval_artifact_conflict", "approval fingerprint")
    payload_json = _event_payload_json(payload)
    if (
        row["approval_fingerprint"] != payload["approval_fingerprint"]
        or row["run_id"] != context["run_id"]
        or row["decision"] != payload["decision"]
        or row["selected_idea_id"] != payload["selected_idea_id"]
        or row["payload_json"] != payload_json
        or row["decided_at"] != payload["decided_at"]
    ):
        raise DiscoveryError("registry_approval_conflict", str(context["run_id"]))
    _require_exact_event(
        connection, str(context["run_id"]), "human_direction_decision", _approval_event(payload)
    )
    return payload


def _load_existing_handoff(
    connection: sqlite3.Connection,
    context: dict[str, object],
) -> dict[str, object] | None:
    rows = connection.execute(
        "SELECT handoff_fingerprint, run_id, idea_id, status, director_result_code, "
        "payload_json, created_at FROM research_discovery_handoffs WHERE run_id=?",
        (context["run_id"],),
    ).fetchall()
    path = context["run_root"] / "handoff.json"
    file_exists = os.path.lexists(path)
    event_count = connection.execute(
        "SELECT COUNT(*) FROM research_discovery_events "
        "WHERE run_id=? AND event_type='handed_to_director'",
        (context["run_id"],),
    ).fetchone()[0]
    if not rows and not file_exists:
        if event_count:
            raise DiscoveryError("registry_artifact_conflict", "handoff event-only")
        return None
    if len(rows) != 1 or not file_exists:
        raise DiscoveryError("registry_artifact_conflict", "handoff.json")
    row = rows[0]
    payload = _load_json(path, "handoff_artifact_conflict")
    validate_artifact(context["repo"], "research-direction-handoff.schema.json", payload)
    if payload["discovery_run_id"] != context["run_id"]:
        raise DiscoveryError("handoff_binding_conflict", "discovery run")
    if payload["handoff_fingerprint"] != artifact_fingerprint(payload, "handoff_fingerprint"):
        raise DiscoveryError("handoff_artifact_conflict", "handoff fingerprint")
    idea_id = Path(str(payload["idea_ref"])).stem.rsplit("-v", 1)[0]
    if (
        row["handoff_fingerprint"] != payload["handoff_fingerprint"]
        or row["run_id"] != context["run_id"]
        or row["idea_id"] != idea_id
        or row["status"] != "handed_to_director"
        or row["director_result_code"] is not None
        or row["payload_json"] != _event_payload_json(payload)
        or not isinstance(row["created_at"], str)
        or not row["created_at"]
    ):
        raise DiscoveryError("registry_handoff_conflict", str(context["run_id"]))
    _require_exact_event(
        connection, str(context["run_id"]), "handed_to_director", _handoff_event(payload)
    )
    return payload


def _approval_matches(
    approval: dict[str, object],
    decision: str,
    reason: str,
    selected: dict[str, object] | None,
    state_fingerprint: str,
    constitution_fingerprint: str,
    shortlist: dict[str, object],
    decided_at: str | None,
) -> bool:
    return (
        approval["decision"] == decision
        and approval["selected_idea_id"] == (selected["idea_id"] if selected else None)
        and approval["selected_idea_fingerprint"] == (selected["idea_fingerprint"] if selected else None)
        and approval["selected_critique_fingerprint"] == (selected["critique_fingerprint"] if selected else None)
        and approval["shortlist_fingerprint"] == shortlist["shortlist_fingerprint"]
        and approval["research_state_fingerprint"] == state_fingerprint
        and approval["constitution_fingerprint"] == constitution_fingerprint
        and approval["reviewer_type"] == "human_user"
        and approval["decision_reason_zh"] == reason
        and (decided_at is None or approval["decided_at"] == decided_at)
    )


def _build_handoff(
    context: dict[str, object],
    run_id: str,
    state_fingerprint: str,
    constitution_fingerprint: str,
    shortlist: dict[str, object],
    latest: dict[str, dict[str, object]],
    critiques: dict[str, dict[str, object]],
    approval: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    if approval["decision"] != "approved_for_director_handoff":
        raise DiscoveryError("direction_not_approved", run_id)
    matches = [
        item
        for item in shortlist["ranked_ideas"]
        if item["idea_id"] == approval["selected_idea_id"]
        and item["idea_fingerprint"] == approval["selected_idea_fingerprint"]
        and item["critique_fingerprint"] == approval["selected_critique_fingerprint"]
    ]
    if len(matches) != 1:
        raise DiscoveryError("approval_binding_conflict", run_id)
    selected, idea, critique = _resolve_selection(
        shortlist, latest, critiques, shortlist["ranked_ideas"].index(matches[0]) + 1
    )
    if selected is None or idea is None or critique is None:
        raise DiscoveryError("approval_binding_conflict", run_id)
    idea_path = (
        context["run_root"]
        / "ideas"
        / f"{idea['idea_id']}-v{idea['idea_version']}.json"
    )
    critique_path = context["run_root"] / "critiques" / f"{critique['critique_id']}.json"
    approval_path = context["run_root"] / "approval.json"
    handoff: dict[str, object] = {
        "schema_version": "research-direction-handoff-v1",
        "discovery_run_id": run_id,
        "idea_ref": idea_path.relative_to(context["repo"]).as_posix(),
        "critique_ref": critique_path.relative_to(context["repo"]).as_posix(),
        "approval_ref": approval_path.relative_to(context["repo"]).as_posix(),
        "idea_fingerprint": idea["semantic_fingerprint"],
        "critique_fingerprint": critique["critic_fingerprint"],
        "approval_fingerprint": approval["approval_fingerprint"],
        "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
        "research_state_fingerprint": state_fingerprint,
        "constitution_fingerprint": constitution_fingerprint,
        "research_question": idea["falsifiable_hypothesis"],
        "execution_authorized": False,
    }
    handoff["handoff_fingerprint"] = artifact_fingerprint(handoff, "handoff_fingerprint")
    validate_artifact(context["repo"], "research-direction-handoff.schema.json", handoff)
    return handoff, idea


def record_direction_decision(
    repo: Path,
    run_id: str,
    request: dict[str, object],
    state: dict[str, object],
    constitution: dict[str, object],
    registry_path: Path,
    *,
    decided_at: str | None = None,
) -> dict[str, object]:
    decision, rank, reason = _validate_request(request)
    context = _canonical_context(repo, run_id, registry_path)
    state_fingerprint, constitution_fingerprint = _current_bindings(context, state, constitution)
    connection = open_director_registry(registry_path)
    try:
        latest, critiques, shortlist = _load_review_bindings(connection, context)
        selected, _, _ = _resolve_selection(shortlist, latest, critiques, rank)
        existing = _load_existing_approval(connection, context)
        try:
            downstream_handoff = _load_existing_handoff(connection, context)
        except DiscoveryError as exc:
            raise DiscoveryError("handoff_stage_conflict", exc.reason_code) from exc
        if existing is not None:
            if _approval_matches(
                existing,
                decision,
                reason,
                selected,
                state_fingerprint,
                constitution_fingerprint,
                shortlist,
                decided_at,
            ):
                allowed_handoff = None
                if existing["decision"] == "approved_for_director_handoff":
                    allowed_handoff, _ = _build_handoff(
                        context,
                        run_id,
                        state_fingerprint,
                        constitution_fingerprint,
                        shortlist,
                        latest,
                        critiques,
                        existing,
                    )
                if downstream_handoff is not None and downstream_handoff != allowed_handoff:
                    raise DiscoveryError(
                        "handoff_stage_conflict",
                        "handoff does not bind to this decision",
                    )
                return existing
            raise DiscoveryError("direction_decision_conflict", run_id)
        if downstream_handoff is not None:
            raise DiscoveryError(
                "handoff_stage_conflict", "handoff precedes direction approval"
            )

        approval: dict[str, object] = {
            "schema_version": "research-direction-approval-v1",
            "discovery_run_id": run_id,
            "decision": decision,
            "selected_idea_id": selected["idea_id"] if selected else None,
            "selected_idea_fingerprint": selected["idea_fingerprint"] if selected else None,
            "selected_critique_fingerprint": selected["critique_fingerprint"] if selected else None,
            "shortlist_fingerprint": shortlist["shortlist_fingerprint"],
            "research_state_fingerprint": state_fingerprint,
            "constitution_fingerprint": constitution_fingerprint,
            "reviewer_type": "human_user",
            "decision_reason_zh": reason,
            "decided_at": decided_at or utc_now(),
        }
        approval["approval_fingerprint"] = artifact_fingerprint(
            approval, "approval_fingerprint"
        )
        validate_artifact(context["repo"], "research-direction-approval.schema.json", approval)
        allowed_handoff = None
        if decision == "approved_for_director_handoff":
            allowed_handoff, _ = _build_handoff(
                context,
                run_id,
                state_fingerprint,
                constitution_fingerprint,
                shortlist,
                latest,
                critiques,
                approval,
            )
        destination = context["run_root"] / "approval.json"

        def record(db, _destination, payload, allow_insert):
            rows = db.execute(
                "SELECT approval_fingerprint, run_id, decision, selected_idea_id, "
                "payload_json, decided_at FROM research_discovery_approvals "
                "WHERE run_id=? OR approval_fingerprint=?",
                (run_id, payload["approval_fingerprint"]),
            ).fetchall()
            if len(rows) > 1:
                raise DiscoveryError("registry_approval_conflict", run_id)
            payload_json = _event_payload_json(payload)
            if rows:
                row = rows[0]
                if (
                    row["approval_fingerprint"] != payload["approval_fingerprint"]
                    or row["run_id"] != run_id
                    or row["decision"] != payload["decision"]
                    or row["selected_idea_id"] != payload["selected_idea_id"]
                    or row["payload_json"] != payload_json
                    or row["decided_at"] != payload["decided_at"]
                ):
                    raise DiscoveryError("registry_approval_conflict", run_id)
                return True
            if not allow_insert:
                return False
            db.execute(
                "INSERT INTO research_discovery_approvals(approval_fingerprint, run_id, "
                "decision, selected_idea_id, payload_json, decided_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    payload["approval_fingerprint"],
                    run_id,
                    payload["decision"],
                    payload["selected_idea_id"],
                    payload_json,
                    payload["decided_at"],
                ),
            )
            return False

        lifecycle = review_support._latest_event(connection, run_id)
        event_payload = _approval_event(approval)
        integrity_check = _integrity_checker(
            connection,
            context,
            latest,
            critiques,
            shortlist,
            allowed_downstream_handoff=allowed_handoff,
            check_downstream_handoff=True,
        )

        def guard(db):
            current = review_support._latest_event(db, run_id)
            if current is not None and current[1] == "human_direction_decision" and current[2] == event_payload:
                return True
            if current != lifecycle or current is None or current[1] != "completed":
                raise DiscoveryError("lifecycle_order_invalid", "approval requires completed")
            return False

        review_support._publish_batch(
            context,
            connection,
            [(destination, approval)],
            record,
            "human_direction_decision",
            event_payload,
            integrity_check=integrity_check,
            transaction_guard=guard,
        )
        return approval
    finally:
        connection.close()


def create_handoff(
    repo: Path,
    run_id: str,
    state: dict[str, object],
    constitution: dict[str, object],
    registry_path: Path,
) -> dict[str, object]:
    context = _canonical_context(repo, run_id, registry_path)
    state_fingerprint, constitution_fingerprint = _current_bindings(context, state, constitution)
    connection = open_director_registry(registry_path)
    try:
        latest, critiques, shortlist = _load_review_bindings(connection, context)
        approval = _load_existing_approval(connection, context)
        if approval is None or approval["decision"] != "approved_for_director_handoff":
            raise DiscoveryError("direction_not_approved", run_id)
        if (
            approval["research_state_fingerprint"] != state_fingerprint
            or approval["constitution_fingerprint"] != constitution_fingerprint
            or approval["shortlist_fingerprint"] != shortlist["shortlist_fingerprint"]
            or approval["reviewer_type"] != "human_user"
        ):
            raise DiscoveryError("approval_binding_conflict", run_id)
        handoff, idea = _build_handoff(
            context,
            run_id,
            state_fingerprint,
            constitution_fingerprint,
            shortlist,
            latest,
            critiques,
            approval,
        )
        existing = _load_existing_handoff(connection, context)
        if existing is not None:
            if existing == handoff:
                return existing
            raise DiscoveryError("direction_handoff_conflict", run_id)
        destination = context["run_root"] / "handoff.json"
        idea_id = str(idea["idea_id"])

        def record(db, _destination, payload, allow_insert):
            rows = db.execute(
                "SELECT handoff_fingerprint, run_id, idea_id, status, "
                "director_result_code, payload_json, created_at FROM "
                "research_discovery_handoffs WHERE run_id=? OR handoff_fingerprint=?",
                (run_id, payload["handoff_fingerprint"]),
            ).fetchall()
            if len(rows) > 1:
                raise DiscoveryError("registry_handoff_conflict", run_id)
            payload_json = _event_payload_json(payload)
            if rows:
                row = rows[0]
                if (
                    row["handoff_fingerprint"] != payload["handoff_fingerprint"]
                    or row["run_id"] != run_id
                    or row["idea_id"] != idea_id
                    or row["status"] != "handed_to_director"
                    or row["director_result_code"] is not None
                    or row["payload_json"] != payload_json
                ):
                    raise DiscoveryError("registry_handoff_conflict", run_id)
                return True
            if not allow_insert:
                return False
            db.execute(
                "INSERT INTO research_discovery_handoffs(handoff_fingerprint, run_id, "
                "idea_id, status, director_result_code, payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    payload["handoff_fingerprint"],
                    run_id,
                    idea_id,
                    "handed_to_director",
                    None,
                    payload_json,
                    utc_now(),
                ),
            )
            return False

        lifecycle = review_support._latest_event(connection, run_id)
        event_payload = _handoff_event(handoff)
        integrity_check = _integrity_checker(
            connection,
            context,
            latest,
            critiques,
            shortlist,
            expected_approval=approval,
        )

        def guard(db):
            current = review_support._latest_event(db, run_id)
            if current is not None and current[1] == "handed_to_director" and current[2] == event_payload:
                return True
            if (
                current != lifecycle
                or current is None
                or current[1] != "human_direction_decision"
                or current[2] != _approval_event(approval)
            ):
                raise DiscoveryError("lifecycle_order_invalid", "handoff requires human approval")
            return False

        review_support._publish_batch(
            context,
            connection,
            [(destination, handoff)],
            record,
            "handed_to_director",
            event_payload,
            integrity_check=integrity_check,
            transaction_guard=guard,
        )
        return handoff
    finally:
        connection.close()
