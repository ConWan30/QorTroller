"""
Phase 91 — Divergence Triage Agent Tests (8 tests)

test_1_triage_agent_empty_store_no_patterns
test_2_triage_detects_class_j_ml_bot_cluster
test_3_triage_detects_cheat_code_cluster
test_4_single_class_j_divergence_not_escalated
test_5_triage_insert_and_retrieve_from_store
test_6_triage_report_endpoint_returns_escalations
test_7_protocol_intelligence_includes_triage_score
test_8_tool_58_get_triage_report_returns_dict
"""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.divergence_triage_agent import DivergenceTriageAgent
from vapi_bridge.protocol_intelligence_agent import ProtocolIntelligenceAgent


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p91.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey91"
    cfg.validation_gate_n = kwargs.get("gate_n", 100)
    cfg.validation_max_divergence_rate = 1.0
    cfg.supervisor_enabled = False
    cfg.supervisor_stale_threshold_minutes = 15
    cfg.agent_dry_run_mode = True
    cfg.divergence_triage_enabled = True
    cfg.protocol_intelligence_enabled = True
    return cfg


def _insert_diverged(store, ruling_id, device_id, divergence_reason_dict):
    """Insert a diverged ruling_validation_log entry with non-nominal reason."""
    store.insert_validation_record(
        ruling_id=ruling_id,
        device_id=device_id,
        llm_verdict="CERTIFY",
        fallback_verdict="BLOCK",
        llm_confidence=0.8,
        fallback_confidence=0.9,
        divergence=1,
        divergence_reason=json.dumps(divergence_reason_dict),
    )


class TestTriageEmptyStore(unittest.TestCase):

    def test_1_triage_agent_empty_store_no_patterns(self):
        """Empty store: _triage_cycle runs without error, no reports generated."""
        store = _make_store()
        cfg = _make_cfg()
        agent = DivergenceTriageAgent(cfg, store)
        # Run synchronously via asyncio
        asyncio.get_event_loop().run_until_complete(agent._triage_cycle())
        reports = store.get_divergence_triage_report()
        self.assertEqual(len(reports), 0)


class TestTriageMLBotCluster(unittest.TestCase):

    def test_2_triage_detects_class_j_ml_bot_cluster(self):
        """Device with 2+ HIGH class_j_ml_bot_risk divergences → escalated=1."""
        store = _make_store()
        cfg = _make_cfg()
        agent = DivergenceTriageAgent(cfg, store)
        dev = "dev_mlbot_" + "a" * 55
        _insert_diverged(store, 1, dev, {"class_j_ml_bot_risk": "HIGH", "ml_bot_candidate": True})
        _insert_diverged(store, 2, dev, {"class_j_ml_bot_risk": "HIGH"})
        asyncio.get_event_loop().run_until_complete(agent._triage_cycle())
        reports = store.get_divergence_triage_report()
        dev_report = next((r for r in reports if r["device_id"] == dev), None)
        self.assertIsNotNone(dev_report)
        self.assertEqual(dev_report["escalated"], 1)
        self.assertIn("ml_bot_cluster", dev_report["patterns"])
        self.assertEqual(dev_report["ml_bot_high_count"], 2)


class TestTriageCheatCluster(unittest.TestCase):

    def test_3_triage_detects_cheat_code_cluster(self):
        """Device with even 1 hard_cheat_codes divergence → escalated=1 (cheat_cluster)."""
        store = _make_store()
        cfg = _make_cfg()
        agent = DivergenceTriageAgent(cfg, store)
        dev = "dev_cheat_" + "b" * 55
        _insert_diverged(store, 10, dev, {"hard_cheat_codes": ["0x28"]})
        asyncio.get_event_loop().run_until_complete(agent._triage_cycle())
        reports = store.get_divergence_triage_report()
        dev_report = next((r for r in reports if r["device_id"] == dev), None)
        self.assertIsNotNone(dev_report)
        self.assertEqual(dev_report["escalated"], 1)
        self.assertIn("cheat_cluster", dev_report["patterns"])


class TestTriageSingleDivergenceNotEscalated(unittest.TestCase):

    def test_4_single_class_j_divergence_not_escalated(self):
        """1 HIGH class_j divergence (below threshold of 2) → escalated=0."""
        store = _make_store()
        cfg = _make_cfg()
        agent = DivergenceTriageAgent(cfg, store)
        dev = "dev_single_" + "c" * 54
        _insert_diverged(store, 20, dev, {"class_j_ml_bot_risk": "HIGH"})
        asyncio.get_event_loop().run_until_complete(agent._triage_cycle())
        reports = store.get_divergence_triage_report()
        dev_report = next((r for r in reports if r["device_id"] == dev), None)
        self.assertIsNotNone(dev_report)
        self.assertEqual(dev_report["escalated"], 0)
        self.assertIsNone(dev_report["patterns"])


class TestTriageStoreOperations(unittest.TestCase):

    def test_5_triage_insert_and_retrieve_from_store(self):
        """insert_divergence_triage_report + get_divergence_triage_report round-trip."""
        store = _make_store()
        row_id = store.insert_divergence_triage_report(
            device_id="dev_store_test",
            divergence_count=3,
            escalated=1,
            patterns="ml_bot_cluster:2x_HIGH",
            ml_bot_high_count=2,
            cheat_count=0,
            enrollment_anomaly_count=0,
        )
        self.assertGreater(row_id, 0)
        reports = store.get_divergence_triage_report()
        self.assertEqual(len(reports), 1)
        r = reports[0]
        self.assertEqual(r["device_id"], "dev_store_test")
        self.assertEqual(r["escalated"], 1)
        self.assertEqual(r["ml_bot_high_count"], 2)


class TestTriageEndpoint(unittest.TestCase):

    def test_6_triage_report_endpoint_returns_escalations(self):
        """GET /agent/triage-report returns entries with escalated_count."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg()
        store.insert_divergence_triage_report("dev1", 3, 1, "ml_bot_cluster:2x_HIGH", 2, 0, 0)
        store.insert_divergence_triage_report("dev2", 1, 0, None, 0, 0, 0)
        client = TestClient(create_operator_app(cfg, store))
        resp = client.get("/agent/triage-report", params={"api_key": "testkey91"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("entries", data)
        self.assertIn("escalated_count", data)
        self.assertIn("clean_count", data)
        self.assertGreaterEqual(data["escalated_count"], 1)


class TestTriageProtocolIntegration(unittest.TestCase):

    def test_7_protocol_intelligence_includes_triage_score(self):
        """When triage reports exist, protocol_health_score includes triage_confidence component."""
        store = _make_store()
        cfg = _make_cfg()
        # 2 clean devices, 1 escalated
        store.insert_divergence_triage_report("d1", 1, 0, None, 0, 0, 0)
        store.insert_divergence_triage_report("d2", 1, 0, None, 0, 0, 0)
        store.insert_divergence_triage_report("d3", 2, 1, "cheat_cluster:1x_codes", 0, 1, 0)
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        self.assertIn("triage_confidence", report["components"])
        # triage_confidence_score = 2/3 → component = 0.05*(2/3)*100 ≈ 3.33
        self.assertAlmostEqual(report["components"]["triage_confidence"], 3.33, places=1)


class TestTool58(unittest.TestCase):

    def test_8_tool_58_get_triage_report_returns_dict(self):
        """Tool #58 get_triage_report returns dict with entries and escalated_count."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg()
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_triage_report", {})
        self.assertIn("entries", result)
        self.assertIn("escalated_count", result)
        self.assertIn("clean_count", result)
        self.assertIsInstance(result["entries"], list)


if __name__ == "__main__":
    unittest.main()
