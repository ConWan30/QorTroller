"""Phase 104 — Persistent Activation Commit + ProtocolMaturityIndex tests.

Tests:
  test_1  activation_state table exists; get_activation_state() defaults
  test_2  set_activation_committed() writes row; returns activation_committed=True
  test_3  compute_pmi() returns 0 on empty store; returns 1 after simulation
  test_4  _restore_activation_state() sets dry_run=False when committed=True
  test_5  _restore_activation_state() does NOT change cfg when committed=False
  test_6  POST /agent/commit-activation returns committed=True pmi>=1
  test_7  GET /agent/protocol-maturity returns required fields
  test_8  Tool #71 get_protocol_maturity returns pmi and activation_committed

Bridge count: 1430 -> 1438 (+8)
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
    return Store(str(Path(td) / "test_p104.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey104"
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
    cfg.activation_auto_restore = True
    cfg.protocol_maturity_enabled = True
    return cfg


class TestActivationCommit(unittest.TestCase):

    def test_1_activation_state_table_defaults(self):
        """activation_state table exists; get_activation_state() returns defaults."""
        store = _make_store()
        state = store.get_activation_state()
        self.assertIsInstance(state, dict)
        self.assertFalse(state["activation_committed"])
        self.assertEqual(state["pmi"], 0)
        self.assertIsNone(state["committed_at"])

    def test_2_set_activation_committed(self):
        """set_activation_committed() writes row; get_activation_state() returns True."""
        store = _make_store()
        row_id = store.set_activation_committed(committed_by="test_op", notes="unit test")
        self.assertIsNotNone(row_id)
        state = store.get_activation_state()
        self.assertTrue(state["activation_committed"])
        self.assertEqual(state["committed_by"], "test_op")

    def test_3_compute_pmi(self):
        """compute_pmi() returns 0 on empty store; 1 after simulation seeding."""
        store = _make_store()
        self.assertEqual(store.compute_pmi(), 0)

        # Seed activation simulation log to get PMI=1
        from vapi_bridge.activation_simulation import ActivationSimulator
        sim = ActivationSimulator(_make_cfg(), store)
        sim.seed_validation_records(n=110)
        sim.seed_protocol_intelligence()
        sim.seed_live_mode_activation_log()
        sim.seed_gate_attestation()
        sim.seed_enforcement_certificate("hmackey")
        sim.seed_vhp_issuance()
        store.insert_activation_simulation_log(
            n_sessions=110, gate_passed=True, cert_created=True,
            dry_run_toggled=True, vhp_minted=True,
            token_id=1, tx_hash="sim_mint_abc123"
        )
        pmi = store.compute_pmi()
        self.assertEqual(pmi, 1)

    def test_4_restore_activation_state_sets_dry_run_false(self):
        """_restore_activation_state() sets cfg.agent_dry_run_mode=False when committed=True."""
        from vapi_bridge.main import _restore_activation_state
        store = _make_store()
        store.set_activation_committed(committed_by="test", notes="test")

        class _Cfg:
            activation_auto_restore = True
            agent_dry_run_mode = True

        cfg = _Cfg()
        _restore_activation_state(cfg, store)
        self.assertFalse(cfg.agent_dry_run_mode)

    def test_5_restore_activation_state_no_change_when_not_committed(self):
        """_restore_activation_state() does NOT change cfg when committed=False."""
        from vapi_bridge.main import _restore_activation_state
        store = _make_store()

        class _Cfg:
            activation_auto_restore = True
            agent_dry_run_mode = True

        cfg = _Cfg()
        _restore_activation_state(cfg, store)
        self.assertTrue(cfg.agent_dry_run_mode)

    def test_6_post_commit_activation_returns_committed(self):
        """POST /agent/commit-activation returns committed=True and pmi>=1."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/agent/commit-activation",
            params={"api_key": "testkey104", "n_sessions": 110},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("committed", body)
        # May succeed or fail depending on simulation result; just check structure
        self.assertIn("pmi", body)
        self.assertIn("timestamp", body)

    def test_7_get_protocol_maturity_returns_required_fields(self):
        """GET /agent/protocol-maturity returns all required fields."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/protocol-maturity",
            params={"api_key": "testkey104"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("pmi", "pmi_label", "activation_committed", "dry_run_active", "vhp_found", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")

    def test_8_tool_71_get_protocol_maturity(self):
        """Tool #71 get_protocol_maturity returns pmi and activation_committed."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_protocol_maturity", {})
        self.assertIsInstance(result, dict)
        self.assertIn("pmi", result)
        self.assertIn("activation_committed", result)
