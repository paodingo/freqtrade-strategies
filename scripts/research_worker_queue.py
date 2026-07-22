#!/usr/bin/env python3
"""Provider-neutral, lease-based worker queue for governed Discovery stages."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
)


ALLOWED_STAGES = {"researcher", "critic", "descriptive_execution"}
TERMINAL_STATUSES = {"completed", "failed"}
FEEDBACK_CONTRACT_PATH = Path(
    "research/governance/low-risk-descriptive-knowledge-feedback-contract-v1.json"
)
FEEDBACK_APPROVAL_PATH = Path(
    "research/governance/approvals/low-risk-descriptive-knowledge-feedback-v1-approval.json"
)
LEGACY_MANIFEST_CONTRACT_PATH = Path(
    "research/governance/legacy-development-manifest-compatibility-v1.json"
)
LEGACY_MANIFEST_APPROVAL_PATH = Path(
    "research/governance/approvals/legacy-development-manifest-compatibility-v1-approval.json"
)


def _job_id(run_id: str, stage: str, round_number: int) -> str:
    return f"worker-job-{fingerprint({'run_id': run_id, 'stage': stage, 'round': round_number})[:16]}"


def enqueue_worker_job(
    connection: Any,
    *,
    run_id: str,
    stage: str,
    round_number: int,
    task_path: str,
    inbox_path: str,
    created_at: str,
    authorization: dict[str, object] | None = None,
    proposal_id: str | None = None,
    proposal_payload_fingerprint: str | None = None,
) -> dict[str, object]:
    if stage not in ALLOWED_STAGES or round_number < 1:
        raise ValueError("worker job stage or round is invalid")
    if stage == "descriptive_execution":
        if (
            not isinstance(authorization, dict)
            or authorization.get("descriptive_execution_authorized") is not True
            or authorization.get("campaign_execution_authorized") is not False
            or authorization.get("trading_execution_authorized") is not False
            or authorization.get("strategy_mutation_authorized") is not False
            or not isinstance(authorization.get("authorization_fingerprint"), str)
            or not isinstance(proposal_id, str)
            or not proposal_id.strip()
            or not isinstance(proposal_payload_fingerprint, str)
            or len(proposal_payload_fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in proposal_payload_fingerprint)
        ):
            raise ValueError("descriptive execution authorization is invalid")
    elif authorization is not None or proposal_id is not None or proposal_payload_fingerprint is not None:
        raise ValueError("authorization is only valid for descriptive execution jobs")
    job_id = _job_id(run_id, stage, round_number)
    payload = {
        "schema_version": "research-worker-job-v1",
        "job_id": job_id,
        "run_id": run_id,
        "stage": stage,
        "round_number": round_number,
        "task_path": task_path,
        "inbox_path": inbox_path,
        "provider_neutral": True,
        "candidate_creation_authorized": False,
        "campaign_execution_authorized": False,
        "strategy_mutation_authorized": False,
        "descriptive_execution_authorized": stage == "descriptive_execution",
    }
    if authorization is not None:
        payload["authorization"] = authorization
        payload["proposal_id"] = proposal_id
        payload["proposal_payload_fingerprint"] = proposal_payload_fingerprint
    payload_json = json.dumps(payload, sort_keys=True)
    connection.execute(
        "INSERT OR IGNORE INTO research_worker_jobs("
        "job_id,run_id,stage,round_number,status,task_path,inbox_path,attempt_count,"
        "lease_owner,lease_expires_at,payload_json,created_at,updated_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            job_id,
            run_id,
            stage,
            round_number,
            "queued",
            task_path,
            inbox_path,
            0,
            None,
            None,
            payload_json,
            created_at,
            created_at,
        ),
    )
    row = connection.execute(
        "SELECT * FROM research_worker_jobs WHERE job_id=?", (job_id,)
    ).fetchone()
    if row is None or any(
        row[field] != expected
        for field, expected in {
            "run_id": run_id,
            "stage": stage,
            "round_number": round_number,
            "task_path": task_path,
            "inbox_path": inbox_path,
            "payload_json": payload_json,
            "created_at": created_at,
        }.items()
    ):
        raise ValueError("worker job identity conflict")
    return dict(row)


def enqueue_descriptive_execution_job(
    connection: Any,
    *,
    run_id: str,
    proposal: dict[str, object],
    task_path: str,
    created_at: str,
) -> dict[str, object]:
    proposal_id = str(proposal.get("proposal_id", ""))
    authorization = proposal.get("descriptive_execution_authorization")
    expected_artifacts = [
        f"research/analysis/{proposal_id}/analysis.json",
        f"reports/audits/{proposal_id}/report.md",
    ]
    if (
        not proposal_id
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in proposal_id)
        or proposal.get("risk_class") != "low"
        or proposal.get("execution_authorized") is not False
        or proposal.get("descriptive_execution_authorized") is not True
        or proposal.get("approval_requirement") != "auto_approved_under_constitution"
        or proposal.get("allowed_changes") != expected_artifacts
        or proposal.get("required_artifacts") != expected_artifacts
        or not isinstance(authorization, dict)
        or authorization.get("exact_artifact_paths") != expected_artifacts
    ):
        raise ValueError("proposal is not eligible for descriptive execution queueing")
    return enqueue_worker_job(
        connection,
        run_id=run_id,
        stage="descriptive_execution",
        round_number=1,
        task_path=task_path,
        inbox_path=f"research/analysis/{proposal_id}",
        created_at=created_at,
        authorization=authorization,
        proposal_id=proposal_id,
        proposal_payload_fingerprint=fingerprint(proposal),
    )


def _load_feedback_authority(repo: Path) -> tuple[dict[str, object], dict[str, object]]:
    contract_path = repo / FEEDBACK_CONTRACT_PATH
    approval_path = repo / FEEDBACK_APPROVAL_PATH
    contract = load_document(contract_path)
    approval = load_document(approval_path)
    execution_contract_path = repo / str(contract.get("prerequisite_execution_contract_path", ""))
    if (
        contract.get("schema_version")
        != "low-risk-descriptive-knowledge-feedback-contract-v1"
        or contract.get("status") != "active"
        or approval.get("approval_status") != "approved"
        or approval.get("approver_type") != "human_user"
        or approval.get("approved_contract_path") != FEEDBACK_CONTRACT_PATH.as_posix()
        or approval.get("approved_contract_sha256") != sha256_file(contract_path)
        or approval.get("approved_automatic_actions") != contract.get("automatic_actions")
        or approval.get("automatic_feedback_approval_authorized") is not False
        or approval.get("automatic_lesson_promotion_authorized") is not False
        or approval.get("strategy_mutation_authorized") is not False
        or contract.get("knowledge_semantics", {}).get("draft_status")
        != "pending_human_review"
        or contract.get("knowledge_semantics", {}).get("trusted_broker_lesson") is not False
        or contract.get("knowledge_semantics", {}).get("automatic_lesson_promotion_authorized")
        is not False
        or contract.get("prerequisite_execution_contract_sha256")
        != sha256_file(execution_contract_path)
    ):
        raise ValueError("descriptive feedback authority is invalid or drifted")
    return contract, approval


def _validated_descriptive_result(
    repo: Path,
    job: Any,
    result_code: str,
    completed_at: str,
) -> dict[str, object]:
    if not result_code.strip():
        raise ValueError("descriptive result code is required")
    payload = json.loads(job["payload_json"])
    authorization = payload.get("authorization")
    proposal_id = payload.get("proposal_id")
    if (
        job["stage"] != "descriptive_execution"
        or payload.get("descriptive_execution_authorized") is not True
        or payload.get("campaign_execution_authorized") is not False
        or payload.get("candidate_creation_authorized") is not False
        or payload.get("strategy_mutation_authorized") is not False
        or not isinstance(authorization, dict)
        or authorization.get("descriptive_execution_authorized") is not True
        or authorization.get("campaign_execution_authorized") is not False
        or authorization.get("trading_execution_authorized") is not False
        or authorization.get("strategy_mutation_authorized") is not False
        or fingerprint({k: v for k, v in authorization.items() if k != "authorization_fingerprint"})
        != authorization.get("authorization_fingerprint")
        or not isinstance(proposal_id, str)
        or not proposal_id
        or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in proposal_id)
    ):
        raise ValueError("descriptive result job authority is invalid")
    expected_paths = [
        f"research/analysis/{proposal_id}/analysis.json",
        f"reports/audits/{proposal_id}/report.md",
    ]
    if authorization.get("exact_artifact_paths") != expected_paths:
        raise ValueError("descriptive result artifact scope is invalid")
    analysis_path, report_path = (repo / relative for relative in expected_paths)
    if not analysis_path.is_file() or not report_path.is_file():
        raise ValueError("descriptive result artifacts are incomplete")
    analysis = load_document(analysis_path)
    scope = analysis.get("execution_scope")
    integrity = analysis.get("source_integrity")
    if (
        analysis.get("proposal_id") != proposal_id
        or not isinstance(scope, dict)
        or scope.get("development_only") is not True
        or scope.get("network_accessed") is not False
        or any(
            scope.get(field) != 0
            for field in (
                "validation_accesses",
                "holdout_accesses",
                "backtests",
                "signals_or_trades_generated",
                "candidates_created",
                "strategy_changes",
                "promotions",
            )
        )
        or not isinstance(integrity, dict)
        or integrity.get("all_ok") is not True
    ):
        raise ValueError("descriptive result attestation failed")
    evidence_artifacts = [
        {"path": expected_paths[0], "sha256": sha256_file(analysis_path)},
        {"path": expected_paths[1], "sha256": sha256_file(report_path)},
    ]
    result = {
        "schema_version": "research-descriptive-execution-result-v1",
        "source_kind": "descriptive_execution",
        "result_id": f"descriptive-result-{fingerprint({'job_id': job['job_id'], 'proposal_id': proposal_id})[:16]}",
        "job_id": str(job["job_id"]),
        "run_id": str(job["run_id"]),
        "proposal_id": proposal_id,
        "result_code": result_code,
        "authorization_fingerprint": str(authorization["authorization_fingerprint"]),
        "evidence_artifacts": evidence_artifacts,
        "execution_attestation": {
            "development_only": True,
            "network_accessed": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
            "backtests": 0,
            "signals_or_trades_generated": 0,
            "candidates_created": 0,
            "strategy_changes": 0,
            "promotions": 0,
        },
        "completed_at": completed_at,
        "completed_by_worker": str(job["lease_owner"]),
        "automatic_lesson_promotion_authorized": False,
        "strategy_mutation_authorized": False,
    }
    result["result_fingerprint"] = fingerprint(result)
    return result


def finish_descriptive_execution_job(
    repo_root: str | Path,
    registry_path: str | Path,
    job_id: str,
    worker_id: str,
    result_code: str,
    *,
    updated_at: str | None = None,
) -> dict[str, object]:
    """Record a bounded descriptive result and queue review-only feedback atomically."""
    repo = Path(repo_root).resolve()
    _load_feedback_authority(repo)
    timestamp = updated_at or utc_now()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        job = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        existing = connection.execute(
            "SELECT * FROM research_descriptive_execution_results WHERE job_id=?", (job_id,)
        ).fetchone()
        if existing is not None:
            stored = json.loads(existing["payload_json"])
            artifacts = stored.get("evidence_artifacts", [])
            feedback = connection.execute(
                "SELECT review_status FROM research_lesson_feedback_drafts WHERE feedback_id=?",
                (f"feedback-{stored.get('result_id', '')}",),
            ).fetchone()
            if (
                job is None
                or job["status"] != "completed"
                or feedback is None
                or stored.get("completed_by_worker") != worker_id
                or stored.get("result_code") != result_code
                or len(artifacts) != 2
                or any(
                    sha256_file(repo / str(item["path"])) != item["sha256"]
                    for item in artifacts
                )
            ):
                raise ValueError("descriptive result replay conflict")
            connection.commit()
            return {
                **stored,
                "feedback_id": f"feedback-{stored['result_id']}",
                "review_status": str(feedback["review_status"]),
            }
        if job is None or job["status"] != "claimed" or job["lease_owner"] != worker_id:
            raise ValueError("worker job lease ownership mismatch")
        result = _validated_descriptive_result(repo, job, result_code, timestamp)
        artifacts = result["evidence_artifacts"]
        result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
        connection.execute(
            "INSERT INTO research_descriptive_execution_results("
            "result_id,job_id,run_id,proposal_id,result_code,authorization_fingerprint,"
            "analysis_path,analysis_sha256,report_path,report_sha256,payload_json,completed_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                result["result_id"], job_id, job["run_id"], result["proposal_id"], result_code,
                result["authorization_fingerprint"], artifacts[0]["path"], artifacts[0]["sha256"],
                artifacts[1]["path"], artifacts[1]["sha256"], result_json, timestamp,
            ),
        )
        feedback_id = f"feedback-{result['result_id']}"
        connection.execute(
            "INSERT INTO research_lesson_feedback_drafts("
            "feedback_id,run_id,campaign_id,proposal_id,result_code,review_status,payload_json,created_at"
            ") VALUES(?,?,?,?,?,?,?,?)",
            (
                feedback_id, job["run_id"], "descriptive_execution", result["proposal_id"],
                result_code, "pending_human_review", result_json, timestamp,
            ),
        )
        connection.execute(
            "UPDATE research_worker_jobs SET status='completed',lease_owner=NULL,lease_expires_at=NULL,"
            "updated_at=? WHERE job_id=?",
            (timestamp, job_id),
        )
        connection.commit()
        return {**result, "feedback_id": feedback_id, "review_status": "pending_human_review"}
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def claim_next_job(
    registry_path: str | Path,
    worker_id: str,
    *,
    lease_seconds: int = 300,
    now: str | None = None,
    stages: set[str] | None = None,
) -> dict[str, object] | None:
    if not worker_id.strip() or lease_seconds < 1 or lease_seconds > 3600:
        raise ValueError("worker claim parameters are invalid")
    claimed_at = now or utc_now()
    selected_stages = sorted(stages or ALLOWED_STAGES)
    if not selected_stages or any(stage not in ALLOWED_STAGES for stage in selected_stages):
        raise ValueError("worker claim stage filter is invalid")
    claimed_dt = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
    if claimed_dt.tzinfo is None:
        claimed_dt = claimed_dt.replace(tzinfo=timezone.utc)
    lease_expires_at = (claimed_dt + timedelta(seconds=lease_seconds)).isoformat()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        placeholders = ",".join("?" for _ in selected_stages)
        row = connection.execute(
            "SELECT job_id FROM research_worker_jobs WHERE stage IN ("
            + placeholders
            + ") AND (status='queued' OR (status='claimed' AND lease_expires_at<=?)) "
            "ORDER BY created_at,job_id LIMIT 1",
            (*selected_stages, claimed_at),
        ).fetchone()
        if row is None:
            connection.commit()
            return None
        connection.execute(
            "UPDATE research_worker_jobs SET status='claimed',attempt_count=attempt_count+1,"
            "lease_owner=?,lease_expires_at=?,updated_at=? WHERE job_id=?",
            (worker_id, lease_expires_at, claimed_at, row["job_id"]),
        )
        claimed = dict(
            connection.execute(
                "SELECT * FROM research_worker_jobs WHERE job_id=?", (row["job_id"],)
            ).fetchone()
        )
        connection.commit()
        return claimed
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def finish_job(
    registry_path: str | Path,
    job_id: str,
    worker_id: str,
    status: str,
    *,
    updated_at: str | None = None,
) -> dict[str, object]:
    if status not in TERMINAL_STATUSES:
        raise ValueError("worker terminal status is invalid")
    timestamp = updated_at or utc_now()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if row is None or row["status"] != "claimed" or row["lease_owner"] != worker_id:
            raise ValueError("worker job lease ownership mismatch")
        if row["stage"] == "descriptive_execution" and status == "completed":
            raise ValueError("descriptive execution completion requires verified result recording")
        connection.execute(
            "UPDATE research_worker_jobs SET status=?,lease_owner=NULL,lease_expires_at=NULL,"
            "updated_at=? WHERE job_id=?",
            (status, timestamp, job_id),
        )
        result = dict(
            connection.execute(
                "SELECT * FROM research_worker_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fail_descriptive_execution_job(
    registry_path: str | Path,
    job_id: str,
    worker_id: str,
    reason_code: str,
    *,
    updated_at: str | None = None,
) -> dict[str, object]:
    """Fail one claimed descriptive job and persist a sanitized audit event atomically."""
    if (
        not reason_code
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in reason_code)
    ):
        raise ValueError("descriptive worker failure reason is invalid")
    timestamp = updated_at or utc_now()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        job = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if (
            job is None
            or job["stage"] != "descriptive_execution"
            or job["status"] != "claimed"
            or job["lease_owner"] != worker_id
        ):
            raise ValueError("worker job lease ownership mismatch")
        payload = {
            "schema_version": "research-descriptive-worker-failure-v1",
            "run_id": str(job["run_id"]),
            "job_id": job_id,
            "attempt_count": int(job["attempt_count"]),
            "status": "failed",
            "reason_code": reason_code,
            "failed_at": timestamp,
            "artifacts_accepted": False,
            "feedback_draft_created": False,
            "candidate_created": False,
            "strategy_modified": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        event_id = "discovery-event-" + fingerprint(
            {"event_type": "descriptive_execution_failed", "payload": payload}
        )[:24]
        connection.execute(
            "UPDATE research_worker_jobs SET status='failed',lease_owner=NULL,lease_expires_at=NULL,"
            "updated_at=? WHERE job_id=?",
            (timestamp, job_id),
        )
        connection.execute(
            "INSERT INTO research_discovery_events("
            "event_id,run_id,event_type,reason_code,payload_json,created_at"
            ") VALUES(?,?,?,?,?,?)",
            (
                event_id,
                job["run_id"],
                "descriptive_execution_failed",
                reason_code,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
        connection.commit()
        return payload
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def retry_failed_descriptive_execution_job(
    repo_root: str | Path,
    registry_path: str | Path,
    job_id: str,
    reviewer_type: str,
    reason_code: str,
    reason_zh: str,
    *,
    updated_at: str | None = None,
) -> dict[str, object]:
    """Requeue one failed descriptive job under explicit human authorization."""
    if (
        reviewer_type != "human_user"
        or not job_id.strip()
        or not reason_code.strip()
        or not reason_zh.strip()
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_"
            for character in reason_code
        )
    ):
        raise ValueError("descriptive retry authorization is invalid")
    timestamp = updated_at or utc_now()
    repo = Path(repo_root).resolve()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        job = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        if (
            job is None
            or job["stage"] != "descriptive_execution"
            or job["status"] != "failed"
            or job["attempt_count"] != 1
            or job["lease_owner"] is not None
            or job["lease_expires_at"] is not None
        ):
            raise ValueError("descriptive job is not eligible for one human retry")
        payload = json.loads(job["payload_json"])
        proposal_id = payload.get("proposal_id")
        task_path = (repo / str(job["task_path"])).resolve()
        try:
            task_path.relative_to(repo)
        except ValueError as exc:
            raise ValueError("descriptive retry task path is outside repository") from exc
        task = load_document(task_path)
        proposals = task.get("proposals")
        matches = (
            [item for item in proposals if item.get("proposal_id") == proposal_id]
            if isinstance(proposals, list)
            else []
        )
        authorization = payload.get("authorization")
        expected_paths = [
            f"research/analysis/{proposal_id}/analysis.json",
            f"reports/audits/{proposal_id}/report.md",
        ]
        if (
            len(matches) != 1
            or fingerprint(matches[0]) != payload.get("proposal_payload_fingerprint")
            or not isinstance(authorization, dict)
            or authorization.get("descriptive_execution_authorized") is not True
            or authorization.get("campaign_execution_authorized") is not False
            or authorization.get("trading_execution_authorized") is not False
            or authorization.get("strategy_mutation_authorized") is not False
            or authorization.get("exact_artifact_paths") != expected_paths
            or any((repo / relative).exists() for relative in expected_paths)
        ):
            raise ValueError("descriptive retry proposal binding or artifact scope drifted")
        failure_events = connection.execute(
            "SELECT * FROM research_discovery_events WHERE run_id=? "
            "AND event_type='descriptive_execution_failed' ORDER BY created_at",
            (job["run_id"],),
        ).fetchall()
        retry_events = connection.execute(
            "SELECT * FROM research_discovery_events WHERE run_id=? "
            "AND event_type='descriptive_execution_retry_authorized'",
            (job["run_id"],),
        ).fetchall()
        result_count = connection.execute(
            "SELECT COUNT(*) FROM research_descriptive_execution_results WHERE job_id=?",
            (job_id,),
        ).fetchone()[0]
        if (
            len(failure_events) != 1
            or failure_events[0]["reason_code"]
            != "descriptive_worker_contract_or_input_failed"
            or retry_events
            or result_count
        ):
            raise ValueError("descriptive retry audit chain is not eligible")
        event = {
            "schema_version": "research-descriptive-worker-retry-authorization-v1",
            "run_id": str(job["run_id"]),
            "job_id": job_id,
            "proposal_id": proposal_id,
            "reviewer_type": reviewer_type,
            "reason_code": reason_code,
            "reason_zh": reason_zh,
            "previous_status": "failed",
            "status": "queued",
            "authorized_at": timestamp,
            "maximum_total_attempts": 2,
            "candidate_created": False,
            "strategy_modified": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        event_id = "discovery-event-" + fingerprint(
            {"event_type": "descriptive_execution_retry_authorized", "payload": event}
        )[:24]
        connection.execute(
            "UPDATE research_worker_jobs SET status='queued',updated_at=? WHERE job_id=?",
            (timestamp, job_id),
        )
        connection.execute(
            "INSERT INTO research_discovery_events("
            "event_id,run_id,event_type,reason_code,payload_json,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                event_id,
                job["run_id"],
                "descriptive_execution_retry_authorized",
                reason_code,
                json.dumps(event, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
        connection.commit()
        return event
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def enqueue_successor_descriptive_execution_job(
    repo_root: str | Path,
    registry_path: str | Path,
    failed_job_id: str,
    reviewer_type: str,
    reason_code: str,
    reason_zh: str,
    *,
    created_at: str | None = None,
) -> dict[str, object]:
    """Create one new round-2 job after an exhausted failed job; never revive it."""
    if (
        reviewer_type != "human_user"
        or not failed_job_id.strip()
        or not reason_code.strip()
        or not reason_zh.strip()
        or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789_"
            for character in reason_code
        )
    ):
        raise ValueError("descriptive successor authorization is invalid")
    timestamp = created_at or utc_now()
    repo = Path(repo_root).resolve()
    contract_path = repo / LEGACY_MANIFEST_CONTRACT_PATH
    approval_path = repo / LEGACY_MANIFEST_APPROVAL_PATH
    contract = load_document(contract_path)
    approval = load_document(approval_path)
    if (
        contract.get("schema_version")
        != "legacy-development-manifest-compatibility-v1"
        or contract.get("status") != "active"
        or contract.get("approval_authority")
        != LEGACY_MANIFEST_APPROVAL_PATH.as_posix()
        or approval.get("approval_status") != "approved"
        or approval.get("approver_type") != "human_user"
        or approval.get("approved_contract_path")
        != LEGACY_MANIFEST_CONTRACT_PATH.as_posix()
        or approval.get("approved_contract_sha256") != sha256_file(contract_path)
        or approval.get("single_successor_descriptive_job_authorized") is not True
        or approval.get("failed_job_revival_authorized") is not False
    ):
        raise ValueError("descriptive successor approval authority is invalid or drifted")
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        failed_job = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE job_id=?", (failed_job_id,)
        ).fetchone()
        if (
            failed_job is None
            or failed_job["stage"] != "descriptive_execution"
            or failed_job["round_number"] != 1
            or failed_job["status"] != "failed"
            or failed_job["attempt_count"] != 2
            or failed_job["lease_owner"] is not None
            or failed_job["lease_expires_at"] is not None
        ):
            raise ValueError("failed descriptive job is not eligible for a successor")
        payload = json.loads(failed_job["payload_json"])
        proposal_id = str(payload.get("proposal_id", ""))
        task_path = (repo / str(failed_job["task_path"])).resolve()
        try:
            task_path.relative_to(repo)
        except ValueError as exc:
            raise ValueError("descriptive successor task path is outside repository") from exc
        task = load_document(task_path)
        proposals = task.get("proposals")
        matches = (
            [item for item in proposals if item.get("proposal_id") == proposal_id]
            if isinstance(proposals, list)
            else []
        )
        authorization = payload.get("authorization")
        expected_paths = [
            f"research/analysis/{proposal_id}/analysis.json",
            f"reports/audits/{proposal_id}/report.md",
        ]
        if (
            len(matches) != 1
            or fingerprint(matches[0]) != payload.get("proposal_payload_fingerprint")
            or not isinstance(authorization, dict)
            or authorization.get("exact_artifact_paths") != expected_paths
            or any((repo / relative).exists() for relative in expected_paths)
            or connection.execute(
                "SELECT COUNT(*) FROM research_descriptive_execution_results WHERE run_id=? AND proposal_id=?",
                (failed_job["run_id"], proposal_id),
            ).fetchone()[0]
        ):
            raise ValueError("descriptive successor proposal binding or artifact scope drifted")
        failure_count = connection.execute(
            "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
            "AND event_type='descriptive_execution_failed'",
            (failed_job["run_id"],),
        ).fetchone()[0]
        retry_count = connection.execute(
            "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
            "AND event_type='descriptive_execution_retry_authorized'",
            (failed_job["run_id"],),
        ).fetchone()[0]
        successor_count = connection.execute(
            "SELECT COUNT(*) FROM research_discovery_events WHERE run_id=? "
            "AND event_type='descriptive_execution_successor_authorized'",
            (failed_job["run_id"],),
        ).fetchone()[0]
        if failure_count != 2 or retry_count != 1 or successor_count != 0:
            raise ValueError("descriptive successor audit chain is not eligible")
        successor = enqueue_worker_job(
            connection,
            run_id=str(failed_job["run_id"]),
            stage="descriptive_execution",
            round_number=2,
            task_path=str(failed_job["task_path"]),
            inbox_path=str(failed_job["inbox_path"]),
            created_at=timestamp,
            authorization=authorization,
            proposal_id=proposal_id,
            proposal_payload_fingerprint=str(
                payload["proposal_payload_fingerprint"]
            ),
        )
        event = {
            "schema_version": "research-descriptive-worker-successor-authorization-v1",
            "run_id": str(failed_job["run_id"]),
            "failed_job_id": failed_job_id,
            "successor_job_id": str(successor["job_id"]),
            "proposal_id": proposal_id,
            "reviewer_type": reviewer_type,
            "reason_code": reason_code,
            "reason_zh": reason_zh,
            "status": "successor_queued",
            "authorized_at": timestamp,
            "failed_job_revived": False,
            "candidate_created": False,
            "strategy_modified": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        event_id = "discovery-event-" + fingerprint(
            {
                "event_type": "descriptive_execution_successor_authorized",
                "payload": event,
            }
        )[:24]
        connection.execute(
            "INSERT INTO research_discovery_events("
            "event_id,run_id,event_type,reason_code,payload_json,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                event_id,
                failed_job["run_id"],
                "descriptive_execution_successor_authorized",
                reason_code,
                json.dumps(event, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
        connection.commit()
        return event
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def defer_run_before_research(
    registry_path: str | Path,
    run_id: str,
    reason_code: str,
    reason_zh: str,
    *,
    updated_at: str | None = None,
) -> dict[str, object]:
    """Atomically defer an untouched Discovery run and its queued researcher job."""
    if (
        not run_id.strip()
        or not reason_code.strip()
        or not reason_zh.strip()
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in reason_code)
    ):
        raise ValueError("pre-research deferral parameters are invalid")
    timestamp = updated_at or utc_now()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        run = connection.execute(
            "SELECT * FROM research_discovery_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if run is None:
            raise ValueError("discovery run is missing")

        jobs = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE run_id=? ORDER BY stage,round_number",
            (run_id,),
        ).fetchall()
        event_rows = connection.execute(
            "SELECT * FROM research_discovery_events "
            "WHERE run_id=? AND event_type='pre_research_deferred'",
            (run_id,),
        ).fetchall()
        if run["status"] == "deferred":
            if (
                len(jobs) != 1
                or jobs[0]["stage"] != "researcher"
                or jobs[0]["round_number"] != 1
                or jobs[0]["status"] != "deferred"
                or len(event_rows) != 1
            ):
                raise ValueError("pre-research deferral replay conflict")
            event = json.loads(event_rows[0]["payload_json"])
            if (
                event.get("reason_code") != reason_code
                or event.get("reason_zh") != reason_zh
            ):
                raise ValueError("pre-research deferral replay conflict")
            connection.commit()
            return event

        if run["status"] != "awaiting_researcher" or event_rows:
            raise ValueError("discovery run is not eligible for pre-research deferral")
        if (
            len(jobs) != 1
            or jobs[0]["stage"] != "researcher"
            or jobs[0]["round_number"] != 1
            or jobs[0]["status"] != "queued"
            or jobs[0]["attempt_count"] != 0
        ):
            raise ValueError("researcher job is not eligible for deferral")
        for table in (
            "research_discovery_ideas",
            "research_discovery_critiques",
            "research_discovery_shortlists",
            "research_discovery_approvals",
            "research_discovery_handoffs",
        ):
            count = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE run_id=?", (run_id,)
            ).fetchone()[0]
            if count:
                raise ValueError("discovery run already has downstream research artifacts")

        run_payload = json.loads(run["payload_json"])
        run_payload["status"] = "deferred"
        run_payload["deferral_reason_code"] = reason_code
        run_payload["deferred_at"] = timestamp
        event = {
            "schema_version": "pre-research-discovery-deferral-v1",
            "run_id": run_id,
            "job_id": jobs[0]["job_id"],
            "previous_status": "awaiting_researcher",
            "status": "deferred",
            "reason_code": reason_code,
            "reason_zh": reason_zh,
            "deferred_at": timestamp,
            "candidate_created": False,
            "campaign_started": False,
        }
        event_id = "discovery-event-" + fingerprint(
            {"event_type": "pre_research_deferred", "payload": event}
        )[:24]
        connection.execute(
            "UPDATE research_discovery_runs SET status=?,payload_json=? WHERE run_id=?",
            ("deferred", json.dumps(run_payload, sort_keys=True), run_id),
        )
        connection.execute(
            "UPDATE research_worker_jobs SET status='deferred',lease_owner=NULL,"
            "lease_expires_at=NULL,updated_at=? WHERE job_id=?",
            (timestamp, jobs[0]["job_id"]),
        )
        connection.execute(
            "INSERT INTO research_discovery_events("
            "event_id,run_id,event_type,reason_code,payload_json,created_at"
            ") VALUES(?,?,?,?,?,?)",
            (
                event_id,
                run_id,
                "pre_research_deferred",
                reason_code,
                json.dumps(event, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
        connection.commit()
        return event
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--claim", action="store_true")
    parser.add_argument("--finish-job")
    parser.add_argument("--retry-failed-job")
    parser.add_argument("--enqueue-successor-job")
    parser.add_argument("--defer-run")
    parser.add_argument("--reviewer-type")
    parser.add_argument("--reason-code")
    parser.add_argument("--reason-zh")
    parser.add_argument("--status", choices=sorted(TERMINAL_STATUSES))
    parser.add_argument("--result-code")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--stage", action="append", choices=sorted(ALLOWED_STAGES))
    args = parser.parse_args(argv)
    if sum(
        (
            args.claim,
            bool(args.finish_job),
            bool(args.retry_failed_job),
            bool(args.enqueue_successor_job),
            bool(args.defer_run),
        )
    ) != 1:
        parser.error(
            "choose exactly one of --claim, --finish-job, --retry-failed-job, --enqueue-successor-job or --defer-run"
        )
    if args.claim:
        result = claim_next_job(
            args.registry,
            args.worker_id,
            lease_seconds=args.lease_seconds,
            stages=set(args.stage) if args.stage else None,
        )
    elif args.finish_job:
        if not args.status:
            parser.error("--status is required with --finish-job")
        if args.result_code:
            if args.status != "completed":
                parser.error("--result-code requires --status completed")
            result = finish_descriptive_execution_job(
                args.repo_root,
                args.registry,
                args.finish_job,
                args.worker_id,
                args.result_code,
            )
        else:
            result = finish_job(args.registry, args.finish_job, args.worker_id, args.status)
    elif args.retry_failed_job:
        if (
            args.status
            or args.result_code
            or not args.reason_code
            or not args.reason_zh
            or not args.reviewer_type
        ):
            parser.error(
                "--reviewer-type, --reason-code and --reason-zh are required with --retry-failed-job"
            )
        result = retry_failed_descriptive_execution_job(
            args.repo_root,
            args.registry,
            args.retry_failed_job,
            args.reviewer_type,
            args.reason_code,
            args.reason_zh,
        )
    elif args.enqueue_successor_job:
        if (
            args.status
            or args.result_code
            or not args.reason_code
            or not args.reason_zh
            or not args.reviewer_type
        ):
            parser.error(
                "--reviewer-type, --reason-code and --reason-zh are required with --enqueue-successor-job"
            )
        result = enqueue_successor_descriptive_execution_job(
            args.repo_root,
            args.registry,
            args.enqueue_successor_job,
            args.reviewer_type,
            args.reason_code,
            args.reason_zh,
        )
    else:
        if args.status or not args.reason_code or not args.reason_zh:
            parser.error("--reason-code and --reason-zh are required with --defer-run")
        result = defer_run_before_research(
            args.registry,
            args.defer_run,
            args.reason_code,
            args.reason_zh,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
