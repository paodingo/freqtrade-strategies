#!/usr/bin/env python3
"""Build a unified knowledge-review packet and apply explicit human decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import fingerprint, load_document, open_director_registry, utc_now, write_json


ROOT = Path(__file__).resolve().parents[1]
PACKET_SCHEMA = Path("research/knowledge/schemas/knowledge-review-packet.schema.json")
EVENT_SCHEMA = Path("research/knowledge/schemas/knowledge-review-event.schema.json")
BATCH_APPROVAL_SCHEMA = Path("research/knowledge/schemas/knowledge-review-batch-approval.schema.json")
DEFAULT_PACKET = Path("reports/audits/open-source-learning-v1/pending-review-packet.json")


def _validate(repo: Path, schema_path: Path, payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(load_document(repo / schema_path)).validate(payload)


def sync_feedback_backlog(registry_path: str | Path, registry_export: dict[str, Any]) -> int:
    """Backfill authoritative historical drafts without resetting local review decisions."""
    rows = registry_export.get("tables", {}).get("research_lesson_feedback_drafts", [])
    connection = open_director_registry(registry_path)
    immutable_fields = ("feedback_id", "run_id", "campaign_id", "proposal_id", "result_code", "payload_json", "created_at")
    try:
        connection.execute("BEGIN IMMEDIATE")
        for row in rows:
            connection.execute(
                "INSERT OR IGNORE INTO research_lesson_feedback_drafts("
                "feedback_id,run_id,campaign_id,proposal_id,result_code,review_status,payload_json,created_at"
                ") VALUES(?,?,?,?,?,?,?,?)",
                tuple(row[field] for field in ("feedback_id", "run_id", "campaign_id", "proposal_id", "result_code", "review_status", "payload_json", "created_at")),
            )
            actual = connection.execute(
                "SELECT * FROM research_lesson_feedback_drafts WHERE feedback_id=?", (row["feedback_id"],)
            ).fetchone()
            if actual is None or any(actual[field] != row[field] for field in immutable_fields):
                raise ValueError("authoritative feedback backlog identity conflict")
        connection.commit()
        return connection.execute("SELECT COUNT(*) FROM research_lesson_feedback_drafts").fetchone()[0]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def build_review_packet(repo: Path, registry_export: dict[str, Any], generated_at: str) -> dict[str, Any]:
    tables = registry_export.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("registry export tables are missing")
    assets_by_run: dict[str, list[str]] = {}
    for asset in tables.get("research_campaign_assets", []):
        assets_by_run.setdefault(str(asset["run_id"]), []).append(str(asset["path"]))
    items = []
    for row in tables.get("research_knowledge_update_proposals", []):
        if row["status"] != "pending_human_approval":
            continue
        items.append({
            "review_key": f"source_update:{row['proposal_id']}",
            "review_type": "source_update",
            "target_id": row["proposal_id"],
            "current_status": row["status"],
            "summary": f"{row['project_id']}: {row['current_commit']} -> {row['upstream_commit']}",
            "evidence": ["reports/audits/open-source-learning-v1/source-refresh-report.json"],
            "allowed_decisions": ["approved", "rejected"],
            "automatic_application_authorized": False,
        })
    for row in tables.get("research_lesson_feedback_drafts", []):
        if row["review_status"] != "pending_human_review":
            continue
        evidence = sorted(set(assets_by_run.get(str(row["run_id"]), [])))
        if not evidence:
            try:
                feedback_payload = json.loads(row["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError("lesson feedback payload is invalid") from exc
            payload_artifacts = feedback_payload.get("evidence_artifacts", [])
            if isinstance(payload_artifacts, list):
                evidence = sorted(
                    {
                        str(item["path"])
                        for item in payload_artifacts
                        if isinstance(item, dict) and isinstance(item.get("path"), str)
                    }
                )
        items.append({
            "review_key": f"lesson_feedback:{row['feedback_id']}",
            "review_type": "lesson_feedback",
            "target_id": row["feedback_id"],
            "current_status": row["review_status"],
            "summary": f"{row['campaign_id']}: {row['result_code']}",
            "evidence": evidence,
            "allowed_decisions": ["approved", "rejected"],
            "automatic_application_authorized": False,
        })
    for row in tables.get("research_knowledge_lifecycle", []):
        if row["item_type"] != "source" or row["lifecycle_status"] != "review_required":
            continue
        items.append({
            "review_key": f"license_review:{row['item_key']}",
            "review_type": "license_review",
            "target_id": row["item_key"],
            "current_status": row["lifecycle_status"],
            "summary": f"License review required for source snapshot {row['item_id']}",
            "evidence": ["research/knowledge/open-source-v1/current-context.json"],
            "allowed_decisions": ["approved", "rejected"],
            "automatic_application_authorized": False,
        })
    items.sort(key=lambda item: (item["review_type"], item["target_id"]))
    counts = {
        "source_updates": sum(item["review_type"] == "source_update" for item in items),
        "lesson_feedback": sum(item["review_type"] == "lesson_feedback" for item in items),
        "license_reviews": sum(item["review_type"] == "license_review" for item in items),
        "total": len(items),
    }
    packet = {
        "schema_version": "knowledge-review-packet-v1",
        "generated_at": generated_at,
        "items": items,
        "counts": counts,
        "decision_contract": {
            "approval_schema": EVENT_SCHEMA.as_posix(),
            "reviewer_type": "human_user",
            "approved_source_update_result": "approved_for_manual_rebuild",
            "approved_lesson_feedback_result": "approved_for_manual_curation",
            "automatic_promotion_authorized": False,
        },
        "execution_authorized": False,
    }
    packet["packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "packet_fingerprint")
    _validate(repo, PACKET_SCHEMA, packet)
    return packet


def build_review_event(repo: Path, packet: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    required = {"review_type", "target_id", "decision", "reviewer_type", "reviewer_id", "reason", "decided_at", "source_packet_fingerprint"}
    if set(intent) != required:
        raise ValueError("human review intent fields are invalid")
    if intent["reviewer_type"] != "human_user" or intent["decision"] not in {"approved", "rejected"}:
        raise ValueError("explicit human review decision is required")
    if intent["source_packet_fingerprint"] != packet.get("packet_fingerprint"):
        raise ValueError("review packet fingerprint mismatch")
    if not any(
        item["review_type"] == intent["review_type"] and item["target_id"] == intent["target_id"]
        for item in packet.get("items", [])
    ):
        raise ValueError("review target is not pending in the packet")
    identity = {key: intent[key] for key in sorted(intent)}
    event_id = f"knowledge-review-{fingerprint(identity)[:16]}"
    event = {
        "schema_version": "knowledge-review-event-v1",
        "review_event_id": event_id,
        **intent,
        "automatic_source_update_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    event["event_fingerprint"] = knowledge.semantic_fingerprint(event, "event_fingerprint")
    _validate(repo, EVENT_SCHEMA, event)
    return event


def _apply_review_event(connection: Any, event: dict[str, Any]) -> dict[str, Any]:
    existing = connection.execute(
            "SELECT payload_json FROM research_knowledge_review_events WHERE review_type=? AND target_id=?",
            (event["review_type"], event["target_id"]),
    ).fetchone()
    payload_json = json.dumps(event, sort_keys=True)
    if existing is not None:
        if existing["payload_json"] != payload_json:
            raise ValueError("knowledge review target already has a different decision")
        return event
    if event["review_type"] == "source_update":
        new_status = "approved_for_manual_rebuild" if event["decision"] == "approved" else "rejected"
        cursor = connection.execute(
            "UPDATE research_knowledge_update_proposals SET status=? WHERE proposal_id=? AND status='pending_human_approval'",
            (new_status, event["target_id"]),
        )
    elif event["review_type"] == "lesson_feedback":
        new_status = "approved_for_manual_curation" if event["decision"] == "approved" else "rejected"
        cursor = connection.execute(
            "UPDATE research_lesson_feedback_drafts SET review_status=? WHERE feedback_id=? AND review_status='pending_human_review'",
            (new_status, event["target_id"]),
        )
    elif event["review_type"] == "license_review":
        new_status = "active_pinned" if event["decision"] == "approved" else "deprecated"
        cursor = connection.execute(
            "UPDATE research_knowledge_lifecycle SET lifecycle_status=?,reason=?,updated_at=? WHERE item_key=? AND lifecycle_status='review_required'",
            (new_status, event["reason"], event["decided_at"], event["target_id"]),
        )
    else:
        raise ValueError("knowledge review type is invalid")
    if cursor.rowcount != 1:
        raise ValueError("knowledge review target is missing or no longer pending")
    connection.execute(
        "INSERT INTO research_knowledge_review_events("
        "review_event_id,review_type,target_id,decision,reviewer_id,source_packet_fingerprint,payload_json,decided_at"
        ") VALUES(?,?,?,?,?,?,?,?)",
        (event["review_event_id"], event["review_type"], event["target_id"], event["decision"], event["reviewer_id"], event["source_packet_fingerprint"], payload_json, event["decided_at"]),
    )
    return event


def apply_review_event(registry_path: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        result = _apply_review_event(connection, event)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def apply_advisory_batch(
    repo: Path,
    registry_path: str | Path,
    packet: dict[str, Any],
    advisory: dict[str, Any],
    approval: dict[str, Any],
) -> list[dict[str, Any]]:
    import research_knowledge_advisory

    summary = research_knowledge_advisory.validate_advisory(repo, packet, advisory)
    _validate(repo, BATCH_APPROVAL_SCHEMA, approval)
    if knowledge.semantic_fingerprint(approval, "approval_fingerprint") != approval["approval_fingerprint"]:
        raise ValueError("batch approval fingerprint mismatch")
    if approval["packet_fingerprint"] != packet["packet_fingerprint"] or approval["advisory_fingerprint"] != advisory["advisory_fingerprint"]:
        raise ValueError("batch approval is not bound to the current decision basis")
    if approval["approved_count"] != summary["approved"] or approval["rejected_count"] != summary["rejected"]:
        raise ValueError("batch approval counts do not match recommendations")
    events = [
        build_review_event(repo, packet, {
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
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        for event in events:
            _apply_review_event(connection, event)
        connection.commit()
        return events
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    subparsers = parser.add_subparsers(dest="mode", required=True)
    packet_parser = subparsers.add_parser("packet")
    packet_parser.add_argument("--registry-export", default="research/director/registry-records.json")
    packet_parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    packet_parser.add_argument("--output", default=str(DEFAULT_PACKET))
    packet_parser.add_argument("--generated-at")
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    apply_parser.add_argument("--packet", default=str(DEFAULT_PACKET))
    apply_parser.add_argument("--approval", required=True)
    batch_parser = subparsers.add_parser("apply-advisory")
    batch_parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    batch_parser.add_argument("--packet", required=True)
    batch_parser.add_argument("--advisory", required=True)
    batch_parser.add_argument("--approval", required=True)
    batch_parser.add_argument("--archive-dir")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    if args.mode == "packet":
        registry_payload = load_document(repo / args.registry_export)
        sync_feedback_backlog(args.registry, registry_payload)
        result = build_review_packet(repo, registry_payload, args.generated_at or utc_now())
        write_json(repo / args.output, result)
    elif args.mode == "apply":
        packet = load_document(repo / args.packet)
        _validate(repo, PACKET_SCHEMA, packet)
        approval_path = Path(args.approval)
        if not approval_path.is_absolute():
            approval_path = repo / approval_path
        result = apply_review_event(args.registry, build_review_event(repo, packet, load_document(approval_path)))
    else:
        packet = load_document(repo / args.packet)
        advisory = load_document(repo / args.advisory)
        approval = load_document(repo / args.approval)
        events = apply_advisory_batch(repo, args.registry, packet, advisory, approval)
        if args.archive_dir:
            archive = repo / args.archive_dir
            write_json(archive / "packet.json", packet)
            write_json(archive / "recommendations.json", advisory)
            write_json(archive / "batch-approval.json", approval)
            write_json(archive / "review-events.json", {"events": events, "execution_authorized": False})
        result = {"applied": len(events), "approved": sum(event["decision"] == "approved" for event in events), "rejected": sum(event["decision"] == "rejected" for event in events)}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
