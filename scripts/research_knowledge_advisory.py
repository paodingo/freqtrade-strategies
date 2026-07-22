#!/usr/bin/env python3
"""Validate non-authoritative review recommendations against a pending packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import load_document


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = Path("research/knowledge/schemas/knowledge-review-recommendations.schema.json")


def validate_advisory(repo: Path, packet: dict[str, Any], advisory: dict[str, Any]) -> dict[str, int]:
    jsonschema.Draft202012Validator(load_document(repo / SCHEMA)).validate(advisory)
    if advisory["packet_fingerprint"] != packet["packet_fingerprint"]:
        raise ValueError("advisory packet fingerprint mismatch")
    packet_items = {
        item["review_key"]: (item["review_type"], item["target_id"])
        for item in packet["items"]
    }
    recommendations = advisory["recommendations"]
    advisory_items = {
        item["review_key"]: (item["review_type"], item["target_id"])
        for item in recommendations
    }
    if len(advisory_items) != len(recommendations) or advisory_items != packet_items:
        raise ValueError("advisory must cover each pending review item exactly once")
    expected_summary = {
        "approved": sum(item["recommended_decision"] == "approved" for item in recommendations),
        "rejected": sum(item["recommended_decision"] == "rejected" for item in recommendations),
        "total": len(recommendations),
    }
    if advisory["summary"] != expected_summary:
        raise ValueError("advisory summary mismatch")
    if knowledge.semantic_fingerprint(advisory, "advisory_fingerprint") != advisory["advisory_fingerprint"]:
        raise ValueError("advisory fingerprint mismatch")
    return expected_summary


def validate_aggregated_advisory(repo: Path, packet: dict[str, Any], advisory: dict[str, Any]) -> dict[str, int]:
    """Apply stricter rules to automatically drafted, local-evidence-only advisories."""
    summary = validate_advisory(repo, packet, advisory)
    expected_id = f"knowledge-review-advisory-{packet['packet_fingerprint'][:16]}"
    if advisory["advisory_id"] != expected_id:
        raise ValueError("aggregated advisory identity mismatch")
    if advisory["generated_at"] != packet["generated_at"]:
        raise ValueError("aggregated advisory must use the stable packet timestamp")
    evidence_by_key = {
        item["review_key"]: set(item["evidence"])
        for item in packet["items"]
    }
    for item in advisory["recommendations"]:
        references = set(item["references"])
        if not references.issubset(evidence_by_key[item["review_key"]]):
            raise ValueError("aggregated advisory references evidence outside the packet")
        for reference in references:
            if reference.startswith(("http://", "https://")):
                raise ValueError("aggregated advisory must use local evidence only")
            candidate = (repo / reference).resolve()
            try:
                candidate.relative_to(repo.resolve())
            except ValueError as exc:
                raise ValueError("aggregated advisory evidence escapes the repository") from exc
            if not candidate.is_file():
                raise ValueError("aggregated advisory local evidence is missing")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--packet", default="reports/audits/open-source-learning-v1/pending-review-packet.json")
    parser.add_argument("--advisory", default="reports/audits/open-source-learning-v1/review-recommendations.json")
    parser.add_argument("--strict-local-evidence", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    validator = validate_aggregated_advisory if args.strict_local_evidence else validate_advisory
    summary = validator(repo, load_document(repo / args.packet), load_document(repo / args.advisory))
    print(json.dumps({"status": "valid_non_authoritative_advisory", "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
