import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_stage3b2_single_variable as stage3b2  # noqa: E402


class Stage3B2SingleVariableTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="stage3b2-test-"))
        (self.tmp / "strategies").mkdir()
        for name in ("RegimeAwareV6.py", "regime_aware_base.py", "regime_detector.py", "risk_manager.py"):
            shutil.copy2(ROOT / "strategies" / name, self.tmp / "strategies" / name)
        (self.tmp / "research/runtime").mkdir(parents=True)
        (self.tmp / "research/data/snapshots/demo").mkdir(parents=True)
        (self.tmp / "research/exchange_snapshots/snap").mkdir(parents=True)
        (self.tmp / "research/runtime/freqtrade-runtime.yaml").write_text("python_executable: python\n", encoding="utf-8")
        (self.tmp / "research/runtime/requirements-freqtrade.lock.txt").write_text("lock\n", encoding="utf-8")
        (self.tmp / "research/runtime/freqtrade-freeze.txt").write_text("freeze\n", encoding="utf-8")
        (self.tmp / "research/runtime/demo-futures-backtest-config.json").write_text(
            json.dumps(
                {
                    "trading_mode": "futures",
                    "margin_mode": "isolated",
                    "stake_currency": "USDT",
                    "exchange": {"pair_whitelist": ["BTC/USDT:USDT"]},
                }
            ),
            encoding="utf-8",
        )
        (self.tmp / "research/data/snapshots/demo/manifest.yaml").write_text(
            'dataset_id: "demo"\ntrading_mode: "futures"\ncandle_types: ["futures", "mark", "funding_rate"]\naggregate_sha256: "dataset-hash"\n',
            encoding="utf-8",
        )
        (self.tmp / "research/exchange_snapshots/snap/manifest.yaml").write_text(
            'snapshot_id: "snap"\ntrading_mode: "futures"\naggregate_sha256: "snapshot-hash"\nbtc_usdt_usdt_contract_size: 1.0\nleverage_tier_artifact: {"sha256": "lev-hash", "network_required": false}\n',
            encoding="utf-8",
        )
        self.base_hash = self._hash(self.tmp / "strategies/RegimeAwareV6.py").upper()
        self.campaign = {
            "campaign_id": "demo-stage3b2-single-variable",
            "mode": "single_variable_semantic_mutation",
            "runner_type": "single_variable_semantic_mutation",
            "scope": {
                "allowed_paths": [
                    "research/candidates/demo-stage3b2-single-variable/1/**",
                    "research/experiments/demo-stage3b2-single-variable/1/**",
                    "research/results/demo-stage3b2-single-variable/**",
                    "research/registry/**",
                    "reports/audits/stage3b2_single_variable_selection.md",
                ],
                "blocked_paths": ["strategies/**", ".env", "secrets/**"],
            },
            "budget": {
                "max_experiments": 1,
                "max_total_attempts": 1,
                "max_consecutive_failures": 1,
                "max_retries_per_experiment": 0,
                "max_wall_clock_minutes": 30,
            },
            "autonomy": {
                "automatically_claim_next": True,
                "automatically_generate_hypotheses": False,
                "automatically_promote_champion": False,
                "access_sealed_holdout": False,
            },
            "fixed_backtest": {
                "runtime_config": "research/runtime/freqtrade-runtime.yaml",
                "dataset_id": "demo",
                "dataset_manifest": "research/data/snapshots/demo/manifest.yaml",
                "strategy": "RegimeAwareV6",
                "strategy_file": "strategies/RegimeAwareV6.py",
                "strategy_path": "strategies",
                "config": "research/runtime/demo-futures-backtest-config.json",
                "timerange": "20260329-20260412",
                "timeframe": "1h",
                "pairs": ["BTC/USDT:USDT"],
                "fee": "0.0004",
                "datadir": "research/data/snapshots/demo/data",
            },
            "sealed_offline_backtest": {"exchange_snapshot": "research/exchange_snapshots/snap"},
            "stage3b1": {
                "baseline_reference": {"run_dir": "missing"},
                "expected_input_fingerprint": "demo",
            },
            "stage3b2": {"max_semantic_mutations": 1},
            "stop_conditions": ["single_experiment_complete"],
            "escalation_conditions": ["blocked_path"],
        }

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _hash(self, path):
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_variable_selection_audit_selects_allowed_threshold_and_excludes_forbidden(self):
        audit = stage3b2.audit_variable_selection(self.tmp)
        self.assertEqual(audit["selected_variable"]["variable_name"], "ranging_short_setup.bb_percent_min")
        forbidden = {item["variable_name"] for item in audit["forbidden_variables_excluded"]}
        self.assertIn("can_short", forbidden)
        self.assertIn("stoploss", forbidden)

    def test_deterministic_experiment_spec_is_complete_and_quality_disabled(self):
        with mock.patch("run_stage3b2_single_variable.BASE_STRATEGY_SHA256", self.base_hash):
            audit = stage3b2.audit_variable_selection(self.tmp)
            spec = stage3b2.create_experiment_spec(self.tmp, self.campaign, "1", audit)
        self.assertEqual(spec["experiment_type"], "single_variable_semantic_mutation")
        self.assertEqual(spec["selected_variable"], "ranging_short_setup.bb_percent_min")
        self.assertEqual(spec["old_value"], 0.8)
        self.assertEqual(spec["new_value"], 0.85)
        self.assertFalse(spec["quality_evaluation_enabled"])
        self.assertFalse(spec["champion_promotion_enabled"])
        self.assertFalse(spec["sealed_holdout_enabled"])
        self.assertTrue((self.tmp / "research/experiments/demo-stage3b2-single-variable/1/experiment-spec.yaml").exists())

    def test_ast_precise_change_and_semantic_mutation_count(self):
        source = (self.tmp / "strategies/regime_aware_base.py").read_text(encoding="utf-8")
        mutated, diff = stage3b2.mutate_dependency_source(source)
        self.assertIn('(dataframe["bb_percent"] > 0.85)', mutated)
        self.assertEqual(diff["semantic_mutation_count"], 1)
        self.assertEqual(diff["old_value"], 0.8)
        self.assertEqual(diff["new_value"], 0.85)

    def test_candidate_manifest_and_single_mutation_verification(self):
        with mock.patch("run_stage3b2_single_variable.BASE_STRATEGY_SHA256", self.base_hash), mock.patch("create_candidate_strategy.BASE_STRATEGY_SHA256", self.base_hash):
            audit = stage3b2.audit_variable_selection(self.tmp)
            spec = stage3b2.create_experiment_spec(self.tmp, self.campaign, "1", audit)
            candidate = stage3b2.create_mutated_candidate(self.tmp, self.campaign, "1", spec)
        verification = stage3b2.verify_ast_single_mutation(self.tmp, self.tmp / candidate["candidate_dir"], candidate["candidate_class"])
        self.assertTrue(verification["ok"])
        self.assertEqual(verification["semantic_mutation_count"], 1)
        self.assertTrue((self.tmp / candidate["candidate_manifest"]).exists())

    def test_second_variable_change_is_rejected(self):
        with mock.patch("run_stage3b2_single_variable.BASE_STRATEGY_SHA256", self.base_hash), mock.patch("create_candidate_strategy.BASE_STRATEGY_SHA256", self.base_hash):
            audit = stage3b2.audit_variable_selection(self.tmp)
            spec = stage3b2.create_experiment_spec(self.tmp, self.campaign, "1", audit)
            candidate = stage3b2.create_mutated_candidate(self.tmp, self.campaign, "1", spec)
        dep = self.tmp / candidate["candidate_dir"] / "regime_aware_base.py"
        dep.write_text(dep.read_text(encoding="utf-8").replace('dataframe["rsi"] > 60', 'dataframe["rsi"] > 61', 1), encoding="utf-8")
        verification = stage3b2.verify_ast_single_mutation(self.tmp, self.tmp / candidate["candidate_dir"], candidate["candidate_class"])
        self.assertFalse(verification["ok"])
        self.assertEqual(verification["reason_code"], "unauthorized_candidate_semantic_diff")

    def test_second_source_location_operator_import_can_short_leverage_stoploss_roi_rejected(self):
        with mock.patch("run_stage3b2_single_variable.BASE_STRATEGY_SHA256", self.base_hash), mock.patch("create_candidate_strategy.BASE_STRATEGY_SHA256", self.base_hash):
            audit = stage3b2.audit_variable_selection(self.tmp)
            spec = stage3b2.create_experiment_spec(self.tmp, self.campaign, "1", audit)
            candidate = stage3b2.create_mutated_candidate(self.tmp, self.campaign, "1", spec)
        dep = self.tmp / candidate["candidate_dir"] / "regime_aware_base.py"
        original_mutated = dep.read_text(encoding="utf-8")
        cases = [
            ("operator", lambda text: text.replace('dataframe["bb_percent"] > 0.85', 'dataframe["bb_percent"] >= 0.85', 1)),
            ("import", lambda text: "import os\n" + text),
            ("can_short", lambda text: text.replace("can_short = True", "can_short = False", 1)),
            ("leverage", lambda text: text + "\ndef leverage(self):\n    return 10\n"),
            ("stoploss", lambda text: text.replace("stoploss = -0.04", "stoploss = -0.05", 1)),
            ("roi", lambda text: text.replace('"0": 0.05', '"0": 0.06', 1)),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                dep.write_text(mutate(original_mutated), encoding="utf-8")
                verification = stage3b2.verify_ast_single_mutation(self.tmp, self.tmp / candidate["candidate_dir"], candidate["candidate_class"])
                self.assertFalse(verification["ok"])

    def test_behavior_changed_and_unchanged_classification(self):
        baseline = {
            "summary": {"core": {"total_trades": 3}, "enter_tag_counts": {}, "exit_reason_counts": {}, "normalized_trades_sha256": "a", "normalized_trades_count": 3},
            "run_dir": "missing",
        }
        unchanged = {"summary": baseline["summary"], "normalized_trades": {"rows": []}}
        changed = {"summary": {"core": {"total_trades": 2}, "enter_tag_counts": {}, "exit_reason_counts": {}, "normalized_trades_sha256": "b", "normalized_trades_count": 2}, "normalized_trades": {"rows": [{"pair": "BTC"}]}}
        self.assertEqual(stage3b2.compare_baseline_candidate(baseline, unchanged)["behavior_verdict"], "behavior_unchanged")
        self.assertEqual(stage3b2.compare_baseline_candidate(baseline, changed)["behavior_verdict"], "behavior_changed")

    def test_registry_records_not_evaluated_and_not_allowed_without_champion(self):
        conn = sqlite3.connect(":memory:")
        stage3b2.init_registry(conn)
        stage3b2.record_registry(
            conn,
            {
                "campaign_id": "c",
                "experiment_id": "1",
                "experiment_spec_path": "spec",
                "base_strategy_hash": "base",
                "candidate_strategy_hash": "candidate",
                "selected_variable": "v",
                "old_value": 1,
                "new_value": 2,
                "semantic_mutation_count": 1,
                "candidate_class": "C",
                "candidate_path": "path",
                "static_validation": "passed",
                "run_a_report": "a",
                "run_b_report": "b",
                "reproducibility_verdict": "passed",
                "baseline_trade_hash": "h",
                "candidate_trade_hash": "h2",
                "behavioral_diff_path": "diff",
                "engineering_verdict": "mutation_verified_behavior_changed",
            },
        )
        row = conn.execute("SELECT quality_evaluation_status, promotion_status, engineering_verdict FROM stage3b2_single_variable_experiments").fetchone()
        self.assertEqual(row[0], "not_evaluated")
        self.assertEqual(row[1], "not_allowed")
        self.assertNotIn("champion", row[2])


if __name__ == "__main__":
    unittest.main()
