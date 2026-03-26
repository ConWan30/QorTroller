"""Phase 107 — Live Mode Readiness Validation tests.

Tests:
  test_1  live_mode_readiness_reports table exists; get_latest_readiness_report() None on empty
  test_2  run_validation(n=20) on fresh store: false_positive_count=0, fp_rate=0.0
  test_3  ready_for_live=False when dry_run=True and activation_committed=False (default)
  test_4  ready_for_live=True when activation_committed=True + PMI=1 + dry_run=False + n=100
  test_5  POST /agent/run-readiness-validation returns 200 with required fields
  test_6  GET /agent/live-mode-readiness: found=False before run; found=True + fields after run
  test_7  insert_readiness_report() + get_latest_readiness_report() roundtrip; all 9 fields
  test_8  Tool #73 get_live_mode_readiness returns n_tested and ready_for_live

Bridge count: 1444 -> 1452 (+8)
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


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p107.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey107"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_dry_run_mode = True
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s = 86400
    cfg.epistemic_consensus_enabled = False
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
    cfg.protocol_maturity_enabled = True
    cfg.gsr_enabled = False
    cfg.synthetic_corpus_enabled = False
    cfg.synthetic_corpus_size = 20
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _seed_pmi(store: Store, cfg) -> None:
    """Seed store so compute_pmi() returns 1 (simulation VHP present and valid)."""
    from vapi_bridge.activation_simulation import ActivationSimulator
    sim = ActivationSimulator(cfg, store)
    sim.seed_validation_records(n=110)
    sim.seed_protocol_intelligence()
    sim.seed_live_mode_activation_log()
    sim.seed_gate_attestation()
    sim.seed_enforcement_certificate("hmackey107")
    sim.seed_vhp_issuance()
    store.insert_activation_simulation_log(
        n_sessions=110, gate_passed=True, cert_created=True,
        dry_run_toggled=True, vhp_minted=True,
        token_id=1, tx_hash="sim_mint_p107test"
    )


class TestPhase107Readiness(unittest.TestCase):

    def test_1_readiness_table_exists_and_empty(self):
        """live_mode_readiness_reports table exists; get_latest_readiness_report() returns None."""
        store = _make_store()
        result = store.get_latest_readiness_report()
        self.assertIsNone(result)

    def test_2_run_validation_nominal_no_false_positives(self):
        """run_validation(n=20) on fresh store: false_positive_count=0, fp_rate=0.0."""
        from vapi_bridge.live_mode_readiness_validator import LiveModeReadinessValidator
        store = _make_store()
        cfg = _make_cfg()
        validator = LiveModeReadinessValidator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(validator.run_validation(n=20))
        self.assertEqual(result["false_positive_count"], 0)
        self.assertAlmostEqual(result["false_positive_rate"], 0.0)
        self.assertEqual(result["n_tested"], 20)
        self.assertIsNone(result.get("error"))
        # W1 isolation: ruling_validation_log must be untouched
        summary = store.get_validation_summary()
        self.assertEqual(summary.get("session_count", 0), 0)

    def test_3_ready_for_live_false_by_default(self):
        """ready_for_live=False when dry_run=True and activation_committed=False (default)."""
        from vapi_bridge.live_mode_readiness_validator import LiveModeReadinessValidator
        store = _make_store()
        cfg = _make_cfg(agent_dry_run_mode=True)
        validator = LiveModeReadinessValidator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(validator.run_validation(n=100))
        self.assertFalse(result["ready_for_live"])
        self.assertFalse(result["activation_committed"])
        self.assertTrue(result["dry_run_active"])

    def test_4_ready_for_live_true_when_all_conditions_met(self):
        """ready_for_live=True when activation_committed=True + PMI=1 + dry_run=False + n=100."""
        from vapi_bridge.live_mode_readiness_validator import LiveModeReadinessValidator
        store = _make_store()
        cfg = _make_cfg(agent_dry_run_mode=False)
        _seed_pmi(store, cfg)
        store.set_activation_committed(committed_by="test_op107", notes="phase107 test")

        validator = LiveModeReadinessValidator(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(validator.run_validation(n=100))

        self.assertEqual(result["false_positive_count"], 0)
        self.assertTrue(result["activation_committed"])
        self.assertFalse(result["dry_run_active"])
        self.assertGreaterEqual(result["pmi"], 1)
        self.assertTrue(result["ready_for_live"])

    def test_5_post_run_readiness_validation_returns_200(self):
        """POST /agent/run-readiness-validation returns 200 with required fields."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post(
            "/agent/run-readiness-validation",
            params={"api_key": "testkey107", "n": 10},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("n_tested", "false_positive_count", "false_positive_rate",
                    "ready_for_live", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")
        self.assertEqual(body["n_tested"], 10)

    def test_6_get_live_mode_readiness_found_flag(self):
        """GET /agent/live-mode-readiness: found=False before run; found=True after run."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        # Before any run
        resp = client.get(
            "/agent/live-mode-readiness",
            params={"api_key": "testkey107"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["found"])
        self.assertFalse(body["ready_for_live"])

        # Run validation
        client.post(
            "/agent/run-readiness-validation",
            params={"api_key": "testkey107", "n": 5},
        )

        # After run
        resp2 = client.get(
            "/agent/live-mode-readiness",
            params={"api_key": "testkey107"},
        )
        self.assertEqual(resp2.status_code, 200)
        body2 = resp2.json()
        self.assertTrue(body2["found"])
        self.assertIn("n_tested", body2)
        self.assertIn("false_positive_count", body2)

    def test_7_insert_get_readiness_report_roundtrip(self):
        """insert_readiness_report() + get_latest_readiness_report() roundtrip; all 9 fields."""
        store = _make_store()
        row_id = store.insert_readiness_report(
            n_tested=100, false_positive_count=0, false_positive_rate=0.0,
            activation_committed=1, pmi=1, dry_run_active=0,
            ready_for_live=1, notes="phase107_validation n=100"
        )
        self.assertIsNotNone(row_id)
        report = store.get_latest_readiness_report()
        self.assertIsNotNone(report)
        self.assertEqual(report["n_tested"], 100)
        self.assertEqual(report["false_positive_count"], 0)
        self.assertAlmostEqual(report["false_positive_rate"], 0.0)
        self.assertTrue(report["activation_committed"])
        self.assertEqual(report["pmi"], 1)
        self.assertFalse(report["dry_run_active"])
        self.assertTrue(report["ready_for_live"])
        self.assertEqual(report["notes"], "phase107_validation n=100")
        self.assertIn("created_at", report)

    def test_8_tool_73_get_live_mode_readiness(self):
        """Tool #73 get_live_mode_readiness returns n_tested and ready_for_live."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)

        # Before any report: found=False
        result = agent._execute_tool("get_live_mode_readiness", {})
        self.assertIsInstance(result, dict)
        self.assertIn("ready_for_live", result)
        self.assertIn("n_tested", result)
        self.assertFalse(result["ready_for_live"])

        # After inserting a report
        store.insert_readiness_report(
            n_tested=100, false_positive_count=0, false_positive_rate=0.0,
            activation_committed=1, pmi=1, dry_run_active=0,
            ready_for_live=1, notes="tool_test"
        )
        result2 = agent._execute_tool("get_live_mode_readiness", {})
        self.assertIn("n_tested", result2)
        self.assertEqual(result2["n_tested"], 100)
        self.assertTrue(result2["ready_for_live"])
        self.assertTrue(result2["found"])
