#!/usr/bin/env python3
"""Run one governed, bounded descriptive Worker supervision cycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import export_director_registry
import research_descriptive_worker as descriptive_worker
import research_knowledge_advisory
import research_knowledge_batcher as knowledge_batcher
import research_review_sla
import research_supervisor_ledger as supervisor_ledger
import research_worker_recovery as worker_recovery
from research_director_common import fingerprint, load_document, sha256_file, utc_now


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("research/director/descriptive-worker-supervisor-v1.json")
DEFAULT_APPROVAL = Path(
    "research/governance/approvals/"
    "development-descriptive-worker-supervisor-v1-approval.json"
)


def _repo_file(repo: Path, relative: str | Path, label: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"{label} path must be repo-relative")
    resolved = (repo / path).resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise ValueError(f"{label} path escapes repository") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} file is missing")
    return resolved


def _semantic_fingerprint(payload: dict[str, Any], field: str) -> str:
    return fingerprint({key: value for key, value in payload.items() if key != field})


def _config(
    repo: Path, relative: str | Path
) -> tuple[dict[str, Any], dict[str, str]]:
    path = Path(relative)
    resolved = _repo_file(repo, path, "supervisor config")
    config = load_document(resolved)
    expected_config_keys = {
        "schema_version",
        "supervisor_id",
        "status",
        "approval_path",
        "registry_path",
        "worker_id",
        "stage",
        "schedule_interval_minutes",
        "max_jobs_per_run",
        "lease_seconds",
        "notification_policy",
        "concurrency_control",
        "run_ledger",
        "failure_recovery",
        "knowledge_review_batching",
        "success_behavior",
        "failure_behavior",
        "prohibited_actions",
        "config_fingerprint",
    }
    if set(config) != expected_config_keys:
        raise ValueError("descriptive worker supervisor config fields are invalid")
    config_fingerprint = config.get("config_fingerprint")
    if (
        not isinstance(config_fingerprint, str)
        or _semantic_fingerprint(config, "config_fingerprint")
        != config_fingerprint
    ):
        raise ValueError("descriptive worker supervisor config fingerprint mismatch")

    approval_relative = config.get("approval_path")
    if approval_relative != DEFAULT_APPROVAL.as_posix():
        raise ValueError("descriptive worker supervisor approval path is invalid")
    approval_path = _repo_file(repo, DEFAULT_APPROVAL, "supervisor approval")
    approval = load_document(approval_path)
    expected_approval_keys = {
        "schema_version",
        "approval_id",
        "approval_status",
        "approver_type",
        "approved_at",
        "authorization_source",
        "user_statement",
        "approved_config_path",
        "approved_config_sha256",
        "approved_config_fingerprint",
        "approved_scope",
        "approved_automatic_actions",
        "network_access_authorized",
        "backtest_authorized",
        "candidate_creation_authorized",
        "strategy_mutation_authorized",
        "validation_accesses_authorized",
        "holdout_accesses_authorized",
        "trading_execution_authorized",
        "automatic_decision_authorized",
        "automatic_application_authorized",
        "automatic_lesson_promotion_authorized",
        "silent_config_amendment_allowed",
        "config_amendment_requires_new_hash_and_human_approval",
        "approval_fingerprint",
    }
    approval_fingerprint = approval.get("approval_fingerprint")
    expected_automatic_actions = [
        "acquire_and_renew_supervisor_global_lease",
        "record_supervisor_run_ledger_events",
        "fail_stale_run_then_takeover_expired_lease",
        "classify_failed_descriptive_jobs",
        "requeue_one_hash_approved_transient_io_failure",
        "claim_at_most_once_batched_review_sla_notifications",
        "drain_allowlisted_descriptive_execution_jobs",
        "evaluate_knowledge_review_batch_threshold",
        "publish_immutable_human_review_handoff",
        "validate_existing_local_evidence_advisory",
    ]
    expected_false_authorizations = (
        "network_access_authorized",
        "backtest_authorized",
        "candidate_creation_authorized",
        "strategy_mutation_authorized",
        "trading_execution_authorized",
        "automatic_decision_authorized",
        "automatic_application_authorized",
        "automatic_lesson_promotion_authorized",
        "silent_config_amendment_allowed",
    )
    if (
        set(approval) != expected_approval_keys
        or approval.get("schema_version")
        != "development-descriptive-worker-supervisor-approval-v1"
        or approval.get("approval_id")
        != "development-descriptive-worker-supervisor-v1"
        or approval.get("approval_status") != "approved"
        or approval.get("approver_type") != "human_user"
        or approval.get("authorization_source") != "explicit_user_instruction"
        or not isinstance(approval.get("user_statement"), str)
        or not approval["user_statement"].strip()
        or approval.get("approved_config_path") != path.as_posix()
        or approval.get("approved_config_sha256") != sha256_file(resolved)
        or approval.get("approved_config_fingerprint") != config_fingerprint
        or approval.get("approved_automatic_actions") != expected_automatic_actions
        or any(approval.get(field) is not False for field in expected_false_authorizations)
        or approval.get("validation_accesses_authorized") != 0
        or approval.get("holdout_accesses_authorized") != 0
        or approval.get("config_amendment_requires_new_hash_and_human_approval")
        is not True
        or not isinstance(approval_fingerprint, str)
        or _semantic_fingerprint(approval, "approval_fingerprint")
        != approval_fingerprint
    ):
        raise ValueError("descriptive worker supervisor approval binding is invalid")
    expected_prohibitions = [
        "network_access",
        "backtest",
        "candidate_creation",
        "strategy_mutation",
        "validation_access",
        "holdout_access",
        "trading_execution",
        "lesson_promotion",
    ]
    expected_concurrency_control = {
        "enabled": True,
        "lock_name": "development-descriptive-worker-supervisor",
        "lease_seconds": 7200,
        "contention_behavior": "skip_cycle_record_ledger",
        "stale_lock_behavior": "fail_stale_run_then_takeover",
        "heartbeat_between_jobs": True,
    }
    expected_run_ledger = {
        "enabled": True,
        "storage": "director_registry",
        "event_types": [
            "started",
            "completed",
            "failed",
            "skipped_lock_held",
        ],
        "result_fingerprint": True,
        "execution_authorized": False,
    }
    expected_failure_recovery = {
        "enabled": True,
        "contract_path": (
            "research/governance/"
            "descriptive-worker-failure-recovery-contract-v1.json"
        ),
        "contract_sha256": (
            "c19834befb1b817cebdbde4b235fef1402bc6a1ecc45e99eda63e8b7e407b193"
        ),
        "approval_path": (
            "research/governance/approvals/"
            "descriptive-worker-failure-recovery-v1-approval.json"
        ),
        "approval_sha256": (
            "abb30f1084d44eff10299eea752bc61224b8ecf874131571c5276948a4514c9b"
        ),
        "automatic_retry_reason_codes": ["descriptive_worker_io_failed"],
        "maximum_automatic_retries_per_job": 1,
        "maximum_total_attempts": 2,
        "maximum_automatic_requeues_per_cycle": 16,
        "manual_review_for_all_other_failures": True,
        "automatic_successor_creation_authorized": False,
    }
    expected_knowledge_review = {
        "enabled": True,
        "policy_path": "research/director/knowledge-review-batch-policy-v1.json",
        "policy_sha256": (
            "c5db0b366ec83c46b9020e4b7552adfe6b59e4c9180a80e07c881e0c185af429"
        ),
        "check_interval_minutes": 60,
        "idle_behavior": "silent_no_write",
        "threshold_behavior": "publish_immutable_human_review_handoff",
        "advisory_behavior": "draft_validate_before_single_notification",
        "advisor_prompt_path": (
            "research/knowledge/prompts/knowledge-review-advisor-v1.md"
        ),
        "advisor_prompt_sha256": (
            "e09eadc7e2fe353ef3fb5009f2dfc6139a2a6467969529545a3603d183dbb2b8"
        ),
        "review_sla_policy_path": (
            "research/director/knowledge-review-sla-policy-v1.json"
        ),
        "review_sla_policy_sha256": (
            "3046bc5217cfb59566da5870300d5a05e96950a691c322c5f6f59de9040e851e"
        ),
        "automatic_decision_authorized": False,
        "automatic_application_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    if (
        config.get("schema_version") != "research-descriptive-worker-supervisor-v1"
        or config.get("status") != "active"
        or config.get("stage") != "descriptive_execution"
        or config.get("schedule_interval_minutes") != 60
        or config.get("notification_policy")
        != "failures_or_validated_advisory_ready"
        or config.get("concurrency_control") != expected_concurrency_control
        or config.get("run_ledger") != expected_run_ledger
        or config.get("failure_recovery") != expected_failure_recovery
        or config.get("knowledge_review_batching")
        != expected_knowledge_review
        or config.get("success_behavior")
        != {"empty_queue": "silent_success", "completed_batch": "silent_success"}
        or config.get("failure_behavior", {}).get("automatic_remediation_authorized") is not False
        or config.get("prohibited_actions") != expected_prohibitions
        or not isinstance(config.get("max_jobs_per_run"), int)
        or not 1 <= config["max_jobs_per_run"] <= 100
        or not isinstance(config.get("lease_seconds"), int)
        or not 1 <= config["lease_seconds"] <= 3600
        or not isinstance(config.get("worker_id"), str)
        or not config["worker_id"].strip()
    ):
        raise ValueError("descriptive worker supervisor config is invalid")
    registry = str(config.get("registry_path", ""))
    if registry != "research/registry/stage4a-director.db":
        raise ValueError("descriptive worker supervisor registry is invalid")
    for dependency, expected_sha256 in (
        (expected_knowledge_review["policy_path"], expected_knowledge_review["policy_sha256"]),
        (
            expected_knowledge_review["advisor_prompt_path"],
            expected_knowledge_review["advisor_prompt_sha256"],
        ),
        (
            expected_knowledge_review["review_sla_policy_path"],
            expected_knowledge_review["review_sla_policy_sha256"],
        ),
        (
            expected_failure_recovery["contract_path"],
            expected_failure_recovery["contract_sha256"],
        ),
        (
            expected_failure_recovery["approval_path"],
            expected_failure_recovery["approval_sha256"],
        ),
    ):
        dependency_path = _repo_file(repo, dependency, "supervisor dependency")
        if sha256_file(dependency_path) != expected_sha256:
            raise ValueError("descriptive worker supervisor dependency hash mismatch")
    return config, {
        "config_path": path.as_posix(),
        "config_sha256": sha256_file(resolved),
        "config_fingerprint": config_fingerprint,
        "approval_path": DEFAULT_APPROVAL.as_posix(),
        "approval_fingerprint": approval_fingerprint,
    }


def _knowledge_review_cycle(
    repo: Path,
    config: dict[str, Any],
    checked_at: str,
) -> dict[str, Any]:
    review_config = config["knowledge_review_batching"]
    policy_path = Path(review_config["policy_path"])
    advisor_prompt_path = Path(review_config["advisor_prompt_path"])
    if not (repo / advisor_prompt_path).is_file():
        raise ValueError("knowledge review advisor prompt is missing")
    policy = load_document(repo / policy_path)
    registry_path = repo / config["registry_path"]
    result = knowledge_batcher.build_batch(
        repo,
        export_director_registry.export_registry(str(registry_path)),
        policy,
        checked_at,
        policy_path,
    )
    newly_published = knowledge_batcher.publish_batch(repo, result)
    public = knowledge_batcher.public_result(result, newly_published)
    review = {
        "status": public["status"],
        "pending_count": public["pending_count"],
        "notification_required": public["notification_required"],
        "artifacts_written": public["artifacts_written"],
        **{
            key: public[key]
            for key in (
                "batch_id",
                "trigger_reason",
                "oldest_pending_at",
                "count_threshold_remaining",
                "next_age_trigger_at",
                "remaining_wait_hours",
            )
            if key in public
        },
        "automatic_decision_authorized": False,
        "automatic_application_authorized": False,
        "automatic_lesson_promotion_authorized": False,
        "execution_authorized": False,
    }
    if result["status"] != "batch_ready":
        return review
    handoff = result["handoff"]
    packet = result["packet"]
    advisory_relative = Path(handoff["planned_advisory_path"])
    advisory_path = repo / advisory_relative
    review.update(
        {
            "batch_id": handoff["batch_id"],
            "packet_path": handoff["packet_path"],
            "planned_advisory_path": advisory_relative.as_posix(),
            "advisor_prompt_path": review_config["advisor_prompt_path"],
            "validation_command": (
                ".\\.venv-freqtrade\\Scripts\\python.exe "
                "scripts\\research_knowledge_advisory.py --packet "
                f"{handoff['packet_path']} --advisory "
                f"{advisory_relative.as_posix()} --strict-local-evidence"
            ),
        }
    )
    if advisory_path.exists():
        advisory = load_document(advisory_path)
        summary = research_knowledge_advisory.validate_aggregated_advisory(
            repo, packet, advisory
        )
        sla = research_review_sla.evaluate(
            repo,
            registry_path,
            batch_id=handoff["batch_id"],
            advisory=advisory,
            checked_at=checked_at,
            policy_path=review_config["review_sla_policy_path"],
        )
        review.update(
            {
                "status": sla["status"],
                "notification_required": sla["notification_required"],
                "artifacts_written": [],
                "advisory_status": "validated",
                "advisory_fingerprint": advisory["advisory_fingerprint"],
                "recommendation_summary": summary,
                "review_sla": sla,
                "required_next_action": sla.get(
                    "required_action", "explicit_human_batch_approval"
                ),
            }
        )
        return review
    review.update(
        {
            "status": "advisory_required",
            "notification_required": False,
            "advisory_status": "missing",
            "required_next_action": (
                "draft_validate_local_evidence_advisory_then_notify_once"
            ),
        }
    )
    return review


def run_supervisor(
    repo_root: str | Path,
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    checked_at: str | None = None,
    trigger_source: str = "automation_or_manual",
    invocation_id: str | None = None,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    config, governance_binding = _config(repo, config_path)
    registry_path = repo / config["registry_path"]
    lock_config = config["concurrency_control"]
    cycle_at = checked_at or utc_now()
    lease = supervisor_ledger.acquire(
        registry_path,
        supervisor_id=config["supervisor_id"],
        lock_name=lock_config["lock_name"],
        lease_seconds=lock_config["lease_seconds"],
        governance_binding=governance_binding,
        started_at=cycle_at,
        trigger_source=trigger_source,
        invocation_id=invocation_id,
    )
    if not lease["acquired"]:
        return {
            "schema_version": "research-descriptive-worker-supervisor-result-v1",
            "supervisor_id": config["supervisor_id"],
            "governance_binding": governance_binding,
            "run_ledger": {
                "supervisor_run_id": lease["supervisor_run_id"],
                "status": "skipped_lock_held",
                "lock_name": lease["lock_name"],
                "lock_holder_run_id": lease["lock_holder_run_id"],
                "lock_lease_expires_at": lease["lock_lease_expires_at"],
            },
            "status": "skipped_lock_held",
            "completed_jobs": 0,
            "queue_checked": False,
            "queue_empty_for_stage": False,
            "result_ids": [],
            "knowledge_review": {
                "status": "not_checked_lock_held",
                "pending_count": None,
                "notification_required": False,
                "artifacts_written": [],
            },
            "failure_recovery": {
                "status": "not_checked_lock_held",
                "notification_required": False,
                "automatic_retries_queued": [],
                "alerts": [],
            },
            "notification_required": False,
            "candidate_created": False,
            "strategy_modified": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }

    def heartbeat() -> None:
        supervisor_ledger.heartbeat(
            registry_path,
            lease,
            lock_config["lease_seconds"],
            renewed_at=cycle_at if checked_at is not None else None,
        )

    try:
        heartbeat()
        recovery = worker_recovery.reconcile_failures(
            repo,
            registry_path,
            checked_at=cycle_at,
        )
        heartbeat()
        drained = descriptive_worker.drain(
            repo,
            registry_path,
            config["worker_id"],
            max_jobs=config["max_jobs_per_run"],
            lease_seconds=config["lease_seconds"],
            progress_callback=heartbeat,
        )
        heartbeat()
        review = _knowledge_review_cycle(repo, config, cycle_at)
        notification_required = bool(
            review["notification_required"] or recovery["notification_required"]
        )
        result = {
            "schema_version": "research-descriptive-worker-supervisor-result-v1",
            "supervisor_id": config["supervisor_id"],
            "governance_binding": governance_binding,
            "run_ledger": {
                "supervisor_run_id": lease["supervisor_run_id"],
                "status": "completed",
                "lock_name": lease["lock_name"],
                "lock_fencing_token": lease["lock_fencing_token"],
                "recovered_stale_run_id": lease["recovered_stale_run_id"],
            },
            "status": (
                "attention_required"
                if recovery["status"] == "attention_required"
                else review["status"]
                if review["status"]
                in {"review_reminder_due", "review_escalation_due"}
                else "advisory_required"
                if review["status"] == "advisory_required"
                else "idle" if drained["completed_jobs"] == 0 else "completed"
            ),
            "completed_jobs": drained["completed_jobs"],
            "queue_checked": True,
            "queue_empty_for_stage": drained["queue_empty_for_stage"],
            "result_ids": drained["result_ids"],
            "knowledge_review": review,
            "failure_recovery": recovery,
            "notification_required": notification_required,
            "candidate_created": False,
            "strategy_modified": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        supervisor_ledger.complete(
            registry_path,
            lease,
            result,
            completed_at=cycle_at if checked_at is not None else None,
        )
        return result
    except Exception as exc:
        supervisor_ledger.fail(
            registry_path,
            lease,
            exc,
            failed_at=cycle_at if checked_at is not None else None,
        )
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(ROOT))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--checked-at")
    parser.add_argument("--trigger-source", default="automation_or_manual")
    parser.add_argument("--invocation-id")
    args = parser.parse_args(argv)
    try:
        result = run_supervisor(
            args.repo_root,
            config_path=args.config,
            checked_at=args.checked_at,
            trigger_source=args.trigger_source,
            invocation_id=args.invocation_id,
        )
    except Exception as exc:
        result = {
            "schema_version": "research-descriptive-worker-supervisor-failure-v1",
            "status": "failed",
            "notification_required": True,
            "failure": {
                "classification": "supervisor_cycle_failed",
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:1000],
                "required_action": "inspect_supervisor_run_ledger_and_fix_root_cause",
            },
            "automatic_retry_authorized": False,
            "candidate_created": False,
            "strategy_modified": False,
            "validation_accesses": 0,
            "holdout_accesses": 0,
        }
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
