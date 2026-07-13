import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import backtest_execution_namespace as ns  # noqa: E402
from research_director_common import sha256_file  # noqa: E402
from run_offline_backtest import run_offline_backtest  # noqa: E402
from run_router_extraction_semantic_equivalence_campaign import (  # noqa: E402
    BASE_SHA256,
    CANDIDATE_SHA256,
    STRATEGY_SHA256,
)


class BacktestExecutionNamespaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="namespace-contract-"))
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.fields = {
            "campaign_id": "campaign",
            "proposal_id": "proposal",
            "research_unit": "unit",
            "attempt_id": "recertification-attempt-3",
            "pair_id": "btc-usdt-usdt",
            "role": "baseline",
            "repetition": "run-a",
            "execution_id": "execution-a",
        }
        self.attempt_root = self.repo / "research/results/campaign/unit/recertification-attempt-3"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def create(self, **changes):
        fields = {**self.fields, **changes}
        return ns.create_execution_namespace(self.repo, self.attempt_root, fields)

    def test_unique_execution_ids_produce_unique_roots(self):
        first = ns.expected_execution_root(self.repo, self.fields)
        second = ns.expected_execution_root(self.repo, {**self.fields, "execution_id": "execution-b"})
        self.assertNotEqual(first, second)

    def test_existing_output_root_is_rejected(self):
        self.create()
        with self.assertRaisesRegex(ns.NamespaceContractError, "already exists"):
            self.create()

    def test_nonempty_output_root_is_rejected(self):
        root = ns.expected_execution_root(self.repo, self.fields)
        root.mkdir(parents=True)
        (root / "stale.txt").write_text("stale", encoding="utf-8")
        with self.assertRaises(ns.NamespaceContractError):
            self.create()

    def test_attempt_two_and_three_do_not_share_path(self):
        third = ns.expected_execution_root(self.repo, self.fields)
        second = ns.expected_execution_root(self.repo, {**self.fields, "attempt_id": "recertification-attempt-2"})
        self.assertNotEqual(second, third)

    def test_baseline_and_candidate_are_isolated(self):
        self.assertNotEqual(ns.expected_execution_root(self.repo, self.fields), ns.expected_execution_root(self.repo, {**self.fields, "role": "candidate"}))

    def test_btc_and_eth_are_isolated(self):
        self.assertNotEqual(ns.expected_execution_root(self.repo, self.fields), ns.expected_execution_root(self.repo, {**self.fields, "pair_id": "eth-usdt-usdt"}))

    def test_run_a_and_b_are_isolated(self):
        self.assertNotEqual(ns.expected_execution_root(self.repo, self.fields), ns.expected_execution_root(self.repo, {**self.fields, "repetition": "run-b"}))

    def test_all_namespace_fields_are_present_in_audit(self):
        _root, audit = self.create()
        self.assertEqual(audit["namespace_fields"], self.fields)
        self.assertEqual(audit["validation_verdict"], "approved")

    def test_parent_traversal_is_rejected(self):
        with self.assertRaises(ns.NamespaceContractError):
            ns.expected_execution_root(self.repo, {**self.fields, "execution_id": ".."})

    def test_separator_in_namespace_field_is_rejected(self):
        with self.assertRaises(ns.NamespaceContractError):
            ns.expected_execution_root(self.repo, {**self.fields, "execution_id": "a/b"})

    def test_symlink_or_junction_ancestor_is_rejected(self):
        with mock.patch("backtest_execution_namespace._is_reparse_point", return_value=True):
            with self.assertRaisesRegex(ns.NamespaceContractError, "symlink or junction"):
                self.create()

    def test_strict_runner_rejects_missing_context(self):
        with self.assertRaisesRegex(ns.NamespaceContractError, "both required"):
            run_offline_backtest(self.repo, {"campaign_id": "campaign"}, 1, "x", self.repo, output_root=self.repo / "x")

    def test_strict_runner_rejects_execution_id_drift(self):
        root, _audit = self.create()
        with self.assertRaisesRegex(ns.NamespaceContractError, "execution ID differs"):
            run_offline_backtest(
                self.repo,
                {"campaign_id": "campaign"},
                1,
                "unexpected",
                self.repo,
                output_root=root,
                execution_context={"execution_id": "execution-a"},
            )

    def test_exact_raw_result_is_extracted_from_named_archive(self):
        root, _audit = self.create()
        archive = root / "backtest-result-execution-a.zip"
        payload = b'{"strategy": {}}'
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("backtest-result-execution-a.json", payload)
        result = root / "backtest-result-execution-a.json"
        binding = ns.extract_exact_result(archive, result, result.name, root, 0)
        self.assertEqual(result.read_bytes(), payload)
        self.assertEqual(binding["raw_result_sha256"], ns.sha256_file(result))

    def test_old_result_member_is_not_accepted(self):
        root, _audit = self.create()
        archive = root / "backtest-result-execution-a.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("backtest-result-old.json", "{}")
        with self.assertRaisesRegex(ns.NamespaceContractError, "expected raw result member missing"):
            ns.extract_exact_result(archive, root / "expected.json", "expected.json", root, 0)

    def test_last_result_pointer_is_not_a_result_source(self):
        root, _audit = self.create()
        (root / ".last_result.json").write_text('{"latest_backtest":"old.zip"}', encoding="utf-8")
        with self.assertRaises(ns.NamespaceContractError):
            ns.extract_exact_result(root / "expected.zip", root / "expected.json", "expected.json", root, 0)

    def test_pre_execution_result_is_rejected(self):
        root, _audit = self.create()
        archive = root / "expected.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("expected.json", "{}")
        with self.assertRaisesRegex(ns.NamespaceContractError, "predates"):
            ns.extract_exact_result(archive, root / "expected.json", "expected.json", root, archive.stat().st_mtime_ns + 1)

    def test_normalized_and_raw_counts_must_match(self):
        with self.assertRaisesRegex(ns.NamespaceContractError, "raw=2"):
            ns.validate_trade_counts(2, 1, 1)

    def test_normalized_and_runner_counts_must_match(self):
        with self.assertRaisesRegex(ns.NamespaceContractError, "runner=2"):
            ns.validate_trade_counts(1, 1, 2)

    def test_nonzero_runner_and_zero_normalized_is_rejected(self):
        with self.assertRaises(ns.NamespaceContractError):
            ns.validate_trade_counts(3, 0, 3)

    def test_matching_trade_counts_pass(self):
        ns.validate_trade_counts(27, 27, 27)

    def test_contaminated_roots_are_rejected(self):
        fields = {**self.fields, "research_unit": "2", "attempt_id": "x"}
        expected = self.repo / "research/results/campaign/2/x/btc-usdt-usdt/baseline/run-a/execution-a"
        with self.assertRaises(ns.NamespaceContractError):
            ns.validate_output_root(self.repo, self.repo / "research/results/campaign/2", expected, fields)

    def test_cross_namespace_write_is_detected(self):
        monitored = self.repo / "monitored"
        monitored.mkdir()
        before = ns.tree_inventory(monitored)
        (monitored / "unexpected.txt").write_text("changed", encoding="utf-8")
        after = ns.tree_inventory(monitored)
        with self.assertRaisesRegex(ns.NamespaceContractError, "tree changed"):
            ns.assert_tree_unchanged(before, after)

    def test_runner_report_rejects_stale_attempt(self):
        root, _audit = self.create()
        with self.assertRaisesRegex(ns.NamespaceContractError, "attempt or execution"):
            ns.validate_report_bindings({"attempt_id": "recertification-attempt-2", "execution_id": "execution-a"}, root, self.fields["attempt_id"], "execution-a")

    def test_all_eight_invalid_worker_results_are_stale(self):
        comparisons = [
            ROOT / "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-2-btc-semantic-equivalence-comparison.json",
            ROOT / "research/analysis/regime-conditioned-branch-factorization/recertification-attempt-2-eth-semantic-equivalence-comparison.json",
        ]
        stale = 0
        for path in comparisons:
            payload = json.loads(path.read_text(encoding="utf-8"))
            for run in payload["runs"]:
                stale += int("/recertification-attempt-2/" not in run["runner_report"].replace("\\", "/"))
        self.assertEqual(stale, 8)

    def test_candidate_and_formal_sources_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"), CANDIDATE_SHA256)
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), STRATEGY_SHA256)
        self.assertEqual(sha256_file(ROOT / "strategies/regime_aware_base.py"), BASE_SHA256)


if __name__ == "__main__":
    unittest.main()
