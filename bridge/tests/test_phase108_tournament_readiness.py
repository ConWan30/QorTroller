"""Phase 108 — Tournament Readiness Scorecard tests.

Tests:
  test_1  tournament_readiness_snapshots table exists; get_latest_tournament_readiness_snapshot() None on empty
  test_2  GET /agent/tournament-readiness returns 200 with required fields
  test_3  software_conditions_met=5 when all software conditions pass (seeded store)
  test_4  hardware_conditions_met=0 with default cfg (separation_ratio=0.362, touchpad=False)
  test_5  hardware_conditions_met=2 when cfg.separation_ratio_current=1.1 + touchpad=True
  test_6  fully_ready=False when sw=5/5 but hw=0/2 (separation_ratio blocker)
  test_7  insert + get_latest roundtrip; all fields present; blocking_conditions is list
  test_8  Tool #74 get_tournament_readiness returns software_conditions_met and fully_ready

Bridge count: 1452 -> 1460 (+8)
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
    return Store(str(Path(td) / "test_p108.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey108"
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
    # Phase 108 hardware condition fields
    cfg.separation_ratio_current = 0.362
    cfg.touchpad_recapture_complete = False
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


def _seed_all_software_conditions(store: Store, cfg) -> None:
    """Seed store so all 5 software conditions pass."""
    from vapi_bridge.activation_simulation import ActivationSimulator
    sim = ActivationSimulator(cfg, store)
    sim.seed_validation_records(n=110)
    sim.seed_protocol_intelligence()
    sim.seed_live_mode_activation_log()
    sim.seed_gate_attestation()
    sim.seed_enforcement_certificate("hmackey108")
    sim.seed_vhp_issuance()
    store.insert_activation_simulation_log(
        n_sessions=110, gate_passed=True, cert_created=True,
        dry_run_toggled=True, vhp_minted=True,
        token_id=1, tx_hash="sim_mint_p108test"
    )
    # Seed Phase 107 readiness report (n_tested=100, fp=0)
    store.insert_readiness_report(
        n_tested=100, false_positive_count=0, false_positive_rate=0.0,
        activation_committed=1, pmi=1, dry_run_active=0,
        ready_for_live=1, notes="seeded_for_test"
    )
    store.set_activation_committed(True)


class TestPhase108TournamentReadiness(unittest.TestCase):

    def test_1_table_exists_and_empty(self):
        """tournament_readiness_snapshots table exists; get_latest returns None on empty."""
        store = _make_store()
        result = store.get_latest_tournament_readiness_snapshot()
        self.assertIsNone(result)

    def test_2_endpoint_returns_200_with_required_fields(self):
        """GET /agent/tournament-readiness returns 200 with required fields."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness?api_key=testkey108")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in [
            "software_conditions", "hardware_conditions", "fully_ready",
            "blocking_conditions", "separation_ratio_current",
            "software_conditions_met", "software_conditions_total",
            "hardware_conditions_met", "hardware_conditions_total",
            "timestamp",
        ]:
            self.assertIn(key, data, f"Missing key: {key}")
        self.assertEqual(data["software_conditions_total"], 5)
        self.assertEqual(data["hardware_conditions_total"], 2)

    def test_3_software_conditions_met_5_when_all_pass(self):
        """software_conditions_met=5 when all software conditions pass."""
        store = _make_store()
        cfg = _make_cfg(agent_dry_run_mode=False)
        _seed_all_software_conditions(store, cfg)
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness?api_key=testkey108")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["software_conditions_met"], 5)

    def test_4_hardware_conditions_met_0_with_defaults(self):
        """hardware_conditions_met=0 with default cfg (separation_ratio=0.362, touchpad=False)."""
        store = _make_store()
        cfg = _make_cfg()  # defaults: sep=0.362, touchpad=False
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness?api_key=testkey108")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["hardware_conditions_met"], 0)
        self.assertAlmostEqual(data["separation_ratio_current"], 0.362, places=3)

    def test_5_hardware_conditions_met_2_when_hw_ready(self):
        """hardware_conditions_met=2 when cfg.separation_ratio_current=1.1 + touchpad=True."""
        store = _make_store()
        cfg = _make_cfg(separation_ratio_current=1.1, touchpad_recapture_complete=True)
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness?api_key=testkey108")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["hardware_conditions_met"], 2)
        self.assertTrue(data["hardware_conditions"]["separation_ratio_above_gate"])
        self.assertTrue(data["hardware_conditions"]["touchpad_recapture_complete"])

    def test_6_fully_ready_false_when_hw_blocking(self):
        """fully_ready=False when sw=5/5 but hw=0/2 (separation_ratio blocker)."""
        store = _make_store()
        cfg = _make_cfg(agent_dry_run_mode=False)
        _seed_all_software_conditions(store, cfg)
        # separation_ratio_current=0.362 (default) — hw blocker
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/tournament-readiness?api_key=testkey108")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["fully_ready"])
        self.assertIn("separation_ratio_above_gate", data["blocking_conditions"])

    def test_7_insert_get_latest_roundtrip(self):
        """insert + get_latest roundtrip; all fields present; blocking_conditions is list."""
        import json
        store = _make_store()
        blocking = ["separation_ratio_gt_1", "touchpad_recapture_complete"]
        row_id = store.insert_tournament_readiness_snapshot(
            n_tested=100, false_positive_count=0,
            activation_committed=1, pmi=1, dry_run_active=0,
            software_conditions_met=5,
            separation_ratio=0.362, separation_ratio_ok=0,
            touchpad_recapture_complete=0, hardware_conditions_met=0,
            fully_ready=0,
            blocking_conditions_json=json.dumps(blocking),
            notes="test_roundtrip"
        )
        self.assertGreater(row_id, 0)
        snap = store.get_latest_tournament_readiness_snapshot()
        self.assertIsNotNone(snap)
        for key in [
            "id", "n_tested", "false_positive_count", "activation_committed",
            "pmi", "dry_run_active", "software_conditions_met", "separation_ratio",
            "separation_ratio_ok", "touchpad_recapture_complete", "hardware_conditions_met",
            "fully_ready", "blocking_conditions", "notes", "created_at",
        ]:
            self.assertIn(key, snap, f"Missing key: {key}")
        self.assertIsInstance(snap["blocking_conditions"], list)
        self.assertEqual(len(snap["blocking_conditions"]), 2)
        self.assertEqual(snap["software_conditions_met"], 5)
        self.assertFalse(snap["fully_ready"])

    def test_8_tool_74_returns_software_conditions_met_and_fully_ready(self):
        """Tool #74 get_tournament_readiness returns software_conditions_met and fully_ready."""
        import json
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        # Pre-seed a snapshot
        store.insert_tournament_readiness_snapshot(
            n_tested=50, false_positive_count=0,
            activation_committed=0, pmi=0, dry_run_active=1,
            software_conditions_met=2,
            separation_ratio=0.362, separation_ratio_ok=0,
            touchpad_recapture_complete=0, hardware_conditions_met=0,
            fully_ready=0,
            blocking_conditions_json=json.dumps(["separation_ratio_gt_1"]),
            notes="tool_test"
        )
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_tournament_readiness", {})
        self.assertIn("software_conditions_met", result)
        self.assertIn("fully_ready", result)
        self.assertFalse(result["fully_ready"])
        self.assertTrue(result.get("found", False))


if __name__ == "__main__":
    unittest.main()
