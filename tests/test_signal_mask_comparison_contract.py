import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document, sha256_file  # noqa: E402
from run_router_extraction_semantic_equivalence_campaign import (  # noqa: E402
    BASE_SHA256,
    CANDIDATE_SHA256,
    STRATEGY_SHA256,
    RuntimeIdentityFailure,
    audit_cross_role_identity,
    audit_runtime_identity,
    compare_signal_semantics,
    runtime_identity_projection,
    signal_semantic_projection,
    signal_semantic_projection_from_rows,
)


class SignalMaskComparisonContractTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "date": "2024-01-01T00:00:00+00:00",
                "enter_long": 1,
                "enter_short": 0,
                "exit_long": 0,
                "exit_short": 0,
                "enter_tag": "trending_long",
                "exit_tag": None,
            }
        ]

    def mask(self, **identity):
        semantic = signal_semantic_projection_from_rows("BTC/USDT:USDT", self.rows)
        return {
            "signal_semantic_projection": semantic,
            "runtime_identity_projection": identity,
            "unknown_runtime_metadata": "does_not_participate",
        }

    def identity(self, role="candidate", repetition="A"):
        candidate = role == "candidate"
        return {
            "schema_version": "runtime_identity_projection_v1",
            "role": role,
            "strategy_class": "RegimeAwareRouterEquivalentV1" if candidate else "RegimeAwareV6",
            "module_name": "RegimeAwareRouterEquivalentV1" if candidate else "RegimeAwareV6",
            "module_path": str(ROOT / ("research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py" if candidate else "strategies/RegimeAwareV6.py")),
            "source_path": "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py" if candidate else "strategies/RegimeAwareV6.py",
            "source_sha256": CANDIDATE_SHA256 if candidate else STRATEGY_SHA256,
            "dependency_path": "strategies/regime_aware_base.py",
            "dependency_sha256": BASE_SHA256,
            "pid": 100 if repetition == "A" else 200,
            "execution_run_id": f"{role}-{repetition}",
            "runtime_versions": {"python": "3.12", "freqtrade": "2025.8", "ccxt": "4.5.64"},
            "experiment_id": 2,
        }

    def make_run(self, role="candidate", repetition="A"):
        identity = self.identity(role, repetition)
        return {"role": role, "pair_key": "btc", "signal_mask": self.mask(**identity), "runtime_identity_projection": identity}

    def assert_identity_difference_is_semantically_ignored(self, field, value):
        first = self.mask(**self.identity("baseline", "A"))
        second_identity = self.identity("candidate", "A")
        second_identity[field] = value
        second = self.mask(**second_identity)
        self.assertTrue(compare_signal_semantics(first, second)["passed"])

    def test_role_difference_does_not_change_semantics(self):
        self.assert_identity_difference_is_semantically_ignored("role", "candidate")

    def test_class_difference_does_not_change_semantics(self):
        self.assert_identity_difference_is_semantically_ignored("strategy_class", "DifferentCandidate")

    def test_module_path_difference_does_not_change_semantics(self):
        self.assert_identity_difference_is_semantically_ignored("module_path", "D:/isolated/candidate.py")

    def test_source_hash_difference_does_not_change_semantics(self):
        self.assert_identity_difference_is_semantically_ignored("source_sha256", "f" * 64)

    def assert_row_change_fails(self, field, value):
        first = {"signal_semantic_projection": signal_semantic_projection_from_rows("BTC/USDT:USDT", self.rows)}
        changed = copy.deepcopy(self.rows)
        changed[0][field] = value
        second = {"signal_semantic_projection": signal_semantic_projection_from_rows("BTC/USDT:USDT", changed)}
        self.assertFalse(compare_signal_semantics(first, second)["passed"])

    def test_enter_long_change_is_semantic_mismatch(self):
        self.assert_row_change_fails("enter_long", 0)

    def test_enter_short_change_is_semantic_mismatch(self):
        self.assert_row_change_fails("enter_short", 1)

    def test_exit_signal_change_is_semantic_mismatch(self):
        self.assert_row_change_fails("exit_long", 1)

    def test_tag_change_is_semantic_mismatch(self):
        self.assert_row_change_fails("enter_tag", "ranging_long")

    def test_timestamp_change_is_semantic_mismatch(self):
        self.assert_row_change_fails("date", "2024-01-01T01:00:00+00:00")

    def test_candidate_run_hash_drift_fails_identity_audit(self):
        first, second = self.make_run("candidate", "A"), self.make_run("candidate", "B")
        second["runtime_identity_projection"]["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeIdentityFailure, "source_sha256"):
            audit_runtime_identity(first, second, "candidate")

    def test_loaded_path_mismatch_fails_identity_audit(self):
        first, second = self.make_run("candidate", "A"), self.make_run("candidate", "B")
        first["runtime_identity_projection"]["source_path"] = "unexpected.py"
        second["runtime_identity_projection"]["source_path"] = "unexpected.py"
        with self.assertRaisesRegex(RuntimeIdentityFailure, "loaded source path/hash"):
            audit_runtime_identity(first, second, "candidate")

    def test_dependency_hash_mismatch_fails_identity_audit(self):
        first, second = self.make_run("candidate", "A"), self.make_run("candidate", "B")
        second["runtime_identity_projection"]["dependency_sha256"] = "0" * 64
        with self.assertRaisesRegex(RuntimeIdentityFailure, "dependency_sha256"):
            audit_runtime_identity(first, second, "candidate")

    def test_unknown_field_is_excluded_and_reported(self):
        first = signal_semantic_projection(self.mask(**self.identity()))
        changed = self.mask(**self.identity())
        changed["signal_semantic_projection"]["future_unknown_field"] = "new"
        second = signal_semantic_projection(changed)
        self.assertEqual(first["semantic_sha256"], second["semantic_sha256"])
        self.assertEqual(second["excluded_unknown_fields"], ["future_unknown_field"])

    def test_original_btc_artifacts_are_semantically_equivalent(self):
        original = load_document(ROOT / "research/analysis/regime-conditioned-branch-factorization/btc-semantic-equivalence-comparison.json")
        runs = {(item["role"], item["repetition"]): item for item in original["runs"]}
        self.assertTrue(compare_signal_semantics(runs[("baseline", "A")]["signal_mask"], runs[("candidate", "A")]["signal_mask"])["passed"])
        self.assertTrue(compare_signal_semantics(runs[("baseline", "B")]["signal_mask"], runs[("candidate", "B")]["signal_mask"])["passed"])

    def test_original_identity_differences_remain_visible(self):
        original = load_document(ROOT / "research/analysis/regime-conditioned-branch-factorization/btc-semantic-equivalence-comparison.json")
        runs = {(item["role"], item["repetition"]): item for item in original["runs"]}
        audit = audit_cross_role_identity(runs[("baseline", "A")], runs[("candidate", "A")])
        self.assertTrue(audit["passed"])
        self.assertEqual(set(audit["expected_differences"]), {"role", "strategy_class", "module_name", "module_path", "source_path", "source_sha256"})
        self.assertNotEqual(runtime_identity_projection(runs[("baseline", "A")])["source_sha256"], runtime_identity_projection(runs[("candidate", "A")])["source_sha256"])

    def test_candidate_source_is_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"), CANDIDATE_SHA256)

    def test_formal_strategy_is_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), STRATEGY_SHA256)

    def test_formal_base_is_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/regime_aware_base.py"), BASE_SHA256)


if __name__ == "__main__":
    unittest.main()
