"""Phase 98 — Epistemic Consensus Protocol tests.

Tests:
  test_1  epistemic_consensus_log table exists + insert/get methods
  test_2  _epistemic_consensus: non-BLOCK verdicts returned unchanged
  test_3  _epistemic_consensus: BLOCK with zero evidence → HOLD (consensus_score=0.2)
  test_4  _epistemic_consensus: BLOCK with HIGH ClassJ → consensus_score=0.60 (reaches threshold)
  test_5  _epistemic_consensus: BLOCK with ClassJ+Triage HIGH → consensus_score≥0.60 → BLOCK
  test_6  disabled: epistemic_consensus_enabled=False → BLOCK returned unchanged
  test_7  GET /agent/epistemic-consensus-log returns entries + downgraded_count
  test_8  Tool #64 get_epistemic_consensus_log returns dict with entries

Bridge count: 1364 → 1372 (+8)
"""
import asyncio
import sys
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store


def _make_store() -> Store:
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_p98.db"))


def _make_cfg(consensus_enabled=True, threshold=0.60):
    cfg = MagicMock()
    cfg.operator_api_key = "testkey98"
    cfg.rate_limit_per_minute = 10000
    cfg.agent_model = "claude-sonnet-4-6"
    cfg.agent_dry_run_mode = True
    cfg.epistemic_consensus_enabled = consensus_enabled
    cfg.epistemic_consensus_threshold = threshold
    cfg.class_j_detection_enabled = True
    cfg.class_j_entropy_windows = 10
    cfg.enforcement_cert_ttl_s = 86400
    # Phase 104/105: required to avoid MagicMock truthy values breaking threshold logic
    cfg.epistemic_recommended_threshold = threshold  # same as base so PMI auto-raise has no effect
    cfg.epistemic_triage_prereq_required = False
    # Phase 109A/109B/109C: prevent MagicMock truthy attr from routing to ioSwarm branches
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.poad_registry_enabled = False  # Phase 111: prevent MagicMock truthy attr from routing to Step D
    return cfg


def _make_adjudicator(store, cfg):
    from vapi_bridge.session_adjudicator import SessionAdjudicator
    adj = SessionAdjudicator.__new__(SessionAdjudicator)
    adj._store = store
    adj._cfg = cfg
    adj._bus = None
    return adj


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestEpistemicConsensusStore(unittest.TestCase):

    def test_1_table_exists_and_methods_work(self):
        """epistemic_consensus_log table exists; insert/get methods work."""
        store = _make_store()
        rid = store.insert_epistemic_consensus(
            device_id="dev_a",
            ruling_id=1,
            proposed_verdict="BLOCK",
            class_j_score=1.0,
            triage_score=1.0,
            supervisor_score=1.0,
            consensus_score=1.0,
            threshold=0.60,
            consensus_reached=True,
            final_verdict="BLOCK",
            downgraded=False,
        )
        self.assertIsNotNone(rid)
        entries = store.get_epistemic_consensus_log()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["device_id"], "dev_a")
        self.assertFalse(entries[0]["downgraded"])

        # Downgraded entry
        store.insert_epistemic_consensus(
            device_id="dev_b",
            ruling_id=2,
            proposed_verdict="BLOCK",
            class_j_score=0.0,
            triage_score=0.0,
            supervisor_score=1.0,
            consensus_score=0.20,
            threshold=0.60,
            consensus_reached=False,
            final_verdict="HOLD",
            downgraded=True,
        )
        entries = store.get_epistemic_consensus_log()
        self.assertEqual(len(entries), 2)
        # Device filter
        filtered = store.get_epistemic_consensus_log(device_id="dev_a")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["device_id"], "dev_a")


class TestEpistemicConsensusLogic(unittest.TestCase):

    def test_2_non_block_verdict_unchanged(self):
        """Non-BLOCK verdicts (CERTIFY, FLAG, HOLD) returned unchanged without consensus check."""
        store = _make_store()
        cfg = _make_cfg()
        adj = _make_adjudicator(store, cfg)

        for verdict in ("CERTIFY", "FLAG", "HOLD"):
            result = _run(adj._epistemic_consensus("dev_x", verdict))
            self.assertEqual(result, verdict, f"{verdict} should pass through unchanged")

        # No log entries — non-BLOCK skips consensus entirely
        entries = store.get_epistemic_consensus_log()
        self.assertEqual(len(entries), 0)

    def test_3_block_with_no_evidence_downgraded_to_hold(self):
        """BLOCK with empty store → supervisor_score=1.0 only → consensus=0.20 < 0.60 → HOLD."""
        store = _make_store()
        cfg = _make_cfg(threshold=0.60)
        adj = _make_adjudicator(store, cfg)

        result = _run(adj._epistemic_consensus("dev_empty", "BLOCK"))
        # Only supervisor_score=1.0 fires (no class_j, no triage data)
        # consensus_score = 0.40*0 + 0.40*0 + 0.20*1.0 = 0.20 < 0.60
        self.assertEqual(result, "HOLD")

        entries = store.get_epistemic_consensus_log(device_id="dev_empty")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["proposed_verdict"], "BLOCK")
        self.assertEqual(entry["final_verdict"], "HOLD")
        self.assertTrue(entry["downgraded"])
        self.assertAlmostEqual(entry["consensus_score"], 0.20, delta=0.01)

    def test_4_block_with_high_class_j_exactly_reaches_threshold(self):
        """BLOCK with HIGH ClassJ only → consensus=0.40*1+0.20*1=0.60 = threshold → BLOCK kept."""
        store = _make_store()
        cfg = _make_cfg(threshold=0.60)
        adj = _make_adjudicator(store, cfg)

        # Insert HIGH Class J for device
        store.insert_class_j_assessment(
            device_id="dev_classj",
            entropy_variance=0.01,  # HIGH (<0.05)
            risk_level="HIGH",
            window_count=10,
        )

        result = _run(adj._epistemic_consensus("dev_classj", "BLOCK"))
        # consensus = 0.40*1.0(classJ) + 0.40*0.0(triage) + 0.20*1.0(supervisor) = 0.60
        # 0.60 >= 0.60 threshold → consensus_reached → BLOCK kept
        entries = store.get_epistemic_consensus_log(device_id="dev_classj")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        # score should be ~0.60
        self.assertAlmostEqual(entry["consensus_score"], 0.60, delta=0.01)
        # consensus_reached depends on whether >= threshold (0.60 >= 0.60 = True)
        self.assertEqual(entry["consensus_reached"], 1)
        self.assertEqual(result, "BLOCK")

    def test_5_block_with_classj_and_triage_high_consensus_reached(self):
        """BLOCK with ClassJ HIGH + triage escalated → score=0.80 → BLOCK."""
        store = _make_store()
        cfg = _make_cfg(threshold=0.60)
        adj = _make_adjudicator(store, cfg)

        # Insert HIGH Class J
        store.insert_class_j_assessment(
            device_id="dev_full",
            entropy_variance=0.01,
            risk_level="HIGH",
            window_count=10,
        )
        # Insert escalated triage report
        store.insert_divergence_triage_report(
            device_id="dev_full",
            divergence_count=3,
            escalated=1,
            patterns="ml_bot_cluster",
            ml_bot_high_count=2,
            cheat_count=0,
            enrollment_anomaly_count=0,
        )

        result = _run(adj._epistemic_consensus("dev_full", "BLOCK"))
        # consensus = 0.40*1.0 + 0.40*1.0 + 0.20*1.0 = 1.0 >= 0.60 → BLOCK
        self.assertEqual(result, "BLOCK")
        entries = store.get_epistemic_consensus_log(device_id="dev_full")
        self.assertEqual(len(entries), 1)
        self.assertAlmostEqual(entries[0]["consensus_score"], 1.0, delta=0.01)
        self.assertFalse(entries[0]["downgraded"])

    def test_6_disabled_block_returned_unchanged(self):
        """With epistemic_consensus_enabled=False, BLOCK passes through without consensus."""
        store = _make_store()
        cfg = _make_cfg(consensus_enabled=False)
        adj = _make_adjudicator(store, cfg)

        result = _run(adj._epistemic_consensus("dev_dis", "BLOCK"))
        self.assertEqual(result, "BLOCK")
        # No log entries written when disabled
        entries = store.get_epistemic_consensus_log(device_id="dev_dis")
        self.assertEqual(len(entries), 0)


class TestEpistemicConsensusEndpoint(unittest.TestCase):

    def _make_app_client(self, store, cfg):
        from fastapi.testclient import TestClient
        from vapi_bridge.operator_api import create_operator_app
        app = create_operator_app(cfg, store)
        return TestClient(app)

    def test_7_endpoint_returns_entries_and_downgraded_count(self):
        """GET /agent/epistemic-consensus-log returns entries + downgraded_count."""
        store = _make_store()
        cfg = _make_cfg()
        # Insert one downgraded entry
        store.insert_epistemic_consensus(
            device_id="dev_q", ruling_id=1, proposed_verdict="BLOCK",
            class_j_score=0.0, triage_score=0.0, supervisor_score=1.0,
            consensus_score=0.20, threshold=0.60, consensus_reached=False,
            final_verdict="HOLD", downgraded=True,
        )
        client = self._make_app_client(store, cfg)
        resp = client.get("/agent/epistemic-consensus-log?api_key=testkey98")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("entries", data)
        self.assertIn("count", data)
        self.assertIn("downgraded_count", data)
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["downgraded_count"], 1)


class TestTool64(unittest.TestCase):

    def test_8_tool_64_returns_entries_dict(self):
        """Tool #64 get_epistemic_consensus_log returns dict with entries key."""
        store = _make_store()
        cfg = MagicMock()
        cfg.agent_model = "claude-sonnet-4-6"
        cfg.operator_api_key = "testkey98"

        from vapi_bridge.bridge_agent import BridgeAgent
        agent = BridgeAgent.__new__(BridgeAgent)
        agent._store = store
        agent._cfg = cfg

        result = agent._execute_tool("get_epistemic_consensus_log", {})
        self.assertIn("entries", result)
        self.assertIn("count", result)
        self.assertIn("downgraded_count", result)
        self.assertIsInstance(result["entries"], list)
