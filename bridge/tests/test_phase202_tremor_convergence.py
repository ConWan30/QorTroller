"""
Phase 202 — TremorRestingConvergenceOracle Tests
T202-1..8

Tests:
  T202-1: insert_tremor_convergence_log stores row correctly
  T202-2: get_tremor_convergence_status returns latest row for session_type
  T202-3: get_tremor_convergence_history returns rows newest-first
  T202-4: convergence_stable=False when velocity negative (declining ratio)
  T202-5: convergence_stable=True reflected in status correctly
  T202-6: tremor_convergence_enabled config field defaults to False
  T202-7: RATIO_VELOCITY_NEGATIVE ORPHAN rule defined in FSCA
  T202-8: multiple session_type isolation — tremor_resting vs touchpad_corners
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# ── web3 / eth_account stubs ───────────────────────────────────────────────
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
    return Store(os.path.join(d, "test202.db"))


# ── T202-1: insert_tremor_convergence_log stores row correctly ─────────────
def test_T202_1_insert_tremor_convergence_log():
    store = _make_store()
    row_id = store.insert_tremor_convergence_log(
        session_type="tremor_resting",
        ratio=0.75,
        velocity=0.022,
        n_sessions=3,
        convergence_stable=True,
        consecutive_positive=2,
        sessions_to_target_est=5,
    )
    assert isinstance(row_id, int)
    assert row_id >= 1
    status = store.get_tremor_convergence_status("tremor_resting")
    assert status is not None
    assert abs(status["ratio"] - 0.75) < 1e-9
    assert abs(status["velocity"] - 0.022) < 1e-9
    assert status["n_sessions"] == 3
    assert status["convergence_stable"] == 1
    assert status["consecutive_positive"] == 2
    assert status["sessions_to_target_est"] == 5
    assert status["session_type"] == "tremor_resting"


# ── T202-2: get_tremor_convergence_status returns latest row ───────────────
def test_T202_2_get_tremor_convergence_status_latest():
    store = _make_store()
    store.insert_tremor_convergence_log(
        "tremor_resting", 0.60, -0.10, 2, False, 0, 10
    )
    store.insert_tremor_convergence_log(
        "tremor_resting", 0.75, 0.15, 3, True, 2, 4
    )
    status = store.get_tremor_convergence_status("tremor_resting")
    assert abs(status["ratio"] - 0.75) < 1e-9
    assert status["convergence_stable"] == 1


# ── T202-3: get_tremor_convergence_history returns newest-first ────────────
def test_T202_3_get_tremor_convergence_history():
    store = _make_store()
    for i in range(5):
        store.insert_tremor_convergence_log(
            "tremor_resting", 0.5 + i * 0.05, 0.05, i + 1, i >= 2, max(0, i - 1), 0
        )
    history = store.get_tremor_convergence_history("tremor_resting", limit=5)
    assert len(history) == 5
    # Newest first: last inserted has highest n_sessions
    assert history[0]["n_sessions"] == 5
    assert history[-1]["n_sessions"] == 1


# ── T202-4: convergence_stable=False when velocity negative ───────────────
def test_T202_4_convergence_stable_false_on_negative_velocity():
    store = _make_store()
    # Simulate touchpad_corners failure mode: ratio declined
    store.insert_tremor_convergence_log(
        "tremor_resting", 0.998, 0.10, 5, False, 0, 3
    )
    store.insert_tremor_convergence_log(
        "tremor_resting", 0.80, -0.099, 6, False, 0, 5
    )
    status = store.get_tremor_convergence_status("tremor_resting")
    assert status["convergence_stable"] == 0
    assert status["velocity"] < 0
    assert status["consecutive_positive"] == 0


# ── T202-5: convergence_stable=True when velocity positive 2 consecutive ───
def test_T202_5_convergence_stable_true_on_positive_velocity():
    store = _make_store()
    store.insert_tremor_convergence_log(
        "tremor_resting", 0.90, 0.033, 4, False, 1, 4
    )
    store.insert_tremor_convergence_log(
        "tremor_resting", 1.05, 0.150, 5, True, 2, 0
    )
    status = store.get_tremor_convergence_status("tremor_resting")
    assert status["convergence_stable"] == 1
    assert status["velocity"] > 0
    assert status["consecutive_positive"] == 2
    assert status["ratio"] > 1.0


# ── T202-6: tremor_convergence_enabled config field defaults to False ──────
def test_T202_6_config_default():
    _saved = {}
    for _k in ("TREMOR_CONVERGENCE_ENABLED",):
        _saved[_k] = os.environ.pop(_k, None)
    try:
        import importlib
        import vapi_bridge.config as _cfg_mod
        importlib.reload(_cfg_mod)
        cfg = _cfg_mod.Config()
        assert hasattr(cfg, "tremor_convergence_enabled")
        assert cfg.tremor_convergence_enabled is False
    finally:
        for _k, _v in _saved.items():
            if _v is not None:
                os.environ[_k] = _v


# ── T202-7: RATIO_VELOCITY_NEGATIVE ORPHAN rule defined in FSCA ───────────
def test_T202_7_ratio_velocity_negative_orphan_rule():
    from vapi_bridge.fleet_signal_coherence_agent import ORPHAN_RULES
    assert "RATIO_VELOCITY_NEGATIVE" in ORPHAN_RULES
    rule = ORPHAN_RULES["RATIO_VELOCITY_NEGATIVE"]
    assert rule["trigger_table"] == "tremor_convergence_log"
    assert rule["trigger_column"] == "convergence_stable"
    assert rule["trigger_value"] == 0
    assert rule["severity"] == "HIGH"
    assert "MINT_QUORUM" in rule["explanation"] or "SeparationRatioRegistry" in rule["explanation"]
    assert len(ORPHAN_RULES) == 6  # 5 original + 1 new Phase 202 rule


# ── T202-8: session_type isolation — tremor_resting vs touchpad_corners ────
def test_T202_8_session_type_isolation():
    store = _make_store()
    store.insert_tremor_convergence_log(
        "tremor_resting", 0.80, 0.05, 4, True, 2, 2
    )
    store.insert_tremor_convergence_log(
        "touchpad_corners", 0.50, -0.10, 3, False, 0, 15
    )
    tremor_status = store.get_tremor_convergence_status("tremor_resting")
    assert tremor_status is not None
    assert tremor_status["convergence_stable"] == 1
    assert abs(tremor_status["ratio"] - 0.80) < 1e-9

    tc_status = store.get_tremor_convergence_status("touchpad_corners")
    assert tc_status is not None
    assert tc_status["convergence_stable"] == 0
    assert abs(tc_status["ratio"] - 0.50) < 1e-9
