import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sealed_exchange_factory import OfflineContractViolation, create_sealed_exchange  # noqa: E402
from validate_exchange_snapshot import aggregate_hash  # noqa: E402
from run_experiment import sha256_file  # noqa: E402


MARKET = {
    "id": "BTCUSDT",
    "symbol": "BTC/USDT",
    "base": "BTC",
    "quote": "USDT",
    "spot": True,
    "active": True,
    "precision": {"amount": 0.00001, "price": 0.01},
    "limits": {"amount": {"min": 0.00001}, "price": {"min": 0.01}},
}
FUTURES_MARKET = {
    "id": "BTCUSDT",
    "symbol": "BTC/USDT:USDT",
    "base": "BTC",
    "quote": "USDT",
    "settle": "USDT",
    "type": "swap",
    "spot": False,
    "swap": True,
    "linear": True,
    "contract": True,
    "contractSize": 1.0,
    "active": True,
    "precision": {"amount": 0.001, "price": 0.1},
    "limits": {"amount": {"min": 0.001}, "price": {"min": 0.1}},
}


class DummyApi:
    def __init__(self):
        self.markets = None
        self.currencies = None
        self.options = {}

    def set_markets(self, markets, currencies):
        self.markets = markets
        self.currencies = currencies


class DummyExchange:
    def __init__(self):
        self._api = DummyApi()
        self._api_async = DummyApi()
        self._markets = {}
        self._leverage_tiers = {}
        self.validated = []

    @property
    def markets(self):
        if not self._markets:
            self.reload_markets(True)
        return self._markets

    def reload_markets(self, *_args, **_kwargs):
        raise AssertionError("reload should be replaced")

    def validate_stakecurrency(self, stake_currency):
        self.validated.append(("stake", stake_currency))

    def validate_timeframes(self, timeframe):
        self.validated.append(("timeframe", timeframe))

    def parse_leverage_tier(self, tier):
        return {
            "minNotional": tier["minNotional"],
            "maxNotional": tier["maxNotional"],
            "maintenanceMarginRate": tier["maintenanceMarginRate"],
            "maxLeverage": tier["maxLeverage"],
            "maintAmt": float(tier.get("info", {}).get("cum", 0)),
        }


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_yaml(path: Path, payload):
    lines = []
    for key, value in payload.items():
        if isinstance(value, (dict, list)):
            lines.append(f"{key}: {json.dumps(value, sort_keys=True)}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_snapshot(root: Path, market=None, currencies=None, trading_mode="spot"):
    snapshot = root / "research" / "exchange_snapshots" / "snapshot"
    snapshot.mkdir(parents=True)
    leverage_path = root / ".venv-freqtrade" / "Lib" / "site-packages" / "freqtrade" / "exchange" / "binance_leverage_tiers.json"
    leverage_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(
        leverage_path,
        {
            "BTC/USDT:USDT": [
                {
                    "minNotional": 0.0,
                    "maxNotional": 300000.0,
                    "maintenanceMarginRate": 0.004,
                    "maxLeverage": 150.0,
                    "info": {"cum": "0.0"},
                }
            ]
        },
    )
    market = market if market is not None else MARKET
    currencies = currencies if currencies is not None else {"BTC": {"code": "BTC"}, "USDT": {"code": "USDT"}}
    pair = "BTC/USDT:USDT" if trading_mode == "futures" else "BTC/USDT"
    write_json(snapshot / "markets.raw.json", {pair: market} if market else {})
    write_json(snapshot / "markets.normalized.json", {pair: market} if market else {})
    write_json(snapshot / "currencies.json", currencies)
    write_json(snapshot / "options.json", {"defaultType": "swap" if trading_mode == "futures" else "spot"})
    if trading_mode == "spot":
        (snapshot / "capture.log").write_text("ok\n", encoding="utf-8")
    else:
        write_json(snapshot / "fapi.exchangeInfo.raw.json", {"symbols": [{"symbol": "BTCUSDT"}]})
        write_json(snapshot / "leverage-tiers-contract.json", {"sha256": "abc123", "network_required": False})
        write_json(snapshot / "futures-scope-fingerprint.json", {"hash_domain": "ccxt_futures_research_scope_v1", "sha256": "def456"})
    entries = []
    for path in sorted(snapshot.iterdir()):
        if path.is_file():
            entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(snapshot / "artifact-hashes.json", {item["path"]: {"bytes": item["bytes"], "sha256": item["sha256"]} for item in entries})
    entries = []
    for path in sorted(snapshot.iterdir()):
        if path.is_file() and path.name != "manifest.yaml":
            entries.append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_yaml(
        snapshot / "manifest.yaml",
        {
            "snapshot_id": "unit",
            "exchange": "binance",
            "trading_mode": trading_mode,
            "python_version": "3.12.13",
            "freqtrade_version": "2025.8",
            "ccxt_version": "4.5.64",
            "markets_count": 1 if market else 0,
            "currencies_count": len(currencies),
            "files": entries,
            "aggregate_sha256": aggregate_hash(entries),
            "sealed": True,
            "leverage_tier_artifact": {
                "path": ".venv-freqtrade/Lib/site-packages/freqtrade/exchange/binance_leverage_tiers.json",
                "sha256": sha256_file(leverage_path),
                "network_required": False,
            }
            if trading_mode == "futures"
            else None,
        },
    )
    return snapshot


class SealedExchangeFactoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sealed-exchange-test-"))
        self.snapshot = create_snapshot(self.tmp)
        self.exchange = DummyExchange()

    def tearDown(self):
        for path in self.tmp.rglob("*"):
            if path.is_file():
                os.chmod(path, 0o666)
        shutil.rmtree(self.tmp)

    def fake_modules(self):
        exchange_resolver_module = types.ModuleType("freqtrade.resolvers.exchange_resolver")

        class ExchangeResolver:
            @staticmethod
            def load_exchange(config, *, validate=True, exchange_config=None, load_leverage_tiers=False):
                self.assertFalse(validate)
                self.assertFalse(load_leverage_tiers)
                return self.exchange

        exchange_resolver_module.ExchangeResolver = ExchangeResolver
        return mock.patch.dict(
            sys.modules,
            {
                "freqtrade": types.ModuleType("freqtrade"),
                "freqtrade.resolvers": types.ModuleType("freqtrade.resolvers"),
                "freqtrade.resolvers.exchange_resolver": exchange_resolver_module,
            },
        )

    def config(self):
        return {"exchange": {"name": "binance"}, "stake_currency": "USDT", "timeframe": "1h", "trading_mode": "spot", "fee": 0.001}

    def futures_config(self):
        return {
            "exchange": {"name": "binance", "pair_whitelist": ["BTC/USDT:USDT"]},
            "stake_currency": "USDT",
            "timeframe": "1h",
            "trading_mode": "futures",
            "margin_mode": "isolated",
            "fee": 0.0004,
        }

    def test_validate_false_and_markets_injected(self):
        with self.fake_modules():
            exchange = create_sealed_exchange(self.config(), self.snapshot)
        self.assertIs(exchange, self.exchange)
        self.assertIn("BTC/USDT", exchange._markets)
        self.assertIn("BTC/USDT", exchange._api.markets)
        self.assertIn("BTC/USDT", exchange._api_async.markets)
        self.assertIn(("stake", "USDT"), exchange.validated)
        self.assertIn(("timeframe", "1h"), exchange.validated)

    def test_reload_markets_forbidden(self):
        with self.fake_modules():
            exchange = create_sealed_exchange(self.config(), self.snapshot)
        with self.assertRaises(OfflineContractViolation):
            exchange.reload_markets(True)

    def test_non_spot_market_rejected(self):
        snapshot = create_snapshot(self.tmp / "bad", dict(MARKET, spot=False))
        with self.fake_modules(), self.assertRaises(Exception):
            create_sealed_exchange(self.config(), snapshot)

    def test_missing_currencies_rejected(self):
        snapshot = create_snapshot(self.tmp / "bad2", currencies={"BTC": {"code": "BTC"}})
        with self.fake_modules(), self.assertRaises(Exception):
            create_sealed_exchange(self.config(), snapshot)

    def test_futures_market_injected(self):
        snapshot = create_snapshot(self.tmp / "futures", market=FUTURES_MARKET, trading_mode="futures")
        with self.fake_modules():
            exchange = create_sealed_exchange(self.futures_config(), snapshot)
        self.assertIs(exchange, self.exchange)
        self.assertIn("BTC/USDT:USDT", exchange._markets)
        self.assertIn("BTC/USDT:USDT", exchange._api.markets)
        self.assertIn("BTC/USDT:USDT", exchange._leverage_tiers)


if __name__ == "__main__":
    unittest.main()
