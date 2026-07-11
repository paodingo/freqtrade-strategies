import json
import os
import shutil
import socket
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from run_offline_backtest import NetworkBlocked, NetworkBlocker, run_offline_backtest  # noqa: E402
from test_sealed_exchange_factory import create_snapshot  # noqa: E402


class DummyExchange:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class OfflineBacktestRunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="offline-runner-test-"))
        (self.tmp / "strategies").mkdir()
        (self.tmp / "research" / "runtime").mkdir(parents=True)
        (self.tmp / "research" / "data" / "snapshots" / "demo").mkdir(parents=True)
        self.snapshot = create_snapshot(self.tmp / "exchange")
        self.strategy_file = self.tmp / "strategies" / "RegimeAwareV6.py"
        self.strategy_file.write_text("class RegimeAwareV6: pass\n", encoding="utf-8")
        self.config_file = self.tmp / "research" / "runtime" / "demo-backtest-config.json"
        self.config_file.write_text('{"dry_run": true, "fee": 0.001}\n', encoding="utf-8")
        self.dataset_manifest = self.tmp / "research" / "data" / "snapshots" / "demo" / "manifest.yaml"
        self.dataset_manifest.write_text("dataset_id: demo\n", encoding="utf-8")

    def tearDown(self):
        for path in self.tmp.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o666)
        shutil.rmtree(self.tmp)

    def campaign(self):
        return {
            "campaign_id": "offline-campaign",
            "fixed_backtest": {
                "strategy": "RegimeAwareV6",
                "strategy_file": "strategies/RegimeAwareV6.py",
                "strategy_path": "strategies",
                "config": "research/runtime/demo-backtest-config.json",
                "dataset_id": "demo",
                "dataset_manifest": "research/data/snapshots/demo/manifest.yaml",
                "timerange": "20240101-20240131",
                "timeframe": "1h",
                "pairs": ["BTC/USDT"],
                "fee": "0.001",
                "datadir": "research/data/snapshots/demo/data",
            },
        }

    def fake_backtesting_module(self):
        module = types.ModuleType("freqtrade.optimize.backtesting")

        class Backtesting:
            def __init__(self, config, exchange=None):
                self.config = config
                self.exchange = exchange

            def start(self):
                payload = {
                    "schema": "fake-freqtrade-backtest-v1",
                    "strategy_name": "RegimeAwareV6",
                    "total_trades": 2,
                    "total_profit": 1.5,
                    "total_profit_pct": 0.015,
                    "max_drawdown": 0.01,
                    "profit_factor": 1.2,
                    "winrate": 0.5,
                    "avg_duration": "1:00:00",
                    "start_time": "2024-01-01",
                    "end_time": "2024-01-31",
                    "trades": [{"pair": "BTC/USDT", "open_date": "a", "close_date": "b", "open_rate": 1, "close_rate": 2}],
                }
                Path(self.config["exportfilename"]).write_text(json.dumps(payload), encoding="utf-8")

        module.Backtesting = Backtesting
        return module

    def test_network_blocker_rejects_connect(self):
        with NetworkBlocker() as blocker:
            with self.assertRaises(NetworkBlocked):
                socket.create_connection(("example.com", 443), timeout=1)
        self.assertTrue(blocker.attempts)

    def test_offline_runner_success_with_injected_exchange(self):
        exchange = DummyExchange()
        def fake_setup(_spec, result_dir):
            return {"fee": 0.001, "exportfilename": result_dir / "freqtrade-backtest-result.json"}

        with mock.patch("run_offline_backtest.setup_backtest_config", side_effect=fake_setup), mock.patch(
            "run_offline_backtest.create_sealed_exchange", return_value=exchange
        ), mock.patch.dict(
            sys.modules,
            {
                "freqtrade": types.ModuleType("freqtrade"),
                "freqtrade.optimize": types.ModuleType("freqtrade.optimize"),
                "freqtrade.optimize.backtesting": self.fake_backtesting_module(),
            },
        ):
            result = run_offline_backtest(self.tmp, self.campaign(), 1, "RUN-A", self.snapshot)
        self.assertEqual(result["status"], "accepted")
        report = json.loads((self.tmp / "research/results/offline-campaign/1/RUN-A/runner-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["network_attempts"], [])
        self.assertTrue(exchange.closed)

    def test_network_attempt_fails_offline_contract(self):
        def attempt_network(_spec, _result_dir):
            socket.create_connection(("example.com", 443), timeout=1)

        with mock.patch("run_offline_backtest.setup_backtest_config", side_effect=attempt_network):
            result = run_offline_backtest(self.tmp, self.campaign(), 1, "RUN-A", self.snapshot)
        self.assertEqual(result["failure_type"], "infra_permanent")
        self.assertEqual(result["reason_code"], "offline_contract_violation")


if __name__ == "__main__":
    unittest.main()
