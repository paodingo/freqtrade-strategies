#!/usr/bin/env python3
"""Render governed lesson drafts automatically queued by completed Campaigns."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

from research_director_common import fingerprint, load_document, open_director_registry


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = Path("research/knowledge/schemas/research-lesson-feedback-draft.schema.json")


def _outcome_class(result_code: str) -> str:
    normalized = result_code.lower()
    if any(token in normalized for token in ("reject", "negative", "degrad", "fail", "invalid", "loss")):
        return "negative"
    if any(token in normalized for token in ("accept", "positive", "pass", "improv")):
        return "positive"
    return "inconclusive"


def render_feedback_draft(
    repo: Path,
    connection: Any,
    row: Any,
) -> dict[str, object]:
    evidence_artifacts = [
        {"path": str(asset[0]), "sha256": str(asset[1])}
        for asset in connection.execute(
            "SELECT path,sha256 FROM research_campaign_assets WHERE run_id=? ORDER BY path",
            (row["run_id"],),
        )
    ]
    return _render_feedback_payload(repo, row, evidence_artifacts)


def _render_feedback_payload(
    repo: Path,
    row: Any,
    evidence_artifacts: list[dict[str, str]],
) -> dict[str, object]:
    try:
        result_payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("campaign feedback payload is invalid") from exc
    payload_artifacts = result_payload.get("evidence_artifacts", [])
    if not evidence_artifacts and isinstance(payload_artifacts, list):
        evidence_artifacts = [
            {"path": str(item["path"]), "sha256": str(item["sha256"])}
            for item in payload_artifacts
            if isinstance(item, dict) and "path" in item and "sha256" in item
        ]
    evidence_artifacts = sorted(evidence_artifacts, key=lambda item: item["path"])
    source_kind = result_payload.get("source_kind")
    if source_kind is None and result_payload.get("registration_mode") == "historical_manual_descriptive_analysis":
        source_kind = "historical_manual_descriptive_analysis"
    draft = {
        "schema_version": "research-lesson-feedback-draft-v1",
        "feedback_id": str(row["feedback_id"]),
        "run_id": str(row["run_id"]),
        "campaign_id": str(row["campaign_id"]),
        "proposal_id": str(row["proposal_id"]),
        "result_code": str(row["result_code"]),
        "outcome_class": _outcome_class(str(row["result_code"])),
        "source_kind": str(source_kind or "campaign"),
        "evidence_paths": [item["path"] for item in evidence_artifacts],
        "evidence_artifacts": evidence_artifacts,
        "result_payload_fingerprint": fingerprint(result_payload),
        "review_status": "pending_human_review",
        "automatic_promotion_authorized": False,
        "candidate_creation_authorized": False,
        "backtest_authorized": False,
    }
    draft["draft_fingerprint"] = fingerprint(draft)
    validator = jsonschema.Draft202012Validator(load_document(repo / SCHEMA_PATH))
    validator.validate(draft)
    return draft


def pending_feedback_drafts(repo: Path, registry_path: str | Path) -> list[dict[str, object]]:
    connection = open_director_registry(registry_path)
    try:
        rows = connection.execute(
            "SELECT * FROM research_lesson_feedback_drafts "
            "WHERE review_status='pending_human_review' ORDER BY created_at,feedback_id"
        ).fetchall()
        return [render_feedback_draft(repo, connection, row) for row in rows]
    finally:
        connection.close()


def pending_feedback_drafts_from_export(
    repo: Path, export_path: str | Path
) -> list[dict[str, object]]:
    payload = load_document(Path(export_path))
    tables = payload.get("tables")
    if not isinstance(tables, dict):
        raise ValueError("registry export tables are missing")
    assets_by_run: dict[str, list[dict[str, str]]] = {}
    for asset in tables.get("research_campaign_assets", []):
        assets_by_run.setdefault(str(asset["run_id"]), []).append(
            {"path": str(asset["path"]), "sha256": str(asset["sha256"])}
        )
    rows = [
        row
        for row in tables.get("research_lesson_feedback_drafts", [])
        if row.get("review_status") == "pending_human_review"
    ]
    rows.sort(key=lambda row: (str(row["created_at"]), str(row["feedback_id"])))
    return [
        _render_feedback_payload(
            repo,
            row,
            assets_by_run.get(str(row["run_id"]), []),
        )
        for row in rows
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--registry")
    source.add_argument("--registry-export")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    drafts = (
        pending_feedback_drafts(repo, args.registry)
        if args.registry
        else pending_feedback_drafts_from_export(repo, args.registry_export)
    )
    print(json.dumps({"count": len(drafts), "drafts": drafts}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
