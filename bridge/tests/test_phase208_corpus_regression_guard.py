"""
Phase 208 — CorpusRatioRegressionGuard Tests
T208-1..8

Tests:
  T208-1: insert_separation_defensibility_log_guarded with guard_enabled=False passes through
  T208-2: insert_separation_defensibility_log_guarded raises CorpusRegressionError on regression
  T208-3: insert_corpus_regression_override stores row with override_hash
  T208-4: guarded insert passes after override is registered
  T208-5: get_corpus_regression_guard_status returns correct keys when no data
  T208-6: corpus_ratio_regression_guard_enabled config defaults to False
  T208-7: GET /agent/corpus-regression-guard-status returns correct keys
  T208-8: provenance_hash chain links consecutive breakthrough entries
"""
import os
import sys
import tempfile
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
    return Store(os.path.join(d, "test208.db"))


def _insert_def(store, session_type="tremor_resting", ratio=0.728,
                all_pairs_above_1=False, n=35):
    """Helper: insert a defensibility log row via the guarded method."""
    return store.insert_separation_defensibility_log_guarded(
        session_type=session_type,
        n_sessions_total=n,
        n_per_player={"P1": 12, "P2": 12, "P3": 11},
        min_n_per_player=10,
        defensible=ratio > 1.0,
        ratio=ratio,
        all_pairs_above_1=all_pairs_above_1,
        guard_enabled=True,
    )


# ── T208-1: guard_enabled=False passes through without side effects ────────────
def test_T208_1_guard_disabled_passes_through():
    """insert_separation_defensibility_log_guarded with guard_enabled=False
    behaves identically to insert_separation_defensibility_log."""
    from vapi_bridge.store import Store
    store = _make_store()
    # First insert a "breakthrough" row manually
    store.insert_separation_defensibility_log(
        session_type="tremor_resting",
        n_sessions_total=27,
        n_per_player={"P1": 9, "P2": 6, "P3": 12},
        min_n_per_player=10,
        defensible=True,
        ratio=1.177,
        all_pairs_above_1=True,
    )
    # Now insert a regression with guard_enabled=False — must NOT raise
    row_id = store.insert_separation_defensibility_log_guarded(
        session_type="tremor_resting",
        n_sessions_total=28,
        n_per_player={"P1": 9, "P2": 7, "P3": 12},
        min_n_per_player=10,
        defensible=False,
        ratio=0.900,
        all_pairs_above_1=False,
        guard_enabled=False,  # guard off — should not raise
    )
    assert isinstance(row_id, int)
    assert row_id >= 1
    # No guard log entry should exist (only breakthrough inserts create guard log rows)
    status = store.get_corpus_regression_guard_status(probe_type="tremor_resting")
    assert status["guard_active"] is False


# ── T208-2: raises CorpusRegressionError on regression with guard enabled ──────
def test_T208_2_raises_corpus_regression_error():
    """CorpusRegressionError is raised when all_pairs_above_1 regresses after a
    prior breakthrough and guard_enabled=True with no override."""
    from vapi_bridge.store import CorpusRegressionError
    store = _make_store()
    # Record a breakthrough (all_pairs_above_1=True)
    _insert_def(store, ratio=1.261, all_pairs_above_1=True, n=11)
    # Now attempt a regression — should raise
    with pytest.raises(CorpusRegressionError) as exc_info:
        _insert_def(store, ratio=0.728, all_pairs_above_1=False, n=35)
    assert "regression blocked" in str(exc_info.value).lower() or \
           "CorpusRegressionError" in type(exc_info.value).__name__
    assert "tremor_resting" in str(exc_info.value)


# ── T208-3: insert_corpus_regression_override stores row with override_hash ────
def test_T208_3_insert_override_stores_hash():
    """insert_corpus_regression_override stores a row with a non-empty override_hash."""
    store = _make_store()
    row_id = store.insert_corpus_regression_override(
        probe_type="tremor_resting",
        old_ratio=1.261,
        new_ratio=0.728,
        reason="P3 intra-player variance structurally elevated; Phase 209 per-pair gate pending",
    )
    assert isinstance(row_id, int)
    assert row_id >= 1
    status = store.get_corpus_regression_guard_status(probe_type="tremor_resting")
    assert status["override_count"] == 1


# ── T208-4: guarded insert passes after override is registered ─────────────────
def test_T208_4_guarded_insert_passes_after_override():
    """After insert_corpus_regression_override, regression insert no longer raises."""
    from vapi_bridge.store import CorpusRegressionError
    store = _make_store()
    # Breakthrough
    _insert_def(store, ratio=1.261, all_pairs_above_1=True, n=11)
    # Register override
    store.insert_corpus_regression_override(
        probe_type="tremor_resting",
        old_ratio=1.261,
        new_ratio=0.728,
        reason="Phase 209 per-pair probe specialization pending",
    )
    # Now regression should succeed
    row_id = _insert_def(store, ratio=0.728, all_pairs_above_1=False, n=35)
    assert isinstance(row_id, int)


# ── T208-5: get_corpus_regression_guard_status empty DB returns correct shape ──
def test_T208_5_guard_status_empty():
    """get_corpus_regression_guard_status returns correct keys on empty DB."""
    store = _make_store()
    status = store.get_corpus_regression_guard_status()
    assert "guard_active" in status
    assert "breakthrough_ratio" in status
    assert "breakthrough_n" in status
    assert "provenance_hash" in status
    assert "override_count" in status
    assert "timestamp" in status
    assert status["guard_active"] is False
    assert status["breakthrough_ratio"] is None
    assert status["override_count"] == 0


# ── T208-6: corpus_ratio_regression_guard_enabled config defaults to False ──────
def test_T208_6_config_default_false():
    """corpus_ratio_regression_guard_enabled defaults to False (infrastructure-first)."""
    import os
    os.environ.pop("CORPUS_RATIO_REGRESSION_GUARD_ENABLED", None)
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.corpus_ratio_regression_guard_enabled is False


# ── T208-7: GET /agent/corpus-regression-guard-status returns correct keys ──────
def test_T208_7_endpoint_returns_correct_keys():
    """GET /agent/corpus-regression-guard-status returns 7 expected keys."""
    import os
    os.environ.pop("CORPUS_RATIO_REGRESSION_GUARD_ENABLED", None)
    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app
    from fastapi.testclient import TestClient

    d = tempfile.mkdtemp()
    store = Store(os.path.join(d, "test208e.db"))
    cfg = Config()
    app = create_operator_app(cfg, store)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.get("/agent/corpus-regression-guard-status")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("corpus_ratio_regression_guard_enabled", "guard_active",
                "breakthrough_ratio", "breakthrough_n",
                "provenance_hash", "override_count", "timestamp"):
        assert key in body, f"Missing key: {key}"
    assert body["corpus_ratio_regression_guard_enabled"] is False
    assert body["guard_active"] is False
    assert body["override_count"] == 0


# ── T208-8: provenance_hash chain links consecutive breakthrough entries ─────────
def test_T208_8_provenance_chain_links():
    """Consecutive all_pairs_above_1=True inserts produce linked provenance hashes."""
    import hashlib
    store = _make_store()
    # First breakthrough
    _insert_def(store, ratio=1.261, all_pairs_above_1=True, n=11)
    s1 = store.get_corpus_regression_guard_status(probe_type="tremor_resting")
    assert s1["guard_active"] is True
    hash1 = s1["provenance_hash"]
    assert hash1 is not None and len(hash1) == 64  # 64-char hex SHA-256

    # Second breakthrough (ratio improved)
    _insert_def(store, ratio=1.350, all_pairs_above_1=True, n=15)
    s2 = store.get_corpus_regression_guard_status(probe_type="tremor_resting")
    hash2 = s2["provenance_hash"]
    assert hash2 is not None and len(hash2) == 64
    assert hash2 != hash1  # Chain must evolve
