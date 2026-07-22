import datetime as dt
import importlib.util
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "data_reliability_controller",
    ROOT / "scripts" / "data_reliability_controller.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


NOW = dt.datetime(2026, 7, 19, 12, 0, tzinfo=dt.timezone.utc)


def healthy_snapshot():
    timestamp = "2026-07-19T11:59:30Z"
    candles = [{"date": timestamp, "close": 100}] * 40
    return {
        "summary": {
            "generatedAt": timestamp,
            "bots": [
                {
                    "key": "v1129",
                    "ok": True,
                    "dryRun": True,
                    "runtimeStatus": "available",
                    "latencyMs": 10,
                    "profitAllCoin": -2.5,
                    "stakeCurrency": "USDT",
                }
            ],
        },
        "registry": {
            "deployment": {
                "available": True,
                "dry_run_only": True,
                "git_short_sha": "0123456789ab",
            }
        },
        "market": {
            "sourceType": "freqtrade",
            "candles": candles,
            "lastAnalyzed": timestamp,
            "dataFreshness": {"ageSeconds": 30, "stale": False},
            "ticker": {"price": 118000.0, "updatedAt": timestamp},
        },
        "alpha": {"status": "ok", "source": "Binance Futures", "errors": []},
    }


class DataReliabilityAssessmentTest(unittest.TestCase):
    def test_healthy_snapshot_allows_data_driven_decisions(self):
        result = MODULE.assess_snapshot(healthy_snapshot(), now=NOW)
        self.assertEqual("reliable", result["overall_status"])
        self.assertTrue(result["decision_allowed"])
        self.assertEqual(0, result["summary"]["issue_count"])

    def test_missing_profit_is_incomplete_and_never_becomes_zero(self):
        snapshot = healthy_snapshot()
        snapshot["summary"]["bots"][0]["profitAllCoin"] = None
        result = MODULE.assess_snapshot(snapshot, now=NOW)
        performance = next(item for item in result["checks"] if item["id"] == "performance.v1129")
        self.assertEqual("incomplete", performance["status"])
        self.assertIsNone(performance["observed_value"])
        self.assertTrue(result["decision_allowed"])

    def test_stale_candles_open_the_circuit_breaker(self):
        snapshot = healthy_snapshot()
        snapshot["market"]["dataFreshness"] = {"ageSeconds": 3600, "stale": True}
        result = MODULE.assess_snapshot(snapshot, now=NOW)
        self.assertEqual("stale", result["overall_status"])
        self.assertFalse(result["decision_allowed"])


class FakeClient:
    base_url = "http://127.0.0.1:8090"

    def __init__(self, snapshots):
        self.snapshots = iter(snapshots)

    def snapshot(self, pair, timeframe):
        return next(self.snapshots)


class DataReliabilityRepairTest(unittest.TestCase):
    def test_dashboard_failure_restarts_only_data_service_then_reprobes(self):
        client = FakeClient([
            ({}, {"summary": "dashboard_request_failed", "registry": "dashboard_request_failed"}),
            (healthy_snapshot(), {}),
        ])
        with mock.patch.object(MODULE, "run_systemctl", return_value=(True, "ok")) as systemctl:
            report = MODULE.build_report(
                client,
                repair=True,
                report_dir=Path("runtime"),
                pair="BTC/USDT:USDT",
                timeframe="15m",
                dashboard_unit="freqtrade-monitor.service",
                refresh_unit="market-refresh.service",
                now=NOW,
            )
        systemctl.assert_called_once_with("restart", "freqtrade-monitor.service")
        self.assertEqual("restart_dashboard_data_service", report["repairs"][0]["action"])
        self.assertTrue(report["decision_allowed"])

    def test_atomic_latest_report_is_readable_by_dashboard_service_user(self):
        with tempfile.TemporaryDirectory() as temporary:
            report_dir = Path(temporary)
            with mock.patch.object(MODULE.os, "chmod", wraps=MODULE.os.chmod) as chmod:
                MODULE.write_report({"schema_version": MODULE.SCHEMA_VERSION}, report_dir)
            chmod.assert_any_call(report_dir / "latest.json", 0o644)

    def test_stale_market_triggers_existing_refresh_unit_then_reprobes(self):
        stale = healthy_snapshot()
        stale["market"]["dataFreshness"] = {"ageSeconds": 3600, "stale": True}
        client = FakeClient([(stale, {}), (healthy_snapshot(), {})])
        with mock.patch.object(MODULE, "run_systemctl", return_value=(True, "ok")) as systemctl:
            report = MODULE.build_report(
                client,
                repair=True,
                report_dir=Path("runtime"),
                pair="BTC/USDT:USDT",
                timeframe="15m",
                dashboard_unit="freqtrade-monitor.service",
                refresh_unit="market-refresh.service",
                now=NOW,
            )
        systemctl.assert_called_once_with("start", "market-refresh.service")
        self.assertEqual("refresh_market_data", report["repairs"][0]["action"])
        self.assertTrue(report["decision_allowed"])

    def test_unreachable_runtime_is_blocked_without_bot_repair_action(self):
        snapshot = healthy_snapshot()
        snapshot["summary"]["bots"][0].update({"ok": False, "errorCode": "ECONNREFUSED"})
        result = MODULE.assess_snapshot(snapshot, now=NOW)
        runtime = next(item for item in result["checks"] if item["id"] == "runtime.v1129")
        self.assertEqual("blocked", runtime["status"])
        self.assertFalse(result["decision_allowed"])

    def test_missing_ticker_and_partial_alpha_are_distinguished(self):
        snapshot = healthy_snapshot()
        snapshot["market"]["ticker"] = None
        snapshot["alpha"] = {"status": "partial", "errors": [{"key": "funding"}]}
        result = MODULE.assess_snapshot(snapshot, now=NOW)
        statuses = {item["id"]: item["status"] for item in result["checks"]}
        self.assertEqual("incomplete", statuses["market.ticker"])
        self.assertEqual("degraded", statuses["market.alpha"])
        self.assertFalse(result["decision_allowed"])

    def test_runtime_market_reload_timeout_blocks_paper_lane_decisions(self):
        checks = MODULE.assess_runtime_observations({
            "freqtrade-v1130-crash-rebound-shadow": {
                "status": "running",
                "restart_count": 0,
                "started_at": "2026-07-19T04:43:51Z",
                "logs": "2026-07-19 - ERROR - Could not load markets.",
                "log_error": None,
            }
        })
        by_id = {item["id"]: item for item in checks}
        incident = by_id["runtime_incidents.freqtrade-v1130-crash-rebound-shadow"]
        self.assertEqual("degraded", incident["status"])
        self.assertTrue(incident["blocks_decisions"])
        self.assertEqual(1, incident["observed_value"]["market_reload_timeouts"])

    def test_clean_running_container_is_reliable(self):
        checks = MODULE.assess_runtime_observations({
            "freqtrade-v1130-crash-rebound-shadow": {
                "status": "running",
                "restart_count": 0,
                "started_at": "2026-07-19T04:43:51Z",
                "logs": "Bot heartbeat.",
                "log_error": None,
            }
        })
        self.assertTrue(all(item["status"] == "reliable" for item in checks))


if __name__ == "__main__":
    unittest.main()
