from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compile_ranging_short_temporal_campaign import (  # noqa: E402
    CANDIDATE_PATH,
    CANDIDATE_SHA256,
    DATASET_AGGREGATE_SHA256,
    DATASET_ID,
    OLD_CAMPAIGN_FINGERPRINT,
    OUTPUT_DIR,
    PROPOSAL_FINGERPRINT,
    SLICE_POLICY_PATH,
    STRATEGY_PATH,
    STRATEGY_SHA256,
    TemporalSliceCompilationError,
    validate_slice_policy,
)
from research_director_common import fingerprint, load_document, sha256_file  # noqa: E402


class RangingShortTemporalCampaignCompilationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_document(ROOT / SLICE_POLICY_PATH)
        cls.campaign = load_document(ROOT / OUTPUT_DIR / "campaign.yaml")
        cls.queue = cls.campaign["experiment_queue"]
        cls.superseded = load_document(ROOT / OUTPUT_DIR / "superseded-campaign.json")
        cls.manifest = load_document(ROOT / "research/data/snapshots" / DATASET_ID / "manifest.yaml")

    def test_proposal_and_new_campaign_fingerprints_are_stable(self):
        self.assertEqual(self.campaign["proposal_fingerprint"], PROPOSAL_FINGERPRINT)
        computed = fingerprint({key: value for key, value in self.campaign.items() if key not in {"compiled_at", "campaign_fingerprint"}})
        self.assertEqual(computed, self.campaign["campaign_fingerprint"])
        self.assertNotEqual(computed, OLD_CAMPAIGN_FINGERPRINT)

    def test_exactly_5000_rows_are_four_sequential_1250_row_slices(self):
        slices = self.policy["slices"]
        self.assertEqual([item["evaluation_1h_candle_count"] for item in slices], [1250] * 4)
        rows = [row for item in slices for row in range(item["evaluation_row_start"], item["evaluation_row_end"] + 1)]
        self.assertEqual(rows, list(range(800, 5800)))

    def test_slices_have_no_overlap_gap_or_reordering(self):
        slices = self.policy["slices"]
        for left, right in zip(slices, slices[1:]):
            self.assertEqual(left["evaluation_row_end"] + 1, right["evaluation_row_start"])
            self.assertEqual(left["evaluation_end_exclusive"], right["evaluation_start"])
        self.assertEqual([item["slice_number"] for item in slices], [1, 2, 3, 4])

    def test_timestamp_gap_is_rejected(self):
        mutated = copy.deepcopy(self.policy)
        mutated["slices"][1]["evaluation_start"] = "2024-03-26T11:00:00Z"
        with self.assertRaisesRegex(TemporalSliceCompilationError, "slice_timestamp_gap"):
            validate_slice_policy(mutated, self.manifest)

    def test_warmup_is_independent_and_excluded_from_evaluation(self):
        for item in self.policy["slices"]:
            self.assertLess(item["warmup_start"], item["evaluation_start"])
            self.assertGreaterEqual(item["warmup_main_1h_candle_count"], 200)
            self.assertEqual(item["warmup_completed_4h_informative_candle_count"], 200)
            self.assertEqual(item["evaluation_1h_candle_count"], 1250)

    def test_informative_mark_and_funding_coverage_is_bound(self):
        for item in self.policy["slices"]:
            bindings = item["source_file_bindings"]
            self.assertEqual(len(bindings), 4)
            self.assertGreaterEqual(item["informative_4h_candle_count"], 512)
            self.assertGreater(item["mark_8h_candle_count"], 0)
            self.assertGreater(item["funding_8h_candle_count"], 0)

    def test_validation_candle_is_rejected(self):
        mutated = copy.deepcopy(self.policy)
        mutated["validation_data_allowed"] = True
        with self.assertRaisesRegex(TemporalSliceCompilationError, "validation_data_allowed"):
            validate_slice_policy(mutated, self.manifest)

    def test_stage3e1_slice_reuse_is_rejected(self):
        mutated = copy.deepcopy(self.policy)
        mutated["slices"][0]["slice_id"] = "stage3e1-s01"
        with self.assertRaisesRegex(TemporalSliceCompilationError, "forbidden_slice_reuse"):
            validate_slice_policy(mutated, self.manifest)

    def test_slice_hashes_are_stable_and_unique(self):
        semantic = [item["slice_semantic_fingerprint"] for item in self.policy["slices"]]
        aggregate = [item["slice_aggregate_sha256"] for item in self.policy["slices"]]
        self.assertEqual(len(set(semantic)), 4)
        self.assertEqual(len(set(aggregate)), 4)
        for item in self.policy["slices"]:
            semantic_payload = {key: value for key, value in item.items() if key not in {"source_file_bindings", "slice_semantic_fingerprint", "split_fingerprint", "slice_aggregate_sha256"}}
            self.assertEqual(fingerprint(semantic_payload), item["slice_semantic_fingerprint"])
            self.assertEqual(item["split_fingerprint"], item["slice_semantic_fingerprint"])
            self.assertEqual(fingerprint({"slice_semantic_fingerprint": item["slice_semantic_fingerprint"], "source_file_bindings": item["source_file_bindings"]}), item["slice_aggregate_sha256"])

    def test_old_campaign_is_superseded_without_execution(self):
        self.assertEqual(self.superseded["old_campaign_fingerprint"], OLD_CAMPAIGN_FINGERPRINT)
        self.assertEqual(self.superseded["execution_status"], "superseded_before_execution")
        self.assertEqual(self.superseded["reason"], "exact_temporal_boundaries_not_frozen")
        self.assertEqual(self.superseded["backtests_consumed"], 0)
        self.assertEqual(sha256_file(ROOT / self.superseded["old_campaign_path"]), self.superseded["old_campaign_artifact_sha256"])

    def test_new_campaign_embeds_complete_slice_boundaries(self):
        embedded = self.campaign["temporal_branch_contribution_review_plan"]["slice_policy"]
        self.assertEqual(embedded["slice_policy_fingerprint"], self.policy["slice_policy_fingerprint"])
        self.assertEqual(embedded["slices"], self.policy["slices"])
        self.assertEqual(embedded["source_dataset_aggregate_sha256"], DATASET_AGGREGATE_SHA256)

    def test_execution_matrix_is_exactly_sixteen_unexecuted_items(self):
        self.assertEqual(len(self.queue), 16)
        expected = [(f"ranging-short-ablation-s{number:02d}", role, run) for number in range(1, 5) for role in ("baseline", "candidate") for run in ("RUN-A", "RUN-B")]
        self.assertEqual([(item["slice_id"], item["role"], item["repetition"]) for item in self.queue], expected)
        self.assertTrue(all(item["status"] == "queued_unexecuted" and item["execution_authorized"] is False for item in self.queue))

    def test_dry_run_budget_cannot_execute_or_retry(self):
        self.assertFalse(self.campaign["execution_authorized"])
        self.assertEqual(self.campaign["budget"]["max_backtest_calls"], 16)
        self.assertEqual(self.campaign["budget"]["max_retries_per_experiment"], 0)
        self.assertEqual(self.campaign["budget"]["max_validation_accesses"], 0)
        self.assertEqual(self.campaign["budget"]["max_holdout_accesses"], 0)
        self.assertEqual(self.campaign["temporal_branch_contribution_review_plan"]["execution_boundary"]["backtests_consumed"], 0)

    def test_candidate_and_formal_strategy_are_unchanged(self):
        self.assertEqual(sha256_file(ROOT / CANDIDATE_PATH), CANDIDATE_SHA256)
        self.assertEqual(sha256_file(ROOT / STRATEGY_PATH), STRATEGY_SHA256)
        self.assertFalse(self.campaign["frozen_inputs"]["candidate"]["modification_allowed"])
        self.assertFalse(self.campaign["frozen_inputs"]["formal_strategy"]["modification_allowed"])

    def test_only_btc_development_is_referenced(self):
        payload = str(self.campaign["temporal_branch_contribution_review_plan"]).lower()
        self.assertEqual(self.policy["source_dataset"], DATASET_ID)
        self.assertNotIn("eth-usdt", payload)
        self.assertNotIn("validation-v2", payload)
        self.assertFalse(self.policy["validation_data_allowed"])

    def test_slice_policy_integrity_validator_accepts_committed_policy(self):
        validate_slice_policy(self.policy, self.manifest)


if __name__ == "__main__":
    unittest.main()
