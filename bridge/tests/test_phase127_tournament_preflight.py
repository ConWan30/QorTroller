"""
Phase 127 — Tournament Pre-Launch Validation Suite (9 tests)

test_1_tournament_preflight_log_empty
test_2_insert_preflight_log_roundtrip
test_3_schema_version_127
test_4_run_preflight_endpoint_returns_required_keys
test_5_preflight_status_endpoint_found_false_on_empty
test_6_preflight_status_endpoint_found_true_after_run
test_7_commit_activation_blocked_by_preflight_p0_separation
test_8_tool_95_structure
test_9_overall_pass_false_when_any_p0_fails
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
    db_path = os.path.join(tmp_path, "test_phase127.db")
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
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestTournamentPreflightLogEmpty(unittest.TestCase):
    def test_1_tournament_preflight_log_empty(self):
        store = _make_store()
        rows = store.get_tournament_preflight_status()
        self.assertEqual(rows, [])


class TestInsertPreflightLogRoundtrip(unittest.TestCase):
    def test_2_insert_preflight_log_roundtrip(self):
        store = _make_store()
        row_id = store.insert_tournament_preflight_log(
            separation_ok=False,
            l4_ok=False,
            gate_ok=True,
            cert_ok=True,
            audit_ok=True,
            dual_gate_warned=True,
            epoch_window_warned=True,
            ioswarm_warned=True,
            overall_pass=False,
            conditions_json='{"separation_ratio": 0.474}',
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)
        rows = store.get_tournament_preflight_status()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertFalse(row["separation_ok"])
        self.assertFalse(row["l4_ok"])
        self.assertTrue(row["gate_ok"])
        self.assertTrue(row["cert_ok"])
        self.assertTrue(row["audit_ok"])
        self.assertTrue(row["dual_gate_warned"])
        self.assertFalse(row["overall_pass"])
        self.assertIn("separation_ratio", row["conditions_json"])


class TestSchemaVersion127(unittest.TestCase):
    def test_3_schema_version_127(self):
        store = _make_store()
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT phase, migration_name FROM schema_versions WHERE phase = 127"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "tournament_preflight")


class TestRunPreflightEndpointKeys(unittest.TestCase):
    def test_4_run_preflight_endpoint_returns_required_keys(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.post("/agent/run-tournament-preflight?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required_keys = {
            "separation_ok", "l4_ok", "gate_ok", "cert_ok", "audit_ok",
            "overall_pass", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, body, f"Missing key: {key}")
        # With no gate sessions and separation_ratio < 1.0, overall_pass must be False
        self.assertFalse(body["overall_pass"])
        self.assertFalse(body["separation_ok"])


class TestPreflightStatusFoundFalseOnEmpty(unittest.TestCase):
    def test_5_preflight_status_endpoint_found_false_on_empty(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.get("/agent/tournament-preflight-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body.get("found", True))
        self.assertFalse(body.get("overall_pass", True))


class TestPreflightStatusFoundAfterRun(unittest.TestCase):
    def test_6_preflight_status_endpoint_found_true_after_run(self):
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        # Run preflight first
        client.post("/agent/run-tournament-preflight?api_key=test-key")
        # Now get status
        resp = client.get("/agent/tournament-preflight-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("found", False))
        self.assertIn("separation_ok", body)
        self.assertIn("overall_pass", body)


class TestCommitActivationBlockedByPreflight(unittest.TestCase):
    def test_7_commit_activation_blocked_by_preflight_p0_separation(self):
        """POST /agent/commit-activation must block if latest preflight shows separation_ok=False."""
        import tempfile
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        # Insert a preflight log entry with separation_ok=False and l4_ok=False
        store.insert_tournament_preflight_log(
            separation_ok=False,  # P0 BLOCK
            l4_ok=False,          # P0 BLOCK
            gate_ok=True,
            cert_ok=True,
            audit_ok=True,
            overall_pass=False,
        )

        from vapi_bridge.operator_api import create_operator_app
        from starlette.testclient import TestClient

        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.post("/agent/commit-activation?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Must not commit — either gate fails OR preflight P0 block
        self.assertFalse(body.get("committed", True))
        self.assertIsNotNone(body.get("error"))


class TestTool95Structure(unittest.TestCase):
    def test_8_tool_95_structure(self):
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

        result = agent._execute_tool("run_tournament_preflight", {})
        required_keys = {
            "separation_ok", "l4_ok", "gate_ok", "cert_ok", "audit_ok",
            "overall_pass", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")


class TestOverallPassFalseWhenP0Fails(unittest.TestCase):
    def test_9_overall_pass_false_when_any_p0_fails(self):
        """overall_pass must be False when ANY P0 condition fails."""
        store = _make_store()
        # Insert with gate_ok=False but all others True
        store.insert_tournament_preflight_log(
            separation_ok=True,
            l4_ok=True,
            gate_ok=False,   # P0 FAIL
            cert_ok=True,
            audit_ok=True,
            overall_pass=False,
        )
        rows = store.get_tournament_preflight_status(limit=1)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["overall_pass"])
        self.assertFalse(rows[0]["gate_ok"])
        self.assertTrue(rows[0]["separation_ok"])
        self.assertTrue(rows[0]["l4_ok"])


if __name__ == "__main__":
    unittest.main()
