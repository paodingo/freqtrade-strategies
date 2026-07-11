import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_experiment import build_command  # noqa: E402
from run_experiment import evaluate_acceptance, parse_metrics  # noqa: E402
from run_stage3a5_acceptance import (  # noqa: E402
    FUTURES_PUBLIC_API,
    ONLINE_PUBLIC_API,
    build_online_network_audit,
    classify_endpoint,
    compare_summaries,
    decimal_string,
    inspect_ccxt_urls,
    make_online_config,
    normalize_trades,
)


class Stage3A5AcceptanceTest(unittest.TestCase):
    def test_fixed_runner_command_forces_cache_none(self):
        command = build_command(
            Path.cwd(),
            {
                "python_executable": sys.executable,
                "strategy": "S",
                "config": "c.json",
                "timerange": "20240101-20240131",
                "timeframe": "1h",
                "datadir": "data",
                "fee": "0.001",
                "pairs": ["BTC/USDT"],
            },
            Path("out"),
        )
        self.assertIn("--cache", command)
        self.assertEqual(command[command.index("--cache") + 1], "none")
        self.assertIn("--export-directory", command)

    def test_online_config_overrides_public_urls_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research/runtime").mkdir(parents=True)
            base = root / "research/runtime/demo-backtest-config.json"
            base.write_text(
                json.dumps(
                    {
                        "exchange": {
                            "key": "x",
                            "secret": "y",
                            "ccxt_config": {"urls": {"api": {"private": "keep"}}},
                            "ccxt_async_config": {"urls": {"api": {"private": "keep"}}},
                            "pair_whitelist": [],
                        },
                        "pairlists": [{"method": "StaticPairList"}],
                    }
                ),
                encoding="utf-8",
            )
            campaign = {
                "fixed_backtest": {
                    "config": "research/runtime/demo-backtest-config.json",
                    "pairs": ["BTC/USDT"],
                    "fee": "0.001",
                    "timeframe": "1h",
                }
            }
            path = make_online_config(root, campaign, root / "out")
            cfg = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(cfg["exchange"]["key"], "")
        self.assertEqual(cfg["exchange"]["secret"], "")
        self.assertEqual(cfg["exchange"]["ccxt_config"]["urls"]["api"]["public"], ONLINE_PUBLIC_API)
        self.assertEqual(cfg["exchange"]["ccxt_async_config"]["urls"]["api"]["public"], ONLINE_PUBLIC_API)
        self.assertEqual(cfg["pairlists"], [{"method": "StaticPairList", "allow_inactive": False}])

    def test_futures_online_config_overrides_fapi_public_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research/runtime").mkdir(parents=True)
            base = root / "research/runtime/demo-futures-config.json"
            base.write_text(
                json.dumps(
                    {
                        "trading_mode": "futures",
                        "margin_mode": "isolated",
                        "exchange": {
                            "key": "x",
                            "secret": "y",
                            "ccxt_config": {"urls": {"api": {"fapiPrivate": "keep-private"}}},
                            "ccxt_async_config": {"urls": {"api": {"fapiPrivate": "keep-private"}}},
                            "pair_whitelist": [],
                        },
                        "pairlists": [{"method": "StaticPairList"}],
                    }
                ),
                encoding="utf-8",
            )
            campaign = {
                "fixed_backtest": {
                    "config": "research/runtime/demo-futures-config.json",
                    "pairs": ["BTC/USDT:USDT"],
                    "fee": "0.0004",
                    "timeframe": "1h",
                }
            }
            path = make_online_config(root, campaign, root / "out")
            cfg = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(cfg["exchange"]["key"], "")
        self.assertEqual(cfg["exchange"]["secret"], "")
        self.assertEqual(cfg["exchange"]["ccxt_config"]["urls"]["api"]["fapiPublic"], FUTURES_PUBLIC_API)
        self.assertEqual(cfg["exchange"]["ccxt_config"]["options"]["fetchMarkets"], {"types": ["linear"]})
        self.assertNotIn("private", cfg["exchange"]["ccxt_config"]["urls"]["api"])

    def test_inspect_ccxt_urls_rejects_private_change(self):
        with mock.patch("run_stage3a5_acceptance.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = json.dumps(
                {
                    "sync_public": ONLINE_PUBLIC_API,
                    "async_public": ONLINE_PUBLIC_API,
                    "sync_private": "changed",
                    "async_private": "https://api.binance.com/api/v3",
                    "sync_sapi": "https://api.binance.com/sapi/v1",
                    "async_sapi": "https://api.binance.com/sapi/v1",
                }
            )
            run.return_value.stderr = ""
            with self.assertRaises(Exception):
                inspect_ccxt_urls(Path.cwd(), {"fixed_backtest": {"runtime_config": "research/runtime/freqtrade-runtime.yaml", "strategy": "S", "timerange": "t", "timeframe": "1h", "datadir": "d", "fee": "0.001", "pairs": ["BTC/USDT"]}}, Path("cfg.json"))

    def test_decimal_canonical_normalization(self):
        self.assertEqual(decimal_string("1.23000000004"), "1.23")
        self.assertEqual(decimal_string("0.00000000006"), "0.0000000001")

    def test_normalized_trades_stable_sort_and_excludes_unstable_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "fake",
                        "trades": [
                            {"pair": "BTC/USDT", "open_date": "b", "open_rate": "2", "trade_id": 2},
                            {"pair": "BTC/USDT", "open_date": "a", "open_rate": "1.00000000001", "trade_id": 1},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            normalized = normalize_trades(path, "S")
        self.assertEqual(normalized["count"], 2)
        self.assertNotIn("trade_id", normalized["rows"][0])
        self.assertEqual(normalized["rows"][0]["open_date"], "a")

    def test_comparison_reports_field_differences(self):
        result = compare_summaries({"core": {"total_trades": 1}, "normalized_trades_sha256": "a"}, {"core": {"total_trades": 2}, "normalized_trades_sha256": "b"})
        self.assertFalse(result["consistent"])
        self.assertIn("core", result["differences"])
        self.assertIn("normalized_trades_sha256", result["differences"])

    def test_zero_trade_coverage_is_validation_error_not_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "schema": "fake-freqtrade-backtest-v1",
                        "strategy_name": "RegimeAwareV6",
                        "total_trades": 0,
                        "total_profit": 0,
                        "total_profit_pct": 0,
                        "max_drawdown": 0,
                        "profit_factor": 0,
                        "winrate": 0,
                        "avg_duration": "0:00:00",
                        "start_time": "2026-03-15",
                        "end_time": "2026-03-29",
                        "trades": [],
                    }
                ),
                encoding="utf-8",
            )
            metrics = parse_metrics(result_path, {"strategy": "RegimeAwareV6", "timerange": "20260315-20260329", "pairs": ["BTC/USDT:USDT"]})
        status, failure_type, reason_code, reasons, verdict = evaluate_acceptance(
            metrics,
            {
                "coverage": {
                    "min_total_trades": 2,
                    "min_long_trades": 1,
                    "min_short_trades": 1,
                    "require_closed_trades": True,
                    "require_enter_tag": True,
                    "require_exit_reason": True,
                }
            },
        )
        self.assertEqual(status, "rejected")
        self.assertEqual(failure_type, "validation_error")
        self.assertEqual(reason_code, "acceptance_fixture_no_trades")
        self.assertEqual(verdict["status"], "incomplete")
        self.assertNotEqual(failure_type, "candidate_rejected")
        self.assertTrue(reasons)

    def test_long_short_coverage_passes_without_profit_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "result.json"
            result_path.write_text(
                json.dumps(
                    {
                        "schema": "fake-freqtrade-backtest-v1",
                        "strategy_name": "RegimeAwareV6",
                        "total_trades": 2,
                        "total_profit": -100,
                        "total_profit_pct": -0.1,
                        "max_drawdown": 999,
                        "profit_factor": 0.1,
                        "winrate": 0,
                        "avg_duration": "1:00:00",
                        "start_time": "2026-03-29",
                        "end_time": "2026-04-12",
                        "trades": [
                            {"pair": "BTC/USDT:USDT", "open_date": "a", "close_date": "b", "is_short": False, "enter_tag": "long", "exit_reason": "roi"},
                            {"pair": "BTC/USDT:USDT", "open_date": "c", "close_date": "d", "is_short": True, "enter_tag": "short", "exit_reason": "stop_loss"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            metrics = parse_metrics(result_path, {"strategy": "RegimeAwareV6", "timerange": "20260329-20260412", "pairs": ["BTC/USDT:USDT"]})
        status, failure_type, reason_code, _reasons, verdict = evaluate_acceptance(
            metrics,
            {"coverage": {"min_total_trades": 2, "min_long_trades": 1, "min_short_trades": 1, "require_closed_trades": True, "require_enter_tag": True, "require_exit_reason": True}},
        )
        self.assertEqual(status, "accepted")
        self.assertIsNone(failure_type)
        self.assertIsNone(reason_code)
        self.assertEqual(verdict["status"], "passed")

    def test_endpoint_policy_allows_only_futures_public_market_data(self):
        allowed = classify_endpoint("GET", "fapi.binance.com", "/fapi/v1/exchangeInfo")
        forbidden = classify_endpoint("GET", "fapi.binance.com", "/fapi/v1/account")
        unknown = classify_endpoint("GET", "fapi.binance.com", "/fapi/v1/ticker/price")
        self.assertTrue(allowed["allowed"])
        self.assertFalse(forbidden["allowed"])
        self.assertEqual(forbidden["classification"], "private_or_trade")
        self.assertFalse(unknown["allowed"])

    def test_online_network_audit_rejects_non_allowlisted_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                build_online_network_audit(
                    Path(tmp),
                    {"ccxt_sync": {}, "ccxt_async": {}},
                    b"fetch Request: binance GET https://fapi.binance.com/fapi/v1/account RequestHeaders: {}",
                    b"",
                    {"used": False},
                )

    def test_online_network_audit_records_allowed_exchange_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = build_online_network_audit(
                Path(tmp),
                {"ccxt_sync": {}, "ccxt_async": {}},
                b"fetch Request: binance GET https://fapi.binance.com/fapi/v1/exchangeInfo RequestHeaders: {}",
                b"",
                {"used": True, "type": "httpsProxy", "host": "127.0.0.1", "port": 10808},
            )
        self.assertEqual(audit["violations"], [])
        self.assertEqual(audit["requests"][0]["path"], "/fapi/v1/exchangeInfo")


if __name__ == "__main__":
    unittest.main()
