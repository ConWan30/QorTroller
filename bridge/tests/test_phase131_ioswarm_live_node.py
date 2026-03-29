"""
Phase 131 — IoSwarm Live Node Foundation (8 tests)

test_1_node_registry_empty
test_2_insert_node_registry_roundtrip
test_3_update_last_seen
test_4_emulator_mode_when_urls_empty
test_5_live_node_client_falls_back_to_emulator
test_6_endpoint_7_keys
test_7_tool_99_structure
test_8_schema_version_131
"""

import os
import sys
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_bridge.store import Store


def _make_store():
    tmp = tempfile.mkdtemp()
    return Store(db_path=os.path.join(tmp, "test_phase131.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    cfg.ioswarm_node_urls = kwargs.get("ioswarm_node_urls", "")
    cfg.ioswarm_node_timeout_seconds = kwargs.get("ioswarm_node_timeout_seconds", 5.0)
    cfg.swarm_operator_gate_address = kwargs.get("swarm_operator_gate_address", "")
    cfg.separation_ratio_current = 0.474
    return cfg


class TestPhase131NodeRegistryStore(unittest.TestCase):
    """Tests 1–3: store layer."""

    def test_1_node_registry_empty(self):
        store = _make_store()
        rows = store.get_ioswarm_node_registry()
        self.assertEqual(rows, [])

    def test_2_insert_node_registry_roundtrip(self):
        store = _make_store()
        row_id = store.insert_ioswarm_node_registry(
            node_url="http://node1.example.com:8090",
            staker_address="0xDeadBeef",
            active=True,
            node_version="1.0.0",
        )
        self.assertGreater(row_id, 0)
        rows = store.get_ioswarm_node_registry(active_only=False)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["node_url"], "http://node1.example.com:8090")
        self.assertEqual(row["staker_address"], "0xDeadBeef")
        self.assertTrue(bool(row["active"]))

    def test_3_update_last_seen(self):
        store = _make_store()
        store.insert_ioswarm_node_registry(
            node_url="http://node2.example.com:8090",
            staker_address="0xCafe",
        )
        ts_now = time.time()
        store.update_ioswarm_node_last_seen(
            node_url="http://node2.example.com:8090",
            ts=ts_now,
            staker_address="0xUpdated",
        )
        rows = store.get_ioswarm_node_registry(active_only=False)
        row = rows[0]
        self.assertAlmostEqual(row["last_seen_ts"], ts_now, places=0)
        self.assertEqual(row["staker_address"], "0xUpdated")


class TestPhase131LiveNodeClient(unittest.TestCase):
    """Tests 4–5: IoSwarmLiveNodeClient."""

    def test_4_emulator_mode_when_urls_empty(self):
        from vapi_bridge.ioswarm_live_node_client import IoSwarmLiveNodeClient
        store = _make_store()
        cfg = _make_cfg(ioswarm_node_urls="")
        client = IoSwarmLiveNodeClient(cfg=cfg, store=store)
        self.assertTrue(client.is_emulator_mode())

    def test_5_live_node_client_falls_back_to_emulator(self):
        from vapi_bridge.ioswarm_live_node_client import IoSwarmLiveNodeClient
        from vapi_bridge.ioswarm_renewal_coordinator import IoSwarmRenewalCoordinator
        store = _make_store()
        cfg = _make_cfg(ioswarm_node_urls="")
        client = IoSwarmLiveNodeClient(cfg=cfg, store=store)
        # Verify coordinator accepts live_client kwarg without error
        coord = IoSwarmRenewalCoordinator(cfg=cfg, store=store, live_client=client)
        self.assertTrue(client.is_emulator_mode())
        self.assertIsNotNone(coord)


class TestPhase131Endpoint(unittest.TestCase):
    """Test 6: REST endpoint 7 keys."""

    def test_6_endpoint_7_keys(self):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.get("/agent/ioswarm-node-registry-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required = {
            "live_nodes", "emulator_mode", "node_urls",
            "node_timeout_s", "registry_count", "last_quorum_ts", "timestamp",
        }
        for key in required:
            self.assertIn(key, body, f"Missing key: {key}")
        # With no node URLs configured, emulator_mode should be True
        self.assertTrue(body["emulator_mode"])


class TestPhase131Tool99(unittest.TestCase):
    """Test 7: BridgeAgent Tool #99."""

    def test_7_tool_99_structure(self):
        from vapi_bridge.bridge_agent import BridgeAgent, _TOOLS
        tool_names = [t["name"] for t in _TOOLS]
        self.assertIn("get_ioswarm_node_registry_status", tool_names)

        store = _make_store()
        cfg = _make_cfg(ioswarm_node_urls="")
        agent = BridgeAgent(cfg=cfg, store=store)
        result = agent._execute_tool("get_ioswarm_node_registry_status", {})
        required = {
            "live_nodes", "emulator_mode", "registry_count",
            "node_timeout_s", "last_quorum_ts", "timestamp", "error",
        }
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")
        # With no node URLs, emulator_mode should be True
        self.assertTrue(result["emulator_mode"])
        self.assertIsNone(result["error"])


class TestPhase131Schema(unittest.TestCase):
    """Test 8: schema_versions row for phase 131."""

    def test_8_schema_version_131(self):
        store = _make_store()
        con = sqlite3.connect(store._db_path)
        try:
            row = con.execute(
                "SELECT migration_name FROM schema_versions WHERE phase=131"
            ).fetchone()
            self.assertIsNotNone(row, "schema_versions must have phase=131 row")
            self.assertEqual(row[0], "ioswarm_node_registry")
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
