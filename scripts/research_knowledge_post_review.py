#!/usr/bin/env python3
"""Compile approved knowledge-review events into a non-executing follow-up plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import fingerprint, load_document


ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = Path("research/knowledge/schemas/knowledge-review-post-approval-plan.schema.json")


def _action(review_type: str, decision: str) -> tuple[str, str, str, bool]:
    if decision == "rejected":
        resulting = "deprecated" if review_type == "license_review" else "rejected"
        return resulting, "closed_no_follow_up", "none", False
    if review_type == "lesson_feedback":
        return "approved_for_manual_curation", "prepare_non_authoritative_lesson_curation_draft", "knowledge_curator", False
    if review_type == "source_update":
        return "approved_for_manual_rebuild", "manual_source_snapshot_rebuild", "human_source_maintainer", True
    if review_type == "license_review":
        return "active_pinned", "manual_source_metadata_rebuild", "human_source_maintainer", True
    raise ValueError("unsupported post-approval review type")


def build_post_approval_plan(
    repo: Path,
    handoff: dict[str, Any],
    packet: dict[str, Any],
    advisory: dict[str, Any],
    approval: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    packet_by_key = {item["review_key"]: item for item in packet["items"]}
    recommendations = advisory["recommendations"]
    if len(events) != len(recommendations) or len(packet_by_key) != len(recommendations):
        raise ValueError("post-approval plan inputs do not have exact coverage")
    actions = []
    for recommendation, event in zip(recommendations, events, strict=True):
        packet_item = packet_by_key.get(recommendation["review_key"])
        if packet_item is None:
            raise ValueError("post-approval recommendation is not in the packet")
        expected = (
            recommendation["review_type"], recommendation["target_id"], recommendation["recommended_decision"]
        )
        if (event["review_type"], event["target_id"], event["decision"]) != expected:
            raise ValueError("post-approval event differs from its recommendation")
        resulting_status, action_type, owner, manual_required = _action(event["review_type"], event["decision"])
        actions.append({
            "review_key": recommendation["review_key"],
            "review_event_id": event["review_event_id"],
            "review_type": event["review_type"],
            "target_id": event["target_id"],
            "decision": event["decision"],
            "resulting_status": resulting_status,
            "action_type": action_type,
            "workflow_owner": owner,
            "evidence": packet_item["evidence"],
            "manual_action_required": manual_required,
            "automatic_execution_authorized": False,
        })
    identity = {
        "batch_id": handoff["batch_id"],
        "approval_fingerprint": approval["approval_fingerprint"],
        "review_event_fingerprints": [event["event_fingerprint"] for event in events],
    }
    plan = {
        "schema_version": "knowledge-review-post-approval-plan-v1",
        "plan_id": f"knowledge-post-approval-plan-{fingerprint(identity)[:16]}",
        "generated_at": approval["decided_at"],
        "batch_id": handoff["batch_id"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "advisory_fingerprint": advisory["advisory_fingerprint"],
        "approval_fingerprint": approval["approval_fingerprint"],
        "actions": actions,
        "summary": {
            "lesson_curation_drafts": sum(item["action_type"] == "prepare_non_authoritative_lesson_curation_draft" for item in actions),
            "source_snapshot_rebuilds": sum(item["action_type"] == "manual_source_snapshot_rebuild" for item in actions),
            "source_metadata_rebuilds": sum(item["action_type"] == "manual_source_metadata_rebuild" for item in actions),
            "closed": sum(item["action_type"] == "closed_no_follow_up" for item in actions),
            "total": len(actions),
        },
        "automatic_candidate_creation_authorized": False,
        "curation_drafting_authorized": True,
        "automatic_source_rebuild_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    plan["plan_fingerprint"] = knowledge.semantic_fingerprint(plan, "plan_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / PLAN_SCHEMA)).validate(plan)
    return plan
