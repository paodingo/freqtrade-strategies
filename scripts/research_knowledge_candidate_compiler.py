#!/usr/bin/env python3
"""Compile validated lesson drafts into review-only candidates and a promotion packet."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
import research_knowledge_curation_draft as curation
from research_director_common import load_document, sha256_file, write_json


ROOT = Path(__file__).resolve().parents[1]
BATCH_ROOT = Path("reports/audits/open-source-learning-v1/review-batches/aggregated")
CANDIDATE_SCHEMA = Path("research/knowledge/schemas/research-lesson-curation-candidate.schema.json")
PROMOTION_PACKET_SCHEMA = Path("research/knowledge/schemas/research-lesson-promotion-packet.schema.json")


def _validate_archived_base(repo: Path, handoff: dict[str, Any]) -> None:
    context_path = repo / handoff["planned_promotion_base_context_path"]
    manifest_path = repo / handoff["planned_promotion_base_manifest_path"]
    context = load_document(context_path)
    manifest = load_document(manifest_path)
    if knowledge.semantic_fingerprint(context, "context_fingerprint") != context["context_fingerprint"]:
        raise ValueError("promotion compilation base context fingerprint mismatch")
    if knowledge.semantic_fingerprint(manifest, "manifest_fingerprint") != manifest["manifest_fingerprint"]:
        raise ValueError("promotion compilation base manifest fingerprint mismatch")
    if context["knowledge_snapshot_fingerprint"] != manifest["knowledge_snapshot_fingerprint"]:
        raise ValueError("promotion compilation base snapshot identity mismatch")
    if sha256_file(context_path) != manifest["context_sha256"]:
        raise ValueError("promotion compilation base context hash mismatch")


def compile_candidate_artifacts(
    repo: Path,
    handoff: dict[str, Any],
    post_plan: dict[str, Any],
    draft_packet: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    curation.validate_draft_packet(repo, handoff, post_plan, draft_packet)
    candidate_validator = jsonschema.Draft202012Validator(load_document(repo / CANDIDATE_SCHEMA))
    candidates = []
    candidate_refs = []
    candidate_root = Path(handoff["planned_curation_candidate_root"])
    for draft in sorted(draft_packet["drafts"], key=lambda item: item["proposed_card"]["lesson_id"]):
        card = draft["proposed_card"]
        candidate = {
            "schema_version": "research-lesson-curation-candidate-v1",
            "candidate_id": f"lesson-candidate-{card['lesson_id']}",
            "status": "pending_human_promotion_review",
            "source_feedback_ids": draft["source_feedback_ids"],
            "merge_disposition": draft["merge_disposition"],
            "supersedes_lesson_ids": draft["supersedes_lesson_ids"],
            "material_difference_zh": draft["material_difference_zh"],
            "proposed_card": card,
            "automatic_promotion_authorized": False,
        }
        candidate["candidate_fingerprint"] = knowledge.semantic_fingerprint(candidate, "candidate_fingerprint")
        candidate_validator.validate(candidate)
        candidates.append(candidate)
        candidate_refs.append({
            "candidate_id": candidate["candidate_id"],
            "proposed_lesson_id": card["lesson_id"],
            "path": (candidate_root / f"{candidate['candidate_id']}.json").as_posix(),
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "source_feedback_ids": candidate["source_feedback_ids"],
            "supersedes_lesson_ids": candidate["supersedes_lesson_ids"],
        })
    base_context_path = repo / handoff["planned_promotion_base_context_path"]
    context = load_document(
        base_context_path
        if base_context_path.is_file()
        else repo / "research/knowledge/open-source-v1/current-context.json"
    )
    eligible = draft_packet["coverage"]["eligible_feedback_ids"]
    packet = {
        "schema_version": "research-lesson-promotion-packet-v1",
        "packet_id": f"knowledge-lesson-promotion-review-{draft_packet['draft_packet_fingerprint'][:16]}",
        "generated_at": draft_packet["generated_at"],
        "source_review_batch": handoff["batch_id"],
        "knowledge_snapshot_fingerprint": context["knowledge_snapshot_fingerprint"],
        "approved_feedback_count": len(eligible),
        "candidate_count": len(candidates),
        "formal_lesson_count_before": len(context["lessons"]),
        "candidates": candidate_refs,
        "coverage": {
            "approved_feedback_ids": eligible,
            "covered_feedback_ids": draft_packet["coverage"]["covered_feedback_ids"],
            "uncovered_feedback_ids": [],
            "duplicate_feedback_merged": draft_packet["coverage"]["duplicate_feedback_merged"],
        },
        "human_approval_required": True,
        "automatic_promotion_authorized": False,
        "execution_authorized": False,
    }
    packet["packet_fingerprint"] = knowledge.semantic_fingerprint(packet, "packet_fingerprint")
    jsonschema.Draft202012Validator(load_document(repo / PROMOTION_PACKET_SCHEMA)).validate(packet)
    return candidates, packet


def build_promotion_decision_request(
    batch_id: str,
    packet: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    summaries = []
    for ordinal, candidate in enumerate(sorted(candidates, key=lambda item: item["candidate_id"]), start=1):
        card = candidate["proposed_card"]
        summaries.append({
            "ordinal": ordinal,
            "candidate_id": candidate["candidate_id"],
            "candidate_fingerprint": candidate["candidate_fingerprint"],
            "proposed_lesson_id": card["lesson_id"],
            "title_zh": card["title_zh"],
            "outcome": card["outcome"],
            "merge_disposition": candidate["merge_disposition"],
            "supersedes_lesson_ids": candidate["supersedes_lesson_ids"],
            "source_feedback_ids": candidate["source_feedback_ids"],
            "material_difference_zh": candidate["material_difference_zh"],
            "evidence_paths": card["evidence_paths"],
        })
    request = {
        "schema_version": "research-lesson-promotion-decision-request-v1",
        "batch_id": batch_id,
        "packet_fingerprint": packet["packet_fingerprint"],
        "knowledge_snapshot_fingerprint": packet["knowledge_snapshot_fingerprint"],
        "candidate_count": len(summaries),
        "formal_lesson_count_before": packet["formal_lesson_count_before"],
        "candidates": summaries,
        "human_decision_required": True,
        "decision_contract": {
            "allowed_decisions": ["approved", "rejected"],
            "every_candidate_must_be_decided_exactly_once": True,
            "approve_all_statement_zh": f"批准 {batch_id} 按 {len(summaries)} 项通过、0 项拒绝执行知识晋升",
            "partial_decision_instruction_zh": "请明确列出通过和拒绝的 candidate_id；两组必须覆盖全部 Candidate，且不得重复。",
        },
        "authorized_effects": [
            "register_exact_candidates_in_research_registry",
            "record_human_lesson_promotion_review_events",
            "publish_approved_formal_lesson_snapshot",
            "archive_fingerprint_bound_promotion_artifacts",
        ],
        "prohibited_effects": [
            "strategy_mutation",
            "signal_or_trade_generation",
            "backtest",
            "validation_or_holdout_access",
            "automatic_lesson_promotion",
        ],
    }
    request["decision_request_fingerprint"] = knowledge.semantic_fingerprint(
        request, "decision_request_fingerprint"
    )
    return request


def _preflight(repo: Path, handoff: dict[str, Any], candidates: list[dict[str, Any]], packet: dict[str, Any]) -> bool:
    candidate_root = repo / handoff["planned_curation_candidate_root"]
    expected = {
        candidate_root / f"{candidate['candidate_id']}.json": candidate
        for candidate in candidates
    }
    packet_path = repo / handoff["planned_promotion_review_packet_path"]
    expected[packet_path] = packet
    base_context_path = repo / handoff["planned_promotion_base_context_path"]
    base_manifest_path = repo / handoff["planned_promotion_base_manifest_path"]
    if base_context_path.exists() != base_manifest_path.exists():
        raise ValueError("promotion compilation base snapshot is partial")
    if base_context_path.exists():
        _validate_archived_base(repo, handoff)
    expected[base_context_path] = load_document(
        base_context_path if base_context_path.exists() else repo / "research/knowledge/open-source-v1/current-context.json"
    )
    expected[base_manifest_path] = load_document(
        base_manifest_path if base_manifest_path.exists() else repo / "research/knowledge/open-source-v1/manifest.json"
    )
    if candidate_root.exists():
        unexpected = {
            path
            for path in candidate_root.glob("*.json")
            if path not in expected
        }
        if unexpected:
            raise ValueError("curation candidate directory contains unexpected artifacts")
    all_existing = True
    for path, payload in expected.items():
        if path.exists():
            if load_document(path) != payload:
                raise ValueError(f"immutable curation candidate artifact conflict: {path}")
        else:
            all_existing = False
    return not all_existing


def publish_candidate_artifacts(
    repo: Path,
    handoff: dict[str, Any],
    candidates: list[dict[str, Any]],
    packet: dict[str, Any],
) -> bool:
    newly_published = _preflight(repo, handoff, candidates, packet)
    candidate_root = repo / handoff["planned_curation_candidate_root"]
    for candidate in candidates:
        path = candidate_root / f"{candidate['candidate_id']}.json"
        if not path.exists():
            write_json(path, candidate)
    packet_path = repo / handoff["planned_promotion_review_packet_path"]
    if not packet_path.exists():
        write_json(packet_path, packet)
    base_context_path = repo / handoff["planned_promotion_base_context_path"]
    if not base_context_path.exists():
        base_context_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / "research/knowledge/open-source-v1/current-context.json", base_context_path)
    base_manifest_path = repo / handoff["planned_promotion_base_manifest_path"]
    if not base_manifest_path.exists():
        base_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / "research/knowledge/open-source-v1/manifest.json", base_manifest_path)
    _validate_archived_base(repo, handoff)
    return newly_published


def _batch_inputs(repo: Path, batch_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    batch_root = repo / BATCH_ROOT / batch_id
    handoff = load_document(batch_root / "handoff.json")
    post_plan = load_document(batch_root / "post-approval-plan.json")
    draft_packet = load_document(repo / handoff["planned_curation_draft_path"])
    return handoff, post_plan, draft_packet


def pending_batches(repo: Path) -> list[dict[str, Any]]:
    root = repo / BATCH_ROOT
    if not root.exists():
        return []
    pending = []
    for batch_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        draft_path = batch_dir / "curation-draft-packet.json"
        if not draft_path.is_file():
            continue
        handoff, post_plan, draft_packet = _batch_inputs(repo, batch_dir.name)
        candidates, packet = compile_candidate_artifacts(repo, handoff, post_plan, draft_packet)
        if _preflight(repo, handoff, candidates, packet):
            pending.append({
                "batch_id": batch_dir.name,
                "candidate_count": len(candidates),
                "candidate_root": handoff["planned_curation_candidate_root"],
                "promotion_review_packet_path": handoff["planned_promotion_review_packet_path"],
            })
    return pending


def build_compilation_result(
    batch_id: str,
    handoff: dict[str, Any],
    candidates: list[dict[str, Any]],
    packet: dict[str, Any],
    newly_published: bool,
) -> dict[str, Any]:
    result = {
        "status": "promotion_review_ready" if newly_published else "awaiting_human_promotion_review",
        "batch_id": batch_id,
        "candidate_count": len(candidates),
        "candidate_root": handoff["planned_curation_candidate_root"],
        "promotion_review_packet_path": handoff["planned_promotion_review_packet_path"],
        "registry_candidates_created": 0,
        "formal_lessons_modified": 0,
        "automatic_promotion_authorized": False,
        "execution_authorized": False,
    }
    if newly_published:
        result["decision_request"] = build_promotion_decision_request(
            batch_id, packet, candidates
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("status")
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--batch-id", required=True)
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    if args.mode == "status":
        pending = pending_batches(repo)
        result = {"status": "candidate_compilation_required" if pending else "idle", "pending": pending}
    else:
        handoff, post_plan, draft_packet = _batch_inputs(repo, args.batch_id)
        candidates, packet = compile_candidate_artifacts(repo, handoff, post_plan, draft_packet)
        newly_published = publish_candidate_artifacts(repo, handoff, candidates, packet)
        result = build_compilation_result(
            args.batch_id, handoff, candidates, packet, newly_published
        )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
