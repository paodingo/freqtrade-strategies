import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from research_control import ResearchStore, run_orchestrator  # noqa: E402
from run_experiment import (  # noqa: E402
    RunnerError,
    build_command,
    parse_metrics,
    run_fixed_backtest,
    trade_detail_signature,
)
from verify_test_baseline import compare  # noqa: E402


def campaign_config(root, fake_script=None, mode="fixed_backtest"):
    fixed = {
        "executable": sys.executable,
        "subcommand": "backtesting",
        "strategy": "FixedDemoStrategy",
        "strategy_file": "strategies/FixedDemoStrategy.py",
        "strategy_path": "strategies",
        "config": "user_data/config_backtest_demo.json",
        "timerange": "20240101-20240102",
        "timeframe": "1h",
        "pairs": ["BTC/USDT"],
        "fee": "0.001",
        "datadir": "user_data/data",
        "timeout_seconds": 5,
        "acceptance_gate": {"min_trades": 1, "max_drawdown": 0.50},
    }
    if fake_script:
        fixed["fake_freqtrade_script"] = str(fake_script.relative_to(root).as_posix())
    return {
        "campaign_id": "runner-campaign",
        "mode": mode,
        "runner_type": "fixed_backtest",
        "scope": {
            "allowed_paths": [
                "research/**",
                "strategies",
                "strategies/FixedDemoStrategy.py",
                "user_data/config_backtest_demo.json",
                "user_data/data",
                "user_data/data/**",
                "research/fakes/**",
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
            "max_total_attempts": 1,
            "max_consecutive_failures": 1,
            "max_retries_per_experiment": 0,
            "max_wall_clock_minutes": 60,
        },
        "autonomy": {
            "automatically_claim_next": True,
            "automatically_generate_hypotheses": False,
            "automatically_promote_champion": False,
            "access_sealed_holdout": False,
            "lease_seconds": 1,
        },
        "fixed_backtest": fixed,
        "stop_conditions": ["queue_empty"],
        "escalation_conditions": ["blocked_path"],
    }


class ResearchRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="research-runner-test-"))
        (self.tmp / "strategies").mkdir()
        (self.tmp / "user_data" / "data").mkdir(parents=True)
        (self.tmp / "research" / "fakes").mkdir(parents=True)
        (self.tmp / "strategies" / "FixedDemoStrategy.py").write_text("class FixedDemoStrategy: pass\n", encoding="utf-8")
        (self.tmp / "user_data" / "config_backtest_demo.json").write_text('{"dry_run": true}\n', encoding="utf-8")
        (self.tmp / "user_data" / "data" / "BTC_USDT-1h.json").write_text("[]\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write_fake(self, body):
        script = self.tmp / "research" / "fakes" / "fake_freqtrade.py"
        script.write_text(body, encoding="utf-8")
        return script

    def successful_fake(self, overrides=None, trades=None):
        metrics = {
            "schema": "fake-freqtrade-backtest-v1",
            "strategy_name": "FixedDemoStrategy",
            "total_trades": 4,
            "total_profit": 12.5,
            "total_profit_pct": 0.12,
            "max_drawdown": 0.05,
            "profit_factor": 1.8,
            "winrate": 0.75,
            "avg_duration": "1:00:00",
            "start_time": "2024-01-01",
            "end_time": "2024-01-02",
            "trades": trades
            if trades is not None
            else [
                {
                    "pair": "BTC/USDT",
                    "open_date": "2024-01-01 01:00:00+00:00",
                    "close_date": "2024-01-01 02:00:00+00:00",
                    "open_rate": 42000.0,
                    "close_rate": 42100.0,
                    "profit_abs": 1.0,
                    "profit_ratio": 0.01,
                    "exit_reason": "roi",
                }
            ],
        }
        if overrides:
            metrics.update(overrides)
        return self.write_fake(
            "import json, sys\n"
            "print('fake stdout')\n"
            "print('fake stderr', file=sys.stderr)\n"
            "out = sys.argv[sys.argv.index('--export-filename') + 1]\n"
            f"metrics = json.loads({json.dumps(json.dumps(metrics))})\n"
            "json.dump(metrics, open(out, 'w', encoding='utf-8'))\n"
        )

    def run_once(self, fake_script, config_overrides=None, payload=None, verification_run_id=None):
        config = campaign_config(self.tmp, fake_script)
        if config_overrides:
            config["fixed_backtest"].update(config_overrides)
        return run_fixed_backtest(self.tmp, config, 1, payload or {}, verification_run_id=verification_run_id)

    def test_command_argument_whitelist(self):
        fake = self.successful_fake()
        config = campaign_config(self.tmp, fake)
        command = build_command(self.tmp, config["fixed_backtest"], self.tmp / "research/results/runner-campaign/1")
        self.assertIn("backtesting", command)
        with self.assertRaises(RunnerError):
            bad = dict(config["fixed_backtest"], subcommand="hyperopt")
            build_command(self.tmp, bad, self.tmp / "research/results/runner-campaign/1")

    def test_subprocess_never_uses_shell_true(self):
        fake = self.successful_fake()
        real_popen = subprocess.Popen

        def guarded_popen(*args, **kwargs):
            self.assertFalse(kwargs.get("shell"))
            return real_popen(*args, **kwargs)

        with mock.patch("subprocess.Popen", side_effect=guarded_popen):
            result = self.run_once(fake)
        self.assertEqual(result["status"], "accepted")

    def test_live_config_rejected_by_guard(self):
        fake = self.successful_fake()
        result = self.run_once(fake, {"config": "user_data/config_live.json"})
        self.assertEqual(result["status"], "escalated")
        self.assertEqual(result["failure_type"], "guard_violation")

    def test_repo_outside_path_rejected(self):
        fake = self.successful_fake()
        result = self.run_once(fake, {"config": "../outside.json"})
        self.assertEqual(result["status"], "escalated")

    def test_normal_backtest_result_parse(self):
        fake = self.successful_fake()
        result = self.run_once(fake)
        metrics = json.loads((self.tmp / "research/results/runner-campaign/1/metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(metrics["normalized"]["total_trades"], 4)
        self.assertEqual(metrics["normalized"]["pair_count"], 1)
        self.assertEqual(metrics["normalized"]["trade_detail_count"], 1)
        self.assertEqual(len(metrics["normalized"]["trade_detail_sha256"]), 64)

    def test_missing_result_file(self):
        fake = self.write_fake("print('no result file')\n")
        result = self.run_once(fake)
        self.assertEqual(result["failure_type"], "output_parse_error")

    def test_nonzero_exit_code(self):
        fake = self.write_fake("import sys\nprint('boom', file=sys.stderr)\nsys.exit(7)\n")
        result = self.run_once(fake)
        self.assertEqual(result["failure_type"], "backtest_error")

    def test_timeout(self):
        fake = self.write_fake("import time\nprint('sleeping')\ntime.sleep(10)\n")
        result = self.run_once(fake, {"timeout_seconds": 1})
        self.assertEqual(result["failure_type"], "infra_transient")

    def test_timeout_cleans_process_tree(self):
        fake = self.write_fake("import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\ntime.sleep(10)\n")
        started = time.time()
        result = self.run_once(fake, {"timeout_seconds": 1})
        self.assertLess(time.time() - started, 8)
        self.assertEqual(result["failure_type"], "infra_transient")

    def test_stdout_stderr_saved(self):
        fake = self.successful_fake()
        self.run_once(fake)
        out = self.tmp / "research/results/runner-campaign/1/stdout.log"
        err = self.tmp / "research/results/runner-campaign/1/stderr.log"
        self.assertIn("fake stdout", out.read_text(encoding="utf-8"))
        self.assertIn("fake stderr", err.read_text(encoding="utf-8"))

    def test_artifact_hashes(self):
        fake = self.successful_fake()
        self.run_once(fake)
        hashes = json.loads((self.tmp / "research/results/runner-campaign/1/artifact-hashes.json").read_text(encoding="utf-8"))
        self.assertIn("command.json", hashes)
        self.assertIn("runner-report.json", hashes)

    def test_output_schema_incompatible(self):
        fake = self.write_fake(
            "import json, sys\nout = sys.argv[sys.argv.index('--export-filename') + 1]\njson.dump({'unexpected': True}, open(out, 'w'))\n"
        )
        result = self.run_once(fake)
        self.assertEqual(result["failure_type"], "output_parse_error")

    def test_metrics_missing_fields(self):
        fake = self.successful_fake({"profit_factor": None})
        result = self.run_once(fake)
        metrics = json.loads((self.tmp / "research/results/runner-campaign/1/metrics.json").read_text(encoding="utf-8"))
        self.assertIn("profit_factor", metrics["missing_fields"])
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["failure_type"], "candidate_rejected")

    def test_acceptance_gate_rejects_candidate(self):
        fake = self.successful_fake({"total_trades": 0})
        result = self.run_once(fake)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["failure_type"], "candidate_rejected")

    def test_orchestrator_crash_recovery_with_fixed_backtest(self):
        fake = self.successful_fake()
        config = campaign_config(self.tmp, fake)
        config["budget"]["max_retries_per_experiment"] = 1
        config["budget"]["max_total_attempts"] = 2
        path = self.tmp / "campaign.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        store = ResearchStore(self.tmp)
        store.init_schema()
        store.begin()
        store.upsert_campaign(config, path, owner="seed")
        store.add_hypothesis("runner-campaign", "fixed", "fixed", {"runner_type": "fixed_backtest"}, 1)
        store.commit()
        store.close()
        with self.assertRaises(Exception):
            run_orchestrator(self.tmp, path, owner="owner-a", simulate_crash_after=1)
        time.sleep(1.2)
        report = run_orchestrator(self.tmp, path, owner="owner-b", resume=True)
        self.assertEqual(report["counts"].get("accepted"), 1)

    def test_idempotent_same_input(self):
        fake = self.successful_fake()
        first = self.run_once(fake)
        second = self.run_once(fake)
        self.assertEqual(first["status"], second["status"])
        self.assertIn("existing runner report reused", second["message"])

    def test_verification_mode_runs_independently(self):
        fake = self.write_fake(
            "import json, pathlib, sys\n"
            "counter = pathlib.Path('research/fakes/counter.txt')\n"
            "value = int(counter.read_text()) + 1 if counter.exists() else 1\n"
            "counter.write_text(str(value))\n"
            "out = sys.argv[sys.argv.index('--export-filename') + 1]\n"
            "payload = {'schema': 'fake-freqtrade-backtest-v1', 'strategy_name': 'FixedDemoStrategy', 'total_trades': 4, 'total_profit': 12.5, 'total_profit_pct': 0.12, 'max_drawdown': 0.05, 'profit_factor': 1.8, 'winrate': 0.75, 'avg_duration': '1:00:00', 'start_time': '2024-01-01', 'end_time': '2024-01-02', 'trades': [{'pair': 'BTC/USDT', 'open_date': '2024-01-01', 'close_date': '2024-01-01', 'open_rate': 1, 'close_rate': 2, 'profit_abs': value}]}\n"
            "json.dump(payload, open(out, 'w', encoding='utf-8'))\n"
        )
        first = self.run_once(fake, verification_run_id="RUN-A")
        second = self.run_once(fake, verification_run_id="RUN-B")
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["status"], "accepted")
        self.assertTrue((self.tmp / "research/results/runner-campaign/1/RUN-A/runner-report.json").exists())
        self.assertTrue((self.tmp / "research/results/runner-campaign/1/RUN-B/runner-report.json").exists())
        first_report = json.loads((self.tmp / "research/results/runner-campaign/1/RUN-A/runner-report.json").read_text(encoding="utf-8"))
        second_report = json.loads((self.tmp / "research/results/runner-campaign/1/RUN-B/runner-report.json").read_text(encoding="utf-8"))
        self.assertEqual(first_report["input_fingerprint"], second_report["input_fingerprint"])
        self.assertEqual((self.tmp / "research/fakes/counter.txt").read_text(encoding="utf-8"), "2")

    def test_trade_detail_signature_is_order_stable(self):
        trades = [
            {"pair": "BTC/USDT", "open_date": "b", "close_date": "b", "open_rate": 2, "close_rate": 3},
            {"pair": "BTC/USDT", "open_date": "a", "close_date": "a", "open_rate": 1, "close_rate": 2},
        ]
        first = trade_detail_signature({"schema": "fake-freqtrade-backtest-v1", "trades": trades}, "FixedDemoStrategy")
        second = trade_detail_signature({"schema": "fake-freqtrade-backtest-v1", "trades": list(reversed(trades))}, "FixedDemoStrategy")
        self.assertEqual(first, second)

    def test_baseline_compare_rejects_new_failure(self):
        expected = [{"test": "known.test", "exception": "AssertionError", "fingerprint": "same"}]
        self.assertEqual(compare("unit", expected, expected), [])
        errors = compare("unit", [{"test": "new.test", "exception": "AssertionError", "fingerprint": "x"}], expected)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
