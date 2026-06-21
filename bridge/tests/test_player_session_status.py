"""
Gameplay Workflow Layer — GET /player/session-status (Phase 3 Path B, Commit 1)

Single-glance "am I verified?" endpoint. Read-only composition over existing surfaces;
adds no new capture/adjudication authority. Every chain call is a pure VIEW (kill-switch safe).

T-PSS-1: 200 + full shape on an empty DB (no device resolvable); enforcement flag surfaced.
T-PSS-2: humanity_prob (records.pitl_humanity_prob) + connection state reflect the latest record.
T-PSS-3: is_fully_eligible.onchain reflects the on-chain lens view; bridge_local reflects the store proxy.
T-PSS-4: gic_chain.length and records_count.total are DISTINCT fields (the 637k-vs-100 conflation guard).
T-PSS-5: on-chain failure → onchain=None, source="unavailable", HTTP 200 (offline/kill-switch safe — never a 500).
"""

import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

# Path A Arc 1 C3 fix (2026-05-27): only install stub modules when the real ones
# CAN'T be imported. Prior version unconditionally stubbed if not in sys.modules,
# which on cold pytest start meant the REAL web3 (installed in the bridge env) got
# replaced with empty stubs — breaking subsequent tests that import chain.py and
# need real AsyncWeb3. Try real import first; fall back to stub only on ImportError.
for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local"]:
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ImportError:
            sys.modules[_mod] = types.ModuleType(_mod)

_KEY = "psstestkey"
_H = {"x-api-key": _KEY}


def _make_store():
    from vapi_bridge.store import Store
    return Store(str(Path(tempfile.mkdtemp()) / "test_pss.db"))


def _make_cfg(**kw):
    from vapi_bridge.config import Config
    defaults = dict(
        operator_api_key=_KEY,
        grind_session_id="grind_test_pss",
        ipact_renewal_enforcement_enabled=True,
        ipact_host_signer_enabled=True,
    )
    defaults.update(kw)
    return Config(**defaults)


def _client(cfg, store, chain=None):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app
    app = create_operator_app(cfg, store, chain=chain)
    return TestClient(app, raise_server_exceptions=False)


class TestPlayerSessionStatus(unittest.TestCase):

    def test_1_empty_db_shape(self):
        """T-PSS-1: 200 + full shape with no resolvable device; enforcement flag surfaced True."""
        cfg, store = _make_cfg(), _make_store()
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        for k in ("controller_connected", "session_active", "is_fully_eligible",
                  "dual_eligible", "vhp_status", "gic_chain", "records_count",
                  "enforcement_active", "host_signer_active", "last_adjudication",
                  "presence", "cco", "identity_grid", "signing_path", "path_a_eligible",
                  "timestamp"):
            self.assertIn(k, j)
        self.assertIn("dormant", j["presence"]["poep"])
        self.assertIsNone(j["identity_grid"]["presence_ceiling_candidate"])
        self.assertFalse(j["controller_connected"])
        self.assertTrue(j["enforcement_active"])
        self.assertTrue(j["host_signer_active"])
        self.assertEqual(j["is_fully_eligible"]["source"], "no_device")
        # PoEP/BCC default-OFF surfaced as pending, NOT as an error
        self.assertFalse(j["presence"]["poep"]["enabled"])
        self.assertTrue(j["presence"]["poep"]["dormant"])
        self.assertIn("pending L6B calibration", j["presence"]["poep"]["status"])

    def test_2_humanity_and_connection(self):
        """T-PSS-2: latest record drives humanity_prob + connection + PITL snapshot."""
        cfg, store = _make_cfg(), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.87, "inference": 32,
             "pitl_l4_distance": 3.1, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {
            "capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000.0}
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["device_id"], "devX")
        self.assertAlmostEqual(j["humanity_prob"], 0.87)
        self.assertTrue(j["controller_connected"])
        self.assertTrue(j["session_active"])
        self.assertTrue(j["pitl_layers"]["nominal"])
        self.assertAlmostEqual(j["pitl_layers"]["l4_distance"], 3.1)

    def test_3_onchain_and_local_eligibility(self):
        """T-PSS-3: on-chain lens view (primary) + bridge-local proxy, labeled distinctly."""
        cfg, store = _make_cfg(), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.9, "inference": 32, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}
        store.get_enrollment = lambda d: {"device_id": d}
        store.get_credential_mint = lambda d: {"credential_id": 1}
        store.is_credential_suspended = lambda d: False
        chain = AsyncMock()
        chain.is_fully_eligible = AsyncMock(return_value=True)
        r = _client(cfg, store, chain=chain).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIs(j["is_fully_eligible"]["onchain"], True)
        self.assertEqual(j["is_fully_eligible"]["source"], "onchain")
        self.assertTrue(j["is_fully_eligible"]["bridge_local"])
        chain.is_fully_eligible.assert_awaited()

    def test_4_gic_and_records_are_distinct(self):
        """T-PSS-4: gic_chain.length (~100) must not be conflated with records_count.total (637k)."""
        cfg, store = _make_cfg(), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {"capture_state": "NOMINAL"}
        store.get_grind_chain_status = lambda sid, c=None: {
            "chain_length": 100, "chain_intact": True, "latest_gic_hash": "ab12cd"}
        store.count_records = lambda device_id=None: (637420 if device_id is None else 12000)
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual(j["gic_chain"]["length"], 100)
        self.assertEqual(j["gic_chain"]["integrity"], "intact")
        self.assertEqual(j["records_count"]["total"], 637420)
        self.assertEqual(j["records_count"]["device"], 12000)
        self.assertNotEqual(j["gic_chain"]["length"], j["records_count"]["total"])

    def test_5_onchain_failure_is_safe(self):
        """T-PSS-5: RPC/offline failure → onchain=None, source=unavailable, HTTP 200 (never 500)."""
        cfg, store = _make_cfg(), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {"capture_state": "NOMINAL"}
        chain = AsyncMock()
        chain.is_fully_eligible = AsyncMock(side_effect=RuntimeError("rpc down"))
        r = _client(cfg, store, chain=chain).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertIsNone(j["is_fully_eligible"]["onchain"])
        self.assertEqual(j["is_fully_eligible"]["source"], "unavailable")

    def test_6_wrong_key_rejected(self):
        """T-PSS-6: read-key auth — wrong x-api-key returns 403 when OPERATOR_API_KEY configured."""
        cfg, store = _make_cfg(), _make_store()
        r = _client(cfg, store).get("/player/session-status", headers={"x-api-key": "wrong"})
        self.assertEqual(r.status_code, 403)

    def test_7_cco_surface_present(self):
        """T-PSS-7: CCO Phase B.2 — cco block with L6B calibration + oracle fields."""
        cfg, store = _make_cfg(l6b_enabled=True), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.9, "inference": 32, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {
            "capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000.0}
        store.get_l6b_calibration_progress = lambda device_id=None: {
            "probe_count": 59,
            "target_n": 50,
            "gate_reached": True,
            "reflex_verdict_distribution": {"REFLEX_OBSERVED": 38},
            "latest_probe": {"reflex_verdict": "REFLEX_OBSERVED", "classification": "HUMAN"},
        }
        store.count_records = lambda device_id=None: 1
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        cco = r.json()["cco"]
        self.assertTrue(cco["l6b_enabled"])
        self.assertEqual(cco["t0_engine"], "L6B")
        self.assertEqual(cco["reflex_verdict"], "REFLEX_OBSERVED")
        self.assertTrue(cco["calibration"]["gate_reached"])
        poep = r.json()["presence"]["poep"]
        self.assertFalse(poep["enabled"])
        self.assertTrue(poep["dormant"])
        self.assertIsNone(poep["verdict"])
        self.assertEqual(poep["challenge_type"], "adaptive_force")
        self.assertTrue(poep["l6b_gate_reached"])

    def test_11_dualsense_profile_rumble_imu_poep(self):
        """T-PSS-11: DEVICE_PROFILE_ID=sony_dualsense_v1 → rumble_imu + telemetry from probe."""
        cfg, store = _make_cfg(
            l6b_enabled=True,
            device_profile_id="sony_dualsense_v1",
        ), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.9, "inference": 32, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {
            "capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000.0}
        store.get_l6b_calibration_progress = lambda device_id=None: {
            "probe_count": 52,
            "target_n": 50,
            "gate_reached": True,
            "latest_probe": {
                "latency_ms": 185.0,
                "accel_delta_peak": 1100.0,
                "classification": "HUMAN",
            },
        }
        store.count_records = lambda device_id=None: 1
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        poep = r.json()["presence"]["poep"]
        self.assertEqual(poep["challenge_type"], "rumble_imu")
        self.assertEqual(poep["runner"]["profile_id"], "sony_dualsense_v1")
        self.assertTrue(poep["telemetry"]["ready"])
        self.assertIsNone(poep["telemetry"]["gap"])

    def test_8_identity_grid_phase_e(self):
        """T-PSS-8: CCO Phase E — identity_grid four-field composable surface."""
        cfg, store = _make_cfg(l6b_enabled=True), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.9, "inference": 32, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {
            "capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000.0}
        store.get_l6b_calibration_progress = lambda device_id=None: {"probe_count": 0, "target_n": 50}
        store.count_records = lambda device_id=None: 1
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        j = r.json()
        grid = j["identity_grid"]
        cco = j["cco"]
        self.assertEqual(grid["schema"], "qortroller-identity-grid-v1")
        self.assertEqual(grid["presence_ceiling_candidate"], cco["presence_ceiling_candidate"])
        self.assertEqual(grid["identity_class"], cco["identity_class"])
        self.assertIn("signing_path", grid)
        self.assertIn("path_a_eligible", grid)
        self.assertFalse(grid["composable_on_chain"])
        self.assertEqual(j["signing_path"], grid["signing_path"])
        self.assertEqual(j["path_a_eligible"], grid["path_a_eligible"])

    def test_9_composability_phase_f(self):
        """T-PSS-9: CCO Phase F — composability prep on identity_grid (deploy-hold)."""
        cfg, store = _make_cfg(cco_composability_enabled=False), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.9, "inference": 32, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {
            "capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000.0}
        store.get_l6b_calibration_progress = lambda device_id=None: {"probe_count": 0, "target_n": 50}
        store.count_records = lambda device_id=None: 1
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        grid = r.json()["identity_grid"]
        self.assertIn("composability", grid)
        comp = grid["composability"]
        self.assertEqual(comp["schema"], "qortroller-composability-v1")
        self.assertFalse(comp["enabled"])
        self.assertEqual(comp["readiness"], "disabled")
        self.assertFalse(grid["composable_on_chain"])
        self.assertEqual(comp["option"], "F1")

    def test_10_controller_class_research_phase_g(self):
        """T-PSS-10: CCO Phase G — research scaffold on identity_grid (default-OFF)."""
        cfg, store = _make_cfg(cco_research_surface_enabled=False), _make_store()
        store.get_recent_records = lambda limit, device_id=None: [
            {"device_id": "devX", "pitl_humanity_prob": 0.9, "inference": 32, "created_at": time.time()}]
        store.get_capture_health_status = lambda limit=10: {
            "capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB", "poll_rate_hz": 1000.0}
        store.get_l6b_calibration_progress = lambda device_id=None: {"probe_count": 0, "target_n": 50}
        store.count_records = lambda device_id=None: 1
        r = _client(cfg, store).get("/player/session-status", headers=_H)
        self.assertEqual(r.status_code, 200)
        research = r.json()["identity_grid"]["controller_class_research"]
        self.assertEqual(research["schema"], "qortroller-controller-class-research-v1")
        self.assertFalse(research["enabled"])
        self.assertEqual(research["grade"], "DISABLED")


if __name__ == "__main__":
    unittest.main()
