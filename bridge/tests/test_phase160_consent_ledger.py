"""Phase 160 — Consent Ledger + Right-to-Erasure (BP-002 foundation) tests.

WIF-018 (W1): Biometric data used after consent revocation — no consent gate in
  defensibility pipeline before Phase 160.
WIF-019 (W2): Consent Ledger as composable privacy primitive.

Tests:
  test_1  consent_ledger table created; get_consent_status returns not-found defaults
  test_2  insert_consent_record + get_consent_status roundtrip (consent_given=True)
  test_3  revoke_consent sets revoked=True + erasure_requested=True
  test_4  mark_erasure_complete anonymizes pitl_session_proofs rows and logs erasure
  test_5  anonymize_device_records returns correct row count
  test_6  GET /agent/consent-status/{device_id} returns 7 required keys (200)
  test_7  POST /agent/register-consent returns registered=True
  test_8  Tool #117 get_consent_status returns 7 keys including consent_ledger_enabled

Bridge count: 1894 -> 1902 (+8)
"""
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


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p160.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key          = "testkey160"
    cfg.rate_limit_per_minute     = 10000
    cfg.agent_dry_run_mode        = True
    cfg.validation_gate_n         = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s    = 86400
    cfg.epistemic_consensus_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.ioswarm_vhp_mint_enabled  = False
    cfg.ioswarm_enabled           = False
    cfg.poad_registry_enabled     = False
    cfg.biometric_privacy_enabled = True
    cfg.bp001_half_life_days      = 90.0
    cfg.consent_ledger_enabled    = True
    cfg.agent_model               = "claude-sonnet-4-6"
    return cfg


class TestConsentLedger(unittest.TestCase):

    def test_1_table_created_and_defaults_not_found(self):
        """consent_ledger table is created; unknown device returns not-found defaults."""
        store = _make_store()
        result = store.get_consent_status("unknown_device_p160")
        self.assertFalse(result["found"])
        self.assertFalse(result["consent_given"])
        self.assertIsNone(result["consent_ts"])
        self.assertFalse(result["revoked"])
        self.assertFalse(result["erasure_requested"])
        self.assertFalse(result["erasure_completed"])

    def test_2_insert_consent_record_roundtrip(self):
        """insert_consent_record stores consent_given=True; get_consent_status returns it."""
        store = _make_store()
        _ts = time.time()
        store.insert_consent_record(
            device_id="dev_p160_a",
            consent_type="biometric_processing",
            consent_given=True,
            consent_ts=_ts,
        )
        result = store.get_consent_status("dev_p160_a")
        self.assertTrue(result["found"])
        self.assertTrue(result["consent_given"])
        self.assertAlmostEqual(result["consent_ts"], _ts, places=0)
        self.assertFalse(result["revoked"])

    def test_3_revoke_consent_sets_flags(self):
        """revoke_consent sets consent_given=False, revoked=True, erasure_requested=True."""
        store = _make_store()
        store.insert_consent_record(
            device_id="dev_p160_b",
            consent_given=True,
        )
        updated = store.revoke_consent(
            device_id="dev_p160_b",
            reason="player_requested",
        )
        self.assertTrue(updated)
        result = store.get_consent_status("dev_p160_b")
        self.assertFalse(result["consent_given"])
        self.assertTrue(result["revoked"])
        self.assertEqual(result["revocation_reason"], "player_requested")
        self.assertTrue(result["erasure_requested"])

    def test_4_mark_erasure_complete_anonymizes_and_logs(self):
        """mark_erasure_complete sets erasure_completed=True and logs to right_to_erasure_log."""
        store = _make_store()
        store.insert_consent_record(device_id="dev_p160_c", consent_given=True)
        store.revoke_consent(device_id="dev_p160_c", reason="test")
        # Register device + insert a dummy agent_rulings row to verify anonymization
        store.upsert_device("dev_p160_c", "aa" * 32)
        import hashlib as _hs
        _hash = _hs.sha256(b"test_p160_c").hexdigest()
        with store._conn() as con:
            con.execute(
                "INSERT INTO agent_rulings"
                " (device_id, verdict, confidence, reasoning, evidence_json,"
                "  commitment_hash, dry_run, source_agent, created_at, expires_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("dev_p160_c", "CERTIFY", 0.95, "human", '{"test":1}',
                 _hash, 1, "test", time.time(), time.time() + 3600),
            )
        fields = store.mark_erasure_complete("dev_p160_c")
        self.assertEqual(fields, 1)
        status = store.get_consent_status("dev_p160_c")
        self.assertTrue(status["erasure_completed"])
        log = store.get_erasure_log("dev_p160_c")
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["fields_anonymized"], 1)

    def test_5_anonymize_device_records_returns_row_count(self):
        """anonymize_device_records returns count of rows anonymized in agent_rulings."""
        store = _make_store()
        store.upsert_device("dev_anon_p160", "bb" * 32)
        import hashlib as _hs
        with store._conn() as con:
            for i in range(3):
                _hash = _hs.sha256(f"test_anon_{i}".encode()).hexdigest()
                con.execute(
                    "INSERT INTO agent_rulings"
                    " (device_id, verdict, confidence, reasoning, evidence_json,"
                    "  commitment_hash, dry_run, source_agent, created_at, expires_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("dev_anon_p160", "CERTIFY", 0.9, "human", "{}",
                     _hash, 1, "test", time.time(), time.time() + 3600),
                )
        count = store.anonymize_device_records("dev_anon_p160")
        self.assertEqual(count, 3)

    def test_6_consent_status_endpoint_returns_7_keys(self):
        """GET /agent/consent-status/{device_id} returns 200 with 7 required keys."""
        store = _make_store()
        cfg   = _make_cfg()
        app   = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/consent-status/dev_endpoint_p160",
            params={"api_key": "testkey160"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in (
            "consent_ledger_enabled",
            "consent_given",
            "consent_ts",
            "revoked",
            "erasure_requested",
            "erasure_completed",
            "timestamp",
        ):
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertTrue(body["consent_ledger_enabled"])
        self.assertFalse(body["consent_given"])

    def test_7_register_consent_endpoint_returns_registered_true(self):
        """POST /agent/register-consent returns registered=True for a new device."""
        store = _make_store()
        cfg   = _make_cfg()
        app   = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/agent/register-consent",
            params={"device_id": "dev_reg_p160", "api_key": "testkey160"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["registered"])
        self.assertEqual(body["device_id"], "dev_reg_p160")
        self.assertIn("consent_ts", body)

        # Verify stored
        status = store.get_consent_status("dev_reg_p160")
        self.assertTrue(status["found"])
        self.assertTrue(status["consent_given"])

    def test_8_tool_117_get_consent_status_returns_required_keys(self):
        """Tool #117 get_consent_status handler returns dict with 7 keys including consent_ledger_enabled."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg   = _make_cfg()
        agent = BridgeAgent(cfg=cfg, store=store)

        result = agent._execute_tool("get_consent_status", {"device_id": "dev_tool_p160"})
        self.assertIsInstance(result, dict)
        for key in (
            "consent_ledger_enabled",
            "consent_given",
            "consent_ts",
            "revoked",
            "erasure_requested",
            "erasure_completed",
            "timestamp",
        ):
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertTrue(result["consent_ledger_enabled"])


if __name__ == "__main__":
    unittest.main()
