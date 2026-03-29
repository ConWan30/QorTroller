"""
Phase 119 — Override Lifecycle Management: TTL + Use-Count Auto-Expiry (9 tests)

W1: stale permanent overrides undermine epoch window security — cold-start grace
    periods never expire, creating persistent bypasses for potentially compromised devices.
W2: max_uses auto-graduation — once a device proves N successful Gate-5 checks,
    override self-deletes, restoring standard fleet policy automatically.

Infrastructure-first: max_uses=None + expires_at=None default → infinite/permanent →
zero behavior change to existing Phase 118 overrides.
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[2]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from bridge.vapi_bridge.store import Store  # noqa: E402


def _make_store() -> Store:
    tmp = tempfile.mkdtemp()
    return Store(f"{tmp}/test_phase119.db")


class TestPhase119OverrideLifecycle(unittest.TestCase):

    def test_1_schema_version_119(self):
        """schema_versions has (119, 'epoch_override_lifecycle') after store init."""
        store = _make_store()
        with store._conn() as conn:
            row = conn.execute(
                "SELECT migration_name FROM schema_versions WHERE phase = 119"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "epoch_override_lifecycle")

    def test_2_new_columns_exist(self):
        """per_device_epoch_overrides table has max_uses, use_count, expires_at columns."""
        store = _make_store()
        with store._conn() as conn:
            row = conn.execute(
                "SELECT max_uses, use_count, expires_at FROM per_device_epoch_overrides LIMIT 0"
            ).fetchone()
        # fetchone returns None on empty; the query succeeding proves columns exist
        self.assertIsNone(row)

    def test_3_insert_with_max_uses_and_retrieve(self):
        """insert_device_epoch_override with max_uses=3; get_override_lifecycle_status returns it."""
        store = _make_store()
        store.insert_device_epoch_override("dev_a", 86400.0, reason="cold start", max_uses=3)
        overrides = store.get_override_lifecycle_status()
        self.assertEqual(len(overrides), 1)
        o = overrides[0]
        self.assertEqual(o["device_id"], "dev_a")
        self.assertEqual(o["max_uses"], 3)
        self.assertEqual(o["use_count"], 0)
        self.assertIsNone(o["expires_at"])

    def test_4_increment_use_count_no_expiry(self):
        """increment_override_use_count increments use_count without deleting when below max_uses."""
        store = _make_store()
        store.insert_device_epoch_override("dev_b", 172800.0, max_uses=5)
        consumed = store.increment_override_use_count("dev_b")
        self.assertFalse(consumed)
        overrides = store.get_override_lifecycle_status()
        self.assertEqual(overrides[0]["use_count"], 1)
        # Override still exists
        val = store.get_device_epoch_override("dev_b")
        self.assertAlmostEqual(val, 172800.0)

    def test_5_increment_use_count_to_max_deletes_override(self):
        """increment_override_use_count auto-deletes override when use_count reaches max_uses."""
        store = _make_store()
        store.insert_device_epoch_override("dev_c", 259200.0, max_uses=3)
        # Two increments — not yet consumed
        store.increment_override_use_count("dev_c")
        store.increment_override_use_count("dev_c")
        val_mid = store.get_device_epoch_override("dev_c")
        self.assertIsNotNone(val_mid)  # still exists after 2
        # Third increment — consumed
        consumed = store.increment_override_use_count("dev_c")
        self.assertTrue(consumed)
        val_gone = store.get_device_epoch_override("dev_c")
        self.assertIsNone(val_gone)

    def test_6_delete_device_epoch_override(self):
        """delete_device_epoch_override removes override; subsequent get returns None."""
        store = _make_store()
        store.insert_device_epoch_override("dev_d", 3600.0)
        revoked = store.delete_device_epoch_override("dev_d")
        self.assertTrue(revoked)
        val = store.get_device_epoch_override("dev_d")
        self.assertIsNone(val)
        # Second delete returns False
        revoked2 = store.delete_device_epoch_override("dev_d")
        self.assertFalse(revoked2)

    def test_7_endpoint_override_status_returns_expected_keys(self):
        """GET /agent/epoch-window-override-status returns 200 with all 5 required keys."""
        from bridge.vapi_bridge.operator_api import create_operator_app
        from fastapi.testclient import TestClient

        cfg = MagicMock()
        cfg.operator_api_key = "key119a"
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0
        cfg.rate_limit_per_minute = 60

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/op119a.db")
        store.insert_device_epoch_override("dev_x", 7200.0, max_uses=5)

        app = create_operator_app(cfg=cfg, store=store, chain=MagicMock(), bus=MagicMock())
        client = TestClient(app)
        resp = client.get("/agent/epoch-window-override-status?api_key=key119a")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("override_count", "overrides_with_max_uses", "overrides",
                    "epoch_window_enabled", "timestamp"):
            self.assertIn(key, body)
        self.assertEqual(body["override_count"], 1)
        self.assertEqual(body["overrides_with_max_uses"], 1)

    def test_8_endpoint_revoke_returns_200(self):
        """DELETE /agent/epoch-window-override returns 200 with revoked=True."""
        from bridge.vapi_bridge.operator_api import create_operator_app
        from fastapi.testclient import TestClient

        cfg = MagicMock()
        cfg.operator_api_key = "key119b"
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0
        cfg.rate_limit_per_minute = 60

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/op119b.db")
        store.insert_device_epoch_override("dev_cold_revoke", 172800.0)

        app = create_operator_app(cfg=cfg, store=store, chain=MagicMock(), bus=MagicMock())
        client = TestClient(app)
        resp = client.delete(
            "/agent/epoch-window-override?api_key=key119b&device_id=dev_cold_revoke"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["device_id"], "dev_cold_revoke")
        self.assertTrue(body["revoked"])
        # Confirm deleted from store
        val = store.get_device_epoch_override("dev_cold_revoke")
        self.assertIsNone(val)

    def test_9_tools_86_87_structure(self):
        """Tool #86 and #87 handlers return dicts with all required keys."""
        from bridge.vapi_bridge.bridge_agent import BridgeAgent

        cfg = MagicMock()
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/ba119.db")
        store.insert_device_epoch_override("dev_tool_test", 43200.0, max_uses=10)

        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        # Tool #86
        result86 = agent._execute_tool("get_epoch_window_override_status", {})
        for key in ("override_count", "overrides_with_max_uses", "overrides",
                    "epoch_window_enabled", "timestamp"):
            self.assertIn(key, result86)
        self.assertEqual(result86["override_count"], 1)

        # Tool #87
        result87 = agent._execute_tool("revoke_device_epoch_override",
                                       {"device_id": "dev_tool_test"})
        for key in ("device_id", "revoked", "timestamp"):
            self.assertIn(key, result87)
        self.assertTrue(result87["revoked"])
        # Confirm deleted
        val = store.get_device_epoch_override("dev_tool_test")
        self.assertIsNone(val)


if __name__ == "__main__":
    unittest.main()
