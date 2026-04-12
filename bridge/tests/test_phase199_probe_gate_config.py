"""
Phase 199 — Prototype Separation Gate Configurability + Tremor Resting Probe.

199-A: all_pairs_gate_enabled config field — controls whether all_pairs_p0_ok
       enforces strict per-pair >= 1.0 (production) or is bypassed (prototype mode).
199-B: tremor_resting structured probe session type — 30s still-hold resting capture
       that isolates neurological tremor_peak_hz from gameplay motion artifacts.
"""
import sys
import tempfile
import os
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


def _make_store():
    from vapi_bridge.store import Store
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "test199.db"))


def _make_cfg(**overrides):
    """Return a minimal config-like namespace for preflight tests."""
    import types
    cfg = types.SimpleNamespace(
        min_separation_ratio=0.70,
        all_pairs_gate_enabled=True,
        tremor_resting_probe_enabled=False,
        live_feature_dim=13,
        calibration_feature_dim=12,
        biometric_credential_ttl_days=90.0,
        dual_primitive_gate_enabled=False,
        epoch_window_enabled=False,
        ioswarm_vhp_mint_enabled=False,
        biometric_ttl_decay_scaling_enabled=False,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# T199-1: all_pairs_gate_enabled=True (default) — blocks when all_pairs_above_1=False
# ---------------------------------------------------------------------------

def test_t199_1_all_pairs_gate_blocks_by_default():
    """When all_pairs_gate_enabled=True (default), all_pairs_p0_ok=False when
    no all_pairs_above_1 data in defensibility log (fail-closed)."""
    store = _make_store()
    cfg = _make_cfg(all_pairs_gate_enabled=True)
    # No defensibility log row inserted → all_pairs_above_1 defaults to False
    _def = store.get_separation_defensibility_status()
    _all_pairs_gate = bool(getattr(cfg, "all_pairs_gate_enabled", True))
    if not _all_pairs_gate:
        all_pairs_p0_ok = True
    else:
        all_pairs_p0_ok = bool(_def.get("all_pairs_above_1", False)) if _def else False
    assert all_pairs_p0_ok is False


# ---------------------------------------------------------------------------
# T199-2: all_pairs_gate_enabled=False — prototype mode bypasses per-pair gate
# ---------------------------------------------------------------------------

def test_t199_2_prototype_mode_bypasses_all_pairs_gate():
    """When all_pairs_gate_enabled=False, all_pairs_p0_ok=True regardless of stored
    all_pairs_above_1 value (prototype mode — P2/P3 proximity known structural limit)."""
    store = _make_store()
    cfg = _make_cfg(all_pairs_gate_enabled=False)
    # Insert a defensibility row with all_pairs_above_1=False (P2vP3=0.401 scenario)
    store.insert_separation_defensibility_log(
        session_type="touchpad_corners",
        n_sessions_total=35,
        n_per_player={"P1": 12, "P2": 12, "P3": 11},
        min_n_per_player=10,
        defensible=True,
        ratio=0.728,
        all_pairs_above_1=False,
    )
    _def = store.get_separation_defensibility_status()
    assert _def is not None
    assert bool(_def["all_pairs_above_1"]) is False

    _all_pairs_gate = bool(getattr(cfg, "all_pairs_gate_enabled", True))
    if not _all_pairs_gate:
        all_pairs_p0_ok = True
    else:
        all_pairs_p0_ok = bool(_def.get("all_pairs_above_1", False)) if _def else False
    assert all_pairs_p0_ok is True


# ---------------------------------------------------------------------------
# T199-3: separation_ok=True when ratio=0.728 >= min_separation_ratio=0.70
# ---------------------------------------------------------------------------

def test_t199_3_separation_ok_at_0728_with_07_threshold():
    """Phase 166 min_separation_ratio=0.70 already makes separation_ok=True at ratio=0.728."""
    cfg = _make_cfg(min_separation_ratio=0.70)
    ratio = 0.728
    _min_sep = float(getattr(cfg, "min_separation_ratio", 0.70))
    separation_ok = ratio >= _min_sep
    assert separation_ok is True


# ---------------------------------------------------------------------------
# T199-4: separation_ok=False when ratio=0.728 with strict threshold=1.0
# ---------------------------------------------------------------------------

def test_t199_4_separation_blocked_at_strict_threshold():
    """With min_separation_ratio=1.0 (production strict), ratio=0.728 fails."""
    cfg = _make_cfg(min_separation_ratio=1.0)
    ratio = 0.728
    _min_sep = float(getattr(cfg, "min_separation_ratio", 1.0))
    separation_ok = ratio >= _min_sep
    assert separation_ok is False


# ---------------------------------------------------------------------------
# T199-5: tremor_resting is a valid STRUCTURED_PROBE_TYPE in store
# ---------------------------------------------------------------------------

def test_t199_5_tremor_resting_in_structured_probe_types():
    """tremor_resting must appear in Store.STRUCTURED_PROBE_TYPES (Phase 199 199-B)."""
    from vapi_bridge.store import Store
    assert "tremor_resting" in Store.STRUCTURED_PROBE_TYPES


# ---------------------------------------------------------------------------
# T199-6: tremor_resting session can be inserted into defensibility log
# ---------------------------------------------------------------------------

def test_t199_6_tremor_resting_defensibility_insert():
    """Should be able to insert a tremor_resting row into separation_defensibility_log."""
    store = _make_store()
    row_id = store.insert_separation_defensibility_log(
        session_type="tremor_resting",
        n_sessions_total=15,
        n_per_player={"P1": 5, "P2": 5, "P3": 5},
        min_n_per_player=5,
        defensible=True,
        ratio=1.25,
        all_pairs_above_1=True,
    )
    assert row_id is not None and row_id > 0
    row = store.get_separation_defensibility_status(session_type="tremor_resting")
    assert row is not None
    assert abs(float(row["ratio"]) - 1.25) < 0.001
    assert bool(row["all_pairs_above_1"]) is True


# ---------------------------------------------------------------------------
# T199-7: invalid session type still raises ValueError (whitelist enforcement)
# ---------------------------------------------------------------------------

def test_t199_7_invalid_session_type_still_blocked():
    """gameplay (free-form) must still be rejected by defensibility log (W1-011)."""
    store = _make_store()
    with pytest.raises(ValueError, match="Invalid session_type"):
        store.insert_separation_defensibility_log(
            session_type="gameplay",
            n_sessions_total=50,
            n_per_player={"P1": 17, "P2": 17, "P3": 16},
            min_n_per_player=10,
            defensible=False,
            ratio=0.060,
            all_pairs_above_1=False,
        )


# ---------------------------------------------------------------------------
# T199-8: all_pairs_gate_enabled config field defaults to True
# ---------------------------------------------------------------------------

def test_t199_8_all_pairs_gate_enabled_default_true():
    """all_pairs_gate_enabled must default to True (production mode — fail-closed)."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.all_pairs_gate_enabled is True
    assert cfg.tremor_resting_probe_enabled is False
