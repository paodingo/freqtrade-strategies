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

from create_candidate_strategy import (  # noqa: E402
    BASE_STRATEGY_SHA256,
    candidate_class_name,
    candidate_root,
    create_candidate_strategy,
    validate_candidate_source,
    validate_candidate_write_scope,
)
from research_guard import PathGuardError  # noqa: E402
from run_stage3b1_candidate_identity import compare_identity, init_registry, record_state, upsert_lifecycle  # noqa: E402


class Stage3B1CandidateLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="stage3b1-test-"))
        (self.tmp / "strategies").mkdir()
        (self.tmp / "research" / "runtime").mkdir(parents=True)
        (self.tmp / "research" / "data" / "snapshots" / "demo").mkdir(parents=True)
        (self.tmp / "research" / "exchange_snapshots" / "snap").mkdir(parents=True)
        (self.tmp / "strategies" / "RegimeAwareV6.py").write_text(
            '"""Historical V6 RegimeAware strategy."""\n'
            "from freqtrade.strategy import IStrategy\n"
            "from regime_aware_base import RegimeAwareBaseMixin\n\n"
            "class RegimeAwareV6(RegimeAwareBaseMixin, IStrategy):\n"
            '    """V6 keeps both trend and ranging entries for historical comparisons."""\n\n'
            "    enable_ranging_entries = True\n",
            encoding="utf-8",
        )
        for name in ("regime_aware_base.py", "regime_detector.py", "risk_manager.py"):
            (self.tmp / "strategies" / name).write_text(f"class {name.replace('.py', '').title().replace('_', '')}: pass\n", encoding="utf-8")
        self.base_hash = self._hash(self.tmp / "strategies" / "RegimeAwareV6.py").upper()
        self.dataset_manifest = self.tmp / "research" / "data" / "snapshots" / "demo" / "manifest.yaml"
        self.dataset_manifest.write_text('dataset_id: "demo"\naggregate_sha256: "dataset-hash"\n', encoding="utf-8")
        self.snapshot_manifest = self.tmp / "research" / "exchange_snapshots" / "snap" / "manifest.yaml"
        self.snapshot_manifest.write_text(
            'snapshot_id: "snap"\naggregate_sha256: "snapshot-hash"\nleverage_tier_artifact: {"sha256": "lev-hash"}\n',
            encoding="utf-8",
        )
        (self.tmp / "research" / "runtime" / "freqtrade-runtime.yaml").write_text("python_executable: python\n", encoding="utf-8")
        (self.tmp / "research" / "runtime" / "requirements-freqtrade.lock.txt").write_text("lock\n", encoding="utf-8")
        (self.tmp / "research" / "runtime" / "freqtrade-freeze.txt").write_text("freeze\n", encoding="utf-8")
        (self.tmp / "research" / "runtime" / "demo-futures-backtest-config.json").write_text("{}", encoding="utf-8")
        self.campaign_path = self.tmp / "campaign.yaml"
        self.campaign_path.write_text(
            """
campaign_id: demo-stage3b1-candidate-identity
mode: candidate_identity_equivalence
runner_type: candidate_identity_equivalence
scope:
  allowed_paths: ["research/candidates/demo-stage3b1-candidate-identity/1/**", "research/results/demo-stage3b1-candidate-identity/**", "research/registry/**"]
  blocked_paths: ["strategies/**", ".env", "secrets/**"]
budget:
  max_experiments: 1
  max_total_attempts: 1
  max_consecutive_failures: 1
  max_retries_per_experiment: 0
  max_wall_clock_minutes: 30
autonomy:
  automatically_claim_next: true
  automatically_generate_hypotheses: false
  automatically_promote_champion: false
  access_sealed_holdout: false
fixed_backtest:
  runtime_config: research/runtime/freqtrade-runtime.yaml
  dataset_id: demo
  dataset_manifest: research/data/snapshots/demo/manifest.yaml
  strategy: RegimeAwareV6
  strategy_file: strategies/RegimeAwareV6.py
  strategy_path: strategies
  config: research/runtime/demo-futures-backtest-config.json
  timerange: 20260329-20260412
  timeframe: 1h
  pairs: ["BTC/USDT:USDT"]
  fee: "0.0004"
  datadir: research/data/snapshots/demo/data
sealed_offline_backtest:
  exchange_snapshot: research/exchange_snapshots/snap
stage3b1:
  expected_input_fingerprint: demo
stop_conditions: ["single_experiment_complete"]
escalation_conditions: ["blocked_path"]
""".strip()
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        for path in self.tmp.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o666)
        shutil.rmtree(self.tmp)

    def _hash(self, path):
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_deterministic_candidate_class_name(self):
        self.assertEqual(candidate_class_name("demo", "1"), "RegimeAware_C3B1_E0001")
        self.assertEqual(candidate_class_name("demo", "stage3b1-identity-001"), "RegimeAware_C3B1_E0001")
        self.assertNotEqual(candidate_class_name("demo", "1"), candidate_class_name("demo", "2"))

    def test_candidate_write_scope_rejects_other_experiment(self):
        campaign = json.loads(json.dumps({"campaign_id": "demo-stage3b1-candidate-identity", "scope": {"allowed_paths": ["research/candidates/demo-stage3b1-candidate-identity/1/**"], "blocked_paths": []}}))
        with self.assertRaises(PathGuardError):
            validate_candidate_write_scope(self.tmp, campaign, "1", [self.tmp / "research/candidates/demo-stage3b1-candidate-identity/2/C.py"])

    def test_candidate_write_scope_rejects_symlink_escape(self):
        campaign = {"campaign_id": "demo-stage3b1-candidate-identity", "scope": {"allowed_paths": ["research/candidates/demo-stage3b1-candidate-identity/1/**"], "blocked_paths": []}}
        root = self.tmp / "research/candidates/demo-stage3b1-candidate-identity"
        (root / "1").mkdir(parents=True)
        original = Path.is_symlink

        def fake_is_symlink(path):
            return path.name == "1" or original(path)

        with mock.patch("pathlib.Path.is_symlink", fake_is_symlink), self.assertRaises(Exception):
            validate_candidate_write_scope(self.tmp, campaign, "1", [root / "1" / "C.py"])

    def test_create_candidate_allows_only_identity_diff(self):
        with mock.patch("create_candidate_strategy.BASE_STRATEGY_SHA256", self.base_hash):
            result = create_candidate_strategy(self.tmp, self.campaign_path, "1")
        candidate_dir = self.tmp / result["candidate_dir"]
        validation = validate_candidate_source(self.tmp, candidate_dir, result["candidate_class"])
        self.assertTrue(validation["ok"])
        self.assertEqual(result["candidate_class"], "RegimeAware_C3B1_E0001")
        self.assertTrue((candidate_dir / "candidate-manifest.yaml").exists())

    def test_modified_can_short_dependency_is_rejected(self):
        with mock.patch("create_candidate_strategy.BASE_STRATEGY_SHA256", self.base_hash):
            result = create_candidate_strategy(self.tmp, self.campaign_path, "1")
        candidate_dir = self.tmp / result["candidate_dir"]
        dep = candidate_dir / "regime_aware_base.py"
        dep.write_text(dep.read_text(encoding="utf-8") + "\ncan_short = False\n", encoding="utf-8")
        validation = validate_candidate_source(self.tmp, candidate_dir, result["candidate_class"])
        self.assertFalse(validation["ok"])
        self.assertIn("regime_aware_base.py", validation["dependency_mismatches"])

    def test_entry_exit_leverage_dependency_changes_are_rejected_by_hash(self):
        with mock.patch("create_candidate_strategy.BASE_STRATEGY_SHA256", self.base_hash):
            result = create_candidate_strategy(self.tmp, self.campaign_path, "1")
        candidate_dir = self.tmp / result["candidate_dir"]
        dep = candidate_dir / "regime_aware_base.py"
        for text in ("def populate_entry_trend(self): pass\n", "def populate_exit_trend(self): pass\n", "def leverage(self): return 10\n"):
            dep.write_text(dep.read_text(encoding="utf-8") + text, encoding="utf-8")
            validation = validate_candidate_source(self.tmp, candidate_dir, result["candidate_class"])
            self.assertFalse(validation["ok"])

    def test_comparison_reports_mismatch_fields(self):
        baseline = {"summary": {"core": {"total_trades": 3, "long_trade_count": 2, "short_trade_count": 1, "total_profit": 1}, "enter_tag_counts": {}, "exit_reason_counts": {}, "normalized_trades_sha256": "a", "normalized_trades_count": 3}, "normalized_trade_hash": "a"}
        candidate = {"summary": {"core": {"total_trades": 2, "long_trade_count": 1, "short_trade_count": 1, "total_profit": 1}, "enter_tag_counts": {}, "exit_reason_counts": {}, "normalized_trades_sha256": "b", "normalized_trades_count": 2}, "normalized_trade_hash": "b"}
        comparison = compare_identity(baseline, candidate)
        self.assertEqual(comparison["reason_code"], "candidate_identity_semantic_mismatch")
        self.assertIn("core", comparison["differences"])

    def test_registry_records_identity_verified_without_champion_terms(self):
        conn = sqlite3.connect(":memory:")
        init_registry(conn)
        record_state(conn, "c", "1", "identity_verified")
        upsert_lifecycle(
            conn,
            "c",
            "1",
            "RegimeAware_C3B1_E0001",
            "research/candidates/c/1/RegimeAware_C3B1_E0001.py",
            BASE_STRATEGY_SHA256,
            creation_status="created",
            static_validation_status="passed",
            execution_status="accepted",
            equivalence_verdict="identity_verified",
        )
        row = conn.execute("SELECT equivalence_verdict FROM stage3b1_candidate_lifecycle").fetchone()
        self.assertEqual(row[0], "identity_verified")
        dump = "\n".join(str(item) for item in conn.execute("SELECT * FROM stage3b1_candidate_lifecycle").fetchall())
        self.assertNotIn("champion", dump.lower())


if __name__ == "__main__":
    unittest.main()
