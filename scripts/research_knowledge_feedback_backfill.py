#!/usr/bin/env python3
"""Compile a non-executing review packet for legacy descriptive feedback registration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

import export_director_registry
import open_source_knowledge as knowledge
import research_knowledge_maintenance
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
HEALTH_PATH = Path("reports/audits/open-source-learning-v1/learning-loop-health.json")
REGISTRY_EXPORT_PATH = Path("research/director/registry-records.json")
SCHEMA_PATH = Path("research/knowledge/schemas/knowledge-result-feedback-backfill-packet.schema.json")
INTENT_SCHEMA_PATH = Path("research/knowledge/schemas/knowledge-result-feedback-backfill-intent.schema.json")
APPROVAL_SCHEMA_PATH = Path("research/knowledge/schemas/knowledge-result-feedback-backfill-approval.schema.json")
OUTPUT_ROOT = Path("reports/audits/open-source-learning-v1/result-feedback-backfill")


def _inside(repo: Path, relative: str) -> Path:
    if not relative or "\\" in relative or Path(relative).is_absolute():
        raise ValueError("backfill evidence path is not canonical repo-relative")
    target = (repo / relative).resolve(strict=True)
    try:
        target.relative_to(repo)
    except ValueError as exc:
        raise ValueError("backfill evidence path escapes repository") from exc
    return target


def _proposal_index(registry_export: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    result = {}
    for row in registry_export["tables"].get("director_proposals", []):
        proposal_id = str(row["proposal_id"])
        if proposal_id in result:
            raise ValueError("duplicate Director proposal identity")
        payload = json.loads(row["payload_json"])
        if payload.get("semantic_fingerprint") != row["semantic_fingerprint"]:
            raise ValueError("Director proposal semantic fingerprint mismatch")
        result[proposal_id] = (row, payload)
    return result


def _handoff_index(registry_export: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for row in registry_export["tables"].get("research_discovery_handoffs", []):
        if row["run_id"] in result:
            raise ValueError("duplicate Discovery handoff identity")
        payload = json.loads(row["payload_json"])
        if payload.get("handoff_fingerprint") != row["handoff_fingerprint"]:
            raise ValueError("Discovery handoff fingerprint mismatch")
        result[str(row["run_id"])] = row
    return result


def _analysis_attestation(analysis: dict[str, Any]) -> tuple[str, str, dict[str, int | bool]]:
    schema = analysis.get("schema_version")
    boundaries: dict[str, int | bool] = {
        "development_only": True,
        "network_accesses": 0,
        "backtests": 0,
        "signals_or_trades_generated": 0,
        "candidates_created": 0,
        "strategy_changes": 0,
        "validation_accesses": 0,
        "holdout_accesses": 0,
        "promotions": 0,
    }
    if schema == "additional-pair-manifest-inventory-analysis-v1":
        scope = analysis.get("boundary_attestation") or {}
        result = analysis.get("result") or {}
        valid = (
            scope.get("network_accesses") == 0
            and scope.get("market_data_downloads") == 0
            and scope.get("backtest_calls") == 0
            and scope.get("candidate_created") is False
            and scope.get("validation_accesses") == 0
            and scope.get("holdout_accesses") == 0
            and scope.get("strategy_modified") is False
            and result.get("status") == "stopped"
            and result.get("reason_code") == "insufficient_frozen_additional_pair_manifests"
        )
        completed_at = analysis.get("executed_at")
        result_code = "stopped_insufficient_frozen_additional_pair_manifests"
    elif schema == "discovery-cross-pair-descriptive-analysis-v1":
        scope = analysis.get("execution_scope") or {}
        valid = (
            scope.get("development_only") is True
            and scope.get("network_accessed") is False
            and scope.get("validation_accesses") == 0
            and scope.get("holdout_accesses") == 0
            and scope.get("backtests") == 0
            and scope.get("signals_or_trades_generated") == 0
            and scope.get("candidates_created") == 0
            and scope.get("strategy_changes") == 0
            and scope.get("promotions") == 0
            and (analysis.get("source_integrity") or {}).get("all_ok") is True
            and (analysis.get("attestation") or {}).get("prohibited_activities_performed") is False
        )
        completed_at = analysis.get("generated_at")
        result_code = "descriptive_distribution_profile_completed"
    else:
        raise ValueError("legacy descriptive analysis schema is not allowlisted")
    if not valid or not isinstance(completed_at, str) or not completed_at:
        raise ValueError("legacy descriptive analysis boundary attestation failed")
    return result_code, completed_at, boundaries


def result_payload_from_item(item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "run_id": item["run_id"],
        "proposal_id": item["proposal_id"],
        "proposal_semantic_fingerprint": item["proposal_semantic_fingerprint"],
        "evidence_artifacts": item["evidence_artifacts"],
        "registration_mode": item["registration_mode"],
        "result_code": item["result_code"],
        "outcome_class": item["outcome_class"],
        "completed_at": item["completed_at"],
        "governance_boundaries": item["governance_boundaries"],
        "automatic_lesson_promotion_authorized": False,
        "candidate_creation_authorized": False,
        "execution_authorized": False,
    }
    if fingerprint(payload) != item["result_payload_fingerprint"]:
        raise ValueError("backfill result payload fingerprint mismatch")
    return payload


def build_packet(
    repo: Path,
    health: dict[str, Any],
    registry_export: dict[str, Any],
) -> dict[str, Any]:
    if knowledge.semantic_fingerprint(health, "health_fingerprint") != health.get("health_fingerprint"):
        raise ValueError("learning-loop health fingerprint mismatch")
    if registry_export.get("integrity") != "ok":
        raise ValueError("Registry export integrity is not ok")
    chain = (health.get("knowledge_impact") or {}).get("result_feedback_chain") or {}
    legacy = [
        item for item in chain.get("runs", [])
        if item.get("classification") == "analysis_completed_feedback_unregistered"
    ]
    if len(legacy) != chain.get("legacy_unregistered_run_count"):
        raise ValueError("health legacy feedback count does not match its run list")
    if not legacy:
        return {
            "status": "idle",
            "pending_count": 0,
            "packet_modified": False,
            "execution_authorized": False,
        }
    proposals = _proposal_index(registry_export)
    handoffs = _handoff_index(registry_export)
    items = []
    for ordinal, source in enumerate(sorted(legacy, key=lambda item: item["run_id"]), 1):
        if source.get("issues") or source.get("proposal_knowledge_binding_verified") is not True:
            raise ValueError("legacy result chain is not cleanly bound")
        run_id = str(source["run_id"])
        proposal_id = str(source["proposal_id"])
        proposal_record = proposals.get(proposal_id)
        handoff = handoffs.get(run_id)
        if proposal_record is None or handoff is None:
            raise ValueError("legacy result proposal or handoff is missing")
        proposal_row, proposal = proposal_record
        if proposal.get("discovery_handoff_fingerprint") != handoff["handoff_fingerprint"]:
            raise ValueError("legacy result proposal-to-handoff binding mismatch")
        expected_paths = [
            f"research/analysis/{proposal_id}/analysis.json",
            f"reports/audits/{proposal_id}/report.md",
        ]
        if proposal.get("required_artifacts") != expected_paths or proposal.get("allowed_changes") != expected_paths:
            raise ValueError("legacy result exact artifact contract mismatch")
        evidence = []
        for relative in expected_paths:
            target = _inside(repo, relative)
            evidence.append({"path": relative, "sha256": sha256_file(target)})
        if evidence != [
            {"path": item["path"], "sha256": item["sha256"]}
            for item in source.get("artifacts", [])
        ]:
            raise ValueError("legacy result artifact fingerprint drift")
        analysis = load_document(_inside(repo, expected_paths[0]))
        if analysis.get("proposal_id") != proposal_id:
            raise ValueError("legacy analysis proposal identity mismatch")
        result_code, completed_at, boundaries = _analysis_attestation(analysis)
        identity = {
            "run_id": run_id,
            "proposal_id": proposal_id,
            "proposal_semantic_fingerprint": proposal_row["semantic_fingerprint"],
            "evidence_artifacts": evidence,
            "registration_mode": "historical_manual_descriptive_analysis",
        }
        suffix = fingerprint(identity)[:16]
        result_payload = {
            **identity,
            "result_code": result_code,
            "outcome_class": "inconclusive",
            "completed_at": completed_at,
            "governance_boundaries": boundaries,
            "automatic_lesson_promotion_authorized": False,
            "candidate_creation_authorized": False,
            "execution_authorized": False,
        }
        item = {
            "ordinal": ordinal,
            "run_id": run_id,
            "selected_idea_id": str(source["selected_idea_id"]),
            "proposal_id": proposal_id,
            "proposal_semantic_fingerprint": str(proposal_row["semantic_fingerprint"]),
            "discovery_handoff_fingerprint": str(handoff["handoff_fingerprint"]),
            "analysis_schema_version": str(analysis["schema_version"]),
            "completed_at": completed_at,
            "result_code": result_code,
            "outcome_class": "inconclusive",
            "registration_mode": "historical_manual_descriptive_analysis",
            "evidence_artifacts": evidence,
            "proposed_result_id": f"historical-descriptive-result-{suffix}",
            "proposed_feedback_id": f"feedback-historical-descriptive-result-{suffix}",
            "proposed_feedback_review_status": "pending_human_review",
            "result_payload_fingerprint": fingerprint(result_payload),
            "governance_boundaries": boundaries,
        }
        item["item_fingerprint"] = knowledge.semantic_fingerprint(item, "item_fingerprint")
        items.append(item)
    packet_id = f"knowledge-result-feedback-backfill-{fingerprint({'health': health['health_fingerprint'], 'items': [item['item_fingerprint'] for item in items]})[:16]}"
    packet = {
        "schema_version": "knowledge-result-feedback-backfill-packet-v1",
        "packet_id": packet_id,
        "source_health_fingerprint": health["health_fingerprint"],
        "knowledge_snapshot_fingerprint": health["knowledge_impact"]["knowledge_snapshot_fingerprint"],
        "registry_integrity": "ok",
        "item_count": len(items),
        "items": items,
        "decision_contract": {
            "allowed_decisions": ["approved", "rejected"],
            "approve_all_statement_zh": (
                f"批准 {packet_id} 中 {len(items)} 项历史描述结果按原始 SHA256 原子补登记结果与 pending_human_review 反馈；"
                "不授权 lesson 晋升、Candidate、回测、策略修改、Validation/Holdout 或任何执行。"
            ),
            "partial_decision_instruction_zh": (
                "如需混合决定，请分别列出批准与拒绝的 proposed_feedback_id；未明确列出的项目不得登记。"
            ),
            "approved_result": "register_result_and_pending_human_review_feedback_atomically",
            "rejected_result": "leave_historical_artifacts_unregistered",
        },
        "human_decision_required": True,
        "automatic_application_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "candidate_creation_authorized": False,
        "execution_authorized": False,
    }
    packet["packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "packet_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / SCHEMA_PATH)).validate(packet)
    return packet


def _validate_packet(repo: Path, packet: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(load_document(repo / SCHEMA_PATH)).validate(packet)
    if knowledge.semantic_fingerprint(packet, "packet_fingerprint") != packet["packet_fingerprint"]:
        raise ValueError("backfill packet fingerprint mismatch")
    for item in packet["items"]:
        if knowledge.semantic_fingerprint(item, "item_fingerprint") != item["item_fingerprint"]:
            raise ValueError("backfill item fingerprint mismatch")
        result_payload_from_item(item)
        for artifact in item["evidence_artifacts"]:
            if sha256_file(_inside(repo, artifact["path"])) != artifact["sha256"]:
                raise ValueError("backfill evidence artifact fingerprint drift")


def build_human_intent(
    repo: Path,
    packet: dict[str, Any],
    statement: str,
    decided_at: str,
    reviewer_id: str = "workspace_user",
) -> dict[str, Any]:
    _validate_packet(repo, packet)
    if statement != packet["decision_contract"]["approve_all_statement_zh"]:
        raise ValueError("human backfill approval statement does not exactly match the packet")
    approved_feedback_ids = [item["proposed_feedback_id"] for item in packet["items"]]
    basis = {
        "packet_id": packet["packet_id"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "reviewer_type": "human_user",
        "reviewer_id": reviewer_id,
        "statement": statement,
        "decided_at": decided_at,
        "approved_feedback_ids": approved_feedback_ids,
        "approved_count": len(approved_feedback_ids),
        "rejected_count": 0,
        "result_and_feedback_registration_authorized": True,
        "automatic_lesson_promotion_authorized": False,
        "candidate_creation_authorized": False,
        "execution_authorized": False,
    }
    intent = {
        "schema_version": "knowledge-result-feedback-backfill-intent-v1",
        "intent_id": f"knowledge-result-feedback-backfill-intent-{fingerprint(basis)[:16]}",
        **basis,
    }
    intent["intent_fingerprint"] = knowledge.semantic_fingerprint(intent, "intent_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / INTENT_SCHEMA_PATH)).validate(intent)
    return intent


def build_approval(repo: Path, packet: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    _validate_packet(repo, packet)
    jsonschema.Draft202012Validator(load_document(repo / INTENT_SCHEMA_PATH)).validate(intent)
    if knowledge.semantic_fingerprint(intent, "intent_fingerprint") != intent["intent_fingerprint"]:
        raise ValueError("backfill intent fingerprint mismatch")
    if intent["packet_id"] != packet["packet_id"] or intent["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise ValueError("backfill intent packet binding mismatch")
    approval = {
        "schema_version": "knowledge-result-feedback-backfill-approval-v1",
        "approval_id": f"knowledge-result-feedback-backfill-approval-{intent['intent_fingerprint'][:16]}",
        "packet_id": packet["packet_id"],
        "packet_fingerprint": packet["packet_fingerprint"],
        "intent_fingerprint": intent["intent_fingerprint"],
        "reviewer_type": intent["reviewer_type"],
        "reviewer_id": intent["reviewer_id"],
        "statement": intent["statement"],
        "decided_at": intent["decided_at"],
        "approved_feedback_ids": intent["approved_feedback_ids"],
        "approved_count": intent["approved_count"],
        "rejected_count": 0,
        "registration_mode": "historical_manual_descriptive_analysis",
        "result_and_feedback_registration_authorized": True,
        "feedback_review_status": "pending_human_review",
        "automatic_feedback_approval_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "candidate_creation_authorized": False,
        "execution_authorized": False,
    }
    approval["approval_fingerprint"] = knowledge.semantic_fingerprint(approval, "approval_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / APPROVAL_SCHEMA_PATH)).validate(approval)
    return approval


def _registration_events(packet: dict[str, Any], approval: dict[str, Any]) -> dict[str, Any]:
    events = []
    for item in packet["items"]:
        event = {
            "event_id": f"knowledge-result-feedback-backfill-event-{fingerprint({'item': item['item_fingerprint'], 'approval': approval['approval_fingerprint']})[:16]}",
            "packet_id": packet["packet_id"],
            "approval_fingerprint": approval["approval_fingerprint"],
            "item_fingerprint": item["item_fingerprint"],
            "result_id": item["proposed_result_id"],
            "feedback_id": item["proposed_feedback_id"],
            "feedback_review_status": "pending_human_review",
            "registration_mode": "historical_manual_descriptive_analysis",
            "execution_authorized": False,
        }
        event["event_fingerprint"] = knowledge.semantic_fingerprint(event, "event_fingerprint")
        events.append(event)
    payload = {
        "schema_version": "knowledge-result-feedback-backfill-events-v1",
        "packet_id": packet["packet_id"],
        "approval_fingerprint": approval["approval_fingerprint"],
        "events": events,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    payload["events_fingerprint"] = knowledge.semantic_fingerprint(payload, "events_fingerprint")
    return payload


def _publish_immutable(path: Path, payload: dict[str, Any]) -> bool:
    if path.exists():
        if load_document(path) != payload:
            raise ValueError(f"immutable backfill approval artifact conflict: {path}")
        return False
    write_json(path, payload)
    return True


def apply_approved_backfill(
    repo: Path,
    registry_path: Path,
    registry_export_path: Path,
    health_path: Path,
    packet: dict[str, Any],
    intent: dict[str, Any],
) -> dict[str, Any]:
    approval = build_approval(repo, packet, intent)
    events = _registration_events(packet, approval)
    batch_root = repo / OUTPUT_ROOT / packet["packet_id"]
    archive = [
        (batch_root / "human-intent.json", intent),
        (batch_root / "approval.json", approval),
        (batch_root / "registration-events.json", events),
    ]
    for path, payload in archive:
        if path.exists() and load_document(path) != payload:
            raise ValueError(f"immutable backfill approval artifact conflict: {path}")
    connection = open_director_registry(registry_path)
    created_paths: list[Path] = []
    export_before = registry_export_path.read_bytes()
    health_before = health_path.read_bytes()
    try:
        connection.execute("BEGIN IMMEDIATE")
        exact_replay = True
        for item in packet["items"]:
            result = connection.execute(
                "SELECT * FROM research_descriptive_execution_results WHERE result_id=?",
                (item["proposed_result_id"],),
            ).fetchone()
            feedback = connection.execute(
                "SELECT * FROM research_lesson_feedback_drafts WHERE feedback_id=?",
                (item["proposed_feedback_id"],),
            ).fetchone()
            if (result is None) != (feedback is None):
                raise ValueError("partial historical backfill registration detected")
            if result is None:
                exact_replay = False
                continue
            payload_json = json.dumps(result_payload_from_item(item), ensure_ascii=False, sort_keys=True)
            expected_result = {
                "result_id": item["proposed_result_id"],
                "job_id": f"historical-manual-{item['proposed_result_id'].rsplit('-', 1)[-1]}",
                "run_id": item["run_id"],
                "proposal_id": item["proposal_id"],
                "result_code": item["result_code"],
                "authorization_fingerprint": approval["approval_fingerprint"],
                "analysis_path": item["evidence_artifacts"][0]["path"],
                "analysis_sha256": item["evidence_artifacts"][0]["sha256"],
                "report_path": item["evidence_artifacts"][1]["path"],
                "report_sha256": item["evidence_artifacts"][1]["sha256"],
                "payload_json": payload_json,
                "completed_at": item["completed_at"],
            }
            expected_feedback = {
                "feedback_id": item["proposed_feedback_id"],
                "run_id": item["run_id"],
                "campaign_id": "historical_manual_descriptive_analysis",
                "proposal_id": item["proposal_id"],
                "result_code": item["result_code"],
                "review_status": "pending_human_review",
                "payload_json": payload_json,
                "created_at": approval["decided_at"],
            }
            if dict(result) != expected_result or dict(feedback) != expected_feedback:
                raise ValueError("historical backfill replay conflict")
        if exact_replay:
            connection.rollback()
            return {
                "status": "historical_feedback_backfill_already_applied",
                "packet_id": packet["packet_id"],
                "registered_results": len(packet["items"]),
                "pending_feedback": len(packet["items"]),
                "registry_modified": False,
                "execution_authorized": False,
            }
        for item in packet["items"]:
            conflicts = connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results WHERE job_id=? OR (run_id=? AND proposal_id=?)",
                (f"historical-manual-{item['proposed_result_id'].rsplit('-', 1)[-1]}", item["run_id"], item["proposal_id"]),
            ).fetchone()[0]
            feedback_conflicts = connection.execute(
                "SELECT COUNT(*) FROM research_lesson_feedback_drafts WHERE run_id=? OR feedback_id=?",
                (item["run_id"], item["proposed_feedback_id"]),
            ).fetchone()[0]
            if conflicts or feedback_conflicts:
                raise ValueError("historical backfill Registry identity conflict")
            payload_json = json.dumps(result_payload_from_item(item), ensure_ascii=False, sort_keys=True)
            connection.execute(
                "INSERT INTO research_descriptive_execution_results(result_id,job_id,run_id,proposal_id,result_code,authorization_fingerprint,analysis_path,analysis_sha256,report_path,report_sha256,payload_json,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item["proposed_result_id"], f"historical-manual-{item['proposed_result_id'].rsplit('-', 1)[-1]}",
                    item["run_id"], item["proposal_id"], item["result_code"], approval["approval_fingerprint"],
                    item["evidence_artifacts"][0]["path"], item["evidence_artifacts"][0]["sha256"],
                    item["evidence_artifacts"][1]["path"], item["evidence_artifacts"][1]["sha256"],
                    payload_json, item["completed_at"],
                ),
            )
            connection.execute(
                "INSERT INTO research_lesson_feedback_drafts(feedback_id,run_id,campaign_id,proposal_id,result_code,review_status,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    item["proposed_feedback_id"], item["run_id"], "historical_manual_descriptive_analysis",
                    item["proposal_id"], item["result_code"], "pending_human_review", payload_json, approval["decided_at"],
                ),
            )
        prospective_export = export_director_registry.export_connection(connection)
        current_health = load_document(health_path)
        prospective_health = research_knowledge_maintenance.build_health(
            repo,
            prospective_export,
            load_document(repo / research_knowledge_maintenance.REPORT_ROOT / "source-refresh-report.json"),
            load_document(repo / research_knowledge_maintenance.REPORT_ROOT / "retrieval-evaluation.json"),
            current_health["checked_at"],
        )
        if prospective_health["knowledge_impact"]["result_feedback_chain"]["broken_chain_run_count"]:
            raise ValueError("prospective historical backfill breaks the result feedback chain")
        for path, payload in archive:
            if _publish_immutable(path, payload):
                created_paths.append(path)
        write_json(registry_export_path, prospective_export)
        write_json(health_path, prospective_health)
        connection.commit()
    except Exception:
        connection.rollback()
        registry_export_path.write_bytes(export_before)
        health_path.write_bytes(health_before)
        for path in reversed(created_paths):
            if path.exists():
                path.unlink()
        raise
    finally:
        connection.close()
    return {
        "status": "historical_feedback_backfill_applied",
        "packet_id": packet["packet_id"],
        "approval_fingerprint": approval["approval_fingerprint"],
        "registered_results": len(packet["items"]),
        "pending_feedback": len(packet["items"]),
        "registry_modified": True,
        "health_status": prospective_health["status"],
        "result_feedback_broken": prospective_health["knowledge_impact"]["result_feedback_chain"]["broken_chain_run_count"],
        "automatic_lesson_promotion_authorized": False,
        "candidate_creation_authorized": False,
        "execution_authorized": False,
    }


def publish_packet(repo: Path, packet: dict[str, Any]) -> tuple[Path, bool]:
    if packet.get("status") == "idle":
        raise ValueError("idle backfill state has no packet to publish")
    path = repo / OUTPUT_ROOT / packet["packet_id"] / "packet.json"
    if path.exists():
        if load_document(path) != packet:
            raise ValueError("immutable backfill review packet conflict")
        return path, False
    write_json(path, packet)
    return path, True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "compile", "apply"), nargs="?", default="status")
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--health", default=str(HEALTH_PATH))
    parser.add_argument("--registry-export", default=str(REGISTRY_EXPORT_PATH))
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--packet-id")
    parser.add_argument("--human-statement")
    parser.add_argument("--decided-at")
    parser.add_argument("--reviewer-id", default="workspace_user")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    if args.command == "apply":
        if not args.packet_id or not args.human_statement:
            raise ValueError("apply requires packet id and exact human statement")
        packet_path = repo / OUTPUT_ROOT / args.packet_id / "packet.json"
        packet = load_document(packet_path)
        intent = build_human_intent(
            repo,
            packet,
            args.human_statement,
            args.decided_at or utc_now(),
            args.reviewer_id,
        )
        result = apply_approved_backfill(
            repo,
            (repo / args.registry).resolve(),
            (repo / args.registry_export).resolve(),
            (repo / args.health).resolve(),
            packet,
            intent,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    packet = build_packet(
        repo,
        load_document(repo / args.health),
        load_document(repo / args.registry_export),
    )
    if packet.get("status") == "idle":
        result = packet
    elif args.command == "status":
        path = repo / OUTPUT_ROOT / packet["packet_id"] / "packet.json"
        result = {
            "status": "awaiting_human_backfill_review" if path.exists() else "backfill_packet_required",
            "packet_id": packet["packet_id"],
            "packet_fingerprint": packet["packet_fingerprint"],
            "pending_count": packet["item_count"],
            "packet_path": path.relative_to(repo).as_posix(),
            "packet_modified": False,
            "decision_request": packet["decision_contract"],
            "execution_authorized": False,
        }
    else:
        path, modified = publish_packet(repo, packet)
        result = {
            "status": "backfill_review_ready" if modified else "awaiting_human_backfill_review",
            "packet_id": packet["packet_id"],
            "packet_fingerprint": packet["packet_fingerprint"],
            "pending_count": packet["item_count"],
            "packet_path": path.relative_to(repo).as_posix(),
            "packet_modified": modified,
            "items": packet["items"],
            "decision_request": packet["decision_contract"],
            "execution_authorized": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
