"""
Phase 126 — Live L4 Gate Per-Battery Routing + BehavioralArchaeologist Fixes (8 tests)

test_1_l4_router_log_empty
test_2_router_returns_global_fallback_when_no_track
test_3_router_returns_per_battery_when_track_exists
test_4_router_log_records_source
test_5_schema_version_126
test_6_router_status_endpoint_7_keys
test_7_tool_94_structure
test_8_behavioral_archaeologist_constants_exist
"""

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sdk"))

from vapi_bridge.store import Store


def _make_store(tmp_path=None):
    import tempfile, os
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    db_path = os.path.join(tmp_path, "test_phase126.db")
    return Store(db_path=db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    cfg.l4_battery_threshold_enabled = False
    cfg.l4_anomaly_threshold = 7.009
    cfg.l4_continuity_threshold = 5.367
    cfg.live_feature_dim = 13
    cfg.calibration_feature_dim = 12
    cfg.calibration_n_sessions = 74
    cfg.calibration_timestamp = 0.0
    cfg.anomaly_threshold = 7.009
    cfg.continuity_threshold = 5.367
    cfg.separation_ratio_current = 0.474
    cfg.confidence_multiplier_enabled = False
    cfg.dual_primitive_gate_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.poad_registry_enabled = False
    cfg.epoch_window_enabled = False
    cfg.epoch_window_seconds = 86400.0
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestL4RouterLogEmpty(unittest.TestCase):
    def test_1_l4_router_log_empty(self):
        store = _make_store()
        rows = store.get_l4_router_log()
        self.assertEqual(rows, [])


class TestRouterGlobalFallbackNoTrack(unittest.TestCase):
    def test_2_router_returns_global_fallback_when_no_track(self):
        from vapi_bridge.l4_threshold_router import get_thresholds
        store = _make_store()
        cfg = _make_cfg(l4_battery_threshold_enabled=True)
        anomaly, continuity, source = get_thresholds("touchpad", store, cfg)
        self.assertEqual(source, "global_fallback")
        self.assertAlmostEqual(anomaly, 7.009, places=3)
        self.assertAlmostEqual(continuity, 5.367, places=3)


class TestRouterPerBatteryWhenTrackExists(unittest.TestCase):
    def test_3_router_returns_per_battery_when_track_exists(self):
        from vapi_bridge.l4_threshold_router import get_thresholds
        import tempfile, os
        tmp = tempfile.mkdtemp()
        store = _make_store(tmp)
        # Insert an active track for "touchpad"
        store.insert_l4_threshold_track(
            battery_type="touchpad",
            anomaly_threshold=7.5,
            continuity_threshold=5.5,
            n_sessions=40,
            calibrated_at=time.time(),
        )
        cfg = _make_cfg(l4_battery_threshold_enabled=True)
        anomaly, continuity, source = get_thresholds("touchpad", store, cfg)
        self.assertEqual(source, "per_battery")
        self.assertAlmostEqual(anomaly, 7.5, places=3)
        self.assertAlmostEqual(continuity, 5.5, places=3)


class TestRouterLogRecordsSource(unittest.TestCase):
    def test_4_router_log_records_source(self):
        store = _make_store()
        row_id = store.insert_l4_router_log(
            battery_type="touchpad",
            threshold_source="per_battery",
            anomaly_used=7.5,
            continuity_used=5.5,
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)
        logs = store.get_l4_router_log()
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log["battery_type"], "touchpad")
        self.assertEqual(log["threshold_source"], "per_battery")
        self.assertAlmostEqual(log["anomaly_used"], 7.5, places=3)
        self.assertAlmostEqual(log["continuity_used"], 5.5, places=3)


class TestSchemaVersion126(unittest.TestCase):
    def test_5_schema_version_126(self):
        store = _make_store()
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT phase, migration_name FROM schema_versions WHERE phase = 126"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "l4_router")


class TestRouterStatusEndpoint7Keys(unittest.TestCase):
    def test_6_router_status_endpoint_7_keys(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.get("/agent/l4-router-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required_keys = {
            "l4_battery_threshold_enabled", "total_lookups", "per_battery_lookups",
            "global_fallback_count", "last_battery_type", "last_source", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertEqual(body["total_lookups"], 0)
        self.assertEqual(body["global_fallback_count"], 0)


class TestTool94Structure(unittest.TestCase):
    def test_7_tool_94_structure(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._cfg = cfg
        agent._store = store
        agent._chain = MagicMock()
        agent._bus = MagicMock()

        result = agent._execute_tool("get_l4_router_status", {})
        required_keys = {
            "l4_battery_threshold_enabled", "total_lookups", "per_battery_lookups",
            "global_fallback_count", "last_battery_type", "last_source", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")


class TestBehavioralArchaeologistConstantsExist(unittest.TestCase):
    def test_8_behavioral_archaeologist_constants_exist(self):
        """_WARMUP_COEFF and _BURST_CV_DIVISOR are named constants (Phase 126 regression guard)."""
        from vapi_bridge import behavioral_archaeologist as ba
        self.assertTrue(hasattr(ba, "_WARMUP_COEFF"), "_WARMUP_COEFF not found in module")
        self.assertTrue(hasattr(ba, "_BURST_CV_DIVISOR"), "_BURST_CV_DIVISOR not found in module")
        self.assertEqual(ba._WARMUP_COEFF, 20_000)
        self.assertAlmostEqual(ba._BURST_CV_DIVISOR, 2.0, places=6)


if __name__ == "__main__":
    unittest.main()
