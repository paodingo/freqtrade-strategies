#!/usr/bin/env python3
"""Classify failed descriptive jobs and recover only hash-approved transient I/O failures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    sha256_file,
    utc_now,
)


CONTRACT_PATH = Path(
    "research/governance/descriptive-worker-failure-recovery-contract-v1.json"
)
APPROVAL_PATH = Path(
    "research/governance/approvals/descriptive-worker-failure-recovery-v1-approval.json"
)
AUTO_RETRY_EVENT = "descriptive_execution_auto_retry_authorized"


def _semantic_fingerprint(payload: dict[str, Any], field: str) -> str:
    return fingerprint({key: value for key, value in payload.items() if key != field})


def load_recovery_authority(repo_root: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    repo = Path(repo_root).resolve()
    contract_path = repo / CONTRACT_PATH
    approval_path = repo / APPROVAL_PATH
    contract = load_document(contract_path)
    approval = load_document(approval_path)
    expected_classes = {
        "descriptive_worker_io_failed": "transient_io_retriable_once",
        "descriptive_worker_contract_or_input_failed": "deterministic_manual_review",
        "descriptive_worker_internal_failed": "internal_manual_review",
        "unknown": "unknown_manual_review",
    }
    expected_prohibitions = [
        "network_access",
        "backtest",
        "candidate_creation",
        "strategy_mutation",
        "validation_access",
        "holdout_access",
        "trading_execution",
        "lesson_promotion",
        "automatic_successor_creation",
        "retry_scope_expansion",
    ]
    retry_policy = contract.get("automatic_retry_policy", {})
    if (
        contract.get("schema_version")
        != "descriptive-worker-failure-recovery-contract-v1"
        or contract.get("contract_id")
        != "development-descriptive-worker-failure-recovery-v1"
        or contract.get("status") != "active"
        or contract.get("approval_authority") != APPROVAL_PATH.as_posix()
        or contract.get("failure_classes") != expected_classes
        or retry_policy.get("enabled") is not True
        or retry_policy.get("allowed_reason_codes")
        != ["descriptive_worker_io_failed"]
        or retry_policy.get("required_job_status") != "failed"
        or retry_policy.get("required_attempt_count") != 1
        or retry_policy.get("maximum_automatic_retries_per_job") != 1
        or retry_policy.get("maximum_total_attempts") != 2
        or retry_policy.get("maximum_automatic_requeues_per_cycle") != 16
        or retry_policy.get("successful_requeue_notification_required") is not False
        or retry_policy.get("automatic_successor_job_authorized") is not False
        or contract.get("manual_review_policy", {}).get("notification_required")
        is not True
        or contract.get("manual_review_policy", {}).get("automatic_retry_authorized")
        is not False
        or contract.get("prohibited_actions") != expected_prohibitions
        or contract.get("contract_fingerprint")
        != _semantic_fingerprint(contract, "contract_fingerprint")
    ):
        raise ValueError("descriptive worker recovery contract is invalid")
    false_approval_fields = (
        "automatic_internal_error_retry_authorized",
        "automatic_contract_or_input_retry_authorized",
        "automatic_unknown_error_retry_authorized",
        "automatic_successor_job_authorized",
        "network_access_authorized",
        "backtest_authorized",
        "candidate_creation_authorized",
        "strategy_mutation_authorized",
        "trading_execution_authorized",
        "lesson_promotion_authorized",
        "silent_contract_amendment_allowed",
    )
    if (
        approval.get("schema_version")
        != "descriptive-worker-failure-recovery-approval-v1"
        or approval.get("approval_id")
        != "development-descriptive-worker-failure-recovery-v1"
        or approval.get("approval_status") != "approved"
        or approval.get("approver_type") != "human_user"
        or approval.get("authorization_source") != "explicit_user_instruction"
        or not isinstance(approval.get("user_statement"), str)
        or not approval["user_statement"].strip()
        or approval.get("approved_contract_path") != CONTRACT_PATH.as_posix()
        or approval.get("approved_contract_sha256") != sha256_file(contract_path)
        or approval.get("approved_contract_fingerprint")
        != contract["contract_fingerprint"]
        or approval.get("automatic_io_retry_authorized") is not True
        or approval.get("maximum_automatic_retries_per_job") != 1
        or approval.get("maximum_total_attempts") != 2
        or approval.get("maximum_automatic_requeues_per_cycle") != 16
        or approval.get("same_job_requeue_only") is not True
        or any(approval.get(field) is not False for field in false_approval_fields)
        or approval.get("validation_accesses_authorized") != 0
        or approval.get("holdout_accesses_authorized") != 0
        or approval.get("contract_amendment_requires_new_hash_and_human_approval")
        is not True
        or approval.get("approval_fingerprint")
        != _semantic_fingerprint(approval, "approval_fingerprint")
    ):
        raise ValueError("descriptive worker recovery approval is invalid")
    return contract, approval


def _job_events(connection: Any, run_id: str, job_id: str) -> list[dict[str, Any]]:
    events = []
    for row in connection.execute(
        "SELECT event_type,reason_code,payload_json,created_at "
        "FROM research_discovery_events WHERE run_id=? "
        "AND event_type IN ('descriptive_execution_failed',?) ORDER BY created_at,event_id",
        (run_id, AUTO_RETRY_EVENT),
    ):
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            continue
        if payload.get("job_id") == job_id:
            events.append({**dict(row), "payload": payload})
    return events


def _binding_error(
    repo: Path,
    connection: Any,
    job: Any,
    payload: dict[str, Any],
    events: list[dict[str, Any]],
) -> str | None:
    proposal_id = payload.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        return "proposal_id_missing"
    task_path = (repo / str(job["task_path"])).resolve()
    try:
        task_path.relative_to(repo)
    except ValueError:
        return "task_path_outside_repository"
    if not task_path.is_file():
        return "task_file_missing"
    try:
        task = load_document(task_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return "task_document_invalid"
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
    failure_events = [
        item for item in events if item["event_type"] == "descriptive_execution_failed"
    ]
    auto_retry_events = [item for item in events if item["event_type"] == AUTO_RETRY_EVENT]
    if len(matches) != 1:
        return "proposal_binding_missing_or_ambiguous"
    if fingerprint(matches[0]) != payload.get("proposal_payload_fingerprint"):
        return "proposal_payload_fingerprint_mismatch"
    if (
        not isinstance(authorization, dict)
        or authorization.get("descriptive_execution_authorized") is not True
        or authorization.get("campaign_execution_authorized") is not False
        or authorization.get("trading_execution_authorized") is not False
        or authorization.get("strategy_mutation_authorized") is not False
        or authorization.get("exact_artifact_paths") != expected_paths
    ):
        return "descriptive_authorization_drift"
    if any((repo / relative).exists() for relative in expected_paths):
        return "existing_artifact_blocks_retry"
    if len(failure_events) != 1 or failure_events[0]["reason_code"] != "descriptive_worker_io_failed":
        return "failure_event_chain_invalid"
    if auto_retry_events:
        return "automatic_retry_already_recorded"
    if connection.execute(
        "SELECT COUNT(*) FROM research_descriptive_execution_results WHERE job_id=?",
        (job["job_id"],),
    ).fetchone()[0]:
        return "result_already_recorded"
    return None


def _completed_successor_exists(
    connection: Any,
    job: Any,
    payload: dict[str, Any],
) -> bool:
    proposal_id = payload.get("proposal_id")
    if not isinstance(proposal_id, str) or not proposal_id:
        return False
    for later in connection.execute(
        "SELECT payload_json FROM research_worker_jobs WHERE run_id=? "
        "AND stage='descriptive_execution' AND status='completed' AND round_number>?",
        (job["run_id"], job["round_number"]),
    ):
        try:
            later_payload = json.loads(later["payload_json"])
        except json.JSONDecodeError:
            continue
        if later_payload.get("proposal_id") == proposal_id:
            return True
    return False


def _classification(reason_code: str, attempt_count: int, auto_retry_count: int) -> tuple[str, str]:
    if reason_code == "descriptive_worker_io_failed":
        if attempt_count == 1 and auto_retry_count == 0:
            return "transient_io_retriable_once", "automatic_retry_if_bindings_valid"
        return "automatic_retry_exhausted", "explicit_human_review"
    if reason_code == "descriptive_worker_contract_or_input_failed":
        return "deterministic_manual_review", "fix_and_explicit_human_retry"
    if reason_code == "descriptive_worker_internal_failed":
        return "internal_manual_review", "diagnose_and_explicit_human_retry"
    return "unknown_manual_review", "diagnose_and_explicit_human_review"


def reconcile_failures(
    repo_root: str | Path,
    registry_path: str | Path,
    *,
    checked_at: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    contract, approval = load_recovery_authority(repo)
    timestamp = checked_at or utc_now()
    limit = contract["automatic_retry_policy"]["maximum_automatic_requeues_per_cycle"]
    connection = open_director_registry(registry_path)
    auto_retried: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    inspected = 0
    recovered_history_ignored = 0
    try:
        connection.execute("BEGIN IMMEDIATE")
        failed_jobs = connection.execute(
            "SELECT * FROM research_worker_jobs WHERE stage='descriptive_execution' "
            "AND status='failed' ORDER BY updated_at,job_id"
        ).fetchall()
        for job in failed_jobs:
            inspected += 1
            try:
                payload = json.loads(job["payload_json"])
            except json.JSONDecodeError:
                alerts.append(
                    {
                        "job_id": job["job_id"],
                        "run_id": job["run_id"],
                        "reason_code": "worker_payload_invalid",
                        "classification": "recovery_binding_invalid",
                        "required_action": "explicit_human_review",
                    }
                )
                continue
            if _completed_successor_exists(connection, job, payload):
                recovered_history_ignored += 1
                continue
            events = _job_events(connection, str(job["run_id"]), str(job["job_id"]))
            failure_events = [
                item for item in events if item["event_type"] == "descriptive_execution_failed"
            ]
            last_reason = (
                str(failure_events[-1]["reason_code"])
                if failure_events
                else "failure_event_missing"
            )
            auto_retry_count = sum(
                item["event_type"] == AUTO_RETRY_EVENT for item in events
            )
            classification, required_action = _classification(
                last_reason, int(job["attempt_count"]), auto_retry_count
            )
            if (
                classification == "transient_io_retriable_once"
                and len(auto_retried) < limit
            ):
                binding_error = _binding_error(repo, connection, job, payload, events)
                if binding_error is None:
                    event = {
                        "schema_version": "descriptive-worker-auto-retry-event-v1",
                        "run_id": str(job["run_id"]),
                        "job_id": str(job["job_id"]),
                        "proposal_id": payload["proposal_id"],
                        "previous_status": "failed",
                        "status": "queued",
                        "failure_reason_code": last_reason,
                        "classification": classification,
                        "authorized_at": timestamp,
                        "contract_fingerprint": contract["contract_fingerprint"],
                        "approval_fingerprint": approval["approval_fingerprint"],
                        "maximum_total_attempts": 2,
                        "same_job_requeued": True,
                        "automatic_successor_created": False,
                        "candidate_created": False,
                        "strategy_modified": False,
                        "validation_accesses": 0,
                        "holdout_accesses": 0,
                    }
                    event_id = "discovery-event-" + fingerprint(
                        {"event_type": AUTO_RETRY_EVENT, "payload": event}
                    )[:24]
                    connection.execute(
                        "UPDATE research_worker_jobs SET status='queued',updated_at=? "
                        "WHERE job_id=? AND status='failed' AND attempt_count=1",
                        (timestamp, job["job_id"]),
                    )
                    connection.execute(
                        "INSERT INTO research_discovery_events("
                        "event_id,run_id,event_type,reason_code,payload_json,created_at"
                        ") VALUES(?,?,?,?,?,?)",
                        (
                            event_id,
                            job["run_id"],
                            AUTO_RETRY_EVENT,
                            "transient_io_retry_under_approved_contract",
                            json.dumps(event, ensure_ascii=False, sort_keys=True),
                            timestamp,
                        ),
                    )
                    auto_retried.append(
                        {
                            "job_id": str(job["job_id"]),
                            "run_id": str(job["run_id"]),
                            "classification": classification,
                            "maximum_total_attempts": 2,
                        }
                    )
                    continue
                classification = "recovery_binding_invalid"
                required_action = "explicit_human_review"
                alerts.append(
                    {
                        "job_id": str(job["job_id"]),
                        "run_id": str(job["run_id"]),
                        "reason_code": last_reason,
                        "classification": classification,
                        "binding_error": binding_error,
                        "required_action": required_action,
                    }
                )
                continue
            if classification == "transient_io_retriable_once":
                classification = "automatic_retry_deferred_cycle_limit"
                required_action = "next_supervisor_cycle"
            alerts.append(
                {
                    "job_id": str(job["job_id"]),
                    "run_id": str(job["run_id"]),
                    "reason_code": last_reason,
                    "classification": classification,
                    "required_action": required_action,
                }
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    actionable_alerts = [
        item
        for item in alerts
        if item["classification"] != "automatic_retry_deferred_cycle_limit"
    ]
    return {
        "schema_version": "descriptive-worker-failure-recovery-result-v1",
        "status": (
            "attention_required"
            if actionable_alerts
            else "auto_retry_queued" if auto_retried else "idle"
        ),
        "inspected_failed_jobs": inspected,
        "recovered_historical_failures_ignored": recovered_history_ignored,
        "automatic_retries_queued": auto_retried,
        "alerts": alerts,
        "notification_required": bool(actionable_alerts),
        "automatic_successor_jobs_created": 0,
        "candidate_created": False,
        "strategy_modified": False,
        "validation_accesses": 0,
        "holdout_accesses": 0,
    }
