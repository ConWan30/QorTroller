"""
Phase 225 — InvariantGate Provenance Chain + Governance History API Tests
T225-1..T225-8

Tests:
  T225-1: insert_governance_provenance() stores record and returns row id
  T225-2: get_latest_governance_provenance_hash() returns '0'*64 on empty table
  T225-3: get_latest_governance_provenance_hash() returns most recent hash after insert
  T225-4: get_governance_provenance_history() returns correct fields and ordering
  T225-5: _compute_governance_provenance_hash() is deterministic within the same ts_ns
  T225-6: GET /agent/allowlist-governance-history returns chain_intact=True for single entry
  T225-7: GET /agent/allowlist-governance-history chain_intact=False when chain broken
  T225-8: POST /agent/allowlist-governance-event with provenance_hash stores chain entry
"""
import os
import sys
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

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
    return Store(os.path.join(d, "test225.db"))


# ── T225-1: insert_governance_provenance() stores record ─────────────────────
def test_T225_1_insert_governance_provenance():
    """insert_governance_provenance() stores record and returns a positive row id."""
    store = _make_store()
    row_id = store.insert_governance_provenance(
        governance_provenance_hash="a" * 64,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="b" * 64,
        reason_category="refactor",
        reason_text="renamed _hash_region helper without semantic change",
    )
    assert isinstance(row_id, int)
    assert row_id >= 1


# ── T225-2: get_latest_governance_provenance_hash() genesis sentinel ──────────
def test_T225_2_latest_provenance_hash_empty():
    """get_latest_governance_provenance_hash() returns '0'*64 on empty table."""
    store = _make_store()
    result = store.get_latest_governance_provenance_hash()
    assert result == "0" * 64


# ── T225-3: get_latest_governance_provenance_hash() after insert ──────────────
def test_T225_3_latest_provenance_hash_after_insert():
    """get_latest_governance_provenance_hash() returns the most recent hash after insert."""
    store = _make_store()
    store.insert_governance_provenance(
        governance_provenance_hash="c" * 64,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="d" * 64,
        reason_category="bugfix",
        reason_text="fixed incorrect threshold validation",
    )
    result = store.get_latest_governance_provenance_hash()
    assert result == "c" * 64


# ── T225-4: get_governance_provenance_history() correct fields + ordering ─────
def test_T225_4_governance_provenance_history():
    """get_governance_provenance_history() returns correct fields ordered newest-first."""
    store = _make_store()
    store.insert_governance_provenance(
        governance_provenance_hash="e" * 64,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="f" * 64,
        reason_category="refactor",
        reason_text="first governance event in chain",
    )
    store.insert_governance_provenance(
        governance_provenance_hash="g" * 64,
        previous_provenance_hash="e" * 64,
        new_allowlist_hash="h" * 64,
        reason_category="bugfix",
        reason_text="second governance event in chain",
    )
    history = store.get_governance_provenance_history(limit=10)
    assert len(history) == 2
    # Newest first
    assert history[0]["governance_provenance_hash"] == "g" * 64
    assert history[1]["governance_provenance_hash"] == "e" * 64
    expected_keys = {
        "id", "governance_provenance_hash", "previous_provenance_hash",
        "new_allowlist_hash", "reason_category", "reason_text", "created_at",
    }
    assert expected_keys.issubset(set(history[0].keys()))


# ── T225-5: _compute_governance_provenance_hash() determinism note ────────────
def test_T225_5_provenance_hash_structure():
    """Provenance hash is 64-char hex SHA-256; structure matches expected inputs."""
    import vapi_invariant_gate as vig
    # The function uses time.time_ns() internally so it is NOT deterministic across calls.
    # Test that it returns a 64-char hex string and changes between different inputs.
    h1 = vig._compute_governance_provenance_hash("0" * 64, "a" * 64, "refactor", "test text here")
    h2 = vig._compute_governance_provenance_hash("0" * 64, "b" * 64, "bugfix", "other text here")
    assert isinstance(h1, str)
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)
    # Different inputs → different hashes (with overwhelming probability)
    assert h1 != h2


# ── T225-6: GET /agent/allowlist-governance-history chain_intact=True ─────────
def test_T225_6_history_endpoint_chain_intact():
    """GET /agent/allowlist-governance-history returns chain_intact=True for a valid single entry."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store225 = _make_store()
    cfg225 = Config()
    app225 = create_operator_app(cfg225, store225)
    client = TestClient(app225)

    # Insert one genesis entry
    store225.insert_governance_provenance(
        governance_provenance_hash="i" * 64,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="j" * 64,
        reason_category="refactor",
        reason_text="genesis governance chain entry test",
    )

    resp = client.get("/agent/allowlist-governance-history?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "entries" in body
    assert "chain_intact" in body
    assert "total_entries" in body
    assert "timestamp" in body
    assert body["chain_intact"] is True
    assert body["total_entries"] == 1


# ── T225-7: GET /agent/allowlist-governance-history chain_intact=False ────────
def test_T225_7_history_endpoint_chain_broken():
    """GET /agent/allowlist-governance-history chain_intact=False when link is broken."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store225b = _make_store()
    cfg225b = Config()
    app225b = create_operator_app(cfg225b, store225b)
    client = TestClient(app225b)

    # Insert two entries where the second's previous_hash does NOT match the first
    store225b.insert_governance_provenance(
        governance_provenance_hash="k" * 64,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="l" * 64,
        reason_category="refactor",
        reason_text="first entry — should chain to next",
    )
    store225b.insert_governance_provenance(
        governance_provenance_hash="m" * 64,
        previous_provenance_hash="z" * 64,   # broken: doesn't match "k"*64
        new_allowlist_hash="n" * 64,
        reason_category="bugfix",
        reason_text="second entry with broken chain link",
    )

    resp = client.get("/agent/allowlist-governance-history?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chain_intact"] is False


# ── T225-8: POST /agent/allowlist-governance-event stores provenance chain ────
def test_T225_8_post_governance_event_stores_provenance():
    """POST /agent/allowlist-governance-event with provenance_hash stores a chain entry."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store225c = _make_store()
    cfg225c = Config()
    app225c = create_operator_app(cfg225c, store225c)
    client = TestClient(app225c)

    resp = client.post(
        "/agent/allowlist-governance-event",
        json={
            "previous_hash":              "a" * 64,
            "new_hash":                   "b" * 64,
            "reason_category":            "refactor",
            "reason_text":                "renamed helper function without semantic change",
            "governance_provenance_hash": "c" * 64,
            "previous_provenance_hash":   "0" * 64,
        },
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["accepted"] is True
    assert "row_id" in body
    assert body.get("governance_provenance_hash") == "c" * 64

    # Verify chain entry was stored
    history = store225c.get_governance_provenance_history(limit=5)
    assert len(history) >= 1
    assert history[0]["governance_provenance_hash"] == "c" * 64
    assert history[0]["reason_category"] == "refactor"
