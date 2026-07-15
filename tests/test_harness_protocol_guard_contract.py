import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = REPO_ROOT / "scripts" / "guard_harness_diff.js"
EXPECTED_P1_PATHS = {
    "harness/protocol/v0.1/harness-protocol.schema.json",
    "harness/protocol/v0.1/protocol-manifest.json",
    "harness/protocol/v0.1/fixtures/normal.json",
    "harness/protocol/v0.1/fixtures/governed-block.json",
    "harness/protocol/v0.1/fixtures/tool-error.json",
    "harness/protocol/v0.1/fixtures/authority-mismatch.json",
    "harness/protocol/v0.1/fixtures/known-baseline-debt.json",
    "tests/test_harness_protocol_guard_contract.py",
    "tests/test_harness_protocol_contracts.py",
    "tests/test_harness_protocol_conformance.py",
}


class HarnessProtocolGuardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard_source = GUARD_PATH.read_text(encoding="utf-8")

    def test_every_p1_path_is_allowlisted_as_an_exact_path(self):
        for path in EXPECTED_P1_PATHS:
            with self.subTest(path=path):
                self.assertEqual(
                    self.guard_source.count(f'{{ exact: "{path}" }}'),
                    1,
                )

    def test_no_broad_protocol_prefix_or_regex_is_allowlisted(self):
        surfaces_match = re.search(
            r"const LOW_RISK_SURFACES = \[(.*?)\r?\n\];",
            self.guard_source,
            re.DOTALL,
        )
        self.assertIsNotNone(surfaces_match)
        surfaces_source = surfaces_match.group(1)

        prefix_starts = list(
            re.finditer(r"\{\s*prefix\s*:", surfaces_source)
        )
        prefixes = []
        for prefix_start in prefix_starts:
            cursor = prefix_start.end()
            while surfaces_source[cursor].isspace():
                cursor += 1
            quote = surfaces_source[cursor]
            self.assertIn(quote, {'"', "'"})
            cursor += 1
            prefix_characters = []
            while cursor < len(surfaces_source):
                character = surfaces_source[cursor]
                if character == quote:
                    break
                if character == "\\":
                    cursor += 1
                    self.assertLess(cursor, len(surfaces_source))
                    escaped_character = surfaces_source[cursor]
                    self.assertIn(escaped_character, {"\\", "/", '"', "'"})
                    prefix_characters.append(escaped_character)
                else:
                    prefix_characters.append(character)
                cursor += 1
            self.assertLess(cursor, len(surfaces_source))
            prefixes.append("".join(prefix_characters))
        self.assertEqual(len(prefixes), len(prefix_starts))
        for prefix in prefixes:
            for path in EXPECTED_P1_PATHS:
                with self.subTest(surface="prefix", value=prefix, path=path):
                    self.assertFalse(path.startswith(prefix))

        regex_entries = []
        regex_starts = list(
            re.finditer(r"\{\s*regex\s*:", surfaces_source)
        )
        for regex_start in regex_starts:
            cursor = regex_start.end()
            while surfaces_source[cursor].isspace():
                cursor += 1
            self.assertEqual(surfaces_source[cursor], "/")
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
            self.assertLess(cursor, len(surfaces_source))
            javascript_pattern = surfaces_source[pattern_start:cursor]
            cursor += 1
            flags_start = cursor
            while (
                cursor < len(surfaces_source)
                and surfaces_source[cursor].isalpha()
            ):
                cursor += 1
            javascript_flags = surfaces_source[flags_start:cursor]
            while surfaces_source[cursor].isspace():
                cursor += 1
            self.assertEqual(surfaces_source[cursor], "}")
            regex_entries.append((javascript_pattern, javascript_flags))
        self.assertEqual(
            len(regex_entries),
            len(regex_starts),
        )
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
            for path in EXPECTED_P1_PATHS:
                with self.subTest(
                    surface="regex",
                    value=javascript_pattern,
                    path=path,
                ):
                    self.assertIsNone(compiled_pattern.search(path))


if __name__ == "__main__":
    unittest.main()
