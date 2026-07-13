import copy
import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from research_director_common import load_document, proposal_fingerprint, sha256_file  # noqa: E402
from route_research_approval import route_proposal  # noqa: E402
from tests.portable_baseline_support import active as portable_baseline_active  # noqa: E402
from run_eth_cross_pair_generalization_campaign import (  # noqa: E402
    COMPILED_FINGERPRINT,
    CONSTITUTION_SHA256,
    POLICY_SHA256,
    STRATEGY_SHA256,
    slice_exact,
    validate_authority,
)


class EthCrossPairGeneralizationCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.approval = load_document(ROOT / "research/governance/approvals/eth-cross-pair-generalization-v1-approval.json")
        cls.proposal = load_document(ROOT / "research/director/proposals/eth-cross-pair-generalization-v1.json")
        cls.constitution = load_document(ROOT / "research/governance/research-constitution.yaml")
        cls.campaign = load_document(ROOT / "research/director/compiled/eth-cross-pair-generalization-v1/campaign.yaml")
        cls.authorization = load_document(ROOT / "research/director/compiled/eth-cross-pair-generalization-v1/execution-authorization.json")
        cls.manifest = load_document(ROOT / "research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml")
        cls.comparison = load_document(ROOT / "research/analysis/eth-cross-pair-generalization/run-comparison.json")
        cls.result = load_document(ROOT / "research/analysis/eth-cross-pair-generalization/cross-pair-generalization-result.json")

    def test_human_approval_freezes_exact_scope(self):
        scope = self.approval["scope"]
        self.assertEqual(scope["pair"], "ETH/USDT:USDT")
        self.assertEqual(scope["timeframe"], "1h")
        self.assertEqual(scope["coverage_source"], "futures-dev-btc-usdt-usdt-20240101-20240830-v2")
        self.assertEqual(scope["evaluation_1h_candles"], 5000)

    def test_medium_risk_route_requires_and_received_human_approval(self):
        route = route_proposal(self.proposal, self.constitution, self.approval)
        self.assertEqual(route["decision"], "human_approval_required")
        self.assertIn("new_pair", next(row for row in route["rule_decisions"] if row["rule"] == "risk_evidence")["details"]["medium_hits"])
        self.assertTrue(self.authorization["execution_authorized"])
        self.assertEqual(self.authorization["approval_route"], "human_approval_required_and_received")

    def test_proposal_and_campaign_fingerprints_are_frozen(self):
        self.assertEqual(proposal_fingerprint(self.proposal), self.proposal["semantic_fingerprint"])
        self.assertEqual(self.campaign["campaign_fingerprint"], COMPILED_FINGERPRINT)
        self.assertEqual(self.authorization["approved_compiled_fingerprint"], COMPILED_FINGERPRINT)

    def test_authority_hashes_and_prohibitions_hold(self):
        self.assertTrue(all(validate_authority(ROOT).values()))
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py"), STRATEGY_SHA256)
        self.assertEqual(sha256_file(ROOT / "research/governance/research-constitution.yaml"), CONSTITUTION_SHA256)
        self.assertEqual(sha256_file(ROOT / "research/evaluation/evaluation-policy.yaml"), POLICY_SHA256)

    def test_dataset_matches_btc_development_boundary(self):
        self.assertEqual(self.manifest["start"], "2024-01-01T00:00:00Z")
        self.assertEqual(self.manifest["end"], "2024-08-29T15:00:00Z")
        self.assertEqual(self.manifest["evaluation_range"]["main_1h_candles"], 5000)
        rows = {item["file"]: item["rows"] for item in self.manifest["coverage"]}
        self.assertEqual(rows["ETH_USDT_USDT-1h-futures.feather"], 5800)
        self.assertEqual(rows["ETH_USDT_USDT-4h-futures.feather"], 1450)
        self.assertEqual(rows["ETH_USDT_USDT-8h-mark.feather"], 725)
        self.assertEqual(rows["ETH_USDT_USDT-8h-funding_rate.feather"], 725)

    def test_sealed_dataset_files_match_manifest_hashes(self):
        if portable_baseline_active():
            self.skipTest("sealed dataset bytes are intentionally absent from the Portable Baseline Profile")
        self.assertTrue(self.manifest["sealed"])
        self.assertFalse(self.manifest["network_accessed_during_campaign"])
        for item in self.manifest["files"]:
            path = ROOT / item["path"]
            self.assertEqual(path.stat().st_size, item["bytes"])
            self.assertEqual(sha256_file(path), item["sha256"])

    def test_cadence_guard_fails_closed(self):
        frame = pd.DataFrame({"date": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T02:00:00Z"]), "open": [1, 1], "high": [1, 1], "low": [1, 1], "close": [1, 1], "volume": [1, 1]})
        with self.assertRaisesRegex(ValueError, "coverage_mismatch|cadence_or_gap_mismatch"):
            slice_exact(frame, pd.Timestamp("2024-01-01T02:00:00Z"), 2, "1h")

    def test_two_fresh_process_runs_are_reproducible(self):
        self.assertTrue(self.comparison["distinct_fresh_processes"])
        self.assertNotEqual(self.comparison["run_a"]["pid"], self.comparison["run_b"]["pid"])
        self.assertEqual(self.comparison["run_a"]["core_metrics_signature"], self.comparison["run_b"]["core_metrics_signature"])
        self.assertEqual(self.comparison["run_a"]["metrics"], self.comparison["run_b"]["metrics"])

    def test_network_access_is_limited_to_runner_loopback(self):
        for run in (self.comparison["run_a"], self.comparison["run_b"]):
            for attempt in run["network_attempts"]:
                self.assertFalse(attempt["blocked"])
                self.assertTrue(attempt["loopback"])
                self.assertEqual(attempt["host"], "127.0.0.1")

    def test_result_is_descriptive_and_does_not_overclaim(self):
        self.assertTrue(self.result["cross_pair_execution_behavior_observed"])
        self.assertFalse(self.result["cross_pair_generalization_proven"])
        self.assertFalse(self.result["profitability_claimed"])
        self.assertFalse(self.result["stage_promotion_allowed"])
        self.assertFalse(self.result["strategy_change_warranted"])

    def test_forbidden_surfaces_remain_unused(self):
        self.assertFalse(self.result["candidate_created"])
        self.assertFalse(self.result["hyperopt_run"])
        self.assertEqual(self.result["validation_accesses"], 0)
        self.assertEqual(self.result["holdout_accesses"], 0)
        self.assertFalse(self.result["evaluation_policy_modified"])

    def test_current_state_records_completed_eth_campaign(self):
        state = load_document(ROOT / "research/director/current-research-state.json")
        campaign = state["eth_cross_pair_generalization"]
        self.assertEqual(campaign["status"], "completed")
        self.assertTrue(campaign["reproducible"])
        self.assertFalse(campaign["cross_pair_generalization_proven"])
        self.assertEqual(state["data_capabilities"]["eth_development_dataset"], self.manifest["dataset_id"])

    def test_director_reports_no_automatic_followup(self):
        run = load_document(ROOT / "research/director/post-eth-cross-pair/proposals/director-run.json")
        self.assertEqual(run["recommendation"], "no_research_recommended")
        self.assertEqual(run["proposals"], [])
        rejected = {item["proposal_key"]: item["reason_code"] for item in run["rejected_proposals"]}
        self.assertEqual(rejected["eth-cross-pair-generalization-v1"], "duplicate_research_question")


if __name__ == "__main__":
    unittest.main()
