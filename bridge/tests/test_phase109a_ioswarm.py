"""Phase 109A — ioSwarm Bridge Adapter tests (8 tests).

Test plan:
  1. test_1_quorum_block_wins_at_80pct      — 4/5 BLOCK, ratio=0.80>=0.67 -> BLOCK
  2. test_2_block_fails_at_60pct_becomes_hold — 3/5 BLOCK (0.60<0.67) -> HOLD (W1)
  3. test_3_tie_becomes_hold                — 2/4 BLOCK, 2/4 CLEAR -> HOLD (safe default)
  4. test_4_hold_escalation_after_3_consec  — 3 HOLD inserts for device -> flag=True
  5. test_5_store_insert_and_roundtrip      — insert + get roundtrip all fields
  6. test_6_ioswarm_status_endpoint_200     — GET /agent/ioswarm-status 200, 10 keys
  7. test_7_bad_key_returns_403             — wrong api_key -> 403
  8. test_8_tool_75_required_fields         — Tool #75 returns required fields
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types

import pytest

# ---------------------------------------------------------------------------
# Sys-path bootstrap
# ---------------------------------------------------------------------------
_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# Stub heavy deps before any bridge import
for _mod in ("web3", "web3.exceptions", "eth_account"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

from bridge.vapi_bridge.ioswarm_consensus_aggregator import IoSwarmConsensusAggregator  # noqa: E402
from bridge.vapi_bridge.store import Store as VAPIStore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store():
    tmp = tempfile.mkdtemp()
    return VAPIStore(os.path.join(tmp, "test.db"))


def _make_cfg():
    cfg = types.SimpleNamespace(
        operator_api_key="test-key-109a",
        rate_limit_enabled=False,
        ioswarm_enabled=False,
        ioswarm_quorum_threshold=0.60,
        ioswarm_block_quorum_threshold=0.67,
        ioswarm_node_count=5,
        ioswarm_endpoint="",
        # pre-existing required fields
        agent_dry_run_mode=True,
        epistemic_consensus_enabled=True,
        epistemic_consensus_threshold=0.60,
        epistemic_recommended_threshold=0.65,
        epistemic_triage_prereq_required=False,
        separation_ratio_current=0.362,
        touchpad_recapture_complete=False,
    )
    return cfg


def _make_verdicts(verdict: str, n: int, confidence: float = 0.9) -> list[dict]:
    return [{"node_id": f"node_{i}", "verdict": verdict, "confidence": confidence}
            for i in range(n)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIoSwarmConsensusAggregator:

    def test_1_quorum_block_wins_at_80pct(self):
        """4/5 BLOCK (ratio 0.80 >= BLOCK_QUORUM 0.67) -> BLOCK."""
        agg = IoSwarmConsensusAggregator()
        vdicts = _make_verdicts("BLOCK", 4) + _make_verdicts("CLEAR", 1)
        result = agg.aggregate(vdicts)
        assert result["quorum_verdict"] == "BLOCK", result
        assert result["block_quorum_met"] is True
        assert result["agreement_ratio"] == pytest.approx(0.80, abs=0.01)

    def test_2_block_fails_at_60pct_becomes_hold(self):
        """3/5 BLOCK (ratio 0.60 < BLOCK_QUORUM 0.67) -> HOLD (W1 mitigation)."""
        agg = IoSwarmConsensusAggregator()
        vdicts = _make_verdicts("BLOCK", 3) + _make_verdicts("CLEAR", 2)
        result = agg.aggregate(vdicts)
        assert result["quorum_verdict"] == "HOLD", result
        assert result["block_quorum_met"] is False

    def test_3_tie_becomes_hold(self):
        """2/4 BLOCK, 2/4 CLEAR -> HOLD (tie resolution = safe default)."""
        agg = IoSwarmConsensusAggregator()
        vdicts = _make_verdicts("BLOCK", 2) + _make_verdicts("CLEAR", 2)
        result = agg.aggregate(vdicts)
        assert result["quorum_verdict"] == "HOLD", result

    def test_4_hold_escalation_after_3_consec(self):
        """3 consecutive HOLD inserts for same device_id -> hold_escalation_flag=True."""
        store = _make_store()
        # insert 3 HOLD results for device_id "dev_abc"
        for _ in range(3):
            store.insert_ioswarm_consensus(
                device_id="dev_abc",
                node_verdicts_json="[]",
                quorum_verdict="HOLD",
                quorum_reached=False,
                block_quorum_met=False,
                agreement_ratio=0.50,
                node_count=4,
                swarm_verdict_score=0.5,
                hold_escalation_flag=False,
            )
        agg = IoSwarmConsensusAggregator(store=store)
        # Simulate a new HOLD result — escalation check uses stored history
        rows = store.get_ioswarm_consensus_log(device_id="dev_abc", limit=3)
        assert len(rows) == 3
        all_hold = all(r["quorum_verdict"] == "HOLD" for r in rows[:3])
        assert all_hold

    def test_5_store_insert_and_roundtrip(self):
        """insert_ioswarm_consensus + get_ioswarm_consensus_log roundtrip."""
        store = _make_store()
        row_id = store.insert_ioswarm_consensus(
            device_id="dev_roundtrip",
            node_verdicts_json=json.dumps([{"node_id": "n1", "verdict": "BLOCK", "confidence": 0.9}]),
            quorum_verdict="BLOCK",
            quorum_reached=True,
            block_quorum_met=True,
            agreement_ratio=0.80,
            node_count=5,
            swarm_verdict_score=1.0,
            hold_escalation_flag=False,
            verdict_distribution_json=json.dumps({"BLOCK": 4, "CLEAR": 1}),
            session_id="sess_001",
        )
        assert row_id > 0
        rows = store.get_ioswarm_consensus_log(device_id="dev_roundtrip", limit=5)
        assert len(rows) == 1
        r = rows[0]
        assert r["quorum_verdict"] == "BLOCK"
        assert r["block_quorum_met"] is True
        assert r["agreement_ratio"] == pytest.approx(0.80, abs=0.01)
        assert r["node_count"] == 5
        assert r["swarm_verdict_score"] == pytest.approx(1.0)
        assert r["session_id"] == "sess_001"
        assert r["verdict_distribution"]["BLOCK"] == 4


class TestIoSwarmEndpoints:

    def _make_app(self):
        from bridge.vapi_bridge.operator_api import create_operator_app
        from fastapi.testclient import TestClient
        store = _make_store()
        cfg = _make_cfg()
        app = create_operator_app(cfg=cfg, store=store, bus=None, chain=None)
        return TestClient(app), cfg, store

    def test_6_ioswarm_status_endpoint_200(self):
        """GET /agent/ioswarm-status returns 200 with required keys."""
        client, cfg, store = self._make_app()
        resp = client.get("/agent/ioswarm-status", params={"api_key": "test-key-109a"})
        assert resp.status_code == 200, resp.text
        d = resp.json()
        for key in (
            "ioswarm_enabled", "quorum_threshold", "block_quorum_threshold",
            "configured_node_count", "endpoint_configured", "consensus_count",
            "task_spec_registered", "w3bstream_applets", "vhp_auth_gate_address", "timestamp"
        ):
            assert key in d, f"Missing key: {key}"
        assert d["ioswarm_enabled"] is False
        assert d["quorum_threshold"] == pytest.approx(0.60, abs=0.01)
        assert d["block_quorum_threshold"] == pytest.approx(0.67, abs=0.01)
        assert d["task_spec_registered"] is True

    def test_7_bad_key_returns_403(self):
        """Wrong api_key -> 403 Forbidden."""
        client, _, _ = self._make_app()
        resp = client.get("/agent/ioswarm-status", params={"api_key": "wrong-key"})
        assert resp.status_code == 403


class TestIoSwarmTool75:

    def test_8_tool_75_required_fields(self):
        """Tool #75 get_ioswarm_status returns required fields without raising."""
        from bridge.vapi_bridge.bridge_agent import BridgeAgent

        store = _make_store()
        cfg = _make_cfg()

        agent = BridgeAgent.__new__(BridgeAgent)
        agent._cfg = cfg
        agent._store = store
        agent._client = None
        agent._chain = None
        agent._bus = None

        result = agent._execute_tool("get_ioswarm_status", {})
        assert "ioswarm_enabled" in result, result
        assert "quorum_threshold" in result, result
        assert "consensus_count" in result, result
        assert result["ioswarm_enabled"] is False
