import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_control import ResearchStore, run_orchestrator  # noqa: E402
from research_environment_doctor import run_environment_doctor  # noqa: E402
from run_experiment import compare_core_metrics, sha256_file  # noqa: E402


def write_yaml(path: Path, data: dict) -> Path:
    lines = []
    for key, value in data.items():
        if isinstance(value, (list, dict)):
            lines.append(f"{key}: {json.dumps(value, sort_keys=True)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class ResearchEnvironmentDoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="research-doctor-test-"))
        (self.tmp / ".venv-freqtrade" / "Scripts").mkdir(parents=True)
        (self.tmp / "research" / "runtime").mkdir(parents=True)
        (self.tmp / "research" / "data" / "snapshots" / "demo" / "data").mkdir(parents=True)
        (self.tmp / "strategies").mkdir()
        (self.tmp / "user_data").mkdir()
        (self.tmp / "strategies" / "FixedDemoStrategy.py").write_text("class FixedDemoStrategy: pass\n", encoding="utf-8")
        (self.tmp / "user_data" / "config_backtest_demo.json").write_text('{"dry_run": true}\n', encoding="utf-8")
        (self.tmp / ".venv-freqtrade" / "Scripts" / "python.exe").write_text("not a real executable\n", encoding="utf-8")
        self.data_file = self.tmp / "research" / "data" / "snapshots" / "demo" / "data" / "BTC_USDT-1h.json"
        self.data_file.write_text("[]\n", encoding="utf-8")
        self.lock_file = self.tmp / "research" / "runtime" / "requirements-freqtrade.lock.txt"
        self.lock_file.write_text("freqtrade==2024.5\n", encoding="utf-8")
        self.runtime_path = write_yaml(
            self.tmp / "research" / "runtime" / "freqtrade-runtime.yaml",
            {
                "runtime_id": "test-runtime",
                "python_executable": ".venv-freqtrade/Scripts/python.exe",
                "expected_python_version": "3.12",
                "expected_freqtrade_version": "2024.5",
                "dependency_lock_file": "research/runtime/requirements-freqtrade.lock.txt",
                "dependency_lock_sha256": sha256_file(self.lock_file),
                "invocation": "python_module",
                "network_access": "disabled",
            },
        )
        self.manifest_path = self.write_manifest()
        self.config = self.base_config()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_manifest(self, **overrides):
        payload = {
            "dataset_id": "demo-dataset",
            "exchange": "binance",
            "trading_mode": "spot",
            "timerange": "20240101-20240131",
            "timeframes": ["1h"],
            "pairs": ["BTC/USDT"],
            "data_path": "research/data/snapshots/demo/data",
            "files": [
                {
                    "path": "research/data/snapshots/demo/data/BTC_USDT-1h.json",
                    "bytes": self.data_file.stat().st_size,
                    "sha256": sha256_file(self.data_file),
                }
            ],
            "source": "unit fixture",
            "created_at": "2026-07-10T00:00:00Z",
            "campaign_mutable": False,
            "network_accessed_during_campaign": False,
        }
        payload.update(overrides)
        return write_yaml(self.tmp / "research" / "data" / "snapshots" / "demo" / "manifest.yaml", payload)

    def base_config(self):
        return {
            "campaign_id": "doctor-campaign",
            "mode": "fixed_backtest",
            "runner_type": "fixed_backtest",
            "scope": {
                "allowed_paths": [
                    "research/**",
                    ".venv-freqtrade/**",
                    "strategies",
                    "strategies/FixedDemoStrategy.py",
                    "user_data/config_backtest_demo.json",
                ],
                "blocked_paths": [
                    ".env",
                    "secrets/**",
                    "deploy/**",
                    "user_data/config_live.json",
                    "configs/production/**",
                    "scripts/start_bot.sh",
                    "scripts/refresh_data.sh",
                ],
            },
            "budget": {
                "max_experiments": 1,
                "max_total_attempts": 2,
                "max_consecutive_failures": 1,
                "max_retries_per_experiment": 1,
                "max_wall_clock_minutes": 60,
            },
            "autonomy": {
                "automatically_claim_next": True,
                "automatically_generate_hypotheses": False,
                "automatically_promote_champion": False,
                "access_sealed_holdout": False,
                "lease_seconds": 1,
            },
            "fixed_backtest": {
                "runtime_config": "research/runtime/freqtrade-runtime.yaml",
                "dataset_id": "demo-dataset",
                "dataset_manifest": "research/data/snapshots/demo/manifest.yaml",
                "subcommand": "backtesting",
                "strategy": "FixedDemoStrategy",
                "strategy_file": "strategies/FixedDemoStrategy.py",
                "strategy_path": "strategies",
                "config": "user_data/config_backtest_demo.json",
                "timerange": "20240101-20240102",
                "timeframe": "1h",
                "pairs": ["BTC/USDT"],
                "fee": "0.001",
                "datadir": "research/data/snapshots/demo/data",
                "timeout_seconds": 5,
                "acceptance_gate": {"min_trades": 1, "max_drawdown": 0.5},
            },
            "stop_conditions": ["queue_empty"],
            "escalation_conditions": ["blocked_path"],
        }

    def mock_python_ok(self):
        return mock.patch(
            "research_environment_doctor.run_python",
            side_effect=[
                (0, "3.12.13"),
                (0, "present"),
                (0, "2024.5"),
            ],
        )

    def test_runtime_yaml_validation(self):
        self.runtime_path.write_text("runtime_id: test-runtime\n", encoding="utf-8")
        with mock.patch("research_environment_doctor.run_python") as run_python:
            report = run_environment_doctor(self.tmp, self.config)
        self.assertFalse(report["ok"])
        self.assertIn("environment_not_ready", report["reason_codes"])
        run_python.assert_not_called()

    def test_python_executable_missing(self):
        (self.tmp / ".venv-freqtrade" / "Scripts" / "python.exe").unlink()
        report = run_environment_doctor(self.tmp, self.config)
        self.assertIn("runtime_python_missing", report["reason_codes"])
        self.assertEqual(report["issues"][0]["failure_type"], "infra_permanent")

    def test_freqtrade_module_missing(self):
        with mock.patch(
            "research_environment_doctor.run_python",
            side_effect=[(0, "3.12.13"), (0, "missing")],
        ):
            report = run_environment_doctor(self.tmp, self.config)
        self.assertIn("freqtrade_module_missing", report["reason_codes"])

    def test_freqtrade_version_mismatch(self):
        with mock.patch(
            "research_environment_doctor.run_python",
            side_effect=[(0, "3.12.13"), (0, "present"), (0, "2023.1")],
        ):
            report = run_environment_doctor(self.tmp, self.config)
        self.assertIn("freqtrade_version_mismatch", report["reason_codes"])

    def test_dataset_missing(self):
        shutil.rmtree(self.tmp / "research" / "data" / "snapshots" / "demo" / "data")
        with self.mock_python_ok():
            report = run_environment_doctor(self.tmp, self.config)
        self.assertIn("dataset_missing", report["reason_codes"])

    def test_manifest_missing(self):
        self.manifest_path.unlink()
        with self.mock_python_ok():
            report = run_environment_doctor(self.tmp, self.config)
        self.assertIn("dataset_manifest_missing", report["reason_codes"])

    def test_file_hash_mismatch(self):
        self.data_file.write_text("[1]\n", encoding="utf-8")
        with self.mock_python_ok():
            report = run_environment_doctor(self.tmp, self.config)
        self.assertIn("dataset_hash_mismatch", report["reason_codes"])

    def test_pair_timeframe_and_timerange_mismatch(self):
        self.write_manifest(pairs=["ETH/USDT"], timeframes=["15m"], timerange="20240201-20240228")
        with self.mock_python_ok():
            report = run_environment_doctor(self.tmp, self.config)
        messages = "\n".join(item["message"] for item in report["issues"])
        self.assertIn("pairs not in dataset", messages)
        self.assertIn("timeframe not in dataset", messages)
        self.assertIn("timerange not covered", messages)

    def test_doctor_aggregates_multiple_errors(self):
        (self.tmp / ".venv-freqtrade" / "Scripts" / "python.exe").unlink()
        self.manifest_path.unlink()
        report = run_environment_doctor(self.tmp, self.config)
        self.assertGreaterEqual(len(report["reason_codes"]), 2)
        self.assertIn("runtime_python_missing", report["reason_codes"])
        self.assertIn("dataset_manifest_missing", report["reason_codes"])

    def test_strict_cli_returns_nonzero(self):
        path = self.tmp / "campaign.json"
        path.write_text(json.dumps(self.config), encoding="utf-8")
        (self.tmp / ".venv-freqtrade" / "Scripts" / "python.exe").unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "research_environment_doctor.py"),
                "--campaign",
                str(path),
                "--strict",
                "--json",
            ],
            cwd=self.tmp,
            text=True,
            capture_output=True,
            shell=False,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_environment_preflight_failure_does_not_create_attempt_or_candidate_failure(self):
        path = self.tmp / "campaign.json"
        path.write_text(json.dumps(self.config), encoding="utf-8")
        (self.tmp / ".venv-freqtrade" / "Scripts" / "python.exe").unlink()
        store = ResearchStore(self.tmp)
        store.init_schema()
        store.begin()
        store.upsert_campaign(self.config, path, owner="seed")
        store.add_hypothesis("doctor-campaign", "fixed", "fixed", {"runner_type": "fixed_backtest"}, 1)
        store.commit()
        store.close()

        report = run_orchestrator(self.tmp, path, owner="runner")
        self.assertEqual(report["campaign"]["status"], "failed")
        self.assertEqual(report["budget"]["attempts"], 0)
        self.assertEqual(report["budget"]["consecutive_failures"], 0)
        store = ResearchStore(self.tmp)
        attempts = store.conn.execute("SELECT COUNT(*) FROM experiment_attempts").fetchone()[0]
        experiment = store.conn.execute("SELECT status, retry_count FROM experiments").fetchone()
        store.close()
        self.assertEqual(attempts, 0)
        self.assertEqual(experiment["status"], "queued")
        self.assertEqual(experiment["retry_count"], 0)

    def test_environment_failure_classification_is_infra_permanent(self):
        report = run_environment_doctor(self.tmp, self.config)
        failures = {item["reason_code"]: item["failure_type"] for item in report["issues"]}
        self.assertEqual(failures["runtime_python_missing"], "infra_permanent")

    def test_repeated_execution_core_metric_compare(self):
        metrics = {
            "normalized": {
                "total_trades": 4,
                "total_profit": 12.5,
                "total_profit_pct": 0.12,
                "max_drawdown": 0.05,
                "profit_factor": 1.8,
                "winrate": 0.75,
            }
        }
        self.assertTrue(compare_core_metrics(metrics, dict(metrics))["consistent"])
        changed = {"normalized": dict(metrics["normalized"], total_trades=5)}
        self.assertFalse(compare_core_metrics(metrics, changed)["consistent"])


if __name__ == "__main__":
    unittest.main()
