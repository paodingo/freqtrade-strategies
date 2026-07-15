#!/usr/bin/env python3
"""Verify the source-side static Harness Protocol distribution."""

from __future__ import annotations

import ast
import json
from pathlib import Path
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
    "sys",
    "typing",
    "build_harness_protocol_distribution",
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


def verify_repository(root: Path = REPO_ROOT) -> dict[str, Any]:
    root = root.resolve()
    schema = load_json_file(root / SCHEMA_PATH)
    manifest = load_json_file(root / OUTPUT_PATH)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(manifest), key=lambda error: list(error.absolute_path))
    if errors:
        raise DistributionError("release_manifest_schema_invalid", errors[0].message)
    if manifest != build_manifest(root):
        raise DistributionError("release_manifest_stale", "manifest differs from deterministic build")
    _assert_source_manifest_relationships(root)
    _assert_static_only_imports(root)
    return {
        "status": "passed",
        "reason_code": "static_distribution_verified",
        "artifact_count": len(manifest["artifacts"]),
        "source_commit": manifest["source_commit"],
        "fingerprint_profile": manifest["fingerprint_profile"],
    }


def main() -> int:
    try:
        result = verify_repository()
    except DistributionError as exc:
        print(f"status=blocked reason_code={exc.reason_code} detail={exc.detail}")
        return 1
    except (OSError, json.JSONDecodeError, SyntaxError) as exc:
        print(f"status=error reason_code=verification_tool_error detail={exc}", file=sys.stderr)
        return 2
    print(" ".join(f"{key}={value}" for key, value in result.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
