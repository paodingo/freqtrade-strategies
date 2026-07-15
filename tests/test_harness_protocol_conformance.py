import json
import unittest
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_ROOT = REPO_ROOT / "harness" / "protocol" / "v0.1"
FIXTURE_ROOT = PROTOCOL_ROOT / "fixtures"
FIXTURE_CASES = {
    "normal": ("passed", "fixture_conforms"),
    "governed-block": ("blocked", "path_blocked"),
    "tool-error": ("error", "environment_unavailable"),
    "authority-mismatch": ("blocked", "authority_mismatch"),
    "known-baseline-debt": ("passed", "known_baseline_debt_preserved"),
}
PORTABLE_EXIT_MAPPING = {0: "passed", 1: "blocked", 2: "error"}


class HarnessProtocolConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(
            (PROTOCOL_ROOT / "harness-protocol.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.fixtures = {
            case_id: json.loads(
                (FIXTURE_ROOT / f"{case_id}.json").read_text(encoding="utf-8")
            )
            for case_id in FIXTURE_CASES
        }

    def documents(self, case_id, contract):
        return [
            document["artifact"]
            for document in self.fixtures[case_id]["documents"]
            if document["contract"] == contract
        ]

    def test_every_document_conforms_to_declared_contract(self):
        for case_id, fixture in self.fixtures.items():
            for document in fixture["documents"]:
                target_schema = {
                    "$schema": self.schema["$schema"],
                    "$defs": self.schema["$defs"],
                    "$ref": f"#/$defs/{document['contract']}",
                }
                with self.subTest(
                    case_id=case_id,
                    contract=document["contract"],
                ):
                    Draft202012Validator(target_schema).validate(
                        document["artifact"]
                    )

    def test_fixture_outcomes_are_exact(self):
        for case_id, (outcome, reason_code) in FIXTURE_CASES.items():
            with self.subTest(case_id=case_id):
                self.assertEqual(
                    self.fixtures[case_id]["expected"],
                    {"outcome": outcome, "reason_code": reason_code},
                )

    def test_portable_exit_mapping_is_preserved(self):
        for case_id in FIXTURE_CASES:
            gates = self.documents(case_id, "GateResult")
            bundles = self.documents(case_id, "EvidenceBundle")
            gates.extend(
                gate for bundle in bundles for gate in bundle["gate_results"]
            )
            commands = [
                result
                for bundle in bundles
                for result in bundle["command_results"]
            ]
            for result in gates + commands:
                exit_code = result.get(
                    "process_exit_code",
                    result.get("exit_code"),
                )
                with self.subTest(case_id=case_id, result=result):
                    self.assertEqual(
                        result["outcome"],
                        PORTABLE_EXIT_MAPPING[exit_code],
                    )

    def test_blocked_path_overrides_allowed_path(self):
        fixture = self.fixtures["governed-block"]
        task = self.documents("governed-block", "TaskManifest")[0]
        gate = self.documents("governed-block", "GateResult")[0]
        attempted = PurePosixPath(fixture["context"]["attempted_path"])
        allowed = PurePosixPath(task["allowed_paths"][0])
        blocked = PurePosixPath(task["blocked_paths"][0])
        self.assertTrue(attempted.is_relative_to(allowed))
        self.assertTrue(attempted.is_relative_to(blocked))
        self.assertEqual(
            (gate["outcome"], gate["process_exit_code"], gate["reason_code"]),
            ("blocked", 1, "path_blocked"),
        )

    def test_tool_failure_is_error_not_governed_block(self):
        gate = self.documents("tool-error", "GateResult")[0]
        self.assertEqual(
            (gate["outcome"], gate["process_exit_code"], gate["reason_code"]),
            ("error", 2, "environment_unavailable"),
        )

    def test_authority_mismatch_fails_closed(self):
        fixture = self.fixtures["authority-mismatch"]
        task = self.documents("authority-mismatch", "TaskManifest")[0]
        gate = self.documents("authority-mismatch", "GateResult")[0]
        self.assertNotEqual(
            task["authority_fingerprint"],
            fixture["context"]["current_authority_fingerprint"],
        )
        self.assertEqual(
            (gate["outcome"], gate["process_exit_code"], gate["reason_code"]),
            ("blocked", 1, "authority_mismatch"),
        )

    def test_known_debt_preserves_business_block_and_completion(self):
        evidence = self.documents("known-baseline-debt", "EvidenceBundle")[0]
        self.assertTrue(evidence["known_baseline_debt"])
        self.assertTrue(evidence["open_blockers"])
        self.assertEqual(evidence["business_readiness"], "blocked")
        self.assertEqual(evidence["harness_completion"], "completed")
        self.assertEqual(evidence["final_run_state"], "completed")


if __name__ == "__main__":
    unittest.main()
