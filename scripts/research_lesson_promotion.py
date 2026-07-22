#!/usr/bin/env python3
"""Apply an exact human-approved lesson promotion batch without trading execution."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import fingerprint, load_document, open_director_registry, write_json


ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA = Path("research/knowledge/schemas/knowledge-review-event.schema.json")
ARCHIVE_ROOT = Path("reports/audits/open-source-learning-v1/promotion-batches/open-source-learning-v1-lesson-promotion-20260720")


def validate_approval(repo: Path, approval: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    cards = knowledge.promoted_lesson_cards(repo)
    if approval != load_document(repo / knowledge.PROMOTION_APPROVAL):
        raise ValueError("lesson promotion approval must be the governed workspace approval")
    if packet != load_document(repo / knowledge.PROMOTION_PACKET):
        raise ValueError("lesson promotion packet must be the governed workspace packet")
    if approval["approved_count"] != 6 or approval["rejected_count"] != 0 or len(cards) != 6:
        raise ValueError("lesson promotion approval counts do not match the explicit human decision")
    return cards


def build_events(repo: Path, approval: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    validator = jsonschema.Draft202012Validator(load_document(repo / EVENT_SCHEMA))
    events = []
    for decision in sorted(approval["decisions"], key=lambda item: item["candidate_id"]):
        identity = {
            "review_type": "lesson_promotion",
            "target_id": decision["candidate_id"],
            "decision": decision["decision"],
            "reviewer_id": approval["reviewer_id"],
            "source_packet_fingerprint": packet["packet_fingerprint"],
        }
        event = {
            "schema_version": "knowledge-review-event-v1",
            "review_event_id": f"knowledge-review-{fingerprint(identity)[:16]}",
            **identity,
            "reviewer_type": "human_user",
            "reason": f"accepted_human_promotion_batch:{approval['approval_id']}",
            "decided_at": approval["decided_at"],
            "automatic_source_update_authorized": False,
            "automatic_lesson_promotion_authorized": False,
            "execution_authorized": False,
        }
        event["event_fingerprint"] = knowledge.semantic_fingerprint(event, "event_fingerprint")
        validator.validate(event)
        events.append(event)
    return events


def apply_registry_promotion(
    registry_path: str | Path,
    approval: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, int]:
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        decisions = sorted(approval["decisions"], key=lambda item: item["candidate_id"])
        for decision, event in zip(decisions, events):
            row = connection.execute(
                "SELECT candidate_fingerprint,status FROM research_lesson_curation_candidates WHERE candidate_id=?",
                (decision["candidate_id"],),
            ).fetchone()
            if row is None or row["candidate_fingerprint"] != decision["candidate_fingerprint"]:
                raise ValueError("lesson promotion registry candidate identity conflict")
            if row["status"] not in {"pending_human_promotion_review", "promoted"}:
                raise ValueError("lesson promotion registry candidate is not promotable")
            connection.execute(
                "UPDATE research_lesson_curation_candidates SET status='promoted' WHERE candidate_id=?",
                (decision["candidate_id"],),
            )
            payload_json = json.dumps(event, sort_keys=True)
            existing = connection.execute(
                "SELECT payload_json FROM research_knowledge_review_events WHERE review_type='lesson_promotion' AND target_id=?",
                (decision["candidate_id"],),
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO research_knowledge_review_events(review_event_id,review_type,target_id,decision,reviewer_id,source_packet_fingerprint,payload_json,decided_at) VALUES(?,?,?,?,?,?,?,?)",
                    (event["review_event_id"], event["review_type"], event["target_id"], event["decision"], event["reviewer_id"], event["source_packet_fingerprint"], payload_json, event["decided_at"]),
                )
            elif existing["payload_json"] != payload_json:
                raise ValueError("lesson promotion review event conflict")
        replacement = "ranging-short-temporal-retention-v1"
        connection.execute(
            "UPDATE research_knowledge_lifecycle SET lifecycle_status='superseded',superseded_by=?,reason=?,updated_at=? WHERE item_type='lesson' AND item_id='ranging-short-branch-negative-contributor-v1' AND lifecycle_status IN ('active','superseded')",
            (replacement, f"approved_promotion:{approval['approval_id']}", approval["decided_at"]),
        )
        connection.execute(
            "DELETE FROM open_source_knowledge_lineage WHERE target_type='research_lesson' AND target_id='ranging-short-branch-negative-contributor-v1'"
        )
        connection.execute(
            "DELETE FROM open_source_research_lessons WHERE lesson_id='ranging-short-branch-negative-contributor-v1'"
        )
        connection.commit()
        return {
            "promoted": connection.execute("SELECT COUNT(*) FROM research_lesson_curation_candidates WHERE status='promoted'").fetchone()[0],
            "promotion_events": connection.execute("SELECT COUNT(*) FROM research_knowledge_review_events WHERE review_type='lesson_promotion'").fetchone()[0],
            "formal_lessons": connection.execute("SELECT COUNT(*) FROM open_source_research_lessons").fetchone()[0],
            "knowledge_lineage_edges": connection.execute("SELECT COUNT(*) FROM open_source_knowledge_lineage").fetchone()[0],
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    approval = load_document(repo / knowledge.PROMOTION_APPROVAL)
    packet = load_document(repo / knowledge.PROMOTION_PACKET)
    cards = validate_approval(repo, approval, packet)
    events = build_events(repo, approval, packet)
    with tempfile.TemporaryDirectory(prefix=".lesson-promotion-preflight-", dir=repo) as temporary:
        preflight = knowledge.build_knowledge(repo, Path(temporary) / "knowledge")
        if preflight["counts"]["lessons"] != 9:
            raise ValueError("promoted formal lesson catalog must contain exactly nine cards")
    manifest = knowledge.build_knowledge(repo)
    registration = knowledge.register_knowledge(repo, Path(args.registry), manifest)
    registry = apply_registry_promotion(args.registry, approval, events)
    import research_knowledge_maintenance as maintenance
    lifecycle = maintenance.register_lifecycle_and_updates(
        repo,
        Path(args.registry),
        load_document(repo / "reports/audits/open-source-learning-v1/source-refresh-report.json"),
    )
    write_json(repo / ARCHIVE_ROOT / "packet.json", packet)
    write_json(repo / ARCHIVE_ROOT / "approval.json", approval)
    write_json(repo / ARCHIVE_ROOT / "review-events.json", {"events": events, "execution_authorized": False})
    result = {
        "approved": len(cards),
        "rejected": 0,
        "formal_lessons": manifest["counts"]["lessons"],
        "knowledge_snapshot_fingerprint": manifest["knowledge_snapshot_fingerprint"],
        "registry": registry,
        "registration": registration,
        "lifecycle": lifecycle,
        "automatic_lesson_promotion_authorized": False,
        "trading_execution_authorized": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
