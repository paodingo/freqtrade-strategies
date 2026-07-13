from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import windows_execution_paths as paths  # noqa: E402
import run_ranging_short_temporal_campaign as temporal  # noqa: E402
import run_router_extraction_semantic_equivalence_campaign as harness  # noqa: E402


CAMPAIGN_ID = "stage4a-ranging-short-branch-decision-review-v1-temporal-v2"
CAMPAIGN_FINGERPRINT = "ce25aae5d98b52f57e5fa793e2d1259022a803ad08c394bf793d67e52ab3b2f1"
PROPOSAL_ID = "ranging-short-branch-decision-review-v1"
PROPOSAL_FINGERPRINT = "e5b01ecdfc922b06a20e8e0c1eb901fd363563da23d246819cfa8e268247c0c3"
ATTEMPT_ID = "temporal-ablation-execution-attempt-3"
ATTEMPT_TWO_STOP_SHA256 = "1866aa84aa63a91b64d0ed59876287e44078945ac8470cebfd3d2ee87445dbeb"


def frozen_identity(slice_number: int = 1, role: str = "baseline", repetition: str = "RUN-A") -> dict[str, str]:
    return {
        "proposal_id": PROPOSAL_ID,
        "proposal_fingerprint": PROPOSAL_FINGERPRINT,
        "campaign_id": CAMPAIGN_ID,
        "campaign_fingerprint": CAMPAIGN_FINGERPRINT,
        "attempt_id": ATTEMPT_ID,
        "slice_id": f"ranging-short-ablation-s0{slice_number}",
        "slice_fingerprint": f"{'0' * 63}{slice_number}",
        "role": role,
        "repetition": repetition,
        "candidate_class": "RegimeAware_Ablation_RangingShort_C1",
        "candidate_path": "research/candidates/branch-contribution-ablation-v1/1/RegimeAware_Ablation_RangingShort_C1.py",
        "candidate_sha256": "e20dd42d2ba8a11ac2b832ad610c8f25cce28e6c92b74959ba0cce286c753eb0",
        "formal_strategy_sha256": "1a422f41ab801746c2ee39f5d20722b26b674098bca6ac1684e78bd8e7285509",
        "dataset_id": "futures-dev-btc-usdt-usdt-20240101-20240830-v2",
        "dataset_sha256": "1" * 64,
        "runtime_asset_manifest_fingerprint": "fa9bb13132dad44344e91d262c5fd38473e2cbed7a930e72f677eb7a0ce11f64",
        "evaluation_policy_sha256": "2" * 64,
        "exchange_snapshot_sha256": "3" * 64,
        "router_sha256": "bee68e27b345a93a1fe8481275e365829c986f700d2719fdd10ffd907e1dffa1",
    }


class WindowsExecutionPathBudgetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = paths.load_contract(ROOT)

    def test_contract_is_versioned_fingerprinted_and_does_not_require_long_paths(self):
        self.assertEqual(self.contract["contract_id"], "windows-short-execution-path-v1")
        self.assertFalse(self.contract["long_paths_required"])
        self.assertTrue(self.contract["preflight_required"])
        self.assertEqual(self.contract["max_absolute_path_chars"], 220)
        self.assertEqual(self.contract["contract_fingerprint"], paths.contract_fingerprint(self.contract))

    def test_all_four_slices_roles_and_repetitions_fit_current_worktree(self):
        plans = []
        for slice_number in range(1, 5):
            for role in ("baseline", "candidate"):
                for repetition in ("RUN-A", "RUN-B"):
                    plan = paths.plan_execution(ROOT, self.contract, frozen_identity(slice_number, role, repetition))
                    self.assertLessEqual(plan["path_budget"]["worst_absolute_path_chars"], 220)
                    plans.append(plan)
        self.assertEqual(len(plans), 16)
        self.assertEqual(len({item["namespace"] for item in plans}), 16)
        self.assertEqual(len({item["execution_short_id"] for item in plans}), 16)

    def test_namespace_uses_only_short_aliases_and_excludes_attempt_two(self):
        plan = paths.plan_execution(ROOT, self.contract, frozen_identity())
        self.assertRegex(plan["namespace"], r"^\.runs/rtv2/a3/s01/b/a/[0-9a-f]{10}$")
        forbidden = (
            PROPOSAL_ID,
            CAMPAIGN_ID,
            "RegimeAware_Ablation_RangingShort_C1",
            CAMPAIGN_FINGERPRINT,
            "temporal-ablation-execution-attempt-2",
        )
        self.assertTrue(all(value not in plan["namespace"] for value in forbidden))

    def test_longest_metadata_filename_is_in_preflight_inventory(self):
        plan = paths.plan_execution(ROOT, self.contract, frozen_identity())
        budget = plan["path_budget"]
        self.assertIn("metadata", budget["anticipated_outputs"])
        self.assertEqual(budget["worst_output_key"], "metadata")
        self.assertTrue(budget["anticipated_outputs"]["metadata"].endswith(".meta.json"))

    def test_path_budget_fails_before_namespace_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / ("x" * 225)
            with self.assertRaises(paths.ExecutionPathContractError) as raised:
                paths.create_execution_namespace(repo, self.contract, frozen_identity())
            self.assertEqual(raised.exception.reason_code, "execution_path_budget_exceeded")
            self.assertFalse(repo.exists())

    def test_short_id_collision_and_existing_directory_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            plan = paths.create_execution_namespace(repo, self.contract, frozen_identity())
            self.assertTrue((repo / plan["namespace"]).is_dir())
            with self.assertRaises(paths.ExecutionPathContractError) as raised:
                paths.create_execution_namespace(repo, self.contract, frozen_identity())
            self.assertEqual(raised.exception.reason_code, "short_execution_namespace_collision")

            registry_path = repo / plan["alias_registry"]
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["executions"][plan["execution_short_id"]]["execution_id"] = "different-full-id"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            target = repo / plan["namespace"]
            target.rmdir()
            with self.assertRaises(paths.ExecutionPathContractError) as collision:
                paths.create_execution_namespace(repo, self.contract, frozen_identity())
            self.assertEqual(collision.exception.reason_code, "short_execution_namespace_collision")

    def test_manifest_recovers_full_identity_and_binds_outputs_one_to_one(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            identity = frozen_identity()
            plan = paths.create_execution_namespace(repo, self.contract, identity)
            root = repo / plan["namespace"]
            for name in ("raw_result", "normalized_trades", "runner_report"):
                target = root / plan["path_budget"]["relative_outputs"][name]
                target.write_text(json.dumps({"artifact": name}), encoding="utf-8")
            manifest = paths.build_execution_manifest(repo, plan, identity)
            (root / "execution-manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            audit = paths.validate_binding_chain(repo, root / "execution-manifest.json")
            self.assertTrue(audit["passed"])
            self.assertEqual(manifest["full_identity"]["proposal_id"], PROPOSAL_ID)
            self.assertEqual(manifest["short_namespace_mapping"]["attempt_alias"], "a3")
            self.assertEqual(set(audit["verified"]), {"raw_result", "normalized_trades", "runner_report"})

    def test_attempt_two_stop_record_remains_immutable_and_non_evidentiary(self):
        stop = ROOT / "research/analysis/ranging-short-temporal-review-v1/campaign-stopped-attempt-2.json"
        self.assertEqual(paths.sha256_file(stop), ATTEMPT_TWO_STOP_SHA256)
        payload = json.loads(stop.read_text(encoding="utf-8"))
        self.assertEqual(payload["reason_code"], "windows_path_length_limit")
        self.assertEqual((payload["attempted_backtest_calls"], payload["completed_backtest_calls"]), (1, 0))
        self.assertEqual(payload["backtest_engine_unsealed_trade_count"], 21)
        self.assertEqual(payload["research_verdict"], "not_evaluated")
        self.assertFalse(payload["path_length_evidence"]["normalized_trades_present"])
        execution_root = (
            ROOT
            / "research/results/ranging-short-temporal-review-v1/ranging-short-ablation-s01"
            / "temporal-ablation-execution-attempt-2/btc-usdt-usdt/baseline/run-a/cd110c0ff7cb"
        )
        sealed = json.loads((execution_root / "artifact-hashes.json").read_text(encoding="utf-8"))
        actual = {path.name for path in execution_root.iterdir() if path.is_file() and path.name != "artifact-hashes.json"}
        self.assertEqual(actual, set(sealed))
        for name, expected in sealed.items():
            artifact = execution_root / name
            self.assertEqual(artifact.stat().st_size, expected["bytes"])
            self.assertEqual(paths.sha256_file(artifact), expected["sha256"])

    def test_attempt_three_request_is_pending_and_frozen_campaign_is_unchanged(self):
        request = json.loads((ROOT / paths.ATTEMPT_REQUEST_PATH).read_text(encoding="utf-8"))
        self.assertEqual(request["execution_attempt_id"], ATTEMPT_ID)
        self.assertEqual(request["approval_status"], "pending_human_review")
        self.assertFalse(request["execution_authorized"])
        self.assertEqual(request["campaign_fingerprint"], CAMPAIGN_FINGERPRINT)
        self.assertEqual(request["validation_accesses"], request["holdout_accesses"])
        self.assertEqual(request["validation_accesses"], 0)
        self.assertEqual(request["path_budget_contract_fingerprint"], self.contract["contract_fingerprint"])
        self.assertEqual(len(request["planned_executions"]), 16)
        self.assertEqual(len({item["namespace"] for item in request["planned_executions"]}), 16)
        self.assertLessEqual(request["worst_absolute_path_chars"], 220)
        generated = []
        for slice_number in range(1, 5):
            for role in ("baseline", "candidate"):
                for repetition in ("A", "B"):
                    item = temporal.plan_short_execution(
                        ROOT, f"ranging-short-ablation-s0{slice_number}", role, repetition
                    )["plan"]
                    generated.append(
                        {
                            "slice_id": f"ranging-short-ablation-s0{slice_number}",
                            "role": role,
                            "repetition": f"RUN-{repetition}",
                            "execution_id": item["execution_id"],
                            "execution_short_id": item["execution_short_id"],
                            "namespace": item["namespace"],
                        }
                    )
        self.assertEqual(request["planned_executions"], generated)

    def test_attempt_three_selects_short_factory_without_reading_historical_results(self):
        self.assertEqual(temporal.ATTEMPT_ID, ATTEMPT_ID)
        temporal.configure_harness(ROOT, "ranging-short-ablation-s01")
        self.assertIsNotNone(harness.SHORT_NAMESPACE_FACTORY)
        self.assertEqual(harness.CONTAMINATED_ROOTS, ())
        planned = temporal.plan_short_execution(ROOT, "ranging-short-ablation-s01", "baseline", "A")
        self.assertTrue(planned["plan"]["namespace"].startswith(".runs/rtv2/a3/s01/b/a/"))

    def test_path_budget_failure_prevents_worker_process_start(self):
        error = paths.ExecutionPathContractError("execution_path_budget_exceeded", "too long")
        with mock.patch.object(temporal, "plan_short_execution", side_effect=error), mock.patch.object(
            temporal.subprocess, "run"
        ) as process:
            with self.assertRaises(paths.ExecutionPathContractError) as raised:
                temporal.run_fresh(ROOT, "ranging-short-ablation-s01", "baseline", "A")
            self.assertEqual(raised.exception.reason_code, "execution_path_budget_exceeded")
            process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
