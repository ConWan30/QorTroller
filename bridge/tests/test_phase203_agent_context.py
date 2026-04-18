"""
Phase 203 — AgentContextRegistry Tests
T203-1..8

Tests:
  T203-1: upsert_agent_context_hash inserts new hash idempotently
  T203-2: get_agent_context_status returns latest hash for agent
  T203-3: get_all_agent_context_status returns all 3 agent records
  T203-4: UNIQUE constraint (agent_id, prompt_sha256) prevents duplicates
  T203-5: different phase_number can coexist for same agent (same hash)
  T203-6: agent_context_on_chain_enabled config field defaults to False
  T203-7: CONTEXT_HASH_MISMATCH INVERSION rule defined in FSCA
  T203-8: FSCA now has 4 INVERSION rules (original 3 + CONTEXT_HASH_MISMATCH)
"""
import hashlib
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# ── web3 / eth_account stubs ───────────────────────────────────────────────
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
    return Store(os.path.join(d, "test203.db"))


# ── T203-1: upsert_agent_context_hash inserts new hash idempotently ────────
def test_T203_1_upsert_agent_context_hash_idempotent():
    store = _make_store()
    sha = hashlib.sha256(b"test prompt bridge agent").hexdigest()
    row_id_1 = store.upsert_agent_context_hash("bridge_agent", sha, 203)
    assert isinstance(row_id_1, int)
    assert row_id_1 >= 1
    # Second call with same agent_id + sha256 → no-op, returns same row id
    row_id_2 = store.upsert_agent_context_hash("bridge_agent", sha, 203)
    assert row_id_2 == row_id_1

    # New hash → new row (different sha)
    sha2 = hashlib.sha256(b"updated prompt bridge agent").hexdigest()
    row_id_3 = store.upsert_agent_context_hash("bridge_agent", sha2, 203)
    assert row_id_3 != row_id_1


# ── T203-2: get_agent_context_status returns latest hash for agent ─────────
def test_T203_2_get_agent_context_status():
    store = _make_store()
    sha_v1 = hashlib.sha256(b"prompt v1").hexdigest()
    sha_v2 = hashlib.sha256(b"prompt v2").hexdigest()
    store.upsert_agent_context_hash("session_adjudicator", sha_v1, 201)
    store.upsert_agent_context_hash("session_adjudicator", sha_v2, 203)

    status = store.get_agent_context_status("session_adjudicator")
    assert status is not None
    assert status["agent_id"] == "session_adjudicator"
    # Latest inserted is sha_v2
    assert status["prompt_sha256"] == sha_v2
    assert status["phase_number"] == 203


# ── T203-3: get_all_agent_context_status returns all 3 agents ─────────────
def test_T203_3_get_all_agent_context_status():
    store = _make_store()
    agents = [
        "bridge_agent",
        "session_adjudicator",
        "calibration_intelligence_agent",
    ]
    for _agent in agents:
        sha = hashlib.sha256(f"prompt {_agent}".encode()).hexdigest()
        store.upsert_agent_context_hash(_agent, sha, 203)

    all_status = store.get_all_agent_context_status()
    assert len(all_status) == 3
    agent_ids = {r["agent_id"] for r in all_status}
    assert agent_ids == set(agents)


# ── T203-4: UNIQUE constraint prevents duplicate (agent_id, sha256) ────────
def test_T203_4_unique_constraint_no_duplicate():
    store = _make_store()
    sha = hashlib.sha256(b"stable prompt").hexdigest()
    id_1 = store.upsert_agent_context_hash("bridge_agent", sha, 203)
    id_2 = store.upsert_agent_context_hash("bridge_agent", sha, 203)
    id_3 = store.upsert_agent_context_hash("bridge_agent", sha, 203)
    # All calls return the same id — no new rows
    assert id_1 == id_2 == id_3

    # Verify only one row exists for this agent+sha
    all_status = store.get_all_agent_context_status()
    bridge_rows = [r for r in all_status if r["agent_id"] == "bridge_agent"]
    assert len(bridge_rows) == 1
    assert bridge_rows[0]["prompt_sha256"] == sha


# ── T203-5: different hashes for same agent coexist as separate rows ────────
def test_T203_5_different_hashes_coexist():
    store = _make_store()
    sha_a = hashlib.sha256(b"prompt phase 201").hexdigest()
    sha_b = hashlib.sha256(b"prompt phase 203").hexdigest()
    id_a = store.upsert_agent_context_hash("bridge_agent", sha_a, 201)
    id_b = store.upsert_agent_context_hash("bridge_agent", sha_b, 203)
    assert id_a != id_b

    # get_agent_context_status returns the latest (highest id)
    status = store.get_agent_context_status("bridge_agent")
    assert status["prompt_sha256"] == sha_b
    assert status["phase_number"] == 203


# ── T203-6: agent_context_on_chain_enabled config defaults to False ────────
def test_T203_6_config_default():
    _saved = {}
    for _k in ("AGENT_CONTEXT_ON_CHAIN_ENABLED",):
        _saved[_k] = os.environ.pop(_k, None)
    try:
        import importlib
        import vapi_bridge.config as _cfg_mod
        importlib.reload(_cfg_mod)
        cfg = _cfg_mod.Config()
        assert hasattr(cfg, "agent_context_on_chain_enabled")
        assert cfg.agent_context_on_chain_enabled is False
    finally:
        for _k, _v in _saved.items():
            if _v is not None:
                os.environ[_k] = _v


# ── T203-7: CONTEXT_HASH_MISMATCH INVERSION rule defined in FSCA ──────────
def test_T203_7_context_hash_mismatch_inversion_rule():
    from vapi_bridge.fleet_signal_coherence_agent import INVERSION_RULES
    assert "CONTEXT_HASH_MISMATCH" in INVERSION_RULES
    rule = INVERSION_RULES["CONTEXT_HASH_MISMATCH"]
    assert "dag_query" in rule
    assert "agents_involved" in rule
    assert rule["severity"] == "HIGH"
    # dag_query must reference agent_context_log
    assert "agent_context_log" in rule["dag_query"]
    # dag_query must reference all 3 agent IDs
    assert "bridge_agent" in rule["dag_query"]
    assert "session_adjudicator" in rule["dag_query"]
    assert "calibration_intelligence_agent" in rule["dag_query"]
    # Explanation must mention prompt / hash
    assert "prompt" in rule["explanation"].lower() or "hash" in rule["explanation"].lower()


# ── T203-8: FSCA INVERSION rule count (Phase 225 added GOVERNANCE_CHAIN_BROKEN → 5) ─────
def test_T203_8_fsca_has_four_inversion_rules():
    from vapi_bridge.fleet_signal_coherence_agent import INVERSION_RULES, ORPHAN_RULES
    assert len(INVERSION_RULES) == 5  # 3 original + CONTEXT_HASH_MISMATCH + GOVERNANCE_CHAIN_BROKEN
    assert "COMMITMENT_PREDATES_CONSENT" in INVERSION_RULES
    assert "BADGE_WITHOUT_RENEWAL_PARENT" in INVERSION_RULES
    assert "RULING_PREDATES_CALIBRATION" in INVERSION_RULES
    assert "CONTEXT_HASH_MISMATCH" in INVERSION_RULES
    # Also verify total ORPHAN count
    assert len(ORPHAN_RULES) == 7  # 5 original + RATIO_VELOCITY_NEGATIVE + PER_PAIR_GAP_BLOCKER_UNRESOLVED
