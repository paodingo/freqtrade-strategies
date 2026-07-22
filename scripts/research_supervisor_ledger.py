#!/usr/bin/env python3
"""Atomic lease and append-only event ledger for governed Supervisor runs."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_director_common import canonical_json, fingerprint, open_director_registry, utc_now


RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
TERMINAL_STATUSES = {"completed", "failed", "skipped_lock_held"}


def _instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("supervisor ledger timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("supervisor ledger timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _lease_expiry(started_at: str, lease_seconds: int) -> str:
    if type(lease_seconds) is not int or not 60 <= lease_seconds <= 21600:
        raise ValueError("supervisor lock lease is invalid")
    return (_instant(started_at) + timedelta(seconds=lease_seconds)).isoformat()


def _run_id(supervisor_id: str, started_at: str, invocation_id: str | None) -> str:
    if invocation_id is not None:
        if not RUN_ID_PATTERN.fullmatch(invocation_id):
            raise ValueError("supervisor invocation id is invalid")
        return invocation_id
    nonce = uuid.uuid4().hex
    return f"supervisor-run-{fingerprint([supervisor_id, started_at, nonce])[:24]}"


def _event(
    connection: Any,
    supervisor_run_id: str,
    event_type: str,
    payload: dict[str, Any],
    created_at: str,
) -> None:
    event_payload = {
        "schema_version": "research-supervisor-run-event-v1",
        "supervisor_run_id": supervisor_run_id,
        "event_type": event_type,
        "created_at": created_at,
        **payload,
    }
    event_fingerprint = fingerprint(event_payload)
    event_id = f"supervisor-event-{event_fingerprint[:24]}"
    connection.execute(
        "INSERT INTO research_supervisor_run_events("
        "event_id,supervisor_run_id,event_type,event_fingerprint,payload_json,created_at"
        ") VALUES(?,?,?,?,?,?)",
        (
            event_id,
            supervisor_run_id,
            event_type,
            event_fingerprint,
            canonical_json(event_payload),
            created_at,
        ),
    )


def _insert_run(
    connection: Any,
    *,
    supervisor_run_id: str,
    supervisor_id: str,
    trigger_source: str,
    status: str,
    lock_name: str,
    fencing_token: int | None,
    governance_binding: dict[str, str],
    payload: dict[str, Any],
    started_at: str,
    completed_at: str | None,
) -> None:
    connection.execute(
        "INSERT INTO research_supervisor_runs("
        "supervisor_run_id,supervisor_id,trigger_source,status,lock_name,"
        "lock_fencing_token,config_fingerprint,approval_fingerprint,"
        "result_fingerprint,payload_json,started_at,completed_at"
        ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            supervisor_run_id,
            supervisor_id,
            trigger_source,
            status,
            lock_name,
            fencing_token,
            governance_binding["config_fingerprint"],
            governance_binding["approval_fingerprint"],
            None,
            canonical_json(payload),
            started_at,
            completed_at,
        ),
    )


def _fail_stale_owner(
    connection: Any,
    stale_run_id: str,
    recovered_by_run_id: str,
    failed_at: str,
) -> bool:
    row = connection.execute(
        "SELECT status,payload_json FROM research_supervisor_runs "
        "WHERE supervisor_run_id=?",
        (stale_run_id,),
    ).fetchone()
    if row is None or row["status"] != "started":
        return False
    payload = json.loads(row["payload_json"])
    payload.update(
        {
            "status": "failed",
            "reason_code": "lock_lease_expired_before_completion",
            "recovered_by_run_id": recovered_by_run_id,
            "completed_at": failed_at,
        }
    )
    connection.execute(
        "UPDATE research_supervisor_runs SET status='failed',payload_json=?,"
        "completed_at=? WHERE supervisor_run_id=? AND status='started'",
        (canonical_json(payload), failed_at, stale_run_id),
    )
    _event(
        connection,
        stale_run_id,
        "failed",
        {
            "reason_code": "lock_lease_expired_before_completion",
            "recovered_by_run_id": recovered_by_run_id,
        },
        failed_at,
    )
    return True


def acquire(
    registry_path: str | Path,
    *,
    supervisor_id: str,
    lock_name: str,
    lease_seconds: int,
    governance_binding: dict[str, str],
    started_at: str | None = None,
    trigger_source: str = "automation_or_manual",
    invocation_id: str | None = None,
) -> dict[str, Any]:
    """Atomically record an invocation and acquire or skip the global lease."""
    timestamp = started_at or utc_now()
    now = _instant(timestamp)
    expires_at = _lease_expiry(timestamp, lease_seconds)
    if not isinstance(lock_name, str) or not RUN_ID_PATTERN.fullmatch(lock_name):
        raise ValueError("supervisor lock name is invalid")
    if not isinstance(trigger_source, str) or not trigger_source.strip():
        raise ValueError("supervisor trigger source is invalid")
    for field in ("config_fingerprint", "approval_fingerprint"):
        if not isinstance(governance_binding.get(field), str):
            raise ValueError("supervisor governance binding is invalid")
    supervisor_run_id = _run_id(supervisor_id, timestamp, invocation_id)
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT owner_run_id,fencing_token,lease_expires_at "
            "FROM research_supervisor_locks WHERE lock_name=?",
            (lock_name,),
        ).fetchone()
        if current is not None and _instant(current["lease_expires_at"]) > now:
            payload = {
                "schema_version": "research-supervisor-run-ledger-v1",
                "supervisor_run_id": supervisor_run_id,
                "supervisor_id": supervisor_id,
                "status": "skipped_lock_held",
                "lock_name": lock_name,
                "lock_holder_run_id": current["owner_run_id"],
                "lock_lease_expires_at": current["lease_expires_at"],
                "governance_binding": governance_binding,
                "started_at": timestamp,
                "completed_at": timestamp,
            }
            _insert_run(
                connection,
                supervisor_run_id=supervisor_run_id,
                supervisor_id=supervisor_id,
                trigger_source=trigger_source,
                status="skipped_lock_held",
                lock_name=lock_name,
                fencing_token=None,
                governance_binding=governance_binding,
                payload=payload,
                started_at=timestamp,
                completed_at=timestamp,
            )
            _event(
                connection,
                supervisor_run_id,
                "skipped_lock_held",
                {
                    "lock_name": lock_name,
                    "lock_holder_run_id": current["owner_run_id"],
                    "lock_lease_expires_at": current["lease_expires_at"],
                },
                timestamp,
            )
            connection.commit()
            return {
                "acquired": False,
                "supervisor_run_id": supervisor_run_id,
                "status": "skipped_lock_held",
                "lock_name": lock_name,
                "lock_holder_run_id": current["owner_run_id"],
                "lock_lease_expires_at": current["lease_expires_at"],
            }

        fencing_token = 1 if current is None else int(current["fencing_token"]) + 1
        recovered_stale_run_id = None
        if current is not None:
            recovered_stale_run_id = str(current["owner_run_id"])
            _fail_stale_owner(
                connection,
                recovered_stale_run_id,
                supervisor_run_id,
                timestamp,
            )
        payload = {
            "schema_version": "research-supervisor-run-ledger-v1",
            "supervisor_run_id": supervisor_run_id,
            "supervisor_id": supervisor_id,
            "status": "started",
            "lock_name": lock_name,
            "lock_fencing_token": fencing_token,
            "lock_lease_expires_at": expires_at,
            "recovered_stale_run_id": recovered_stale_run_id,
            "governance_binding": governance_binding,
            "started_at": timestamp,
        }
        _insert_run(
            connection,
            supervisor_run_id=supervisor_run_id,
            supervisor_id=supervisor_id,
            trigger_source=trigger_source,
            status="started",
            lock_name=lock_name,
            fencing_token=fencing_token,
            governance_binding=governance_binding,
            payload=payload,
            started_at=timestamp,
            completed_at=None,
        )
        if current is None:
            connection.execute(
                "INSERT INTO research_supervisor_locks("
                "lock_name,owner_run_id,fencing_token,lease_expires_at,acquired_at,updated_at"
                ") VALUES(?,?,?,?,?,?)",
                (
                    lock_name,
                    supervisor_run_id,
                    fencing_token,
                    expires_at,
                    timestamp,
                    timestamp,
                ),
            )
        else:
            connection.execute(
                "UPDATE research_supervisor_locks SET owner_run_id=?,fencing_token=?,"
                "lease_expires_at=?,acquired_at=?,updated_at=? WHERE lock_name=?",
                (
                    supervisor_run_id,
                    fencing_token,
                    expires_at,
                    timestamp,
                    timestamp,
                    lock_name,
                ),
            )
        _event(
            connection,
            supervisor_run_id,
            "started",
            {
                "lock_name": lock_name,
                "lock_fencing_token": fencing_token,
                "lock_lease_expires_at": expires_at,
                "recovered_stale_run_id": recovered_stale_run_id,
            },
            timestamp,
        )
        connection.commit()
        return {
            "acquired": True,
            "supervisor_run_id": supervisor_run_id,
            "status": "started",
            "lock_name": lock_name,
            "lock_fencing_token": fencing_token,
            "lock_lease_expires_at": expires_at,
            "recovered_stale_run_id": recovered_stale_run_id,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def heartbeat(
    registry_path: str | Path,
    lease: dict[str, Any],
    lease_seconds: int,
    *,
    renewed_at: str | None = None,
) -> str:
    timestamp = renewed_at or utc_now()
    expires_at = _lease_expiry(timestamp, lease_seconds)
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        updated = connection.execute(
            "UPDATE research_supervisor_locks SET lease_expires_at=?,updated_at=? "
            "WHERE lock_name=? AND owner_run_id=? AND fencing_token=?",
            (
                expires_at,
                timestamp,
                lease["lock_name"],
                lease["supervisor_run_id"],
                lease["lock_fencing_token"],
            ),
        ).rowcount
        if updated != 1:
            raise ValueError("supervisor lock ownership lost")
        connection.commit()
        lease["lock_lease_expires_at"] = expires_at
        return expires_at
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def complete(
    registry_path: str | Path,
    lease: dict[str, Any],
    result: dict[str, Any],
    *,
    completed_at: str | None = None,
) -> str:
    timestamp = completed_at or utc_now()
    result_fingerprint = fingerprint(result)
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        lock = connection.execute(
            "SELECT owner_run_id,fencing_token FROM research_supervisor_locks "
            "WHERE lock_name=?",
            (lease["lock_name"],),
        ).fetchone()
        if (
            lock is None
            or lock["owner_run_id"] != lease["supervisor_run_id"]
            or lock["fencing_token"] != lease["lock_fencing_token"]
        ):
            raise ValueError("supervisor lock ownership lost before completion")
        row = connection.execute(
            "SELECT status,payload_json FROM research_supervisor_runs "
            "WHERE supervisor_run_id=?",
            (lease["supervisor_run_id"],),
        ).fetchone()
        if row is None or row["status"] != "started":
            raise ValueError("supervisor run is not completable")
        payload = json.loads(row["payload_json"])
        payload.update(
            {
                "status": "completed",
                "result": result,
                "result_fingerprint": result_fingerprint,
                "completed_at": timestamp,
            }
        )
        connection.execute(
            "UPDATE research_supervisor_runs SET status='completed',result_fingerprint=?,"
            "payload_json=?,completed_at=? WHERE supervisor_run_id=? AND status='started'",
            (
                result_fingerprint,
                canonical_json(payload),
                timestamp,
                lease["supervisor_run_id"],
            ),
        )
        _event(
            connection,
            lease["supervisor_run_id"],
            "completed",
            {"result_fingerprint": result_fingerprint},
            timestamp,
        )
        connection.execute(
            "DELETE FROM research_supervisor_locks WHERE lock_name=? "
            "AND owner_run_id=? AND fencing_token=?",
            (
                lease["lock_name"],
                lease["supervisor_run_id"],
                lease["lock_fencing_token"],
            ),
        )
        connection.commit()
        return result_fingerprint
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fail(
    registry_path: str | Path,
    lease: dict[str, Any],
    error: BaseException,
    *,
    failed_at: str | None = None,
) -> bool:
    timestamp = failed_at or utc_now()
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status,payload_json FROM research_supervisor_runs "
            "WHERE supervisor_run_id=?",
            (lease["supervisor_run_id"],),
        ).fetchone()
        if row is None or row["status"] in TERMINAL_STATUSES:
            connection.rollback()
            return False
        payload = json.loads(row["payload_json"])
        failure = {
            "reason_code": "supervisor_cycle_failed",
            "error_type": type(error).__name__,
            "error_message": str(error)[:1000],
        }
        payload.update({"status": "failed", **failure, "completed_at": timestamp})
        connection.execute(
            "UPDATE research_supervisor_runs SET status='failed',payload_json=?,"
            "completed_at=? WHERE supervisor_run_id=? AND status='started'",
            (canonical_json(payload), timestamp, lease["supervisor_run_id"]),
        )
        _event(
            connection,
            lease["supervisor_run_id"],
            "failed",
            failure,
            timestamp,
        )
        connection.execute(
            "DELETE FROM research_supervisor_locks WHERE lock_name=? "
            "AND owner_run_id=? AND fencing_token=?",
            (
                lease["lock_name"],
                lease["supervisor_run_id"],
                lease["lock_fencing_token"],
            ),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
