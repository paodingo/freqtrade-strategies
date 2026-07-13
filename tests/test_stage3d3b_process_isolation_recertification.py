from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_candidate_runtime_identity as audit
import run_stage3d2b_reachability_search as stage3d2b
import run_stage3d3b_recertification as s
from run_experiment import sha256_file
from portable_baseline_support import active as portable_active, fixture_json


class Stage3D3BTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.final = fixture_json("stage3d3b-semantic-summary.json") if portable_active() else json.loads((ROOT / s.FINAL_JSON).read_text(encoding="utf-8"))
        cls.queue = s.load_simple_yaml(ROOT / s.QUEUE_PATH)
        cls.original = s.load_simple_yaml(ROOT / stage3d2b.QUEUE_PATH)
        cls.invalidation = json.loads((ROOT / s.INVALIDATION_PATH).read_text(encoding="utf-8"))

    def identities(self):
        if portable_active():
            yield from self.final["identities"]
            return
        for item in self.final["experiments"]:
            for run in (item["run_a"], item["run_b"]):
                yield json.loads((ROOT / run["runtime_identity"]).read_text(encoding="utf-8"))

    def test_01_each_candidate_independent_pid(self):
        self.assertTrue(self.final["all_worker_pids_unique"])
        self.assertEqual(len(self.final["worker_pids"]), len(set(self.final["worker_pids"])))

    def test_02_run_a_b_pid_different(self):
        self.assertTrue(all(x["run_a"]["process_id"] != x["run_b"]["process_id"] for x in self.final["experiments"]))

    def test_03_experiment_pids_different(self):
        pids = [x["run_a"]["process_id"] for x in self.final["experiments"]]
        self.assertEqual(len(pids), len(set(pids)))

    def test_04_sys_modules_not_reused(self):
        self.assertTrue(all(not identity["foreign_candidate_modules"] for identity in self.identities()))

    def test_05_runtime_module_file(self):
        if portable_active():
            self.assertTrue(all(identity["dependency_source_verified"] for identity in self.identities()))
        else:
            self.assertTrue(all(Path(identity["dependency_module_file"]).exists() for identity in self.identities()))

    def test_06_runtime_dependency_hash(self):
        if portable_active():
            self.assertTrue(all(identity["dependency_source_verified"] and len(identity["dependency_source_sha256"]) == 64 for identity in self.identities()))
        else:
            self.assertTrue(all(sha256_file(Path(identity["dependency_module_file"])) == identity["dependency_source_sha256"] for identity in self.identities()))

    def test_07_runtime_ast_value(self):
        expected = {x["experiment_id"]: x["new_value"] for x in self.final["experiments"]}
        self.assertTrue(all(identity["mutation_proof"]["loaded_ast_value"] == expected[identity["experiment_id"]] for identity in self.identities()))

    def test_08_candidate_one_cannot_shadow_two(self):
        key = "dependency_identity" if portable_active() else "dependency_module_file"
        one = self.final["experiments"][0]["run_a"][key]
        two = self.final["experiments"][1]["run_a"][key]
        self.assertNotEqual(one, two)

    def test_09_forward_reverse_consistent(self):
        self.assertTrue(all(row["consistent"] for row in self.final["reverse_order_samples"]))

    def test_10_process_order_independence(self):
        self.assertTrue(self.final["order_independence_passed"])

    def test_11_stale_module_is_detected(self):
        with self.assertRaisesRegex(audit.RuntimeIdentityError, "hash mismatch"):
            audit.validate_loaded_hashes("candidate-a", "candidate-b", "dependency-a", "dependency-a")

    def test_12_runtime_identity_mismatch_blocks(self):
        with self.assertRaises(audit.RuntimeIdentityError) as caught:
            audit.validate_loaded_hashes("a", "bad", "b", "b")
        self.assertEqual(caught.exception.reason_code, "runtime_candidate_identity_mismatch")

    def test_13_mutation_value_mismatch_blocks(self):
        with self.assertRaises(audit.RuntimeIdentityError) as caught:
            audit.validate_mutation_proof({"loaded_ast_value": 1, "mutation_count": 1}, 2)
        self.assertEqual(caught.exception.reason_code, "runtime_mutation_value_mismatch")

    def test_14_worker_runs_one_backtest(self):
        for identity in self.identities(): self.assertTrue(identity["backtest_started"])
        for item in self.final["experiments"]:
            for run in (item["run_a"], item["run_b"]):
                worker = run["worker"] if portable_active() else json.loads((ROOT / run["run_dir"] / "isolated-worker-result.json").read_text(encoding="utf-8"))
                self.assertEqual(worker["backtest_count"], 1)

    def test_15_worker_cannot_claim_next(self):
        item = self.final["experiments"][0]["run_a"]
        worker = item["worker"] if portable_active() else json.loads((ROOT / item["run_dir"] / "isolated-worker-result.json").read_text(encoding="utf-8"))
        self.assertFalse(worker["claimed_next_experiment"]); self.assertFalse(worker["registry_modified"])

    def test_16_run_a_b_reproducible(self):
        self.assertTrue(all(item["reproducibility"]["passed"] for item in self.final["experiments"]))

    def test_17_original_experiments_invalidated(self):
        invalid = [row["original_experiment_id"] for row in self.invalidation["records"] if row["research_validity"] == "invalidated"]
        self.assertEqual(invalid, list(range(2, 11)))

    def test_18_recertification_linkage(self):
        self.assertTrue(all(row["recertification_campaign_id"] == s.CAMPAIGN_ID for row in self.invalidation["records"]))

    def test_19_original_report_amendment(self):
        text = (ROOT / s.AMENDMENT_PATH).read_text(encoding="utf-8")
        self.assertIn("does not rewrite historical files", text)

    def test_20_experiment_one_existing_position(self):
        self.assertEqual(self.final["experiments"][0]["attribution"]["primary_blockers"], {"existing_same_direction_position": 1})

    def test_21_experiments_two_to_ten_valid(self):
        self.assertTrue(all(item["final_validity"] == "valid_recertified" for item in self.final["experiments"][1:]))

    def test_22_no_new_search_values(self):
        self.assertTrue(all("new_value" not in ref and "variable_id" not in ref for ref in self.queue["references"]))
        self.assertFalse(self.queue["research_hypotheses_redefined"])

    def test_23_original_frozen_queue_unchanged(self):
        self.assertEqual(self.original["queue_sha256"], s.ORIGINAL_QUEUE_SHA256)
        self.assertEqual(self.original["queue_sha256"], stage3d2b.self_hash(self.original, "queue_sha256"))

    def test_24_no_validation_holdout(self):
        self.assertFalse(self.final["validation_access_allowed"]); self.assertEqual(self.final["validation_access_count"], 0)
        self.assertFalse(self.final["forbidden_actions"]["holdout_accessed"])

    def test_25_no_hyperopt(self): self.assertFalse(self.final["forbidden_actions"]["hyperopt_run"])

    def test_26_official_strategy_unchanged(self):
        self.assertEqual(sha256_file(ROOT / "strategies/RegimeAwareV6.py").upper(), s.BASE_STRATEGY_SHA256)

    def test_27_config_unchanged(self):
        if portable_active():
            from research_director_common import fingerprint
            config = json.loads((ROOT / "research/runtime/demo-futures-backtest-config.json").read_text(encoding="utf-8"))
            self.assertEqual(fingerprint(config), "bc43aa4bbb4624aeaafcf26ff2747ba6d68c6d77fce8c81983da3ad73bd88d3a")
        else:
            self.assertEqual(sha256_file(ROOT / "research/runtime/demo-futures-backtest-config.json"), "52e468c9d2896591cef3cb08358ad1cf9523881135c7e49873d9c862712a6a7f")

    def test_28_baseline_guard_and_completion(self):
        self.assertEqual(self.final["status"], "completed")
        self.assertTrue((ROOT / "docs/quality/test-baseline.yaml").exists())


if __name__ == "__main__": unittest.main()
