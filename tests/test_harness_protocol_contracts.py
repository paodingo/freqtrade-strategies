import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "harness" / "protocol" / "v0.1"
SCHEMA_PATH = PROTOCOL_ROOT / "harness-protocol.schema.json"
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


class HarnessProtocolContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.normal_fixture = json.loads(
            NORMAL_FIXTURE_PATH.read_text(encoding="utf-8")
        )

    def test_schema_is_valid_draft_2020_12(self):
        self.assertEqual(
            self.schema["$schema"],
            "https://json-schema.org/draft/2020-12/schema",
        )
        Draft202012Validator.check_schema(self.schema)
        for name, definition in self.schema["$defs"].items():
            if definition.get("type") == "object":
                with self.subTest(closed_definition=name):
                    self.assertIs(
                        definition.get("additionalProperties"),
                        False,
                    )

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
        for document in documents:
            target_schema = {
                "$schema": self.schema["$schema"],
                "$defs": self.schema["$defs"],
                "$ref": f"#/$defs/{document['contract']}",
            }
            with self.subTest(contract=document["contract"]):
                Draft202012Validator(target_schema).validate(
                    document["artifact"]
                )


if __name__ == "__main__":
    unittest.main()
