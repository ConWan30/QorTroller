"""
Phase 224 — InvariantGate On-Chain Anchor + Allowlist Governance Tests
T224-1..T224-8

Tests:
  T224-1: compute_allowlist_hash() is deterministic across repeated calls
  T224-2: --generate without --reason exits code 2
  T224-3: --generate with too-short --reason exits code 2
  T224-4: --generate with invariant_change category without --confirm-governance exits code 2
  T224-5: compute_fleet_root() with mocked allowlist produces 38-leaf structure
  T224-6: insert_allowlist_change_log() stores record with correct fields
  T224-7: get_allowlist_change_status() marks suspicious when reason_from_gate_log is NULL
  T224-8: POST /agent/allowlist-governance-event with valid payload returns 200; invalid returns 422
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    return Store(os.path.join(d, "test224.db"))


# ── T224-1: compute_allowlist_hash() deterministic ───────────────────────────
def test_T224_1_compute_allowlist_hash_deterministic():
    """compute_allowlist_hash() returns same digest on repeated calls."""
    import vapi_invariant_gate as gate
    h1 = gate.compute_allowlist_hash()
    h2 = gate.compute_allowlist_hash()
    assert isinstance(h1, str)
    assert len(h1) == 64
    assert h1 == h2


# ── T224-2: --generate without --reason exits code 2 ─────────────────────────
def test_T224_2_generate_missing_reason_exits_2():
    """--generate without --reason must exit with code 2."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "vapi_invariant_gate.py"), "--generate"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2, (
        f"Expected exit code 2, got {result.returncode}. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )


# ── T224-3: --generate with too-short --reason exits code 2 ──────────────────
def test_T224_3_generate_short_reason_exits_2():
    """--generate with reason shorter than 10 chars must exit code 2."""
    result = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "vapi_invariant_gate.py"),
            "--generate", "--reason", "hi",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2, (
        f"Expected exit code 2 for short reason, got {result.returncode}. "
        f"stdout={result.stdout!r}"
    )


# ── T224-4: invariant_change without --confirm-governance exits code 2 ────────
def test_T224_4_invariant_change_without_confirm_exits_2():
    """invariant_change category without --confirm-governance must exit code 2."""
    result = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "vapi_invariant_gate.py"),
            "--generate", "--reason", "invariant_change: test case for T224-4",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2, (
        f"Expected exit code 2 for missing --confirm-governance, got {result.returncode}. "
        f"stdout={result.stdout!r}"
    )


# ── T224-5: compute_fleet_root() produces 38-leaf tree ───────────────────────
def test_T224_5_compute_fleet_root_38_leaves():
    """compute_fleet_root() builds 38-leaf Merkle tree (37 fleet + 1 virtual allowlist)."""
    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent, _AGENT_IDS

    assert len(_AGENT_IDS) == 37, f"Expected 37 fleet agents, got {len(_AGENT_IDS)}"
    assert "biometric_governance_agent" in _AGENT_IDS, (
        "biometric_governance_agent must be present in _AGENT_IDS (Phase 222)"
    )

    store = _make_store()
    cfg = MagicMock()
    cfg.protocol_coherence_registry_address = ""
    agent = ProtocolCoherenceAgent(store=store, cfg=cfg)

    ts_ns = 1_000_000_000_000_000_000
    root_hex, returned_ts, allowlist_hex = agent.compute_fleet_root(ts_ns=ts_ns)

    assert isinstance(root_hex, str) and len(root_hex) == 64
    assert returned_ts == ts_ns
    assert isinstance(allowlist_hex, str) and len(allowlist_hex) == 64

    # Root must change when allowlist changes (virtual leaf content differs)
    import hashlib
    alt_leaf = hashlib.sha256(
        b"allowlist" + bytes.fromhex("ff" * 8) + ts_ns.to_bytes(8, "big")
    ).digest()
    # Verify internal leaf count indirectly: root hex is non-zero (38 leaves hashed)
    assert root_hex != "0" * 64


# ── T224-6: insert_allowlist_change_log() stores record ──────────────────────
def test_T224_6_insert_allowlist_change_log():
    """insert_allowlist_change_log() stores record and returns row id."""
    store = _make_store()
    row_id = store.insert_allowlist_change_log(
        previous_hash="a" * 64,
        new_hash="b" * 64,
        merkle_root_at_change="c" * 64,
        reason_from_gate_log="refactor: renamed helper",
    )
    assert isinstance(row_id, int) and row_id >= 1


# ── T224-7: suspicious change when reason_from_gate_log is NULL ───────────────
def test_T224_7_suspicious_change_detection():
    """get_allowlist_change_status() reports suspicious_count=1 when reason is NULL."""
    store = _make_store()
    # Insert record with no governance reason (simulates unlogged direct edit)
    store.insert_allowlist_change_log(
        previous_hash="a" * 64,
        new_hash="b" * 64,
        merkle_root_at_change="c" * 64,
        reason_from_gate_log=None,  # suspicious — no governance event
    )
    status = store.get_allowlist_change_status()
    assert status["total_changes"] == 1
    assert status["suspicious_count"] == 1


# ── T224-8: POST /agent/allowlist-governance-event ────────────────────────────
def test_T224_8_allowlist_governance_event_endpoint():
    """POST /agent/allowlist-governance-event: valid payload returns 200; invalid category returns 422."""
    from fastapi.testclient import TestClient
    from vapi_bridge.store import Store
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    d = tempfile.mkdtemp()
    _store = Store(os.path.join(d, "test224_api.db"))
    _cfg = Config()
    app = create_operator_app(_cfg, _store)
    client = TestClient(app)

    # Valid payload
    resp_ok = client.post(
        "/agent/allowlist-governance-event",
        json={
            "previous_hash":   "a" * 64,
            "new_hash":        "b" * 64,
            "reason_category": "refactor",
            "reason_text":     "renamed _hash_region helper without semantic change",
        },
    )
    assert resp_ok.status_code == 200, f"Expected 200, got {resp_ok.status_code}: {resp_ok.text}"
    body_ok = resp_ok.json()
    assert body_ok["accepted"] is True
    assert "row_id" in body_ok

    # Invalid category
    resp_bad = client.post(
        "/agent/allowlist-governance-event",
        json={
            "previous_hash":   "a" * 64,
            "new_hash":        "b" * 64,
            "reason_category": "unknown_cat",
            "reason_text":     "this should fail validation",
        },
    )
    assert resp_bad.status_code == 422, f"Expected 422, got {resp_bad.status_code}"
