#!/usr/bin/env python3
"""Build the deterministic, static-only Harness Protocol distribution manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path("harness/distribution/v0.1/release-manifest.json")
PROFILE_PATH = Path("harness/distribution/v0.1/fingerprint-profiles.json")
SOURCE_REPOSITORY = "https://github.com/paodingo/freqtrade-strategies.git"
SOURCE_COMMIT = "6363b7f8352a53cbcd709a4d3d6b5c0bc7ba3b93"
FINGERPRINT_PROFILE = "sha256-text-lf-v1"

PROTOCOL_CORE_PATHS = (
    "harness/protocol/v0.1/harness-protocol.schema.json",
    "harness/protocol/v0.1/protocol-manifest.json",
    "harness/protocol/v0.1/fixtures/normal.json",
    "harness/protocol/v0.1/fixtures/governed-block.json",
    "harness/protocol/v0.1/fixtures/tool-error.json",
    "harness/protocol/v0.1/fixtures/authority-mismatch.json",
    "harness/protocol/v0.1/fixtures/known-baseline-debt.json",
)
PROJECT_MAPPING_PATHS = (
    "harness/mappings/v0.1/project-mapping.schema.json",
    "harness/mappings/v0.1/mapping-manifest.json",
    "harness/mappings/v0.1/projects/freqtrade-strategies.json",
    "harness/mappings/v0.1/projects/china-sector-radar.json",
    "harness/mappings/v0.1/projects/rehab-intervention.json",
    "harness/mappings/v0.1/fixtures/source-stale.json",
    "harness/mappings/v0.1/fixtures/authority-weakening.json",
    "harness/mappings/v0.1/fixtures/unmapped-gap.json",
)
SOURCE_PATHS = PROTOCOL_CORE_PATHS + PROJECT_MAPPING_PATHS


class DistributionError(ValueError):
    """A fail-closed distribution contract violation."""

    def __init__(self, reason_code: str, detail: str):
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DistributionError("duplicate_json_key", f"duplicate JSON key: {key}")
        result[key] = value
    return result


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def decode_text_bytes(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise DistributionError("utf8_bom_rejected", "UTF-8 BOM is not allowed")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DistributionError("invalid_utf8", str(exc)) from exc


def parse_json_text(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except DistributionError:
        raise
    except json.JSONDecodeError as exc:
        raise DistributionError("invalid_json", str(exc)) from exc


def fingerprint_text_bytes(raw: bytes, *, validate_json: bool = True) -> tuple[str, int]:
    text = decode_text_bytes(raw)
    if validate_json:
        parse_json_text(text)
    normalized = normalize_text(text).encode("utf-8")
    return f"sha256:{hashlib.sha256(normalized).hexdigest()}", len(normalized)


def load_json_file(path: Path) -> Any:
    text = decode_text_bytes(path.read_bytes())
    return parse_json_text(text)


def _assert_regular_file(root: Path, relative_path: str) -> Path:
    path = root / Path(relative_path)
    if not path.exists():
        raise DistributionError("source_file_missing", relative_path)
    if path.is_symlink() or not path.is_file():
        raise DistributionError("source_file_not_regular", relative_path)
    return path


def assert_exact_source_set(root: Path) -> None:
    expected = set(SOURCE_PATHS)
    discovered: set[str] = set()
    for relative_root in (Path("harness/protocol/v0.1"), Path("harness/mappings/v0.1")):
        directory = root / relative_root
        if not directory.is_dir() or directory.is_symlink():
            raise DistributionError("source_directory_missing", relative_root.as_posix())
        for path in directory.rglob("*.json"):
            discovered.add(path.relative_to(root).as_posix())
    if discovered != expected:
        missing = sorted(expected - discovered)
        extra = sorted(discovered - expected)
        raise DistributionError(
            "source_file_set_mismatch",
            f"missing={missing}; extra={extra}",
        )


def assert_fingerprint_profile(root: Path) -> None:
    profile_document = load_json_file(_assert_regular_file(root, PROFILE_PATH.as_posix()))
    profiles = profile_document.get("profiles") if isinstance(profile_document, dict) else None
    if not isinstance(profiles, list) or len(profiles) != 1:
        raise DistributionError("fingerprint_profile_set_mismatch", "exactly one profile is required")
    profile = profiles[0]
    expected = {
        "profile_id": FINGERPRINT_PROFILE,
        "algorithm": "sha256",
        "input_kind": "text",
        "encoding": "utf-8",
        "bom_policy": "reject",
        "eol_normalization": {"crlf": "lf", "cr": "lf", "lf": "lf"},
        "preserve_other_content": True,
        "json_duplicate_key_policy": "reject",
        "unknown_profile_policy": "blocked",
    }
    if profile != expected:
        raise DistributionError("unknown_fingerprint_profile", repr(profile))


def _artifact(root: Path, relative_path: str, component_id: str) -> dict[str, Any]:
    path = _assert_regular_file(root, relative_path)
    fingerprint, normalized_bytes = fingerprint_text_bytes(path.read_bytes())
    media_type = "application/schema+json" if relative_path.endswith(".schema.json") else "application/json"
    return {
        "path": relative_path,
        "component_id": component_id,
        "media_type": media_type,
        "bytes": normalized_bytes,
        "fingerprint": fingerprint,
    }


def build_manifest(root: Path = REPO_ROOT) -> dict[str, Any]:
    root = root.resolve()
    assert_exact_source_set(root)
    assert_fingerprint_profile(root)
    artifacts = [
        *(_artifact(root, path, "protocol-core") for path in PROTOCOL_CORE_PATHS),
        *(_artifact(root, path, "project-mappings") for path in PROJECT_MAPPING_PATHS),
    ]
    return {
        "distribution_version": "0.1",
        "protocol_version": "0.1",
        "mapping_version": "0.1",
        "source_repository": SOURCE_REPOSITORY,
        "source_commit": SOURCE_COMMIT,
        "fingerprint_profile": FINGERPRINT_PROFILE,
        "components": [
            {"component_id": "protocol-core", "paths": list(PROTOCOL_CORE_PATHS)},
            {"component_id": "project-mappings", "paths": list(PROJECT_MAPPING_PATHS)},
        ],
        "artifacts": artifacts,
        "scope": {
            "includes": [
                "static protocol contracts",
                "static project mapping descriptors",
                "synthetic conformance fixtures",
            ],
            "excludes": [
                "shared runtime",
                "command line interface",
                "package",
                "plugin",
                "skill",
                "role pack",
                "publish",
                "consumer rollout",
            ],
        },
        "upgrade_policy": {
            "approval": "explicit-project-approval",
            "auto_update": False,
            "invalidation_triggers": [
                "source-commit-changed",
                "artifact-fingerprint-changed",
                "component-membership-changed",
            ],
        },
        "rollback_policy": {
            "strategy": "consumer-pins-previous-release",
            "preserve_project_runtime": True,
            "automatic_cleanup": False,
        },
    }


def serialize_manifest(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare without writing")
    args = parser.parse_args(argv)
    expected = serialize_manifest(build_manifest())
    output = REPO_ROOT / OUTPUT_PATH
    if args.check:
        if not output.is_file() or output.is_symlink() or output.read_bytes() != expected:
            print("status=blocked reason_code=release_manifest_stale")
            return 1
        print("status=passed reason_code=release_manifest_current")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(expected)
    print(f"status=passed output={OUTPUT_PATH.as_posix()} artifacts={len(SOURCE_PATHS)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except DistributionError as exc:
        print(f"status=error reason_code={exc.reason_code} detail={exc.detail}", file=sys.stderr)
        raise SystemExit(2)
