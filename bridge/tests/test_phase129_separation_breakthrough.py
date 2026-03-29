"""
Phase 129 — Full Covariance + Separation Ratio Breakthrough Monitor (9 tests)

test_1_separation_breakthrough_log_empty
test_2_insert_separation_ratio_breakthrough_roundtrip
test_3_monitor_agent_init_no_raise
test_4_monitor_agent_no_breakthrough_single_snapshot
test_5_monitor_agent_two_consecutive_fires_breakthrough
test_6_schema_version_129
test_7_endpoint_5_keys
test_8_tool_97_structure
test_9_full_covariance_flag_in_analyze_script
"""

import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_bridge.store import Store


def _make_store(tmp_path=None):
    import tempfile, os
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    db_path = os.path.join(tmp_path, "test_phase129.db")
    return Store(db_path=db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    cfg.separation_ratio_current = kwargs.get("separation_ratio_current", 0.0)
    cfg.live_feature_dim = kwargs.get("live_feature_dim", 13)
    cfg.calibration_feature_dim = kwargs.get("calibration_feature_dim", 12)
    cfg.l4_anomaly_threshold = 7.009
    cfg.l4_continuity_threshold = 5.367
    cfg.calibration_n_sessions = 74
    cfg.calibration_timestamp = 0.0
    cfg.dual_primitive_gate_enabled = False
    cfg.epoch_window_enabled = False
    cfg.epoch_window_seconds = 86400.0
    cfg.ioswarm_vhp_mint_enabled = False
    cfg.agent_dry_run_mode = True
    cfg.l4_battery_threshold_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.dual_primitive_gate_address = ""
    cfg.protocol_lens_address = ""
    cfg.adjudication_registry_address = ""
    cfg.gate_n = 100
    cfg.consecutive_clean = kwargs.get("consecutive_clean", 0)
    cfg.confidence_multiplier_enabled = False
    cfg.confidence_multiplier_floor = 0.0
    return cfg


def _make_app(store, cfg):
    from vapi_bridge.operator_api import create_operator_app
    return create_operator_app(cfg=cfg, store=store)


class TestPhase129SeparationBreakthrough(unittest.TestCase):

    # ------------------------------------------------------------------
    # test_1: separation_ratio_breakthrough_log table is empty on fresh store
    # ------------------------------------------------------------------
    def test_1_separation_breakthrough_log_empty(self):
        store = _make_store()
        rows = store.get_separation_ratio_breakthrough(limit=10)
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 0)

    # ------------------------------------------------------------------
    # test_2: insert + get roundtrip
    # ------------------------------------------------------------------
    def test_2_insert_separation_ratio_breakthrough_roundtrip(self):
        store = _make_store()
        row_id = store.insert_separation_ratio_breakthrough(
            before_ratio=0.85,
            after_ratio=1.05,
            n_players=3,
            feature_count=13,
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)
        rows = store.get_separation_ratio_breakthrough(limit=5)
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertAlmostEqual(float(r["before_ratio"]), 0.85, places=2)
        self.assertAlmostEqual(float(r["after_ratio"]), 1.05, places=2)
        self.assertEqual(int(r["n_players"]), 3)
        self.assertIn("breakthrough_at", r)

    # ------------------------------------------------------------------
    # test_3: SeparationRatioMonitorAgent init does not raise
    # ------------------------------------------------------------------
    def test_3_monitor_agent_init_no_raise(self):
        store = _make_store()
        cfg = _make_cfg()
        from vapi_bridge.separation_ratio_monitor_agent import SeparationRatioMonitorAgent
        agent = SeparationRatioMonitorAgent(cfg=cfg, store=store)
        self.assertIsNotNone(agent)

    # ------------------------------------------------------------------
    # test_4: single snapshot with ratio >= 1.0 does NOT fire breakthrough
    #         (W1: requires 2 consecutive)
    # ------------------------------------------------------------------
    def test_4_monitor_agent_no_breakthrough_single_snapshot(self):
        import tempfile, os
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        # Insert a single snapshot with ratio > 1.0
        store.insert_separation_ratio_snapshot(
            pooled_ratio=1.05,
            bt_strat_ratio=-1.0,
            n_sessions=97,
            n_players=3,
            active_features=13,
            tournament_ready=False,
        )

        from vapi_bridge.separation_ratio_monitor_agent import SeparationRatioMonitorAgent
        agent = SeparationRatioMonitorAgent(cfg=cfg, store=store)
        # prev_crossed starts False — single call should NOT fire breakthrough
        asyncio.get_event_loop().run_until_complete(agent._check_and_record())
        # No breakthrough inserted
        rows = store.get_separation_ratio_breakthrough(limit=5)
        self.assertEqual(len(rows), 0)

    # ------------------------------------------------------------------
    # test_5: two consecutive snapshots >= 1.0 fires breakthrough (on second call)
    # ------------------------------------------------------------------
    def test_5_monitor_agent_two_consecutive_fires_breakthrough(self):
        import tempfile, os
        tmp_path = tempfile.mkdtemp()
        store = _make_store(tmp_path)
        cfg = _make_cfg()

        # Insert snapshot with ratio > 1.0
        store.insert_separation_ratio_snapshot(
            pooled_ratio=1.10,
            bt_strat_ratio=-1.0,
            n_sessions=97,
            n_players=3,
            active_features=13,
            tournament_ready=False,
        )

        from vapi_bridge.separation_ratio_monitor_agent import SeparationRatioMonitorAgent
        agent = SeparationRatioMonitorAgent(cfg=cfg, store=store)

        loop = asyncio.new_event_loop()
        # First call: prev_crossed was False → sets prev_crossed=True, prev_ratio=0.0
        loop.run_until_complete(agent._check_and_record())
        # At this point: prev_crossed=True (current crossed), prev_ratio was 0.0
        # Second call with same snapshot and W1: prev_crossed=True, prev_ratio=0.0
        # Fire condition: current_crossed AND prev_crossed AND prev_ratio < 1.0
        loop.run_until_complete(agent._check_and_record())
        loop.close()

        rows = store.get_separation_ratio_breakthrough(limit=5)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(float(rows[0]["after_ratio"]), 1.10, places=2)

    # ------------------------------------------------------------------
    # test_6: schema_version 129 present
    # ------------------------------------------------------------------
    def test_6_schema_version_129(self):
        store = _make_store()
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT phase, migration_name FROM schema_versions WHERE phase=129"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "separation_breakthrough")

    # ------------------------------------------------------------------
    # test_7: endpoint returns exactly 5 required keys
    # ------------------------------------------------------------------
    def test_7_endpoint_5_keys(self):
        store = _make_store()
        cfg = _make_cfg()
        from fastapi.testclient import TestClient
        app = _make_app(store, cfg)
        client = TestClient(app)
        resp = client.get(
            "/agent/separation-ratio-breakthrough",
            params={"api_key": "test-key"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required = {
            "breakthrough_detected", "breakthrough_ratio",
            "breakthrough_ts", "n_players", "error",
        }
        for key in required:
            self.assertIn(key, body, f"Missing key: {key}")

    # ------------------------------------------------------------------
    # test_8: Tool #97 get_separation_ratio_breakthrough returns required keys
    # ------------------------------------------------------------------
    def test_8_tool_97_structure(self):
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

        result = agent._execute_tool("get_separation_ratio_breakthrough", {})
        required_keys = {
            "breakthrough_detected", "breakthrough_ratio",
            "breakthrough_ts", "n_players", "error",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertFalse(result["breakthrough_detected"])

    # ------------------------------------------------------------------
    # test_9: analyze_interperson_separation.py has --full-covariance flag
    # ------------------------------------------------------------------
    def test_9_full_covariance_flag_in_analyze_script(self):
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        analyze_py = scripts_dir / "analyze_interperson_separation.py"
        if not analyze_py.exists():
            self.skipTest("analyze_interperson_separation.py not found")
        content = analyze_py.read_text(encoding="utf-8")
        self.assertIn("full-covariance", content,
            "Phase 129 Part A: --full-covariance flag missing from "
            "analyze_interperson_separation.py")
        self.assertIn("diagonal", content,
            "Phase 129 Part A: --diagonal backward-compat flag missing")


if __name__ == "__main__":
    unittest.main()
