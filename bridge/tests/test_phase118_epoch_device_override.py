"""
Phase 118 — Epoch Window Auto-Tune Advisor + Cold-Start Device Override (9 tests)

W1: cold-start devices show large p95 at gate activation → false-positive block
    mitigation: per-device epoch override bypasses global window for selected devices
W2: auto-tune advisor recommends fleet window + surfaces override candidates

Infrastructure-first: per_device_epoch_overrides table; get_device_epoch_override()
returns None (no override) by default → zero behavior change to existing Gate-5 logic.
"""
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[2]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from bridge.vapi_bridge.store import Store  # noqa: E402


def _make_store() -> Store:
    tmp = tempfile.mkdtemp()
    return Store(f"{tmp}/test_phase118.db")


class TestPhase118EpochDeviceOverride(unittest.TestCase):

    def test_1_table_exists_and_no_override_returns_none(self):
        """get_device_epoch_override returns None when no override is set."""
        store = _make_store()
        result = store.get_device_epoch_override("dev_cold")
        self.assertIsNone(result)

    def test_2_insert_and_retrieve_override(self):
        """insert_device_epoch_override + get_device_epoch_override roundtrip."""
        store = _make_store()
        store.insert_device_epoch_override("dev_a", 172800.0, "cold start override")
        val = store.get_device_epoch_override("dev_a")
        self.assertAlmostEqual(val, 172800.0)

    def test_3_upsert_updates_existing_device(self):
        """Second insert_device_epoch_override for same device_id replaces old value."""
        store = _make_store()
        store.insert_device_epoch_override("dev_b", 86400.0)
        store.insert_device_epoch_override("dev_b", 259200.0, "updated reason")
        val = store.get_device_epoch_override("dev_b")
        self.assertAlmostEqual(val, 259200.0)

    def test_4_get_all_device_epoch_overrides_returns_list(self):
        """get_all_device_epoch_overrides returns all overrides as list of dicts."""
        store = _make_store()
        store.insert_device_epoch_override("dev_x", 3600.0, "reason x")
        store.insert_device_epoch_override("dev_y", 7200.0, "reason y")
        overrides = store.get_all_device_epoch_overrides()
        device_ids = {o["device_id"] for o in overrides}
        self.assertIn("dev_x", device_ids)
        self.assertIn("dev_y", device_ids)

    def test_5_schema_version_118(self):
        """schema_versions has (118, epoch_window_device_overrides) after store init."""
        store = _make_store()
        with store._conn() as conn:
            row = conn.execute(
                "SELECT migration_name FROM schema_versions WHERE phase = 118"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "epoch_window_device_overrides")

    def test_6_endpoint_auto_tune_returns_7_keys(self):
        """GET /agent/epoch-window-auto-tune returns 200 with all 7 required keys."""
        from bridge.vapi_bridge.operator_api import create_operator_app
        from fastapi.testclient import TestClient

        cfg = MagicMock()
        cfg.operator_api_key = "key118"
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0
        cfg.rate_limit_per_minute = 60

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/op118.db")

        app = create_operator_app(cfg=cfg, store=store, chain=MagicMock(), bus=MagicMock())
        client = TestClient(app)
        resp = client.get("/agent/epoch-window-auto-tune?api_key=key118")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("epoch_window_enabled", "current_window_seconds",
                    "recommended_window_seconds", "fleet_p95_age_seconds",
                    "override_count", "override_candidates", "timestamp"):
            self.assertIn(key, body)

    def test_7_endpoint_override_post_stores_and_returns(self):
        """POST /agent/epoch-window-override upserts override and returns device_id + window."""
        from bridge.vapi_bridge.operator_api import create_operator_app
        from fastapi.testclient import TestClient

        cfg = MagicMock()
        cfg.operator_api_key = "key118b"
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0
        cfg.rate_limit_per_minute = 60

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/op118b.db")

        app = create_operator_app(cfg=cfg, store=store, chain=MagicMock(), bus=MagicMock())
        client = TestClient(app)
        resp = client.post(
            "/agent/epoch-window-override"
            "?api_key=key118b"
            "&device_id=dev_cold_start"
            "&window_seconds=172800"
            "&reason=cold+start+override"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["device_id"], "dev_cold_start")
        self.assertAlmostEqual(body["override_window_seconds"], 172800.0)
        # Confirm it persisted
        val = store.get_device_epoch_override("dev_cold_start")
        self.assertAlmostEqual(val, 172800.0)

    def test_8_tool_84_auto_tune_returns_7_keys(self):
        """Tool #84 get_epoch_window_auto_tune handler returns dict with 7 required keys."""
        from bridge.vapi_bridge.bridge_agent import BridgeAgent

        cfg = MagicMock()
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/ba118a.db")

        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        result = agent._execute_tool("get_epoch_window_auto_tune", {})
        for key in ("epoch_window_enabled", "current_window_seconds",
                    "recommended_window_seconds", "fleet_p95_age_seconds",
                    "override_count", "override_candidates", "timestamp"):
            self.assertIn(key, result)

    def test_9_tool_85_set_override_returns_5_keys(self):
        """Tool #85 set_device_epoch_override handler stores override and returns 5 keys."""
        from bridge.vapi_bridge.bridge_agent import BridgeAgent

        cfg = MagicMock()
        cfg.epoch_window_enabled = False
        cfg.epoch_window_seconds = 86400.0

        tmp = tempfile.mkdtemp()
        store = Store(f"{tmp}/ba118b.db")

        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        result = agent._execute_tool("set_device_epoch_override", {
            "device_id": "dev_override_tool",
            "window_seconds": 604800.0,
            "reason": "weekly window for slow adjudicator",
        })
        for key in ("device_id", "override_window_seconds", "reason", "row_id", "timestamp"):
            self.assertIn(key, result)
        self.assertEqual(result["device_id"], "dev_override_tool")
        self.assertAlmostEqual(result["override_window_seconds"], 604800.0)
        # Confirm persisted
        val = store.get_device_epoch_override("dev_override_tool")
        self.assertAlmostEqual(val, 604800.0)


if __name__ == "__main__":
    unittest.main()
