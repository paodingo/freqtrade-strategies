import ast
import copy
import json
import re
import unittest
from pathlib import Path, PurePosixPath


REPO_ROOT = Path(__file__).resolve().parents[1]
MAPPING_ROOT = REPO_ROOT / "harness" / "mappings" / "v0.1"
MANIFEST_PATH = MAPPING_ROOT / "mapping-manifest.json"
FIXTURE_PATHS = {
    "source-stale": MAPPING_ROOT / "fixtures" / "source-stale.json",
    "authority-weakening": MAPPING_ROOT / "fixtures" / "authority-weakening.json",
    "unmapped-gap": MAPPING_ROOT / "fixtures" / "unmapped-gap.json",
}
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
EXPECTED_FIXTURE_KEYS = {
    "fixture_version",
    "scenario",
    "project_id",
    "contract",
    "input",
    "expected",
}
EXPECTED_INPUT_KEYS = {
    "expected_source_commit",
    "observed_source_commit",
    "source_available",
    "parse_valid",
    "requested_authority_mode",
    "mapping_status",
    "instance_generation_requested",
    "capability_declared",
    "deny_unknown_capabilities",
}
EXPECTED_RESULT_KEYS = {"outcome", "reason_code"}
ABSOLUTE_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_mapping_request(payload):
    if not payload["parse_valid"]:
        return {"outcome": "error", "reason_code": "parser_error"}
    if not payload["source_available"]:
        return {"outcome": "blocked", "reason_code": "source_unavailable"}
    if payload["expected_source_commit"] != payload["observed_source_commit"]:
        return {"outcome": "blocked", "reason_code": "source_identity_stale"}
    if payload["requested_authority_mode"] != "preserve_or_tighten":
        return {"outcome": "blocked", "reason_code": "authority_weakening"}
    if payload["mapping_status"] == "gap" and payload[
        "instance_generation_requested"
    ]:
        return {"outcome": "blocked", "reason_code": "contract_gap"}
    if (
        payload["deny_unknown_capabilities"]
        and not payload["capability_declared"]
    ):
        return {"outcome": "blocked", "reason_code": "unknown_capability"}
    return {"outcome": "passed", "reason_code": "mapping_conformant"}


def iter_strings(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from iter_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_strings(value)
    elif isinstance(node, str):
        yield node


class HarnessProjectMappingConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(MANIFEST_PATH)
        cls.fixtures = {
            scenario: load_json(path)
            for scenario, path in FIXTURE_PATHS.items()
        }
        cls.projects = {
            project_id: load_json(path)
            for project_id, path in PROJECT_PATHS.items()
        }

    def test_manifest_indexes_exact_failure_fixture_outcomes(self):
        expected = [
            {
                "path": f"fixtures/{scenario}.json",
                **self.fixtures[scenario]["expected"],
            }
            for scenario in FIXTURE_PATHS
        ]
        self.assertEqual(self.manifest["failure_fixtures"], expected)

    def test_fixture_documents_have_closed_exact_structure(self):
        for scenario, fixture in self.fixtures.items():
            with self.subTest(scenario=scenario):
                self.assertEqual(set(fixture), EXPECTED_FIXTURE_KEYS)
                self.assertEqual(
                    fixture["fixture_version"],
                    "harness-project-mapping-fixture-v0.1",
                )
                self.assertEqual(fixture["scenario"], scenario)
                self.assertEqual(set(fixture["input"]), EXPECTED_INPUT_KEYS)
                self.assertEqual(set(fixture["expected"]), EXPECTED_RESULT_KEYS)

    def test_stale_source_identity_is_blocked(self):
        fixture = self.fixtures["source-stale"]
        self.assertNotEqual(
            fixture["input"]["expected_source_commit"],
            fixture["input"]["observed_source_commit"],
        )
        self.assertEqual(evaluate_mapping_request(fixture["input"]), fixture["expected"])

    def test_authority_weakening_is_blocked(self):
        fixture = self.fixtures["authority-weakening"]
        self.assertNotEqual(
            fixture["input"]["requested_authority_mode"],
            "preserve_or_tighten",
        )
        self.assertEqual(evaluate_mapping_request(fixture["input"]), fixture["expected"])

    def test_gap_cannot_generate_a_contract_instance(self):
        fixture = self.fixtures["unmapped-gap"]
        self.assertEqual(fixture["input"]["mapping_status"], "gap")
        self.assertIs(fixture["input"]["instance_generation_requested"], True)
        self.assertEqual(evaluate_mapping_request(fixture["input"]), fixture["expected"])

    def test_unknown_capability_missing_source_and_parser_error_stay_distinct(self):
        base = copy.deepcopy(self.fixtures["source-stale"]["input"])
        base["observed_source_commit"] = base["expected_source_commit"]

        unknown = copy.deepcopy(base)
        unknown["capability_declared"] = False
        unavailable = copy.deepcopy(base)
        unavailable["source_available"] = False
        parse_error = copy.deepcopy(base)
        parse_error["parse_valid"] = False

        self.assertEqual(
            evaluate_mapping_request(unknown),
            {"outcome": "blocked", "reason_code": "unknown_capability"},
        )
        self.assertEqual(
            evaluate_mapping_request(unavailable),
            {"outcome": "blocked", "reason_code": "source_unavailable"},
        )
        self.assertEqual(
            evaluate_mapping_request(parse_error),
            {"outcome": "error", "reason_code": "parser_error"},
        )

    def test_project_specific_truths_are_preserved(self):
        freqtrade_text = json.dumps(self.projects["freqtrade-strategies"])
        china_text = json.dumps(self.projects["china-sector-radar"])
        rehab_text = json.dumps(self.projects["rehab-intervention"])
        self.assertIn("timestamps must not be collapsed", freqtrade_text)
        self.assertIn("H1.1 review pass does not authorize H2", china_text)
        self.assertIn("Four registered H2 business-semantic blockers remain open", china_text)
        self.assertIn("generated state file remains local and ignored by git", rehab_text)
        self.assertIn("historical baseline debt", rehab_text.lower())

    def test_conformance_layer_is_static_and_contains_no_local_absolute_paths(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertEqual(imports, {"ast", "copy", "json", "re", "unittest", "pathlib"})

        for document in [*self.fixtures.values(), *self.projects.values()]:
            for value in iter_strings(document):
                with self.subTest(value=value):
                    self.assertFalse(ABSOLUTE_WINDOWS_PATH.match(value))
                    if "/" in value and " " not in value:
                        path = PurePosixPath(value)
                        self.assertNotIn("..", path.parts)


if __name__ == "__main__":
    unittest.main()
