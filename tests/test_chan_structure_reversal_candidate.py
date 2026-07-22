import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_chan_structure_readiness as readiness  # noqa: E402
import run_chan_structure_reversal_campaign as campaign_runner  # noqa: E402


CANDIDATE_PATH = (
    ROOT
    / "research/candidates/chan-structure-reversal-v1/RegimeAwareChanStructureLongV1.py"
)
SPEC = importlib.util.spec_from_file_location("RegimeAwareChanStructureLongV1", CANDIDATE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
Candidate = MODULE.RegimeAwareChanStructureLongV1
RouterReference = MODULE.RegimeAwareRouterEquivalentV1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_long_structure() -> pd.DataFrame:
    closes = [10, 12, 14, 11, 8, 10, 12, 16, 14, 13, 14, 16, 17]
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.2 for value in closes],
            "low": [value - 0.2 for value in closes],
            "close": closes,
            "volume": [100.0] * len(closes),
        }
    )


class ChanStructureReversalCandidateTests(unittest.TestCase):
    def test_candidate_mask_exactly_reuses_frozen_readiness_semantics(self):
        frame = synthetic_long_structure()
        expected = pd.Series(False, index=frame.index)
        sequences = readiness.structure_sequences(frame, readiness.POLICY)
        for event in sequences["long_unique_signals"]:
            expected.iloc[event["signal_confirmation_index"]] = True

        actual = Candidate.causal_structure_long_mask(frame)

        pd.testing.assert_series_equal(actual, expected)
        self.assertFalse(actual.iloc[4])
        self.assertTrue(actual.iloc[11])

    def test_entry_branch_adds_only_novel_confirmed_long_rows(self):
        frame = pd.DataFrame(
            {
                "chan_structure_long_signal": [1, 1, 1, 0],
                "regime_4h": ["trending", "ranging", "", "trending"],
                "volume": [100.0, 100.0, 100.0, 100.0],
                "enter_long": [0, 1, 0, 0],
                "enter_short": [0, 1, 1, 0],
                "enter_tag": ["", "existing_long", "existing_short", ""],
            }
        )
        candidate = Candidate.__new__(Candidate)

        with patch.object(RouterReference, "populate_entry_trend", return_value=frame.copy()):
            result = candidate.populate_entry_trend(frame.copy(), {"pair": "BTC/USDT:USDT"})

        self.assertEqual(result["enter_long"].tolist(), [1, 1, 0, 0])
        self.assertEqual(result["enter_short"].tolist(), [0, 1, 1, 0])
        self.assertEqual(result.loc[0, "enter_tag"], "chan_structure_long_trending")
        self.assertEqual(result.loc[1, "enter_tag"], "existing_long")
        self.assertEqual(result["research_chan_structure_long_pre_gate"].tolist(), [1, 1, 1, 0])
        self.assertEqual(result["research_chan_structure_long_novel"].tolist(), [1, 0, 0, 0])

    def test_candidate_does_not_override_exit_or_risk_methods(self):
        candidate_methods = Candidate.__dict__

        for name in (
            "populate_exit_trend",
            "custom_exit",
            "custom_stoploss",
            "custom_stake_amount",
            "leverage",
            "confirm_trade_entry",
            "confirm_trade_exit",
        ):
            self.assertNotIn(name, candidate_methods)

    def test_manifest_binds_single_candidate_and_frozen_hashes(self):
        manifest_path = ROOT / "research/candidates/chan-structure-reversal-v1/candidate-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["candidate_count"], 1)
        self.assertEqual(manifest["class_name"], Candidate.__name__)
        self.assertEqual(manifest["source_sha256"], sha256_file(CANDIDATE_PATH))
        self.assertEqual(
            manifest["formal_strategy_sha256"],
            sha256_file(ROOT / "strategies/RegimeAwareV6.py"),
        )
        self.assertEqual(
            manifest["readiness_semantics_sha256"],
            sha256_file(ROOT / "scripts/analyze_chan_structure_readiness.py"),
        )
        self.assertEqual(manifest["new_signal_groups"], 1)
        self.assertEqual(manifest["new_sides"], ["long"])

    def test_execution_approval_records_direct_human_continuation(self):
        approval = json.loads(
            (ROOT / "research/governance/approvals/chan-structure-reversal-v1-execution-approval.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertTrue(approval["execution_authorized"])
        self.assertEqual(approval["approver_type"], "human_user")
        self.assertEqual(approval["approval_source"], "user_message_continue")
        self.assertEqual(approval["budget"]["max_candidates"], 1)
        self.assertEqual(approval["budget"]["max_backtest_calls"], 8)
        self.assertEqual(approval["data_access"]["validation"], "forbidden")
        self.assertEqual(approval["data_access"]["holdout"], "forbidden")

    def test_compiled_campaign_fingerprint_and_authority_are_bound(self):
        campaign = campaign_runner.load_json(campaign_runner.CAMPAIGN_PATH)
        approval = campaign_runner.load_json(campaign_runner.APPROVAL_PATH)

        self.assertEqual(
            campaign_runner.campaign_fingerprint(campaign),
            campaign["campaign_fingerprint"],
        )
        self.assertEqual(approval["compiled_campaign_fingerprint"], campaign["campaign_fingerprint"])
        self.assertTrue(all(campaign_runner.validate_authority().values()))

    def test_execution_matrix_is_exactly_eight_development_calls(self):
        self.assertEqual(len(campaign_runner.RUN_ORDER), 8)
        self.assertEqual(len(set(campaign_runner.RUN_ORDER)), 8)
        for pair_key, role, repetition in campaign_runner.RUN_ORDER:
            spec = campaign_runner.build_spec(pair_key, role)["fixed_backtest"]
            self.assertEqual(spec["timeframe"], "1h")
            self.assertEqual(spec["timerange"], "20240609-20240811")
            self.assertNotIn("validation", spec["dataset_id"])
            self.assertIn(repetition, ("A", "B"))

    def test_gate_rejects_material_cross_pair_degradation(self):
        def role(total_return, profit_factor, drawdown, structure_trades=0):
            return {
                "core": {
                    "total_trades": 25,
                    "long_trade_count": 15,
                    "short_trade_count": 10,
                    "total_profit": total_return * 1000,
                    "total_profit_pct": total_return,
                    "profit_factor": profit_factor,
                    "winrate": 0.5,
                    "max_drawdown_account": drawdown,
                    "funding_fees": 0.0,
                },
                "structure_trade_count": structure_trades,
            }

        pair_results = {
            "btc": {
                "baseline": role(0.02, 1.1, 0.05),
                "candidate": role(0.04, 1.3, 0.04, 8),
            },
            "eth": {
                "baseline": role(0.01, 1.1, 0.05),
                "candidate": role(-0.02, 0.8, 0.09, 7),
            },
        }
        for result in pair_results.values():
            result["candidate_minus_baseline"] = campaign_runner.metric_delta(
                result["candidate"], result["baseline"]
            )

        classification, checks = campaign_runner.classify(pair_results, True, True)

        self.assertEqual(classification, "development_rejected_material_degradation")
        self.assertFalse(checks["eth_descriptive_no_material_degradation"])

    def test_network_contract_allows_only_unblocked_loopback_ipc(self):
        allowed = [{"host": "127.0.0.1", "port": 1234, "blocked": False, "loopback": True}]
        blocked = [{"host": "127.0.0.1", "port": 1234, "blocked": True, "loopback": True}]
        external = [{"host": "example.com", "port": 443, "blocked": True, "loopback": False}]

        self.assertEqual(campaign_runner.forbidden_network_attempts(allowed), [])
        self.assertEqual(campaign_runner.forbidden_network_attempts(blocked), blocked)
        self.assertEqual(campaign_runner.forbidden_network_attempts(external), external)

    def test_completed_report_stays_within_authorized_execution_budget(self):
        report_path = ROOT / "reports/audits/chan-structure-reversal-v1/final-report.json"
        if not report_path.is_file():
            self.skipTest("campaign has not been executed")
        report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(report["budget_used"]["backtest_calls"], 8)
        self.assertEqual(report["budget_used"]["validation_accesses"], 0)
        self.assertEqual(report["budget_used"]["holdout_accesses"], 0)
        self.assertTrue(report["reproducible"])
        if report.get("finalization_mode") == "existing_completed_runs_no_new_backtests":
            self.assertEqual(report["budget_used"]["report_only_backtest_calls"], 0)
            self.assertEqual(report["budget_used"]["forbidden_network_attempt_count"], 0)

    def test_guard_surface_is_exact_without_candidate_or_report_prefixes(self):
        guard = (ROOT / "scripts/guard_harness_diff.js").read_text(encoding="utf-8")
        exact_paths = (
            "research/candidates/chan-structure-reversal-v1/RegimeAwareChanStructureLongV1.py",
            "research/candidates/chan-structure-reversal-v1/candidate-manifest.json",
            "scripts/run_chan_structure_reversal_campaign.py",
            "tests/test_chan_structure_reversal_candidate.py",
            "research/analysis/chan-structure-reversal-v1/development-comparison.json",
            "reports/audits/chan-structure-reversal-v1/final-report.json",
            "reports/audits/chan-structure-reversal-v1/final-report.md",
        )
        for path in exact_paths:
            self.assertIn(f'{{ path: "{path}" }}', guard)
        self.assertNotIn('{ prefix: "research/candidates/chan-structure-reversal-v1/" }', guard)
        self.assertNotIn('{ prefix: "research/analysis/chan-structure-reversal-v1/" }', guard)
        self.assertNotIn('{ prefix: "reports/audits/chan-structure-reversal-v1/" }', guard)


if __name__ == "__main__":
    unittest.main()
