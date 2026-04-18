"""
Phase 222 — BiometricBoundGovernance (BBG) Tests
T222-1..10

Tests:
  T222-1:  insert_bbg_proposal_log stores entry and returns row id
  T222-2:  get_bbg_status returns 6 expected keys after insert
  T222-3:  get_bbg_status with no data returns empty sentinel
  T222-4:  get_bbg_proposal_history returns entries reverse chronological
  T222-5:  bbg_enabled config defaults to False
  T222-6:  bbg_max_age_seconds config defaults to 3600
  T222-7:  BiometricGovernanceAgent.validate_proposal_locally rejects VHP_EXPIRES_TOO_SOON
  T222-8:  BiometricGovernanceAgent.validate_proposal_locally accepts valid proposal
  T222-9:  GET /agent/bbg-status returns 200 with 7 keys
  T222-10: POST /agent/bbg-propose rejects VHP_EXPIRES_TOO_SOON proposal
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
    return Store(os.path.join(d, "test222.db"))


# ── T222-1: insert_bbg_proposal_log stores entry ─────────────────────────────
def test_T222_1_insert_bbg_proposal_log():
    """insert_bbg_proposal_log stores entry and returns row id."""
    store = _make_store()
    row_id = store.insert_bbg_proposal_log(
        proposal_hash="dead" * 16,
        proposer_address="0xABCDEF",
        vhp_token_id=42,
        vhp_expires_at=time.time() + 7200,
        on_chain_confirmed=False,
    )
    assert isinstance(row_id, int)
    assert row_id >= 1


# ── T222-2: get_bbg_status returns 6 expected keys ───────────────────────────
def test_T222_2_get_bbg_status_keys():
    """get_bbg_status returns 6 expected keys after insert."""
    store = _make_store()
    store.insert_bbg_proposal_log(
        proposal_hash="beef" * 16, proposer_address="0xCAFE",
        vhp_token_id=1, vhp_expires_at=time.time() + 7200,
    )
    result = store.get_bbg_status()
    expected = {
        "total_proposals", "latest_proposal_hash", "latest_proposer",
        "on_chain_confirmed", "last_proposal_ts", "timestamp",
    }
    assert expected.issubset(set(result.keys()))
    assert result["total_proposals"] == 1
    assert result["on_chain_confirmed"] is False


# ── T222-3: get_bbg_status with no data ──────────────────────────────────────
def test_T222_3_get_bbg_status_empty():
    """get_bbg_status returns empty sentinel with no data."""
    store = _make_store()
    result = store.get_bbg_status()
    assert result["total_proposals"] == 0
    assert result["latest_proposal_hash"] is None
    assert result["latest_proposer"] is None
    assert result["on_chain_confirmed"] is False
    assert result["last_proposal_ts"] is None


# ── T222-4: get_bbg_proposal_history reverse order ───────────────────────────
def test_T222_4_get_bbg_proposal_history_order():
    """get_bbg_proposal_history returns entries reverse chronological order."""
    store = _make_store()
    store.insert_bbg_proposal_log("aaaa" * 16, proposer_address="0x1", vhp_token_id=1)
    time.sleep(0.01)
    store.insert_bbg_proposal_log("bbbb" * 16, proposer_address="0x2", vhp_token_id=2)
    time.sleep(0.01)
    store.insert_bbg_proposal_log("cccc" * 16, proposer_address="0x3", vhp_token_id=3)
    history = store.get_bbg_proposal_history(limit=3)
    assert len(history) == 3
    assert history[0]["proposal_hash"] == "cccc" * 16
    assert history[2]["proposal_hash"] == "aaaa" * 16


# ── T222-5: bbg_enabled defaults to False ────────────────────────────────────
def test_T222_5_config_bbg_enabled_default():
    """bbg_enabled config field defaults to False."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.bbg_enabled is False


# ── T222-6: bbg_max_age_seconds defaults to 3600 ─────────────────────────────
def test_T222_6_config_bbg_max_age_default():
    """bbg_max_age_seconds config field defaults to 3600."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.bbg_max_age_seconds == 3600


# ── T222-7: validate_proposal_locally rejects VHP_EXPIRES_TOO_SOON ───────────
def test_T222_7_validate_rejects_expiry():
    """BiometricGovernanceAgent.validate_proposal_locally rejects VHP_EXPIRES_TOO_SOON."""
    from vapi_bridge.config import Config
    from vapi_bridge.biometric_governance_agent import BiometricGovernanceAgent

    cfg = Config()
    store = _make_store()
    agent = BiometricGovernanceAgent(store, cfg)

    result = agent.validate_proposal_locally(
        proposal_hash="a" * 64,
        proposer_address="0xDEADBEEF",
        vhp_token_id=1,
        vhp_expires_at=time.time() + 100,  # expires in 100s < 3600s threshold
    )
    assert result["valid"] is False
    assert result["rejection_reason"] == "VHP_EXPIRES_TOO_SOON"


# ── T222-8: validate_proposal_locally accepts valid proposal ──────────────────
def test_T222_8_validate_accepts_valid():
    """BiometricGovernanceAgent.validate_proposal_locally accepts valid proposal."""
    from vapi_bridge.config import Config
    from vapi_bridge.biometric_governance_agent import BiometricGovernanceAgent

    cfg = Config()
    store = _make_store()
    agent = BiometricGovernanceAgent(store, cfg)

    result = agent.validate_proposal_locally(
        proposal_hash="b" * 64,
        proposer_address="0xCAFEBABE",
        vhp_token_id=2,
        vhp_expires_at=time.time() + 86400,  # expires in 24h >> 3600s threshold
    )
    assert result["valid"] is True
    assert result["vhp_freshness_ok"] is True
    assert result["rejection_reason"] is None


# ── T222-9: GET /agent/bbg-status returns 7 keys ─────────────────────────────
def test_T222_9_endpoint_bbg_status_keys():
    """GET /agent/bbg-status returns all 7 expected keys."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store222 = _make_store()
    cfg222   = Config()
    app222   = create_operator_app(cfg222, store222)
    client   = TestClient(app222)

    resp = client.get("/agent/bbg-status")
    assert resp.status_code == 200
    body = resp.json()
    expected_keys = {
        "bbg_enabled", "total_proposals", "latest_proposal_hash",
        "latest_proposer", "on_chain_confirmed", "last_proposal_ts", "timestamp",
    }
    assert set(body.keys()) == expected_keys


# ── T222-10: POST /agent/bbg-propose rejects VHP_EXPIRES_TOO_SOON ────────────
def test_T222_10_endpoint_bbg_propose_rejects_expiry():
    """POST /agent/bbg-propose rejects proposal with VHP expiring too soon."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.operator_api import create_operator_app

    store222 = _make_store()
    cfg222   = Config()
    app222   = create_operator_app(cfg222, store222)
    client   = TestClient(app222)

    resp = client.post(
        "/agent/bbg-propose",
        params={
            "proposal_hash":    "c" * 64,
            "proposer_address": "0xDEAD",
            "vhp_token_id":     1,
            "vhp_expires_at":   time.time() + 100,  # expires too soon
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["rejection_reason"] == "VHP_EXPIRES_TOO_SOON"
