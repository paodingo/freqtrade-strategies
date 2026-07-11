import sqlite3
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_stage3c1_data_plane as stage3c1
from profile_futures_market_regimes import build_profile
from research_data_guard import DataAccessError, check_data_access


class Stage3C1DataPlaneTest(unittest.TestCase):
    def test_split_is_chronological_with_embargo_and_fixture_quarantine(self):
        split = {key: stage3c1.ts(value) for key, value in stage3c1.SPLIT.items()}

        self.assertLess(split["development_end"], split["embargo_start"])
        self.assertLess(split["embargo_end"], split["validation_warmup_start"])
        self.assertLess(split["validation_warmup_start"], split["validation_evaluation_start"])
        self.assertLess(split["validation_evaluation_start"], split["validation_evaluation_end"])

        acceptance_start = stage3c1.ts("2026-03-29T00:00:00Z")
        acceptance_end = stage3c1.ts("2026-04-12T00:00:00Z")
        self.assertLessEqual(split["embargo_start"], acceptance_start)
        self.assertLessEqual(acceptance_end, split["embargo_end"])

        warmup_hours = (split["validation_evaluation_start"] - split["validation_warmup_start"]).total_seconds() / 3600
        self.assertGreaterEqual(warmup_hours, 200 * 4)

    def test_dataset_ids_do_not_reuse_acceptance_fixture_as_ranking_dataset(self):
        self.assertTrue(stage3c1.SOURCE_DATASET_ID.startswith("demo-btc-usdt-usdt-futures-acceptance-"))
        self.assertTrue(stage3c1.DEV_DATASET_ID.startswith("futures-dev-"))
        self.assertTrue(stage3c1.VAL_DATASET_ID.startswith("futures-validation-"))
        self.assertNotEqual(stage3c1.DEV_DATASET_ID, stage3c1.SOURCE_DATASET_ID)
        self.assertNotEqual(stage3c1.VAL_DATASET_ID, stage3c1.SOURCE_DATASET_ID)

    def test_validate_frame_detects_duplicates_missing_and_bad_ohlc(self):
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-03-01T00:00:00Z",
                        "2026-03-01T01:00:00Z",
                        "2026-03-01T01:00:00Z",
                        "2026-03-01T04:00:00Z",
                    ],
                    utc=True,
                ),
                "open": [10.0, 11.0, 12.0, 13.0],
                "high": [10.5, 11.5, 11.0, 13.5],
                "low": [9.5, 10.5, 12.5, 12.5],
                "close": [10.2, 11.2, 12.2, 13.2],
                "volume": [1.0, 1.0, 1.0, 1.0],
            }
        )

        result = stage3c1.validate_frame(frame, "1h", "futures")

        self.assertFalse(result["ok"])
        self.assertIn("duplicate_timestamps", result["issues"])
        self.assertIn("missing_or_irregular_candles", result["issues"])
        self.assertIn("invalid_ohlc", result["issues"])

    def test_funding_validation_allows_subsecond_exchange_timestamp_jitter(self):
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2026-03-01T00:00:00.005Z",
                        "2026-03-01T08:00:00.000Z",
                        "2026-03-01T16:00:00.007Z",
                    ],
                    utc=True,
                ),
                "open": [0.0, 0.0, 0.0],
                "high": [0.0, 0.0, 0.0],
                "low": [0.0, 0.0, 0.0],
                "close": [0.0001, 0.0001, 0.0001],
                "volume": [0.0, 0.0, 0.0],
            }
        )

        result = stage3c1.validate_frame(frame, "8h", "funding_rate")

        self.assertTrue(result["ok"])
        self.assertEqual(result["missing_intervals"], 0)

    def test_data_guard_role_and_layer_policy(self):
        dev = ROOT / "research/data/snapshots/futures-dev-btc-usdt-usdt-20260301-20260328-v1/manifest.yaml"
        val = ROOT / "research/data/snapshots/futures-validation-btc-usdt-usdt-20260503-20260628-v1/manifest.yaml"
        fixture = ROOT / "research/data/snapshots/demo-btc-usdt-usdt-futures-acceptance-20260329-20260412/manifest.yaml"

        self.assertEqual(check_data_access(ROOT, dev, "candidate_generator")["layer"], "development")
        self.assertEqual(check_data_access(ROOT, val, "validation_evaluator")["layer"], "validation")
        self.assertEqual(check_data_access(ROOT, fixture, "candidate_runner")["layer"], "acceptance_fixture")

        with self.assertRaises(DataAccessError) as val_error:
            check_data_access(ROOT, val, "candidate_generator")
        self.assertEqual(val_error.exception.reason_code, "validation_access_denied")

        with self.assertRaises(DataAccessError) as write_error:
            check_data_access(ROOT, dev, "candidate_generator", operation="write")
        self.assertEqual(write_error.exception.reason_code, "sealed_dataset_write_blocked")

    def test_data_guard_blocks_holdout_and_path_escape(self):
        with self.assertRaises(DataAccessError) as holdout_error:
            check_data_access(ROOT, "research/data/holdout/futures-secret/manifest.yaml", "validation_evaluator")
        self.assertEqual(holdout_error.exception.reason_code, "holdout_access_denied")

        with self.assertRaises(DataAccessError) as escape_error:
            check_data_access(ROOT, "../outside/manifest.yaml", "validation_evaluator")
        self.assertEqual(escape_error.exception.reason_code, "data_path_escape")

    def test_lineage_schema_contains_governance_tables(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(Path(tmp) / "lineage.sqlite")
            try:
                stage3c1.init_lineage(conn)
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                conn.close()

        self.assertIn("datasets", tables)
        self.assertIn("data_lineage_files", tables)
        self.assertIn("validation_access_events", tables)
        self.assertIn("contamination_events", tables)

    def test_market_profile_is_strategy_independent(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ohlcv = tmp_path / "ohlcv.feather"
            funding = tmp_path / "funding.feather"
            pd.DataFrame(
                {
                    "date": pd.date_range("2026-03-01", periods=24, freq="1h", tz="UTC"),
                    "open": [100.0] * 24,
                    "high": [101.0] * 24,
                    "low": [99.0] * 24,
                    "close": [100.0 + idx for idx in range(24)],
                    "volume": [10.0] * 24,
                }
            ).to_feather(ohlcv)
            pd.DataFrame(
                {
                    "date": pd.date_range("2026-03-01", periods=3, freq="8h", tz="UTC"),
                    "open": [0.0] * 3,
                    "high": [0.0] * 3,
                    "low": [0.0] * 3,
                    "close": [0.0001] * 3,
                    "volume": [0.0] * 3,
                }
            ).to_feather(funding)

            profile = build_profile(
                "unit-split",
                ohlcv,
                funding,
                {"development": {"start": "2026-03-01T00:00:00Z", "end": "2026-03-01T23:00:00Z"}},
            )

        self.assertTrue(profile["strategy_independent"])
        self.assertFalse(profile["uses_strategy_results"])
        self.assertEqual(profile["windows"]["development"]["rows"], 24)

    def test_policy_files_define_validation_budget_and_contamination_states(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            paths = stage3c1.write_policy_files(tmp_path)

            validation_policy = (tmp_path / paths["validation_access"]).read_text(encoding="utf-8")
            pollution_model = (tmp_path / paths["pollution_model"]).read_text(encoding="utf-8")
            usage_policy = (tmp_path / paths["usage_policy"]).read_text(encoding="utf-8")

        self.assertIn("max_evaluations_per_campaign: 1", validation_policy)
        self.assertIn("validation_contaminated", pollution_model)
        self.assertIn("champion_promotion", usage_policy)
        self.assertIn("prohibited_uses", usage_policy)


if __name__ == "__main__":
    unittest.main()
