import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from exchange_endpoint_doctor import (  # noqa: E402
    EndpointPolicyError,
    GuardedRedirectHandler,
    classify_http_status,
    normalize_base_url,
    redact_proxy,
    resolve_proxy,
    run_doctor,
)


class ExchangeEndpointDoctorTest(unittest.TestCase):
    def test_official_allowlist_accepts_data_api(self):
        self.assertEqual(normalize_base_url("https://data-api.binance.vision"), "https://data-api.binance.vision")

    def test_arbitrary_host_rejected(self):
        with self.assertRaises(EndpointPolicyError):
            normalize_base_url("https://example.com")

    def test_localhost_rejected(self):
        with self.assertRaises(EndpointPolicyError):
            normalize_base_url("https://localhost")

    def test_private_ip_rejected(self):
        with self.assertRaises(EndpointPolicyError):
            normalize_base_url("https://192.168.1.10")

    def test_redirect_to_non_allowlist_rejected(self):
        handler = GuardedRedirectHandler()
        with self.assertRaises(EndpointPolicyError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://example.com/api/v3/exchangeInfo")

    def test_http_status_classification(self):
        self.assertEqual(classify_http_status(403), "endpoint_http_403")
        self.assertEqual(classify_http_status(418), "endpoint_http_418")
        self.assertEqual(classify_http_status(429), "endpoint_http_429")
        self.assertEqual(classify_http_status(500), "endpoint_unexpected_status")

    def test_endpoint_fallback_selects_first_success(self):
        fail = {"base_url": "https://api1.binance.com", "ok": False, "reason_code": "endpoint_connect_timeout"}
        success = {"base_url": "https://api2.binance.com", "ok": True, "reason_code": "ok"}
        with mock.patch("exchange_endpoint_doctor.diagnose_endpoint", side_effect=[fail, fail, fail, success]):
            report = run_doctor(base_urls=["https://api1.binance.com", "https://api2.binance.com"], connect_timeout=0.1, request_timeout=0.1, allow_proxy_sources=False)
        self.assertEqual(report["selected_base_url"], "https://api2.binance.com")
        self.assertEqual(len(report["endpoints"][0]["attempts"]), 3)

    def test_timeout_retries_stop_after_success(self):
        timeout = {"base_url": "https://api1.binance.com", "ok": False, "reason_code": "endpoint_read_timeout"}
        success = {"base_url": "https://api1.binance.com", "ok": True, "reason_code": "ok"}
        with mock.patch("exchange_endpoint_doctor.diagnose_endpoint", side_effect=[timeout, success]):
            report = run_doctor(base_urls=["https://api1.binance.com"], connect_timeout=0.1, request_timeout=0.1, allow_proxy_sources=False)
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["endpoints"][0]["attempts"]), 2)

    def test_proxy_types_are_mutually_exclusive(self):
        with mock.patch.dict(os.environ, {"RESEARCH_BINANCE_HTTPS_PROXY": "https://proxy.example:443", "RESEARCH_BINANCE_HTTP_PROXY": "http://proxy.example:8080"}, clear=False):
            with self.assertRaises(EndpointPolicyError):
                resolve_proxy(None)

    def test_proxy_redaction(self):
        redacted = redact_proxy("https://user:pass@proxy.example:8443")
        self.assertEqual(redacted["scheme"], "https")
        self.assertEqual(redacted["host"], "proxy.example")
        self.assertEqual(redacted["port"], 8443)
        self.assertTrue(redacted["has_auth"])
        self.assertNotIn("pass", str(redacted))


if __name__ == "__main__":
    unittest.main()
