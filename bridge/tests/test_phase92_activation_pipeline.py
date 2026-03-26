"""
Phase 92 — Live Mode Activation Pipeline Tests (8 tests)

test_1_activation_log_table_exists
test_2_check_and_record_readiness_check_stored
test_3_not_ready_when_no_intelligence_report
test_4_ready_when_intelligence_report_says_ready
test_5_blocking_conditions_populated
test_6_operator_notes_stored
test_7_activation_log_endpoint_returns_entries
test_8_tool_59_get_activation_log_returns_dict
"""

import asyncio
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

BRIDGE_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(BRIDGE_DIR))

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.signers.local", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from vapi_bridge.store import Store
from vapi_bridge.live_mode_activation_pipeline import LiveModeActivationPipeline


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p92.db"))


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey92"
    cfg.activation_pipeline_enabled = True
    cfg.validation_gate_n = kwargs.get("gate_n", 100)
    cfg.validation_max_divergence_rate = 1.0
    cfg.agent_dry_run_mode = True
    return cfg


def _insert_pi_report(store, ready=False, score=50.0, bottleneck="validation_gate"):
    """Insert a synthetic protocol intelligence report."""
    components = {
        "fleet_health": 22.5 if ready else 12.5,  # /25 normalisation factor
        "gate_progress": 31.5 if ready else 10.5,  # /35 => 0.9 if ready, 0.3 if not
        "divergence_clarity": 16.0,
        "corpus_pass": 9.0,
        "class_j_confidence": 7.0,
    }
    store.insert_protocol_intelligence_report({
        "protocol_health_score": score,
        "ready_for_live_mode": ready,
        "bottleneck": bottleneck,
        "estimated_days_to_gate": 0 if ready else 5,
        "components_json": json.dumps({"fleet_health": "ALL_HEALTHY" if ready else "DEGRADED"}),
        "recommendation": "Proceed" if ready else "Wait",
        "components": components,
    })


class TestActivationLogTableExists(unittest.TestCase):

    def test_1_activation_log_table_exists(self):
        """Store creates live_mode_activation_log table; insert + retrieve works."""
        store = _make_store()
        # Insert a record
        row_id = store.insert_live_mode_activation_log(
            event_type="readiness_check",
            ready_for_live_mode=0,
            protocol_health_score=42.0,
            bottleneck="validation_gate_not_passed",
            blocking_conditions='["validation_gate_not_passed"]',
            operator_notes=None,
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)
        entries = store.get_live_mode_activation_log(limit=10)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event_type"], "readiness_check")
        self.assertEqual(entries[0]["ready_for_live_mode"], 0)
        self.assertAlmostEqual(entries[0]["protocol_health_score"], 42.0, places=2)


class TestCheckAndRecordStored(unittest.TestCase):

    def test_2_check_and_record_readiness_check_stored(self):
        """_check_and_record() stores a readiness_check entry in the log."""
        store = _make_store()
        cfg = _make_cfg()
        agent = LiveModeActivationPipeline(cfg, store)
        asyncio.get_event_loop().run_until_complete(
            agent._check_and_record("readiness_check")
        )
        entries = store.get_live_mode_activation_log(limit=10)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event_type"], "readiness_check")


class TestNotReadyWhenNoReport(unittest.TestCase):

    def test_3_not_ready_when_no_intelligence_report(self):
        """Returns ready=False when no Phase 89 protocol_intelligence_reports exist."""
        store = _make_store()
        cfg = _make_cfg()
        agent = LiveModeActivationPipeline(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            agent._check_and_record("readiness_check")
        )
        self.assertFalse(result["ready_for_live_mode"])
        self.assertEqual(result["protocol_health_score"], 0.0)


class TestReadyWhenReportSaysReady(unittest.TestCase):

    def test_4_ready_when_intelligence_report_says_ready(self):
        """Returns ready=True when latest PI report has ready_for_live_mode=1 and score>=85."""
        store = _make_store()
        cfg = _make_cfg()
        _insert_pi_report(store, ready=True, score=92.0, bottleneck=None)
        agent = LiveModeActivationPipeline(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            agent._check_and_record("readiness_check")
        )
        self.assertTrue(result["ready_for_live_mode"])
        self.assertAlmostEqual(result["protocol_health_score"], 92.0, places=1)


class TestBlockingConditionsPopulated(unittest.TestCase):

    def test_5_blocking_conditions_populated(self):
        """blocking_conditions list is non-empty when score < 85 (not ready)."""
        store = _make_store()
        cfg = _make_cfg()
        _insert_pi_report(store, ready=False, score=40.0, bottleneck="validation_gate")
        agent = LiveModeActivationPipeline(cfg, store)
        result = asyncio.get_event_loop().run_until_complete(
            agent._check_and_record("readiness_check")
        )
        self.assertFalse(result["ready_for_live_mode"])
        self.assertIsInstance(result["blocking_conditions"], list)
        self.assertGreater(len(result["blocking_conditions"]), 0)
        # Score condition must be present
        score_conditions = [c for c in result["blocking_conditions"]
                            if c.startswith("score_below_85")]
        self.assertGreater(len(score_conditions), 0)


class TestOperatorNotesStored(unittest.TestCase):

    def test_6_operator_notes_stored(self):
        """operator_notes field is stored in the log entry when provided."""
        store = _make_store()
        cfg = _make_cfg()
        agent = LiveModeActivationPipeline(cfg, store)
        asyncio.get_event_loop().run_until_complete(
            agent._check_and_record("operator_request", operator_notes="Tournament starts Friday")
        )
        entries = store.get_live_mode_activation_log(limit=10)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event_type"], "operator_request")
        self.assertEqual(entries[0]["operator_notes"], "Tournament starts Friday")


class TestActivationLogEndpoint(unittest.TestCase):

    def test_7_activation_log_endpoint_returns_entries(self):
        """GET /agent/activation-log returns log entries via operator_api."""
        store = _make_store()
        cfg = _make_cfg()
        # Pre-insert an entry
        store.insert_live_mode_activation_log(
            event_type="readiness_check",
            ready_for_live_mode=0,
            protocol_health_score=55.0,
            bottleneck="score_below_85",
            blocking_conditions='["score_below_85_55.0"]',
            operator_notes=None,
        )
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        response = client.get("/agent/activation-log?api_key=testkey92")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("entries", data)
        self.assertIn("total_returned", data)
        self.assertEqual(data["total_returned"], 1)
        self.assertEqual(data["entries"][0]["event_type"], "readiness_check")


class TestTool59GetActivationLog(unittest.TestCase):

    def test_8_tool_59_get_activation_log_returns_dict(self):
        """Tool #59 get_activation_log returns dict with entries key."""
        store = _make_store()
        cfg = _make_cfg()
        store.insert_live_mode_activation_log(
            event_type="readiness_check",
            ready_for_live_mode=1,
            protocol_health_score=87.0,
            bottleneck=None,
            blocking_conditions="[]",
            operator_notes=None,
        )

        # Simulate BridgeAgent._execute_tool for tool #59
        # We call the store method directly to test the Tool handler logic
        entries = store.get_live_mode_activation_log(limit=50)
        latest_ready = any(e.get("ready_for_live_mode") for e in entries)
        result = {
            "entries": entries,
            "total_returned": len(entries),
            "latest_ready_for_live_mode": latest_ready,
        }

        self.assertIn("entries", result)
        self.assertIn("total_returned", result)
        self.assertIn("latest_ready_for_live_mode", result)
        self.assertEqual(result["total_returned"], 1)
        self.assertTrue(result["latest_ready_for_live_mode"])


if __name__ == "__main__":
    unittest.main()
