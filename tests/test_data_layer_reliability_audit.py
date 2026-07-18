import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import audit_data_layer_reliability as audit_module
from research_director_common import load_document


AUDIT_PATH = (
    ROOT
    / "research/analysis/ranging-short-router-unanimous-expansion-candidate-preparation-v1"
    / "data-layer-reliability-audit.json"
)


class DataLayerReliabilityAuditTest(unittest.TestCase):
    def test_current_audit_separates_source_from_local_pipeline(self):
        audit = load_document(AUDIT_PATH)
        self.assertEqual(audit["overall_verdict"], "not_reliable_for_current_strategy_decisioning")
        self.assertTrue(all(item["ok"] for item in audit["public_endpoint_probe"].values()))
        self.assertEqual(
            audit["verdicts"]["sealed_historical_research_integrity"]["grade"],
            "reliable",
        )
        self.assertEqual(audit["verdicts"]["dashboard_live_fetch_path"]["grade"], "unreliable")
        self.assertEqual(audit["verdicts"]["local_persistence_freshness"]["grade"], "unreliable")
        self.assertEqual(audit["verdicts"]["feature_completeness"]["grade"], "partial")

    def test_node_proxy_root_cause_is_reproduced_without_secret_material(self):
        audit = load_document(AUDIT_PATH)
        diagnosis = audit["node_proxy_diagnosis"]
        self.assertTrue(diagnosis["http_or_https_proxy_present"])
        self.assertFalse(diagnosis["default_node_fetch"]["ok"])
        self.assertTrue(diagnosis["node_fetch_with_env_proxy"]["ok"])
        self.assertTrue(diagnosis["root_cause_confirmed"])
        serialized = json.dumps(audit)
        self.assertNotIn("proxy_url", serialized)
        self.assertFalse(audit["security"]["credentials_read"])
        self.assertFalse(audit["security"]["private_endpoints_called"])

    def test_runtime_and_simulated_performance_are_stale_or_absent(self):
        audit = load_document(AUDIT_PATH)
        runtime = audit["runtime"]
        self.assertFalse(runtime["dashboard_port_8090_listening"])
        self.assertFalse(runtime["freqtrade_port_8122_listening"])
        self.assertTrue(runtime["monitor_store"]["stale"])
        self.assertEqual(runtime["local_market_history"]["user_data_market_file_count"], 0)
        self.assertFalse(runtime["trade_store"]["current_simulated_pnl_available"])

    def test_current_history_feature_coverage_is_fail_closed(self):
        audit = load_document(AUDIT_PATH)
        current = audit["feature_coverage"]["current_on_demand"]
        self.assertTrue(all(current.values()))
        historical = audit["feature_coverage"]["continuous_local_history"]
        self.assertFalse(any(historical.values()))
        self.assertGreaterEqual(len(audit["remediation_gates"]), 5)

    def test_epoch_conversion_uses_utc(self):
        self.assertEqual(audit_module.epoch_ms_iso(0), None)
        self.assertEqual(audit_module.epoch_ms_iso(1_000), "1970-01-01T00:00:01Z")


if __name__ == "__main__":
    unittest.main()
