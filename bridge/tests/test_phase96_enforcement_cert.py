"""Phase 96 — Enforcement Readiness Certificate + W1 Fix tests.

Tests:
  test_1  W1 fix: pre-readiness attestation excluded from audit count
  test_2  W1 fix: post-readiness attestation counted correctly (audit_valid=True)
  test_3  insert_enforcement_certificate stores and UNIQUE(audit_hash) deduplicates
  test_4  get_latest_enforcement_certificate returns None on empty store
  test_5  POST /agent/enforcement-certificate returns cert with audit_hash and hmac_sig
  test_6  GET /agent/enforcement-certificate returns has_certificate + is_expired fields
  test_7  Expired cert still returned (is_expired=True advisory, not blocking)
  test_8  Tool #62 get_enforcement_certificate returns dict with has_certificate key

Bridge count: 1350 → 1358 (+8)
"""
import hashlib
import struct
import tempfile
import time
import unittest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p96.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey96"
    cfg.rate_limit_per_minute = 10000
    cfg.enforcement_cert_ttl_s = 86400
    return cfg


def _insert_activation_log(store, ready: int, ts: float):
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO live_mode_activation_log "
            "(event_type, ready_for_live_mode, protocol_health_score, "
            " bottleneck, blocking_conditions, created_at) VALUES (?,?,?,?,?,?)",
            ("readiness_check", ready, 90.0, None, None, ts),
        )


def _insert_gate_attestation(store, ts: float):
    h = hashlib.sha256(struct.pack(">d", ts)).hexdigest()
    with store._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO gate_attestations "
            "(attestation_hash, consecutive_clean, gate_n, divergence_rate, created_at) "
            "VALUES (?,?,?,?,?)",
            (h, 100, 100, 0.0, ts),
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestW1Fix(unittest.TestCase):

    def test_1_pre_readiness_attestation_excluded(self):
        """W1 fix: attestation before first_ready_check_at is excluded — audit_valid=False."""
        store = _make_store()
        # Attestation at t=100 (infrastructure test), readiness at t=200
        _insert_gate_attestation(store, ts=100.0)
        _insert_activation_log(store, ready=1, ts=200.0)
        result = store.get_activation_audit_summary()
        # The pre-readiness attestation must NOT count
        self.assertFalse(result["audit_valid"])
        self.assertEqual(result["gate_attestation_count"], 0,
                         "Pre-readiness attestation must be excluded from count")
        self.assertIsNone(result["latest_attestation_at"],
                          "Pre-readiness attestation must not set latest_attestation_at")

    def test_2_post_readiness_attestation_counted(self):
        """W1 fix: attestation after first_ready_check_at is counted — audit_valid=True."""
        store = _make_store()
        # Readiness at t=100, attestation at t=200 (correct order)
        _insert_activation_log(store, ready=1, ts=100.0)
        _insert_gate_attestation(store, ts=200.0)
        result = store.get_activation_audit_summary()
        self.assertTrue(result["audit_valid"])
        self.assertEqual(result["gate_attestation_count"], 1)
        self.assertAlmostEqual(result["latest_attestation_at"], 200.0, delta=1)
        self.assertIn("VALID", result["audit_summary"])


class TestEnforcementCertificateStore(unittest.TestCase):

    def test_3_insert_and_dedup(self):
        """insert_enforcement_certificate stores row; UNIQUE(audit_hash) deduplicates."""
        store = _make_store()
        id1 = store.insert_enforcement_certificate(
            audit_hash="abc123", hmac_sig="sig1", audit_valid=True,
            first_ready_check_at=100.0, gate_attestation_count=1,
            latest_attestation_at=200.0, expires_at=time.time() + 86400,
        )
        # Second insert with same audit_hash is INSERT OR IGNORE — returns None or 0
        id2 = store.insert_enforcement_certificate(
            audit_hash="abc123", hmac_sig="sig1_dup", audit_valid=True,
            first_ready_check_at=100.0, gate_attestation_count=1,
            latest_attestation_at=200.0, expires_at=time.time() + 86400,
        )
        # Only one row should exist
        with store._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM enforcement_certificates WHERE audit_hash='abc123'"
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_4_get_latest_returns_none_empty(self):
        """get_latest_enforcement_certificate returns None on empty store."""
        store = _make_store()
        self.assertIsNone(store.get_latest_enforcement_certificate())


class TestEnforcementCertEndpoints(unittest.TestCase):

    def _make_app_client(self, store, cfg):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        app = create_operator_app(cfg, store)
        return TestClient(app)

    def test_5_post_returns_cert_fields(self):
        """POST /agent/enforcement-certificate returns audit_hash and hmac_sig."""
        store = _make_store()
        cfg = _make_cfg()
        # Setup valid audit sequence
        _insert_activation_log(store, ready=1, ts=time.time() - 200)
        _insert_gate_attestation(store, ts=time.time() - 50)
        client = self._make_app_client(store, cfg)
        resp = client.post("/agent/enforcement-certificate?api_key=testkey96")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("audit_hash", data)
        self.assertIn("hmac_sig", data)
        self.assertIsNotNone(data["audit_hash"])
        self.assertGreater(len(data["audit_hash"]), 0)

    def test_6_get_returns_has_certificate_and_is_expired(self):
        """GET /agent/enforcement-certificate returns has_certificate + is_expired."""
        store = _make_store()
        cfg = _make_cfg()
        _insert_activation_log(store, ready=1, ts=time.time() - 200)
        _insert_gate_attestation(store, ts=time.time() - 50)
        client = self._make_app_client(store, cfg)
        # Issue cert first
        client.post("/agent/enforcement-certificate?api_key=testkey96")
        # Now GET it
        resp = client.get("/agent/enforcement-certificate?api_key=testkey96")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("has_certificate", data)
        self.assertIn("is_expired", data)
        self.assertTrue(data["has_certificate"])
        self.assertFalse(data["is_expired"])

    def test_7_expired_cert_returned_with_is_expired_true(self):
        """Expired cert still returned — is_expired=True (advisory, not blocking)."""
        store = _make_store()
        cfg = _make_cfg()
        # Insert an already-expired cert directly
        store.insert_enforcement_certificate(
            audit_hash="expired_hash", hmac_sig="sig_exp", audit_valid=True,
            first_ready_check_at=1.0, gate_attestation_count=1,
            latest_attestation_at=2.0, expires_at=time.time() - 3600,  # expired 1h ago
        )
        client = self._make_app_client(store, cfg)
        resp = client.get("/agent/enforcement-certificate?api_key=testkey96")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["has_certificate"])
        self.assertTrue(data["is_expired"])
        self.assertIsNotNone(data["certificate"])


class TestTool62(unittest.TestCase):

    def test_8_tool_62_returns_has_certificate(self):
        """Tool #62 get_enforcement_certificate returns dict with has_certificate key."""
        store = _make_store()
        cfg = MagicMock()
        cfg.agent_model = "claude-sonnet-4-6"
        cfg.operator_api_key = "testkey96"

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        result = agent._execute_tool("get_enforcement_certificate", {})
        self.assertIn("has_certificate", result)
        self.assertFalse(result["has_certificate"])  # empty store
