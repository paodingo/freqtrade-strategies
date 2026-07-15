import copy
import json
import re
import unittest
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_ROOT = REPO_ROOT / "harness" / "mappings" / "v0.1"
SCHEMA_PATH = MAPPING_ROOT / "project-mapping.schema.json"
MANIFEST_PATH = MAPPING_ROOT / "mapping-manifest.json"
PROJECT_PATHS = {
    "freqtrade-strategies": MAPPING_ROOT
    / "projects"
    / "freqtrade-strategies.json",
    "china-sector-radar": MAPPING_ROOT
    / "projects"
    / "china-sector-radar.json",
    "rehab-intervention": MAPPING_ROOT
    / "projects"
    / "rehab-intervention.json",
}
EXPECTED_CONTRACTS = [
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
EXPECTED_SOURCE_COMMITS = {
    "freqtrade-strategies": "fc621f1deee152689a2d79b3099a5da581486144",
    "china-sector-radar": "a8b99c74f43aeb1e34db600bdbd5608a888d2d7f",
    "rehab-intervention": "03ca6e841bf3d840307c5c802bb93d637b60b0c0",
}


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_object_schemas(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for value in node.values():
            yield from iter_object_schemas(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_object_schemas(value)


class HarnessProjectMappingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = load_json(SCHEMA_PATH)
        cls.manifest = load_json(MANIFEST_PATH)
        cls.projects = {
            project_id: load_json(path)
            for project_id, path in PROJECT_PATHS.items()
        }
        cls.validator = Draft202012Validator(cls.schema)

    def test_schema_is_valid_draft_2020_12(self):
        self.assertEqual(
            self.schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        try:
            Draft202012Validator.check_schema(self.schema)
        except SchemaError as error:
            self.fail(str(error))

    def test_manifest_indexes_exact_mapping_surface(self):
        self.assertEqual(
            self.manifest["mapping_manifest_version"],
            "harness-project-mapping-manifest-v0.1",
        )
        self.assertEqual(self.manifest["mapping_version"], "0.1")
        self.assertEqual(self.manifest["protocol_version"], "0.1")
        self.assertEqual(
            self.manifest["schema_path"],
            "project-mapping.schema.json",
        )
        self.assertEqual(
            self.manifest["project_mappings"],
            [
                {
                    "project_id": project_id,
                    "path": f"projects/{project_id}.json",
                    "source_commit": EXPECTED_SOURCE_COMMITS[project_id],
                }
                for project_id in PROJECT_PATHS
            ],
        )
        self.assertEqual(
            self.manifest["failure_fixtures"],
            [
                {
                    "path": "fixtures/source-stale.json",
                    "outcome": "blocked",
                    "reason_code": "source_identity_stale",
                },
                {
                    "path": "fixtures/authority-weakening.json",
                    "outcome": "blocked",
                    "reason_code": "authority_weakening",
                },
                {
                    "path": "fixtures/unmapped-gap.json",
                    "outcome": "blocked",
                    "reason_code": "contract_gap",
                },
            ],
        )

    def test_project_descriptors_validate_against_schema(self):
        for project_id, document in self.projects.items():
            with self.subTest(project_id=project_id):
                errors = list(self.validator.iter_errors(document))
                self.assertEqual(errors, [], [error.message for error in errors])

    def test_every_descriptor_covers_exact_protocol_contracts_once(self):
        for project_id, document in self.projects.items():
            names = [item["contract"] for item in document["contracts"]]
            with self.subTest(project_id=project_id):
                self.assertEqual(names, EXPECTED_CONTRACTS)
                self.assertEqual(len(names), len(set(names)))

    def test_source_identities_match_audit_snapshot(self):
        expected_branches = {
            "freqtrade-strategies": "codex/btc-mvp-system-p1-integrated",
            "china-sector-radar": "main",
            "rehab-intervention": "main",
        }
        for project_id, document in self.projects.items():
            identity = document["source_repository_identity"]
            with self.subTest(project_id=project_id):
                self.assertEqual(identity["repository_id"], project_id)
                self.assertEqual(
                    identity["source_commit"],
                    EXPECTED_SOURCE_COMMITS[project_id],
                )
                self.assertEqual(
                    identity["source_branch"],
                    expected_branches[project_id],
                )
                self.assertEqual(identity["status_at_audit"], "clean")

        rehab_authorities = self.projects["rehab-intervention"][
            "authority_precedence"
        ]
        self.assertEqual(rehab_authorities[0]["authority_kind"], "project_policy")
        self.assertNotIn(
            "human_approval",
            [item["authority_kind"] for item in rehab_authorities],
        )
        rehab_approval = next(
            item
            for item in self.projects["rehab-intervention"]["contracts"]
            if item["contract"] == "ApprovalRecord"
        )
        self.assertEqual(rehab_approval["mapping_status"], "gap")

    def test_source_refs_are_normalized_repo_relative_paths(self):
        scheme_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
        for project_id, document in self.projects.items():
            refs = [item["source_ref"] for item in document["authority_precedence"]]
            refs.extend(
                source_ref
                for contract in document["contracts"]
                for source_ref in contract["source_refs"]
            )
            for source_ref in refs:
                path = PurePosixPath(source_ref)
                with self.subTest(project_id=project_id, source_ref=source_ref):
                    self.assertFalse(source_ref.startswith("/"))
                    self.assertNotIn("\\", source_ref)
                    self.assertNotRegex(source_ref, scheme_pattern)
                    self.assertNotIn("", path.parts)
                    self.assertNotIn(".", path.parts)
                    self.assertNotIn("..", path.parts)
                    self.assertEqual(path.as_posix(), source_ref)

    def test_mapping_status_payloads_are_fail_closed(self):
        for project_id, document in self.projects.items():
            self.assertEqual(
                document["safety"],
                {
                    "authority_mode": "preserve_or_tighten",
                    "deny_unknown_capabilities": True,
                    "runtime_execution": False,
                    "sibling_writes": False,
                },
            )
            for contract in document["contracts"]:
                status = contract["mapping_status"]
                with self.subTest(project_id=project_id, contract=contract["contract"]):
                    if status == "gap":
                        self.assertEqual(contract["source_refs"], [])
                        self.assertTrue(contract["gaps"])
                        self.assertEqual(contract["instance_generation"], "forbidden")
                    else:
                        self.assertTrue(contract["source_refs"])
                        self.assertTrue(contract["preserved_rules"])
                        self.assertEqual(
                            contract["instance_generation"],
                            "not_implemented",
                        )

    def test_schema_closes_every_object_and_rejects_mutations(self):
        object_schemas = list(iter_object_schemas(self.schema))
        self.assertGreaterEqual(len(object_schemas), 4)
        for object_schema in object_schemas:
            self.assertIs(object_schema.get("additionalProperties"), False)

        for project_id, document in self.projects.items():
            missing_required = copy.deepcopy(document)
            del missing_required["project_id"]
            unknown_field = copy.deepcopy(document)
            unknown_field["unexpected"] = True
            invalid_status = copy.deepcopy(document)
            invalid_status["contracts"][0]["mapping_status"] = "complete"
            duplicate_contracts = copy.deepcopy(document)
            duplicate_contracts["contracts"] = [
                copy.deepcopy(document["contracts"][0]) for _ in range(11)
            ]
            invalid_gap = copy.deepcopy(document)
            invalid_gap["contracts"][0]["mapping_status"] = "gap"
            invalid_gap["contracts"][0]["gaps"] = []
            invalid_gap["contracts"][0]["instance_generation"] = "not_implemented"
            invalid_derived = copy.deepcopy(document)
            invalid_derived["contracts"][0]["source_refs"] = []
            invalid_derived["contracts"][0]["preserved_rules"] = []
            invalid_derived["contracts"][0]["instance_generation"] = "forbidden"
            for label, mutation in (
                ("missing_required", missing_required),
                ("unknown_field", unknown_field),
                ("invalid_status", invalid_status),
                ("duplicate_contracts", duplicate_contracts),
                ("invalid_gap", invalid_gap),
                ("invalid_derived", invalid_derived),
            ):
                with self.subTest(project_id=project_id, mutation=label):
                    self.assertFalse(self.validator.is_valid(mutation))


if __name__ == "__main__":
    unittest.main()
