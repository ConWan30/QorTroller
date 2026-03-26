"""Phase 95 — Activation Audit Verifier tests.

Tests:
  test_1  get_activation_audit_summary returns 5 required fields on empty store
  test_2  audit_valid=False when no ready_for_live_mode=True entry exists
  test_3  audit_valid=False when ready_for_live_mode=True exists but no gate attestation
  test_4  audit_valid=True when ready_check_at < attestation_at
  test_5  audit_valid=False (chronological violation) when attestation_at < ready_check_at
  test_6  GET /agent/activation-audit returns audit_valid + timestamp

Bridge count: 1344 → 1350 (+6)
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

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p95.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey95"
    cfg.rate_limit_per_minute = 10000
    return cfg


def _insert_activation_log(store, ready: int, ts: float, score: float = 90.0):
    """Insert a live_mode_activation_log row with a specific created_at timestamp."""
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO live_mode_activation_log "
            "(event_type, ready_for_live_mode, protocol_health_score, "
            " bottleneck, blocking_conditions, created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("readiness_check", ready, score, None, None, ts),
        )


def _insert_gate_attestation(store, ts: float):
    """Insert a gate_attestations row with a specific created_at timestamp."""
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

class TestActivationAuditStore(unittest.TestCase):

    def test_1_required_fields(self):
        """get_activation_audit_summary returns 5 required keys on empty store."""
        store = _make_store()
        result = store.get_activation_audit_summary()
        for key in ("audit_valid", "first_ready_check_at",
                    "gate_attestation_count", "latest_attestation_at", "audit_summary"):
            self.assertIn(key, result)

    def test_2_invalid_no_ready_entry(self):
        """audit_valid=False when no ready_for_live_mode=True row exists."""
        store = _make_store()
        _insert_activation_log(store, ready=0, ts=time.time() - 100)
        result = store.get_activation_audit_summary()
        self.assertFalse(result["audit_valid"])
        self.assertIsNone(result["first_ready_check_at"])
        self.assertIn("NOT VALID", result["audit_summary"])

    def test_3_invalid_no_attestation(self):
        """audit_valid=False when ready entry exists but no gate attestation yet."""
        store = _make_store()
        _insert_activation_log(store, ready=1, ts=time.time() - 50)
        result = store.get_activation_audit_summary()
        self.assertFalse(result["audit_valid"])
        self.assertIsNotNone(result["first_ready_check_at"])
        self.assertEqual(result["gate_attestation_count"], 0)
        self.assertIn("No gate attestations", result["audit_summary"])

    def test_4_valid_correct_order(self):
        """audit_valid=True when ready_check_at precedes gate attestation."""
        store = _make_store()
        ready_ts = time.time() - 200
        attest_ts = time.time() - 50
        _insert_activation_log(store, ready=1, ts=ready_ts)
        _insert_gate_attestation(store, ts=attest_ts)
        result = store.get_activation_audit_summary()
        self.assertTrue(result["audit_valid"])
        self.assertAlmostEqual(result["first_ready_check_at"], ready_ts, delta=1)
        self.assertGreaterEqual(result["gate_attestation_count"], 1)
        self.assertIn("VALID", result["audit_summary"])
        self.assertIn("Chronological sequence confirmed", result["audit_summary"])

    def test_5_invalid_chronological_violation(self):
        """audit_valid=False when gate attestation predates first ready check.

        Phase 96 W1 fix: pre-readiness attestations are now excluded by the SQL filter
        (WHERE created_at >= first_ready_at), so the error is reported as
        'No gate attestations on-chain yet' rather than 'predates'. Both forms
        correctly produce audit_valid=False — the test validates the invariant,
        not the specific message.
        """
        store = _make_store()
        attest_ts = time.time() - 300   # attestation BEFORE ready check
        ready_ts = time.time() - 100
        _insert_gate_attestation(store, ts=attest_ts)
        _insert_activation_log(store, ready=1, ts=ready_ts)
        result = store.get_activation_audit_summary()
        self.assertFalse(result["audit_valid"])
        self.assertIn("NOT VALID", result["audit_summary"])


class TestActivationAuditEndpoint(unittest.TestCase):

    def test_6_endpoint_returns_audit_valid(self):
        """GET /agent/activation-audit returns audit_valid and timestamp."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        store = _make_store()
        cfg = _make_cfg()

        ready_ts = time.time() - 200
        attest_ts = time.time() - 50
        _insert_activation_log(store, ready=1, ts=ready_ts)
        _insert_gate_attestation(store, ts=attest_ts)

        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/activation-audit?api_key=testkey95")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("audit_valid", data)
        self.assertTrue(data["audit_valid"])
        self.assertIn("timestamp", data)
        self.assertGreaterEqual(data["gate_attestation_count"], 1)
