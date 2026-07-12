#!/usr/bin/env python3
"""Approval and integrity gates for the single authorized Stage 4B.1 campaign."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from research_director_common import fingerprint, load_document, proposal_fingerprint, sha256_file


APPROVED_CAMPAIGN_FINGERPRINT = "5950353be61676185d53d7eced07fcbf094ccf10d68f2c60f0812f5820da9581"
SELECTED_PROPOSAL_ID = "cross-pair-data-readiness-audit-v1"


def compiled_campaign_fingerprint(campaign: dict[str, Any]) -> str:
    """Reconstruct the approved pre-authorization compilation identity."""
    payload = copy.deepcopy(campaign)
    payload.pop("compiled_at", None)
    payload.pop("campaign_fingerprint", None)
    payload.pop("execution_authorization", None)
    if payload.get("authorization_overlay_applied"):
        payload.pop("authorization_overlay_applied", None)
        payload["execution_authorized"] = False
        payload["approval_granted"] = False
        payload["approval_route"] = "auto_approvable_future"
    return fingerprint(payload)


def verify_campaign_fingerprint(campaign: dict[str, Any], approved: str = APPROVED_CAMPAIGN_FINGERPRINT) -> dict[str, Any]:
    actual = compiled_campaign_fingerprint(campaign)
    return {
        "approved": approved,
        "actual": actual,
        "matched": actual == approved,
        "reason_code": None if actual == approved else "compiled_campaign_fingerprint_drift",
    }


def verify_constitution_approval(repo: Path, constitution: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    path = repo / event["constitution_path"]
    actual = sha256_file(path)
    matched = (
        constitution.get("approval_status") == "approved"
        and constitution.get("approver_type") == "human_user"
        and event.get("approval_status") == "approved"
        and event.get("approver_type") == "human_user"
        and actual == event.get("approved_constitution_sha256")
    )
    return {"actual_sha256": actual, "approved_sha256": event.get("approved_constitution_sha256"), "matched": matched}


def verify_human_selection_for(proposal: dict[str, Any], event: dict[str, Any], expected_proposal_id: str) -> dict[str, Any]:
    actual = proposal_fingerprint(proposal)
    matched = (
        event.get("approval_status") == "approved"
        and event.get("approver_type") == "human_user"
        and event.get("proposal_id") == proposal.get("proposal_id") == expected_proposal_id
        and event.get("proposal_fingerprint") == actual
        and event.get("only_selected_proposal") is True
        and event.get("other_proposals_authorized") is False
    )
    return {"actual_fingerprint": actual, "approved_fingerprint": event.get("proposal_fingerprint"), "matched": matched}


def verify_human_selection(proposal: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    return verify_human_selection_for(proposal, event, SELECTED_PROPOSAL_ID)


def provisioning_scope(proposal: dict[str, Any], campaign: dict[str, Any]) -> dict[str, Any]:
    explicit = campaign.get("provisioning_scope") or proposal.get("provisioning_scope") or {}
    pair = explicit.get("pair")
    timeframe = explicit.get("timeframe")
    coverage = explicit.get("timerange") or explicit.get("coverage_rule")
    frozen = bool(pair and timeframe and coverage and pair != "BTC/USDT:USDT")
    return {
        "pair": pair,
        "timeframe": timeframe,
        "timerange_or_coverage_rule": coverage,
        "fully_frozen": frozen,
        "provisioning_authorized": frozen,
        "reason_code": None if frozen else "human_scope_required_for_provisioning",
    }


def classify_public_endpoint(method: str, host: str, path: str) -> dict[str, Any]:
    method = method.upper()
    allowed = method == "GET" and (
        (host == "fapi.binance.com" and path == "/fapi/v1/exchangeInfo")
        or (host == "data.binance.vision" and path.startswith("/data/futures/um/"))
    )
    private_markers = ("account", "order", "position", "listenkey", "api/v3")
    private = any(marker in path.lower() for marker in private_markers)
    return {
        "allowed": allowed and not private,
        "public_market_data_only": allowed and not private,
        "reason_code": None if allowed and not private else "private_or_unapproved_endpoint",
    }


def load_stage4b1_authorities(repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_document(repo / "research/governance/research-constitution.yaml"),
        load_document(repo / "research/governance/approvals/research-constitution-v1-approval.json"),
        load_document(repo / "research/director/proposals/cross-pair-data-readiness-audit-v1.json"),
        load_document(repo / "research/director/approvals/cross-pair-data-readiness-audit-v1-human-selection.json"),
        load_document(repo / "research/director/compiled/cross-pair-data-readiness-audit-v1/campaign.yaml"),
    )
