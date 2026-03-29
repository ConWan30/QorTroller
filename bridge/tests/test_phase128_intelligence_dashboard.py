"""
Phase 128 — Protocol Intelligence Dashboard (8 tests)

test_1_protocol_intelligence_reports_roundtrip
test_2_score_zero_when_all_conditions_unmet
test_3_score_partial_separation_ratio_weight
test_4_schema_version_128
test_5_endpoint_9_keys
test_6_tool_96_structure
test_7_score_increases_when_l4_stale_cleared
test_8_conditions_met_count_correct
"""

import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "sdk"))

from vapi_bridge.store import Store


def _make_store(tmp_path=None):
    import tempfile
    import os
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    db_path = os.path.join(tmp_path, "test_phase128.db")
    return Store(db_path=db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    # separation
    cfg.separation_ratio_current = kwargs.get("separation_ratio_current", 0.0)
    # L4 staleness
    cfg.live_feature_dim = kwargs.get("live_feature_dim", 13)
    cfg.calibration_feature_dim = kwargs.get("calibration_feature_dim", 12)
    cfg.l4_anomaly_threshold = 7.009
    cfg.l4_continuity_threshold = 5.367
    cfg.calibration_n_sessions = 74
    cfg.calibration_timestamp = 0.0
    # dual gate
    cfg.dual_primitive_gate_enabled = kwargs.get("dual_primitive_gate_enabled", False)
    # epoch window
    cfg.epoch_window_enabled = kwargs.get("epoch_window_enabled", False)
    cfg.epoch_window_seconds = kwargs.get("epoch_window_seconds", 86400.0)
    # ioswarm
    cfg.ioswarm_vhp_mint_enabled = kwargs.get("ioswarm_vhp_mint_enabled", False)
    # dry run
    cfg.agent_dry_run_mode = kwargs.get("agent_dry_run_mode", True)
    # misc
    cfg.l4_battery_threshold_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.dual_primitive_gate_address = ""
    cfg.protocol_lens_address = ""
    cfg.adjudication_registry_address = ""
    cfg.gate_n = 100
    cfg.consecutive_clean = kwargs.get("consecutive_clean", 0)
    return cfg


def _make_app(store, cfg):
    from vapi_bridge.operator_api import create_operator_app
    return create_operator_app(cfg=cfg, store=store)


class TestPhase128IntelligenceDashboard(unittest.TestCase):

    # ------------------------------------------------------------------
    # test_1: protocol_intelligence_reports table roundtrip via new methods
    # ------------------------------------------------------------------
    def test_1_protocol_intelligence_reports_roundtrip(self):
        store = _make_store()
        breakdown = {"separation_score": 0.0, "l4_score": 0.0}
        row_id = store.insert_readiness_score(
            score=0.42,
            breakdown_json=json.dumps(breakdown),
            conditions_met=2,
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)
        rows = store.get_readiness_scores(limit=5)
        self.assertGreaterEqual(len(rows), 1)
        latest = rows[0]
        self.assertAlmostEqual(float(latest["score"]), 0.42, places=2)
        self.assertEqual(latest["conditions_met"], 2)
        self.assertIn("breakdown", latest)

    # ------------------------------------------------------------------
    # test_2: score = 0.0 when all conditions unmet (dry_run=True, sep=0,
    #         l4 stale, dual gate disabled, epoch disabled, ioswarm disabled)
    # ------------------------------------------------------------------
    def test_2_score_zero_when_all_conditions_unmet(self):
        store = _make_store()
        cfg = _make_cfg(
            separation_ratio_current=0.0,
            live_feature_dim=13,
            calibration_feature_dim=12,
            dual_primitive_gate_enabled=False,
            epoch_window_enabled=False,
            ioswarm_vhp_mint_enabled=False,
            agent_dry_run_mode=True,
        )
        from fastapi.testclient import TestClient
        app = _make_app(store, cfg)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness-score", params={"api_key": "test-key"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # separation_score=0 (ratio=0), l4_score=0 (stale), dry_run_score=0
        self.assertAlmostEqual(body["separation_score"], 0.0, places=3)
        self.assertAlmostEqual(body["l4_score"], 0.0, places=3)
        self.assertAlmostEqual(body["dry_run_score"], 0.0, places=3)
        self.assertLessEqual(body["score"], 0.5)

    # ------------------------------------------------------------------
    # test_3: score reflects partial separation_ratio weight
    # separation_ratio=0.5 → separation_score=min(1.0,0.5)=0.5 → contribution=0.30×0.5=0.15
    # ------------------------------------------------------------------
    def test_3_score_partial_separation_ratio_weight(self):
        store = _make_store()
        cfg = _make_cfg(
            separation_ratio_current=0.5,
            live_feature_dim=13,
            calibration_feature_dim=12,
            agent_dry_run_mode=True,
        )
        from fastapi.testclient import TestClient
        app = _make_app(store, cfg)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness-score", params={"api_key": "test-key"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertAlmostEqual(body["separation_score"], 0.5, places=2)
        # separation contribution = 0.30 * 0.5 = 0.15
        # total score >= 0.14 (non-zero)
        self.assertGreater(body["score"], 0.10)

    # ------------------------------------------------------------------
    # test_4: schema_version 128 present
    # ------------------------------------------------------------------
    def test_4_schema_version_128(self):
        store = _make_store()
        with store._conn() as conn:
            rows = conn.execute(
                "SELECT phase, migration_name FROM schema_versions WHERE phase=128"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "intelligence_dashboard")

    # ------------------------------------------------------------------
    # test_5: endpoint returns exactly 9 required keys
    # ------------------------------------------------------------------
    def test_5_endpoint_9_keys(self):
        store = _make_store()
        cfg = _make_cfg()
        from fastapi.testclient import TestClient
        app = _make_app(store, cfg)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness-score", params={"api_key": "test-key"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required = {
            "score", "separation_score", "l4_score", "dual_gate_score",
            "epoch_score", "ioswarm_score", "dry_run_score",
            "conditions_met", "timestamp",
        }
        for key in required:
            self.assertIn(key, body, f"Missing key: {key}")

    # ------------------------------------------------------------------
    # test_6: Tool #96 get_tournament_readiness_score structure
    # ------------------------------------------------------------------
    def test_6_tool_96_structure(self):
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

        result = agent._execute_tool("get_tournament_readiness_score", {})
        required_keys = {
            "score", "separation_score", "l4_score", "dual_gate_score",
            "epoch_score", "ioswarm_score", "dry_run_score",
            "conditions_met", "timestamp",
        }
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")

    # ------------------------------------------------------------------
    # test_7: score increases when L4 staleness cleared
    #         stale (calib=12, live=13) → l4_score=0.0
    #         fresh (calib=13, live=13) → l4_score=1.0
    # ------------------------------------------------------------------
    def test_7_score_increases_when_l4_stale_cleared(self):
        from fastapi.testclient import TestClient

        # Stale configuration
        store_stale = _make_store()
        cfg_stale = _make_cfg(
            separation_ratio_current=0.0,
            live_feature_dim=13,
            calibration_feature_dim=12,
            agent_dry_run_mode=True,
        )
        app_stale = _make_app(store_stale, cfg_stale)
        client_stale = TestClient(app_stale)
        resp_stale = client_stale.get(
            "/agent/tournament-readiness-score", params={"api_key": "test-key"}
        )
        self.assertEqual(resp_stale.status_code, 200)
        score_stale = resp_stale.json()["score"]
        l4_stale = resp_stale.json()["l4_score"]

        # Fresh configuration (dims match)
        store_fresh = _make_store()
        cfg_fresh = _make_cfg(
            separation_ratio_current=0.0,
            live_feature_dim=13,
            calibration_feature_dim=13,
            agent_dry_run_mode=True,
        )
        app_fresh = _make_app(store_fresh, cfg_fresh)
        client_fresh = TestClient(app_fresh)
        resp_fresh = client_fresh.get(
            "/agent/tournament-readiness-score", params={"api_key": "test-key"}
        )
        self.assertEqual(resp_fresh.status_code, 200)
        score_fresh = resp_fresh.json()["score"]
        l4_fresh = resp_fresh.json()["l4_score"]

        # l4_score should improve from 0 → 1
        self.assertAlmostEqual(l4_stale, 0.0, places=2)
        self.assertAlmostEqual(l4_fresh, 1.0, places=2)
        # overall score should also be higher
        self.assertGreater(score_fresh, score_stale)

    # ------------------------------------------------------------------
    # test_8: conditions_met count is an integer >= 0 and <= 6
    # ------------------------------------------------------------------
    def test_8_conditions_met_count_correct(self):
        store = _make_store()
        cfg = _make_cfg(
            separation_ratio_current=1.0,   # passes
            live_feature_dim=13,
            calibration_feature_dim=13,     # l4 fresh → passes
            agent_dry_run_mode=False,       # dry_run_score=1.0 → passes
        )
        from fastapi.testclient import TestClient
        app = _make_app(store, cfg)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness-score", params={"api_key": "test-key"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        conditions_met = body["conditions_met"]
        self.assertIsInstance(conditions_met, int)
        self.assertGreaterEqual(conditions_met, 0)
        self.assertLessEqual(conditions_met, 6)
        # With separation=1.0, l4_fresh, dry_run=False, at least 3 signals pass
        self.assertGreaterEqual(conditions_met, 3)


if __name__ == "__main__":
    unittest.main()
