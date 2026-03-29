"""
Phase 120 — Bluetooth Transport Foundation Bridge Tests (8 tests)

test_1_bt_transport_log_roundtrip
test_2_get_bt_transport_status_empty
test_3_get_bt_transport_status_newest_first
test_4_schema_version_120
test_5_bt_transport_status_endpoint_7_keys
test_6_bt_transport_endpoint_disabled_default
test_7_mock_ble_transport_constants
test_8_tool_88_structure
"""

import asyncio
import sys
import time
import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add bridge root to path
BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

from vapi_bridge.store import Store


def _make_store() -> Store:
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_phase120.db")
    return Store(db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.bt_transport_enabled    = kwargs.get("bt_transport_enabled", False)
    cfg.bt_device_address       = kwargs.get("bt_device_address", "")
    cfg.bt_sampling_rate_hz     = kwargs.get("bt_sampling_rate_hz", 250)
    cfg.operator_api_key        = "test-key"
    cfg.operator_rate_limit     = 1000
    cfg.epoch_window_enabled    = False
    cfg.dual_primitive_gate_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.poad_registry_enabled   = False
    cfg.agent_dry_run_mode      = True
    return cfg


# ---------------------------------------------------------------------------
# 1. insert + roundtrip
# ---------------------------------------------------------------------------

class TestBtTransportLogRoundtrip(unittest.TestCase):

    def test_1_bt_transport_log_roundtrip(self):
        """insert_bt_transport_log roundtrip — all fields stored and retrieved correctly."""
        store = _make_store()
        row_id = store.insert_bt_transport_log(
            device_address="AA:BB:CC:DD:EE:FF",
            sampling_rate_hz=250,
            frames_received=10000,
            frames_dropped=2,
            avg_interval_ms=4.01,
            session_start_ts=1000.0,
            session_end_ts=1040.0,
        )
        self.assertGreater(row_id, 0)
        logs = store.get_bt_transport_status(limit=10)
        self.assertEqual(len(logs), 1)
        row = logs[0]
        self.assertEqual(row["device_address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(row["sampling_rate_hz"], 250)
        self.assertEqual(row["frames_received"], 10000)
        self.assertEqual(row["frames_dropped"], 2)
        self.assertAlmostEqual(row["avg_interval_ms"], 4.01, places=2)


# ---------------------------------------------------------------------------
# 2. empty store returns empty list
# ---------------------------------------------------------------------------

class TestBtTransportStatusEmpty(unittest.TestCase):

    def test_2_get_bt_transport_status_empty(self):
        """Empty store returns empty list, no exception."""
        store = _make_store()
        logs = store.get_bt_transport_status()
        self.assertIsInstance(logs, list)
        self.assertEqual(len(logs), 0)


# ---------------------------------------------------------------------------
# 3. newest first ordering
# ---------------------------------------------------------------------------

class TestBtTransportNewestFirst(unittest.TestCase):

    def test_3_get_bt_transport_status_newest_first(self):
        """Multiple inserts — ORDER BY id DESC returns newest first."""
        store = _make_store()
        for i in range(3):
            store.insert_bt_transport_log(
                device_address=f"AA:BB:CC:DD:EE:{i:02X}",
                sampling_rate_hz=250,
                frames_received=i * 1000,
                frames_dropped=0,
                avg_interval_ms=4.0,
                session_start_ts=float(i * 100),
                session_end_ts=float(i * 100 + 40),
            )
        logs = store.get_bt_transport_status(limit=3)
        self.assertEqual(len(logs), 3)
        # Newest first: frames_received descending (2000, 1000, 0)
        self.assertGreater(logs[0]["frames_received"], logs[1]["frames_received"])


# ---------------------------------------------------------------------------
# 4. schema version 120
# ---------------------------------------------------------------------------

class TestSchemaVersion120(unittest.TestCase):

    def test_4_schema_version_120(self):
        """schema_versions table has (120, 'bt_transport') after store init."""
        store = _make_store()
        version = store.get_schema_version()
        self.assertGreaterEqual(version, 120)


# ---------------------------------------------------------------------------
# 5. GET /agent/bt-transport-status endpoint returns 7 required keys
# ---------------------------------------------------------------------------

class TestBtTransportEndpoint(unittest.TestCase):

    def test_5_bt_transport_status_endpoint_7_keys(self):
        """GET /agent/bt-transport-status returns 200 with all 7 required keys."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        store = _make_store()
        cfg   = _make_cfg()
        chain = MagicMock()
        bus   = MagicMock()

        app    = create_operator_app(cfg, store, chain, bus=bus)
        client = TestClient(app)

        resp = client.get("/agent/bt-transport-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        required_keys = {
            "bt_transport_enabled", "device_address", "sampling_rate_hz",
            "frames_received", "frames_dropped", "avg_interval_ms", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, data, f"Missing key: {key}")


# ---------------------------------------------------------------------------
# 6. bt_transport_enabled=False by default
# ---------------------------------------------------------------------------

class TestBtTransportDisabledDefault(unittest.TestCase):

    def test_6_bt_transport_endpoint_disabled_default(self):
        """bt_transport_enabled=False by default in endpoint response."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        store = _make_store()
        cfg   = _make_cfg(bt_transport_enabled=False)
        chain = MagicMock()
        bus   = MagicMock()

        app    = create_operator_app(cfg, store, chain, bus=bus)
        client = TestClient(app)

        resp = client.get("/agent/bt-transport-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["bt_transport_enabled"])
        self.assertEqual(data["sampling_rate_hz"], 250)


# ---------------------------------------------------------------------------
# 7. MockBLETransport constants and interface
# ---------------------------------------------------------------------------

class TestMockBLETransportConstants(unittest.TestCase):

    def test_7_mock_ble_transport_constants(self):
        """BT constants correct; MockBLETransport produces BTFrames with TRANSPORT_TYPE_BLE."""
        from vapi_bridge.transports.bluetooth import (
            BT_POLL_HZ, BT_FRAME_MS, BT_WINDOW, BT_HZ_PER_BIN,
            TRANSPORT_TYPE_BLE, MockBLETransport, BTFrame,
        )
        # Verify constants
        self.assertEqual(BT_POLL_HZ, 250)
        self.assertAlmostEqual(BT_FRAME_MS, 4.0, places=5)
        self.assertEqual(BT_WINDOW, 1024)
        self.assertAlmostEqual(BT_HZ_PER_BIN, 0.244, places=3)
        self.assertEqual(TRANSPORT_TYPE_BLE, 0x02)

        # Verify mock produces frames with correct transport_type
        async def _collect():
            mock = MockBLETransport(seed=42, n_frames=5)
            frames = []
            async for frame in mock.stream_frames():
                frames.append(frame)
            return frames

        frames = asyncio.get_event_loop().run_until_complete(_collect())
        self.assertEqual(len(frames), 5)
        for frame in frames:
            self.assertIsInstance(frame, BTFrame)
            self.assertEqual(frame.transport_type, TRANSPORT_TYPE_BLE)
            # Sticks should be near center 128
            self.assertGreater(frame.left_stick_x, 0)
            self.assertLess(frame.left_stick_x, 256)


# ---------------------------------------------------------------------------
# 8. Tool #88 structure — returns 6 required keys
# ---------------------------------------------------------------------------

class TestTool88Structure(unittest.TestCase):

    def test_8_tool_88_structure(self):
        """Tool #88 get_bt_transport_status handler returns dict with 6 required keys."""
        from vapi_bridge.bridge_agent import BridgeAgent

        store = _make_store()
        cfg   = _make_cfg()

        agent  = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_bt_transport_status", {})

        required_keys = {
            "bt_transport_enabled", "device_address", "sampling_rate_hz",
            "frames_received", "frames_dropped", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Tool #88 missing key: {key}")
        self.assertFalse(result["bt_transport_enabled"])
        self.assertEqual(result["sampling_rate_hz"], 250)


if __name__ == "__main__":
    unittest.main()
