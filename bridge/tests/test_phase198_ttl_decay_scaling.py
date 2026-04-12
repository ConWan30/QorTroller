"""
Phase 198 — Biometric TTL Decay Scaling tests.

effective_ttl = base_ttl × (mean_decay_factor / 0.50) when enabled.
Clamped to [base_ttl × 0.25, base_ttl × 4.0].
"""
import sys
import tempfile
import os
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test198.db"))


def _insert_compliance(store, mean_decay_factor: float):
    """Insert a privacy_compliance_log row with the given decay factor."""
    store.insert_privacy_compliance_log(
        records_monitored=100,
        records_expired=0,
        mean_decay_factor=mean_decay_factor,
        oldest_session_days=45.0,
        privacy_budget_epsilon=0.1,
        warning_triggered=False,
    )


# ---------------------------------------------------------------------------
# T198-1: scaling disabled → effective_ttl == base_ttl
# ---------------------------------------------------------------------------

def test_t198_1_scaling_disabled_returns_base_ttl():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=0.5)
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=False)
    assert abs(result["effective_ttl_days"] - 90.0) < 0.001
    assert abs(result["scaling_factor"] - 1.0) < 0.001
    assert result["scaling_enabled"] is False


# ---------------------------------------------------------------------------
# T198-2: scaling enabled, mean_decay=0.50 → effective_ttl == base_ttl (×1.0)
# ---------------------------------------------------------------------------

def test_t198_2_scaling_at_half_life_no_change():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=0.50)
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    assert abs(result["effective_ttl_days"] - 90.0) < 0.001
    assert abs(result["scaling_factor"] - 1.0) < 0.001


# ---------------------------------------------------------------------------
# T198-3: fresh data (decay=1.0) → effective_ttl = 2× base (×2.0 factor)
# ---------------------------------------------------------------------------

def test_t198_3_fresh_data_doubles_ttl():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=1.0)
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    assert abs(result["effective_ttl_days"] - 180.0) < 0.001
    assert abs(result["scaling_factor"] - 2.0) < 0.001


# ---------------------------------------------------------------------------
# T198-4: old data (decay=0.25) → effective_ttl = 0.5× base
# ---------------------------------------------------------------------------

def test_t198_4_old_data_halves_ttl():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=0.25)
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    assert abs(result["effective_ttl_days"] - 45.0) < 0.001
    assert abs(result["scaling_factor"] - 0.5) < 0.001


# ---------------------------------------------------------------------------
# T198-5: very old data (decay=0.0) → clamped to base × 0.25
# ---------------------------------------------------------------------------

def test_t198_5_zero_decay_clamped_to_min():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=0.0)
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    # 0.0/0.5 = 0.0, clamped to 0.25
    assert abs(result["effective_ttl_days"] - 22.5) < 0.001
    assert abs(result["scaling_factor"] - 0.25) < 0.001


# ---------------------------------------------------------------------------
# T198-6: very fresh data (decay=2.0) → clamped to base × 4.0
# ---------------------------------------------------------------------------

def test_t198_6_high_decay_clamped_to_max():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=2.0)
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    # 2.0/0.5 = 4.0, exactly at max
    assert abs(result["effective_ttl_days"] - 360.0) < 0.001
    assert abs(result["scaling_factor"] - 4.0) < 0.001


# ---------------------------------------------------------------------------
# T198-7: no compliance data → mean_decay=1.0 (default), scaling still works
# ---------------------------------------------------------------------------

def test_t198_7_no_compliance_data_defaults():
    store = _make_store()
    # No privacy_compliance_log rows inserted
    result = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    # Default mean_decay_factor=1.0 → scaling_factor=2.0 → effective=180
    assert abs(result["effective_ttl_days"] - 180.0) < 0.001
    assert abs(result["mean_decay_factor"] - 1.0) < 0.001


# ---------------------------------------------------------------------------
# T198-8: scaling_enabled flag is returned correctly in result dict
# ---------------------------------------------------------------------------

def test_t198_8_scaling_enabled_flag_in_result():
    store = _make_store()
    _insert_compliance(store, mean_decay_factor=0.75)
    r_disabled = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=False)
    r_enabled  = store.get_effective_biometric_ttl(base_ttl_days=90.0, scaling_enabled=True)
    assert r_disabled["scaling_enabled"] is False
    assert r_enabled["scaling_enabled"] is True
    # Disabled returns 90, enabled returns 90×(0.75/0.5)=135
    assert abs(r_disabled["effective_ttl_days"] - 90.0) < 0.001
    assert abs(r_enabled["effective_ttl_days"] - 135.0) < 0.001
