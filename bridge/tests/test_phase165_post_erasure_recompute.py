"""Phase 165 — Post-Erasure Separation Ratio Recompute tests (WIF-024).

8 tests → Bridge 1934 → 1942.

WIF-024: When a device's biometric records are erased (GDPR Art.17), the stored
separation ratio becomes stale because the anonymised device can no longer contribute
feature vectors to the next run of analyze_interperson_separation.py.
Phase 165 adds an audit trail (post_erasure_ratio_log) so operators are alerted
when the ratio needs recomputing after a consent erasure.
"""

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from bridge.vapi_bridge.store import Store


def _make_store() -> Store:
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test165.db"), consent_ledger_enabled=True)


class TestPhase165PostErasureRecompute(unittest.TestCase):

    def test_1_schema_version_165(self):
        """schema_versions table contains phase 165 post_erasure_recompute entry."""
        s = _make_store()
        version = s.get_schema_version()
        self.assertGreaterEqual(version, 165)

    def test_2_get_post_erasure_recompute_status_empty(self):
        """get_post_erasure_recompute_status returns safe defaults on empty store."""
        s = _make_store()
        result = s.get_post_erasure_recompute_status()
        self.assertEqual(result["total_recomputes"],   0)
        self.assertEqual(result["pending_recomputes"], 0)
        self.assertFalse(result["recompute_needed"])
        self.assertIsNone(result["latest_recompute_ts"])
        self.assertIsNone(result["latest_ratio_before"])

    def test_3_anonymize_with_recompute_logs_entry(self):
        """anonymize_device_records(post_erasure_recompute=True) inserts to post_erasure_ratio_log.

        Even with no existing records for the device (count=0), the log entry is always
        written when post_erasure_recompute=True so operators are alerted.
        """
        s = _make_store()
        # No records to redact — count will be 0, but log entry must still be written
        count = s.anonymize_device_records("dev_165", post_erasure_recompute=True)
        self.assertEqual(count, 0)
        result = s.get_post_erasure_recompute_status(device_id="dev_165")
        self.assertEqual(result["total_recomputes"],   1)
        self.assertEqual(result["pending_recomputes"], 1)
        self.assertTrue(result["recompute_needed"])
        self.assertIsNotNone(result["latest_recompute_ts"])

    def test_4_anonymize_without_recompute_no_log(self):
        """anonymize_device_records(post_erasure_recompute=False) does NOT write to post_erasure_ratio_log."""
        s = _make_store()
        s.anonymize_device_records("dev_no_recompute", post_erasure_recompute=False)
        result = s.get_post_erasure_recompute_status()
        self.assertEqual(result["total_recomputes"],   0)
        self.assertEqual(result["pending_recomputes"], 0)
        self.assertFalse(result["recompute_needed"])

    def test_5_insert_post_erasure_log_roundtrip(self):
        """insert_post_erasure_recompute_log roundtrip: row stored and retrieved correctly."""
        s = _make_store()
        row_id = s.insert_post_erasure_recompute_log(
            device_id="dev_roundtrip",
            n_anonymized=3,
            ratio_before=1.261,
            ratio_after=None,
            triggered_by="test",
            consent_type="biometric",
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)
        result = s.get_post_erasure_recompute_status(device_id="dev_roundtrip")
        self.assertEqual(result["total_recomputes"],    1)
        self.assertEqual(result["latest_ratio_before"], 1.261)
        self.assertTrue(result["recompute_needed"])

    def test_6_endpoint_returns_7_keys(self):
        """GET /agent/post-erasure-recompute-status returns 7 required keys."""
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from bridge.vapi_bridge.operator_api import create_operator_app

        _s = _make_store()
        _cfg = MagicMock()
        _cfg.operator_api_key = "testkey165"
        _cfg.rate_limit_enabled = False
        _cfg.consent_ledger_enabled = True
        app = create_operator_app(_cfg, _s, None, None)
        client = TestClient(app)
        resp = client.get("/agent/post-erasure-recompute-status?api_key=testkey165")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in (
            "consent_ledger_enabled", "total_recomputes", "pending_recomputes",
            "latest_recompute_ts", "latest_ratio_before", "recompute_needed", "timestamp",
        ):
            self.assertIn(key, data, f"Missing key: {key}")

    def test_7_separation_defensibility_status_has_post_erasure_field(self):
        """GET /agent/separation-defensibility-status includes post_erasure_recomputed_at."""
        from unittest.mock import MagicMock
        from fastapi.testclient import TestClient
        from bridge.vapi_bridge.operator_api import create_operator_app

        _s = _make_store()
        _cfg = MagicMock()
        _cfg.operator_api_key = "testkey165b"
        _cfg.rate_limit_enabled = False
        _cfg.min_touchpad_sessions_per_player = 10
        app = create_operator_app(_cfg, _s, None, None)
        client = TestClient(app)
        resp = client.get(
            "/agent/separation-defensibility-status?api_key=testkey165b"
            "&session_type=touchpad_corners"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("post_erasure_recomputed_at", data)

    def test_8_tool_122_returns_dict_with_required_keys(self):
        """Tool #122 trigger_post_erasure_recompute returns a dict with required keys."""
        from unittest.mock import MagicMock
        from bridge.vapi_bridge.bridge_agent import BridgeAgent

        _s = _make_store()
        _cfg = MagicMock()
        _cfg.consent_ledger_enabled = True
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = _s
        agent._cfg   = _cfg
        agent._chain = None

        result = agent._execute_tool("trigger_post_erasure_recompute", {"dry_run": True})
        self.assertIsInstance(result, dict)
        for key in (
            "consent_ledger_enabled", "total_recomputes", "pending_recomputes",
            "recompute_needed", "triggered", "timestamp",
        ):
            self.assertIn(key, result, f"Missing key: {key}")
        # dry_run=True should not trigger erasure
        self.assertFalse(result["triggered"])


if __name__ == "__main__":
    unittest.main()
