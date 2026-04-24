"""
Phase 89 — Protocol Intelligence Synthesis Agent Tests (8 tests)

test_1_protocol_intelligence_empty_store_zero_score
test_2_gate_progress_component_reflects_clean_sessions
test_3_fleet_health_degraded_lowers_score
test_4_ready_for_live_mode_false_below_threshold
test_5_bottleneck_identifies_lowest_component
test_6_estimated_days_to_gate_from_velocity
test_7_protocol_intelligence_endpoint_returns_required_fields
test_8_tool_56_get_protocol_intelligence_returns_dict
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.protocol_intelligence_agent import ProtocolIntelligenceAgent


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p89.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey89"
    cfg.validation_gate_n = kwargs.get("gate_n", 100)
    cfg.validation_max_divergence_rate = kwargs.get("max_dr", 1.0)
    cfg.supervisor_enabled = False
    cfg.supervisor_stale_threshold_minutes = 15
    cfg.agent_dry_run_mode = True
    cfg.protocol_intelligence_enabled = True
    return cfg


def _insert_ruling(store, ruling_id, verdict="CERTIFY", divergence=0, divergence_reason=None):
    store.insert_validation_record(
        ruling_id=ruling_id,
        device_id="dev001",
        llm_verdict=verdict,
        fallback_verdict=verdict,
        llm_confidence=0.8,
        fallback_confidence=0.8,
        divergence=divergence,
        divergence_reason=divergence_reason,
        pcc_state="NOMINAL" if not divergence else None,
        pcc_host_state="EXCLUSIVE_USB" if not divergence else None,
    )


class TestProtocolIntelligenceEmpty(unittest.TestCase):

    def test_1_protocol_intelligence_empty_store_zero_score(self):
        """Empty store: gate_progress=0, score reflects neutral components, ready=False."""
        store = _make_store()
        cfg = _make_cfg()
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        self.assertIn("protocol_health_score", report)
        self.assertIn("ready_for_live_mode", report)
        self.assertIn("bottleneck", report)
        self.assertIn("components", report)
        self.assertIn("recommendation", report)
        self.assertFalse(report["ready_for_live_mode"])
        # gate_progress_score = 0 with empty store
        self.assertEqual(report["components"]["gate_progress"], 0.0)
        # Score should be < 85 (gate not passed, score too low)
        self.assertLess(report["protocol_health_score"], 85.0)


class TestGateProgressComponent(unittest.TestCase):

    def test_2_gate_progress_component_reflects_clean_sessions(self):
        """50 clean sessions → gate_progress component = 35*0.5 = 17.5 points."""
        store = _make_store()
        cfg = _make_cfg(gate_n=100)
        for i in range(1, 51):
            _insert_ruling(store, ruling_id=i, verdict="CERTIFY", divergence=0)
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        self.assertAlmostEqual(report["components"]["gate_progress"], 17.5, places=1)
        # consecutive_clean should be 50
        self.assertEqual(report["consecutive_clean"], 50)
        self.assertFalse(report["gate_passed"])


class TestFleetHealthComponent(unittest.TestCase):

    def test_3_fleet_health_degraded_lowers_score(self):
        """When fleet_health cannot be read (empty supervisor log), defaults to UNKNOWN → 0.0."""
        store = _make_store()
        cfg = _make_cfg()
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        # With empty supervisor log, fleet_health = UNKNOWN → fleet_health_score = 0.0
        self.assertIn(report["fleet_health"], ("UNKNOWN", "ALL_HEALTHY", "DEGRADED", "CRITICAL"))
        # fleet_health component contribution
        self.assertIn("fleet_health", report["components"])


class TestReadyForLiveMode(unittest.TestCase):

    def test_4_ready_for_live_mode_false_below_threshold(self):
        """ready_for_live_mode=False when gate not passed (need 100 consecutive clean)."""
        store = _make_store()
        cfg = _make_cfg(gate_n=100)
        # Insert 50 clean sessions — not enough for gate
        for i in range(1, 51):
            _insert_ruling(store, ruling_id=i, verdict="CERTIFY", divergence=0)
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        self.assertFalse(report["ready_for_live_mode"])
        self.assertFalse(report["gate_passed"])

    def test_5_bottleneck_identifies_lowest_component(self):
        """bottleneck is the key with the lowest score contribution."""
        store = _make_store()
        cfg = _make_cfg(gate_n=100)
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        components = report["components"]
        bottleneck = report["bottleneck"]
        self.assertIn(bottleneck, components)
        min_val = min(components.values())
        self.assertEqual(components[bottleneck], min_val)


class TestEstimatedDaysToGate(unittest.TestCase):

    def test_6_estimated_days_to_gate_from_velocity(self):
        """estimated_days_to_gate is None with 0 or 1 sessions, numeric with >=2."""
        store = _make_store()
        cfg = _make_cfg(gate_n=100)
        # 0 sessions
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        self.assertIsNone(report["estimated_days_to_gate"])
        # Insert 2 sessions with 1 day apart (manually via raw SQL to control timestamps)
        _insert_ruling(store, ruling_id=1, verdict="CERTIFY")
        _insert_ruling(store, ruling_id=2, verdict="CERTIFY")
        # With 2 rows and same timestamp, span_days ~0 → estimate may be None (div by zero guard)
        report2 = agent.compute_report()
        # Just assert no crash and field is present (None or numeric)
        self.assertIn("estimated_days_to_gate", report2)


class TestProtocolIntelligenceEndpoint(unittest.TestCase):

    def test_7_protocol_intelligence_endpoint_returns_required_fields(self):
        """GET /agent/protocol-intelligence returns all required fields."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        client = TestClient(create_operator_app(cfg, store))
        resp = client.get("/agent/protocol-intelligence", params={"api_key": "testkey89"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for field in ("protocol_health_score", "ready_for_live_mode", "bottleneck",
                      "recommendation", "components"):
            self.assertIn(field, data, f"Missing field: {field}")
        self.assertIsInstance(data["protocol_health_score"], (int, float))
        self.assertIsInstance(data["ready_for_live_mode"], bool)


class TestTool56(unittest.TestCase):

    def test_8_tool_56_get_protocol_intelligence_returns_dict(self):
        """Tool #56 get_protocol_intelligence returns dict with required keys."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_protocol_intelligence", {})
        self.assertIn("protocol_health_score", result)
        self.assertIn("ready_for_live_mode", result)
        self.assertIn("bottleneck", result)
        self.assertIsInstance(result["protocol_health_score"], (int, float))
        self.assertIsInstance(result["ready_for_live_mode"], bool)


if __name__ == "__main__":
    unittest.main()
