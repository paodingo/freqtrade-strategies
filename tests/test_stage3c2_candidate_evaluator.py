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

import evaluate_research_candidate as evaluator
from research_data_guard import DataAccessError, check_data_access
from run_experiment import dump_json, dump_manifest, sha256_file


POLICY_PATH = ROOT / "research/evaluation/evaluation-policy.yaml"
CANDIDATE_MANIFEST = ROOT / "research/candidates/demo-stage3b2-single-variable/1/candidate-manifest.yaml"
EXPERIMENT_SPEC = ROOT / "research/experiments/demo-stage3b2-single-variable/1/experiment-spec.yaml"


class Stage3C2CandidateEvaluatorTest(unittest.TestCase):
    def test_evaluation_policy_schema_and_hash(self):
        policy = evaluator.load_policy(POLICY_PATH)
        phash = evaluator.policy_hash(POLICY_PATH)

        self.assertIn(policy["schema_version"], {"stage3c2-evaluation-policy-v1", "stage3c3-balanced-research-gate-v1"})
        self.assertIn(policy["policy_approval_status"], {"pending_human_review", "approved"})
        self.assertEqual(len(phash), 64)
        self.assertFalse(policy["champion_promotion_allowed"])
        self.assertFalse(policy["qualified_challenger_allowed"])
        self.assertFalse(policy["holdout_access_allowed"])

    def test_pending_policy_does_not_allow_validation(self):
        policy = evaluator.load_policy(POLICY_PATH)
        policy["policy_approval_status"] = "pending_human_review"
        candidate = evaluator.validate_candidate(ROOT, CANDIDATE_MANIFEST)
        with tempfile.TemporaryDirectory() as tmp:
            event = evaluator.maybe_authorize_validation(
                Path(tmp),
                policy,
                "a" * 64,
                candidate,
                {},
                "validation_evaluator",
                "development_eligible",
            )

        self.assertEqual(event["authorization_result"], "denied")
        self.assertEqual(event["reason_code"], "policy_pending_human_review")
        self.assertEqual(event["access_count_after"], 0)

    def test_single_score_cannot_override_hard_gate_or_pending_policy(self):
        policy = evaluator.load_policy(POLICY_PATH)
        policy["policy_approval_status"] = "pending_human_review"
        baseline = {"metrics": {}, "normalized_trade_hash": "a", "normalized_trade_count": 0, "normalized_trades": []}
        candidate = {
            "metrics": {
                "total_trades": {"normalized_value": 0},
                "long_trades": {"normalized_value": 0},
                "short_trades": {"normalized_value": 0},
            },
            "normalized_trade_hash": "b",
            "normalized_trade_count": 0,
            "normalized_trades": [],
        }
        comparison = {"trade_diff": {"same_trade_hash": False}, "auxiliary_score": {"favorable_metric_count": 99}}

        decision = evaluator.gate_decision(policy, baseline, candidate, comparison)

        self.assertEqual(decision["final_decision"], "development_evaluated_policy_pending")
        self.assertTrue(decision["hard_gates_override_score"])

    def test_baseline_candidate_dataset_hash_mismatch_is_rejected(self):
        policy = evaluator.load_policy(POLICY_PATH)
        policy["development_dataset_aggregate_sha256"] = "bad"

        with self.assertRaises(evaluator.EvaluationError) as err:
            evaluator.validate_dataset(ROOT, policy["development_dataset_id"], policy, "development_evaluator")

        self.assertEqual(err.exception.reason_code, "dataset_hash_mismatch")

    def test_data_access_roles_for_development_and_validation(self):
        dev = ROOT / "research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/manifest.yaml"
        val = ROOT / "research/data/snapshots/futures-validation-btc-usdt-usdt-20260503-20260628-v1/manifest.yaml"

        self.assertEqual(check_data_access(ROOT, dev, "development_evaluator")["layer"], "development")
        self.assertEqual(check_data_access(ROOT, val, "validation_evaluator")["layer"], "validation")
        with self.assertRaises(DataAccessError):
            check_data_access(ROOT, val, "development_evaluator")
        with self.assertRaises(DataAccessError):
            check_data_access(ROOT, val, "candidate_generator")

    def test_candidate_hashes_are_validated(self):
        manifest = evaluator.validate_candidate(ROOT, CANDIDATE_MANIFEST)

        self.assertEqual(manifest["candidate_strategy_sha256"].lower(), sha256_file(ROOT / manifest["candidate_strategy_path"]).lower())
        self.assertEqual(manifest["base_strategy_sha256"].lower(), sha256_file(ROOT / manifest["base_strategy_path"]).lower())

    def test_candidate_freeze_and_changed_source_detection(self):
        candidate = evaluator.validate_candidate(ROOT, CANDIDATE_MANIFEST)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = tmp_path / "development-result.json"
            dump_json(result, {"ok": True})
            freeze_path = tmp_path / "candidate-freeze.yaml"
            freeze = evaluator.create_candidate_freeze(
                ROOT,
                candidate,
                CANDIDATE_MANIFEST,
                EXPERIMENT_SPEC,
                result,
                "d" * 64,
                "p" * 64,
                freeze_path,
            )
            self.assertTrue(freeze["mutation_prohibited"])

            valid = evaluator.validate_candidate_freeze(ROOT, freeze_path, candidate, CANDIDATE_MANIFEST, EXPERIMENT_SPEC)
            self.assertTrue(valid["valid"])

            text = freeze_path.read_text(encoding="utf-8").replace(freeze["source_sha256"], "0" * 64)
            freeze_path.write_text(text, encoding="utf-8")
            invalid = evaluator.validate_candidate_freeze(ROOT, freeze_path, candidate, CANDIDATE_MANIFEST, EXPERIMENT_SPEC)
            self.assertFalse(invalid["valid"])
            self.assertIn("candidate_changed_after_freeze", invalid["mismatches"])

    def test_validation_budget_is_one_per_candidate(self):
        policy = evaluator.load_policy(POLICY_PATH)
        policy["policy_approval_status"] = "approved"
        candidate = evaluator.validate_candidate(ROOT, CANDIDATE_MANIFEST)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = evaluator.maybe_authorize_validation(root, policy, "p" * 64, candidate, {}, "validation_evaluator", "development_eligible")
            second = evaluator.maybe_authorize_validation(root, policy, "p" * 64, candidate, {}, "validation_evaluator", "development_eligible")

        self.assertEqual(first["authorization_result"], "authorized")
        self.assertEqual(first["access_count_after"], 1)
        self.assertEqual(second["authorization_result"], "denied")
        self.assertEqual(second["reason_code"], "validation_budget_exhausted")
        self.assertEqual(second["access_count_after"], 1)

    def test_infra_retry_denial_does_not_consume_validation_budget(self):
        candidate_id = "candidate:1"
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "r.db")
            try:
                evaluator.init_registry(conn)
                denied = evaluator.record_validation_access(conn, candidate_id, "s" * 64, "p" * 64, "validation_evaluator", "dataset", "d" * 64, False, "infra_transient_retry")
                authorized = evaluator.record_validation_access(conn, candidate_id, "s" * 64, "p" * 64, "validation_evaluator", "dataset", "d" * 64, True, None)
            finally:
                conn.close()

        self.assertEqual(denied["access_count_after"], 0)
        self.assertEqual(authorized["access_count_before"], 0)
        self.assertEqual(authorized["access_count_after"], 1)

    def test_missing_metric_is_not_defaulted_to_zero(self):
        metric = evaluator.metric_record("funding_fees", None, "stake_currency", "higher", "trade_export", "no funding fee field")

        self.assertIsNone(metric["raw_value"])
        self.assertIsNone(metric["normalized_value"])
        self.assertEqual(metric["missing_reason"], "no funding fee field")

    def test_metric_comparison_and_trade_diff(self):
        baseline = {
            "metrics": {"profit_factor": {"normalized_value": 1.0, "direction": "higher"}},
            "normalized_trade_hash": "same",
            "normalized_trade_count": 1,
            "normalized_trades": [{"id": 1}],
        }
        candidate = {
            "metrics": {"profit_factor": {"normalized_value": 1.2, "direction": "higher"}},
            "normalized_trade_hash": "same",
            "normalized_trade_count": 1,
            "normalized_trades": [{"id": 1}],
        }

        comparison = evaluator.compare_vectors(baseline, candidate)

        self.assertEqual(comparison["metric_deltas"]["profit_factor"]["delta"], 0.19999999999999996)
        self.assertTrue(comparison["trade_diff"]["same_trade_hash"])
        self.assertFalse(comparison["auxiliary_score"]["decides_gate"])

    def test_development_inconclusive_when_policy_approved_but_coverage_missing(self):
        policy = evaluator.load_policy(POLICY_PATH)
        policy["policy_approval_status"] = "approved"
        candidate = {
            "metrics": {
                "total_trades": {"normalized_value": 0},
                "long_trades": {"normalized_value": 0},
                "short_trades": {"normalized_value": 0},
            }
        }
        decision = evaluator.gate_decision(policy, {}, candidate, {"trade_diff": {"same_trade_hash": True}})

        self.assertEqual(decision["final_decision"], "development_inconclusive_insufficient_coverage")

    def test_validation_status_variants_are_declared(self):
        policy = evaluator.load_policy(POLICY_PATH)

        self.assertIn("validation_passed_provisional", policy["validation_states"])
        self.assertIn("validation_failed", policy["validation_states"])
        self.assertIn("validation_inconclusive", policy["validation_states"])

    def test_limited_disclosure_withholds_trade_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "limited.json"
            result = {
                "development_status": "development_evaluated_policy_pending",
                "gate_decision": {"final_decision": "development_evaluated_policy_pending", "reasons": ["pending"]},
                "candidate_metrics": {
                    "metrics": {
                        "total_trades": {"normalized_value": 3},
                        "long_trades": {"normalized_value": 2},
                        "short_trades": {"normalized_value": 1},
                        "total_profit_ratio": {"normalized_value": 0.01},
                        "max_drawdown_absolute": {"normalized_value": 1.0},
                        "profit_factor": {"normalized_value": 1.2},
                    }
                },
                "comparison": {"metric_deltas": {"total_profit": {"delta": 1}}},
            }
            evaluator.write_limited_disclosure(path, result)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertIn("complete_trade_list", payload["withheld"])
        self.assertNotIn("normalized_trades", payload)
        self.assertNotIn("field_level_trade_diff", payload)

    def test_bias_checks_limit_promotion_and_no_champion(self):
        policy = evaluator.load_policy(POLICY_PATH)
        candidate = {
            "metrics": {
                "total_trades": {"normalized_value": 1},
                "long_trades": {"normalized_value": 1},
                "short_trades": {"normalized_value": 1},
            }
        }
        policy["policy_approval_status"] = "approved"
        decision = evaluator.gate_decision(policy, {}, candidate, {"trade_diff": {"same_trade_hash": False}})

        self.assertEqual(policy["promotion_ceiling"], "validation_passed_provisional")
        self.assertEqual(decision["champion_promotion"], "not_allowed")
        self.assertEqual(decision["qualified_challenger"], "not_allowed")
        self.assertIn(decision["bias_validation"]["lookahead_analysis"], {"not_run", "not_required_until_behavior_changed"})
        self.assertFalse(decision["holdout_accessed"])

    def test_holdout_and_hyperopt_and_strategy_mutation_are_disabled(self):
        policy = evaluator.load_policy(POLICY_PATH)

        self.assertFalse(policy["holdout_access_allowed"])
        self.assertFalse(policy["hyperopt_allowed"])
        self.assertFalse(policy["strategy_mutation_allowed"])
        self.assertFalse(policy["new_candidate_generation_allowed"])

    def test_registry_tables_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "registry.db")
            try:
                evaluator.init_registry(conn)
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                conn.close()

        for table in {
            "evaluation_policies",
            "candidate_freezes",
            "development_evaluations",
            "validation_evaluations",
            "metric_values",
            "baseline_comparisons",
            "validation_access_events",
            "contamination_events",
            "evaluation_artifacts",
            "gate_decisions",
        }:
            self.assertIn(table, tables)

    def test_experiment_id_does_not_clear_contamination_budget(self):
        policy = evaluator.load_policy(POLICY_PATH)
        policy["policy_approval_status"] = "approved"
        candidate = evaluator.validate_candidate(ROOT, CANDIDATE_MANIFEST)
        candidate_same_source_new_experiment = dict(candidate)
        candidate_same_source_new_experiment["experiment_id"] = "changed-experiment-id"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = evaluator.maybe_authorize_validation(root, policy, "p" * 64, candidate, {}, "validation_evaluator", "development_eligible")
            second = evaluator.maybe_authorize_validation(root, policy, "p" * 64, candidate_same_source_new_experiment, {}, "validation_evaluator", "development_eligible")

        self.assertEqual(first["authorization_result"], "authorized")
        self.assertEqual(second["reason_code"], "validation_budget_exhausted")
        self.assertEqual(candidate["candidate_strategy_sha256"], candidate_same_source_new_experiment["candidate_strategy_sha256"])


if __name__ == "__main__":
    unittest.main()
