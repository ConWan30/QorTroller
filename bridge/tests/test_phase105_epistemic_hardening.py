"""Phase 105 — Epistemic Consensus Hardening tests.

Tests:
  test_1  epistemic_threshold_history table exists; insert + get returns record
  test_2  _epistemic_consensus() uses recommended threshold (0.65) when pmi >= 1
  test_3  _epistemic_consensus() uses base threshold (0.60) when pmi == 0
  test_4  triage_prereq_required=True + triage_score=0.0 -> returns proposed_verdict
  test_5  GET /agent/epistemic-config returns required fields
  test_6  Tool #72 get_epistemic_config returns at_risk and effective_threshold

Bridge count: 1438 -> 1444 (+6)
"""
import asyncio
import tempfile
import time
import unittest
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    return Store(str(Path(td) / "test_p105.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey105"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_dry_run_mode = True
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s = 86400
    cfg.epistemic_consensus_enabled = True
    cfg.epistemic_consensus_threshold = 0.60
    cfg.epistemic_recommended_threshold = 0.65
    cfg.epistemic_triage_prereq_required = False
    cfg.agent_model = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache = None
    cfg.vhp_contract_address = ""
    cfg.layerzero_endpoint_address = ""
    cfg.warm_up_batch_size = 5
    cfg.stiotx_token_address = ""
    cfg.quicksilver_collateral_address = ""
    cfg.activation_auto_restore = True
    cfg.gsr_enabled = False
    # Phase 109A/109B/109C: prevent MagicMock truthy attr from routing to ioSwarm branches
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.poad_registry_enabled = False  # Phase 111: prevent MagicMock truthy attr from routing to Step D
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


class TestEpistemicHardening(unittest.TestCase):

    def test_1_epistemic_threshold_history_table(self):
        """epistemic_threshold_history table exists; insert + get returns record."""
        store = _make_store()
        row_id = store.insert_epistemic_threshold_change(
            old_threshold=0.60, new_threshold=0.65,
            trigger="pmi_auto", pmi_at_change=1, notes="Phase 105 test"
        )
        self.assertIsNotNone(row_id)
        history = store.get_epistemic_threshold_history(limit=5)
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertAlmostEqual(entry["old_threshold"], 0.60)
        self.assertAlmostEqual(entry["new_threshold"], 0.65)
        self.assertEqual(entry["trigger"], "pmi_auto")

    def test_2_epistemic_uses_recommended_when_pmi_gte_1(self):
        """_epistemic_consensus() uses 0.65 when pmi >= 1 (ClassJ 0.40+sup 0.20=0.60 < 0.65 -> HOLD)."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        # Seed activation_simulation_log so compute_pmi() returns 1
        from vapi_bridge.activation_simulation import ActivationSimulator
        cfg_mock = _make_cfg()
        sim = ActivationSimulator(cfg_mock, store)
        sim.seed_validation_records(n=110)
        sim.seed_protocol_intelligence()
        sim.seed_live_mode_activation_log()
        sim.seed_gate_attestation()
        sim.seed_enforcement_certificate("hmackey105")
        sim.seed_vhp_issuance()
        store.insert_activation_simulation_log(
            n_sessions=110, gate_passed=True, cert_created=True,
            dry_run_toggled=True, vhp_minted=True,
            token_id=1, tx_hash="sim_mint_abc105"
        )

        # Verify PMI is 1
        self.assertEqual(store.compute_pmi(), 1)

        # Seed class_j HIGH for the device
        store.insert_class_j_assessment(
            device_id="test_device_105",
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # No triage escalation -> triage_score=0.0
        # Supervisor = UNKNOWN/not seeded -> supervisor_score=1.0 (default optimistic)
        # Score = 0.40*1.0 + 0.40*0.0 + 0.20*1.0 = 0.60
        # With threshold=0.65 (PMI>=1): 0.60 < 0.65 -> HOLD (downgraded)
        # With threshold=0.60 (base): 0.60 >= 0.60 -> BLOCK (not downgraded)

        cfg = _make_cfg()
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("test_device_105", "BLOCK")
        )
        # With PMI=1 and recommended=0.65: score 0.60 < 0.65 -> should be HOLD
        self.assertEqual(result, "HOLD")

    def test_3_epistemic_uses_base_when_pmi_is_0(self):
        """_epistemic_consensus() uses 0.60 when pmi=0 (empty store, ClassJ HIGH -> BLOCK)."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()
        # Empty store -> pmi=0 -> threshold=0.60

        store.insert_class_j_assessment(
            device_id="test_device_105b",
            risk_level="HIGH",
            entropy_variance=0.01,
            window_count=10,
        )
        # Score = 0.40*1.0 + 0.40*0.0 + 0.20*1.0 = 0.60
        # threshold=0.60 (pmi=0): 0.60 >= 0.60 -> BLOCK

        cfg = _make_cfg()
        sa = SessionAdjudicator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("test_device_105b", "BLOCK")
        )
        self.assertEqual(result, "BLOCK")

    def test_4_triage_prereq_required_returns_proposed_verdict(self):
        """triage_prereq_required=True + triage_score=0.0 -> returns proposed_verdict unchanged."""
        from vapi_bridge.session_adjudicator import SessionAdjudicator
        store = _make_store()

        cfg = _make_cfg(epistemic_triage_prereq_required=True)
        sa = SessionAdjudicator(cfg, store)
        # No triage escalation for this device -> triage_score=0.0
        result = asyncio.get_event_loop().run_until_complete(
            sa._epistemic_consensus("no_triage_device", "BLOCK")
        )
        # prereq not met -> return proposed_verdict unchanged (BLOCK)
        self.assertEqual(result, "BLOCK")

    def test_5_get_epistemic_config_returns_required_fields(self):
        """GET /agent/epistemic-config returns all required fields."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/epistemic-config",
            params={"api_key": "testkey105"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("configured_threshold", "recommended_threshold", "effective_threshold",
                    "pmi_triggered", "triage_prereq_required", "at_risk", "pmi",
                    "threshold_history", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")

    def test_6_tool_72_get_epistemic_config(self):
        """Tool #72 get_epistemic_config returns at_risk and effective_threshold."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_epistemic_config", {})
        self.assertIsInstance(result, dict)
        self.assertIn("at_risk", result)
        self.assertIn("effective_threshold", result)
