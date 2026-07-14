#!/usr/bin/env python3
"""Prepare an idempotent, provider-neutral research discovery run."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from research_director_common import (
    fingerprint,
    load_document,
    open_director_registry,
    utc_now,
)
from research_discovery_common import (
    DiscoveryError,
    artifact_fingerprint,
    validate_artifact,
    write_immutable_json,
)


ALLOWED_EVENTS = {
    "campaign_completed",
    "branch_closed",
    "director_no_research",
    "manual_request",
}

STATE_PATH = Path("research/director/current-research-state.json")
CONSTITUTION_PATH = Path("research/governance/research-constitution.yaml")
SOURCE_POLICY_PATH = Path("research/discovery/policy/source-policy.yaml")
IDEA_SCHEMA_PATH = Path("research/discovery/schemas/research-idea.schema.json")
RESEARCHER_PROMPT_PATH = Path("research/discovery/prompts/researcher.md")

EVIDENCE_SECTIONS = (
    "allowed_research_scope",
    "closed_branches",
    "evaluation_policy",
    "fixed_harness_defects",
    "harness_capabilities",
    "invalidated_research",
    "possible_next_directions",
    "proposal_history",
    "unresolved_research_questions",
)

FORBIDDEN_PATH_PARTS = {
    "candidate",
    "candidates",
    "execution",
    "holdout",
    "live",
    "private",
    "runner",
    "runners",
    "secret",
    "secrets",
    "strategies",
    "validation",
}


def create_trigger(
    event_type: str,
    event_ref: str,
    state: dict[str, object],
    constitution: dict[str, object],
    source_policy: dict[str, object],
    created_at: str | None = None,
) -> dict[str, object]:
    if event_type not in ALLOWED_EVENTS:
        raise DiscoveryError("unsupported_trigger", event_type)
    if not isinstance(event_ref, str) or not event_ref.strip():
        raise DiscoveryError("trigger_input_missing", "event_ref")
    if state.get("state_conflicts"):
        raise DiscoveryError(
            "state_conflict", "current research state contains conflicts"
        )
    state_fingerprint = state.get("state_fingerprint")
    if not isinstance(state_fingerprint, str) or not state_fingerprint:
        raise DiscoveryError("state_missing", "state_fingerprint")
    if constitution.get("status") != "approved" or constitution.get(
        "approval_status"
    ) != "approved":
        raise DiscoveryError(
            "constitution_not_approved", "approved Constitution is required"
        )
    source_policy_version = source_policy.get("schema_version")
    if not isinstance(source_policy_version, str) or not source_policy_version:
        raise DiscoveryError("source_policy_missing", "schema_version")

    trigger = {
        "schema_version": "research-trigger-v1",
        "trigger_id": f"discovery-trigger-{fingerprint({'event_type': event_type, 'event_ref': event_ref, 'state': state_fingerprint})[:16]}",
        "event_type": event_type,
        "event_ref": event_ref,
        "research_state_fingerprint": state_fingerprint,
        "constitution_fingerprint": fingerprint(constitution),
        "source_policy_version": source_policy_version,
        "created_at": created_at or utc_now(),
    }
    trigger["trigger_fingerprint"] = artifact_fingerprint(
        trigger, "trigger_fingerprint"
    )
    return trigger


def _load_bound_document(
    repo: Path, relative_path: Path, missing_reason: str
) -> dict[str, object]:
    path = repo / relative_path
    try:
        return load_document(path)
    except FileNotFoundError as exc:
        raise DiscoveryError(missing_reason, relative_path.as_posix()) from exc
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError(
            f"{missing_reason.removesuffix('_missing')}_invalid",
            f"{relative_path.as_posix()}: {type(exc).__name__}: {exc}",
        ) from exc


def _path_is_forbidden(relative_path: str) -> bool:
    parts = [part.lower() for part in Path(relative_path).parts]
    for part in parts:
        stem = part.split(".", 1)[0]
        if stem in FORBIDDEN_PATH_PARTS:
            return True
        if any(stem.startswith(f"{prefix}-") for prefix in FORBIDDEN_PATH_PARTS):
            return True
        if any(stem.startswith(f"{prefix}_") for prefix in FORBIDDEN_PATH_PARTS):
            return True
    return False


def _safe_repo_source(repo: Path, raw_path: object) -> str | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    normalized = raw_path.strip().replace("\\", "/")
    if not normalized.startswith(("docs/", "reports/", "research/")):
        return None
    relative = Path(normalized)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    if _path_is_forbidden(normalized):
        return None

    repo_root = repo.resolve()
    resolved = (repo_root / relative).resolve()
    if not resolved.is_relative_to(repo_root):
        return None
    if not resolved.is_file():
        raise DiscoveryError("source_missing", relative.as_posix())
    return relative.as_posix()


def _evidence_paths(value: object) -> list[object]:
    if isinstance(value, dict):
        evidence = value.get("evidence")
        return list(evidence) if isinstance(evidence, list) else []
    if isinstance(value, list):
        paths: list[object] = []
        for item in value:
            paths.extend(_evidence_paths(item))
        return paths
    return []


def _allowed_source_paths(repo: Path, state: dict[str, object]) -> list[str]:
    source_paths = {
        STATE_PATH.as_posix(),
        CONSTITUTION_PATH.as_posix(),
        SOURCE_POLICY_PATH.as_posix(),
        IDEA_SCHEMA_PATH.as_posix(),
    }

    datasets = state.get("datasets")
    if isinstance(datasets, list):
        for dataset in datasets:
            if not isinstance(dataset, dict):
                continue
            intended_use = dataset.get("intended_use")
            pairs = dataset.get("pairs")
            timeframes = dataset.get("timeframes")
            if not isinstance(intended_use, str) or not intended_use.startswith(
                "development"
            ):
                continue
            if not isinstance(pairs, list) or not set(pairs).issubset(
                {"BTC/USDT:USDT", "ETH/USDT:USDT"}
            ):
                continue
            if not isinstance(timeframes, list) or not {"1h", "4h"}.issubset(
                set(timeframes)
            ):
                continue
            source = _safe_repo_source(repo, dataset.get("path"))
            if source:
                source_paths.add(source)

    runtime_contracts = state.get("runtime_contracts")
    if isinstance(runtime_contracts, list):
        for contract in runtime_contracts:
            if not isinstance(contract, dict) or contract.get("exists") is not True:
                continue
            source = _safe_repo_source(repo, contract.get("path"))
            if source:
                source_paths.add(source)

    for section in EVIDENCE_SECTIONS:
        for raw_path in _evidence_paths(state.get(section)):
            source = _safe_repo_source(repo, raw_path)
            if source:
                source_paths.add(source)

    for required_path in sorted(source_paths):
        _safe_repo_source(repo, required_path)
    return sorted(source_paths)


def _bound_context(
    repo: Path, trigger: dict[str, object]
) -> tuple[dict[str, object], list[str]]:
    validate_artifact(repo, "research-trigger.schema.json", trigger)
    actual_trigger_fingerprint = artifact_fingerprint(
        trigger, "trigger_fingerprint"
    )
    if trigger.get("trigger_fingerprint") != actual_trigger_fingerprint:
        raise DiscoveryError(
            "trigger_fingerprint_conflict",
            "trigger content does not match trigger_fingerprint",
        )

    state = _load_bound_document(repo, STATE_PATH, "state_missing")
    if state.get("state_conflicts"):
        raise DiscoveryError(
            "state_conflict", "current research state contains conflicts"
        )
    if state.get("state_fingerprint") != trigger.get(
        "research_state_fingerprint"
    ):
        raise DiscoveryError(
            "stale_trigger", "current research state fingerprint changed"
        )

    constitution = _load_bound_document(
        repo, CONSTITUTION_PATH, "constitution_missing"
    )
    if constitution.get("status") != "approved" or constitution.get(
        "approval_status"
    ) != "approved":
        raise DiscoveryError(
            "constitution_not_approved", "approved Constitution is required"
        )
    if fingerprint(constitution) != trigger.get("constitution_fingerprint"):
        raise DiscoveryError(
            "constitution_conflict", "approved Constitution fingerprint changed"
        )

    source_policy = _load_bound_document(
        repo, SOURCE_POLICY_PATH, "source_policy_missing"
    )
    if source_policy.get("schema_version") != trigger.get(
        "source_policy_version"
    ):
        raise DiscoveryError(
            "source_policy_conflict", "source policy version changed"
        )

    return state, _allowed_source_paths(repo, state)


def _validate_run_paths(
    repo: Path, run_path: Path, temp_inbox: Path
) -> tuple[Path, Path]:
    if run_path.is_absolute() or ".." in run_path.parts:
        raise DiscoveryError("run_path_invalid", run_path.as_posix())
    if run_path.parts[:3] != ("research", "discovery", "runs"):
        raise DiscoveryError("run_path_invalid", run_path.as_posix())
    if len(run_path.parts) != 4:
        raise DiscoveryError("run_path_invalid", run_path.as_posix())

    run_root = (repo / run_path).resolve()
    governed_runs = (repo / "research/discovery/runs").resolve()
    if not run_root.is_relative_to(governed_runs):
        raise DiscoveryError("run_path_invalid", run_path.as_posix())

    expected_inbox = (
        Path(tempfile.gettempdir())
        / "freqtrade-research-discovery"
        / run_path.name
        / "researcher"
    ).resolve()
    actual_inbox = temp_inbox.resolve()
    if actual_inbox != expected_inbox or actual_inbox.is_relative_to(repo.resolve()):
        raise DiscoveryError("temp_inbox_invalid", str(actual_inbox))
    return run_root, actual_inbox


def _researcher_packet_text(
    repo: Path,
    run_path: Path,
    trigger: dict[str, object],
    temp_inbox: Path,
) -> str:
    state, source_paths = _bound_context(repo, trigger)
    _, inbox = _validate_run_paths(repo, run_path, temp_inbox)
    prompt_path = repo / RESEARCHER_PROMPT_PATH
    try:
        prompt = prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DiscoveryError(
            "researcher_prompt_missing", RESEARCHER_PROMPT_PATH.as_posix()
        ) from exc

    allowed_scope = state.get("allowed_research_scope")
    if not isinstance(allowed_scope, dict):
        raise DiscoveryError("state_missing", "allowed_research_scope")
    if (
        allowed_scope.get("approved_market") != "Binance USD-M Futures"
        or allowed_scope.get("baseline_timeframe") != "1h"
    ):
        raise DiscoveryError("state_conflict", "fixed market scope changed")

    source_lines = "\n".join(f"- `{path}`" for path in source_paths)
    return (
        "# Researcher Task Packet / 研究员任务包\n\n"
        "## Immutable bindings / 不可变绑定\n\n"
        f"- Trigger fingerprint: `{trigger['trigger_fingerprint']}`\n"
        f"- Research state fingerprint: `{trigger['research_state_fingerprint']}`\n"
        f"- Constitution fingerprint: `{trigger['constitution_fingerprint']}`\n"
        f"- Source policy version: `{trigger['source_policy_version']}`\n\n"
        "## Allowed read-only sources / 允许只读来源\n\n"
        "Read only the exact allowlisted paths below. Do not follow other repository references.\n\n"
        f"{source_lines}\n\n"
        "## Fixed scope / 固定范围\n\n"
        "Keep Binance USD-M Futures, isolated margin, approved BTC/ETH Development data, "
        "`1h` primary, `4h` informative, the approved runtime, and all existing risk "
        "parameters unchanged. You may propose data readiness work, but Do not download "
        "market data.\n\n"
        "## Forbidden boundaries / 禁止边界\n\n"
        "Do not access Validation, Holdout, secrets, private APIs, live accounts, strategy "
        "mutation surfaces, Candidate surfaces, or execution surfaces. Do not create or "
        "start a Candidate, Campaign, experiment, backtest, or any execution.\n\n"
        "## Output / 输出\n\n"
        f"Write only `research-idea-v1` JSON objects to this absolute system TEMP inbox: `{inbox}`. "
        "The inbox is untrusted staging and is outside the governed repository. Do not modify "
        "the trigger or task packet.\n\n"
        "## Role contract / 角色合同\n\n"
        f"{prompt.rstrip()}\n"
    )


def _write_immutable_text(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise DiscoveryError("immutable_artifact_conflict", path.as_posix())
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_researcher_packet(
    repo: Path,
    run_path: Path,
    trigger: dict[str, object],
    temp_inbox: Path,
) -> str:
    repo = Path(repo).resolve()
    run_path = Path(run_path)
    packet = _researcher_packet_text(repo, run_path, trigger, temp_inbox)
    run_root, inbox = _validate_run_paths(repo, run_path, temp_inbox)
    inbox.mkdir(parents=True, exist_ok=True)
    _write_immutable_text(run_root / "researcher-task.md", packet)
    return packet


def _expected_result(trigger: dict[str, object]) -> dict[str, object]:
    run_id = f"discovery-run-{trigger['trigger_fingerprint'][:16]}"
    run_path = Path("research/discovery/runs") / run_id
    temp_inbox = (
        Path(tempfile.gettempdir())
        / "freqtrade-research-discovery"
        / run_id
        / "researcher"
    ).resolve()
    return {
        "run_id": run_id,
        "run_path": run_path.as_posix(),
        "researcher_inbox": str(temp_inbox),
        "status": "awaiting_researcher",
        "trigger_fingerprint": trigger["trigger_fingerprint"],
    }


def _verify_existing_run(
    repo: Path,
    trigger: dict[str, object],
    result: dict[str, object],
) -> None:
    run_path = Path(str(result["run_path"]))
    temp_inbox = Path(str(result["researcher_inbox"]))
    run_root, inbox = _validate_run_paths(repo, run_path, temp_inbox)
    trigger_path = run_root / "trigger.json"
    packet_path = run_root / "researcher-task.md"
    if not trigger_path.is_file() or not packet_path.is_file():
        raise DiscoveryError("run_artifact_missing", result["run_id"])
    existing_trigger = load_document(trigger_path)
    validate_artifact(repo, "research-trigger.schema.json", existing_trigger)
    if (
        existing_trigger.get("trigger_fingerprint")
        != trigger.get("trigger_fingerprint")
        or artifact_fingerprint(existing_trigger, "trigger_fingerprint")
        != trigger.get("trigger_fingerprint")
    ):
        raise DiscoveryError(
            "immutable_artifact_conflict", trigger_path.as_posix()
        )
    expected_packet = _researcher_packet_text(repo, run_path, trigger, temp_inbox)
    if packet_path.read_text(encoding="utf-8") != expected_packet:
        raise DiscoveryError("immutable_artifact_conflict", packet_path.as_posix())
    inbox.mkdir(parents=True, exist_ok=True)


def prepare_run(
    repo: Path, trigger: dict[str, object], registry_path: Path
) -> dict[str, object]:
    repo = Path(repo).resolve()
    _bound_context(repo, trigger)
    result = _expected_result(trigger)
    connection = open_director_registry(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT run_id, payload_json FROM research_discovery_runs "
            "WHERE trigger_fingerprint=?",
            (trigger["trigger_fingerprint"],),
        ).fetchone()
        if existing:
            try:
                existing_result = json.loads(existing["payload_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise DiscoveryError(
                    "registry_payload_invalid", str(existing["run_id"])
                ) from exc
            if (
                not isinstance(existing_result, dict)
                or existing["run_id"] != result["run_id"]
                or existing_result != result
            ):
                raise DiscoveryError(
                    "registry_run_conflict", str(existing["run_id"])
                )
            _verify_existing_run(repo, trigger, existing_result)
            connection.commit()
            return existing_result

        run_path = Path(str(result["run_path"]))
        temp_inbox = Path(str(result["researcher_inbox"]))
        temp_inbox.mkdir(parents=True, exist_ok=True)
        write_immutable_json(repo / run_path / "trigger.json", trigger)
        render_researcher_packet(repo, run_path, trigger, temp_inbox)
        connection.execute(
            "INSERT INTO research_discovery_runs("
            "run_id, trigger_fingerprint, status, state_fingerprint, payload_json, created_at"
            ") VALUES (?, ?, ?, ?, ?, ?)",
            (
                result["run_id"],
                trigger["trigger_fingerprint"],
                result["status"],
                trigger["research_state_fingerprint"],
                json.dumps(result, sort_keys=True),
                trigger["created_at"],
            ),
        )
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _resolve_input(repo: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo / path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--event-ref", required=True)
    parser.add_argument("--state", default=STATE_PATH.as_posix())
    parser.add_argument("--constitution", default=CONSTITUTION_PATH.as_posix())
    parser.add_argument("--source-policy", default=SOURCE_POLICY_PATH.as_posix())
    parser.add_argument("--director-registry", required=True)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args(argv)

    repo = Path(args.repo_root).resolve()
    state = load_document(_resolve_input(repo, args.state))
    constitution = load_document(_resolve_input(repo, args.constitution))
    source_policy = load_document(_resolve_input(repo, args.source_policy))
    registry = _resolve_input(repo, args.director_registry)
    trigger = create_trigger(
        event_type=args.event_type,
        event_ref=args.event_ref,
        state=state,
        constitution=constitution,
        source_policy=source_policy,
    )
    result = prepare_run(repo, trigger, registry)
    public_result = {
        key: result[key]
        for key in ("run_id", "run_path", "status", "trigger_fingerprint")
    }
    print(json.dumps(public_result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
