#!/usr/bin/env python3
"""Apply one explicitly human-approved generic lesson promotion batch."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import jsonschema

import build_current_research_state
import export_director_registry
import open_source_knowledge as knowledge
import research_knowledge_maintenance as maintenance
from research_director_common import fingerprint, load_document, open_director_registry, sha256_file


ROOT = Path(__file__).resolve().parents[1]
BATCH_ROOT = Path("reports/audits/open-source-learning-v1/review-batches/aggregated")
INTENT_SCHEMA = Path("research/knowledge/schemas/research-lesson-promotion-human-intent.schema.json")
APPROVAL_SCHEMA = Path("research/knowledge/schemas/research-lesson-promotion-approval.schema.json")
PACKET_SCHEMA = Path("research/knowledge/schemas/research-lesson-promotion-packet.schema.json")
CANDIDATE_SCHEMA = Path("research/knowledge/schemas/research-lesson-curation-candidate.schema.json")
EVENT_SCHEMA = Path("research/knowledge/schemas/knowledge-review-event.schema.json")
KNOWLEDGE_ROOT = Path("research/knowledge/open-source-v1")
CURRENT_STATE_JSON = Path("research/director/current-research-state.json")
CURRENT_STATE_MD = Path("research/director/current-research-state.md")
RETRIEVAL_EVALUATION = Path("reports/audits/open-source-learning-v1/retrieval-evaluation.json")
LEARNING_LOOP_HEALTH = Path("reports/audits/open-source-learning-v1/learning-loop-health.json")
SOURCE_REFRESH_REPORT = Path("reports/audits/open-source-learning-v1/source-refresh-report.json")


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_canonical_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _validate(repo: Path, schema: Path, payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(load_document(repo / schema)).validate(payload)


def load_promotion_basis(repo: Path, batch_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    batch_root = repo / BATCH_ROOT / batch_id
    handoff = load_document(batch_root / "handoff.json")
    packet = load_document(repo / handoff["planned_promotion_review_packet_path"])
    _validate(repo, PACKET_SCHEMA, packet)
    if knowledge.semantic_fingerprint(packet, "packet_fingerprint") != packet["packet_fingerprint"]:
        raise ValueError("promotion packet fingerprint mismatch")
    if packet["source_review_batch"] != batch_id:
        raise ValueError("promotion packet batch mismatch")
    candidate_validator = jsonschema.Draft202012Validator(load_document(repo / CANDIDATE_SCHEMA))
    candidates = []
    expected_root = Path(handoff["planned_curation_candidate_root"])
    for reference in packet["candidates"]:
        expected_path = expected_root / f"{reference['candidate_id']}.json"
        if reference["path"] != expected_path.as_posix():
            raise ValueError("promotion candidate path is not batch-bound")
        candidate = load_document(repo / reference["path"])
        candidate_validator.validate(candidate)
        if candidate["candidate_id"] != reference["candidate_id"] or candidate["candidate_fingerprint"] != reference["candidate_fingerprint"]:
            raise ValueError("promotion candidate reference mismatch")
        if knowledge.semantic_fingerprint(candidate, "candidate_fingerprint") != candidate["candidate_fingerprint"]:
            raise ValueError("promotion candidate fingerprint mismatch")
        for evidence in candidate["proposed_card"]["evidence_paths"]:
            evidence_path = (repo / evidence).resolve()
            try:
                evidence_path.relative_to(repo.resolve())
            except ValueError as exc:
                raise ValueError("promotion candidate evidence escapes the repository") from exc
            if not evidence_path.is_file():
                raise ValueError("promotion candidate evidence is missing")
        candidates.append(candidate)
    if len({item["candidate_id"] for item in candidates}) != len(candidates):
        raise ValueError("promotion packet contains duplicate candidates")
    return handoff, packet, candidates


def build_human_intent(
    repo: Path,
    batch_id: str,
    packet: dict[str, Any],
    candidates: list[dict[str, Any]],
    reviewer_id: str,
    statement: str,
    decided_at: str,
    decisions_by_id: dict[str, str],
) -> dict[str, Any]:
    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    if set(decisions_by_id) != set(candidate_by_id) or any(value not in {"approved", "rejected"} for value in decisions_by_id.values()):
        raise ValueError("human promotion decisions must cover candidates exactly once")
    decisions = [
        {
            "candidate_id": candidate_id,
            "candidate_fingerprint": candidate_by_id[candidate_id]["candidate_fingerprint"],
            "decision": decisions_by_id[candidate_id],
        }
        for candidate_id in sorted(candidate_by_id)
    ]
    basis = {
        "batch_id": batch_id,
        "reviewer_type": "human_user",
        "reviewer_id": reviewer_id,
        "statement": statement,
        "decided_at": decided_at,
        "authorization_source": "explicit_user_instruction",
        "packet_fingerprint": packet["packet_fingerprint"],
        "decisions": decisions,
        "approved_count": sum(item["decision"] == "approved" for item in decisions),
        "rejected_count": sum(item["decision"] == "rejected" for item in decisions),
        "knowledge_candidate_registration_authorized": True,
        "formal_knowledge_publication_authorized": True,
        "lesson_promotion_application_authorized": True,
        "strategy_mutation_authorized": False,
        "trading_execution_authorized": False,
    }
    intent = {
        "schema_version": "research-lesson-promotion-human-intent-v1",
        "intent_id": f"lesson-promotion-human-intent-{fingerprint(basis)[:16]}",
        **basis,
    }
    intent["intent_fingerprint"] = knowledge.semantic_fingerprint(intent, "intent_fingerprint")
    _validate(repo, INTENT_SCHEMA, intent)
    return intent


def build_approval(
    repo: Path,
    packet: dict[str, Any],
    candidates: list[dict[str, Any]],
    intent: dict[str, Any],
) -> dict[str, Any]:
    _validate(repo, INTENT_SCHEMA, intent)
    if knowledge.semantic_fingerprint(intent, "intent_fingerprint") != intent["intent_fingerprint"]:
        raise ValueError("promotion human intent fingerprint mismatch")
    identity = {
        key: value for key, value in intent.items()
        if key not in {"schema_version", "intent_id", "intent_fingerprint"}
    }
    if intent["intent_id"] != f"lesson-promotion-human-intent-{fingerprint(identity)[:16]}":
        raise ValueError("promotion human intent identity mismatch")
    if intent["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise ValueError("promotion human intent packet mismatch")
    expected = {
        item["candidate_id"]: item["candidate_fingerprint"]
        for item in candidates
    }
    actual = {
        item["candidate_id"]: item["candidate_fingerprint"]
        for item in intent["decisions"]
    }
    if len(actual) != len(intent["decisions"]) or actual != expected:
        raise ValueError("promotion human intent candidate binding mismatch")
    if intent["approved_count"] + intent["rejected_count"] != len(candidates):
        raise ValueError("promotion human intent count mismatch")
    if intent["approved_count"] != sum(item["decision"] == "approved" for item in intent["decisions"]):
        raise ValueError("promotion human intent approved count mismatch")
    if intent["rejected_count"] != sum(item["decision"] == "rejected" for item in intent["decisions"]):
        raise ValueError("promotion human intent rejected count mismatch")
    approval = {
        "schema_version": "research-lesson-promotion-approval-v1",
        "approval_id": f"lesson-promotion-approval-{intent['intent_fingerprint'][:16]}",
        "reviewer_type": intent["reviewer_type"],
        "reviewer_id": intent["reviewer_id"],
        "statement": intent["statement"],
        "decided_at": intent["decided_at"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "decisions": intent["decisions"],
        "approved_count": intent["approved_count"],
        "rejected_count": intent["rejected_count"],
        "automatic_lesson_promotion_authorized": False,
        "trading_execution_authorized": False,
    }
    approval["approval_fingerprint"] = knowledge.semantic_fingerprint(approval, "approval_fingerprint")
    _validate(repo, APPROVAL_SCHEMA, approval)
    return approval


def build_events(repo: Path, packet: dict[str, Any], approval: dict[str, Any]) -> list[dict[str, Any]]:
    validator = jsonschema.Draft202012Validator(load_document(repo / EVENT_SCHEMA))
    events = []
    for decision in approval["decisions"]:
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


def _validate_current_snapshot(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    context = load_document(repo / KNOWLEDGE_ROOT / "current-context.json")
    manifest = load_document(repo / KNOWLEDGE_ROOT / "manifest.json")
    if knowledge.semantic_fingerprint(context, "context_fingerprint") != context["context_fingerprint"]:
        raise ValueError("current knowledge context fingerprint mismatch")
    if knowledge.semantic_fingerprint(manifest, "manifest_fingerprint") != manifest["manifest_fingerprint"]:
        raise ValueError("current knowledge manifest fingerprint mismatch")
    if manifest["knowledge_snapshot_fingerprint"] != context["knowledge_snapshot_fingerprint"]:
        raise ValueError("current knowledge snapshot identity mismatch")
    if sha256_file(repo / manifest["context_path"]) != manifest["context_sha256"]:
        raise ValueError("current knowledge context hash mismatch")
    for asset in manifest["assets"]:
        if sha256_file(repo / asset["path"]) != asset["sha256"]:
            raise ValueError("current knowledge asset hash mismatch")
    return context, manifest


def build_target_snapshot(
    repo: Path,
    packet: dict[str, Any],
    candidates: list[dict[str, Any]],
    approval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], set[str]]:
    current, current_manifest = _validate_current_snapshot(repo)
    if current["knowledge_snapshot_fingerprint"] != packet["knowledge_snapshot_fingerprint"]:
        raise ValueError("promotion packet is stale against the formal knowledge snapshot")
    candidate_by_id = {item["candidate_id"]: item for item in candidates}
    approved = [candidate_by_id[item["candidate_id"]] for item in approval["decisions"] if item["decision"] == "approved"]
    superseded = {lesson_id for item in approved for lesson_id in item["supersedes_lesson_ids"]}
    current_by_id = {item["lesson_id"]: item for item in current["lessons"]}
    if any(item not in current_by_id for item in superseded):
        raise ValueError("promotion replacement target is not in the formal catalog")
    target_by_id = {key: value for key, value in current_by_id.items() if key not in superseded}
    for candidate in approved:
        card = candidate["proposed_card"]
        if card["lesson_id"] in target_by_id:
            raise ValueError("approved promotion collides with an unreplaced formal lesson")
        target_by_id[card["lesson_id"]] = card
    lessons = [target_by_id[key] for key in sorted(target_by_id)]
    knowledge.validate_assets(repo, current["sources"], current["patterns"], lessons)
    asset_payloads: dict[str, dict[str, Any]] = {}
    assets = []
    current_assets = {item["path"]: item for item in current_manifest["assets"]}
    for kind, items, id_field, folder in (
        ("source", current["sources"], "project_id", "sources"),
        ("pattern", current["patterns"], "pattern_id", "patterns"),
        ("lesson", lessons, "lesson_id", "lessons"),
    ):
        for item in items:
            relative = (KNOWLEDGE_ROOT / folder / f"{item[id_field]}.json").as_posix()
            current_asset = current_assets.get(relative)
            current_path = repo / relative
            if current_asset is not None and current_path.is_file() and load_document(current_path) == item:
                asset_hash = current_asset["sha256"]
            else:
                asset_payloads[relative] = item
                asset_hash = _sha256(_json_bytes(item))
            assets.append({"kind": kind, "path": relative, "sha256": asset_hash})
    assets.sort(key=lambda item: item["path"])
    snapshot_fingerprint = fingerprint({"assets": assets})
    target_context = {
        **{key: value for key, value in current.items() if key not in {"knowledge_snapshot_fingerprint", "lessons", "context_fingerprint"}},
        "knowledge_snapshot_fingerprint": snapshot_fingerprint,
        "lessons": lessons,
    }
    target_context["context_fingerprint"] = knowledge.semantic_fingerprint(target_context, "context_fingerprint")
    context_path = (KNOWLEDGE_ROOT / "current-context.json").as_posix()
    target_manifest = {
        **{key: value for key, value in current_manifest.items() if key not in {"generated_at", "knowledge_snapshot_fingerprint", "counts", "assets", "context_sha256", "manifest_fingerprint"}},
        "generated_at": approval["decided_at"],
        "knowledge_snapshot_fingerprint": snapshot_fingerprint,
        "counts": {"sources": len(current["sources"]), "patterns": len(current["patterns"]), "lessons": len(lessons)},
        "assets": assets,
        "context_sha256": _sha256(_json_bytes(target_context)),
    }
    target_manifest["manifest_fingerprint"] = knowledge.semantic_fingerprint(target_manifest, "manifest_fingerprint")
    asset_payloads[context_path] = target_context
    asset_payloads[(KNOWLEDGE_ROOT / "manifest.json").as_posix()] = target_manifest
    return target_context, target_manifest, asset_payloads, superseded


def resolve_target_snapshot(
    repo: Path,
    packet: dict[str, Any],
    candidates: list[dict[str, Any]],
    approval: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], set[str], bool]:
    current, manifest = _validate_current_snapshot(repo)
    if current["knowledge_snapshot_fingerprint"] == packet["knowledge_snapshot_fingerprint"]:
        context, target_manifest, payloads, superseded = build_target_snapshot(repo, packet, candidates, approval)
        return context, target_manifest, payloads, superseded, False
    decisions = {item["candidate_id"]: item["decision"] for item in approval["decisions"]}
    approved = [item for item in candidates if decisions[item["candidate_id"]] == "approved"]
    current_by_id = {item["lesson_id"]: item for item in current["lessons"]}
    for candidate in approved:
        card = candidate["proposed_card"]
        if current_by_id.get(card["lesson_id"]) != card:
            raise ValueError("formal knowledge snapshot drifted from the approved promotion")
        if any(item in current_by_id and item != card["lesson_id"] for item in candidate["supersedes_lesson_ids"]):
            raise ValueError("superseded lesson remains active after promotion")
    superseded = {lesson_id for item in approved for lesson_id in item["supersedes_lesson_ids"]}
    return current, manifest, {}, superseded, True


def apply_registry_state(
    connection: Any,
    candidates: list[dict[str, Any]],
    approval: dict[str, Any],
    events: list[dict[str, Any]],
    target_context: dict[str, Any],
    superseded: set[str],
) -> None:
    decision_by_id = {item["candidate_id"]: item["decision"] for item in approval["decisions"]}
    event_by_target = {event["target_id"]: event for event in events}
    for candidate in candidates:
        event = event_by_target[candidate["candidate_id"]]
        payload_json = json.dumps(candidate, sort_keys=True)
        existing = connection.execute(
            "SELECT candidate_fingerprint,payload_json,status FROM research_lesson_curation_candidates WHERE candidate_id=?",
            (candidate["candidate_id"],),
        ).fetchone()
        target_status = "promoted" if decision_by_id[candidate["candidate_id"]] == "approved" else "rejected"
        if existing is None:
            connection.execute(
                "INSERT INTO research_lesson_curation_candidates(candidate_id,proposed_lesson_id,candidate_fingerprint,status,source_feedback_ids_json,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
                (candidate["candidate_id"], candidate["proposed_card"]["lesson_id"], candidate["candidate_fingerprint"], target_status, json.dumps(candidate["source_feedback_ids"], sort_keys=True), payload_json, approval["decided_at"]),
            )
        elif existing["candidate_fingerprint"] != candidate["candidate_fingerprint"] or existing["payload_json"] != payload_json or existing["status"] != target_status:
            raise ValueError("promotion Registry candidate conflict")
        event_json = json.dumps(event, sort_keys=True)
        review = connection.execute(
            "SELECT payload_json FROM research_knowledge_review_events WHERE review_type='lesson_promotion' AND target_id=?",
            (candidate["candidate_id"],),
        ).fetchone()
        if review is None:
            connection.execute(
                "INSERT INTO research_knowledge_review_events(review_event_id,review_type,target_id,decision,reviewer_id,source_packet_fingerprint,payload_json,decided_at) VALUES(?,?,?,?,?,?,?,?)",
                (event["review_event_id"], event["review_type"], event["target_id"], event["decision"], event["reviewer_id"], event["source_packet_fingerprint"], event_json, event["decided_at"]),
            )
        elif review["payload_json"] != event_json:
            raise ValueError("promotion Registry event conflict")
    for candidate in candidates:
        if decision_by_id[candidate["candidate_id"]] != "approved":
            continue
        replacement = candidate["proposed_card"]["lesson_id"]
        for lesson_id in candidate["supersedes_lesson_ids"]:
            connection.execute(
                "UPDATE research_knowledge_lifecycle SET lifecycle_status='superseded',superseded_by=?,reason=?,updated_at=? WHERE item_type='lesson' AND item_id=? AND lifecycle_status IN ('active','superseded')",
                (replacement, f"approved_promotion:{approval['approval_id']}", approval["decided_at"], lesson_id),
            )
    connection.execute("DELETE FROM open_source_knowledge_lineage WHERE target_type='research_lesson'")
    connection.execute("DELETE FROM open_source_research_lessons")
    for lesson in target_context["lessons"]:
        connection.execute(
            "INSERT INTO open_source_research_lessons(lesson_id,lesson_fingerprint,outcome,mechanism_keys_json,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (lesson["lesson_id"], lesson["lesson_fingerprint"], lesson["outcome"], json.dumps(lesson["mechanism_keys"], sort_keys=True), json.dumps(lesson, sort_keys=True), approval["decided_at"]),
        )
        for evidence in lesson["evidence_paths"]:
            lineage_id = fingerprint({"evidence": evidence, "lesson": lesson["lesson_id"]})
            connection.execute(
                "INSERT INTO open_source_knowledge_lineage(lineage_id,source_type,source_id,relation,target_type,target_id,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (lineage_id, "internal_evidence", evidence, "supports", "research_lesson", lesson["lesson_id"], "{}", approval["decided_at"]),
            )
        item_key = f"lesson:{lesson['lesson_id']}@{lesson['lesson_fingerprint'][:16]}"
        connection.execute(
            "INSERT OR REPLACE INTO research_knowledge_lifecycle(item_key,item_type,item_id,snapshot_fingerprint,lifecycle_status,superseded_by,reason,payload_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (item_key, "lesson", lesson["lesson_id"], lesson["lesson_fingerprint"], "active", None, f"approved_promotion:{approval['approval_id']}", json.dumps(lesson, sort_keys=True), approval["decided_at"]),
        )


def _publish_snapshot(repo: Path, payloads: dict[str, dict[str, Any]], target_context: dict[str, Any]) -> Callable[[], None]:
    current_lesson_dir = repo / KNOWLEDGE_ROOT / "lessons"
    target_lesson_paths = {
        repo / KNOWLEDGE_ROOT / "lessons" / f"{item['lesson_id']}.json"
        for item in target_context["lessons"]
    }
    stale = set(current_lesson_dir.glob("*.json")) - target_lesson_paths
    changed_paths = [repo / path for path in payloads if "/lessons/" in path or path.endswith("current-context.json") or path.endswith("manifest.json")]
    affected = set(changed_paths) | stale
    backups = {path: path.read_bytes() if path.exists() else None for path in affected}

    def restore() -> None:
        for path, content in backups.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

    try:
        for path in stale:
            path.unlink()
        for relative, payload in payloads.items():
            if "/lessons/" in relative or relative.endswith("current-context.json") or relative.endswith("manifest.json"):
                _write_canonical_json(repo / relative, payload)
        manifest = payloads[(KNOWLEDGE_ROOT / "manifest.json").as_posix()]
        if load_document(repo / KNOWLEDGE_ROOT / "current-context.json") != target_context:
            raise ValueError("published knowledge context mismatch")
        for asset in manifest["assets"]:
            actual_sha256 = sha256_file(repo / asset["path"])
            if actual_sha256 != asset["sha256"]:
                raise ValueError(
                    f"published knowledge asset mismatch: {asset['path']} "
                    f"expected={asset['sha256']} actual={actual_sha256}"
                )
    except Exception:
        restore()
        raise
    return restore


def build_effective_research_state(
    repo: Path,
    handoff: dict[str, Any],
    packet: dict[str, Any],
    approval: dict[str, Any],
) -> dict[str, Any]:
    state = copy.deepcopy(load_document(repo / CURRENT_STATE_JSON))
    knowledge_summary = knowledge.knowledge_state_summary(repo)
    batch_root = (repo / handoff["planned_promotion_review_packet_path"]).parent
    knowledge_summary["maintenance"].update({
        "lesson_curation": (
            f"promotion_completed_{approval['approved_count']}_approved_"
            f"{approval['rejected_count']}_rejected"
        ),
        "promotion_review_packet": handoff["planned_promotion_review_packet_path"],
        "last_promotion_batch": {
            "status": "completed",
            "approved": approval["approved_count"],
            "rejected": approval["rejected_count"],
            "archive": batch_root.relative_to(repo).as_posix(),
            "automatic_application_authorized": False,
        },
    })
    if knowledge_summary["knowledge_snapshot_fingerprint"] == packet["knowledge_snapshot_fingerprint"] and approval["approved_count"]:
        raise ValueError("approved promotion did not advance the formal knowledge snapshot")
    state["generated_at"] = approval["decided_at"]
    state["open_source_knowledge"] = knowledge_summary
    identity = {
        key: value
        for key, value in state.items()
        if key not in {"generated_at", "snapshot_id", "state_fingerprint"}
    }
    state["state_fingerprint"] = fingerprint(identity)
    state["snapshot_id"] = f"research-state-{state['state_fingerprint'][:16]}"
    return state


def _publish_transaction_artifacts(
    json_payloads: dict[Path, dict[str, Any]],
    byte_payloads: dict[Path, bytes],
    immutable_paths: set[Path],
) -> Callable[[], None]:
    affected = set(json_payloads) | set(byte_payloads)
    backups = {path: path.read_bytes() if path.exists() else None for path in affected}

    def restore() -> None:
        for path, content in backups.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

    try:
        for path, payload in json_payloads.items():
            if path in immutable_paths and path.exists():
                if load_document(path) != payload:
                    raise ValueError(f"immutable promotion artifact conflict: {path}")
                continue
            _write_canonical_json(path, payload)
        for path, payload in byte_payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        for path, payload in json_payloads.items():
            if load_document(path) != payload:
                raise ValueError(f"published derived promotion artifact mismatch: {path}")
        for path, payload in byte_payloads.items():
            if path.read_bytes() != payload:
                raise ValueError(f"published derived promotion bytes mismatch: {path}")
    except Exception:
        restore()
        raise
    return restore


def register_effective_research_state(
    connection: Any,
    state: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    payload_json = json.dumps(state, sort_keys=True)
    existing = connection.execute(
        "SELECT fingerprint,payload_json FROM research_state_snapshots WHERE snapshot_id=?",
        (state["snapshot_id"],),
    ).fetchone()
    if existing is None:
        connection.execute(
            "INSERT INTO research_state_snapshots(snapshot_id,fingerprint,git_head,status,payload_json,created_at) VALUES(?,?,?,?,?,?)",
            (
                state["snapshot_id"],
                state["state_fingerprint"],
                state["git"]["head"],
                "generated_after_knowledge_promotion",
                payload_json,
                approval["decided_at"],
            ),
        )
    elif existing["fingerprint"] != state["state_fingerprint"] or existing["payload_json"] != payload_json:
        raise ValueError("promotion research state snapshot conflict")


def merge_effective_state_snapshots(
    base_payload: dict[str, Any],
    registry_payload: dict[str, Any],
) -> dict[str, Any]:
    base_rows = base_payload["tables"].get("research_state_snapshots", [])
    registry_rows = registry_payload["tables"].get("research_state_snapshots", [])
    rows = {row["snapshot_id"]: row for row in base_rows}
    rows.update({row["snapshot_id"]: row for row in registry_rows})
    merged_rows = [rows[key] for key in sorted(rows)]
    base_payload["tables"]["research_state_snapshots"] = merged_rows
    base_payload["counts"]["research_state_snapshots"] = len(merged_rows)
    return base_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--registry-export", default="research/director/registry-records.json")
    parser.add_argument("--intent")
    parser.add_argument("--human-statement")
    parser.add_argument("--reviewer-id", default="workspace_user")
    parser.add_argument("--decided-at")
    parser.add_argument("--approve-all", action="store_true")
    parser.add_argument("--approve-candidate", action="append", default=[])
    parser.add_argument("--reject-candidate", action="append", default=[])
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    registry = Path(args.registry)
    if not registry.is_absolute():
        registry = repo / registry
    handoff, packet, candidates = load_promotion_basis(repo, args.batch_id)
    intent_path = repo / handoff["planned_promotion_human_intent_path"]
    if args.intent:
        if args.human_statement or args.decided_at or args.approve_all or args.approve_candidate or args.reject_candidate:
            raise ValueError("provide either an existing promotion intent or explicit human decision fields")
        supplied = Path(args.intent)
        if not supplied.is_absolute():
            supplied = repo / supplied
        if supplied.resolve() != intent_path.resolve():
            raise ValueError("promotion intent path is not batch-bound")
        intent = load_document(supplied)
    else:
        if not args.human_statement or not args.decided_at:
            raise ValueError("explicit human promotion statement and decision time are required")
        candidate_ids = {item["candidate_id"] for item in candidates}
        if args.approve_all:
            if args.approve_candidate or args.reject_candidate:
                raise ValueError("approve-all cannot be combined with per-candidate decisions")
            decisions = {item: "approved" for item in candidate_ids}
        else:
            if set(args.approve_candidate) & set(args.reject_candidate):
                raise ValueError("candidate cannot be both approved and rejected")
            decisions = {item: "approved" for item in args.approve_candidate}
            decisions.update({item: "rejected" for item in args.reject_candidate})
        intent = build_human_intent(repo, args.batch_id, packet, candidates, args.reviewer_id, args.human_statement, args.decided_at, decisions)
    approval = build_approval(repo, packet, candidates, intent)
    events = build_events(repo, packet, approval)
    target_context, target_manifest, payloads, superseded, snapshot_already_published = resolve_target_snapshot(
        repo, packet, candidates, approval
    )
    archive_payloads = {
        intent_path: intent,
        repo / handoff["planned_promotion_approval_path"]: approval,
        repo / handoff["planned_promotion_events_path"]: {"events": events, "execution_authorized": False},
        repo / handoff["planned_published_manifest_path"]: target_manifest,
    }
    for path, payload in archive_payloads.items():
        if path.exists() and load_document(path) != payload:
            raise ValueError(f"immutable promotion artifact conflict: {path}")
    connection = open_director_registry(registry)
    restores: list[Callable[[], None]] = []
    evaluation: dict[str, Any] | None = None
    health: dict[str, Any] | None = None
    try:
        connection.execute("BEGIN IMMEDIATE")
        apply_registry_state(connection, candidates, approval, events, target_context, superseded)
        if not snapshot_already_published:
            restores.append(_publish_snapshot(repo, payloads, target_context))
        state = build_effective_research_state(repo, handoff, packet, approval)
        evaluation = maintenance.evaluate_retrieval(repo, state)
        if evaluation["status"] != "passed":
            raise ValueError("promoted knowledge snapshot failed retrieval recertification")
        register_effective_research_state(connection, state, approval)
        full_registry_payload = export_director_registry.export_connection(connection)
        registry_payload = export_director_registry.merge_knowledge_tables(
            load_document(repo / args.registry_export),
            full_registry_payload,
        )
        registry_payload = merge_effective_state_snapshots(
            registry_payload, full_registry_payload
        )
        health = maintenance.build_health(
            repo,
            registry_payload,
            load_document(repo / SOURCE_REFRESH_REPORT),
            evaluation,
            approval["decided_at"],
        )
        if health["status"] == "failed":
            raise ValueError("promoted knowledge snapshot failed learning-loop health recertification")
        export_path = repo / args.registry_export
        json_payloads = {
            repo / CURRENT_STATE_JSON: state,
            repo / RETRIEVAL_EVALUATION: evaluation,
            repo / LEARNING_LOOP_HEALTH: health,
            export_path: registry_payload,
            **archive_payloads,
        }
        state_markdown = build_current_research_state.markdown(state).encode("utf-8")
        restores.append(_publish_transaction_artifacts(
            json_payloads,
            {repo / CURRENT_STATE_MD: state_markdown},
            set(archive_payloads),
        ))
        connection.commit()
    except Exception:
        connection.rollback()
        for restore in reversed(restores):
            restore()
        raise
    finally:
        connection.close()
    print(json.dumps({
        "status": "human_approved_lesson_promotion_applied",
        "batch_id": args.batch_id,
        "approved": approval["approved_count"],
        "rejected": approval["rejected_count"],
        "knowledge_snapshot_fingerprint": target_manifest["knowledge_snapshot_fingerprint"],
        "formal_lesson_count": target_manifest["counts"]["lessons"],
        "retrieval_recertification": evaluation["status"],
        "learning_loop_health": health["status"],
        "knowledge_broker_ready": True,
        "strategy_mutation_authorized": False,
        "trading_execution_authorized": False,
    }, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
