import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "harness" / "protocol" / "v0.1"
SCHEMA_PATH = PROTOCOL_ROOT / "harness-protocol.schema.json"
MANIFEST_PATH = PROTOCOL_ROOT / "protocol-manifest.json"
NORMAL_FIXTURE_PATH = PROTOCOL_ROOT / "fixtures" / "normal.json"

EXPECTED_SCHEMA_VERSIONS = {
    "ProjectBinding": "harness-project-binding-v0.1",
    "PhaseAuthority": "harness-phase-authority-v0.1",
    "CapabilityPolicy": "harness-capability-policy-v0.1",
    "RoleContract": "harness-role-contract-v0.1",
    "TaskManifest": "harness-task-manifest-v0.1",
    "GateResult": "harness-gate-result-v0.1",
    "RunState": "harness-run-state-v0.1",
    "ApprovalRecord": "harness-approval-record-v0.1",
    "EscalationRecord": "harness-escalation-record-v0.1",
    "EvidenceBundle": "harness-evidence-bundle-v0.1",
}
EXPECTED_CONTRACTS = set(EXPECTED_SCHEMA_VERSIONS) | {"Budget"}
EXPECTED_ORDERED_CONTRACTS = [
    "ProjectBinding",
    "PhaseAuthority",
    "CapabilityPolicy",
    "RoleContract",
    "TaskManifest",
    "Budget",
    "GateResult",
    "RunState",
    "ApprovalRecord",
    "EscalationRecord",
    "EvidenceBundle",
]
EXPECTED_FIXTURES = [
    {
        "path": "fixtures/normal.json",
        "outcome": "passed",
        "reason_code": "fixture_conforms",
    },
    {
        "path": "fixtures/governed-block.json",
        "outcome": "blocked",
        "reason_code": "path_blocked",
    },
    {
        "path": "fixtures/tool-error.json",
        "outcome": "error",
        "reason_code": "environment_unavailable",
    },
    {
        "path": "fixtures/authority-mismatch.json",
        "outcome": "blocked",
        "reason_code": "authority_mismatch",
    },
    {
        "path": "fixtures/known-baseline-debt.json",
        "outcome": "passed",
        "reason_code": "known_baseline_debt_preserved",
    },
]


class HarnessProtocolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.normal_fixture = json.loads(
            NORMAL_FIXTURE_PATH.read_text(encoding="utf-8")
        )

    def test_manifest_indexes_exact_protocol_surface(self):
        self.assertEqual(
            self.manifest["manifest_version"],
            "harness-protocol-manifest-v0.1",
        )
        self.assertEqual(self.manifest["protocol_version"], "0.1")
        self.assertEqual(
            self.manifest["schema_path"],
            "harness-protocol.schema.json",
        )
        self.assertEqual(
            self.manifest["fixture_version"],
            "harness-protocol-fixture-v0.1",
        )
        self.assertEqual(len(self.manifest["contracts"]), 11)
        self.assertEqual(
            self.manifest["contracts"],
            EXPECTED_ORDERED_CONTRACTS,
        )
        self.assertEqual(len(self.manifest["fixtures"]), 5)
        self.assertEqual(self.manifest["fixtures"], EXPECTED_FIXTURES)
        self.assertEqual(
            self.manifest["portable_exit_mapping"],
            {"0": "passed", "1": "blocked", "2": "error"},
        )
        self.assertEqual(
            self.manifest["scope"],
            {
                "includes": [
                    "language-neutral contracts",
                    "synthetic golden fixtures",
                    "isolated conformance tests",
                ],
                "excludes": [
                    "shared executable runtime",
                    "command line interface",
                    "project adapters",
                    "role packs",
                    "production integration",
                ],
            },
        )

    def test_schema_is_valid_draft_2020_12(self):
        self.assertEqual(
            self.schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        Draft202012Validator.check_schema(self.schema)

        def iter_schema_nodes(node, path=()):
            if isinstance(node, dict):
                yield path, node
                for key, value in node.items():
                    yield from iter_schema_nodes(value, path + (key,))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    yield from iter_schema_nodes(value, path + (index,))

        for path, schema_node in iter_schema_nodes(self.schema):
            if schema_node.get("type") == "object":
                with self.subTest(closed_object_schema=path):
                    self.assertIs(
                        schema_node.get("additionalProperties"),
                        False,
                    )

        def validator_for(definition_name):
            return Draft202012Validator(
                {
                    "$schema": self.schema["$schema"],
                    "$defs": self.schema["$defs"],
                    "$ref": f"#/$defs/{definition_name}",
                }
            )

        repo_path_validator = validator_for("repoPath")
        accepted_repo_paths = (
            "a",
            "authority/project.json",
            ".config/policy.json",
            "nested/name.with-dots.json",
        )
        rejected_repo_paths = (
            "",
            "/absolute/path",
            "C:/outside",
            "C:\\outside",
            "\\\\server\\share",
            "a\\b",
            ".",
            "..",
            "./a",
            "a/.",
            "../a",
            "a/../b",
            "a//b",
            "file:relative",
            "https://example.invalid/a",
            "urn:example:a",
        )
        for value in accepted_repo_paths:
            with self.subTest(accepted_repo_path=value):
                self.assertTrue(repo_path_validator.is_valid(value))
        for value in rejected_repo_paths:
            with self.subTest(rejected_repo_path=value):
                self.assertFalse(repo_path_validator.is_valid(value))

        timestamp_validator = validator_for("timestamp")
        accepted_timestamps = (
            "2026-07-15T00:00:00Z",
            "2026-07-15T23:59:59.123+23:59",
            "2026-07-15T01:02:03-00:30",
        )
        rejected_timestamps = (
            "not-a-date",
            "2026-07-15T00:00:00",
            "2026-13-15T00:00:00Z",
            "2026-07-15T24:00:00Z",
            "2026-07-15T00:60:00Z",
            "2026-07-15T00:00:60Z",
            "2026-07-15 00:00:00Z",
            "2026-07-15T00:00:00+24:00",
            "2026-07-15T00:00:00+00:60",
            "2026-07-15t00:00:00z",
            "2026-07-15T00:00:00Z\n",
        )
        for value in accepted_timestamps:
            with self.subTest(accepted_timestamp=value):
                self.assertTrue(timestamp_validator.is_valid(value))
        for value in rejected_timestamps:
            with self.subTest(rejected_timestamp=value):
                self.assertFalse(timestamp_validator.is_valid(value))

    def test_schema_exposes_only_approved_contracts(self):
        public_defs = {
            name
            for name, definition in self.schema["$defs"].items()
            if "schema_version" in definition.get("properties", {})
        } | {"Budget"}
        self.assertEqual(public_defs, EXPECTED_CONTRACTS)
        self.assertEqual(
            {
                item["$ref"].removeprefix("#/$defs/")
                for item in self.schema["oneOf"]
            },
            EXPECTED_CONTRACTS - {"Budget"},
        )

    def test_schema_versions_are_exact(self):
        for contract, version in EXPECTED_SCHEMA_VERSIONS.items():
            with self.subTest(contract=contract):
                self.assertEqual(
                    self.schema["$defs"][contract]["properties"]["schema_version"],
                    {"const": version},
                )

    def test_normal_fixture_has_one_valid_artifact_per_root_contract(self):
        documents = self.normal_fixture["documents"]
        self.assertEqual(
            {document["contract"] for document in documents},
            set(EXPECTED_SCHEMA_VERSIONS),
        )
        self.assertEqual(len(documents), len(EXPECTED_SCHEMA_VERSIONS))

        def resolve_local_ref(schema_node):
            resolved = schema_node
            visited_refs = set()
            while "$ref" in resolved:
                ref = resolved["$ref"]
                self.assertTrue(ref.startswith("#/"))
                self.assertNotIn(ref, visited_refs)
                visited_refs.add(ref)
                resolved = self.schema
                for token in ref[2:].split("/"):
                    token = token.replace("~1", "/").replace("~0", "~")
                    resolved = resolved[token]
            return resolved

        def select_instance_schema(schema_node, instance):
            selected = resolve_local_ref(schema_node)
            while True:
                branch_keyword = next(
                    (
                        keyword
                        for keyword in ("oneOf", "anyOf")
                        if keyword in selected
                    ),
                    None,
                )
                if branch_keyword is None:
                    return selected
                valid_branches = []
                for branch in selected[branch_keyword]:
                    branch_schema = {
                        "$schema": self.schema["$schema"],
                        "$defs": self.schema["$defs"],
                        **branch,
                    }
                    if Draft202012Validator(branch_schema).is_valid(instance):
                        valid_branches.append(branch)
                self.assertEqual(
                    len(valid_branches),
                    1,
                    f"canonical instance must select exactly one {branch_keyword} branch",
                )
                selected = resolve_local_ref(valid_branches[0])

        def walk_instance(instance, schema_node, path=()):
            selected_schema = select_instance_schema(schema_node, instance)
            yield path, instance, selected_schema
            if isinstance(instance, dict):
                properties = selected_schema.get("properties", {})
                for key, value in instance.items():
                    self.assertIn(key, properties)
                    yield from walk_instance(
                        value,
                        properties[key],
                        path + (key,),
                    )
            elif isinstance(instance, list):
                self.assertIn("items", selected_schema)
                for index, value in enumerate(instance):
                    yield from walk_instance(
                        value,
                        selected_schema["items"],
                        path + (index,),
                    )

        def deep_copy_and_get(instance, path):
            mutated = json.loads(json.dumps(instance))
            target = mutated
            for segment in path:
                target = target[segment]
            return mutated, target

        def replace_at_path(instance, path, replacement):
            mutated = json.loads(json.dumps(instance))
            if not path:
                return replacement
            target = mutated
            for segment in path[:-1]:
                target = target[segment]
            target[path[-1]] = replacement
            return mutated

        covered_object_paths = set()
        mutation_counts = {
            "remove_required": 0,
            "inject_unknown": 0,
            "replace_enum": 0,
        }
        for document in documents:
            target_schema = {
                "$schema": self.schema["$schema"],
                "$defs": self.schema["$defs"],
                "$ref": f"#/$defs/{document['contract']}",
            }
            validator = Draft202012Validator(target_schema)
            artifact = document["artifact"]
            with self.subTest(contract=document["contract"]):
                validator.validate(artifact)

            reachable_nodes = list(walk_instance(artifact, target_schema))
            for path, instance, selected_schema in reachable_nodes:
                path_label = "/".join(str(segment) for segment in path) or "<root>"
                if isinstance(instance, dict):
                    covered_object_paths.add((document["contract"], path_label))
                    for required_field in selected_schema.get("required", []):
                        self.assertIn(required_field, instance)
                        mutated, target = deep_copy_and_get(artifact, path)
                        del target[required_field]
                        with self.subTest(
                            contract=document["contract"],
                            mutation="remove_required",
                            path=path_label,
                            field=required_field,
                        ):
                            self.assertFalse(validator.is_valid(mutated))
                        mutation_counts["remove_required"] += 1

                    unknown_field = "__unexpected_protocol_field__"
                    self.assertNotIn(unknown_field, instance)
                    mutated, target = deep_copy_and_get(artifact, path)
                    target[unknown_field] = True
                    with self.subTest(
                        contract=document["contract"],
                        mutation="inject_unknown",
                        path=path_label,
                    ):
                        self.assertFalse(validator.is_valid(mutated))
                    mutation_counts["inject_unknown"] += 1

                if "enum" in selected_schema:
                    invalid_enum_value = "__invalid_enum_sentinel__"
                    self.assertIn(instance, selected_schema["enum"])
                    self.assertNotIn(invalid_enum_value, selected_schema["enum"])
                    mutated = replace_at_path(
                        artifact,
                        path,
                        invalid_enum_value,
                    )
                    with self.subTest(
                        contract=document["contract"],
                        mutation="replace_enum",
                        path=path_label,
                    ):
                        self.assertFalse(validator.is_valid(mutated))
                    mutation_counts["replace_enum"] += 1

        expected_nested_object_paths = {
            ("ProjectBinding", "runtime_entries/0"),
            ("ProjectBinding", "state_backend"),
            ("TaskManifest", "input_bindings/0"),
            ("TaskManifest", "budgets"),
            ("TaskManifest", "validation_commands/0"),
            ("TaskManifest", "validation_commands/0/exit_code_mapping"),
            ("GateResult", "evidence_refs/0"),
            ("ApprovalRecord", "bound_artifacts/0"),
            ("ApprovalRecord", "expiry_policy"),
            ("EvidenceBundle", "authority_snapshot"),
            ("EvidenceBundle", "input_identities/0"),
            ("EvidenceBundle", "gate_results/0"),
            ("EvidenceBundle", "gate_results/0/evidence_refs/0"),
            ("EvidenceBundle", "command_results/0"),
            ("EvidenceBundle", "artifact_refs/0"),
        }
        self.assertLessEqual(expected_nested_object_paths, covered_object_paths)
        for mutation, count in mutation_counts.items():
            with self.subTest(mutation=mutation):
                self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
