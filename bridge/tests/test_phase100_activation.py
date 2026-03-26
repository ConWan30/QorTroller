"""Phase 100 — Live Mode Activation Bootstrap + Activation Status Dashboard.

Tests:
  test_1  store.get_ioid_devices returns list (ioid_devices table, Phase 100)
  test_2  GET /agent/activation-status returns required top-level keys
  test_3  current_blocking_step == 1 when consecutive_clean == 0
  test_4  progress_pct advances proportionally with consecutive_clean
  test_5  current_blocking_step == 4 when gate+cert+audit all pass but dry_run=True
  test_6  fully_activated=True when all 5 conditions met
  test_7  POST /agent/warm-up with device_ids param passes ids to runner
  test_8  Tool #66 get_activation_status returns current_blocking_step

Bridge count: 1392 -> 1400 (+8)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p100.db"))


def _make_cfg(dry_run: bool = True):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey100"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_dry_run_mode = dry_run
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.enforcement_cert_ttl_s = 86400
    cfg.epistemic_consensus_enabled = False
    cfg.agent_model = "claude-sonnet-4-6"
    cfg.mpc_ceremony_hash_cache = None
    cfg.vhp_contract_address = ""
    cfg.layerzero_endpoint_address = ""
    cfg.warm_up_batch_size = 5
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _insert_clean_validation_records(store: Store, n: int) -> None:
    """Insert n clean (divergence=0) validation log records."""
    with store._conn() as conn:
        for i in range(n):
            conn.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                "llm_confidence, fallback_confidence, divergence, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    i + 1000, f"dev_clean_{i}", "CERTIFY", "CERTIFY",
                    0.9, 0.9, 0, time.time() - (n - i),
                ),
            )


def _insert_enforcement_cert(store: Store) -> None:
    """Insert a valid enforcement certificate."""
    now = time.time()
    with store._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO enforcement_certificates "
            "(audit_hash, hmac_sig, audit_valid, gate_attestation_count, "
            "first_ready_check_at, latest_attestation_at, expires_at, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            ("hash_p100", "sig_p100", 1, 1, now - 300, now - 100, now + 86400, now),
        )


def _insert_activation_log_and_gate(store: Store) -> None:
    """Insert activation log + gate attestation for audit_valid=True."""
    ready_ts = time.time() - 200
    att_ts = time.time() - 50
    with store._conn() as conn:
        conn.execute(
            "INSERT INTO live_mode_activation_log "
            "(event_type, ready_for_live_mode, protocol_health_score, bottleneck, "
            "blocking_conditions, operator_notes, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            ("operator_request", 1, 90, "", "[]", "", ready_ts),
        )
        conn.execute(
            "INSERT OR IGNORE INTO gate_attestations "
            "(attestation_hash, consecutive_clean, gate_n, divergence_rate, created_at) "
            "VALUES (?,?,?,?,?)",
            ("att_hash_p100", 100, 100, 0.0, att_ts),
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetIoidDevices(unittest.TestCase):

    def test_1_get_ioid_devices_returns_list(self):
        """store.get_ioid_devices returns list; registered device appears."""
        store = _make_store()
        store.store_ioid_device(
            device_id="dev_ioid_p100",
            device_address="0xabc",
            did="did:io:0xabc",
            tx_hash="0xtx1",
        )
        result = store.get_ioid_devices(limit=1)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["device_id"], "dev_ioid_p100")


class TestActivationStatusEndpoint(unittest.TestCase):

    def test_2_activation_status_returns_required_keys(self):
        """GET /agent/activation-status returns all required top-level keys."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/activation-status",
            params={"api_key": "testkey100"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("steps", "current_blocking_step", "fully_activated",
                    "recommended_action", "warnings", "timestamp"):
            self.assertIn(key, body, f"Missing key: {key}")
        steps = body["steps"]
        for step_key in ("step1_validation_gate", "step2_enforcement_cert",
                         "step3_audit_valid", "step4_live_mode", "step5_vhp_mint"):
            self.assertIn(step_key, steps, f"Missing step: {step_key}")

    def test_3_blocking_step_1_when_no_clean_sessions(self):
        """current_blocking_step == 1 when consecutive_clean == 0."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/activation-status",
            params={"api_key": "testkey100"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["current_blocking_step"], 1)

    def test_4_progress_pct_advances_with_clean_sessions(self):
        """progress_pct == 50.0 when 50 clean sessions recorded (gate_n=100)."""
        store = _make_store()
        cfg = _make_cfg()
        _insert_clean_validation_records(store, 50)
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/activation-status",
            params={"api_key": "testkey100"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        step1 = body["steps"]["step1_validation_gate"]
        self.assertAlmostEqual(step1["progress_pct"], 50.0, places=0)
        self.assertEqual(step1["sessions_remaining"], 50)

    def test_5_blocking_step_4_when_gate_cert_audit_pass_but_dry_run(self):
        """current_blocking_step == 4 when gate+cert+audit pass but dry_run=True."""
        store = _make_store()
        cfg = _make_cfg(dry_run=True)
        _insert_clean_validation_records(store, 100)
        _insert_enforcement_cert(store)
        _insert_activation_log_and_gate(store)
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/activation-status",
            params={"api_key": "testkey100"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["current_blocking_step"], 4)

    def test_6_fully_activated_when_all_conditions_met(self):
        """fully_activated=True when gate+cert+audit all pass and dry_run=False."""
        store = _make_store()
        cfg = _make_cfg(dry_run=False)
        _insert_clean_validation_records(store, 100)
        _insert_enforcement_cert(store)
        _insert_activation_log_and_gate(store)
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get(
            "/agent/activation-status",
            params={"api_key": "testkey100"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["fully_activated"])
        self.assertEqual(body["current_blocking_step"], 6)


class TestWarmUpBootstrap(unittest.TestCase):

    def test_7_warm_up_with_device_ids_param(self):
        """POST /agent/warm-up with device_ids param passes ids to runner."""
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg, store)
        client = TestClient(app, raise_server_exceptions=False)

        captured_ids = []

        async def _mock_run_warm_up(_self, device_ids=None, chain=None):
            if device_ids:
                captured_ids.extend(device_ids)
            return {
                "completed": len(device_ids) if device_ids else 0,
                "failed": 0,
                "llm_available": False,
                "fallback_count": 0,
                "duration_ms": 1.0,
                "device_ids_attempted": list(device_ids) if device_ids else [],
                "batch_size": 5,
                "on_chain_published": False,
                "on_chain_tx": None,
            }

        with patch(
            "vapi_bridge.adjudication_warm_up.AdjudicationWarmUpRunner.run_warm_up",
            new=_mock_run_warm_up,
        ):
            resp = client.post(
                "/agent/warm-up",
                params={"api_key": "testkey100", "device_ids": "dev123"},
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn("dev123", captured_ids)


class TestTool66(unittest.TestCase):

    def test_8_tool_66_returns_current_blocking_step(self):
        """Tool #66 get_activation_status returns current_blocking_step."""
        store = _make_store()
        cfg = _make_cfg()

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._cfg = cfg
        agent._store = store
        agent._chain = None
        agent._bus = None

        result = agent._execute_tool("get_activation_status", {})
        self.assertIn("current_blocking_step", result)
        self.assertIsInstance(result["current_blocking_step"], int)
        self.assertIn("fully_activated", result)
        self.assertIn("consecutive_clean", result)
        self.assertIn("gate_n", result)
        self.assertIn("progress_pct", result)
