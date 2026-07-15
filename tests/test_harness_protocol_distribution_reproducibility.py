from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_harness_protocol_distribution as builder
import verify_harness_protocol_distribution as verifier


class HarnessProtocolDistributionReproducibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vectors = {
            vector["vector_id"]: vector
            for vector in json.loads((REPO_ROOT / "harness/distribution/v0.1/fingerprint-test-vectors.json").read_text(encoding="utf-8"))["vectors"]
        }

    def _assert_vector_passes(self, vector_id: str) -> tuple[str, int]:
        vector = self.vectors[vector_id]
        result = builder.fingerprint_text_bytes(
            vector["input_text"].encode("utf-8"), validate_json=False
        )
        self.assertEqual(result, (vector["expected_fingerprint"], vector["expected_normalized_bytes"]))
        return result

    def test_01_lf_and_crlf_have_the_same_fingerprint(self) -> None:
        self.assertEqual(self._assert_vector_passes("lf-portable"), self._assert_vector_passes("crlf-portable"))

    def test_02_lone_cr_normalizes_to_lf(self) -> None:
        self.assertEqual(self._assert_vector_passes("lf-portable"), self._assert_vector_passes("cr-portable"))

    def test_03_utf8_bom_is_rejected(self) -> None:
        vector = self.vectors["bom-rejected"]
        with self.assertRaises(builder.DistributionError) as context:
            builder.fingerprint_text_bytes(bytes.fromhex(vector["input_hex"]))
        self.assertEqual(context.exception.reason_code, vector["expected_reason_code"])

    def test_04_invalid_utf8_is_rejected(self) -> None:
        vector = self.vectors["invalid-utf8-rejected"]
        with self.assertRaises(builder.DistributionError) as context:
            builder.fingerprint_text_bytes(bytes.fromhex(vector["input_hex"]))
        self.assertEqual(context.exception.reason_code, vector["expected_reason_code"])

    def test_05_duplicate_json_keys_are_rejected(self) -> None:
        vector = self.vectors["duplicate-json-key-rejected"]
        with self.assertRaises(builder.DistributionError) as context:
            builder.fingerprint_text_bytes(vector["input_text"].encode("utf-8"))
        self.assertEqual(context.exception.reason_code, vector["expected_reason_code"])

    def test_06_content_drift_changes_the_fingerprint(self) -> None:
        self.assertNotEqual(self._assert_vector_passes("drift-a")[0], self._assert_vector_passes("drift-b")[0])

    def test_07_independent_builds_are_byte_identical(self) -> None:
        first = builder.serialize_manifest(builder.build_manifest(REPO_ROOT))
        second = builder.serialize_manifest(builder.build_manifest(REPO_ROOT))
        self.assertEqual(first, second)
        self.assertTrue(first.endswith(b"\n"))
        self.assertNotIn(b"\r", first)

    def test_08_builder_and_verifier_are_static_source_side_only(self) -> None:
        forbidden_roots = {"requests", "urllib", "http", "socket", "subprocess", "freqtrade", "research", "strategies", "user_data"}
        for relative_path in (
            "scripts/build_harness_protocol_distribution.py",
            "scripts/verify_harness_protocol_distribution.py",
        ):
            tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
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
            self.assertFalse(imports & forbidden_roots, relative_path)
        result = verifier.verify_repository(REPO_ROOT)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["artifact_count"], 15)


if __name__ == "__main__":
    unittest.main()
