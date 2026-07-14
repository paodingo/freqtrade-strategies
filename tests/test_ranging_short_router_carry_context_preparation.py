from __future__ import annotations

import importlib
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

class RouterCarryContextContractTest(unittest.TestCase):
    def test_contract_freezes_one_runtime_observable_context(self):
        spec = importlib.util.find_spec("ranging_short_router_context")
        self.assertIsNotNone(spec, "router context contract module must exist")
        router_context = importlib.import_module("ranging_short_router_context")
        contract = router_context.build_context_contract(ROOT)

        self.assertEqual(
            contract["context_id"],
            "ranging_state_without_current_range_signal",
        )
        self.assertEqual(contract["context_count"], 1)
        self.assertEqual(
            contract["output_regime"],
            {"column": "regime_4h", "operator": "eq", "value": "ranging"},
        )
        self.assertEqual(
            contract["current_raw_ranging_signal"],
            {
                "all": [
                    {"column": "adx_4h", "operator": "lt", "value": 20},
                    {
                        "any": [
                            {
                                "left": "bb_width_4h",
                                "operator": "lte",
                                "right": "bb_width_mean_4h",
                            },
                            {
                                "left": "atr_4h",
                                "operator": "lte",
                                "right": "atr_mean_4h",
                            },
                        ]
                    },
                ]
            },
        )
        self.assertEqual(
            contract["context_expression"],
            {
                "all": [
                    contract["output_regime"],
                    {"not": contract["current_raw_ranging_signal"]},
                ]
            },
        )
        self.assertEqual(
            contract["evaluation_preconditions"],
            ["bb_width_mean_4h > 0", "atr_mean_4h > 0"],
        )
        self.assertFalse(contract["threshold_search_authorized"])
        self.assertFalse(contract["time_slice_used_as_regime_label"])


if __name__ == "__main__":
    unittest.main()
