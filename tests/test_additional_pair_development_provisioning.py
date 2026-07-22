import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import provision_additional_pair_development_data as module  # noqa: E402
from build_stage3c2p_provisioning import validate_public_archive_url  # noqa: E402


class AdditionalPairDevelopmentProvisioningTests(unittest.TestCase):
    def test_scope_is_exactly_human_approved_pairs_and_development_only(self):
        self.assertEqual(
            [item.pair for item in module.PAIR_SCOPES],
            ["BNB/USDT:USDT", "XRP/USDT:USDT"],
        )
        self.assertNotIn("validation", module.STAGING_ROOT.as_posix().lower())
        self.assertNotIn("holdout", module.STAGING_ROOT.as_posix().lower())

    def test_all_planned_urls_are_public_usdm_archives(self):
        rows = module.planned_archives()
        self.assertEqual(len(rows), 2 * 4 * 8)
        for pair, _stream, _month, url in rows:
            self.assertTrue(validate_public_archive_url(url)["allowed"])
            self.assertTrue(url.startswith(module.ARCHIVE_ROOT + "/"))
            self.assertIn(f"/{pair.symbol}/", url)
            self.assertNotIn("?", url)

    def test_exact_complete_window_passes_and_gap_fails(self):
        stream = module.STREAM_SCOPES[0]
        dates = pd.date_range(module.WINDOW_START, stream.end, freq="1h")
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 1.0,
            }
        )
        window, check = module.validate_window(frame, stream)
        self.assertTrue(check["ok"])
        self.assertEqual(len(window), 5800)
        _, gap_check = module.validate_window(frame.drop(index=100), stream)
        self.assertFalse(gap_check["ok"])
        self.assertEqual(gap_check["missing_intervals"], 1)


if __name__ == "__main__":
    unittest.main()
