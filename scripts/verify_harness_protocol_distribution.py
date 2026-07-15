#!/usr/bin/env python3
"""Verify the source-side static Harness Protocol distribution."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
from typing import Any

from jsonschema import Draft202012Validator

from build_harness_protocol_distribution import (
    DistributionError,
    OUTPUT_PATH,
    PROJECT_MAPPING_PATHS,
    PROTOCOL_CORE_PATHS,
    REPO_ROOT,
    build_manifest,
    load_json_file,
)


SCHEMA_PATH = Path("harness/distribution/v0.1/distribution-manifest.schema.json")
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "ast",
    "hashlib",
    "json",
    "jsonschema",
    "pathlib",
    "re",
    "sys",
    "typing",
    "build_harness_protocol_distribution",
}
SENSITIVE_MATERIAL_KEYS = {
    "password",
    "passwd",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "secret_key",
    "private_key",
    "credential",
    "credentials",
}
PROTOCOL_DOMAIN_LITERALS = {
    "freqtrade",
    "china-sector-radar",
    "rehab-intervention",
    "bitcoin",
    "btc/usdt",
    "sector rotation",
    "patient",
}
PARSER_ERROR_REASON_CODES = {
    "utf8_bom_rejected",
    "invalid_utf8",
    "invalid_json",
    "duplicate_json_key",
}


def _assert_static_only_imports(root: Path) -> None:
    for relative_path in (
        "scripts/build_harness_protocol_distribution.py",
        "scripts/verify_harness_protocol_distribution.py",
    ):
        path = root / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_path)
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for module in imported:
                if module.split(".")[0] not in ALLOWED_IMPORT_ROOTS:
                    raise DistributionError("non_static_import", f"{relative_path}: {module}")


def _assert_source_manifest_relationships(root: Path) -> None:
    protocol = load_json_file(root / "harness/protocol/v0.1/protocol-manifest.json")
    mapping = load_json_file(root / "harness/mappings/v0.1/mapping-manifest.json")
    if protocol.get("protocol_version") != "0.1" or mapping.get("protocol_version") != "0.1":
        raise DistributionError("protocol_version_mismatch", "P1/P2 protocol versions differ")
    if mapping.get("mapping_version") != "0.1":
        raise DistributionError("mapping_version_mismatch", repr(mapping.get("mapping_version")))
    protocol_paths = {
        "harness/protocol/v0.1/harness-protocol.schema.json",
        "harness/protocol/v0.1/protocol-manifest.json",
        *(f"harness/protocol/v0.1/{entry['path']}" for entry in protocol.get("fixtures", [])),
    }
    mapping_paths = {
        "harness/mappings/v0.1/project-mapping.schema.json",
        "harness/mappings/v0.1/mapping-manifest.json",
        *(f"harness/mappings/v0.1/{entry['path']}" for entry in mapping.get("project_mappings", [])),
        *(f"harness/mappings/v0.1/{entry['path']}" for entry in mapping.get("failure_fixtures", [])),
    }
    if protocol_paths != set(PROTOCOL_CORE_PATHS):
        raise DistributionError("protocol_component_mismatch", repr(sorted(protocol_paths)))
    if mapping_paths != set(PROJECT_MAPPING_PATHS):
        raise DistributionError("mapping_component_mismatch", repr(sorted(mapping_paths)))


def assert_manifest_identity_contract(manifest: dict[str, Any]) -> None:
    artifact_paths = [artifact.get("path") for artifact in manifest.get("artifacts", [])]
    expected_paths = list(PROTOCOL_CORE_PATHS + PROJECT_MAPPING_PATHS)
    if artifact_paths != expected_paths:
        raise DistributionError("artifact_identity_mismatch", repr(artifact_paths))
    if len(set(artifact_paths)) != len(artifact_paths):
        raise DistributionError("duplicate_artifact_path", repr(artifact_paths))
    expected_components = [
        {"component_id": "protocol-core", "paths": list(PROTOCOL_CORE_PATHS)},
        {"component_id": "project-mappings", "paths": list(PROJECT_MAPPING_PATHS)},
    ]
    if manifest.get("components") != expected_components:
        raise DistributionError("component_identity_mismatch", repr(manifest.get("components")))
    if manifest.get("fingerprint_profile") != "sha256-text-lf-v1":
        raise DistributionError("unknown_fingerprint_profile", repr(manifest.get("fingerprint_profile")))
    membership = {
        path: component["component_id"]
        for component in expected_components
        for path in component["paths"]
    }
    if any(
        artifact.get("component_id") != membership.get(artifact.get("path"))
        for artifact in manifest.get("artifacts", [])
    ):
        raise DistributionError("artifact_component_mismatch", "artifact membership differs")


def _walk_json(document: Any):
    if isinstance(document, dict):
        for key, value in document.items():
            yield key, value
            yield from _walk_json(value)
    elif isinstance(document, list):
        for value in document:
            yield from _walk_json(value)


def _assert_no_absolute_paths_or_secret_material(root: Path) -> None:
    windows_absolute = re.compile(r"^[A-Za-z]:[\\/]")
    for relative_path in PROTOCOL_CORE_PATHS + PROJECT_MAPPING_PATHS:
        document = load_json_file(root / relative_path)
        for key, value in _walk_json(document):
            if key.casefold() in SENSITIVE_MATERIAL_KEYS:
                raise DistributionError("secret_material_key", f"{relative_path}: {key}")
            if isinstance(value, str) and (
                value.startswith("/")
                or value.startswith("\\\\")
                or windows_absolute.match(value)
            ):
                raise DistributionError("absolute_path_detected", f"{relative_path}: {value}")


def _assert_no_protocol_domain_drift(root: Path) -> None:
    for relative_path in PROTOCOL_CORE_PATHS:
        text = (root / relative_path).read_text(encoding="utf-8").casefold()
        for literal in PROTOCOL_DOMAIN_LITERALS:
            if literal in text:
                raise DistributionError("protocol_domain_drift", f"{relative_path}: {literal}")


def verify_repository(root: Path = REPO_ROOT) -> dict[str, Any]:
    root = root.resolve()
    schema = load_json_file(root / SCHEMA_PATH)
    manifest = load_json_file(root / OUTPUT_PATH)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.absolute_path))
    if errors:
        raise DistributionError("release_manifest_schema_invalid", errors[0].message)
    assert_manifest_identity_contract(manifest)
    if manifest != build_manifest(root):
        raise DistributionError("release_manifest_stale", "manifest differs from deterministic build")
    _assert_source_manifest_relationships(root)
    _assert_no_absolute_paths_or_secret_material(root)
    _assert_no_protocol_domain_drift(root)
    _assert_static_only_imports(root)
    return {
        "status": "passed",
        "reason_code": "static_distribution_verified",
        "artifact_count": len(manifest["artifacts"]),
        "source_commit": manifest["source_commit"],
        "fingerprint_profile": manifest["fingerprint_profile"],
    }


def exit_status_for_reason(reason_code: str) -> tuple[str, int]:
    if reason_code in PARSER_ERROR_REASON_CODES:
        return "error", 2
    return "blocked", 1


def main() -> int:
    try:
        result = verify_repository()
    except DistributionError as exc:
        status, exit_code = exit_status_for_reason(exc.reason_code)
        print(f"status={status} reason_code={exc.reason_code} detail={exc.detail}")
        return exit_code
    except (OSError, json.JSONDecodeError, SyntaxError) as exc:
        print(f"status=error reason_code=verification_tool_error detail={exc}", file=sys.stderr)
        return 2
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
