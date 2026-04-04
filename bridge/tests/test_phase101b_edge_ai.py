"""Phase 101B — Edge AI Bridge Profile tests.

Tests:
  test_1  get_edge_ai_profile returns required top-level keys (never raises)
  test_2  agent_fleet_size == 13
  test_3  GET /agent/edge-ai-profile returns 200 with required fields
  test_4  iotex_layer_integration dict has ioID=True and w3bstream=True

Bridge count: 1406 -> 1410 (+4)
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
from vapi_bridge.edge_ai_profile import get_edge_ai_profile

try:
    from starlette.testclient import TestClient
except ImportError:
    from fastapi.testclient import TestClient


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p101b.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey101b"
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
    cfg.stiotx_token_address = ""
    cfg.quicksilver_collateral_address = ""
    return cfg


class TestEdgeAIProfile(unittest.TestCase):

    def test_1_get_edge_ai_profile_returns_required_keys(self):
        """get_edge_ai_profile returns all required top-level keys and never raises."""
        result = get_edge_ai_profile(cfg=None, store=None)
        self.assertIsInstance(result, dict)
        for key in ("protocol", "agent_fleet_size", "inference_mode",
                    "iotex_layer_integration", "positioning", "timestamp"):
            self.assertIn(key, result, f"Missing key: {key}")

    def test_2_agent_fleet_size_is_20(self):
        """agent_fleet_size == 20 (20-agent autonomous fleet — agents #19-20 added Phases 155-156)."""
        result = get_edge_ai_profile()
        self.assertEqual(result["agent_fleet_size"], 20)

    def test_3_edge_ai_profile_endpoint_returns_200(self):
        """GET /agent/edge-ai-profile returns 200 with required fields."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/edge-ai-profile",
            params={"api_key": "testkey101b"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("protocol", "agent_fleet_size", "inference_mode",
                    "iotex_layer_integration", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")

    def test_4_iotex_layer_integration_has_ioid_and_w3bstream(self):
        """iotex_layer_integration has ioID=True and w3bstream=True (both LIVE)."""
        result = get_edge_ai_profile(cfg=None, store=None)
        integration = result["iotex_layer_integration"]
        self.assertTrue(integration["ioID"])
        self.assertTrue(integration["w3bstream"])
        self.assertFalse(integration["realms"])  # Deferred
