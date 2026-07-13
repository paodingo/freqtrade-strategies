import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_stage3c2p_provisioning as stage3c2p
from research_control import load_simple_yaml
from run_experiment import sha256_file
from portable_baseline_support import TemporaryRegistry, active as portable_active, fixture_json


POLICY = ROOT / "research/data/splits/futures-dev-validation-v2-policy.yaml"
SPLIT = ROOT / "research/data/splits/futures-dev-validation-v2.yaml"
COVERAGE_PLAN = ROOT / "research/data/provisioning/stage3c2p-coverage-plan.yaml"
INTEGRITY = ROOT / "research/data/provisioning/stage3c2p-data-integrity-report.json"
FINAL = ROOT / "research/data/provisioning/stage3c2p-final-report.json"
READINESS = ROOT / "research/evaluation/stage3c3-readiness.json"
PROBE = ROOT / "research/data/provisioning/stage3c2p-development-probe.json"
DEV_V1 = ROOT / "research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/manifest.yaml"
DEV_V2 = ROOT / "research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml"
VAL_V2 = ROOT / "research/data/snapshots/futures-validation-btc-usdt-usdt-20240912-20250128-v2/manifest.yaml"
EVAL_POLICY = ROOT / "research/evaluation/evaluation-policy.yaml"
RUNTIME_CONTRACT = ROOT / "reports/audits/stage3c2p_runtime_data_contract.md"


class Stage3C2PProvisioningTest(unittest.TestCase):
    def test_endpoint_policy_allows_only_public_market_data(self):
        self.assertTrue(stage3c2p.classify_public_endpoint("GET", "fapi.binance.com", "/fapi/v1/exchangeInfo")["allowed"])
        self.assertTrue(stage3c2p.classify_public_endpoint("GET", "data.binance.vision", "/data/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2024-01.zip")["allowed"])
        forbidden = stage3c2p.classify_public_endpoint("GET", "fapi.binance.com", "/fapi/v1/account")
        self.assertFalse(forbidden["allowed"])
        self.assertEqual(forbidden["classification"], "private_or_trade")
        self.assertFalse(stage3c2p.classify_public_endpoint("GET", "fapi.binance.com", "/fapi/v1/ticker/price")["allowed"])

    def test_proxy_log_is_redacted(self):
        redacted = stage3c2p.redact_proxy_url("http://alice:secret@127.0.0.1:10808")
        self.assertEqual(redacted["type"], "httpProxy")
        self.assertEqual(redacted["host"], "127.0.0.1")
        self.assertEqual(redacted["port"], 10808)
        self.assertNotIn("alice", json.dumps(redacted))
        self.assertNotIn("secret", json.dumps(redacted))

    def test_split_policy_records_human_5000_2500_decision(self):
        policy = load_simple_yaml(POLICY)
        self.assertEqual(policy["schema_version"], "stage3c2p-split-v2-policy-v2")
        self.assertEqual(policy["status"], "approved_for_data_split")
        self.assertEqual(policy["development"]["evaluation_1h_candles"], 5000)
        self.assertEqual(policy["validation"]["evaluation_1h_candles"], 2500)
        self.assertIsNone(policy["validation"]["evaluation_ratio"])
        self.assertEqual(policy["human_decision_event"]["approver_type"], "human_user")
        self.assertEqual(len(policy["split_policy_sha256"]), 64)

    def test_split_policy_approval_is_separate_from_evaluation_policy(self):
        policy = load_simple_yaml(POLICY)
        evaluation_policy = load_simple_yaml(EVAL_POLICY)
        self.assertEqual(policy["status"], "approved_for_data_split")
        self.assertEqual(policy["human_decision_event"]["evaluation_policy_approval"], "not_approved")
        self.assertIn(evaluation_policy["policy_approval_status"], {"pending_human_review", "approved"})

    def test_coverage_plan_contains_full_5000_2500_calculation(self):
        plan = load_simple_yaml(COVERAGE_PLAN)
        self.assertEqual(plan["status"], "ready_for_download")
        self.assertEqual(plan["reason_codes"], [])
        self.assertEqual(plan["development_evaluation_1h_candles"], 5000)
        self.assertEqual(plan["validation_evaluation_1h_candles"], 2500)
        self.assertEqual(plan["validation_evaluation_ratio"], None)
        self.assertEqual(plan["development_warmup_1h_candles"], 800)
        self.assertEqual(plan["embargo_1h_candles"], 336)
        self.assertEqual(plan["validation_warmup_1h_candles"], 800)
        self.assertEqual(plan["total_required_raw_1h_candles"], 9604)
        self.assertEqual(plan["estimated_row_counts"]["funding_rate_8h"], 1201)

    def test_freqtrade_2025_8_does_not_use_candle_types_flag(self):
        contract = RUNTIME_CONTRACT.read_text(encoding="utf-8")
        plan = load_simple_yaml(COVERAGE_PLAN)
        command = plan["planned_command"]
        self.assertIn("Expected Freqtrade: `2025.8`", contract)
        self.assertIn("`download-data` supports `--candle-types`: `false`", contract)
        self.assertNotIn("--candle-types", command)
        self.assertNotIn("2025.12", contract)

    def test_data_integrity_passes_for_futures_mark_funding_and_informative(self):
        integrity = json.loads(INTEGRITY.read_text(encoding="utf-8"))
        self.assertEqual(integrity["status"], "passed")
        self.assertFalse(integrity["synthetic_funding_used"])
        for key in ("futures_1h", "futures_4h", "mark_8h", "funding_rate_8h"):
            self.assertTrue(integrity["checks"][key]["ok"], key)
            self.assertEqual(integrity["checks"][key]["missing_interval_count"], 0)

    def test_staging_is_separate_and_v1_snapshot_hashes_hold(self):
        final = json.loads(FINAL.read_text(encoding="utf-8"))
        self.assertTrue(final["staging_written"])
        self.assertFalse(final["v1_snapshots_overwritten"])
        if portable_active():
            dev_v1 = fixture_json("stage3c2-v1-integrity.json")
            self.assertTrue(dev_v1["source_files_verified"])
            self.assertTrue(all(record["verified"] for record in dev_v1["files"]))
            return
        dev_v1 = load_simple_yaml(DEV_V1)
        for record in dev_v1["files"]:
            self.assertEqual(sha256_file(ROOT / record["path"]), record["sha256"])

    def test_concrete_split_has_exact_development_validation_and_embargo(self):
        split = load_simple_yaml(SPLIT)
        self.assertTrue(split["frozen_before_strategy_probe"])
        self.assertFalse(split["strategy_results_used"])
        self.assertFalse(split["probe_may_move_split"])
        self.assertEqual(split["development"]["evaluation_1h_candles"], 5000)
        self.assertEqual(split["validation"]["evaluation_1h_candles"], 2500)
        self.assertEqual(split["validation"]["evaluation_ratio"], None)
        self.assertLess(split["development"]["evaluation_end"], split["embargo"]["start"])
        self.assertLess(split["embargo"]["end"], split["validation"]["warmup_start"])
        self.assertLess(split["validation"]["warmup_start"], split["validation"]["evaluation_start"])

    def test_v2_snapshots_are_sealed_with_expected_candle_counts(self):
        dev = load_simple_yaml(DEV_V2)
        val = load_simple_yaml(VAL_V2)
        self.assertTrue(dev["sealed"])
        self.assertTrue(val["sealed"])
        self.assertEqual(dev["evaluation_range"]["main_1h_candles"], 5000)
        self.assertEqual(val["evaluation_range"]["main_1h_candles"], 2500)
        self.assertEqual(dev["validation_checks"]["futures_1h"]["rows"], 5800)
        self.assertEqual(val["validation_checks"]["futures_1h"]["rows"], 3300)
        self.assertFalse(dev["funding_model_synthetic"])
        self.assertFalse(val["funding_model_synthetic"])

    def test_probe_ran_on_development_only_and_did_not_move_split(self):
        probe = json.loads(PROBE.read_text(encoding="utf-8"))
        final = json.loads(FINAL.read_text(encoding="utf-8"))
        self.assertTrue(final["development_probe_run"])
        self.assertFalse(final["validation_accessed"])
        self.assertFalse(probe["split_modified_after_probe"])
        self.assertEqual(probe["baseline"]["total_trades"], 27)
        self.assertEqual(probe["candidate"]["total_trades"], 27)
        self.assertTrue(probe["cost_stress_has_real_trades"])
        self.assertTrue(probe["recursive_candle_coverage"])

    def test_stage3c2p_policy_blocker_is_preserved_but_stage3c3_may_later_complete(self):
        readiness = json.loads(READINESS.read_text(encoding="utf-8"))
        final = json.loads(FINAL.read_text(encoding="utf-8"))
        self.assertEqual(final["policy_approval_status"], "pending_human_review")
        if readiness.get("schema_version") == "stage3c3-readiness-v3":
            self.assertTrue(readiness["readiness_checks"]["policy_human_approved"])
            self.assertFalse(readiness["bulk_autonomous_search_ready"])
        else:
            self.assertFalse(readiness["ready"])
            self.assertIn("evaluation_policy_pending_human_review", readiness["blockers"])
        self.assertFalse(final["validation_accessed"])

    def test_forbidden_stages_are_not_run(self):
        final = json.loads(FINAL.read_text(encoding="utf-8"))
        self.assertFalse(final["holdout_accessed"])
        self.assertFalse(final["hyperopt_run"])
        self.assertFalse(final["lookahead_run"])
        self.assertFalse(final["recursive_run"])
        self.assertFalse(final["cost_stress_run"])
        self.assertFalse(final["strategy_modified"])
        self.assertFalse(final["candidate_modified"])

    def test_registry_records_split_decision_and_provisioning_event(self):
        portable = TemporaryRegistry() if portable_active() else None
        conn = sqlite3.connect(portable.path if portable else ROOT / "research/registry/research.db")
        try:
            event = conn.execute("SELECT status FROM stage3c2p_provisioning_events WHERE event_id = ?", ("stage3c2p-provisioning",)).fetchone()
            split_event = conn.execute("SELECT approver_type, evaluation_policy_approved FROM split_policy_decision_events WHERE event_id = ?", ("stage3c2p-human-split-policy-decision",)).fetchone()
        finally:
            conn.close()
            if portable:
                portable.cleanup()
        self.assertEqual(event[0], "completed_with_policy_blocker")
        self.assertEqual(split_event[0], "human_user")
        self.assertEqual(split_event[1], 0)


if __name__ == "__main__":
    unittest.main()
