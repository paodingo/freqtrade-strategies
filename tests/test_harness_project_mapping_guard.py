import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = REPO_ROOT / "scripts" / "guard_harness_diff.js"
EXPECTED_P2_PATHS = {
    "harness/mappings/v0.1/project-mapping.schema.json",
    "harness/mappings/v0.1/mapping-manifest.json",
    "harness/mappings/v0.1/projects/freqtrade-strategies.json",
    "harness/mappings/v0.1/projects/china-sector-radar.json",
    "harness/mappings/v0.1/projects/rehab-intervention.json",
    "harness/mappings/v0.1/fixtures/source-stale.json",
    "harness/mappings/v0.1/fixtures/authority-weakening.json",
    "harness/mappings/v0.1/fixtures/unmapped-gap.json",
    "tests/test_harness_project_mapping_guard.py",
    "tests/test_harness_project_mapping_contracts.py",
    "tests/test_harness_project_mapping_conformance.py",
}


def extract_low_risk_surfaces(guard_source):
    surfaces_match = re.search(
        r"const LOW_RISK_SURFACES = \[(.*?)\r?\n\];",
        guard_source,
        re.DOTALL,
    )
    if surfaces_match is None:
        raise AssertionError("LOW_RISK_SURFACES is missing")
    surfaces_source = surfaces_match.group(1)

    prefixes = []
    prefix_starts = list(re.finditer(r"\{\s*prefix\s*:", surfaces_source))
    for prefix_start in prefix_starts:
        cursor = prefix_start.end()
        while surfaces_source[cursor].isspace():
            cursor += 1
        quote = surfaces_source[cursor]
        if quote not in {'"', "'"}:
            raise AssertionError("prefix must use a string literal")
        cursor += 1
        characters = []
        while cursor < len(surfaces_source):
            character = surfaces_source[cursor]
            if character == quote:
                break
            if character == "\\":
                cursor += 1
                if cursor >= len(surfaces_source):
                    raise AssertionError("unterminated prefix escape")
                character = surfaces_source[cursor]
                if character not in {"\\", "/", '"', "'"}:
                    raise AssertionError("unsupported prefix escape")
            characters.append(character)
            cursor += 1
        if cursor >= len(surfaces_source):
            raise AssertionError("unterminated prefix")
        prefixes.append("".join(characters))
    if len(prefixes) != len(prefix_starts):
        raise AssertionError("prefix extraction is incomplete")

    regex_entries = []
    regex_starts = list(re.finditer(r"\{\s*regex\s*:", surfaces_source))
    for regex_start in regex_starts:
        cursor = regex_start.end()
        while surfaces_source[cursor].isspace():
            cursor += 1
        if surfaces_source[cursor] != "/":
            raise AssertionError("regex must use a literal")
        pattern_start = cursor + 1
        cursor = pattern_start
        escaped = False
        in_character_class = False
        while cursor < len(surfaces_source):
            character = surfaces_source[cursor]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "[":
                in_character_class = True
            elif character == "]":
                in_character_class = False
            elif character == "/" and not in_character_class:
                break
            cursor += 1
        if cursor >= len(surfaces_source):
            raise AssertionError("unterminated regex")
        javascript_pattern = surfaces_source[pattern_start:cursor]
        cursor += 1
        flags_start = cursor
        while cursor < len(surfaces_source) and surfaces_source[cursor].isalpha():
            cursor += 1
        javascript_flags = surfaces_source[flags_start:cursor]
        while surfaces_source[cursor].isspace():
            cursor += 1
        if surfaces_source[cursor] != "}":
            raise AssertionError("regex surface is malformed")
        regex_entries.append((javascript_pattern, javascript_flags))
    if len(regex_entries) != len(regex_starts):
        raise AssertionError("regex extraction is incomplete")
    return prefixes, regex_entries


class HarnessProjectMappingGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard_source = GUARD_PATH.read_text(encoding="utf-8")

    def test_every_p2_path_is_allowlisted_once_as_an_exact_path(self):
        for path in EXPECTED_P2_PATHS:
            with self.subTest(path=path):
                self.assertEqual(
                    self.guard_source.count(f'{{ exact: "{path}" }}'),
                    1,
                )

    def test_no_broad_mapping_prefix_or_regex_is_allowlisted(self):
        prefixes, regex_entries = extract_low_risk_surfaces(self.guard_source)
        for prefix in prefixes:
            for path in EXPECTED_P2_PATHS:
                with self.subTest(surface="prefix", value=prefix, path=path):
                    self.assertFalse(path.startswith(prefix))

        for javascript_pattern, javascript_flags in regex_entries:
            unsupported_flags = set(javascript_flags) - {"i", "m", "s", "u"}
            self.assertFalse(unsupported_flags)
            python_flags = 0
            if "i" in javascript_flags:
                python_flags |= re.IGNORECASE
            if "m" in javascript_flags:
                python_flags |= re.MULTILINE
            if "s" in javascript_flags:
                python_flags |= re.DOTALL
            compiled_pattern = re.compile(
                javascript_pattern.replace(r"\/", "/"),
                python_flags,
            )
            for path in EXPECTED_P2_PATHS:
                with self.subTest(
                    surface="regex",
                    value=javascript_pattern,
                    path=path,
                ):
                    self.assertIsNone(compiled_pattern.search(path))


if __name__ == "__main__":
    unittest.main()
