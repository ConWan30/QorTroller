"""
Phase 221 — ProtocolCoherenceAgent / ProtocolCoherenceRegistry Tests
T221-1..10

Tests:
  T221-1:  insert_protocol_coherence_log stores entry correctly
  T221-2:  get_protocol_coherence_status returns 6 expected keys
  T221-3:  get_protocol_coherence_status with no data returns empty sentinel
  T221-4:  get_protocol_coherence_history returns entries in reverse chronological order
  T221-5:  protocol_coherence_enabled config defaults to False
  T221-6:  protocol_coherence_anchor_interval_s config defaults to 3600
  T221-7:  GET /agent/protocol-coherence-status returns 200 with 7 keys
  T221-8:  GET /agent/protocol-coherence-status returns total_anchors=0 with no data
  T221-9:  ProtocolCoherenceAgent._compute_merkle_root returns consistent 32-byte result
  T221-10: different agent sets produce different Merkle roots
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# ── web3 / eth_account stubs ──────────────────────────────────────────────────
import types

for _mod in ("web3", "web3.exceptions", "eth_account", "eth_account.messages",
             "web3.middleware", "web3.gas_strategies", "web3.gas_strategies.time_based"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_fake_web3 = sys.modules["web3"]
if not hasattr(_fake_web3, "Web3"):
    class _W3Stub:
        HTTPProvider = lambda *a, **kw: None
        class middleware_onion:
            inject = lambda *a, **kw: None
    _fake_web3.Web3 = _W3Stub

_fake_exc = sys.modules["web3.exceptions"]
if not hasattr(_fake_exc, "ContractLogicError"):
    _fake_exc.ContractLogicError = type("ContractLogicError", (Exception,), {})


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test221.db"))


# ── T221-1: insert_protocol_coherence_log stores entry ───────────────────────
def test_T221_1_insert_protocol_coherence_log():
    """insert_protocol_coherence_log stores entry and returns a row id."""
    store = _make_store()
    row_id = store.insert_protocol_coherence_log(
        merkle_root="abcd" * 16,
        agent_count=36,
        anchor_hash="",
        on_chain_confirmed=False,
    )
    assert isinstance(row_id, int)
    assert row_id >= 1


# ── T221-2: get_protocol_coherence_status returns 6 expected keys ─────────────
def test_T221_2_get_protocol_coherence_status_keys():
    """get_protocol_coherence_status returns 6 expected keys after insert."""
    store = _make_store()
    store.insert_protocol_coherence_log(
        merkle_root="cafe" * 16, agent_count=36,
    )
    result = store.get_protocol_coherence_status()
    expected = {
        "total_anchors", "latest_merkle_root", "agent_count",
        "on_chain_confirmed", "last_anchor_ts", "timestamp",
    }
    assert expected.issubset(set(result.keys()))
    assert result["total_anchors"] == 1
    assert result["agent_count"] == 36
    assert result["on_chain_confirmed"] is False


# ── T221-3: get_protocol_coherence_status with no data ───────────────────────
def test_T221_3_get_protocol_coherence_status_empty():
    """get_protocol_coherence_status returns empty sentinel with no data."""
    store = _make_store()
    result = store.get_protocol_coherence_status()
    assert result["total_anchors"] == 0
    assert result["latest_merkle_root"] is None
    assert result["agent_count"] == 0
    assert result["on_chain_confirmed"] is False
    assert result["last_anchor_ts"] is None


# ── T221-4: get_protocol_coherence_history reverse order ─────────────────────
def test_T221_4_get_protocol_coherence_history_order():
    """get_protocol_coherence_history returns entries in reverse chronological order."""
    store = _make_store()
    # Insert 3 entries with slightly different timestamps
    store.insert_protocol_coherence_log("aaa1" * 16, agent_count=36)
    time.sleep(0.01)
    store.insert_protocol_coherence_log("bbb2" * 16, agent_count=36)
    time.sleep(0.01)
    store.insert_protocol_coherence_log("ccc3" * 16, agent_count=36)
    history = store.get_protocol_coherence_history(limit=3)
    assert len(history) == 3
    # Most recent first
    assert history[0]["merkle_root"] == "ccc3" * 16
    assert history[1]["merkle_root"] == "bbb2" * 16
    assert history[2]["merkle_root"] == "aaa1" * 16


# ── T221-5: protocol_coherence_enabled defaults to False ─────────────────────
def test_T221_5_config_default_false():
    """protocol_coherence_enabled config field defaults to False."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.protocol_coherence_enabled is False


# ── T221-6: protocol_coherence_anchor_interval_s defaults to 3600 ────────────
def test_T221_6_config_interval_default():
    """protocol_coherence_anchor_interval_s config field defaults to 3600."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.protocol_coherence_anchor_interval_s == 3600


# ── T221-7: GET /agent/protocol-coherence-status returns 7 keys ──────────────
def test_T221_7_endpoint_returns_correct_keys():
    """GET /agent/protocol-coherence-status returns all 7 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store221 = _make_store()
    cfg221   = Config()
    app221   = create_operator_app(cfg221, store221)
    client   = TestClient(app221)

    resp = client.get("/agent/protocol-coherence-status")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "protocol_coherence_enabled", "total_anchors", "latest_merkle_root",
        "agent_count", "on_chain_confirmed", "last_anchor_ts", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T221-8: GET /agent/protocol-coherence-status with no data ─────────────────
def test_T221_8_endpoint_empty_state():
    """GET /agent/protocol-coherence-status returns total_anchors=0 with no data."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store221 = _make_store()
    cfg221   = Config()
    app221   = create_operator_app(cfg221, store221)
    client   = TestClient(app221)

    resp = client.get("/agent/protocol-coherence-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_anchors"] == 0
    assert body["latest_merkle_root"] is None
    assert body["on_chain_confirmed"] is False
    assert body["protocol_coherence_enabled"] is False


# ── T221-9: _compute_merkle_root returns consistent 32-byte result ────────────
def test_T221_9_compute_merkle_root_consistent():
    """ProtocolCoherenceAgent._compute_merkle_root returns consistent 32-byte result."""
    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent
    import hashlib

    leaves = [hashlib.sha256(f"agent_{i}".encode()).digest() for i in range(36)]
    root1 = ProtocolCoherenceAgent._compute_merkle_root(leaves)
    root2 = ProtocolCoherenceAgent._compute_merkle_root(leaves)
    assert isinstance(root1, bytes)
    assert len(root1) == 32
    assert root1 == root2  # deterministic


# ── T221-10: different agent sets produce different Merkle roots ──────────────
def test_T221_10_different_agent_sets_different_roots():
    """Different agent sets produce different Merkle roots."""
    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent
    import hashlib

    ts = int(time.time_ns())
    leaves_a = [ProtocolCoherenceAgent._compute_leaf(f"agent_{i}", ts) for i in range(36)]
    leaves_b = [ProtocolCoherenceAgent._compute_leaf(f"agent_{i}", ts) for i in range(35)]
    leaves_b.append(ProtocolCoherenceAgent._compute_leaf("extra_agent", ts))

    root_a = ProtocolCoherenceAgent._compute_merkle_root(leaves_a)
    root_b = ProtocolCoherenceAgent._compute_merkle_root(leaves_b)
    assert root_a != root_b
