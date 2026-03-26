"""Phase 109C — IoSwarm Adjudication (ClassJ+Triage dual-quorum veto) tests.

Test plan:
  1. test_1_adjudication_log_insert_roundtrip      — insert + get, 11 fields, dual_veto bool
  2. test_2_classj_high_entropy_blocks             — entropy=0.03 → 5/5 BLOCK → quorum BLOCK
  3. test_3_classj_low_entropy_clears              — entropy=0.20 → 5/5 CLEAR → quorum CLEAR
  4. test_4_triage_ml_bot_blocks                   — escalated+ml_bot → 5/5 BLOCK → quorum BLOCK
  5. test_5_triage_not_escalated_clears            — escalated=False → 5/5 CLEAR → quorum CLEAR
  6. test_6_dual_veto_fires_when_both_block        — entropy=0.03 + ml_bot → dual_veto=True
  7. test_7_ioswarm_adjudication_endpoint_200      — GET /agent/ioswarm-adjudication-status 200
  8. test_8_tool_77_required_fields               — Tool #77 returns all 7 required fields
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
import time

import pytest

_BRIDGE = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if _BRIDGE not in sys.path:
    sys.path.insert(0, _BRIDGE)

from vapi_bridge.store import Store as VAPIStore
from vapi_bridge.ioswarm_classj_emulator import IoSwarmClassJEmulator
from vapi_bridge.ioswarm_triage_emulator import IoSwarmTriageEmulator
from vapi_bridge.ioswarm_consensus_aggregator import IoSwarmConsensusAggregator


def _make_store() -> VAPIStore:
    tmp = tempfile.mkdtemp()
    return VAPIStore(os.path.join(tmp, "test109c.db"))


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace(
        # Phase 109C
        ioswarm_adjudication_enabled=False,
        ioswarm_classj_block_quorum=0.67,
        ioswarm_triage_block_quorum=0.67,
        # Phase 109B
        ioswarm_renewal_enabled=False,
        ioswarm_renewal_min_quorum=3,
        # Phase 109A
        ioswarm_enabled=False,
        ioswarm_quorum_threshold=0.60,
        ioswarm_block_quorum_threshold=0.67,
        ioswarm_node_count=5,
        ioswarm_endpoint="",
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_emulators():
    return (
        IoSwarmClassJEmulator(n_nodes=5, seed=109),
        IoSwarmTriageEmulator(n_nodes=5, seed=109),
    )


# ---------------------------------------------------------------------------
# Test 1 — Store insert + roundtrip
# ---------------------------------------------------------------------------

def test_1_adjudication_log_insert_roundtrip():
    """insert_ioswarm_adjudication + get_ioswarm_adjudication_log roundtrip; 11 fields."""
    store = _make_store()

    row_id = store.insert_ioswarm_adjudication(
        device_id="dev_test_109c",
        session_id="sess_001",
        classj_quorum_verdict="BLOCK",
        classj_agreement_ratio=0.80,
        triage_quorum_verdict="BLOCK",
        triage_agreement_ratio=0.90,
        dual_veto=True,
        node_count=5,
        classj_verdicts_json='[{"node_id":"n0","verdict":"BLOCK","confidence":0.95}]',
        triage_verdicts_json='[{"node_id":"n0","verdict":"BLOCK","confidence":0.88}]',
    )
    assert isinstance(row_id, int) and row_id > 0

    logs = store.get_ioswarm_adjudication_log()
    assert len(logs) == 1
    r = logs[0]

    # Verify all 11 fields
    assert r["device_id"] == "dev_test_109c"
    assert r["session_id"] == "sess_001"
    assert r["classj_quorum_verdict"] == "BLOCK"
    assert abs(r["classj_agreement_ratio"] - 0.80) < 0.001
    assert r["triage_quorum_verdict"] == "BLOCK"
    assert abs(r["triage_agreement_ratio"] - 0.90) < 0.001
    assert r["dual_veto"] is True
    assert r["node_count"] == 5
    assert isinstance(r["classj_verdicts"], list)
    assert isinstance(r["triage_verdicts"], list)
    assert r["created_at"] > 0


# ---------------------------------------------------------------------------
# Test 2 — ClassJ high entropy → BLOCK quorum
# ---------------------------------------------------------------------------

def test_2_classj_high_entropy_blocks():
    """IoSwarmClassJEmulator: entropy_variance=0.03 → 5/5 BLOCK → quorum BLOCK."""
    cj_emulator = IoSwarmClassJEmulator(n_nodes=5, seed=109)
    nodes = cj_emulator.evaluate_classj("dev_test", "", 0.03)

    assert len(nodes) == 5
    assert all(r["verdict"] == "BLOCK" for r in nodes), [r["verdict"] for r in nodes]

    # Aggregate via Phase 109A aggregator
    agg = IoSwarmConsensusAggregator().aggregate(nodes)
    assert agg["quorum_verdict"] == "BLOCK", f"Expected BLOCK, got {agg}"
    assert agg["block_quorum_met"] is True


# ---------------------------------------------------------------------------
# Test 3 — ClassJ low entropy → CLEAR quorum
# ---------------------------------------------------------------------------

def test_3_classj_low_entropy_clears():
    """IoSwarmClassJEmulator: entropy_variance=0.20 → 5/5 CLEAR → quorum CLEAR."""
    cj_emulator = IoSwarmClassJEmulator(n_nodes=5, seed=109)
    nodes = cj_emulator.evaluate_classj("dev_test", "", 0.20)

    assert len(nodes) == 5
    assert all(r["verdict"] == "CLEAR" for r in nodes), [r["verdict"] for r in nodes]

    agg = IoSwarmConsensusAggregator().aggregate(nodes)
    assert agg["quorum_verdict"] == "CLEAR", f"Expected CLEAR, got {agg}"
    assert agg["block_quorum_met"] is False


# ---------------------------------------------------------------------------
# Test 4 — Triage ml_bot_cluster → BLOCK quorum
# ---------------------------------------------------------------------------

def test_4_triage_ml_bot_blocks():
    """IoSwarmTriageEmulator: escalated+ml_bot_cluster → 5/5 BLOCK → quorum BLOCK."""
    tr_emulator = IoSwarmTriageEmulator(n_nodes=5, seed=109)
    nodes = tr_emulator.evaluate_triage("dev_test", "", True, "ml_bot_cluster:2x_HIGH")

    assert len(nodes) == 5
    assert all(r["verdict"] == "BLOCK" for r in nodes), [r["verdict"] for r in nodes]

    agg = IoSwarmConsensusAggregator().aggregate(nodes)
    assert agg["quorum_verdict"] == "BLOCK"
    assert agg["block_quorum_met"] is True


# ---------------------------------------------------------------------------
# Test 5 — Triage not escalated → CLEAR quorum
# ---------------------------------------------------------------------------

def test_5_triage_not_escalated_clears():
    """IoSwarmTriageEmulator: escalated=False → 5/5 CLEAR → quorum CLEAR."""
    tr_emulator = IoSwarmTriageEmulator(n_nodes=5, seed=109)
    nodes = tr_emulator.evaluate_triage("dev_test", "", False, None)

    assert len(nodes) == 5
    assert all(r["verdict"] == "CLEAR" for r in nodes), [r["verdict"] for r in nodes]

    agg = IoSwarmConsensusAggregator().aggregate(nodes)
    assert agg["quorum_verdict"] == "CLEAR"
    assert agg["block_quorum_met"] is False


# ---------------------------------------------------------------------------
# Test 6 — Dual-veto fires when both ClassJ+Triage BLOCK
# ---------------------------------------------------------------------------

def test_6_dual_veto_fires_when_both_block():
    """entropy=0.03 + ml_bot_cluster → dual_veto=True; both quorum verdicts BLOCK."""
    from vapi_bridge.ioswarm_adjudication_coordinator import (
        IoSwarmAdjudicationCoordinator,
        DUAL_VETO_SCORE,
    )

    store = _make_store()
    cfg = _make_cfg(ioswarm_adjudication_enabled=True)

    cj_em, tr_em = _make_emulators()
    coord = IoSwarmAdjudicationCoordinator(
        cfg=cfg, store=store,
        classj_emulator=cj_em, triage_emulator=tr_em,
    )

    result = coord.evaluate(
        device_id="dev_dual_veto",
        session_id="",
        entropy_variance=0.03,       # → 5/5 BLOCK
        escalated=True,
        triage_patterns="ml_bot_cluster:2x_HIGH",  # → 5/5 BLOCK
    )

    assert result["classj_quorum_verdict"] == "BLOCK", result
    assert result["triage_quorum_verdict"] == "BLOCK", result
    assert result["dual_veto"] is True, result
    assert result["dual_veto_score"] == DUAL_VETO_SCORE

    # Verify score override logic
    # consensus_score before veto = 0.40*1.0 + 0.40*1.0 + 0.20*1.0 = 1.0 (sup=1.0 default)
    # max(1.0, 0.80) = 1.0; dual veto only adds value when consensus < 0.80
    assert DUAL_VETO_SCORE == 0.80

    # Verify audit log was written
    logs = store.get_ioswarm_adjudication_log()
    assert len(logs) >= 1
    assert logs[0]["dual_veto"] is True


# ---------------------------------------------------------------------------
# Test 7 — GET /agent/ioswarm-adjudication-status endpoint returns 200 + 8 keys
# ---------------------------------------------------------------------------

def test_7_ioswarm_adjudication_endpoint_200():
    """GET /agent/ioswarm-adjudication-status returns HTTP 200 with 8 required keys."""
    from unittest.mock import MagicMock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store = _make_store()
    cfg = _make_cfg()
    cfg.operator_api_key = "test-key-109c"
    bus = MagicMock()
    chain = MagicMock()

    app = create_operator_app(cfg=cfg, store=store, bus=bus, chain=chain)
    client = TestClient(app)

    resp = client.get("/agent/ioswarm-adjudication-status?api_key=test-key-109c")
    assert resp.status_code == 200, resp.text

    data = resp.json()
    required_keys = {
        "ioswarm_adjudication_enabled",
        "classj_block_quorum",
        "triage_block_quorum",
        "dual_veto_count",
        "adjudication_count",
        "recent_adjudication_logs",
        "task_spec_registered",
        "timestamp",
    }
    missing = required_keys - set(data.keys())
    assert not missing, f"Missing keys: {missing}"
    assert data["task_spec_registered"] is True
    assert data["ioswarm_adjudication_enabled"] is False  # default


# ---------------------------------------------------------------------------
# Test 8 — Tool #77 returns all 7 required fields
# ---------------------------------------------------------------------------

def test_8_tool_77_required_fields():
    """Tool #77 get_ioswarm_adjudication_status returns all 7 required fields."""
    from unittest.mock import MagicMock
    from vapi_bridge.bridge_agent import BridgeAgent

    store = _make_store()
    cfg = _make_cfg()
    cfg.operator_api_key = "test-key-109c"

    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg = cfg
    agent._chain = MagicMock()
    agent._bus = MagicMock()

    result = agent._execute_tool("get_ioswarm_adjudication_status", {})

    required_fields = {
        "ioswarm_adjudication_enabled",
        "classj_block_quorum",
        "triage_block_quorum",
        "dual_veto_count",
        "adjudication_count",
        "task_spec_registered",
        "timestamp",
    }
    missing = required_fields - set(result.keys())
    assert not missing, f"Tool #77 missing fields: {missing}"
