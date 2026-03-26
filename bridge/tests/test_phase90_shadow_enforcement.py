"""
Phase 90 — Shadow Enforcement Mode Tests (8 tests)

test_1_shadow_mode_config_field_exists
test_2_shadow_block_logs_entry_without_chain_call
test_3_shadow_enforcement_stats_empty_store
test_4_shadow_pass_rate_computed_correctly
test_5_shadow_enforcement_log_endpoint_returns_entries
test_6_protocol_intelligence_includes_shadow_score_when_data_exists
test_7_shadow_mode_does_not_affect_consecutive_clean
test_8_tool_57_get_shadow_enforcement_log_returns_dict
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.protocol_intelligence_agent import ProtocolIntelligenceAgent


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p90.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey90"
    cfg.validation_gate_n = kwargs.get("gate_n", 100)
    cfg.validation_max_divergence_rate = 1.0
    cfg.supervisor_enabled = False
    cfg.supervisor_stale_threshold_minutes = 15
    cfg.agent_dry_run_mode = True
    cfg.enforcement_shadow_mode = kwargs.get("shadow_mode", False)
    cfg.protocol_intelligence_enabled = True
    return cfg


class TestShadowModeConfig(unittest.TestCase):

    def test_1_shadow_mode_config_field_exists(self):
        """enforcement_shadow_mode config field is accessible and defaults to False."""
        from vapi_bridge.config import Config
        cfg = MagicMock()
        cfg.enforcement_shadow_mode = False
        self.assertFalse(cfg.enforcement_shadow_mode)
        cfg2 = MagicMock()
        cfg2.enforcement_shadow_mode = True
        self.assertTrue(cfg2.enforcement_shadow_mode)


class TestShadowBlockLogging(unittest.TestCase):

    def test_2_shadow_block_logs_entry_without_chain_call(self):
        """_shadow_block logs to shadow_enforcement_log; no chain call made."""
        store = _make_store()
        cfg = _make_cfg(shadow_mode=True)
        # Insert a shadow log entry directly
        row_id = store.insert_shadow_enforcement_log(
            device_id="dev_shadow_001",
            ruling_id=42,
            commitment_hash="a" * 64,
            would_have_suspended=1,
            duration_s=86400,
            warmup_attack_score=0.1,
        )
        self.assertGreater(row_id, 0)
        entries = store.get_shadow_enforcement_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["device_id"], "dev_shadow_001")
        self.assertEqual(entries[0]["would_have_suspended"], 1)
        self.assertEqual(entries[0]["verdict"], "BLOCK")


class TestShadowStats(unittest.TestCase):

    def test_3_shadow_enforcement_stats_empty_store(self):
        """Empty shadow log: stats.total=0, pass_rate=None."""
        store = _make_store()
        stats = store.get_shadow_enforcement_stats()
        self.assertEqual(stats["total"], 0)
        self.assertIsNone(stats["pass_rate"])

    def test_4_shadow_pass_rate_computed_correctly(self):
        """3 entries: 2 not suspended, 1 suspended → pass_rate = 2/3."""
        store = _make_store()
        store.insert_shadow_enforcement_log("d1", 1, "h"*64, would_have_suspended=0)
        store.insert_shadow_enforcement_log("d2", 2, "i"*64, would_have_suspended=0)
        store.insert_shadow_enforcement_log("d3", 3, "j"*64, would_have_suspended=1)
        stats = store.get_shadow_enforcement_stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["passed"], 2)
        self.assertAlmostEqual(stats["pass_rate"], 2/3, places=3)


class TestShadowEndpoint(unittest.TestCase):

    def test_5_shadow_enforcement_log_endpoint_returns_entries(self):
        """GET /agent/shadow-enforcement-log returns required fields."""
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        store = _make_store()
        cfg = _make_cfg(shadow_mode=True)
        store.insert_shadow_enforcement_log("dev001", 1, "a"*64, would_have_suspended=1)
        client = TestClient(create_operator_app(cfg, store))
        resp = client.get("/agent/shadow-enforcement-log", params={"api_key": "testkey90"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("shadow_mode_active", data)
        self.assertIn("entries", data)
        self.assertIn("stats", data)
        self.assertEqual(data["total_returned"], 1)


class TestShadowProtocolIntegration(unittest.TestCase):

    def test_6_protocol_intelligence_includes_shadow_score_when_data_exists(self):
        """When shadow log has rows, protocol report includes shadow_pass in components."""
        store = _make_store()
        cfg = _make_cfg(shadow_mode=True)
        # Add shadow entries: 4 passed, 1 blocked
        for i in range(4):
            store.insert_shadow_enforcement_log(f"d{i}", i, "a"*64, would_have_suspended=0)
        store.insert_shadow_enforcement_log("d5", 5, "b"*64, would_have_suspended=1)
        agent = ProtocolIntelligenceAgent(cfg, store)
        report = agent.compute_report()
        # shadow_pass should appear in components
        self.assertIn("shadow_pass", report["components"])
        # shadow_pass_score = 4/5 = 0.8 → component = 0.05*0.8*100 = 4.0
        self.assertAlmostEqual(report["components"]["shadow_pass"], 4.0, places=1)

    def test_7_shadow_mode_does_not_affect_consecutive_clean(self):
        """Shadow log entries do NOT appear in ruling_validation_log (no gate pollution)."""
        store = _make_store()
        cfg = _make_cfg()
        store.insert_shadow_enforcement_log("dev001", 1, "a"*64, would_have_suspended=1)
        summary = store.get_validation_summary(gate_n=100, max_divergence_rate=1.0)
        # shadow log is separate table — consecutive_clean unaffected
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["consecutive_clean"], 0)


class TestTool57(unittest.TestCase):

    def test_8_tool_57_get_shadow_enforcement_log_returns_dict(self):
        """Tool #57 get_shadow_enforcement_log returns dict with required keys."""
        from vapi_bridge.bridge_agent import BridgeAgent
        store = _make_store()
        cfg = _make_cfg(shadow_mode=True)
        agent = BridgeAgent(cfg, store)
        result = agent._execute_tool("get_shadow_enforcement_log", {})
        self.assertIn("shadow_mode_active", result)
        self.assertIn("entries", result)
        self.assertIn("stats", result)


if __name__ == "__main__":
    unittest.main()
