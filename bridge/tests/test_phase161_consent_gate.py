"""Phase 161 — Consent Gate Enforcement (BP-002 WIF-018/020 closure) tests.

WIF-018 (W1, CLOSED): insert_validation_record now calls _check_consent_gate when
  consent_ledger_enabled=True on Store — revoked/erasure_requested devices are blocked.
WIF-020 (W2, CLOSED): anonymize_device_records() now also redacts
  ruling_validation_log.divergence_reason (GDPR Art.17 full closure).

Tests:
  test_1  consent_gate_violation_log table created; get_consent_gate_status returns zeros
  test_2  _check_consent_gate: unknown device (no consent record) → no exception (fail-open)
  test_3  _check_consent_gate: device with consent_given=True, revoked=False → no exception
  test_4  _check_consent_gate: device with revoked=True → ValueError + violation logged
  test_5  _check_consent_gate: device with erasure_requested=True → ValueError + violation logged
  test_6  insert_validation_record blocked when erasure_requested=True and
            consent_ledger_enabled=True on Store; passes through when False (default)
  test_7  GET /agent/consent-gate-status returns 5 required keys; gate_active=True when enabled
  test_8  Tool #118 get_consent_gate_status returns dict with 5 keys including violations_total

Bridge count: 1902 -> 1910 (+8)
"""
import hashlib
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
from vapi_bridge.operator_api import create_operator_app

try:
    from starlette.testclient import TestClient
except ImportError:
    from fastapi.testclient import TestClient


def _make_store(consent_ledger_enabled: bool = False) -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p161.db"), consent_ledger_enabled=consent_ledger_enabled)


def _make_cfg(consent_ledger_enabled: bool = True):
    cfg = MagicMock()
    cfg.operator_api_key              = "testkey161"
    cfg.rate_limit_per_minute         = 10000
    cfg.agent_dry_run_mode            = True
    cfg.validation_gate_n             = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s        = 86400
    cfg.epistemic_consensus_enabled   = False
    cfg.ioswarm_adjudication_enabled  = False
    cfg.ioswarm_vhp_mint_enabled      = False
    cfg.ioswarm_enabled               = False
    cfg.poad_registry_enabled         = False
    cfg.biometric_privacy_enabled     = True
    cfg.bp001_half_life_days          = 90.0
    cfg.consent_ledger_enabled        = consent_ledger_enabled
    cfg.agent_model                   = "claude-sonnet-4-6"
    return cfg


def _insert_ruling_validation_row(store: Store, device_id: str, reason: str) -> None:
    """Helper: directly insert a ruling_validation_log row bypassing the consent gate."""
    with store._conn() as con:
        con.execute(
            "INSERT INTO ruling_validation_log"
            " (ruling_id, device_id, llm_verdict, fallback_verdict,"
            "  llm_confidence, fallback_confidence, divergence, divergence_reason, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (1, device_id, "CERTIFY", "CERTIFY", 0.9, 0.9, 0, reason, time.time()),
        )


class TestConsentGate(unittest.TestCase):

    def test_1_table_created_and_gate_status_returns_zeros(self):
        """consent_gate_violation_log table is created; get_consent_gate_status returns zeros/None."""
        store = _make_store()
        status = store.get_consent_gate_status()
        self.assertEqual(status["violations_total"], 0)
        self.assertIsNone(status["last_violation_ts"])
        self.assertIsNone(status["last_violation_device"])

    def test_2_check_consent_gate_unknown_device_no_exception(self):
        """_check_consent_gate: unknown device (not in consent_ledger) → no exception (fail-open)."""
        store = _make_store(consent_ledger_enabled=True)
        # Should not raise — unknown device is allowed (fail-open design)
        try:
            store._check_consent_gate("never_registered_device", "insert_validation_record")
        except ValueError:
            self.fail("_check_consent_gate raised ValueError for unknown device (should fail-open)")

    def test_3_check_consent_gate_consented_device_no_exception(self):
        """_check_consent_gate: device with consent_given=True, revoked=False → no exception."""
        store = _make_store(consent_ledger_enabled=True)
        store.insert_consent_record(device_id="dev161_consented", consent_given=True)
        try:
            store._check_consent_gate("dev161_consented", "insert_validation_record")
        except ValueError:
            self.fail("_check_consent_gate raised ValueError for consented device")

    def test_4_check_consent_gate_revoked_device_raises(self):
        """_check_consent_gate: device with revoked=True → ValueError + violation logged.

        revoke_consent sets both revoked=True and erasure_requested=True; gate fires on
        either condition.  Use direct SQL to simulate revoked-only (erasure_requested=False)
        to verify the consent_revoked reason path.
        """
        store = _make_store(consent_ledger_enabled=True)
        store.insert_consent_record(device_id="dev161_revoked", consent_given=True)
        # Manually set revoked_at (non-null = revoked) without erasure_requested
        # to exercise the consent_revoked reason path in _check_consent_gate
        with store._conn() as con:
            con.execute(
                "UPDATE consent_ledger SET consent_given=0, revoked_at=?, erasure_requested=0"
                " WHERE device_id=?",
                (time.time(), "dev161_revoked"),
            )
        with self.assertRaises(ValueError) as ctx:
            store._check_consent_gate("dev161_revoked", "insert_validation_record")
        self.assertIn("Consent gate", str(ctx.exception))
        self.assertIn("consent_revoked", str(ctx.exception))
        # Verify violation was logged
        status = store.get_consent_gate_status()
        self.assertEqual(status["violations_total"], 1)
        self.assertEqual(status["last_violation_device"], "dev161_revoked")

    def test_5_check_consent_gate_erasure_requested_raises(self):
        """_check_consent_gate: device with erasure_requested=True → ValueError + violation logged."""
        store = _make_store(consent_ledger_enabled=True)
        store.insert_consent_record(device_id="dev161_erasure", consent_given=True)
        store.revoke_consent(device_id="dev161_erasure", reason="gdpr_request")
        with self.assertRaises(ValueError) as ctx:
            store._check_consent_gate("dev161_erasure", "insert_validation_record")
        self.assertIn("erasure_requested", str(ctx.exception))
        status = store.get_consent_gate_status()
        self.assertGreater(status["violations_total"], 0)

    def test_6_insert_validation_record_blocked_and_passthrough(self):
        """insert_validation_record blocked (raises) when erasure_requested=True and
        consent_ledger_enabled=True; passes through when consent_ledger_enabled=False (default)."""
        # --- Gate enabled: should block ---
        store_gated = _make_store(consent_ledger_enabled=True)
        # upsert_device required before agent_rulings insert (FK constraint)
        store_gated.upsert_device("dev161_gate_test", "cc" * 32)
        with store_gated._conn() as con:
            con.execute(
                "INSERT INTO agent_rulings"
                " (device_id, verdict, confidence, reasoning, evidence_json,"
                "  commitment_hash, dry_run, source_agent, created_at, expires_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("dev161_gate_test", "CERTIFY", 0.9, "r", "{}", hashlib.sha256(b"x").hexdigest(),
                 1, "test", time.time(), time.time() + 3600),
            )
        # Register and revoke consent
        store_gated.insert_consent_record(device_id="dev161_gate_test", consent_given=True)
        store_gated.revoke_consent(device_id="dev161_gate_test", reason="test")
        with self.assertRaises(ValueError):
            store_gated.insert_validation_record(
                ruling_id=1,
                device_id="dev161_gate_test",
                llm_verdict="CERTIFY",
                fallback_verdict="CERTIFY",
                llm_confidence=0.9,
                fallback_confidence=0.9,
                divergence=0,
            )

        # --- Gate disabled (default): should pass through ---
        store_open = _make_store(consent_ledger_enabled=False)
        store_open.insert_consent_record(device_id="dev161_open_test", consent_given=True)
        store_open.revoke_consent(device_id="dev161_open_test", reason="test")
        # Should not raise
        row_id = store_open.insert_validation_record(
            ruling_id=1,
            device_id="dev161_open_test",
            llm_verdict="CERTIFY",
            fallback_verdict="CERTIFY",
            llm_confidence=0.9,
            fallback_confidence=0.9,
            divergence=0,
        )
        self.assertIsNotNone(row_id)

    def test_7_consent_gate_status_endpoint_returns_5_keys(self):
        """GET /agent/consent-gate-status returns 200 with 5 required keys; gate_active=True."""
        store = _make_store()
        cfg   = _make_cfg(consent_ledger_enabled=True)
        app   = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/consent-gate-status",
            params={"api_key": "testkey161"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in (
            "consent_ledger_enabled",
            "gate_active",
            "violations_total",
            "last_violation_ts",
            "timestamp",
        ):
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertTrue(body["consent_ledger_enabled"])
        self.assertTrue(body["gate_active"])
        self.assertEqual(body["violations_total"], 0)

    def test_8_tool_118_get_consent_gate_status_returns_required_keys(self):
        """Tool #118 get_consent_gate_status handler returns dict with 5 keys including violations_total."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg   = _make_cfg(consent_ledger_enabled=True)
        agent = BridgeAgent(cfg=cfg, store=store)

        result = agent._execute_tool("get_consent_gate_status", {})
        self.assertIsInstance(result, dict)
        for key in (
            "consent_ledger_enabled",
            "gate_active",
            "violations_total",
            "last_violation_ts",
            "timestamp",
        ):
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertEqual(result["violations_total"], 0)


if __name__ == "__main__":
    unittest.main()
