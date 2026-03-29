"""
Phase 130A — USB Feedback Backoff + P256 Log Dedup + Snapshot Writer +
VAPISwarmOperatorGate (Bridge+SDK) — 8 tests

test_1_swarm_quorum_log_empty
test_2_insert_swarm_quorum_validation_roundtrip
test_3_schema_version_130
test_4_endpoint_6_keys
test_5_tool_98_structure
test_6_feedback_consecutive_timeout_backoff
test_7_batcher_p256_suppression_after_first
test_8_separation_snapshot_write_flag
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from vapi_bridge.store import Store


def _make_store(tmp_path=None):
    if tmp_path is None:
        tmp_path = tempfile.mkdtemp()
    db_path = os.path.join(tmp_path, "test_phase130.db")
    return Store(db_path=db_path)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 60
    cfg.swarm_operator_gate_address = kwargs.get("swarm_operator_gate_address", "")
    cfg.separation_ratio_current = kwargs.get("separation_ratio_current", 0.0)
    return cfg


class TestPhase130SwarmQuorumStore(unittest.TestCase):
    """Tests 1–3: store layer"""

    def test_1_swarm_quorum_log_empty(self):
        store = _make_store()
        rows = store.get_swarm_quorum_validation_log()
        self.assertEqual(rows, [])

    def test_2_insert_swarm_quorum_validation_roundtrip(self):
        store = _make_store()
        row_id = store.insert_swarm_quorum_validation(
            node_count=5,
            distinct_stakers=3,
            quorum_valid=True,
            gate_address="0xDeadBeef",
        )
        self.assertGreater(row_id, 0)
        rows = store.get_swarm_quorum_validation_log(limit=1)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["node_count"], 5)
        self.assertEqual(row["distinct_stakers"], 3)
        self.assertTrue(bool(row["quorum_valid"]))
        self.assertEqual(row["gate_address"], "0xDeadBeef")

    def test_3_schema_version_130(self):
        store = _make_store()
        import sqlite3
        con = sqlite3.connect(store._db_path)
        try:
            row = con.execute(
                "SELECT migration_name FROM schema_versions WHERE phase=130"
            ).fetchone()
            self.assertIsNotNone(row, "schema_versions must have phase=130 row")
            self.assertEqual(row[0], "swarm_operator_gate")
        finally:
            con.close()


class TestPhase130Endpoint(unittest.TestCase):
    """Test 4: REST endpoint"""

    def test_4_endpoint_6_keys(self):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app

        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg=cfg, store=store)
        client = TestClient(app)
        resp = client.get("/agent/swarm-operator-gate-status?api_key=test-key")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        required = {
            "swarm_gate_address", "gate_configured", "total_validations",
            "last_valid", "last_node_count", "timestamp",
        }
        for key in required:
            self.assertIn(key, body, f"Missing key: {key}")


class TestPhase130Tool98(unittest.TestCase):
    """Test 5: BridgeAgent Tool #98"""

    def test_5_tool_98_structure(self):
        from vapi_bridge.bridge_agent import BridgeAgent, _TOOLS
        # Tool #98 must be in the tools list
        tool_names = [t["name"] for t in _TOOLS]
        self.assertIn("get_swarm_operator_gate_status", tool_names)

        store = _make_store()
        cfg = _make_cfg(swarm_operator_gate_address="")
        agent = BridgeAgent(cfg=cfg, store=store)
        result = agent._execute_tool("get_swarm_operator_gate_status", {})
        required = {"gate_configured", "valid", "node_count", "timestamp", "error"}
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")
        # gate_configured=False when swarm_operator_gate_address=""
        self.assertFalse(result["gate_configured"])


class TestPhase130USBBackoff(unittest.TestCase):
    """Test 6: USB feedback consecutive timeout backoff constants"""

    def test_6_feedback_consecutive_timeout_backoff(self):
        from vapi_bridge import dualshock_integration as _di
        # Constants must exist with plan-specified values
        self.assertTrue(
            hasattr(_di, "_FEEDBACK_SKIP_THRESHOLD"),
            "_FEEDBACK_SKIP_THRESHOLD constant missing from dualshock_integration",
        )
        self.assertTrue(
            hasattr(_di, "_FEEDBACK_COOLDOWN_MOD"),
            "_FEEDBACK_COOLDOWN_MOD constant missing from dualshock_integration",
        )
        self.assertEqual(_di._FEEDBACK_SKIP_THRESHOLD, 3)
        self.assertEqual(_di._FEEDBACK_COOLDOWN_MOD, 10)

        # _consecutive_fb_timeouts instance variable: verify by inspecting __init__
        # We can't instantiate DualShockIntegration without HID, so inspect source
        src = Path(_di.__file__).read_text(encoding="utf-8")
        self.assertIn("_consecutive_fb_timeouts", src,
                      "_consecutive_fb_timeouts not found in dualshock_integration.py")


class TestPhase130BatcherP256Suppression(unittest.TestCase):
    """Test 7: Batcher P256 dead-letter log suppression"""

    def test_7_batcher_p256_suppression_after_first(self):
        from vapi_bridge import batcher as _bat
        # _p256_unavailable flag must be initialized in __init__
        src = Path(_bat.__file__).read_text(encoding="utf-8")
        self.assertIn("_p256_unavailable", src,
                      "_p256_unavailable not found in batcher.py")

        # Verify the flag is initialized to False and that the logic
        # sets it to True after first hit (inspect source for pattern)
        # Accepts both `self._p256_unavailable = False` and annotated form `...: bool = False`
        self.assertTrue(
            "self._p256_unavailable = False" in src or
            "self._p256_unavailable: bool = False" in src,
            "Batcher.__init__ must initialize self._p256_unavailable to False",
        )
        self.assertIn("self._p256_unavailable = True", src,
                      "P256 detection block must set self._p256_unavailable = True after first warning")


class TestPhase130SnapshotWriteFlag(unittest.TestCase):
    """Test 8: analyze_interperson_separation.py --write-snapshot flag"""

    def test_8_separation_snapshot_write_flag(self):
        analyze_path = (
            Path(__file__).parent.parent.parent
            / "scripts"
            / "analyze_interperson_separation.py"
        )
        self.assertTrue(analyze_path.exists(),
                        f"analyze_interperson_separation.py not found at {analyze_path}")
        src = analyze_path.read_text(encoding="utf-8")
        self.assertIn("--write-snapshot", src,
                      "--write-snapshot flag not found in analyze_interperson_separation.py")
        self.assertIn("--db", src,
                      "--db flag not found in analyze_interperson_separation.py")
        self.assertIn("insert_separation_ratio_snapshot", src,
                      "insert_separation_ratio_snapshot not called in snapshot write block")


if __name__ == "__main__":
    unittest.main()
