"""Phase 99C — VHP Soulbound Token bridge tests.

Tests:
  test_1  store.insert_vhp_issuance + get_vhp_status returns dict with required fields
  test_2  get_vhp_status returns None for unknown device
  test_3  POST /agent/mint-vhp returns 422 when dry_run=True
  test_4  POST /agent/mint-vhp returns 422 when audit_valid=False
  test_5  GET /agent/vhp-status/{device_id} returns 200 with required fields
  test_6  GET /agent/vhp-status/{device_id} with bad api_key returns 403

Bridge count: 1386 → 1392 (+6)
"""
import asyncio
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p99c.db"))


def _make_cfg(dry_run: bool = True, audit_valid_override: bool = False):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey99c"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_dry_run_mode = dry_run
    cfg.vhp_contract_address = ""
    cfg.layerzero_endpoint_address = ""
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s = 86400
    cfg.epistemic_consensus_enabled = False
    cfg.agent_model = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache = None
    cfg.ioswarm_vhp_mint_enabled = False  # Phase 110: prevent MagicMock truthy routing
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVHPStore(unittest.TestCase):

    def test_1_insert_and_retrieve_vhp_issuance(self):
        """insert_vhp_issuance + get_vhp_status returns dict with required fields."""
        store = _make_store()
        device_id = "dev_vhp_test99c"
        expires = time.time() + 90 * 86400

        rid = store.insert_vhp_issuance(
            device_id=device_id,
            token_id=1,
            tx_hash="0xabc123",
            expires_at=expires,
            cert_level=1,
            consecutive_clean=25,
            to_address="0x1234567890abcdef1234567890abcdef12345678",
        )
        self.assertIsNotNone(rid)
        self.assertGreater(rid, 0)

        result = store.get_vhp_status(device_id)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["device_id"], device_id)
        self.assertEqual(result["token_id"], 1)
        self.assertEqual(result["tx_hash"], "0xabc123")
        self.assertEqual(result["cert_level"], 1)
        self.assertEqual(result["consecutive_clean"], 25)
        self.assertAlmostEqual(result["expires_at"], expires, places=0)

    def test_2_get_vhp_status_unknown_device_returns_none(self):
        """get_vhp_status returns None for unknown device."""
        store = _make_store()
        result = store.get_vhp_status("dev_never_seen_99c")
        self.assertIsNone(result)


class TestMintVHPEndpoint(unittest.TestCase):

    def test_3_mint_vhp_returns_422_when_dry_run(self):
        """POST /agent/mint-vhp returns 422 when dry_run=True."""
        store = _make_store()
        cfg = _make_cfg(dry_run=True)
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/agent/mint-vhp",
            params={
                "api_key": "testkey99c",
                "device_id": "dev_vhp_dry",
                "to_address": "0x1234567890abcdef1234567890abcdef12345678",
            },
        )
        self.assertEqual(resp.status_code, 422)
        body = resp.json()
        # Should mention dry_run or audit or gate in the error detail
        detail = str(body.get("detail", ""))
        self.assertTrue(
            "dry_run" in detail.lower() or "audit" in detail.lower() or "gate" in detail.lower(),
            f"Unexpected error detail: {detail}",
        )

    def test_4_mint_vhp_returns_422_when_audit_invalid(self):
        """POST /agent/mint-vhp returns 422 when activation audit not passed."""
        store = _make_store()
        cfg = _make_cfg(dry_run=False)
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        # No activation audit data in store → audit_valid=False → 422
        resp = client.post(
            "/agent/mint-vhp",
            params={
                "api_key": "testkey99c",
                "device_id": "dev_vhp_no_audit",
                "to_address": "0x1234567890abcdef1234567890abcdef12345678",
            },
        )
        self.assertEqual(resp.status_code, 422)


class TestVHPStatusEndpoint(unittest.TestCase):

    def test_5_vhp_status_returns_200_with_required_fields(self):
        """GET /agent/vhp-status/{device_id} returns 200 with required fields."""
        store = _make_store()
        cfg = _make_cfg()
        device_id = "dev_vhp_status_test"

        # Pre-insert a VHP record
        store.insert_vhp_issuance(
            device_id=device_id,
            token_id=7,
            tx_hash="0xdeadbeef",
            expires_at=time.time() + 86400,
            cert_level=2,
            consecutive_clean=33,
            to_address="0xabcdef",
        )

        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            f"/agent/vhp-status/{device_id}",
            params={"api_key": "testkey99c"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["device_id"], device_id)
        self.assertTrue(body["found"])
        self.assertIn("is_valid", body)
        self.assertIn("token_id", body)
        self.assertIn("cert_level", body)
        self.assertIn("expires_at", body)
        self.assertIn("timestamp", body)
        # is_valid=True since expires_at is in the future
        self.assertTrue(body["is_valid"])

    def test_6_vhp_status_bad_api_key_returns_403(self):
        """GET /agent/vhp-status/{device_id} with wrong api_key returns 403."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/vhp-status/some_device",
            params={"api_key": "WRONG_KEY"},
        )
        self.assertEqual(resp.status_code, 403)
