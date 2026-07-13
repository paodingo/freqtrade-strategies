from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_stage3d2b_reachability_search as s
from portable_baseline_support import active as portable_active, fixture_path


class Stage3D2BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.space = s.build_search_space(ROOT)
        cls.queue = s.build_queue(cls.space)
        cls.campaign = s.build_campaign(cls.space, cls.queue)

    def test_01_approval(self):
        self.assertEqual((self.space["approval_status"], self.space["approver_type"], self.space["approval_scope"]), ("approved", "human_user", "stage3d2b_batch1_only"))

    def test_02_unapproved_value_rejected(self):
        altered = json.loads(json.dumps(self.space)); altered["approved_variables"][0]["approved_values"].append(45.42615404)
        with self.assertRaises(s.Stage3D2BError): s.validate_approval(altered, self.queue)

    def test_03_multi_variable_rejected(self):
        altered = json.loads(json.dumps(self.queue)); altered["experiments"][0]["variable_id"] = s.FORBIDDEN_VARIABLES[0]
        with self.assertRaises(s.Stage3D2BError): s.validate_approval(self.space, altered)

    def test_04_queue_order_and_hash(self):
        self.assertEqual([x["experiment_id"] for x in self.queue["experiments"]], list(range(1, 11)))
        self.assertEqual(self.queue["queue_sha256"], s.self_hash(self.queue, "queue_sha256"))

    def test_05_frozen_queue_drift(self):
        altered = json.loads(json.dumps(self.queue)); altered["experiments"][0]["new_value"] = 99
        with self.assertRaises(s.Stage3D2BError): s.assert_frozen_inputs(ROOT, self.space, altered)

    def test_06_reachability_preflight(self):
        path = fixture_path("stage3d2b-e0001-reachability.json") if portable_active() else ROOT / s.RESULT_ROOT / "1/reachability-preflight.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(result["actual_final_signal_mask_changes"], 0)

    def test_07_prediction_miss_route(self):
        self.assertEqual(s.gate_route("reachability_prediction_miss", None)["development"], "not_run_behavior_unchanged")

    def test_08_signal_no_trade(self):
        self.assertEqual(s.classify_trade_behavior({"normalized_trade_hash": s.BASELINE_RUNNER_TRADE_HASH})["classification"], "signal_changed_no_trade_behavior_change")

    def test_09_trade_changed(self):
        self.assertEqual(s.classify_trade_behavior({"normalized_trade_hash": "different"})["classification"], "trade_behavior_changed")

    def test_10_single_ast_mutation(self):
        source = (ROOT / "strategies/regime_aware_base.py").read_text(encoding="utf-8")
        changed, diff = s.mutate_source_exact(source, self.queue["experiments"][0])
        self.assertEqual(diff["semantic_mutation_count"], 1); self.assertNotEqual(ast.dump(ast.parse(source)), ast.dump(ast.parse(changed)))

    def test_11_unauthorized_ast_diff(self):
        item = dict(self.queue["experiments"][0]); item["line"] = 1
        with self.assertRaises(s.Stage3D2BError): s.mutate_source_exact((ROOT / "strategies/regime_aware_base.py").read_text(encoding="utf-8"), item)

    def test_12_run_independence(self):
        r = s.stage3d1.compare_repro({"summary": {}, "input_fingerprint": "x", "normalized_trade_hash": "y", "run_dir": "A"}, {"summary": {}, "input_fingerprint": "x", "normalized_trade_hash": "y", "run_dir": "B"})
        self.assertTrue(r["run_a_run_b_independent"])

    def test_13_repro_mismatch(self):
        r = s.stage3d1.compare_repro({"summary": {}, "input_fingerprint": "x", "normalized_trade_hash": "a", "run_dir": "A"}, {"summary": {}, "input_fingerprint": "x", "normalized_trade_hash": "b", "run_dir": "B"})
        self.assertFalse(r["passed"])

    def test_14_development_gate(self):
        self.assertEqual(s.gate_route("trade_behavior_changed", "development_ineligible_no_material_improvement")["bias"], "not_run_development_not_eligible")

    def test_15_bias_gate(self):
        self.assertEqual(s.gate_route("trade_behavior_changed", "development_eligible_bias_pending")["bias"], "required")

    def test_16_cost_gate(self):
        self.assertEqual(s.gate_route("trade_behavior_changed", "development_eligible_bias_pending")["cost"], "pending_bias")

    def test_17_validation_budget(self):
        self.assertEqual(self.campaign["budget"]["max_validation_evaluations"], 2)

    def test_18_experiment_sequence(self):
        self.assertEqual([(x["variable_id"], str(x["new_value"])) for x in self.queue["experiments"]], [(a, str(b)) for a, b in s.APPROVED_ORDER])

    def test_19_validation_limited_disclosure(self):
        self.assertFalse(self.campaign["validation"]["result_feedback_to_queue"])

    def test_20_no_followups(self):
        self.assertFalse(self.queue["adaptive_followups_allowed"]); self.assertFalse(self.campaign["autonomy"]["automatically_generate_followup_tasks"])

    def test_21_no_hyperopt(self): self.assertIn("hyperopt", self.campaign["forbidden_actions"])
    def test_22_no_holdout(self): self.assertFalse(self.campaign["autonomy"]["access_sealed_holdout"])
    def test_23_no_champion(self): self.assertFalse(self.campaign["autonomy"]["automatically_promote_champion"])
    def test_24_no_qualified_challenger(self): self.assertIn("qualified_challenger", self.campaign["forbidden_actions"])

    def test_25_global_integrity_stop(self):
        altered = json.loads(json.dumps(self.space)); altered["policy_sha256"] = "bad"
        with self.assertRaises(s.Stage3D2BError): s.assert_frozen_inputs(ROOT, altered, self.queue)

    def test_26_candidate_failure_continues(self):
        self.assertNotIn("candidate_rejected", self.campaign["stop_conditions"])

    def _temp_registry(self, status="queued"):
        tmp = tempfile.TemporaryDirectory(); root = Path(tmp.name); (root / "research/registry").mkdir(parents=True)
        conn = sqlite3.connect(root / "research/registry/research.db"); s.init_registry(conn)
        conn.execute("INSERT INTO stage3d2b_experiments(campaign_id,experiment_id,fingerprint,variable_id,new_value,status,updated_at,pollution_json,artifact_index_json,lifecycle_json) VALUES(?,?,?,?,?,?,?,'[]','{}','[]')", (s.CAMPAIGN_ID, 1, "fp", "v", "1", status, s.utc_now())); conn.commit(); conn.close()
        return tmp, root

    def test_27_crash_lease_recovery(self):
        tmp, root = self._temp_registry()
        try:
            self.assertTrue(s.claim_experiment(root, 1, "a", 1)); self.assertFalse(s.claim_experiment(root, 1, "b", 1))
            conn = sqlite3.connect(root / "research/registry/research.db"); conn.execute("UPDATE stage3d2b_experiments SET lease_expires_at=?", (time.time() - 1,)); conn.commit(); conn.close()
            self.assertTrue(s.claim_experiment(root, 1, "b", 1))
        finally: tmp.cleanup()

    def test_28_no_repeat_completed(self):
        tmp, root = self._temp_registry("recorded")
        try: self.assertFalse(s.claim_experiment(root, 1, "a", 1))
        finally: tmp.cleanup()

    def test_29_calibration_fields(self):
        path = fixture_path("stage3d2b-e0003-reachability.json") if portable_active() else ROOT / s.RESULT_ROOT / "3/reachability-preflight.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue({"predicted_condition_mask_changes", "actual_condition_mask_changes", "predicted_final_signal_mask_changes", "actual_final_signal_mask_changes", "prediction_classification_accurate"}.issubset(result))

    def test_30_baseline_and_yaml(self):
        self.assertTrue((ROOT / "docs/quality/test-baseline.yaml").exists())
        for path in (s.SEARCH_SPACE_PATH, s.QUEUE_PATH, s.CAMPAIGN_PATH): self.assertIsInstance(s.load_simple_yaml(ROOT / path), dict)


if __name__ == "__main__": unittest.main()
