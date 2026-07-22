#!/usr/bin/env python3
"""Discover and validate non-authoritative lesson curation draft packets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import load_document


ROOT = Path(__file__).resolve().parents[1]
BATCH_ROOT = Path("reports/audits/open-source-learning-v1/review-batches/aggregated")
DRAFT_SCHEMA = Path("research/knowledge/schemas/research-lesson-curation-draft-packet.schema.json")
LESSON_SCHEMA = Path("research/knowledge/schemas/research-lesson-card.schema.json")
HANDOFF_SCHEMA = Path("research/knowledge/schemas/knowledge-review-batch-handoff.schema.json")
POST_PLAN_SCHEMA = Path("research/knowledge/schemas/knowledge-review-post-approval-plan.schema.json")


def _local_evidence(repo: Path, evidence: list[str]) -> None:
    for reference in evidence:
        if reference.startswith(("http://", "https://")):
            raise ValueError("curation draft evidence must be local")
        candidate = (repo / reference).resolve()
        try:
            candidate.relative_to(repo.resolve())
        except ValueError as exc:
            raise ValueError("curation draft evidence escapes the repository") from exc
        if not candidate.is_file():
            raise ValueError("curation draft local evidence is missing")


def _validate_basis(repo: Path, handoff: dict[str, Any], post_plan: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(load_document(repo / HANDOFF_SCHEMA)).validate(handoff)
    jsonschema.Draft202012Validator(load_document(repo / POST_PLAN_SCHEMA)).validate(post_plan)
    if knowledge.semantic_fingerprint(handoff, "handoff_fingerprint") != handoff["handoff_fingerprint"]:
        raise ValueError("curation draft handoff fingerprint mismatch")
    if knowledge.semantic_fingerprint(post_plan, "plan_fingerprint") != post_plan["plan_fingerprint"]:
        raise ValueError("curation draft post-approval plan fingerprint mismatch")
    if post_plan["batch_id"] != handoff["batch_id"] or post_plan["curation_drafting_authorized"] is not True:
        raise ValueError("curation drafting basis is not authorized")


def validate_draft_packet(
    repo: Path,
    handoff: dict[str, Any],
    post_plan: dict[str, Any],
    draft_packet: dict[str, Any],
) -> dict[str, int]:
    _validate_basis(repo, handoff, post_plan)
    jsonschema.Draft202012Validator(load_document(repo / DRAFT_SCHEMA)).validate(draft_packet)
    if knowledge.semantic_fingerprint(draft_packet, "draft_packet_fingerprint") != draft_packet["draft_packet_fingerprint"]:
        raise ValueError("curation draft packet fingerprint mismatch")
    if draft_packet["batch_id"] != handoff["batch_id"]:
        raise ValueError("curation draft batch mismatch")
    if draft_packet["generated_at"] != post_plan["generated_at"]:
        raise ValueError("curation draft must use the stable approval timestamp")
    if draft_packet["post_approval_plan_fingerprint"] != post_plan["plan_fingerprint"]:
        raise ValueError("curation draft post-approval plan mismatch")
    expected_id = f"knowledge-curation-draft-{post_plan['plan_fingerprint'][:16]}"
    if draft_packet["draft_packet_id"] != expected_id:
        raise ValueError("curation draft packet identity mismatch")
    base_context_path = repo / handoff["planned_promotion_base_context_path"]
    context = load_document(
        base_context_path
        if base_context_path.is_file()
        else repo / "research/knowledge/open-source-v1/current-context.json"
    )
    if knowledge.semantic_fingerprint(context, "context_fingerprint") != context["context_fingerprint"]:
        raise ValueError("curation draft knowledge context fingerprint mismatch")
    if draft_packet["knowledge_snapshot_fingerprint"] != context["knowledge_snapshot_fingerprint"]:
        raise ValueError("curation draft knowledge snapshot mismatch")
    formal_ids = {item["lesson_id"] for item in context["lessons"]}
    eligible_actions = {
        item["target_id"]: item
        for item in post_plan["actions"]
        if item["action_type"] == "prepare_non_authoritative_lesson_curation_draft"
    }
    eligible = sorted(eligible_actions)
    covered: list[str] = []
    lesson_validator = jsonschema.Draft202012Validator(load_document(repo / LESSON_SCHEMA))
    proposed_ids: set[str] = set()
    for draft in draft_packet["drafts"]:
        if knowledge.semantic_fingerprint(draft, "draft_fingerprint") != draft["draft_fingerprint"]:
            raise ValueError("curation draft fingerprint mismatch")
        source_ids = draft["source_feedback_ids"]
        if source_ids != sorted(source_ids) or any(item not in eligible_actions for item in source_ids):
            raise ValueError("curation draft source feedback is not exact and sorted")
        expected_events = sorted(eligible_actions[item]["review_event_id"] for item in source_ids)
        if draft["source_review_event_ids"] != expected_events:
            raise ValueError("curation draft review event binding mismatch")
        allowed_evidence = {
            path
            for item in source_ids
            for path in eligible_actions[item]["evidence"]
        }
        if draft["evidence_paths"] != sorted(draft["evidence_paths"]) or not set(draft["evidence_paths"]).issubset(allowed_evidence):
            raise ValueError("curation draft evidence is outside its approved actions")
        _local_evidence(repo, draft["evidence_paths"])
        card = draft["proposed_card"]
        lesson_validator.validate(card)
        if knowledge.semantic_fingerprint(card, "lesson_fingerprint") != card["lesson_fingerprint"]:
            raise ValueError("proposed lesson card fingerprint mismatch")
        if card["evidence_paths"] != draft["evidence_paths"]:
            raise ValueError("proposed lesson evidence differs from the curation draft")
        if card["lesson_id"] in proposed_ids:
            raise ValueError("curation draft proposes a duplicate lesson id")
        proposed_ids.add(card["lesson_id"])
        supersedes = draft["supersedes_lesson_ids"]
        if draft["merge_disposition"] == "replace_existing_lesson":
            if not supersedes or any(item not in formal_ids for item in supersedes):
                raise ValueError("replacement draft must bind existing lessons")
        elif supersedes:
            raise ValueError("non-replacement draft cannot supersede lessons")
        elif card["lesson_id"] in formal_ids:
            raise ValueError("standalone curation draft collides with a formal lesson")
        covered.extend(source_ids)
    if sorted(covered) != eligible or len(covered) != len(set(covered)):
        raise ValueError("curation drafts must cover eligible feedback exactly once")
    expected_coverage = {
        "eligible_feedback_ids": eligible,
        "covered_feedback_ids": eligible,
        "uncovered_feedback_ids": [],
        "duplicate_feedback_merged": len(eligible) - len(draft_packet["drafts"]),
    }
    if draft_packet["coverage"] != expected_coverage:
        raise ValueError("curation draft coverage summary mismatch")
    return {"eligible_feedback": len(eligible), "drafts": len(draft_packet["drafts"])}


def pending_batches(repo: Path) -> list[dict[str, Any]]:
    root = repo / BATCH_ROOT
    if not root.exists():
        return []
    pending = []
    for batch_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        handoff_path = batch_dir / "handoff.json"
        plan_path = batch_dir / "post-approval-plan.json"
        if not handoff_path.is_file() or not plan_path.is_file():
            continue
        handoff = load_document(handoff_path)
        post_plan = load_document(plan_path)
        _validate_basis(repo, handoff, post_plan)
        eligible = sum(item["action_type"] == "prepare_non_authoritative_lesson_curation_draft" for item in post_plan["actions"])
        if eligible == 0:
            continue
        output = repo / handoff["planned_curation_draft_path"]
        if output.is_file():
            validate_draft_packet(repo, handoff, post_plan, load_document(output))
            continue
        pending.append({
            "batch_id": handoff["batch_id"],
            "eligible_feedback": eligible,
            "post_approval_plan_path": handoff["planned_post_approval_plan_path"],
            "planned_curation_draft_path": handoff["planned_curation_draft_path"],
            "advisor_prompt_path": "research/knowledge/prompts/lesson-curation-draft-advisor-v1.md",
        })
    return pending


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    subparsers = parser.add_subparsers(dest="mode", required=True)
    subparsers.add_parser("status")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--batch-id", required=True)
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    if args.mode == "status":
        pending = pending_batches(repo)
        result = {"status": "curation_draft_required" if pending else "idle", "pending": pending}
    else:
        batch_root = repo / BATCH_ROOT / args.batch_id
        handoff = load_document(batch_root / "handoff.json")
        post_plan = load_document(batch_root / "post-approval-plan.json")
        summary = validate_draft_packet(
            repo, handoff, post_plan, load_document(repo / handoff["planned_curation_draft_path"])
        )
        result = {"status": "valid_non_authoritative_curation_draft", "batch_id": args.batch_id, **summary}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
