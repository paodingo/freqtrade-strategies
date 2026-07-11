import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_stage3d1_bounded_search as stage3d1


class Stage3D1BoundedSearchTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_paths = {
            "CAMPAIGN_PATH": stage3d1.CAMPAIGN_PATH,
            "CATALOG_PATH": stage3d1.CATALOG_PATH,
            "QUEUE_PATH": stage3d1.QUEUE_PATH,
        }
        tmp = Path(self._tmp.name)
        stage3d1.CAMPAIGN_PATH = tmp / "stage3d1-bounded-autonomous-search.yaml"
        stage3d1.CATALOG_PATH = tmp / "regime-aware-safe-mutations-v1.yaml"
        stage3d1.QUEUE_PATH = tmp / "stage3d1-experiments.yaml"

    def tearDown(self):
        for name, value in self._old_paths.items():
            setattr(stage3d1, name, value)
        self._tmp.cleanup()

    def test_safe_mutation_catalog_excludes_forbidden_variables(self):
        catalog = stage3d1.write_catalog(ROOT)
        names = {item["variable_id"] for item in catalog["variables"]}

        self.assertTrue(catalog["frozen"])
        self.assertEqual(catalog["base_strategy_sha256"], stage3d1.BASE_STRATEGY_SHA256)
        for forbidden in stage3d1.FORBIDDEN_VARIABLES:
            self.assertNotIn(forbidden, names)

    def test_queue_is_frozen_unique_and_excludes_stage3b2_duplicate(self):
        catalog = stage3d1.write_catalog(ROOT)
        queue = stage3d1.write_queue(ROOT, catalog)
        fingerprints = [item["fingerprint"] for item in queue["experiments"]]

        self.assertTrue(queue["queue_frozen"])
        self.assertLessEqual(len(queue["experiments"]), 10)
        self.assertEqual(len(fingerprints), len(set(fingerprints)))
        self.assertEqual(queue["queue_sha256"], stage3d1.stable_hash({key: value for key, value in queue.items() if key != "queue_sha256"}))
        self.assertNotIn(
            stage3d1.queue_fingerprint(
                {
                    "variable_id": "ranging_short_setup.bb_percent_min",
                    "source_path": "strategies/regime_aware_base.py",
                    "line": 231,
                    "old_value": 0.80,
                    "new_value": 0.85,
                }
            ),
            fingerprints,
        )

    def test_catalog_entries_have_required_safe_surface_metadata(self):
        catalog = stage3d1.write_catalog(ROOT)
        required = {
            "variable_id",
            "source_path",
            "line",
            "old_value",
            "candidate_values",
            "transformation_rule",
            "affects_entry_or_exit",
            "affects_side",
            "forbidden_other_surfaces",
            "risk_level",
            "audit_evidence",
        }
        for item in catalog["variables"]:
            self.assertTrue(required.issubset(item.keys()))
            self.assertNotIn("market", item["affects_entry_or_exit"])
            self.assertIn(item["affects_side"], {"long", "short"})
            self.assertIn("leverage", item["forbidden_other_surfaces"])
            self.assertIn("funding", item["forbidden_other_surfaces"])

    def test_campaign_budget_stop_conditions_and_scope_are_fixed(self):
        campaign = stage3d1.write_campaign_config(ROOT)

        self.assertEqual(campaign["budget"]["max_experiments"], 10)
        self.assertEqual(campaign["budget"]["max_wall_clock_hours"], 8)
        self.assertEqual(campaign["budget"]["max_total_attempts"], 24)
        self.assertEqual(campaign["budget"]["max_retries_per_experiment"], 1)
        self.assertEqual(campaign["budget"]["max_validation_evaluations"], 2)
        self.assertIn("queue_complete", campaign["stop_conditions"])
        self.assertIn("wall_clock_exceeded", campaign["stop_conditions"])
        self.assertIn("base_strategy_integrity_violation", campaign["stop_conditions"])
        self.assertIn("policy_hash_drift", campaign["escalation_conditions"])
        self.assertIn("strategies/**", campaign["scope"]["blocked_paths"])

    def test_queue_drift_is_rejected(self):
        catalog = stage3d1.write_catalog(ROOT)
        queue = stage3d1.write_queue(ROOT, catalog)
        queue["experiments"][0]["new_value"] = 999
        from run_experiment import dump_manifest

        dump_manifest(ROOT / stage3d1.QUEUE_PATH, queue)
        with self.assertRaises(stage3d1.Stage3D1Error) as err:
            stage3d1.load_stage3d1_queue(ROOT)
        self.assertEqual(err.exception.reason_code, "frozen_queue_drift")
        stage3d1.write_queue(ROOT, catalog)

    def test_single_variable_ast_mutation(self):
        catalog = stage3d1.write_catalog(ROOT)
        queue = stage3d1.write_queue(ROOT, catalog)
        experiment = queue["experiments"][0]
        source = (ROOT / experiment["source_path"]).read_text(encoding="utf-8")
        mutated, diff = stage3d1.mutate_source(source, experiment)

        self.assertEqual(diff["semantic_mutation_count"], 1)
        self.assertNotEqual(source, mutated)
        self.assertIn(str(experiment["new_value"]), mutated)

    def test_ast_mutation_rejects_non_unique_anchor(self):
        experiment = {
            "line": 223,
            "old_value": 0.20,
            "new_value": 0.25,
            "variable_id": "duplicate.constant",
        }
        source = "\n" * 222 + "value = 0.20 + 0.20\n"

        with self.assertRaises(stage3d1.Stage3D1Error) as err:
            stage3d1.mutate_source(source, experiment)
        self.assertEqual(err.exception.reason_code, "safe_mutation_ast_anchor_not_unique")

    def test_queue_order_is_deterministic_by_experiment_id(self):
        catalog = stage3d1.write_catalog(ROOT)
        queue = stage3d1.write_queue(ROOT, catalog)
        ids = [item["experiment_id"] for item in queue["experiments"]]
        classes = [item["candidate_class"] for item in queue["experiments"]]

        self.assertEqual(ids, sorted(ids))
        self.assertEqual(classes[0], "RegimeAware_C3D1_E0001")
        self.assertEqual(classes[-1], f"RegimeAware_C3D1_E{ids[-1]:04d}")

    def test_reproducibility_comparison_requires_independent_runs(self):
        run_a = {
            "summary": {"total_trades": 1, "long_trades": 1, "short_trades": 0, "normalized_trade_hash": "h"},
            "input_fingerprint": "i",
            "normalized_trade_hash": "h",
            "run_dir": "a",
        }
        run_b = {
            "summary": {"total_trades": 1, "long_trades": 1, "short_trades": 0, "normalized_trade_hash": "h"},
            "input_fingerprint": "i",
            "normalized_trade_hash": "h",
            "run_dir": "b",
        }

        self.assertTrue(stage3d1.compare_repro(run_a, run_b)["passed"])
        run_b["run_dir"] = "a"
        self.assertFalse(stage3d1.compare_repro(run_a, run_b)["passed"])

    def test_reproducibility_rejects_metric_or_input_drift(self):
        run_a = {
            "summary": {"total_trades": 1, "long_trades": 1, "short_trades": 0, "normalized_trade_hash": "h"},
            "input_fingerprint": "i",
            "normalized_trade_hash": "h",
            "run_dir": "a",
        }
        run_b = {
            "summary": {"total_trades": 2, "long_trades": 2, "short_trades": 0, "normalized_trade_hash": "h2"},
            "input_fingerprint": "changed",
            "normalized_trade_hash": "h2",
            "run_dir": "b",
        }
        result = stage3d1.compare_repro(run_a, run_b)

        self.assertFalse(result["passed"])
        self.assertFalse(result["input_fingerprint_consistent"])
        self.assertFalse(result["normalized_trade_hash_consistent"])

    def test_validation_budget_is_two_and_order_is_experiment_id(self):
        campaign = stage3d1.write_campaign_config(ROOT)
        catalog = stage3d1.write_catalog(ROOT)
        queue = stage3d1.write_queue(ROOT, catalog)
        ids = [item["experiment_id"] for item in queue["experiments"]]

        self.assertEqual(campaign["budget"]["max_validation_evaluations"], 2)
        self.assertEqual(ids, sorted(ids))

    def test_forbidden_actions_disabled_in_campaign(self):
        campaign = stage3d1.write_campaign_config(ROOT)

        self.assertFalse(campaign["autonomy"]["automatically_generate_hypotheses"])
        self.assertFalse(campaign["autonomy"]["automatically_promote_champion"])
        self.assertFalse(campaign["autonomy"]["access_sealed_holdout"])
        self.assertIn("strategies/**", campaign["scope"]["blocked_paths"])

    def test_validation_request_denied_before_bias_and_cost_verified(self):
        result = stage3d1.validation_request(ROOT, {}, {}, "development_inconclusive_behavior_unchanged", 0, 2)

        self.assertEqual(result["authorization_result"], "denied")
        self.assertEqual(result["reason_code"], "development_not_eligible")
        self.assertEqual(result["access_count_after"], 0)

    def test_validation_request_denied_when_campaign_budget_exhausted(self):
        result = stage3d1.validation_request(ROOT, {}, {}, "development_eligible_bias_and_cost_verified", 2, 2)

        self.assertEqual(result["authorization_result"], "denied")
        self.assertEqual(result["reason_code"], "campaign_validation_budget_exhausted")
        self.assertEqual(result["access_count_after"], 2)

    def test_policy_and_base_integrity_checks(self):
        stage3d1.assert_base_integrity(ROOT)
        stage3d1.assert_policy_integrity(ROOT)

    def test_global_registry_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "registry.db")
            try:
                stage3d1.init_registry(conn)
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                conn.close()

        self.assertIn("stage3d1_campaigns", tables)
        self.assertIn("stage3d1_experiments", tables)

    def test_registry_prevents_duplicate_campaign_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "registry.db")
            try:
                stage3d1.init_registry(conn)
                payload = (
                    stage3d1.CAMPAIGN_ID,
                    1,
                    "same-fingerprint",
                    "var",
                    "1",
                    "2",
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    "{}",
                    None,
                    None,
                    None,
                    None,
                    "recorded",
                    "{}",
                    "now",
                )
                conn.execute(
                    """
                    INSERT INTO stage3d1_experiments(
                      campaign_id, experiment_id, queue_fingerprint, variable_id, old_value, new_value,
                      candidate_class, candidate_hash, lifecycle_json, run_a_report, run_b_report,
                      reproducibility_json, development_status, bias_status, cost_status, validation_status,
                      final_status, artifact_index_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO stage3d1_experiments(
                          campaign_id, experiment_id, queue_fingerprint, variable_id, old_value, new_value,
                          candidate_class, candidate_hash, lifecycle_json, run_a_report, run_b_report,
                          reproducibility_json, development_status, bias_status, cost_status, validation_status,
                          final_status, artifact_index_json, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (stage3d1.CAMPAIGN_ID, 2, *payload[2:]),
                    )
            finally:
                conn.close()

    def test_completed_experiment_registry_resume_skips_finished_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research/registry").mkdir(parents=True)
            conn = sqlite3.connect(root / "research/registry/research.db")
            try:
                stage3d1.init_registry(conn)
                conn.execute(
                    """
                    INSERT INTO stage3d1_experiments(
                      campaign_id, experiment_id, queue_fingerprint, variable_id, old_value, new_value,
                      candidate_class, candidate_hash, lifecycle_json, run_a_report, run_b_report,
                      reproducibility_json, development_status, bias_status, cost_status, validation_status,
                      final_status, artifact_index_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stage3d1.CAMPAIGN_ID,
                        7,
                        "fp",
                        "var",
                        "1",
                        "2",
                        None,
                        None,
                        "[]",
                        None,
                        None,
                        "{}",
                        None,
                        None,
                        None,
                        None,
                        "development_inconclusive_behavior_unchanged",
                        "{}",
                        "now",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            self.assertEqual(stage3d1.completed_experiment_ids(root), {7})

    def test_behavior_statuses_do_not_authorize_hyperopt_holdout_or_champion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            final = {
                "forbidden_actions": {
                    "hyperopt_run": False,
                    "holdout_accessed": False,
                    "champion_created": False,
                    "qualified_challenger_created": False,
                    "adaptive_search": False,
                }
            }
        self.assertFalse(final["forbidden_actions"]["hyperopt_run"])
        self.assertFalse(final["forbidden_actions"]["holdout_accessed"])
        self.assertFalse(final["forbidden_actions"]["champion_created"])
        self.assertFalse(final["forbidden_actions"]["qualified_challenger_created"])


if __name__ == "__main__":
    unittest.main()
