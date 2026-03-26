"""Phase 103 -- Live Activation Protocol tests.

Tests:
  test_1  activation_simulation_log table exists; insert + get returns record
  test_2  ActivationSimulator.seed_validation_records(110) -> gate_passed=True
  test_3  get_first_vhp_status() returns None on empty store
  test_4  ActivationRunner.run(n_sessions=110) -> vhp_minted=True, fully_activated=True
  test_5  GET /agent/first-vhp-status returns 200 with {found=True, is_simulation=True}
  test_6  POST /agent/run-activation-simulation returns 200 with {vhp_minted, fully_activated}
  test_7  Tool #70 run_activation_sequence returns vhp_minted in result dict
  test_8  after ActivationRunner.run(), get_total_vhp_count() > 0 (lifecycle_warning suppressed)

Bridge count: 1422 -> 1430 (+8)
"""
import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store
from vapi_bridge.operator_api import create_operator_app
from vapi_bridge.activation_simulation import ActivationSimulator
from vapi_bridge.activation_runner import ActivationRunner

try:
    from starlette.testclient import TestClient
except ImportError:
    from fastapi.testclient import TestClient


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p103.db"))


def _make_cfg():
    cfg = MagicMock()
    cfg.operator_api_key = "testkey103"
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


class TestPhase103Activation(unittest.TestCase):

    def test_1_activation_simulation_log_table_and_methods(self):
        """activation_simulation_log table exists; insert + get returns record with required fields."""
        store = _make_store()
        # Table exists -- no exception
        rid = store.insert_activation_simulation_log(
            n_sessions=110,
            gate_passed=True,
            cert_created=True,
            dry_run_toggled=True,
            vhp_minted=True,
            token_id=1,
            tx_hash="sim_mint_abc123",
        )
        self.assertIsNotNone(rid)
        entries = store.get_activation_simulation_log(limit=5)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        for key in ("id", "n_sessions", "gate_passed", "cert_created",
                    "dry_run_toggled", "vhp_minted", "token_id", "tx_hash", "created_at"):
            self.assertIn(key, e, f"Missing key: {key}")
        self.assertEqual(e["n_sessions"], 110)
        self.assertTrue(e["gate_passed"])
        self.assertEqual(e["tx_hash"], "sim_mint_abc123")

    def test_2_seed_validation_records_gate_passed(self):
        """ActivationSimulator.seed_validation_records(110) -> gate_passed=True."""
        store = _make_store()
        cfg = _make_cfg()
        sim = ActivationSimulator(cfg, store)
        count = sim.seed_validation_records(110)
        self.assertGreaterEqual(count, 110)
        summary = store.get_validation_summary(
            gate_n=100, max_divergence_rate=1.0
        )
        # consecutive_clean is computed over the trailing gate_n (100) window,
        # so the max returned value is 100 (all 100 window rows are clean).
        self.assertGreaterEqual(summary["consecutive_clean"], 100)
        self.assertTrue(summary["gate_passed"])

    def test_3_get_first_vhp_status_returns_none_on_empty_store(self):
        """get_first_vhp_status() returns None on empty store (before activation)."""
        store = _make_store()
        result = store.get_first_vhp_status()
        self.assertIsNone(result)

    def test_4_activation_runner_run_fully_activated(self):
        """ActivationRunner.run(n_sessions=110) -> vhp_minted=True, fully_activated=True, error=None."""
        store = _make_store()
        cfg = _make_cfg()
        runner = ActivationRunner(cfg, store, bus=None)
        result = asyncio.run(runner.run(n_sessions=110))
        self.assertIsNone(result["error"], f"Unexpected error: {result.get('error')}")
        self.assertTrue(result["vhp_minted"])
        self.assertTrue(result["fully_activated"])
        self.assertTrue(result["gate_passed"])
        self.assertTrue(result["dry_run_toggled"])
        self.assertGreater(result["elapsed_ms"], 0)

    def test_5_first_vhp_status_endpoint_returns_200_found_is_simulation(self):
        """GET /agent/first-vhp-status returns 200 with {found=True, is_simulation=True} after run()."""
        store = _make_store()
        cfg = _make_cfg()
        runner = ActivationRunner(cfg, store, bus=None)
        asyncio.run(runner.run(n_sessions=110))

        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/agent/first-vhp-status", params={"api_key": "testkey103"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body.get("found"), f"found=False in {body}")
        self.assertTrue(body.get("is_simulation"), f"is_simulation=False in {body}")
        self.assertIn("tx_hash", body)

    def test_6_run_activation_simulation_endpoint_returns_200(self):
        """POST /agent/run-activation-simulation returns 200 with {vhp_minted, fully_activated}."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/agent/run-activation-simulation",
            params={"api_key": "testkey103", "n_sessions": 110},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("vhp_minted", body)
        self.assertIn("fully_activated", body)
        self.assertTrue(body.get("vhp_minted"))
        self.assertTrue(body.get("fully_activated"))

    def test_7_tool_70_run_activation_sequence(self):
        """Tool #70 run_activation_sequence returns vhp_minted in result dict."""
        store = _make_store()
        cfg = _make_cfg()
        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("run_activation_sequence", {"n_sessions": 110})
        self.assertIn("vhp_minted", result, f"Missing vhp_minted in {result}")
        self.assertTrue(result["vhp_minted"])

    def test_8_after_runner_total_vhp_count_gt_0_lifecycle_warning_suppressed(self):
        """After ActivationRunner.run(), get_total_vhp_count() > 0 (lifecycle_warning suppressed)."""
        store = _make_store()
        cfg = _make_cfg()
        runner = ActivationRunner(cfg, store, bus=None)
        asyncio.run(runner.run(n_sessions=110))
        count = store.get_total_vhp_count()
        self.assertGreater(count, 0)
