import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

STRATEGY_PATH = Path(__file__).resolve().parents[1] / "strategies"
sys.path.insert(0, str(STRATEGY_PATH))

from trade_supervisor_filter import apply_trade_supervisor_filter, load_trade_supervisor_decisions


class TradeSupervisorFilterTest(unittest.TestCase):
    def test_loads_v66_decision_from_monitor_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "monitor.sqlite"
            _write_supervisor_decision(
                db_path,
                sampled_at="2026-06-10T23:40:00.000Z",
                payload={
                    "mode": "defensive",
                    "systemAction": "observe",
                    "windowType": "chop",
                    "allowedPlaybook": "flat",
                    "actions": {
                        "v66": {
                            "allowFreshEntries": False,
                            "recommendedAction": "block_new_entries",
                            "allowedTags": [],
                            "blockedTags": ["ranging_long", "ranging_short", "trending_long", "trending_short"],
                        },
                    },
                },
            )

            samples = load_trade_supervisor_decisions(db_path)

        self.assertEqual(len(samples), 1)
        self.assertEqual(samples.loc[0, "mode"], "defensive")
        self.assertEqual(samples.loc[0, "v66_action"], "block_new_entries")
        self.assertFalse(samples.loc[0, "v66_allow_fresh_entries"])
        self.assertEqual(samples.loc[0, "v66_allowed_tags"], "")

    def test_blocks_v66_new_entries_when_supervisor_says_observe(self):
        dataframe = pd.DataFrame([
            _entry_row(enter_long=1, enter_short=0, enter_tag="v66_ranging_long_edge"),
            _entry_row(enter_long=0, enter_short=1, enter_tag="trending_short"),
        ])
        samples = _samples([{
            "sampled_at": "2026-06-10T23:44:00.000Z",
            "v66_allow_fresh_entries": False,
            "v66_action": "block_new_entries",
            "v66_allowed_tags": "",
        }])

        result = apply_trade_supervisor_filter(dataframe, samples, mode="latest")

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[1, "enter_short"], 0)
        self.assertTrue(result["trade_supervisor_block_entry"].all())
        self.assertEqual(result.loc[0, "trade_supervisor_action"], "block_new_entries")

    def test_routes_v66_to_trend_short_only(self):
        dataframe = pd.DataFrame([
            _entry_row(enter_long=1, enter_short=0, enter_tag="trending_long"),
            _entry_row(enter_long=0, enter_short=1, enter_tag="trending_short"),
            _entry_row(enter_long=0, enter_short=1, enter_tag="v66_ranging_short_edge"),
        ])
        samples = _samples([{
            "sampled_at": "2026-06-10T23:44:00.000Z",
            "v66_allow_fresh_entries": True,
            "v66_action": "allow_trend_short",
            "v66_allowed_tags": "trending_short",
        }])

        result = apply_trade_supervisor_filter(dataframe, samples, mode="latest")

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertEqual(result.loc[1, "enter_short"], 1)
        self.assertEqual(result.loc[2, "enter_short"], 0)

    def test_routes_v66_to_range_edges_only(self):
        dataframe = pd.DataFrame([
            _entry_row(enter_long=1, enter_short=0, enter_tag="v66_ranging_long_edge"),
            _entry_row(enter_long=0, enter_short=1, enter_tag="v66_ranging_short_edge"),
            _entry_row(enter_long=0, enter_short=1, enter_tag="trending_short"),
        ])
        samples = _samples([{
            "sampled_at": "2026-06-10T23:44:00.000Z",
            "v66_allow_fresh_entries": True,
            "v66_action": "allow_range_edge",
            "v66_allowed_tags": "ranging_long,ranging_short",
        }])

        result = apply_trade_supervisor_filter(dataframe, samples, mode="latest")

        self.assertEqual(result.loc[0, "enter_long"], 1)
        self.assertEqual(result.loc[1, "enter_short"], 1)
        self.assertEqual(result.loc[2, "enter_short"], 0)

    def test_fail_closed_blocks_entries_when_supervisor_sample_is_missing(self):
        dataframe = pd.DataFrame([
            _entry_row(enter_long=1, enter_short=0, enter_tag="v66_ranging_long_edge"),
        ])

        result = apply_trade_supervisor_filter(dataframe, pd.DataFrame(), mode="latest", fail_closed=True)

        self.assertEqual(result.loc[0, "enter_long"], 0)
        self.assertTrue(result.loc[0, "trade_supervisor_block_entry"])
        self.assertEqual(result.loc[0, "trade_supervisor_action"], "missing_supervisor")


def _entry_row(*, enter_long, enter_short, enter_tag):
    return {
        "date": pd.Timestamp("2026-06-10T23:45:00Z"),
        "enter_long": enter_long,
        "enter_short": enter_short,
        "enter_tag": enter_tag,
    }


def _samples(records):
    return pd.DataFrame.from_records(records)


def _write_supervisor_decision(db_path, *, sampled_at, payload):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE trade_supervisor_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sampled_at TEXT NOT NULL,
                generated_at TEXT,
                mode TEXT,
                system_action TEXT,
                window_type TEXT,
                allowed_playbook TEXT,
                risk_budget_pct REAL,
                payload TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO trade_supervisor_decisions (
                sampled_at, generated_at, mode, system_action, window_type,
                allowed_playbook, risk_budget_pct, payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sampled_at,
                sampled_at,
                payload["mode"],
                payload["systemAction"],
                payload["windowType"],
                payload["allowedPlaybook"],
                25,
                json.dumps(payload),
            ),
        )


if __name__ == "__main__":
    unittest.main()
