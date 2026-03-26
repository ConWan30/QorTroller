"""
Phase 84 — Live Mode Gate Completion + Adjudication Warm-Up Tests (6 tests)

test_1_compute_gate_attestation_hash_is_deterministic
test_2_gate_attestation_store_round_trip
test_3_warm_up_runner_returns_report_with_llm_available_field
test_4_warm_up_runner_empty_store_no_crash
test_5_gate_readiness_endpoint_returns_composite_status
test_6_tool_53_get_gate_readiness_returns_dict
"""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local",
             "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.adjudication_warm_up import (
    AdjudicationWarmUpRunner,
    compute_gate_attestation_hash,
)


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p84.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey84"
    cfg.supervisor_enabled = True
    cfg.supervisor_stale_threshold_minutes = 15
    cfg.validation_gate_n = 100
    cfg.validation_max_divergence_rate = 1.0
    cfg.agent_dry_run_mode = True
    cfg.warm_up_batch_size = kwargs.get("batch_size", 5)
    return cfg


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# 1. Gate attestation hash determinism
# ---------------------------------------------------------------------------

class TestGateAttestationHash(unittest.TestCase):

    def test_1_compute_gate_attestation_hash_is_deterministic(self):
        """Same inputs always produce the same 64-char hex hash."""
        h1 = compute_gate_attestation_hash(
            consecutive_clean=100,
            gate_n=100,
            divergence_rate=0.0,
            timestamp_ns=1711000000000000000,
        )
        h2 = compute_gate_attestation_hash(
            consecutive_clean=100,
            gate_n=100,
            divergence_rate=0.0,
            timestamp_ns=1711000000000000000,
        )
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex = 64 chars
        # Different consecutive_clean → different hash
        h3 = compute_gate_attestation_hash(
            consecutive_clean=101,
            gate_n=100,
            divergence_rate=0.0,
            timestamp_ns=1711000000000000000,
        )
        self.assertNotEqual(h1, h3)


# ---------------------------------------------------------------------------
# 2. Store round-trip
# ---------------------------------------------------------------------------

class TestGateAttestationStore(unittest.TestCase):

    def test_2_gate_attestation_store_round_trip(self):
        """insert_gate_attestation persists; get_gate_attestations returns it."""
        store = _make_store()
        attestation_hash = compute_gate_attestation_hash(
            consecutive_clean=100,
            gate_n=100,
            divergence_rate=0.0,
            timestamp_ns=1711000000000000000,
        )
        row_id = store.insert_gate_attestation(
            attestation_hash=attestation_hash,
            consecutive_clean=100,
            gate_n=100,
            divergence_rate=0.0,
            on_chain_tx=None,
        )
        self.assertIsNotNone(row_id)

        rows = store.get_gate_attestations(limit=10)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["attestation_hash"], attestation_hash)
        self.assertEqual(row["consecutive_clean"], 100)
        self.assertEqual(row["gate_n"], 100)
        self.assertAlmostEqual(row["divergence_rate"], 0.0)

        # INSERT OR IGNORE — duplicate hash is silent no-op
        store.insert_gate_attestation(
            attestation_hash=attestation_hash,
            consecutive_clean=100,
            gate_n=100,
            divergence_rate=0.0,
        )
        self.assertEqual(len(store.get_gate_attestations(limit=10)), 1)


# ---------------------------------------------------------------------------
# 3. WarmUpRunner report shape
# ---------------------------------------------------------------------------

class TestWarmUpRunner(unittest.TestCase):

    def test_3_warm_up_runner_returns_report_with_llm_available_field(self):
        """WarmUpReport always contains llm_available and fallback_count (W1)."""
        store = _make_store()
        cfg = _make_cfg()
        runner = AdjudicationWarmUpRunner(cfg, store)
        report = _run(runner.run_warm_up(device_ids=[]))  # no devices → trivially complete
        self.assertIn("llm_available", report)
        self.assertIn("fallback_count", report)
        self.assertIn("completed", report)
        self.assertIn("failed", report)
        self.assertIn("duration_ms", report)
        self.assertIn("device_ids_attempted", report)
        self.assertIsInstance(report["llm_available"], bool)
        self.assertIsInstance(report["fallback_count"], int)

    def test_4_warm_up_runner_empty_store_no_crash(self):
        """No devices in store → WarmUpRunner returns completed=0, no exception."""
        store = _make_store()
        cfg = _make_cfg()
        runner = AdjudicationWarmUpRunner(cfg, store)
        report = _run(runner.run_warm_up())  # auto-selects recent devices from empty store
        self.assertEqual(report["completed"], 0)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["device_ids_attempted"], [])


# ---------------------------------------------------------------------------
# 4. Gate readiness REST endpoint
# ---------------------------------------------------------------------------

class TestGateReadinessEndpoint(unittest.TestCase):

    def test_5_gate_readiness_endpoint_returns_composite_status(self):
        """GET /agent/gate-readiness returns overall_ready, validation_gate, fleet_health."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        client = TestClient(create_operator_app(cfg, store))
        resp = client.get(
            "/agent/gate-readiness",
            params={"api_key": "testkey84"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("overall_ready", data)
        self.assertIn("validation_gate", data)
        self.assertIn("fleet_health", data)
        self.assertIn("dry_run_active", data)
        self.assertIn("gate_attestations_count", data)
        self.assertIsInstance(data["overall_ready"], bool)


# ---------------------------------------------------------------------------
# 5. Tool #53
# ---------------------------------------------------------------------------

class TestGateReadinessTool(unittest.TestCase):

    def test_6_tool_53_get_gate_readiness_returns_dict(self):
        """Tool #53 get_gate_readiness returns dict with overall_ready + sections."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_gate_readiness", {})
        self.assertIn("overall_ready", result)
        self.assertIn("validation_gate", result)
        self.assertIn("fleet_health", result)
        self.assertIn("gate_attestations_count", result)
        self.assertIsInstance(result["overall_ready"], bool)


if __name__ == "__main__":
    unittest.main()
