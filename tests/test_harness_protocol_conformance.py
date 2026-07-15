import ast
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
FIXTURE_CONTRACTS = {
    "normal": (
        "ProjectBinding",
        "PhaseAuthority",
        "CapabilityPolicy",
        "RoleContract",
        "TaskManifest",
        "GateResult",
        "RunState",
        "ApprovalRecord",
        "EscalationRecord",
        "EvidenceBundle",
    ),
    "governed-block": ("TaskManifest", "GateResult"),
    "tool-error": ("GateResult",),
    "authority-mismatch": ("TaskManifest", "GateResult"),
    "known-baseline-debt": ("EvidenceBundle",),
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
            self.assertEqual(
                fixture["fixture_version"],
                "harness-protocol-fixture-v0.1",
            )
            self.assertEqual(fixture["case_id"], case_id)
            contracts = [
                document["contract"] for document in fixture["documents"]
            ]
            self.assertEqual(len(contracts), len(FIXTURE_CONTRACTS[case_id]))
            self.assertCountEqual(contracts, FIXTURE_CONTRACTS[case_id])
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
        self.assertIn(
            "core.write_allowlisted_artifact",
            task["capabilities"],
        )
        self.assertEqual(
            (
                gate["outcome"],
                gate["process_exit_code"],
                gate["reason_code"],
                gate["local_reason_code"],
            ),
            (
                "blocked",
                1,
                "path_blocked",
                "blocked_path_overrides_allowlist",
            ),
        )

    def test_tool_failure_is_error_not_governed_block(self):
        gate = self.documents("tool-error", "GateResult")[0]
        self.assertEqual(
            (
                gate["outcome"],
                gate["process_exit_code"],
                gate["reason_code"],
                gate["local_reason_code"],
            ),
            (
                "error",
                2,
                "environment_unavailable",
                "validator_process_not_available",
            ),
        )

    def test_authority_mismatch_fails_closed(self):
        fixture = self.fixtures["authority-mismatch"]
        task = self.documents("authority-mismatch", "TaskManifest")[0]
        gate = self.documents("authority-mismatch", "GateResult")[0]
        self.assertEqual(
            task["authority_fingerprint"],
            f"sha256:{'2' * 64}",
        )
        self.assertEqual(
            fixture["context"]["current_authority_fingerprint"],
            f"sha256:{'3' * 64}",
        )
        self.assertNotEqual(
            task["authority_fingerprint"],
            fixture["context"]["current_authority_fingerprint"],
        )
        self.assertEqual(
            (
                gate["outcome"],
                gate["process_exit_code"],
                gate["reason_code"],
                gate["local_reason_code"],
            ),
            (
                "blocked",
                1,
                "authority_mismatch",
                "bound_authority_is_stale",
            ),
        )

    def test_known_debt_preserves_business_block_and_completion(self):
        evidence = self.documents("known-baseline-debt", "EvidenceBundle")[0]
        self.assertEqual(
            [
                (gate["outcome"], gate["process_exit_code"])
                for gate in evidence["gate_results"]
            ],
            [("passed", 0)],
        )
        self.assertEqual(
            [
                (result["outcome"], result["exit_code"])
                for result in evidence["command_results"]
            ],
            [("passed", 0)],
        )
        self.assertTrue(evidence["known_baseline_debt"])
        self.assertTrue(evidence["open_blockers"])
        self.assertEqual(evidence["business_readiness"], "blocked")
        self.assertEqual(evidence["harness_completion"], "completed")
        self.assertEqual(evidence["final_run_state"], "completed")

    def test_protocol_tests_do_not_import_project_runtime(self):
        allowed_top_level_modules = {
            "ast",
            "json",
            "pathlib",
            "re",
            "unittest",
            "jsonschema",
        }
        test_paths = (
            REPO_ROOT / "tests" / "test_harness_protocol_guard_contract.py",
            REPO_ROOT / "tests" / "test_harness_protocol_contracts.py",
            REPO_ROOT / "tests" / "test_harness_protocol_conformance.py",
        )
        for test_path in test_paths:
            tree = ast.parse(test_path.read_text(encoding="utf-8"))
            imported_modules = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_modules.update(
                        alias.name.split(".", 1)[0] for alias in node.names
                    )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_modules.add(node.module.split(".", 1)[0])
            with self.subTest(test_path=test_path.name):
                self.assertLessEqual(
                    imported_modules,
                    allowed_top_level_modules,
                )

    def test_protocol_json_contains_no_project_domain_literals(self):
        forbidden_literals = {
            "freqtrade",
            "binance",
            "btc/usdt",
            "chinasectorradar",
            "rehab-intervention",
            "prisma",
            "regimeaware",
            "holdout",
            "scheduler",
            "strategy_family",
        }
        json_paths = sorted(PROTOCOL_ROOT.rglob("*.json"))
        self.assertEqual(len(json_paths), 7)
        for json_path in json_paths:
            content = json_path.read_text(encoding="utf-8").lower()
            for literal in forbidden_literals:
                with self.subTest(path=json_path.name, literal=literal):
                    self.assertNotIn(literal, content)


if __name__ == "__main__":
    unittest.main()
