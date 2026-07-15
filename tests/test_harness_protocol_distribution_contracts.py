from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import sys
import unittest

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_harness_protocol_distribution as builder


class HarnessProtocolDistributionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads((REPO_ROOT / "harness/distribution/v0.1/distribution-manifest.schema.json").read_text(encoding="utf-8"))
        cls.manifest = builder.build_manifest(REPO_ROOT)
        cls.validator = Draft202012Validator(cls.schema)

    def test_01_distribution_schema_is_valid_draft_2020_12(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_02_manifest_has_exact_closed_shape(self) -> None:
        expected = {
            "distribution_version", "protocol_version", "mapping_version", "source_repository",
            "source_commit", "fingerprint_profile", "components", "artifacts", "scope",
            "upgrade_policy", "rollback_policy",
        }
        self.assertEqual(set(self.manifest), expected)
        self.assertEqual(list(self.validator.iter_errors(self.manifest)), [])
        self.assertFalse(self.schema["additionalProperties"])

    def test_03_manifest_has_exact_ordered_fifteen_file_source_set(self) -> None:
        paths = [artifact["path"] for artifact in self.manifest["artifacts"]]
        self.assertEqual(paths, list(builder.SOURCE_PATHS))
        self.assertEqual(len(paths), 15)

    def test_04_component_membership_is_exact(self) -> None:
        self.assertEqual(
            self.manifest["components"],
            [
                {"component_id": "protocol-core", "paths": list(builder.PROTOCOL_CORE_PATHS)},
                {"component_id": "project-mappings", "paths": list(builder.PROJECT_MAPPING_PATHS)},
            ],
        )
        membership = {path: component["component_id"] for component in self.manifest["components"] for path in component["paths"]}
        self.assertTrue(all(artifact["component_id"] == membership[artifact["path"]] for artifact in self.manifest["artifacts"]))

    def test_05_all_artifact_paths_are_repo_relative_posix_paths(self) -> None:
        for path in builder.SOURCE_PATHS:
            self.assertNotIn("\\", path)
            self.assertFalse(path.startswith("/"))
            self.assertNotIn("..", Path(path).parts)
            self.assertEqual(Path(path).as_posix(), path)

    def test_06_versions_repository_and_source_commit_are_bound(self) -> None:
        self.assertEqual(self.manifest["distribution_version"], "0.1")
        self.assertEqual(self.manifest["protocol_version"], "0.1")
        self.assertEqual(self.manifest["mapping_version"], "0.1")
        self.assertEqual(self.manifest["source_repository"], builder.SOURCE_REPOSITORY)
        self.assertEqual(self.manifest["source_commit"], builder.SOURCE_COMMIT)
        self.assertRegex(self.manifest["source_commit"], r"^[0-9a-f]{40}$")

    def test_07_scope_excludes_runtime_packaging_and_distribution_actions(self) -> None:
        excludes = set(self.manifest["scope"]["excludes"])
        self.assertTrue({"shared runtime", "command line interface", "package", "plugin", "skill", "role pack", "publish", "consumer rollout"}.issubset(excludes))
        self.assertFalse(self.manifest["upgrade_policy"]["auto_update"])
        self.assertFalse(self.manifest["rollback_policy"]["automatic_cleanup"])

    def test_08_unknown_duplicate_missing_fields_fail_closed_and_guard_is_exact(self) -> None:
        unknown = copy.deepcopy(self.manifest)
        unknown["unexpected"] = True
        missing = copy.deepcopy(self.manifest)
        del missing["source_commit"]
        self.assertTrue(list(self.validator.iter_errors(unknown)))
        self.assertTrue(list(self.validator.iter_errors(missing)))
        with self.assertRaisesRegex(builder.DistributionError, "duplicate JSON key"):
            builder.parse_json_text('{"source_commit":"a","source_commit":"b"}')

        guard = (REPO_ROOT / "scripts/guard_harness_diff.js").read_text(encoding="utf-8")
        exact_paths = (
            "harness/distribution/v0.1/distribution-manifest.schema.json",
            "harness/distribution/v0.1/fingerprint-profiles.json",
            "harness/distribution/v0.1/fingerprint-test-vectors.json",
            "harness/distribution/v0.1/release-manifest.json",
            "scripts/build_harness_protocol_distribution.py",
            "scripts/verify_harness_protocol_distribution.py",
            "tests/test_harness_protocol_distribution_contracts.py",
            "tests/test_harness_protocol_distribution_reproducibility.py",
            "docs/harness/harness-protocol-distribution-policy.md",
            "docs/harness/harness-protocol-distribution-policy.zh-CN.html",
        )
        for path in exact_paths:
            self.assertEqual(guard.count(f'{{ exact: "{path}" }}'), 1, path)
        self.assertIsNone(re.search(r"(?:prefix|regex):[^\n]*harness/distribution", guard))
        self.assertNotIn("scripts/build_harness_protocol_*", guard)


if __name__ == "__main__":
    unittest.main()
