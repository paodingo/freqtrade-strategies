import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from protected_manifest_hash import (  # noqa: E402
    ProtectedManifestError,
    canonical_manifest_bytes,
    canonical_text_sha256,
    semantic_manifest_fingerprint,
    validate_protected_manifests,
)
from research_director_common import load_document, sha256_file, write_yaml  # noqa: E402
import protected_manifest_hash as protected_hash  # noqa: E402


class ProtectedManifestHashContractTests(unittest.TestCase):
    def test_frozen_text_hash_accepts_exact_or_checkout_normalized_bytes(self):
        self.assertTrue(
            hasattr(protected_hash, "checkout_stable_text_sha256_matches"),
            "checkout-stable frozen text matcher is missing",
        )
        expected_lf = hashlib.sha256(b'{"value": 1}\n').hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frozen.json"
            path.write_bytes(b'{"value": 1}\r\n')
            self.assertTrue(
                protected_hash.checkout_stable_text_sha256_matches(path, expected_lf)
            )
            path.write_bytes(b'{"value": 2}\r\n')
            self.assertFalse(
                protected_hash.checkout_stable_text_sha256_matches(path, expected_lf)
            )

    def test_lf_and_crlf_have_same_canonical_hash(self):
        self.assertEqual(canonical_text_sha256(b"a: 1\n"), canonical_text_sha256(b"a: 1\r\n"))

    def test_utf8_bom_is_removed(self):
        self.assertEqual(canonical_text_sha256(b"a: 1\n"), canonical_text_sha256(b"\xef\xbb\xbfa: 1\n"))

    def test_final_newlines_normalize_to_exactly_one(self):
        expected = b"a: 1\n"
        self.assertEqual(canonical_manifest_bytes(b"a: 1"), expected)
        self.assertEqual(canonical_manifest_bytes(b"a: 1\n\n\n"), expected)

    def test_value_change_changes_canonical_and_semantic_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            one = Path(directory) / "one.yaml"
            two = Path(directory) / "two.yaml"
            one.write_text("a: 1\n", encoding="utf-8")
            two.write_text("a: 2\n", encoding="utf-8")
            self.assertNotEqual(canonical_text_sha256(one), canonical_text_sha256(two))
            self.assertNotEqual(semantic_manifest_fingerprint(one), semantic_manifest_fingerprint(two))

    def test_comments_and_mapping_order_are_textual_but_not_semantic(self):
        with tempfile.TemporaryDirectory() as directory:
            one = Path(directory) / "one.yaml"
            two = Path(directory) / "two.yaml"
            one.write_text("a: 1\nb: 2\n", encoding="utf-8")
            two.write_text("# note\nb: 2\na: 1\n", encoding="utf-8")
            self.assertNotEqual(canonical_text_sha256(one), canonical_text_sha256(two))
            self.assertEqual(semantic_manifest_fingerprint(one), semantic_manifest_fingerprint(two))

    def test_raw_hash_is_diagnostic_not_gate(self):
        registry = load_document(ROOT / "research/governance/protected-manifest-hash-registry.yaml")
        record = registry["manifests"][0]
        raw_lf = canonical_manifest_bytes((ROOT / record["path"]).read_bytes())
        raw_crlf = raw_lf.replace(b"\n", b"\r\n")
        self.assertNotEqual(hashlib.sha256(raw_lf).hexdigest(), hashlib.sha256(raw_crlf).hexdigest())
        self.assertEqual(canonical_text_sha256(raw_lf), canonical_text_sha256(raw_crlf))
        self.assertTrue(validate_protected_manifests(ROOT)["passed"])

    def registry_failure(self, field, value):
        registry = load_document(ROOT / "research/governance/protected-manifest-hash-registry.yaml")
        registry["manifests"][0][field] = value
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.yaml"
            write_yaml(path, registry)
            with self.assertRaises(ProtectedManifestError):
                validate_protected_manifests(ROOT, str(path))

    def test_canonical_hash_mismatch_blocks(self):
        self.registry_failure("canonical_text_sha256", "0" * 64)

    def test_semantic_fingerprint_mismatch_blocks(self):
        self.registry_failure("semantic_fingerprint", "0" * 64)

    def test_aggregate_hash_mismatch_blocks(self):
        self.registry_failure("aggregate_hash", "0" * 64)

    def test_git_eol_diagnostics_and_attributes_cover_all_manifests(self):
        registry = load_document(ROOT / "research/governance/protected-manifest-hash-registry.yaml")
        for record in registry["manifests"]:
            output = subprocess.check_output(["git", "ls-files", "--eol", "--", record["path"]], cwd=ROOT, text=True)
            self.assertIn("i/lf", output)
            self.assertRegex(output, r"w/(?:lf|crlf)")
            self.assertIn("eol=lf", output)

    def test_current_protected_manifests_match_registry(self):
        result = validate_protected_manifests(ROOT)
        self.assertTrue(result["passed"])
        self.assertFalse(result["raw_worktree_hash_gate"])
        self.assertEqual(len(result["manifests"]), 3)

    def test_no_dataset_or_snapshot_payload_is_modified(self):
        changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines()
        self.assertFalse(any("/data/" in path or path.endswith(".feather") for path in changed))
        self.assertFalse(any(path.startswith("research/exchange_snapshots/") for path in changed))

    def test_strategy_policy_runtime_hashes_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509")
        self.assertEqual(sha256_file(ROOT / "research/evaluation/evaluation-policy.yaml"), "ee4769e4c814e209e771c31fa35ff4d8c4719137fffe7291d3ae87d73c8e8b5e")
        self.assertEqual(sha256_file(ROOT / "research/runtime/freqtrade-runtime.yaml"), "e87e375a8c61d8b7eeae8e53fc0715840956ea617471ad9c7d06275d9726f76d")


if __name__ == "__main__":
    unittest.main()
