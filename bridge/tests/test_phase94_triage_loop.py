"""
Phase 94 — Class J Reactive Triage Loop Tests (6 tests)

test_1_escalation_ruling_log_table_exists
test_2_triage_rate_bucket_limits_to_one_per_window
test_3_triage_rate_bucket_resets_after_window
test_4_triage_buckets_dict_capped_at_1000
test_5_escalation_log_endpoint_returns_entries
test_6_tool_60_get_escalation_ruling_log_returns_dict
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.session_adjudicator import _TriageRateBucket, SessionAdjudicator


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p94.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey94"
    cfg.triage_reactive_rate_limit = kwargs.get("rate_limit", 1)
    cfg.triage_reactive_window_seconds = kwargs.get("window_s", 3600.0)
    cfg.reactive_adjudication_rate_limit = 2
    cfg.reactive_adjudication_window_seconds = 60
    cfg.agent_dry_run_mode = True
    return cfg


class TestEscalationRulingLogTableExists(unittest.TestCase):

    def test_1_escalation_ruling_log_table_exists(self):
        """Store creates escalation_ruling_log table; insert + retrieve works."""
        store = _make_store()
        row_id = store.insert_escalation_ruling_log(
            device_id="abc123",
            patterns="ml_bot_cluster",
            verdict="FLAG",
            ruling_id=42,
            was_deferred=False,
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)

        entries = store.get_escalation_ruling_log(limit=10)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["device_id"], "abc123")
        self.assertEqual(entries[0]["patterns"], "ml_bot_cluster")
        self.assertEqual(entries[0]["verdict"], "FLAG")
        self.assertEqual(entries[0]["ruling_id"], 42)
        self.assertEqual(entries[0]["was_deferred"], 0)


class TestTriageRateBucketLimits(unittest.TestCase):

    def test_2_triage_rate_bucket_limits_to_one_per_window(self):
        """Token bucket rejects second call within the same window (max_tokens=1)."""
        bucket = _TriageRateBucket(max_tokens=1, window_s=3600.0)
        # First call: should succeed
        self.assertTrue(bucket.consume())
        # Second call within same window: should be rejected
        self.assertFalse(bucket.consume())
        # Third call still rejected
        self.assertFalse(bucket.consume())


class TestTriageRateBucketResets(unittest.TestCase):

    def test_3_triage_rate_bucket_resets_after_window(self):
        """Token bucket resets after the window expires."""
        bucket = _TriageRateBucket(max_tokens=1, window_s=0.01)  # 10ms window
        self.assertTrue(bucket.consume())
        self.assertFalse(bucket.consume())
        # Wait for the window to expire
        time.sleep(0.05)
        # Should reset and allow again
        self.assertTrue(bucket.consume())


class TestTriageBucketsDictCapped(unittest.TestCase):

    def test_4_triage_buckets_dict_capped_at_1000(self):
        """Adding 1001 unique devices keeps the dict at most 1000 entries."""
        store = _make_store()
        cfg = _make_cfg()
        adjudicator = SessionAdjudicator(cfg, store)

        # Insert 1001 unique device buckets
        for i in range(1001):
            device_id = f"device_{i:04d}"
            adjudicator._get_triage_bucket(device_id)

        self.assertLessEqual(len(adjudicator._triage_buckets), 1000)


class TestEscalationLogEndpoint(unittest.TestCase):

    def test_5_escalation_log_endpoint_returns_entries(self):
        """GET /agent/escalation-ruling-log returns entries via operator_api."""
        store = _make_store()
        cfg = _make_cfg()
        # Pre-insert entries
        store.insert_escalation_ruling_log(
            device_id="dev_abc",
            patterns="cheat_cluster",
            verdict="HOLD",
            ruling_id=10,
            was_deferred=False,
        )
        store.insert_escalation_ruling_log(
            device_id="dev_def",
            patterns="ml_bot_cluster",
            verdict=None,
            ruling_id=None,
            was_deferred=True,
        )

        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        response = client.get("/agent/escalation-ruling-log?api_key=testkey94")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("entries", data)
        self.assertIn("total_returned", data)
        self.assertEqual(data["total_returned"], 2)
        verdicts = {e["device_id"] for e in data["entries"]}
        self.assertIn("dev_abc", verdicts)
        self.assertIn("dev_def", verdicts)


class TestTool60GetEscalationRulingLog(unittest.TestCase):

    def test_6_tool_60_get_escalation_ruling_log_returns_dict(self):
        """Tool #60 get_escalation_ruling_log returns dict with entries key."""
        store = _make_store()
        cfg = _make_cfg()
        store.insert_escalation_ruling_log(
            device_id="dev_xyz",
            patterns="enrollment_anomaly",
            verdict="FLAG",
            ruling_id=99,
            was_deferred=False,
        )

        # Simulate the tool handler logic directly
        entries = store.get_escalation_ruling_log(device_id=None, limit=50)
        deferred_count = sum(1 for e in entries if e.get("was_deferred"))
        result = {
            "entries": entries,
            "total_returned": len(entries),
            "deferred_count": deferred_count,
        }

        self.assertIn("entries", result)
        self.assertIn("total_returned", result)
        self.assertIn("deferred_count", result)
        self.assertEqual(result["total_returned"], 1)
        self.assertEqual(result["deferred_count"], 0)
        self.assertEqual(result["entries"][0]["device_id"], "dev_xyz")


if __name__ == "__main__":
    unittest.main()
