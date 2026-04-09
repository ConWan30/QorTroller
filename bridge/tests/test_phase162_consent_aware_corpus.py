"""Phase 162 — Consent-Aware Corpus Status (WIF-021 closure) tests.

WIF-021 (W1, CLOSED): get_separation_defensibility_status() and the corpus analysis
  script did not filter revoked-consent devices before computing separation ratio. A
  player who revokes consent continues to contribute biometric sessions to the corpus.

Phase 162 adds get_consent_corpus_coverage() and get_active_consent_devices() to
Store, plus GET /agent/consent-aware-corpus-status (6 keys) and Tool #119.

Tests:
  test_1  get_consent_corpus_coverage returns zeros on empty store
  test_2  get_active_consent_devices returns only active-consent devices
  test_3  consent_corpus_defensible=True when all registered devices have active consent
  test_4  consent_corpus_defensible=False when any device has revoked consent
  test_5  consent_corpus_defensible=False when any device has erasure_requested=True
  test_6  revoked_count and erasure_requested_count are independently tracked
  test_7  GET /agent/consent-aware-corpus-status returns 6 required keys
  test_8  Tool #119 get_consent_aware_corpus_status returns dict with 6 keys

Bridge count: 1910 -> 1918 (+8)
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


def _make_store(consent_ledger_enabled: bool = True) -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p162.db"), consent_ledger_enabled=consent_ledger_enabled)


def _make_cfg(consent_ledger_enabled: bool = True):
    cfg = MagicMock()
    cfg.operator_api_key              = "testkey162"
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


class TestConsentAwareCorpus(unittest.TestCase):

    def test_1_coverage_zeros_on_empty_store(self):
        """get_consent_corpus_coverage returns zeros and defensible=False on empty store."""
        store = _make_store()
        cov = store.get_consent_corpus_coverage()
        self.assertEqual(cov["total_registered"], 0)
        self.assertEqual(cov["active_consent_count"], 0)
        self.assertEqual(cov["revoked_count"], 0)
        self.assertEqual(cov["erasure_requested_count"], 0)
        self.assertFalse(cov["consent_corpus_defensible"])

    def test_2_get_active_consent_devices_filters_correctly(self):
        """get_active_consent_devices returns only devices with active consent."""
        store = _make_store()
        # Insert two devices: one consented, one revoked
        store.insert_consent_record(device_id="dev162_active", consent_given=True)
        store.insert_consent_record(device_id="dev162_revoke", consent_given=True)
        store.revoke_consent(device_id="dev162_revoke", reason="test_revoke")

        active = store.get_active_consent_devices()
        device_ids = {r["device_id"] for r in active}
        self.assertIn("dev162_active", device_ids)
        self.assertNotIn("dev162_revoke", device_ids)

    def test_3_defensible_true_when_all_active(self):
        """consent_corpus_defensible=True when all devices have active consent."""
        store = _make_store()
        store.insert_consent_record(device_id="dev162_a", consent_given=True)
        store.insert_consent_record(device_id="dev162_b", consent_given=True)
        cov = store.get_consent_corpus_coverage()
        self.assertTrue(cov["consent_corpus_defensible"])
        self.assertEqual(cov["active_consent_count"], 2)
        self.assertEqual(cov["revoked_count"], 0)
        self.assertEqual(cov["erasure_requested_count"], 0)

    def test_4_defensible_false_when_revoked(self):
        """consent_corpus_defensible=False when any device has revoked consent."""
        store = _make_store()
        store.insert_consent_record(device_id="dev162_c", consent_given=True)
        store.insert_consent_record(device_id="dev162_d", consent_given=True)
        store.revoke_consent(device_id="dev162_c", reason="gdpr")
        cov = store.get_consent_corpus_coverage()
        self.assertFalse(cov["consent_corpus_defensible"])
        self.assertGreater(cov["revoked_count"], 0)

    def test_5_defensible_false_when_erasure_requested(self):
        """consent_corpus_defensible=False when any device has erasure_requested=True."""
        store = _make_store()
        store.insert_consent_record(device_id="dev162_e", consent_given=True)
        # Directly set erasure_requested without full revoke
        store.insert_consent_record(device_id="dev162_f", consent_given=True)
        store.revoke_consent(device_id="dev162_f", reason="erasure_test")
        cov = store.get_consent_corpus_coverage()
        self.assertFalse(cov["consent_corpus_defensible"])
        # revoke_consent sets erasure_requested=1 by default
        self.assertGreater(cov["erasure_requested_count"], 0)

    def test_6_revoked_and_erasure_tracked_independently(self):
        """revoked_count and erasure_requested_count are independently tracked."""
        store = _make_store()
        store.insert_consent_record(device_id="dev162_only_revoked", consent_given=True)
        store.insert_consent_record(device_id="dev162_erasure", consent_given=True)

        # Set only revoked_at (no erasure_requested) on first device
        import sqlite3
        with store._conn() as con:
            con.execute(
                "UPDATE consent_ledger SET consent_given=0, revoked_at=?, erasure_requested=0"
                " WHERE device_id=?",
                (time.time(), "dev162_only_revoked"),
            )
        # Full revoke (sets erasure_requested=1) on second
        store.revoke_consent(device_id="dev162_erasure", reason="test")

        cov = store.get_consent_corpus_coverage()
        self.assertGreaterEqual(cov["revoked_count"], 1)
        self.assertGreaterEqual(cov["erasure_requested_count"], 1)
        self.assertFalse(cov["consent_corpus_defensible"])

    def test_7_endpoint_returns_6_keys(self):
        """GET /agent/consent-aware-corpus-status returns 200 with 6 required keys."""
        store = _make_store()
        cfg   = _make_cfg(consent_ledger_enabled=True)
        app   = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/consent-aware-corpus-status",
            params={"api_key": "testkey162"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in (
            "consent_ledger_enabled",
            "active_consent_count",
            "revoked_count",
            "erasure_requested_count",
            "consent_corpus_defensible",
            "timestamp",
        ):
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertTrue(body["consent_ledger_enabled"])
        self.assertEqual(body["active_consent_count"], 0)
        self.assertFalse(body["consent_corpus_defensible"])

    def test_8_tool_119_returns_required_keys(self):
        """Tool #119 get_consent_aware_corpus_status returns dict with 6 keys."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg   = _make_cfg(consent_ledger_enabled=True)
        agent = BridgeAgent(cfg=cfg, store=store)

        result = agent._execute_tool("get_consent_aware_corpus_status", {})
        self.assertIsInstance(result, dict)
        for key in (
            "consent_ledger_enabled",
            "active_consent_count",
            "revoked_count",
            "erasure_requested_count",
            "consent_corpus_defensible",
            "timestamp",
        ):
            self.assertIn(key, result, f"Missing key: {key}")
        self.assertEqual(result["active_consent_count"], 0)
        self.assertFalse(result["consent_corpus_defensible"])


if __name__ == "__main__":
    unittest.main()
