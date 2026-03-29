"""
Phase 125 — Per-Battery Threshold Calibrator + Calibration Apply Tests (8 tests)

test_1_l4_battery_calibration_runs_table_empty
test_2_insert_l4_battery_calibration_run_roundtrip
test_3_apply_endpoint_inserts_track_and_returns_summary
test_4_apply_endpoint_returns_422_on_bounds_violation
test_5_schema_version_125
test_6_calibration_feature_dim_updates_on_apply
test_7_tool_93_structure
test_8_staleness_clears_after_apply
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
    db_path = os.path.join(tmp_path, "test_phase125.db")
    return Store(db_path=db_path)


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


class TestL4BatteryCalibrationRunsEmpty(unittest.TestCase):
    def test_1_l4_battery_calibration_runs_table_empty(self):
        store = _make_store()
        rows = store.get_l4_battery_calibration_runs()
        self.assertEqual(rows, [])


class TestInsertL4BatteryCalibrationRunRoundtrip(unittest.TestCase):
    def test_2_insert_l4_battery_calibration_run_roundtrip(self):
        store = _make_store()
        row_id = store.insert_l4_battery_calibration_run(
            battery_type="touchpad",
            anomaly_threshold=7.009,
            continuity_threshold=5.367,
            n_sessions=32,
            calibration_feature_dim=13,
            notes="Phase 125 test",
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)
        rows = store.get_l4_battery_calibration_runs()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["battery_type"], "touchpad")
        self.assertAlmostEqual(row["anomaly_threshold"], 7.009, places=3)
        self.assertAlmostEqual(row["continuity_threshold"], 5.367, places=3)
        self.assertEqual(row["n_sessions"], 32)
        self.assertEqual(row["calibration_feature_dim"], 13)
        self.assertEqual(row["notes"], "Phase 125 test")


class TestApplyEndpointInsertTrackAndReturnsSummary(unittest.TestCase):
    def test_3_apply_endpoint_inserts_track_and_returns_summary(self):
        import tempfile, os
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.post(
            "/agent/apply-l4-battery-calibration"
            "?api_key=test-key"
            "&battery_type=touchpad"
            "&anomaly_threshold=7.5"
            "&continuity_threshold=5.5"
            "&n_sessions=40"
            "&calibration_feature_dim=13"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required_keys = {
            "track_id", "run_id", "battery_type",
            "anomaly_threshold", "continuity_threshold",
            "n_sessions", "calibration_feature_dim", "stale", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertEqual(body["battery_type"], "touchpad")
        self.assertAlmostEqual(body["anomaly_threshold"], 7.5, places=3)
        # verify track was inserted
        tracks = store.get_l4_threshold_tracks()
        self.assertEqual(len(tracks), 1)
        # verify run was logged
        runs = store.get_l4_battery_calibration_runs()
        self.assertEqual(len(runs), 1)


class TestApplyEndpointReturns422OnBoundsViolation(unittest.TestCase):
    def test_4_apply_endpoint_returns_422_on_bounds_violation(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        # anomaly_threshold below 5.0 — bounds violation
        resp = client.post(
            "/agent/apply-l4-battery-calibration"
            "?api_key=test-key"
            "&battery_type=touchpad"
            "&anomaly_threshold=4.9"
            "&continuity_threshold=5.0"
            "&n_sessions=10"
        )
        self.assertEqual(resp.status_code, 422)
        # continuity_threshold above 10.0 — bounds violation
        resp2 = client.post(
            "/agent/apply-l4-battery-calibration"
            "?api_key=test-key"
            "&battery_type=trigger"
            "&anomaly_threshold=7.0"
            "&continuity_threshold=10.1"
            "&n_sessions=10"
        )
        self.assertEqual(resp2.status_code, 422)
        # Confirm no tracks or runs were inserted
        self.assertEqual(store.get_l4_threshold_tracks(), [])
        self.assertEqual(store.get_l4_battery_calibration_runs(), [])


class TestSchemaVersion125(unittest.TestCase):
    def test_5_schema_version_125(self):
        store = _make_store()
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT phase, migration_name FROM schema_versions WHERE phase = 125"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "per_battery_calibration")


class TestCalibrationFeatureDimUpdatesOnApply(unittest.TestCase):
    def test_6_calibration_feature_dim_updates_on_apply(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        # Start stale: live=13, calib=12
        cfg = _make_cfg(live_feature_dim=13, calibration_feature_dim=12)

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)

        # Verify stale before apply
        self.assertNotEqual(cfg.live_feature_dim, cfg.calibration_feature_dim)

        resp = client.post(
            "/agent/apply-l4-battery-calibration"
            "?api_key=test-key"
            "&battery_type=touchpad"
            "&anomaly_threshold=7.5"
            "&continuity_threshold=5.5"
            "&n_sessions=40"
            "&calibration_feature_dim=13"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # stale should now be False (13 == 13)
        self.assertFalse(body["stale"])
        # cfg updated in-process
        self.assertEqual(cfg.calibration_feature_dim, 13)


class TestTool93Structure(unittest.TestCase):
    def test_7_tool_93_structure(self):
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

        result = agent._execute_tool("apply_l4_battery_calibration", {
            "battery_type": "touchpad",
            "anomaly_threshold": 7.5,
            "continuity_threshold": 5.5,
            "n_sessions": 40,
        })
        required_keys = {
            "track_id", "run_id", "battery_type",
            "anomaly_threshold", "continuity_threshold",
            "n_sessions", "calibration_feature_dim", "stale", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")


class TestStalenessClearsAfterApply(unittest.TestCase):
    def test_8_staleness_clears_after_apply(self):
        """stale=True (dim 12≠13) → apply dim=13 → stale=False."""
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        # dim 12 ≠ 13 → stale
        cfg = _make_cfg(live_feature_dim=13, calibration_feature_dim=12)

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)

        # Check staleness endpoint before apply
        stale_resp = client.get("/agent/l4-calibration-status?api_key=test-key")
        self.assertEqual(stale_resp.status_code, 200)
        self.assertTrue(stale_resp.json()["stale"])

        # Apply calibration with feature_dim=13
        apply_resp = client.post(
            "/agent/apply-l4-battery-calibration"
            "?api_key=test-key"
            "&battery_type=gameplay"
            "&anomaly_threshold=7.2"
            "&continuity_threshold=5.1"
            "&n_sessions=35"
            "&calibration_feature_dim=13"
        )
        self.assertEqual(apply_resp.status_code, 200)
        self.assertFalse(apply_resp.json()["stale"])

        # cfg dimension was updated → staleness endpoint now returns False
        stale_after = client.get("/agent/l4-calibration-status?api_key=test-key")
        self.assertEqual(stale_after.status_code, 200)
        self.assertFalse(stale_after.json()["stale"])


if __name__ == "__main__":
    unittest.main()
