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
                  "presence", "timestamp"):
            self.assertIn(k, j)
        self.assertFalse(j["controller_connected"])
        self.assertTrue(j["enforcement_active"])
        self.assertTrue(j["host_signer_active"])
        self.assertEqual(j["is_fully_eligible"]["source"], "no_device")
        # PoEP/BCC default-OFF surfaced as pending, NOT as an error
        self.assertFalse(j["presence"]["poep"]["enabled"])
        self.assertIn("pending calibration", j["presence"]["poep"]["status"])

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


if __name__ == "__main__":
    unittest.main()
