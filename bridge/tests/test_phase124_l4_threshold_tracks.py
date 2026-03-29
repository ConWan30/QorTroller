"""
Phase 124 — L4 Per-Battery Threshold Track Registry Tests (8 tests)

test_1_l4_threshold_tracks_table_empty
test_2_insert_l4_threshold_track_roundtrip
test_3_get_l4_threshold_tracks_by_battery_type
test_4_get_l4_threshold_tracks_active_only
test_5_schema_version_124
test_6_endpoint_returns_6_keys
test_7_bounds_enforcement_raises_on_out_of_range
test_8_tool_92_structure
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
    db_path = os.path.join(tmp_path, "test_phase124.db")
    store = Store(db_path=db_path)
    return store


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    cfg.separation_ratio_current = 0.474
    cfg.l4_battery_threshold_enabled = False
    cfg.live_feature_dim = 13
    cfg.calibration_feature_dim = 12
    cfg.calibration_n_sessions = 74
    cfg.calibration_timestamp = 0.0
    cfg.anomaly_threshold = 7.009
    cfg.continuity_threshold = 5.367
    cfg.confidence_multiplier_enabled = False
    cfg.dual_primitive_gate_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.poad_registry_enabled = False
    cfg.epoch_window_enabled = False
    cfg.epoch_window_seconds = 86400.0
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestL4ThresholdTracksEmpty(unittest.TestCase):
    def test_1_l4_threshold_tracks_table_empty(self):
        store = _make_store()
        rows = store.get_l4_threshold_tracks()
        self.assertEqual(rows, [])


class TestInsertL4ThresholdTrackRoundtrip(unittest.TestCase):
    def test_2_insert_l4_threshold_track_roundtrip(self):
        store = _make_store()
        row_id = store.insert_l4_threshold_track(
            battery_type="touchpad",
            anomaly_threshold=7.009,
            continuity_threshold=5.367,
            n_sessions=74,
            calibrated_at=time.time(),
            active=True,
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)
        rows = store.get_l4_threshold_tracks()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["battery_type"], "touchpad")
        self.assertAlmostEqual(row["anomaly_threshold"], 7.009, places=3)
        self.assertAlmostEqual(row["continuity_threshold"], 5.367, places=3)
        self.assertEqual(row["n_sessions"], 74)
        self.assertTrue(row["active"])


class TestGetL4ThresholdTracksByBatteryType(unittest.TestCase):
    def test_3_get_l4_threshold_tracks_by_battery_type(self):
        store = _make_store()
        store.insert_l4_threshold_track(
            battery_type="touchpad", anomaly_threshold=7.0, continuity_threshold=5.0,
            n_sessions=10, calibrated_at=time.time(), active=True,
        )
        store.insert_l4_threshold_track(
            battery_type="trigger", anomaly_threshold=8.0, continuity_threshold=6.0,
            n_sessions=20, calibrated_at=time.time(), active=True,
        )
        touchpad_rows = store.get_l4_threshold_tracks(battery_type="touchpad")
        self.assertEqual(len(touchpad_rows), 1)
        self.assertEqual(touchpad_rows[0]["battery_type"], "touchpad")

        trigger_rows = store.get_l4_threshold_tracks(battery_type="trigger")
        self.assertEqual(len(trigger_rows), 1)
        self.assertEqual(trigger_rows[0]["battery_type"], "trigger")

        all_rows = store.get_l4_threshold_tracks()
        self.assertEqual(len(all_rows), 2)


class TestGetL4ThresholdTracksActiveOnly(unittest.TestCase):
    def test_4_get_l4_threshold_tracks_active_only(self):
        store = _make_store()
        store.insert_l4_threshold_track(
            battery_type="touchpad", anomaly_threshold=7.0, continuity_threshold=5.0,
            n_sessions=10, calibrated_at=time.time(), active=True,
        )
        store.insert_l4_threshold_track(
            battery_type="gameplay", anomaly_threshold=7.5, continuity_threshold=5.5,
            n_sessions=30, calibrated_at=time.time(), active=False,
        )
        active_rows = store.get_l4_threshold_tracks(active_only=True)
        self.assertEqual(len(active_rows), 1)
        self.assertEqual(active_rows[0]["battery_type"], "touchpad")

        all_rows = store.get_l4_threshold_tracks()
        self.assertEqual(len(all_rows), 2)


class TestSchemaVersion124(unittest.TestCase):
    def test_5_schema_version_124(self):
        store = _make_store()
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT phase, migration_name FROM schema_versions WHERE phase = 124"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "l4_threshold_tracks")


class TestEndpointReturns6Keys(unittest.TestCase):
    def test_6_endpoint_returns_6_keys(self):
        import tempfile, os
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.get("/agent/l4-threshold-tracks?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required_keys = {
            "l4_battery_threshold_enabled",
            "track_count",
            "active_count",
            "battery_types_tracked",
            "tracks",
            "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertEqual(body["track_count"], 0)
        self.assertEqual(body["active_count"], 0)
        self.assertFalse(body["l4_battery_threshold_enabled"])


class TestBoundsEnforcementRaisesOnOutOfRange(unittest.TestCase):
    def test_7_bounds_enforcement_raises_on_out_of_range(self):
        store = _make_store()
        # anomaly_threshold below 5.0
        with self.assertRaises(ValueError):
            store.insert_l4_threshold_track(
                battery_type="touchpad", anomaly_threshold=4.9, continuity_threshold=5.0,
                n_sessions=10, calibrated_at=time.time(),
            )
        # anomaly_threshold above 15.0
        with self.assertRaises(ValueError):
            store.insert_l4_threshold_track(
                battery_type="touchpad", anomaly_threshold=15.1, continuity_threshold=5.0,
                n_sessions=10, calibrated_at=time.time(),
            )
        # continuity_threshold below 3.0
        with self.assertRaises(ValueError):
            store.insert_l4_threshold_track(
                battery_type="touchpad", anomaly_threshold=7.0, continuity_threshold=2.9,
                n_sessions=10, calibrated_at=time.time(),
            )
        # continuity_threshold above 10.0
        with self.assertRaises(ValueError):
            store.insert_l4_threshold_track(
                battery_type="touchpad", anomaly_threshold=7.0, continuity_threshold=10.1,
                n_sessions=10, calibrated_at=time.time(),
            )
        # Verify no rows were inserted
        rows = store.get_l4_threshold_tracks()
        self.assertEqual(len(rows), 0)


class TestTool92Structure(unittest.TestCase):
    def test_8_tool_92_structure(self):
        import tempfile, os
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._cfg = cfg
        agent._store = store
        agent._chain = MagicMock()
        agent._bus = MagicMock()

        result = agent._execute_tool("get_l4_threshold_tracks", {})
        required_keys = {
            "l4_battery_threshold_enabled",
            "track_count",
            "active_count",
            "battery_types_tracked",
            "tracks",
            "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")


if __name__ == "__main__":
    unittest.main()
