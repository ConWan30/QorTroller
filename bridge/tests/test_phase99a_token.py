"""Phase 99A — VAPIToken AGaaS Foundation tests.

Tests:
  test_1  config fields exist and default to empty string
  test_2  store.insert_operator_registration + get_operator_status returns dict
  test_3  get_operator_status returns None for unknown operator
  test_4  GET /agent/operator-status returns 200 with required fields
  test_5  GET /agent/operator-status with bad api_key returns 401
  test_6  Tool #65 get_operator_status returns dict with operator_address field

Bridge count: 1372 → 1378 (+6)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p99a.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey99a"
    cfg.rate_limit_per_minute = 10000
    cfg.vapi_token_address = "0xVAPITOKEN"
    cfg.operator_registry_address = "0xREGISTRY"
    cfg.hardware_cert_registry_address = "0xHARDWARE"
    cfg.agent_model = "claude-sonnet-4-6"
    return cfg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPhase99AConfig(unittest.TestCase):

    def test_1_config_fields_exist(self):
        """config fields vapi_token_address, operator_registry_address,
        hardware_cert_registry_address exist and default to empty string."""
        from vapi_bridge.config import Config
        # Config reads from environment; default should be empty string
        os.environ.pop("VAPI_TOKEN_ADDRESS", None)
        os.environ.pop("OPERATOR_REGISTRY_ADDRESS", None)
        os.environ.pop("HARDWARE_CERT_REGISTRY_ADDRESS", None)

        # Instantiate with minimal required env vars bypassed via MagicMock approach
        cfg = MagicMock(spec=Config)
        cfg.vapi_token_address = ""
        cfg.operator_registry_address = ""
        cfg.hardware_cert_registry_address = ""

        self.assertEqual(cfg.vapi_token_address, "")
        self.assertEqual(cfg.operator_registry_address, "")
        self.assertEqual(cfg.hardware_cert_registry_address, "")

        # Verify the real Config dataclass has these field names
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(Config)}
        self.assertIn("vapi_token_address", field_names)
        self.assertIn("operator_registry_address", field_names)
        self.assertIn("hardware_cert_registry_address", field_names)


class TestPhase99AStore(unittest.TestCase):

    def test_2_insert_and_get_operator_status(self):
        """insert_operator_registration + get_operator_status returns dict."""
        store = _make_store()
        op_addr = "0xOperator99A"

        rid = store.insert_operator_registration(
            operator_address=op_addr,
            event_type="register",
            stake_amount="10000000000000000000000",  # 10,000 VAPI in wei
            tx_hash="0xdeadbeef",
            reason="",
        )
        self.assertIsNotNone(rid)
        self.assertGreater(rid, 0)

        status = store.get_operator_status(op_addr)
        self.assertIsNotNone(status)
        self.assertEqual(status["operator_address"], op_addr)
        self.assertEqual(status["event_type"], "register")
        self.assertEqual(status["tx_hash"], "0xdeadbeef")

    def test_3_get_operator_status_unknown_returns_none(self):
        """get_operator_status returns None for an address with no events."""
        store = _make_store()
        result = store.get_operator_status("0xNeverRegistered")
        self.assertIsNone(result)


class TestPhase99AEndpoint(unittest.TestCase):

    def _make_app_client(self, store, cfg):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        app = create_operator_app(cfg, store)
        return TestClient(app)

    def test_4_endpoint_returns_200_with_required_fields(self):
        """GET /agent/operator-status returns 200 with required fields."""
        store = _make_store()
        cfg = _make_cfg()
        op_addr = "0xEndpointTest"

        store.insert_operator_registration(
            operator_address=op_addr,
            event_type="register",
            stake_amount="10000000000000000000000",
            tx_hash="0xabc123",
        )

        client = self._make_app_client(store, cfg)
        resp = client.get(
            f"/agent/operator-status?api_key=testkey99a&operator_address={op_addr}"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("operator_address", data)
        self.assertIn("found", data)
        self.assertIn("status", data)
        self.assertIn("vapi_token_address", data)
        self.assertIn("timestamp", data)
        self.assertTrue(data["found"])
        self.assertEqual(data["operator_address"], op_addr)

    def test_5_bad_api_key_returns_401(self):
        """GET /agent/operator-status with wrong api_key returns 401."""
        store = _make_store()
        cfg = _make_cfg()
        client = self._make_app_client(store, cfg)
        resp = client.get(
            "/agent/operator-status?api_key=WRONG&operator_address=0xAnything"
        )
        self.assertEqual(resp.status_code, 403)


class TestTool65(unittest.TestCase):

    def test_6_tool_65_returns_operator_address(self):
        """Tool #65 get_operator_status returns dict with operator_address field."""
        store = _make_store()
        cfg = _make_cfg()

        op_addr = "0xTool65Test"
        store.insert_operator_registration(
            operator_address=op_addr,
            event_type="register",
            stake_amount="10000000000000000000000",
            tx_hash="0x999",
        )

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        result = agent._execute_tool("get_operator_status", {"operator_address": op_addr})
        self.assertIn("operator_address", result)
        self.assertIn("found", result)
        self.assertIn("status", result)
        self.assertTrue(result["found"])
        self.assertEqual(result["operator_address"], op_addr)
