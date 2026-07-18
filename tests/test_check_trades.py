import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_DIR / "scripts" / "check_trades.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("check_trades", SCRIPT)
CHECK_TRADES = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(CHECK_TRADES)


class CheckTradesTest(unittest.TestCase):
    def test_registry_sources_create_baseline_then_emit_exact_close(self):
        registry = {
            "schema_version": "strategy-registry-v1",
            "strategies": [{
                "strategy_id": "v1130",
                "display_name": "V11.30",
                "stage": "dry_run",
                "runtime": {"bot_key": "v1130", "source": "sqlite", "dry_run": True},
            }],
        }
        open_trade = {
            "trade_id": "8", "pair": "ETH/USDT:USDT", "is_open": True,
            "is_short": False, "enter_tag": "v1130_crash_rebound_long",
        }
        closed_trade = {**open_trade, "is_open": False, "exit_reason": "v1130_rebound_time_exit", "profit_abs": "3.5"}

        with patch.object(CHECK_TRADES, "read_strategy_trades", return_value=[open_trade]):
            baseline, events = CHECK_TRADES.monitor(registry, {})
        self.assertEqual([], events)

        with patch.object(CHECK_TRADES, "read_strategy_trades", return_value=[closed_trade]):
            updated, events = CHECK_TRADES.monitor(registry, baseline)
        self.assertEqual(1, len(events))
        self.assertEqual("closed", events[0]["type"])
        self.assertEqual("v1130_rebound_time_exit", events[0]["trade"]["exit_reason"])
        self.assertTrue(updated["bots"]["v1130"]["ok"])

    def test_sqlite_reader_normalizes_freqtrade_trade(self):
        with tempfile.TemporaryDirectory() as temporary:
            db_path = Path(temporary) / "trades.sqlite"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE trades (id INTEGER, pair TEXT, is_open INTEGER, is_short INTEGER, "
                "enter_tag TEXT, exit_reason TEXT, close_profit_abs REAL, close_profit REAL)"
            )
            connection.execute(
                "INSERT INTO trades VALUES (1, 'BTC/USDT:USDT', 0, 1, 'v102_trending_short_core', 'stop_loss', -4.2, -0.01)"
            )
            connection.commit()
            connection.close()
            runtime = {"sqlite": {"env": "TEST_TRADE_DB"}}
            with patch.dict("os.environ", {"TEST_TRADE_DB": str(db_path)}):
                trades = CHECK_TRADES.read_sqlite(runtime)
        self.assertEqual("1", trades[0]["trade_id"])
        self.assertEqual("stop_loss", trades[0]["exit_reason"])
        self.assertEqual(-4.2, trades[0]["profit_abs"])

    def test_first_run_state_file_does_not_replay_history(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            registry_path = root / "registry.json"
            state_path = root / "state.json"
            registry_path.write_text(json.dumps({
                "schema_version": "strategy-registry-v1",
                "strategies": [],
            }), encoding="utf-8")
            self.assertEqual(0, CHECK_TRADES.main(["--registry", str(registry_path), "--state", str(state_path)]))
            saved = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(CHECK_TRADES.STATE_SCHEMA, saved["schema"])

    def test_recovered_source_establishes_baseline_without_replaying_history(self):
        registry = {
            "schema_version": "strategy-registry-v1",
            "strategies": [{
                "strategy_id": "v1130", "display_name": "V11.30", "stage": "dry_run",
                "runtime": {"bot_key": "v1130", "source": "sqlite", "dry_run": True},
            }],
        }
        previous = {
            "schema": CHECK_TRADES.STATE_SCHEMA,
            "bots": {"v1130": {"ok": False, "error": "database missing", "consecutive_failures": 3}},
        }
        historical = [{"trade_id": "1", "pair": "BTC/USDT:USDT", "is_open": False, "exit_reason": "stop_loss"}]
        with patch.object(CHECK_TRADES, "read_strategy_trades", return_value=historical):
            state, events = CHECK_TRADES.monitor(registry, previous)
        self.assertEqual([], events)
        self.assertTrue(state["bots"]["v1130"]["ok"])
        self.assertIn("1", state["bots"]["v1130"]["trades"])


if __name__ == "__main__":
    unittest.main()
