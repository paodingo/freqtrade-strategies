#!/usr/bin/env python3
"""Aggregate pending knowledge reviews into threshold-triggered immutable handoffs."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

import jsonschema

import export_director_registry
import open_source_knowledge as knowledge
import research_knowledge_review
from research_director_common import fingerprint, load_document, utc_now, write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = Path("research/director/knowledge-review-batch-policy-v1.json")
HANDOFF_SCHEMA = Path("research/knowledge/schemas/knowledge-review-batch-handoff.schema.json")
EXPECTED_REVIEW_TYPES = ["source_update", "lesson_feedback", "license_review"]


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("pending review timestamp is missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("pending review timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _validate_policy(policy: dict[str, Any]) -> None:
    required = {
        "schema_version", "policy_id", "status", "count_threshold", "max_wait_hours",
        "included_review_types", "output_root", "idle_behavior", "triggered_behavior",
        "advisory_drafting_authorized", "automatic_decision_authorized",
        "automatic_application_authorized", "automatic_lesson_promotion_authorized",
        "execution_authorized", "policy_fingerprint",
    }
    if set(policy) != required:
        raise ValueError("knowledge review batch policy fields are invalid")
    if policy["schema_version"] != "knowledge-review-batch-policy-v1" or policy["status"] != "active":
        raise ValueError("knowledge review batch policy is not active v1")
    if policy["included_review_types"] != EXPECTED_REVIEW_TYPES:
        raise ValueError("knowledge review batch policy types are not the closed allowlist")
    if not isinstance(policy["count_threshold"], int) or policy["count_threshold"] < 1:
        raise ValueError("knowledge review count threshold is invalid")
    if not isinstance(policy["max_wait_hours"], int) or policy["max_wait_hours"] < 1:
        raise ValueError("knowledge review max wait threshold is invalid")
    if policy["output_root"] != "reports/audits/open-source-learning-v1/review-batches/aggregated":
        raise ValueError("knowledge review output root is invalid")
    if policy["idle_behavior"] != "silent_no_write" or policy["triggered_behavior"] != "immutable_human_review_handoff":
        raise ValueError("knowledge review batch behavior is invalid")
    if policy["advisory_drafting_authorized"] is not True:
        raise ValueError("review-only advisory drafting must remain available")
    for field in (
        "automatic_decision_authorized", "automatic_application_authorized",
        "automatic_lesson_promotion_authorized", "execution_authorized",
    ):
        if policy[field] is not False:
            raise ValueError(f"{field} must remain false")
    if knowledge.semantic_fingerprint(policy, "policy_fingerprint") != policy["policy_fingerprint"]:
        raise ValueError("knowledge review batch policy fingerprint mismatch")


def _pending_timestamps(registry_export: dict[str, Any]) -> dict[tuple[str, str], datetime]:
    tables = registry_export.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("registry export tables are missing")
    timestamps: dict[tuple[str, str], datetime] = {}
    for row in tables.get("research_knowledge_update_proposals", []):
        if row["status"] == "pending_human_approval":
            timestamps[("source_update", str(row["proposal_id"]))] = _parse_timestamp(row["created_at"])
    for row in tables.get("research_lesson_feedback_drafts", []):
        if row["review_status"] == "pending_human_review":
            timestamps[("lesson_feedback", str(row["feedback_id"]))] = _parse_timestamp(row["created_at"])
    for row in tables.get("research_knowledge_lifecycle", []):
        if row["item_type"] == "source" and row["lifecycle_status"] == "review_required":
            timestamps[("license_review", str(row["item_key"]))] = _parse_timestamp(row["updated_at"])
    return timestamps


def build_batch(
    repo: Path,
    registry_export: dict[str, Any],
    policy: dict[str, Any],
    now: str,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    """Return an idle result or a complete immutable batch without writing files."""
    _validate_policy(policy)
    current_time = _parse_timestamp(now)
    timestamps = _pending_timestamps(registry_export)
    if not timestamps:
        return {"status": "idle", "pending_count": 0, "notification_required": False, "artifacts_written": []}

    packet_basis = max(timestamps.values())
    packet = research_knowledge_review.build_review_packet(repo, registry_export, _format_timestamp(packet_basis))
    packet_keys = {(item["review_type"], item["target_id"]) for item in packet["items"]}
    if packet_keys != set(timestamps):
        raise ValueError("pending review packet and timestamp identities differ")

    oldest = min(timestamps.values())
    age_hours = (current_time - oldest).total_seconds() / 3600
    if age_hours < 0:
        raise ValueError("pending review timestamp is in the future")
    if packet["counts"]["total"] >= policy["count_threshold"]:
        trigger_reason = "count_threshold"
    elif age_hours >= policy["max_wait_hours"]:
        trigger_reason = "max_wait_threshold"
    else:
        next_age_trigger = oldest + timedelta(hours=policy["max_wait_hours"])
        return {
            "status": "idle",
            "pending_count": packet["counts"]["total"],
            "oldest_pending_at": _format_timestamp(oldest),
            "count_threshold_remaining": max(
                0, policy["count_threshold"] - packet["counts"]["total"]
            ),
            "next_age_trigger_at": _format_timestamp(next_age_trigger),
            "remaining_wait_hours": round(
                max(
                    0.0,
                    (next_age_trigger - current_time).total_seconds() / 3600,
                ),
                6,
            ),
            "notification_required": False,
            "artifacts_written": [],
        }

    identity = {
        "packet_fingerprint": packet["packet_fingerprint"],
        "policy_fingerprint": policy["policy_fingerprint"],
        "trigger_reason": trigger_reason,
    }
    batch_id = f"knowledge-review-batch-{fingerprint(identity)[:16]}"
    batch_root = Path(policy["output_root"]) / batch_id
    packet_path = batch_root / "packet.json"
    handoff_path = batch_root / "handoff.json"
    advisory_path = batch_root / "recommendations.json"
    human_intent_path = batch_root / "human-intent.json"
    approval_path = batch_root / "batch-approval.json"
    review_events_path = batch_root / "review-events.json"
    post_approval_plan_path = batch_root / "post-approval-plan.json"
    curation_draft_path = batch_root / "curation-draft-packet.json"
    curation_candidate_root = batch_root / "lesson-candidates"
    promotion_review_packet_path = batch_root / "promotion-review-packet.json"
    promotion_base_context_path = batch_root / "promotion-base-context.json"
    promotion_base_manifest_path = batch_root / "promotion-base-manifest.json"
    promotion_human_intent_path = batch_root / "promotion-human-intent.json"
    promotion_approval_path = batch_root / "promotion-approval.json"
    promotion_events_path = batch_root / "promotion-events.json"
    published_manifest_path = batch_root / "published-knowledge-manifest.json"
    handoff = {
        "schema_version": "knowledge-review-batch-handoff-v1",
        "batch_id": batch_id,
        "batch_basis_at": _format_timestamp(packet_basis),
        "trigger_reason": trigger_reason,
        "thresholds": {
            "count_threshold": policy["count_threshold"],
            "max_wait_hours": policy["max_wait_hours"],
        },
        "counts": packet["counts"],
        "oldest_pending_at": _format_timestamp(oldest),
        "newest_pending_at": _format_timestamp(packet_basis),
        "policy_path": policy_path.as_posix(),
        "policy_fingerprint": policy["policy_fingerprint"],
        "packet_path": packet_path.as_posix(),
        "packet_fingerprint": packet["packet_fingerprint"],
        "planned_advisory_path": advisory_path.as_posix(),
        "planned_human_intent_path": human_intent_path.as_posix(),
        "planned_approval_path": approval_path.as_posix(),
        "planned_review_events_path": review_events_path.as_posix(),
        "planned_post_approval_plan_path": post_approval_plan_path.as_posix(),
        "planned_curation_draft_path": curation_draft_path.as_posix(),
        "planned_curation_candidate_root": curation_candidate_root.as_posix(),
        "planned_promotion_review_packet_path": promotion_review_packet_path.as_posix(),
        "planned_promotion_base_context_path": promotion_base_context_path.as_posix(),
        "planned_promotion_base_manifest_path": promotion_base_manifest_path.as_posix(),
        "planned_promotion_human_intent_path": promotion_human_intent_path.as_posix(),
        "planned_promotion_approval_path": promotion_approval_path.as_posix(),
        "planned_promotion_events_path": promotion_events_path.as_posix(),
        "planned_published_manifest_path": published_manifest_path.as_posix(),
        "required_next_action": "human_review_recommendations_then_explicit_batch_approval",
        "human_decision_required": True,
        "advisory_drafting_authorized": True,
        "automatic_decision_authorized": False,
        "automatic_application_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    handoff["handoff_fingerprint"] = knowledge.semantic_fingerprint(handoff, "handoff_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / HANDOFF_SCHEMA)).validate(handoff)
    return {
        "status": "batch_ready",
        "pending_count": packet["counts"]["total"],
        "batch_id": batch_id,
        "trigger_reason": trigger_reason,
        "notification_required": True,
        "artifacts_written": [packet_path.as_posix(), handoff_path.as_posix()],
        "packet": packet,
        "handoff": handoff,
    }


def _publish_immutable(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        if load_document(path) != payload:
            raise ValueError(f"immutable knowledge review artifact conflict: {path}")
        return
    write_json(path, payload)


def publish_batch(repo: Path, result: dict[str, Any]) -> bool:
    if result["status"] != "batch_ready":
        return False
    packet_path, handoff_path = (repo / path for path in result["artifacts_written"])
    already_published = packet_path.exists() and handoff_path.exists()
    for path, payload in ((packet_path, result["packet"]), (handoff_path, result["handoff"])):
        if path.exists() and load_document(path) != payload:
            raise ValueError(f"immutable knowledge review artifact conflict: {path}")
    _publish_immutable(packet_path, result["packet"])
    _publish_immutable(handoff_path, result["handoff"])
    return not already_published


def public_result(result: dict[str, Any], newly_published: bool) -> dict[str, Any]:
    payload = {key: value for key, value in result.items() if key not in {"packet", "handoff"}}
    if result["status"] == "batch_ready" and not newly_published:
        payload["status"] = "awaiting_human_review"
        payload["notification_required"] = False
        payload["artifacts_written"] = []
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--now")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    policy_path = Path(args.policy)
    if policy_path.is_absolute():
        try:
            policy_relative = policy_path.resolve().relative_to(repo).as_posix()
        except ValueError as exc:
            raise ValueError("knowledge review batch policy must be inside the repository") from exc
        policy_path = Path(policy_relative)
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo / registry_path
    policy = load_document(repo / policy_path)
    result = build_batch(repo, export_director_registry.export_registry(str(registry_path)), policy, args.now or utc_now(), policy_path)
    newly_published = publish_batch(repo, result)
    print(json.dumps(public_result(result, newly_published), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
