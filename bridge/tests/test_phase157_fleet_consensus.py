"""Phase 157 — FleetConsensusSnapshotAgent + WIF-012 dual-condition + WIF-016 cov_regime.

8 tests → bridge 1868 → 1876.

Deliverables:
  WIF-012: overall_ready requires sessions_needed==0 AND defensible==True
  WIF-016: cov_stability_check() returns correct regime labels
  WIF-013: FleetConsensusSnapshotAgent computes PoFC hash + stores snapshots
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

for _m in ["anthropic", "web3", "web3.exceptions", "eth_account",
           "pydualsense", "hidapi", "hid"]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

os.chdir(tempfile.mkdtemp())

from bridge.vapi_bridge.store import Store
from bridge.vapi_bridge.enrollment_auto_guidance_agent import EnrollmentAutoGuidanceAgent
from bridge.vapi_bridge.fleet_consensus_snapshot_agent import FleetConsensusSnapshotAgent


def _make_store() -> Store:
    db_dir = tempfile.mkdtemp()
    return Store(os.path.join(db_dir, "test_p157.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key                 = "testkey157"
    cfg.rate_limit_per_minute            = 10000
    cfg.min_touchpad_sessions_per_player = 10
    cfg.capture_stagnation_window_days   = 7.0
    cfg.capture_stagnation_threshold     = 0.5
    cfg.cov_stability_margin_np          = 0.5
    cfg.fleet_consensus_enabled          = True
    cfg.fleet_consensus_snapshot_interval_s = 1800
    cfg.separation_ratio_current         = 1.261
    cfg.validation_gate_n                = 100
    cfg.validation_max_divergence_rate   = 1.0
    cfg.enforcement_cert_ttl_s           = 86400
    cfg.epistemic_consensus_enabled      = False
    cfg.agent_model                      = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache          = None
    cfg.vhp_contract_address             = ""
    cfg.layerzero_endpoint_address       = ""
    cfg.warm_up_batch_size               = 5
    cfg.stiotx_token_address             = ""
    cfg.quicksilver_collateral_address   = ""
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestWIF012DualCondition(unittest.TestCase):
    """WIF-012: overall_ready requires sessions_needed==0 AND defensible==True."""

    def test_overall_ready_requires_defensible_false(self):
        """overall_ready stays False when sessions_needed==0 but defensible==False."""
        store = _make_store()
        cfg   = _make_cfg()
        agent = EnrollmentAutoGuidanceAgent(cfg, store)

        # Mock: Phase 151 says ready (sessions_needed=0), Phase 150 says not defensible
        mock_guidance = {"sessions_needed_total": 0, "overall_ready": True}
        mock_defensibility = {"defensible": False, "ratio": 0.8, "n_per_player": {"P1": 3, "P2": 4, "P3": 4}}

        with patch.object(store, "get_enrollment_capture_guidance", return_value=mock_guidance), \
             patch.object(store, "get_separation_defensibility_status", return_value=mock_defensibility), \
             patch.object(store, "compute_capture_stagnation", return_value={"stagnant": False, "sessions_per_day": 0.5}), \
             patch.object(store, "compute_centroid_velocity", return_value={"stagnant": False}):
            report = agent._synthesize_guidance()

        # WIF-012: defensible=False → overall_ready=False even when guidance says ready
        self.assertFalse(report["overall_ready"])

    def test_overall_ready_both_conditions_met(self):
        """overall_ready=True when sessions_needed==0 AND defensible==True."""
        store = _make_store()
        cfg   = _make_cfg()
        agent = EnrollmentAutoGuidanceAgent(cfg, store)

        mock_guidance     = {"sessions_needed_total": 0, "overall_ready": True}
        mock_defensibility = {"defensible": True, "ratio": 1.261, "n_per_player": {"P1": 10, "P2": 10, "P3": 10}}

        with patch.object(store, "get_enrollment_capture_guidance", return_value=mock_guidance), \
             patch.object(store, "get_separation_defensibility_status", return_value=mock_defensibility), \
             patch.object(store, "compute_capture_stagnation", return_value={"stagnant": False, "sessions_per_day": 1.0}), \
             patch.object(store, "compute_centroid_velocity", return_value={"stagnant": False}):
            report = agent._synthesize_guidance()

        # Both conditions met → overall_ready=True
        self.assertTrue(report["overall_ready"])


class TestWIF016CovStability(unittest.TestCase):
    """WIF-016: cov_stability_check() returns correct regime labels."""

    def test_cov_stability_diagonal_stable(self):
        """N/p=1.375 (current: N=11, p=8) → 'diagonal_stable'."""
        result = EnrollmentAutoGuidanceAgent._cov_stability_check(
            cov_np_ratio=1.375, cov_min_ratio=3.0, margin=0.5
        )
        self.assertEqual(result, "diagonal_stable")

    def test_cov_stability_transition_warning(self):
        """N/p=3.1 (N=24.8, p=8 — within margin band) → 'transition_warning'."""
        result = EnrollmentAutoGuidanceAgent._cov_stability_check(
            cov_np_ratio=3.1, cov_min_ratio=3.0, margin=0.5
        )
        self.assertEqual(result, "transition_warning")

    def test_cov_stability_full_covariance_active(self):
        """N/p=4.0 (N=32, p=8 — past margin) → 'full_covariance_active'."""
        result = EnrollmentAutoGuidanceAgent._cov_stability_check(
            cov_np_ratio=4.0, cov_min_ratio=3.0, margin=0.5
        )
        self.assertEqual(result, "full_covariance_active")


class TestWIF013FleetConsensusSnapshot(unittest.TestCase):
    """WIF-013: FleetConsensusSnapshotAgent PoFC hash + store."""

    def test_fleet_consensus_insert_roundtrip(self):
        """Insert a snapshot and retrieve it."""
        store   = _make_store()
        pofc_h  = "a" * 64
        row_id  = store.insert_fleet_consensus_snapshot(
            pofc_hash        = pofc_h,
            agent_count      = 5,
            separation_ratio = 1.261,
            verdict_summary  = {"CERTIFY": 4, "NOMINAL": 1},
        )
        self.assertIsInstance(row_id, int)
        self.assertGreater(row_id, 0)

        snaps = store.get_fleet_consensus_snapshot(limit=1)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["pofc_hash"], pofc_h)
        self.assertEqual(snaps[0]["agent_count"], 5)
        self.assertAlmostEqual(snaps[0]["separation_ratio"], 1.261, places=3)

    def test_fleet_consensus_pofc_hash_is_sha256(self):
        """compute_pofc_hash returns 64-char lowercase hex SHA-256 digest."""
        sorted_verdicts = [("dev_abc", "CERTIFY"), ("dev_xyz", "NOMINAL")]
        sep_ratio       = 1.261
        ts_ns           = 1712270400_000_000_000

        result = FleetConsensusSnapshotAgent.compute_pofc_hash(
            sorted_verdicts, sep_ratio, ts_ns
        )
        self.assertEqual(len(result), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in result))

        # Deterministic: same inputs → same hash
        result2 = FleetConsensusSnapshotAgent.compute_pofc_hash(
            sorted_verdicts, sep_ratio, ts_ns
        )
        self.assertEqual(result, result2)

    def test_fleet_consensus_endpoint_6_keys(self):
        """GET /agent/fleet-consensus-snapshot returns 6 required keys."""
        store = _make_store()
        cfg   = _make_cfg()

        from bridge.vapi_bridge.operator_api import create_operator_app
        try:
            from starlette.testclient import TestClient
        except ImportError:
            from fastapi.testclient import TestClient

        app    = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/agent/fleet-consensus-snapshot",
                          params={"api_key": "testkey157"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("fleet_consensus_enabled", "total_snapshots", "latest_pofc_hash",
                    "latest_agent_count", "latest_separation_ratio", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")

    def test_fleet_consensus_tool_113(self):
        """Tool #113 get_fleet_consensus_snapshot returns dict with required keys."""
        store = _make_store()
        cfg   = _make_cfg()

        store.insert_fleet_consensus_snapshot(
            pofc_hash        = "b" * 64,
            agent_count      = 3,
            separation_ratio = 0.417,
        )

        from bridge.vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_fleet_consensus_snapshot", {})
        self.assertIn("fleet_consensus_enabled", result)
        self.assertIn("total_snapshots", result)
        self.assertIn("latest_pofc_hash", result)
        self.assertGreater(result["total_snapshots"], 0)


if __name__ == "__main__":
    unittest.main()
