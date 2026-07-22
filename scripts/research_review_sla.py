#!/usr/bin/env python3
"""Issue at-most-once, batched human-review reminders under a sealed SLA policy."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from research_director_common import (
    canonical_json,
    fingerprint,
    load_document,
    open_director_registry,
)


DEFAULT_POLICY = Path("research/director/knowledge-review-sla-policy-v1.json")


def _instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("knowledge review SLA timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("knowledge review SLA timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _semantic_fingerprint(payload: dict[str, Any], field: str) -> str:
    return fingerprint({key: value for key, value in payload.items() if key != field})


def load_policy(repo_root: str | Path, relative: str | Path = DEFAULT_POLICY) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    path = Path(relative)
    if path.is_absolute():
        raise ValueError("knowledge review SLA policy path must be repo-relative")
    resolved = (repo / path).resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise ValueError("knowledge review SLA policy escapes repository") from exc
    policy = load_document(resolved)
    expected_levels = [
        {
            "level": "reminder_72h",
            "after_hours": 72,
            "required_action": "review_existing_batch_recommendations",
        },
        {
            "level": "escalation_168h",
            "after_hours": 168,
            "required_action": "resolve_or_explicitly_defer_existing_batch",
        },
    ]
    if (
        policy.get("schema_version") != "knowledge-review-sla-policy-v1"
        or policy.get("policy_id") != "development-knowledge-review-sla-v1"
        or policy.get("status") != "active"
        or policy.get("time_anchor") != "validated_advisory_generated_at"
        or policy.get("timezone") != "Asia/Shanghai"
        or policy.get("notification_window")
        != {"start_hour_inclusive": 9, "end_hour_exclusive": 20}
        or policy.get("followup_levels") != expected_levels
        or policy.get("maximum_followup_notifications_per_batch") != 2
        or policy.get("catch_up_behavior") != "highest_due_level_only"
        or policy.get("deduplication_key") != "batch_id_plus_notification_level"
        or policy.get("initial_notification_delivery")
        != "external_advisory_creation_flow"
        or policy.get("resolved_batch_behavior") != "silent_stop"
        or policy.get("automatic_decision_authorized") is not False
        or policy.get("automatic_application_authorized") is not False
        or policy.get("automatic_lesson_promotion_authorized") is not False
        or policy.get("execution_authorized") is not False
        or policy.get("policy_fingerprint")
        != _semantic_fingerprint(policy, "policy_fingerprint")
    ):
        raise ValueError("knowledge review SLA policy is invalid")
    return policy


def _next_window(now: datetime, timezone_name: str, start_hour: int) -> str:
    zone = ZoneInfo(timezone_name)
    local = now.astimezone(zone)
    candidate = local.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc).isoformat()


def _existing_levels(
    connection: Any,
    batch_id: str,
    advisory_fingerprint: str,
) -> set[str]:
    levels: set[str] = set()
    for row in connection.execute(
        "SELECT * FROM research_review_sla_events WHERE batch_id=? "
        "ORDER BY created_at,event_id",
        (batch_id,),
    ):
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError as exc:
            raise ValueError("knowledge review SLA event payload is invalid") from exc
        if (
            payload.get("batch_id") != batch_id
            or payload.get("notification_level") != row["notification_level"]
            or payload.get("advisory_fingerprint") != advisory_fingerprint
            or row["advisory_fingerprint"] != advisory_fingerprint
            or fingerprint(payload) != row["event_fingerprint"]
        ):
            raise ValueError("knowledge review SLA event binding is invalid")
        levels.add(str(row["notification_level"]))
    return levels


def evaluate(
    repo_root: str | Path,
    registry_path: str | Path,
    *,
    batch_id: str,
    advisory: dict[str, Any],
    checked_at: str,
    policy_path: str | Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    policy = load_policy(repo_root, policy_path)
    if (
        not isinstance(batch_id, str)
        or not batch_id.startswith("knowledge-review-batch-")
        or advisory.get("human_decision_required") is not True
        or advisory.get("automatic_application_authorized") is not False
        or advisory.get("execution_authorized") is not False
        or not isinstance(advisory.get("advisory_fingerprint"), str)
        or not isinstance(advisory.get("generated_at"), str)
    ):
        raise ValueError("knowledge review SLA advisory binding is invalid")
    anchor = _instant(advisory["generated_at"])
    now = _instant(checked_at)
    if now < anchor:
        raise ValueError("knowledge review SLA check precedes advisory generation")
    levels = policy["followup_levels"]
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        recorded = _existing_levels(
            connection, batch_id, advisory["advisory_fingerprint"]
        )
        level_index = {item["level"]: index for index, item in enumerate(levels)}
        unknown = recorded - set(level_index)
        if unknown or len(recorded) > policy["maximum_followup_notifications_per_batch"]:
            raise ValueError("knowledge review SLA event levels are invalid")
        highest_recorded = max((level_index[level] for level in recorded), default=-1)
        due = [
            item
            for index, item in enumerate(levels)
            if index > highest_recorded
            and now >= anchor + timedelta(hours=item["after_hours"])
        ]
        if due:
            selected = due[-1]
            window = policy["notification_window"]
            local_hour = now.astimezone(ZoneInfo(policy["timezone"])).hour
            if not (
                window["start_hour_inclusive"]
                <= local_hour
                < window["end_hour_exclusive"]
            ):
                connection.rollback()
                return {
                    "schema_version": "knowledge-review-sla-result-v1",
                    "status": "awaiting_notification_window",
                    "batch_id": batch_id,
                    "notification_required": False,
                    "notification_level": selected["level"],
                    "next_notification_at": _next_window(
                        now, policy["timezone"], window["start_hour_inclusive"]
                    ),
                    "recorded_levels": sorted(recorded, key=level_index.get),
                    "automatic_decision_authorized": False,
                    "automatic_application_authorized": False,
                    "automatic_lesson_promotion_authorized": False,
                    "execution_authorized": False,
                }
            payload = {
                "schema_version": "knowledge-review-sla-notification-event-v1",
                "batch_id": batch_id,
                "notification_level": selected["level"],
                "advisory_fingerprint": advisory["advisory_fingerprint"],
                "advisory_generated_at": advisory["generated_at"],
                "due_after_hours": selected["after_hours"],
                "required_action": selected["required_action"],
                "notification_due_claimed": True,
                "created_at": checked_at,
                "automatic_decision_authorized": False,
                "automatic_application_authorized": False,
                "automatic_lesson_promotion_authorized": False,
                "execution_authorized": False,
            }
            event_fingerprint = fingerprint(payload)
            connection.execute(
                "INSERT INTO research_review_sla_events("
                "event_id,batch_id,notification_level,advisory_fingerprint,"
                "event_fingerprint,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    f"review-sla-event-{event_fingerprint[:24]}",
                    batch_id,
                    selected["level"],
                    advisory["advisory_fingerprint"],
                    event_fingerprint,
                    canonical_json(payload),
                    checked_at,
                ),
            )
            connection.commit()
            return {
                "schema_version": "knowledge-review-sla-result-v1",
                "status": (
                    "review_escalation_due"
                    if selected["level"].startswith("escalation_")
                    else "review_reminder_due"
                ),
                "batch_id": batch_id,
                "notification_required": True,
                "notification_level": selected["level"],
                "required_action": selected["required_action"],
                "recorded_levels": sorted(
                    {*recorded, selected["level"]}, key=level_index.get
                ),
                "automatic_decision_authorized": False,
                "automatic_application_authorized": False,
                "automatic_lesson_promotion_authorized": False,
                "execution_authorized": False,
            }

        next_levels = [
            item
            for index, item in enumerate(levels)
            if index > highest_recorded
        ]
        connection.rollback()
        return {
            "schema_version": "knowledge-review-sla-result-v1",
            "status": "awaiting_human_review",
            "batch_id": batch_id,
            "notification_required": False,
            "next_notification_at": (
                (anchor + timedelta(hours=next_levels[0]["after_hours"])).isoformat()
                if next_levels
                else None
            ),
            "recorded_levels": sorted(recorded, key=level_index.get),
            "automatic_decision_authorized": False,
            "automatic_application_authorized": False,
            "automatic_lesson_promotion_authorized": False,
            "execution_authorized": False,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
