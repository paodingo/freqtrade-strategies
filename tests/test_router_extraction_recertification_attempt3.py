import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from backtest_execution_namespace import tree_inventory  # noqa: E402
from research_director_common import proposal_fingerprint, sha256_file  # noqa: E402
from run_router_extraction_semantic_equivalence_campaign import BASE_SHA256, CANDIDATE_SHA256, STRATEGY_SHA256  # noqa: E402


class RouterExtractionRecertificationAttempt3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = ROOT / "research/analysis/regime-conditioned-branch-factorization"
        cls.final = json.loads((base / "recertification-attempt-3-semantic-equivalence-result.json").read_text(encoding="utf-8"))
        cls.pairs = {
            pair: json.loads((base / f"recertification-attempt-3-{pair}-semantic-equivalence-comparison.json").read_text(encoding="utf-8"))
            for pair in ("btc", "eth")
        }

    def test_success_requires_all_eight_current_workers(self):
        self.assertEqual(self.final["status"], "router_extraction_semantic_equivalence_verified")
        self.assertEqual(self.final["backtest_calls"], 8)
        self.assertEqual(len(set(self.final["worker_pids"])), 8)

    def test_each_execution_namespace_is_unique_and_attempt_bound(self):
        runs = [run for pair in self.pairs.values() for run in pair["runs"]]
        roots = {run["output_root"] for run in runs}
        execution_ids = {run["execution_id"] for run in runs}
        self.assertEqual(len(roots), 8)
        self.assertEqual(len(execution_ids), 8)
        self.assertTrue(all("/recertification-attempt-3/" in root for root in roots))

    def test_raw_normalized_and_runner_counts_are_equal(self):
        for pair in self.pairs.values():
            for run in pair["runs"]:
                self.assertEqual(run["normalized_trade_count"], 27)
                self.assertEqual(run["summary"]["core"]["total_trades"], 27)
                self.assertTrue(run["raw_result_sha256"])

    def test_btc_and_eth_semantic_equivalence(self):
        for pair in self.pairs.values():
            self.assertTrue(pair["passed"])
            self.assertTrue(all(item["passed"] for item in pair["comparisons"].values()))

    def test_normalized_trade_hashes_are_pair_specific_and_reproducible(self):
        expected = {
            "btc": "94de8d81bea16a648a6f9a3e2c379cefde16e8240b71293ff724d19aecf45559",
            "eth": "f3cf00845c8852c254af8125f87d2b18ebe133f01c21c49c62822e8e43010d1b",
        }
        for pair, comparison in self.pairs.items():
            self.assertEqual({run["normalized_trade_hash"] for run in comparison["runs"]}, {expected[pair]})

    def test_contaminated_roots_remain_frozen(self):
        expected = {
            "2": "91996c1ef6a0b3a610035dc8ebff60fc785dcedfa6f912510226e3e1d0cb593b",
            "3": "d86fea0999835b66afd5983becc57e836655a09efcd8c2c6daa2779ffb2ab962",
        }
        for suffix, digest in expected.items():
            root = ROOT / f"research/results/stage4a-regime-conditioned-branch-factorization-v1/{suffix}"
            if root.exists():
                self.assertEqual(tree_inventory(root)["tree_sha256"], digest)
        registry = (ROOT / "research/governance/artifact-contamination-registry.yaml").read_text(encoding="utf-8")
        self.assertIn("research_use_allowed: false", registry)
        for digest in expected.values():
            self.assertIn(digest, registry)

    def test_next_proposal_is_pending_and_uncompiled(self):
        proposal_path = ROOT / "research/director/next-after-router-equivalence/proposals/branch-contribution-ablation-v1.json"
        status_path = ROOT / "research/director/next-after-router-equivalence/branch-contribution-ablation-v1-review-status.json"
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        status = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(proposal_fingerprint(proposal), proposal["semantic_fingerprint"])
        self.assertEqual(proposal["risk_class"], "medium")
        self.assertEqual(status["status"], "pending_human_review")
        self.assertFalse(status["compiled"])
        self.assertFalse(status["executed"])

    def test_protected_sources_and_access_boundaries_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "research/candidates/regime-conditioned-branch-factorization-v1/RegimeAwareRouterEquivalentV1.py"), CANDIDATE_SHA256)
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), STRATEGY_SHA256)
        self.assertEqual(sha256_file(ROOT / "strategies/regime_aware_base.py"), BASE_SHA256)
        self.assertEqual(self.final["validation_accesses"], 0)
        self.assertEqual(self.final["holdout_accesses"], 0)
        self.assertFalse(self.final["branch_ablation_run"])
        self.assertFalse(self.final["hyperopt_run"])

    def test_registry_links_attempt_lineage_and_pending_proposal(self):
        registry = json.loads((ROOT / "research/director/registry-records.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["integrity"], "ok")
        proposals = registry["tables"]["director_proposals"]
        row = next(item for item in proposals if item["proposal_id"] == "branch-contribution-ablation-v1")
        self.assertEqual(row["status"], "pending_human_review")
        assets = registry["tables"]["research_campaign_assets"]
        paths = {item["path"] for item in assets if item["run_id"] == "regime-conditioned-branch-factorization-v1-recertification-attempt-3"}
        self.assertIn("research/analysis/regime-conditioned-branch-factorization/recertification-attempt-3-lineage.json", paths)
        self.assertIn("research/analysis/regime-conditioned-branch-factorization/recertification-attempt-2-invalidation.json", paths)


if __name__ == "__main__":
    unittest.main()
