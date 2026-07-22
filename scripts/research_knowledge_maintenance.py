#!/usr/bin/env python3
"""Govern source refresh, lifecycle, retrieval evaluation, and learning-loop health."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import jsonschema

import open_source_knowledge as knowledge
from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = Path("reports/audits/open-source-learning-v1")
REFRESH_SCHEMA = Path("research/knowledge/schemas/knowledge-source-refresh-report.schema.json")
EVALUATION_SCHEMA = Path("research/knowledge/schemas/knowledge-retrieval-evaluation.schema.json")
HEALTH_SCHEMA = Path("research/knowledge/schemas/research-learning-loop-health.schema.json")
EVALUATION_CASES = Path("research/knowledge/evaluation/retrieval-cases-v1.json")


def _validate(repo: Path, schema_path: Path, payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(load_document(repo / schema_path)).validate(payload)


def fetch_remote_heads() -> dict[str, str | Exception]:
    results: dict[str, str | Exception] = {}
    for spec in knowledge.SOURCE_SPECS:
        try:
            output = subprocess.check_output(
                [
                    "git",
                    "ls-remote",
                    "--heads",
                    spec["canonical_url"],
                    f"refs/heads/{spec['default_branch']}",
                ],
                text=True,
                encoding="utf-8",
                timeout=30,
            ).strip()
            commit = output.split()[0] if output else ""
            if len(commit) != 40:
                raise ValueError("upstream branch head is missing")
            results[spec["project_id"]] = commit
        except Exception as exc:
            results[spec["project_id"]] = exc
    return results


def build_refresh_report(
    repo: Path,
    remote_heads: dict[str, str | Exception],
    checked_at: str,
) -> dict[str, Any]:
    projects = []
    for spec in knowledge.SOURCE_SPECS:
        remote = remote_heads.get(spec["project_id"])
        error = None
        if isinstance(remote, Exception) or not isinstance(remote, str):
            status = "check_failed"
            upstream = None
            error = type(remote).__name__ if isinstance(remote, Exception) else "missing_result"
        else:
            upstream = remote
            status = "current" if upstream == spec["commit_sha"] else "update_available"
        proposal_id = None
        if status == "update_available":
            proposal_id = f"knowledge-update-{fingerprint({'project': spec['project_id'], 'current': spec['commit_sha'], 'upstream': upstream})[:16]}"
        projects.append(
            {
                "project_id": spec["project_id"],
                "canonical_url": spec["canonical_url"],
                "branch": spec["default_branch"],
                "pinned_commit": spec["commit_sha"],
                "upstream_commit": upstream,
                "status": status,
                "license_status": "review_required" if spec["license_spdx"] == "NOASSERTION" else "asserted",
                "error": error,
                "human_approval_required": True,
                "proposal_id": proposal_id,
            }
        )
    report = {
        "schema_version": "knowledge-source-refresh-report-v1",
        "checked_at": checked_at,
        "projects": projects,
        "summary": {
            "current": sum(item["status"] == "current" for item in projects),
            "update_available": sum(item["status"] == "update_available" for item in projects),
            "check_failed": sum(item["status"] == "check_failed" for item in projects),
            "license_review_required": sum(item["license_status"] == "review_required" for item in projects),
        },
        "automatic_update_authorized": False,
    }
    report["report_fingerprint"] = knowledge.semantic_fingerprint(report, "report_fingerprint")
    _validate(repo, REFRESH_SCHEMA, report)
    return report


def register_lifecycle_and_updates(
    repo: Path,
    registry_path: str | Path,
    refresh_report: dict[str, Any],
) -> dict[str, int]:
    context = load_document(repo / knowledge.OUTPUT_ROOT / "current-context.json")
    connection = open_director_registry(registry_path)
    try:
        items = []
        for source in context["sources"]:
            status = "review_required" if source["license_spdx"] == "NOASSERTION" else "active_pinned"
            items.append(("source", source["snapshot_id"], source["content_fingerprint"], status))
        items.extend(("pattern", item["pattern_id"], item["pattern_fingerprint"], "active") for item in context["patterns"])
        items.extend(("lesson", item["lesson_id"], item["lesson_fingerprint"], "active") for item in context["lessons"])
        for item_type, item_id, item_fingerprint, status in items:
            item_key = f"{item_type}:{item_id}@{item_fingerprint[:16]}"
            payload = {
                "item_key": item_key,
                "item_type": item_type,
                "item_id": item_id,
                "snapshot_fingerprint": item_fingerprint,
                "lifecycle_status": status,
                "automatic_transition_authorized": False,
            }
            connection.execute(
                "INSERT OR IGNORE INTO research_knowledge_lifecycle("
                "item_key,item_type,item_id,snapshot_fingerprint,lifecycle_status,superseded_by,reason,payload_json,updated_at"
                ") VALUES(?,?,?,?,?,?,?,?,?)",
                (item_key, item_type, item_id, item_fingerprint, status, None, "initial_v1_registration", json.dumps(payload, sort_keys=True), refresh_report["checked_at"]),
            )
        for project in refresh_report["projects"]:
            if project["status"] != "update_available":
                continue
            payload = {
                "schema_version": "knowledge-update-proposal-v1",
                **project,
                "status": "pending_human_approval",
                "automatic_update_authorized": False,
            }
            connection.execute(
                "INSERT OR IGNORE INTO research_knowledge_update_proposals("
                "proposal_id,project_id,current_commit,upstream_commit,status,payload_json,created_at"
                ") VALUES(?,?,?,?,?,?,?)",
                (project["proposal_id"], project["project_id"], project["pinned_commit"], project["upstream_commit"], "pending_human_approval", json.dumps(payload, sort_keys=True), refresh_report["checked_at"]),
            )
        connection.commit()
        return {
            "lifecycle": connection.execute("SELECT COUNT(*) FROM research_knowledge_lifecycle").fetchone()[0],
            "update_proposals": connection.execute("SELECT COUNT(*) FROM research_knowledge_update_proposals").fetchone()[0],
        }
    finally:
        connection.close()


def apply_lifecycle_decision(
    connection: Any,
    item_key: str,
    new_status: str,
    approval: dict[str, Any],
    *,
    superseded_by: str | None = None,
) -> None:
    if new_status not in {"active", "active_pinned", "review_required", "deprecated", "superseded"}:
        raise ValueError("knowledge lifecycle status is invalid")
    if approval.get("reviewer_type") != "human_user" or approval.get("decision") != "approved":
        raise ValueError("human lifecycle approval is required")
    if new_status == "superseded" and not superseded_by:
        raise ValueError("superseded knowledge requires a replacement")
    row = connection.execute(
        "SELECT * FROM research_knowledge_lifecycle WHERE item_key=?", (item_key,)
    ).fetchone()
    if row is None:
        raise ValueError("knowledge lifecycle item is missing")
    connection.execute(
        "UPDATE research_knowledge_lifecycle SET lifecycle_status=?,superseded_by=?,reason=?,payload_json=?,updated_at=? WHERE item_key=?",
        (new_status, superseded_by, str(approval.get("reason", "human_approved_transition")), json.dumps(approval, sort_keys=True), str(approval["decided_at"]), item_key),
    )


def evaluate_retrieval(repo: Path, state: dict[str, Any]) -> dict[str, Any]:
    cases_document = load_document(repo / EVALUATION_CASES)
    results = []
    for case in cases_document["cases"]:
        selection = knowledge.broker_selection(
            repo,
            "manual_request",
            case["query"],
            fingerprint({"evaluation_case": case["case_id"]}),
            state,
        )
        key = "selected_patterns" if case["expected_type"] == "pattern" else "selected_lessons"
        id_key = "pattern_id" if case["expected_type"] == "pattern" else "lesson_id"
        ranked_ids = [item[id_key] for item in selection[key]]
        rank = ranked_ids.index(case["expected_id"]) + 1 if case["expected_id"] in ranked_ids else None
        results.append({**case, "rank": rank, "hit": rank is not None})
    hits = sum(item["hit"] for item in results)
    first = sum(item["rank"] == 1 for item in results)
    threshold = 0.875
    report = {
        "schema_version": "knowledge-retrieval-evaluation-v1",
        "evaluation_id": "open-source-knowledge-retrieval-v1",
        "knowledge_snapshot_fingerprint": state["open_source_knowledge"]["knowledge_snapshot_fingerprint"],
        "case_count": len(results),
        "hit_rate_at_4": hits / len(results),
        "first_rank_rate": first / len(results),
        "threshold": threshold,
        "status": "passed" if hits / len(results) >= threshold else "failed",
        "cases": results,
    }
    report["evaluation_fingerprint"] = knowledge.semantic_fingerprint(report, "evaluation_fingerprint")
    _validate(repo, EVALUATION_SCHEMA, report)
    return report


def build_knowledge_influence_chain(
    tables: dict[str, list[dict[str, Any]]],
    observed_runs: list[str],
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    ideas_by_run: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for row in tables.get("research_discovery_ideas", []):
        ideas_by_run.setdefault(row["run_id"], []).append((row, json.loads(row["payload_json"])))
    critiques_by_key = {
        row["idea_key"]: (row, json.loads(row["payload_json"]))
        for row in tables.get("research_discovery_critiques", [])
    }
    shortlist_by_run = {
        row["run_id"]: row for row in tables.get("research_discovery_shortlists", [])
    }
    approval_by_run = {
        row["run_id"]: row for row in tables.get("research_discovery_approvals", [])
    }
    handoff_by_run = {
        row["run_id"]: (row, json.loads(row["payload_json"]))
        for row in tables.get("research_discovery_handoffs", [])
    }
    chains = []
    for run_id in observed_runs:
        run_bindings = [row for row in bindings if row["target_id"] == run_id]
        binding_payloads = [json.loads(row["payload_json"]) for row in run_bindings]
        selection_ids = {item.get("selection_id") for item in binding_payloads}
        selection_fingerprints = {
            item.get("selection_fingerprint") for item in binding_payloads
        }
        issues = []
        if len(selection_ids) != 1 or None in selection_ids:
            issues.append("retrieval_selection_id_inconsistent")
        if len(selection_fingerprints) != 1 or None in selection_fingerprints:
            issues.append("retrieval_selection_fingerprint_inconsistent")
        selection_id = next(iter(selection_ids)) if len(selection_ids) == 1 else None
        selection_fingerprint = (
            next(iter(selection_fingerprints))
            if len(selection_fingerprints) == 1
            else None
        )
        selected_patterns = {
            row["source_id"] for row in run_bindings
            if row["source_type"] == "strategy_pattern"
        }
        selected_lessons = {
            row["source_id"] for row in run_bindings
            if row["source_type"] == "research_lesson"
        }
        idea_records = ideas_by_run.get(run_id, [])
        bound_idea_keys = set()
        critic_verified_keys = set()
        semantic_duplicate_keys = set()
        for idea_row, idea in idea_records:
            use = idea.get("knowledge_use")
            idea_key = idea_row["idea_key"]
            if not isinstance(use, dict):
                issues.append(f"idea_knowledge_binding_missing:{idea_key}")
                continue
            differences = use.get("material_difference_from_lessons") or []
            difference_ids = [item.get("lesson_id") for item in differences if isinstance(item, dict)]
            binding_valid = (
                use.get("selection_id") == selection_id
                and use.get("selection_fingerprint") == selection_fingerprint
                and set(use.get("used_pattern_ids") or []).issubset(selected_patterns)
                and set(use.get("considered_lesson_ids") or []) == selected_lessons
                and set(difference_ids) == selected_lessons
                and len(difference_ids) == len(set(difference_ids))
            )
            if not binding_valid:
                issues.append(f"idea_knowledge_binding_invalid:{idea_key}")
                continue
            bound_idea_keys.add(idea_key)
            critique_record = critiques_by_key.get(idea_key)
            if critique_record is None:
                issues.append(f"critic_missing:{idea_key}")
                continue
            _, critique = critique_record
            verification = critique.get("knowledge_verification")
            checks = (
                verification.get("lesson_checks")
                if isinstance(verification, dict)
                else []
            ) or []
            check_ids = [item.get("lesson_id") for item in checks if isinstance(item, dict)]
            verification_valid = (
                isinstance(verification, dict)
                and verification.get("selection_id") == selection_id
                and verification.get("selection_fingerprint") == selection_fingerprint
                and verification.get("idea_knowledge_use_verified") is True
                and set(check_ids) == selected_lessons
                and len(check_ids) == len(set(check_ids))
            )
            if not verification_valid:
                issues.append(f"critic_knowledge_verification_invalid:{idea_key}")
                continue
            critic_verified_keys.add(idea_key)
            if any(item.get("result") == "semantic_duplicate" for item in checks):
                semantic_duplicate_keys.add(idea_key)
        approval = approval_by_run.get(run_id)
        selected_idea_id = approval.get("selected_idea_id") if approval else None
        selected_idea_use = None
        selected_idea_key = None
        selected_critique = None
        if selected_idea_id:
            selected_rows = [
                item for item in idea_records if item[0]["idea_id"] == selected_idea_id
            ]
            if selected_rows:
                selected_row, selected_payload = max(
                    selected_rows, key=lambda item: item[0]["idea_version"]
                )
                selected_idea_key = selected_row["idea_key"]
                selected_idea_use = selected_payload.get("knowledge_use")
                selected_critique = critiques_by_key.get(selected_idea_key)
            else:
                issues.append("selected_idea_record_missing")
        handoff_record = handoff_by_run.get(run_id)
        handoff_bound = False
        if handoff_record is not None:
            handoff_row, handoff_payload = handoff_record
            if selected_idea_key is None or selected_critique is None:
                issues.append("director_handoff_without_selected_knowledge_chain")
            else:
                selected_row = next(
                    row for row, _ in idea_records if row["idea_key"] == selected_idea_key
                )
                critic_row, _ = selected_critique
                handoff_bound = (
                    selected_idea_key in bound_idea_keys
                    and selected_idea_key in critic_verified_keys
                    and handoff_payload.get("idea_fingerprint")
                    == selected_row["semantic_fingerprint"]
                    and handoff_payload.get("critique_fingerprint")
                    == critic_row["critic_fingerprint"]
                    and handoff_row.get("idea_id") == selected_idea_id
                )
                if not handoff_bound:
                    issues.append("director_handoff_knowledge_binding_invalid")
        recommendation = shortlist_by_run.get(run_id, {}).get("recommendation")
        if issues:
            classification = "broken_knowledge_chain"
        elif not idea_records:
            classification = "retrieved_only_no_idea_artifacts"
        elif handoff_bound:
            classification = "director_handoff_knowledge_bound"
        elif recommendation == "no_research_recommended":
            classification = "critic_verified_no_direction"
        elif recommendation == "research_recommended":
            classification = "critic_verified_awaiting_direction_decision"
        else:
            classification = "idea_and_critic_bound_no_handoff"
        chains.append({
            "run_id": run_id,
            "selection_id": selection_id,
            "selection_fingerprint": selection_fingerprint,
            "classification": classification,
            "retrieved_pattern_ids": sorted(selected_patterns),
            "retrieved_lesson_ids": sorted(selected_lessons),
            "idea_artifact_count": len(idea_records),
            "knowledge_bound_idea_count": len(bound_idea_keys),
            "critic_verified_idea_count": len(critic_verified_keys),
            "semantic_duplicate_idea_count": len(semantic_duplicate_keys),
            "selected_idea_id": selected_idea_id,
            "selected_idea_used_pattern_ids": sorted(
                (selected_idea_use or {}).get("used_pattern_ids") or []
            ),
            "selected_idea_considered_lesson_ids": sorted(
                (selected_idea_use or {}).get("considered_lesson_ids") or []
            ),
            "director_handoff_bound": handoff_bound,
            "issues": sorted(set(issues)),
        })
    return {
        "observed_run_count": len(chains),
        "retrieved_only_run_count": sum(
            item["classification"] == "retrieved_only_no_idea_artifacts"
            for item in chains
        ),
        "critic_verified_run_count": sum(
            item["critic_verified_idea_count"] > 0 for item in chains
        ),
        "director_handoff_bound_run_count": sum(
            item["director_handoff_bound"] for item in chains
        ),
        "broken_chain_run_count": sum(
            item["classification"] == "broken_knowledge_chain" for item in chains
        ),
        "runs": chains,
    }


def build_result_feedback_chain(
    repo: Path,
    tables: dict[str, list[dict[str, Any]]],
    influence_chain: dict[str, Any],
) -> dict[str, Any]:
    """Trace knowledge-bound handoffs into proposals, artifacts, and review feedback."""
    handoffs_by_run = {
        row["run_id"]: (row, json.loads(row["payload_json"]))
        for row in tables.get("research_discovery_handoffs", [])
    }
    proposals = [
        (row, json.loads(row["payload_json"]))
        for row in tables.get("director_proposals", [])
    ]
    results_by_proposal: dict[str, list[dict[str, Any]]] = {}
    for row in tables.get("research_descriptive_execution_results", []):
        results_by_proposal.setdefault(str(row["proposal_id"]), []).append(row)
    feedback_by_proposal: dict[str, list[dict[str, Any]]] = {}
    for row in tables.get("research_lesson_feedback_drafts", []):
        if row.get("proposal_id") is not None:
            feedback_by_proposal.setdefault(str(row["proposal_id"]), []).append(row)
    worker_jobs_by_run: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for row in tables.get("research_worker_jobs", []):
        if row.get("stage") != "descriptive_execution":
            continue
        worker_jobs_by_run.setdefault(str(row["run_id"]), []).append(
            (row, json.loads(row["payload_json"]))
        )

    def artifact_path(relative: str) -> Path:
        if not relative or "\\" in relative or Path(relative).is_absolute():
            raise ValueError("result feedback artifact path is not canonical repo-relative")
        target = (repo / relative).resolve(strict=False)
        try:
            target.relative_to(repo)
        except ValueError as exc:
            raise ValueError("result feedback artifact path escapes repository") from exc
        return target

    chains = []
    for influence in influence_chain["runs"]:
        if not influence["director_handoff_bound"]:
            continue
        run_id = influence["run_id"]
        issues = []
        handoff_record = handoffs_by_run.get(run_id)
        if handoff_record is None:
            issues.append("knowledge_bound_handoff_record_missing")
            handoff_fingerprint = None
        else:
            _, handoff_payload = handoff_record
            handoff_fingerprint = handoff_payload.get("handoff_fingerprint")
        matching_proposals = [
            item
            for item in proposals
            if item[1].get("discovery_handoff_fingerprint") == handoff_fingerprint
        ]
        proposal_row = None
        proposal = None
        if len(matching_proposals) == 0:
            proposal_id = None
        elif len(matching_proposals) > 1:
            proposal_id = None
            issues.append("multiple_proposals_for_knowledge_bound_handoff")
        else:
            proposal_row, proposal = matching_proposals[0]
            proposal_id = str(proposal_row["proposal_id"])
            if (
                proposal.get("proposal_id") != proposal_id
                or proposal.get("knowledge_selection_id") != influence["selection_id"]
                or proposal.get("knowledge_selection_fingerprint")
                != influence["selection_fingerprint"]
                or set(proposal.get("knowledge_pattern_ids") or [])
                != set(influence["selected_idea_used_pattern_ids"])
                or set(proposal.get("knowledge_lesson_ids") or [])
                != set(influence["selected_idea_considered_lesson_ids"])
            ):
                issues.append("director_proposal_knowledge_binding_invalid")

        required_artifacts: list[str] = []
        artifact_rows: list[dict[str, Any]] = []
        analysis = None
        if proposal is not None:
            required = proposal.get("required_artifacts")
            allowed = proposal.get("allowed_changes")
            expected = [
                f"research/analysis/{proposal_id}/analysis.json",
                f"reports/audits/{proposal_id}/report.md",
            ]
            if required != expected or allowed != expected:
                issues.append("director_proposal_artifact_scope_invalid")
            else:
                required_artifacts = expected
                for relative in expected:
                    try:
                        target = artifact_path(relative)
                    except ValueError:
                        issues.append("director_proposal_artifact_path_invalid")
                        continue
                    artifact_rows.append({
                        "path": relative,
                        "exists": target.is_file(),
                        "sha256": sha256_file(target) if target.is_file() else None,
                    })
                existing = [item for item in artifact_rows if item["exists"]]
                if existing and len(existing) != len(expected):
                    issues.append("descriptive_analysis_artifact_set_partial")
                if len(existing) == len(expected):
                    try:
                        analysis = load_document(artifact_path(expected[0]))
                    except (OSError, ValueError, json.JSONDecodeError):
                        issues.append("descriptive_analysis_json_invalid")
                    if analysis is not None and (
                        analysis.get("proposal_id") != proposal_id
                        or (
                            analysis.get("discovery_run_id") is not None
                            and analysis.get("discovery_run_id") != run_id
                        )
                        or (
                            analysis.get("proposal_semantic_fingerprint") is not None
                            and analysis.get("proposal_semantic_fingerprint")
                            != proposal_row["semantic_fingerprint"]
                        )
                    ):
                        issues.append("descriptive_analysis_proposal_binding_invalid")

        result_rows = results_by_proposal.get(proposal_id or "", [])
        feedback_rows = feedback_by_proposal.get(proposal_id or "", [])
        failed_worker_job_ids = sorted(
            str(row["job_id"])
            for row, payload in worker_jobs_by_run.get(run_id, [])
            if row.get("status") == "failed"
            and payload.get("proposal_id") == proposal_id
        )
        if len(result_rows) > 1:
            issues.append("multiple_descriptive_results_for_proposal")
        if len(feedback_rows) > 1:
            issues.append("multiple_feedback_drafts_for_proposal")
        if result_rows and not feedback_rows:
            issues.append("registered_descriptive_result_missing_feedback")
        if feedback_rows and not result_rows:
            issues.append("feedback_draft_missing_registered_descriptive_result")

        analysis_complete = (
            len(artifact_rows) == 2
            and all(item["exists"] for item in artifact_rows)
            and analysis is not None
        )
        if issues:
            classification = "broken_result_feedback_chain"
        elif proposal is None:
            classification = "handoff_bound_awaiting_proposal"
        elif failed_worker_job_ids and not analysis_complete:
            classification = "proposal_bound_execution_failed"
        elif not analysis_complete:
            classification = "proposal_bound_awaiting_execution"
        elif feedback_rows:
            classification = (
                "analysis_feedback_pending_human_review"
                if feedback_rows[0]["review_status"] == "pending_human_review"
                else "analysis_feedback_reviewed"
            )
        elif result_rows:
            classification = "broken_result_feedback_chain"
        else:
            classification = "analysis_completed_feedback_unregistered"
        chains.append({
            "run_id": run_id,
            "selected_idea_id": influence["selected_idea_id"],
            "proposal_id": proposal_id,
            "proposal_knowledge_binding_verified": proposal is not None and not any(
                issue.startswith("director_proposal_") for issue in issues
            ),
            "classification": classification,
            "required_artifacts": required_artifacts,
            "artifacts": artifact_rows,
            "analysis_completed": analysis_complete,
            "registered_result_ids": sorted(
                str(row["result_id"]) for row in result_rows
            ),
            "feedback_ids": sorted(str(row["feedback_id"]) for row in feedback_rows),
            "feedback_review_statuses": sorted(
                str(row["review_status"]) for row in feedback_rows
            ),
            "failed_worker_job_ids": failed_worker_job_ids,
            "issues": sorted(set(issues)),
        })
    return {
        "director_bound_run_count": len(chains),
        "proposal_bound_run_count": sum(item["proposal_id"] is not None for item in chains),
        "analysis_completed_run_count": sum(item["analysis_completed"] for item in chains),
        "registered_result_run_count": sum(bool(item["registered_result_ids"]) for item in chains),
        "feedback_draft_run_count": sum(bool(item["feedback_ids"]) for item in chains),
        "feedback_reviewed_run_count": sum(
            item["classification"] == "analysis_feedback_reviewed" for item in chains
        ),
        "legacy_unregistered_run_count": sum(
            item["classification"] == "analysis_completed_feedback_unregistered"
            for item in chains
        ),
        "execution_failed_run_count": sum(
            item["classification"] == "proposal_bound_execution_failed"
            for item in chains
        ),
        "broken_chain_run_count": sum(
            item["classification"] == "broken_result_feedback_chain" for item in chains
        ),
        "runs": chains,
    }


def build_knowledge_impact(
    repo: Path,
    registry_export: dict[str, Any],
) -> dict[str, Any]:
    context = load_document(repo / knowledge.OUTPUT_ROOT / "current-context.json")
    snapshot = context["knowledge_snapshot_fingerprint"]
    tables = registry_export["tables"]
    formal_ids = {
        "strategy_pattern": {item["pattern_id"] for item in context["patterns"]},
        "research_lesson": {item["lesson_id"] for item in context["lessons"]},
    }
    usage: dict[str, dict[str, set[str] | int]] = {
        source_type: {
            item_id: {"retrieval_count": 0, "run_ids": set()}
            for item_id in item_ids
        }
        for source_type, item_ids in formal_ids.items()
    }
    bindings = []
    for row in tables.get("open_source_knowledge_lineage", []):
        if row.get("relation") != "retrieved_for" or row.get("target_type") != "discovery_run":
            continue
        payload = json.loads(row["payload_json"])
        if payload.get("knowledge_snapshot_fingerprint") != snapshot:
            continue
        source_type = row["source_type"]
        source_id = row["source_id"]
        if source_type not in usage or source_id not in usage[source_type]:
            raise ValueError("Broker usage references knowledge outside the formal snapshot")
        usage[source_type][source_id]["retrieval_count"] += 1
        usage[source_type][source_id]["run_ids"].add(row["target_id"])
        bindings.append(row)
    observed_runs = sorted({row["target_id"] for row in bindings})
    shortlist_by_run = {
        row["run_id"]: row
        for row in tables.get("research_discovery_shortlists", [])
    }
    approval_by_run = {
        row["run_id"]: row
        for row in tables.get("research_discovery_approvals", [])
    }
    handoff_by_run = {
        row["run_id"]: row
        for row in tables.get("research_discovery_handoffs", [])
    }

    def usage_summary(source_type: str) -> dict[str, Any]:
        records = usage[source_type]
        items = [
            {
                "item_id": item_id,
                "retrieval_count": int(record["retrieval_count"]),
                "discovery_run_ids": sorted(record["run_ids"]),
            }
            for item_id, record in sorted(records.items())
        ]
        never = [item["item_id"] for item in items if item["retrieval_count"] == 0]
        return {
            "formal_count": len(items),
            "retrieved_count": len(items) - len(never),
            "never_retrieved_count": len(never),
            "never_retrieved_ids": never,
            "items": items,
        }

    run_binding_counts = {
        run_id: sum(row["target_id"] == run_id for row in bindings)
        for run_id in observed_runs
    }
    run_outcomes = [
        {
            "run_id": run_id,
            "retrieval_binding_count": run_binding_counts[run_id],
            "shortlist_recommendation": (
                shortlist_by_run.get(run_id, {}).get("recommendation")
            ),
            "selected_idea_id": approval_by_run.get(run_id, {}).get("selected_idea_id"),
            "handoff_status": handoff_by_run.get(run_id, {}).get("status"),
        }
        for run_id in observed_runs
    ]
    influence_chain = build_knowledge_influence_chain(
        tables, observed_runs, bindings
    )
    result_feedback_chain = build_result_feedback_chain(
        repo, tables, influence_chain
    )
    report = {
        "schema_version": "knowledge-impact-v1",
        "knowledge_snapshot_fingerprint": snapshot,
        "status": "observed_usage" if observed_runs else "no_observed_usage",
        "observed_discovery_runs": len(observed_runs),
        "retrieval_binding_count": len(bindings),
        "pattern_usage": usage_summary("strategy_pattern"),
        "lesson_usage": usage_summary("research_lesson"),
        "run_outcomes": run_outcomes,
        "influence_chain": influence_chain,
        "result_feedback_chain": result_feedback_chain,
        "causal_performance_attribution_authorized": False,
        "execution_authorized": False,
    }
    report["impact_fingerprint"] = knowledge.semantic_fingerprint(
        report, "impact_fingerprint"
    )
    return report


def build_health(
    repo: Path,
    registry_export: dict[str, Any],
    refresh_report: dict[str, Any],
    evaluation: dict[str, Any],
    checked_at: str,
) -> dict[str, Any]:
    tables = registry_export["tables"]
    worker_jobs = tables.get("research_worker_jobs", [])
    lifecycle = tables.get("research_knowledge_lifecycle", [])
    proposals = tables.get("research_knowledge_update_proposals", [])
    review_events = tables.get("research_knowledge_review_events", [])
    feedback = tables.get("research_lesson_feedback_drafts", [])
    curation_candidates = tables.get("research_lesson_curation_candidates", [])
    pending_updates = sum(row["status"] == "pending_human_approval" for row in proposals)
    pending_feedback = sum(row["review_status"] == "pending_human_review" for row in feedback)
    pending_licenses = sum(
        row.get("item_type") == "source" and row.get("lifecycle_status") == "review_required"
        for row in lifecycle
    )
    pending_promotions = sum(
        row.get("status") == "pending_human_promotion_review"
        for row in curation_candidates
    )
    descriptive_jobs = [
        (row, json.loads(row["payload_json"]))
        for row in worker_jobs
        if row.get("stage") == "descriptive_execution"
    ]
    failed_descriptive_jobs = [
        (row, payload)
        for row, payload in descriptive_jobs
        if row.get("status") == "failed"
    ]
    unrecovered_failed_jobs = [
        row
        for row, payload in failed_descriptive_jobs
        if not any(
            later.get("status") == "completed"
            and later.get("run_id") == row.get("run_id")
            and int(later.get("round_number", 0)) > int(row.get("round_number", 0))
            and later_payload.get("proposal_id") == payload.get("proposal_id")
            for later, later_payload in descriptive_jobs
        )
    ]
    warnings = []
    failures = []
    impact = build_knowledge_impact(repo, registry_export)
    if refresh_report["summary"]["check_failed"]:
        failures.append("source_refresh_check_failed")
    if pending_updates:
        warnings.append("source_updates_pending_human_approval")
    if pending_licenses:
        warnings.append("source_license_review_required")
    if pending_promotions:
        warnings.append("lesson_promotion_review_pending")
    if evaluation["status"] != "passed":
        failures.append("retrieval_evaluation_failed")
    if impact["status"] == "no_observed_usage":
        warnings.append("knowledge_broker_usage_not_observed")
    if impact["influence_chain"]["broken_chain_run_count"]:
        failures.append("knowledge_influence_chain_broken")
    if impact["result_feedback_chain"]["broken_chain_run_count"]:
        failures.append("knowledge_result_feedback_chain_broken")
    if impact["result_feedback_chain"]["legacy_unregistered_run_count"]:
        warnings.append("knowledge_result_feedback_registration_pending")
    if unrecovered_failed_jobs:
        warnings.append("worker_jobs_failed")
    if len(feedback) > 20:
        warnings.append("lesson_feedback_backlog_high")
    metrics = {
        "worker_jobs_queued": sum(row["status"] == "queued" for row in worker_jobs),
        "worker_jobs_claimed": sum(row["status"] == "claimed" for row in worker_jobs),
        "worker_jobs_failed": sum(row["status"] == "failed" for row in worker_jobs),
        "worker_jobs_failed_unrecovered": len(unrecovered_failed_jobs),
        "feedback_drafts_pending_review": pending_feedback,
        "lesson_curation_candidates_pending_promotion": pending_promotions,
        "knowledge_lifecycle_items": len(lifecycle),
        "knowledge_update_proposals_pending": pending_updates,
        "knowledge_license_reviews_pending": pending_licenses,
        "knowledge_review_items_pending": pending_updates + pending_feedback + pending_licenses + pending_promotions,
        "knowledge_review_events": len(review_events),
        "retrieval_evaluation_cases": evaluation["case_count"],
        "broker_discovery_runs_observed": impact["observed_discovery_runs"],
        "broker_retrieval_bindings": impact["retrieval_binding_count"],
        "knowledge_patterns_retrieved": impact["pattern_usage"]["retrieved_count"],
        "knowledge_lessons_retrieved": impact["lesson_usage"]["retrieved_count"],
        "knowledge_influence_runs_critic_verified": impact["influence_chain"]["critic_verified_run_count"],
        "knowledge_influence_runs_director_bound": impact["influence_chain"]["director_handoff_bound_run_count"],
        "knowledge_influence_runs_retrieved_only": impact["influence_chain"]["retrieved_only_run_count"],
        "knowledge_influence_runs_broken": impact["influence_chain"]["broken_chain_run_count"],
        "knowledge_result_runs_analysis_completed": impact["result_feedback_chain"]["analysis_completed_run_count"],
        "knowledge_result_runs_feedback_drafted": impact["result_feedback_chain"]["feedback_draft_run_count"],
        "knowledge_result_runs_feedback_reviewed": impact["result_feedback_chain"]["feedback_reviewed_run_count"],
        "knowledge_result_runs_registration_pending": impact["result_feedback_chain"]["legacy_unregistered_run_count"],
        "knowledge_result_runs_execution_failed": impact["result_feedback_chain"]["execution_failed_run_count"],
        "knowledge_result_runs_broken": impact["result_feedback_chain"]["broken_chain_run_count"],
    }
    report = {
        "schema_version": "research-learning-loop-health-v1",
        "checked_at": checked_at,
        "status": "failed" if failures else ("attention_required" if warnings else "healthy"),
        "metrics": metrics,
        "warnings": sorted(set(warnings)),
        "failures": sorted(set(failures)),
        "knowledge_impact": impact,
        "execution_authorized": False,
    }
    report["health_fingerprint"] = knowledge.semantic_fingerprint(report, "health_fingerprint")
    _validate(repo, HEALTH_SCHEMA, report)
    return report


def refresh_knowledge_impact(
    repo: Path,
    registry_export: dict[str, Any],
    checked_at: str,
) -> dict[str, Any]:
    health_path = repo / REPORT_ROOT / "learning-loop-health.json"
    current = load_document(health_path)
    impact = build_knowledge_impact(repo, registry_export)
    if (
        current.get("knowledge_impact", {}).get("impact_fingerprint")
        == impact["impact_fingerprint"]
    ):
        return {
            "status": "idle",
            "knowledge_snapshot_fingerprint": impact["knowledge_snapshot_fingerprint"],
            "impact_fingerprint": impact["impact_fingerprint"],
            "observed_discovery_runs": impact["observed_discovery_runs"],
            "report_modified": False,
            "execution_authorized": False,
        }
    health = build_health(
        repo,
        registry_export,
        load_document(repo / REPORT_ROOT / "source-refresh-report.json"),
        load_document(repo / REPORT_ROOT / "retrieval-evaluation.json"),
        checked_at,
    )
    write_json(health_path, health)
    return {
        "status": "knowledge_impact_updated",
        "knowledge_snapshot_fingerprint": impact["knowledge_snapshot_fingerprint"],
        "impact_fingerprint": impact["impact_fingerprint"],
        "observed_discovery_runs": impact["observed_discovery_runs"],
        "report_modified": True,
        "execution_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--registry", default="research/registry/stage4a-director.db")
    parser.add_argument("--registry-export", default="research/director/registry-records.json")
    parser.add_argument("--mode", choices=("refresh", "evaluation", "health", "impact"), default="refresh")
    parser.add_argument("--checked-at")
    args = parser.parse_args(argv)
    repo = Path(args.repo_root).resolve()
    checked_at = args.checked_at or utc_now()
    if args.mode == "refresh":
        refresh = build_refresh_report(repo, fetch_remote_heads(), checked_at)
        evaluation = evaluate_retrieval(repo, load_document(repo / "research/director/current-research-state.json"))
        registration = register_lifecycle_and_updates(repo, args.registry, refresh)
        write_json(repo / REPORT_ROOT / "source-refresh-report.json", refresh)
        write_json(repo / REPORT_ROOT / "retrieval-evaluation.json", evaluation)
        result = {"refresh": refresh["summary"], "evaluation": evaluation["status"], "registration": registration}
    elif args.mode == "evaluation":
        evaluation = evaluate_retrieval(repo, load_document(repo / "research/director/current-research-state.json"))
        write_json(repo / REPORT_ROOT / "retrieval-evaluation.json", evaluation)
        result = evaluation
    elif args.mode == "health":
        refresh = load_document(repo / REPORT_ROOT / "source-refresh-report.json")
        evaluation = load_document(repo / REPORT_ROOT / "retrieval-evaluation.json")
        health = build_health(repo, load_document(repo / args.registry_export), refresh, evaluation, checked_at)
        write_json(repo / REPORT_ROOT / "learning-loop-health.json", health)
        result = health
    else:
        result = refresh_knowledge_impact(
            repo,
            load_document(repo / args.registry_export),
            checked_at,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
