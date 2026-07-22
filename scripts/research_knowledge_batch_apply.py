#!/usr/bin/env python3
"""Compile an explicit human batch intent and apply its exact review recommendations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

import export_director_registry
import open_source_knowledge as knowledge
import research_knowledge_advisory
import research_knowledge_review
import research_knowledge_post_review
from research_director_common import fingerprint, load_document, write_json


ROOT = Path(__file__).resolve().parents[1]
INTENT_SCHEMA = Path("research/knowledge/schemas/knowledge-review-human-intent.schema.json")
HANDOFF_SCHEMA = Path("research/knowledge/schemas/knowledge-review-batch-handoff.schema.json")
APPROVAL_SCHEMA = Path("research/knowledge/schemas/knowledge-review-batch-approval.schema.json")
BATCH_ROOT = Path("reports/audits/open-source-learning-v1/review-batches/aggregated")


def _validate(repo: Path, schema: Path, payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(load_document(repo / schema)).validate(payload)


def build_approval(
    repo: Path,
    handoff: dict[str, Any],
    packet: dict[str, Any],
    advisory: dict[str, Any],
    intent: dict[str, Any],
) -> dict[str, Any]:
    _validate(repo, HANDOFF_SCHEMA, handoff)
    _validate(repo, INTENT_SCHEMA, intent)
    if knowledge.semantic_fingerprint(handoff, "handoff_fingerprint") != handoff["handoff_fingerprint"]:
        raise ValueError("knowledge review handoff fingerprint mismatch")
    if knowledge.semantic_fingerprint(intent, "intent_fingerprint") != intent["intent_fingerprint"]:
        raise ValueError("human approval intent fingerprint mismatch")
    intent_identity = {
        key: value
        for key, value in intent.items()
        if key not in {"schema_version", "intent_id", "intent_fingerprint"}
    }
    if intent["intent_id"] != f"knowledge-review-human-intent-{fingerprint(intent_identity)[:16]}":
        raise ValueError("human approval intent identity mismatch")
    summary = research_knowledge_advisory.validate_aggregated_advisory(repo, packet, advisory)
    if intent["batch_id"] != handoff["batch_id"]:
        raise ValueError("human approval intent batch mismatch")
    if intent["packet_fingerprint"] != packet["packet_fingerprint"] or handoff["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise ValueError("human approval intent packet mismatch")
    if intent["advisory_fingerprint"] != advisory["advisory_fingerprint"]:
        raise ValueError("human approval intent advisory mismatch")
    if intent["approved_count"] != summary["approved"] or intent["rejected_count"] != summary["rejected"]:
        raise ValueError("human approval intent counts do not match recommendations")
    approval = {
        "schema_version": "knowledge-review-batch-approval-v1",
        "approval_id": f"knowledge-review-approval-{intent['intent_fingerprint'][:16]}",
        "reviewer_type": intent["reviewer_type"],
        "reviewer_id": intent["reviewer_id"],
        "decision": intent["decision"],
        "statement": intent["statement"],
        "decided_at": intent["decided_at"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "advisory_fingerprint": advisory["advisory_fingerprint"],
        "approved_count": summary["approved"],
        "rejected_count": summary["rejected"],
        "automatic_source_update_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    approval["approval_fingerprint"] = knowledge.semantic_fingerprint(approval, "approval_fingerprint")
    _validate(repo, APPROVAL_SCHEMA, approval)
    return approval


def build_human_intent(
    repo: Path,
    handoff: dict[str, Any],
    packet: dict[str, Any],
    advisory: dict[str, Any],
    reviewer_id: str,
    statement: str,
    decided_at: str,
    approved_count: int,
    rejected_count: int,
) -> dict[str, Any]:
    summary = research_knowledge_advisory.validate_aggregated_advisory(repo, packet, advisory)
    if approved_count != summary["approved"] or rejected_count != summary["rejected"]:
        raise ValueError("explicit human approval counts do not match recommendations")
    basis = {
        "batch_id": handoff["batch_id"],
        "reviewer_type": "human_user",
        "reviewer_id": reviewer_id,
        "decision": "approve_recommendations",
        "statement": statement,
        "decided_at": decided_at,
        "authorization_source": "explicit_user_instruction",
        "packet_fingerprint": packet["packet_fingerprint"],
        "advisory_fingerprint": advisory["advisory_fingerprint"],
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "review_event_application_authorized": True,
        "automatic_source_update_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    intent = {
        "schema_version": "knowledge-review-human-intent-v1",
        "intent_id": f"knowledge-review-human-intent-{fingerprint(basis)[:16]}",
        **basis,
    }
    intent["intent_fingerprint"] = knowledge.semantic_fingerprint(intent, "intent_fingerprint")
    _validate(repo, INTENT_SCHEMA, intent)
    return intent


def apply_human_approved_batch(
    repo: Path,
    registry_path: str | Path,
    handoff: dict[str, Any],
    packet: dict[str, Any],
    advisory: dict[str, Any],
    intent: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    approval = build_approval(repo, handoff, packet, advisory, intent)
    events = research_knowledge_review.apply_advisory_batch(repo, registry_path, packet, advisory, approval)
    return approval, events


def _publish_immutable(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        if load_document(path) != payload:
            raise ValueError(f"immutable knowledge review approval artifact conflict: {path}")
        return
    write_json(path, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--intent")
    parser.add_argument("--human-statement")
    parser.add_argument("--reviewer-id", default="workspace_user")
    parser.add_argument("--decided-at")
    parser.add_argument("--approved-count", type=int)
    parser.add_argument("--rejected-count", type=int)
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--registry-export", default="research/director/registry-records.json")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo / registry_path
    if not args.batch_id.startswith("knowledge-review-batch-") or len(args.batch_id) != 39:
        raise ValueError("knowledge review batch id is invalid")
    batch_root = BATCH_ROOT / args.batch_id
    expected_intent = batch_root / "human-intent.json"
    handoff = load_document(repo / batch_root / "handoff.json")
    packet = load_document(repo / handoff["packet_path"])
    advisory = load_document(repo / handoff["planned_advisory_path"])
    if args.intent:
        if any(value is not None for value in (args.human_statement, args.decided_at, args.approved_count, args.rejected_count)):
            raise ValueError("provide either an existing intent or explicit human approval fields, not both")
        intent_path = Path(args.intent)
        if intent_path.is_absolute():
            intent_path = Path(intent_path.resolve().relative_to(repo).as_posix())
        if intent_path.as_posix() != expected_intent.as_posix():
            raise ValueError("human approval intent must use the batch-bound exact path")
        intent = load_document(repo / intent_path)
    else:
        if args.human_statement is None or args.decided_at is None or args.approved_count is None or args.rejected_count is None:
            raise ValueError("explicit human statement, decision time, approved count, and rejected count are required")
        intent_path = expected_intent
        intent = build_human_intent(
            repo, handoff, packet, advisory, args.reviewer_id, args.human_statement,
            args.decided_at, args.approved_count, args.rejected_count,
        )
    if handoff["planned_human_intent_path"] != intent_path.as_posix():
        raise ValueError("handoff human intent path mismatch")
    approval_path = Path(handoff["planned_approval_path"])
    events_path = Path(handoff["planned_review_events_path"])
    approval = build_approval(repo, handoff, packet, advisory, intent)
    prospective_events = [
        research_knowledge_review.build_review_event(repo, packet, {
            "review_type": item["review_type"],
            "target_id": item["target_id"],
            "decision": item["recommended_decision"],
            "reviewer_type": approval["reviewer_type"],
            "reviewer_id": approval["reviewer_id"],
            "reason": f"accepted_advisory:{advisory['advisory_id']}:{item['disposition']}",
            "decided_at": approval["decided_at"],
            "source_packet_fingerprint": packet["packet_fingerprint"],
        })
        for item in advisory["recommendations"]
    ]
    events_payload = {"events": prospective_events, "execution_authorized": False}
    post_plan_path = Path(handoff["planned_post_approval_plan_path"])
    post_plan = research_knowledge_post_review.build_post_approval_plan(
        repo, handoff, packet, advisory, approval, prospective_events
    )
    for path, payload in (
        (repo / intent_path, intent),
        (repo / approval_path, approval),
        (repo / events_path, events_payload),
        (repo / post_plan_path, post_plan),
    ):
        if path.exists() and load_document(path) != payload:
            raise ValueError(f"immutable knowledge review approval artifact conflict: {path}")
    approval, events = apply_human_approved_batch(repo, registry_path, handoff, packet, advisory, intent)
    if events != prospective_events:
        raise ValueError("applied review events differ from the preflight set")
    _publish_immutable(repo / intent_path, intent)
    _publish_immutable(repo / approval_path, approval)
    _publish_immutable(repo / events_path, events_payload)
    _publish_immutable(repo / post_plan_path, post_plan)
    export_path = repo / args.registry_export
    base_export = load_document(export_path)
    live_export = export_director_registry.export_registry(str(registry_path))
    write_json(export_path, export_director_registry.merge_knowledge_tables(base_export, live_export))
    result = {
        "status": "human_approved_batch_applied",
        "batch_id": args.batch_id,
        "approved": approval["approved_count"],
        "rejected": approval["rejected_count"],
        "review_events": len(events),
        "approval_path": approval_path.as_posix(),
        "review_events_path": events_path.as_posix(),
        "post_approval_plan_path": post_plan_path.as_posix(),
        "automatic_source_update_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
