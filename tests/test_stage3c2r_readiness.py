import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_stage3c2r_readiness as stage3c2r
from research_control import load_simple_yaml
from run_experiment import sha256_file


DEV_V1 = ROOT / "research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/manifest.yaml"
SPLIT_V2 = ROOT / "research/data/splits/futures-dev-validation-v2-policy.yaml"
PROPOSAL = ROOT / "research/evaluation/evaluation-policy-proposal.yaml"
READINESS = ROOT / "research/evaluation/stage3c3-readiness.json"
FINAL = ROOT / "research/results/stage3c2r-readiness/stage3c2r-final-report.json"
AUDIT = ROOT / "reports/audits/stage3c2r_evaluation_data_coverage_audit.md"
DECISION = ROOT / "reports/decisions/stage3c2_evaluation_policy_decision_packet.md"


class Stage3C2RReadinessTest(unittest.TestCase):
    def test_dev_v1_is_marked_insufficient_without_rewriting_data_files(self):
        manifest = load_simple_yaml(DEV_V1)
        readiness = manifest["evaluation_readiness"]

        self.assertEqual(readiness["status"], "insufficient")
        self.assertEqual(readiness["total_trades"], 0)
        self.assertIn("no_baseline_trades", readiness["reason_codes"])
        self.assertFalse(readiness["suitable_for_strategy_ranking"])
        for record in manifest["files"]:
            self.assertEqual(sha256_file(ROOT / record["path"]), record["sha256"])

    def test_zero_trade_dataset_is_evaluation_not_ready(self):
        manifest = load_simple_yaml(DEV_V1)
        reasons = set(manifest["evaluation_readiness"]["reason_codes"])

        self.assertIn("no_candidate_trades", reasons)
        self.assertIn("insufficient_for_relative_evaluation", reasons)
        self.assertFalse(manifest["evaluation_readiness"]["suitable_for_cost_stress"])

    def test_acceptance_fixture_cannot_be_upgraded_to_development(self):
        split = load_simple_yaml(SPLIT_V2)
        audit_text = AUDIT.read_text(encoding="utf-8")

        self.assertTrue(split["chronological_rules"]["acceptance_fixture_outside_evaluation"])
        self.assertNotIn("demo-btc-usdt-usdt-futures-acceptance", str(split.get("development_v2_dataset_id")))
        self.assertIn("Acceptance fixture can be Development: `false`", audit_text)

    def test_split_is_frozen_before_strategy_probe_and_uses_no_strategy_results(self):
        split = load_simple_yaml(SPLIT_V2)

        self.assertTrue(split["frozen_before_strategy_probe"])
        self.assertFalse(split["strategy_results_used"])
        self.assertFalse(split["strategy_probe_run"])
        self.assertEqual(split["selection_basis"], "data_coverage_only_no_strategy_results")
        self.assertIn("profit_factor", split["prohibited_selection_inputs"])

    def test_development_candle_requirement_blocks_v2_when_local_data_is_short(self):
        split = load_simple_yaml(SPLIT_V2)
        available = split["available_data_summary"]

        self.assertGreaterEqual(split["minimum_requirements"]["development_evaluation_1h_candles"], 5000)
        self.assertLess(available["main_1h_candles"], split["minimum_requirements"]["development_evaluation_1h_candles"])
        if split["status"] == "data_provisioning_blocked":
            self.assertIn("insufficient_continuous_1h_coverage", split["blocker_reasons"])
        else:
            self.assertEqual(split["status"], "approved_for_data_split")
            self.assertTrue(split["development_v2_sealed"])
            self.assertTrue(split["validation_v2_sealed"])

    def test_warmup_not_counted_and_embargo_declared(self):
        split = load_simple_yaml(SPLIT_V2)
        requirements = split["minimum_requirements"]

        self.assertFalse(requirements["warmup_counted_in_evaluation"])
        self.assertEqual(requirements["startup_candles_4h"], 200)
        self.assertGreater(requirements["embargo_hours"], 0)

    def test_development_validation_non_overlap_and_order_are_policy_rules(self):
        split = load_simple_yaml(SPLIT_V2)
        rules = split["chronological_rules"]

        self.assertTrue(rules["development_uses_earliest_continuous_history"])
        self.assertTrue(rules["embargo_after_development"])
        self.assertTrue(rules["validation_strictly_after_development"])
        self.assertFalse(rules["development_validation_overlap_allowed"])

    def test_informative_futures_mark_and_funding_requirements_are_explicit(self):
        split = load_simple_yaml(SPLIT_V2)

        self.assertIn("4h", split["informative_timeframes"])
        self.assertIn("futures", split["required_candle_types"])
        self.assertIn("mark", split["required_candle_types"])
        self.assertIn("funding_rate", split["required_candle_types"])

    def test_v2_snapshots_are_not_sealed_when_data_is_insufficient(self):
        split = load_simple_yaml(SPLIT_V2)
        final = json.loads(FINAL.read_text(encoding="utf-8"))

        if split["status"] == "data_provisioning_blocked":
            self.assertFalse(split["development_v2_sealed"])
            self.assertFalse(split["validation_v2_sealed"])
            self.assertIsNone(split["development_v2_dataset_id"])
            self.assertIsNone(split["validation_v2_dataset_id"])
            self.assertFalse(final["v2_snapshots_created"])
        else:
            self.assertTrue(split["development_v2_sealed"])
            self.assertTrue(split["validation_v2_sealed"])
            self.assertTrue((ROOT / "research/data/snapshots" / split["development_v2_dataset_id"] / "manifest.yaml").exists())
            self.assertTrue((ROOT / "research/data/snapshots" / split["validation_v2_dataset_id"] / "manifest.yaml").exists())

    def test_probe_is_not_run_and_quality_verdict_is_not_created(self):
        final = json.loads(FINAL.read_text(encoding="utf-8"))

        self.assertFalse(final["strategy_probe_run"])
        self.assertFalse(final["stage3c3_started"])
        self.assertFalse(final["validation_accessed"])
        self.assertEqual(final["status"], "blocked")

    def test_policy_proposal_is_pending_and_has_no_codex_approval(self):
        proposal = load_simple_yaml(PROPOSAL)

        self.assertEqual(proposal["policy_approval_status"], "pending_human_review")
        self.assertIsNone(proposal["approver"])
        self.assertFalse(proposal["codex_may_approve"])
        self.assertIn("approved", proposal["policy_statuses"])
        self.assertIn("rejected", proposal["policy_statuses"])

    def test_policy_readiness_blocks_or_records_stage3c3_completion(self):
        readiness = json.loads(READINESS.read_text(encoding="utf-8"))

        if readiness.get("schema_version") == "stage3c3-readiness-v3":
            self.assertTrue(readiness["ready"])
            self.assertTrue(readiness["readiness_checks"]["policy_human_approved"])
            self.assertFalse(readiness["readiness_checks"]["validation_accessed"])
            self.assertFalse(readiness["bulk_autonomous_search_ready"])
        else:
            self.assertFalse(readiness["ready"])
            self.assertIn("evaluation_policy_pending_human_review", readiness["blockers"])
            self.assertTrue(readiness["readiness_checks"]["candidate_validation_not_read"])
            self.assertTrue(readiness["readiness_checks"]["holdout_not_accessed"])

    def test_nonzero_trades_required_for_cost_stress_and_lookahead_readiness(self):
        readiness = json.loads(READINESS.read_text(encoding="utf-8"))

        checks = readiness["readiness_checks"]
        if readiness.get("schema_version") == "stage3c3-readiness-v3":
            self.assertTrue(checks["lookahead_runner_executable"])
            self.assertTrue(checks["recursive_runner_executable"])
            self.assertTrue(checks["cost_stress_runner_executable"])
        elif checks["development_has_nonzero_trades"]:
            self.assertTrue(checks["cost_stress_has_real_trades"])
            self.assertTrue(checks["lookahead_analysis_signal_coverage"])
            self.assertTrue(checks["recursive_analysis_time_coverage"])
        else:
            self.assertFalse(checks["cost_stress_has_real_trades"])
            self.assertFalse(checks["lookahead_analysis_signal_coverage"])
            self.assertFalse(checks["recursive_analysis_time_coverage"])

    def test_holdout_hyperopt_strategy_and_candidate_remain_blocked(self):
        final = json.loads(FINAL.read_text(encoding="utf-8"))

        self.assertFalse(final["holdout_accessed"])
        self.assertFalse(final["hyperopt_run"])
        self.assertFalse(final["strategy_modified"])
        self.assertFalse(final["candidate_modified"])

    def test_registry_contains_stage3c2r_tables_and_records(self):
        conn = sqlite3.connect(ROOT / "research/registry/research.db")
        try:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            for table in {
                "dataset_readiness",
                "split_v2_records",
                "evaluation_readiness_probes",
                "policy_proposals",
                "policy_approval_events",
                "stage3c3_readiness",
                "provisioning_blockers",
                "evaluation_artifact_refs",
            }:
                self.assertIn(table, tables)
            dataset = conn.execute("SELECT status FROM dataset_readiness WHERE dataset_id = ?", (stage3c2r.DEV_V1_ID,)).fetchone()
            proposal = conn.execute("SELECT approval_status FROM policy_proposals WHERE proposal_id = ?", ("stage3c2-futures-single-pair-policy-proposal-v1",)).fetchone()
        finally:
            conn.close()

        self.assertEqual(dataset[0], "insufficient")
        self.assertEqual(proposal[0], "pending_human_review")

    def test_required_artifacts_exist(self):
        for path in [AUDIT, SPLIT_V2, PROPOSAL, READINESS, FINAL, DECISION]:
            self.assertTrue(path.exists(), str(path))

    def test_validation_v1_audit_is_manifest_only(self):
        audit_text = AUDIT.read_text(encoding="utf-8")

        self.assertIn("Sealed Validation data audit mode: `manifest_only`", audit_text)
        self.assertIn("`manifest_only`", audit_text)


if __name__ == "__main__":
    unittest.main()
