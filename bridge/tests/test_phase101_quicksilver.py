"""Phase 101A — QuickSilver stIOTX Collateral bridge tests.

Tests:
  test_1  store.insert_quicksilver_collateral_event + get_quicksilver_collateral_status
  test_2  get_quicksilver_collateral_status returns found=False for unknown operator
  test_3  GET /agent/quicksilver-status returns required fields
  test_4  GET /agent/quicksilver-status with bad api_key returns 403
  test_5  Tool #67 get_quicksilver_collateral_status returns correct structure
  test_6  double_yield_note present in quicksilver_status response (W2 positioning)

Bridge count: 1400 -> 1406 (+6)
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
    return Store(str(Path(td) / "test_p101.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey101"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_dry_run_mode = True
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s = 86400
    cfg.epistemic_consensus_enabled = False
    cfg.agent_model = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache = None
    cfg.vhp_contract_address = ""
    cfg.layerzero_endpoint_address = ""
    cfg.warm_up_batch_size = 5
    cfg.stiotx_token_address = "0xMockStIOTX"
    cfg.quicksilver_collateral_address = "0xMockQSCollateral"
    return cfg


class TestQuickSilverStore(unittest.TestCase):

    def test_1_insert_and_retrieve_collateral_event(self):
        """insert_quicksilver_collateral_event + get_quicksilver_collateral_status returns dict."""
        store = _make_store()
        op_addr = "0xOperator101"
        rid = store.insert_quicksilver_collateral_event(
            operator_address=op_addr,
            event_type="lock",
            amount_wei="10000000000000000000000",
            tx_hash="0xlocktx101",
        )
        self.assertGreater(rid, 0)

        result = store.get_quicksilver_collateral_status(op_addr)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["found"])
        self.assertEqual(result["operator_address"], op_addr)
        self.assertEqual(result["latest_event_type"], "lock")
        self.assertEqual(result["amount_wei"], "10000000000000000000000")
        self.assertEqual(result["events_count"], 1)
        self.assertIsNotNone(result["last_event_at"])

    def test_2_unknown_operator_returns_found_false(self):
        """get_quicksilver_collateral_status returns found=False for unknown operator."""
        store = _make_store()
        result = store.get_quicksilver_collateral_status("0xNeverSeen")
        self.assertFalse(result["found"])
        self.assertIsNone(result["latest_event_type"])
        self.assertEqual(result["events_count"], 0)


class TestQuickSilverStatusEndpoint(unittest.TestCase):

    def test_3_quicksilver_status_returns_required_fields(self):
        """GET /agent/quicksilver-status returns required top-level fields."""
        store = _make_store()
        cfg = _make_cfg()
        store.insert_quicksilver_collateral_event(
            operator_address="0xOp101",
            event_type="lock",
            amount_wei="10000000000000000000000",
        )
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/quicksilver-status",
            params={"api_key": "testkey101", "operator_address": "0xOp101"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("operator_address", "found", "stiotx_token_address",
                    "quicksilver_collateral_address", "double_yield_note", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertTrue(body["found"])

    def test_4_quicksilver_status_bad_key_returns_403(self):
        """GET /agent/quicksilver-status with wrong api_key returns 403."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/quicksilver-status",
            params={"api_key": "WRONG", "operator_address": "0x123"},
        )
        self.assertEqual(resp.status_code, 403)


class TestQuickSilverTool(unittest.TestCase):

    def test_5_tool_67_returns_correct_structure(self):
        """Tool #67 get_quicksilver_collateral_status returns required fields."""
        store = _make_store()
        cfg = _make_cfg()

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._cfg = cfg
        agent._store = store
        agent._chain = None
        agent._bus = None

        result = agent._execute_tool("get_quicksilver_collateral_status",
                                     {"operator_address": "0xUnknown"})
        self.assertIn("operator_address", result)
        self.assertIn("found", result)
        self.assertIn("timestamp", result)
        self.assertFalse(result["found"])

    def test_6_double_yield_note_in_quicksilver_response(self):
        """double_yield_note present in quicksilver_status — W2 double-yield positioning."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/quicksilver-status",
            params={"api_key": "testkey101", "operator_address": "0xAny"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        note = body.get("double_yield_note", "")
        self.assertIn("yield", note.lower())
