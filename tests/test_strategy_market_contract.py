import json
import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_strategy_market_contract import validate_contract  # noqa: E402


def write_strategy(path: Path, can_short: bool, leverage: bool = False):
    body = f"class DemoStrategy:\n    can_short = {can_short!r}\n"
    if leverage:
        body += "    def leverage(self, *args, **kwargs):\n        return 1\n"
    path.write_text(body, encoding="utf-8")


def write_config(path: Path, trading_mode: str, pair: str, stake: str = "USDT"):
    path.write_text(
        json.dumps(
            {
                "trading_mode": trading_mode,
                "margin_mode": "isolated" if trading_mode == "futures" else "",
                "stake_currency": stake,
                "exchange": {"pair_whitelist": [pair]},
            }
        ),
        encoding="utf-8",
    )


def write_manifest(path: Path, trading_mode: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = ""
    if trading_mode == "futures":
        extra = 'candle_types: ["futures", "mark", "funding_rate"]\nfunding_model_synthetic: false\n'
    path.write_text(f'trading_mode: "{trading_mode}"\n{extra}', encoding="utf-8")


def write_snapshot(path: Path, trading_mode: str):
    path.mkdir(parents=True, exist_ok=True)
    extra = ""
    if trading_mode == "futures":
        extra = (
            "btc_usdt_usdt_contract_size: 1.0\n"
            'leverage_tier_artifact: {"sha256": "abc123", "network_required": false}\n'
        )
    (path / "manifest.yaml").write_text(f'trading_mode: "{trading_mode}"\n{extra}', encoding="utf-8")


class StrategyMarketContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.strategy = self.root / "DemoStrategy.py"
        self.config = self.root / "config.json"
        self.dataset = self.root / "dataset" / "manifest.yaml"
        self.snapshot = self.root / "snapshot"

    def tearDown(self):
        self.tmp.cleanup()

    def result(self, can_short, trading_mode, pair, dataset_mode, snapshot_mode, stake="USDT"):
        write_strategy(self.strategy, can_short)
        write_config(self.config, trading_mode, pair, stake=stake)
        write_manifest(self.dataset, dataset_mode)
        write_snapshot(self.snapshot, snapshot_mode)
        return validate_contract(self.strategy, "DemoStrategy", self.config, self.dataset, self.snapshot)

    def test_can_short_true_spot_rejected(self):
        self.assertFalse(self.result(True, "spot", "BTC/USDT", "spot", "spot")["ok"])

    def test_can_short_false_spot_allowed(self):
        self.assertTrue(self.result(False, "spot", "BTC/USDT", "spot", "spot")["ok"])

    def test_can_short_true_futures_allowed(self):
        self.assertTrue(self.result(True, "futures", "BTC/USDT:USDT", "futures", "futures")["ok"])

    def test_spot_pair_with_futures_config_rejected(self):
        self.assertFalse(self.result(True, "futures", "BTC/USDT", "futures", "futures")["ok"])

    def test_futures_pair_with_spot_config_rejected(self):
        self.assertFalse(self.result(False, "spot", "BTC/USDT:USDT", "spot", "spot")["ok"])

    def test_spot_dataset_with_futures_config_rejected(self):
        self.assertFalse(self.result(True, "futures", "BTC/USDT:USDT", "spot", "futures")["ok"])

    def test_spot_snapshot_with_futures_config_rejected(self):
        self.assertFalse(self.result(True, "futures", "BTC/USDT:USDT", "futures", "spot")["ok"])

    def test_settle_currency_mismatch_rejected(self):
        self.assertFalse(self.result(True, "futures", "BTC/USDT:USDT", "futures", "futures", stake="BUSD")["ok"])

    def test_futures_dataset_requires_mark_candles(self):
        write_strategy(self.strategy, True)
        write_config(self.config, "futures", "BTC/USDT:USDT")
        self.dataset.parent.mkdir(parents=True, exist_ok=True)
        self.dataset.write_text('trading_mode: "futures"\ncandle_types: ["futures", "funding_rate"]\n', encoding="utf-8")
        write_snapshot(self.snapshot, "futures")
        result = validate_contract(self.strategy, "DemoStrategy", self.config, self.dataset, self.snapshot)
        self.assertFalse(result["ok"])
        self.assertIn("mark candles", " ".join(result["issues"]))

    def test_futures_snapshot_requires_leverage_contract(self):
        write_strategy(self.strategy, True)
        write_config(self.config, "futures", "BTC/USDT:USDT")
        write_manifest(self.dataset, "futures")
        self.snapshot.mkdir(parents=True, exist_ok=True)
        (self.snapshot / "manifest.yaml").write_text('trading_mode: "futures"\nbtc_usdt_usdt_contract_size: 1.0\n', encoding="utf-8")
        result = validate_contract(self.strategy, "DemoStrategy", self.config, self.dataset, self.snapshot)
        self.assertFalse(result["ok"])
        self.assertIn("leverage-tier", " ".join(result["issues"]))


if __name__ == "__main__":
    unittest.main()
