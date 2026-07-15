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
        patterns = (
            r'\{\s*prefix:\s*["\']harness/protocol/',
            r'\{\s*regex:\s*/[^\n]*harness\\?/protocol',
        )
        for pattern in patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.guard_source))


if __name__ == "__main__":
    unittest.main()
