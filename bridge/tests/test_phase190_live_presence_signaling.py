"""
Phase 190 tests — LivePresenceSignalingAgent (agent #34).

Tests:
  T190-1: live_presence_signaling_log table created by Store.__init__
  T190-2: insert_presence_signal stores record with correct fields
  T190-3: get_presence_signal_status returns zero totals when empty
  T190-4: controller_fired_count counts only controller_fired=1 rows
  T190-5: ps5_suppressed_count counts only ps5_compat_mode=1 rows
  T190-6: Config fields live_presence_signaling_enabled=False,
           live_presence_haptic_enabled=True, live_presence_chain_milestone_interval=100
  T190-7: _event_to_signal_type maps bus events correctly
  T190-8: _dispatch_signal persists to DB (no controller when ds=None)
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Stubs for optional heavy imports
# ---------------------------------------------------------------------------
import types as _types

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402
from vapi_bridge.live_presence_signaling_agent import LivePresenceSignalingAgent  # noqa: E402


@pytest.fixture()
def tmp_db():
    _d = tempfile.mkdtemp()
    _p = os.path.join(_d, "test_phase190.db")
    yield _p


@pytest.fixture()
def store(tmp_db):
    return Store(db_path=tmp_db)


@pytest.fixture()
def cfg():
    return Config()


@pytest.fixture()
def agent(store, cfg):
    return LivePresenceSignalingAgent(store=store, cfg=cfg, bus=None, ds_integration=None)


# ---------------------------------------------------------------------------
# T190-1: table created
# ---------------------------------------------------------------------------

def test_t190_1_table_created(store):
    """T190-1: live_presence_signaling_log table created by Store.__init__."""
    import sqlite3
    with sqlite3.connect(store._db_path) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "live_presence_signaling_log" in tables


# ---------------------------------------------------------------------------
# T190-2: insert stores record with correct fields
# ---------------------------------------------------------------------------

def test_t190_2_insert_stores_record(store):
    """T190-2: insert_presence_signal stores record with correct fields."""
    import sqlite3
    row_id = store.insert_presence_signal(
        signal_source="persona_break",
        signal_type="PERSONA_BREAK_DETECTED",
        led_rgb=(255, 220, 0),
        haptic_duration=150,
        terminal_output="[VAPI] persona break detected -- re-enrollment needed",
        controller_fired=True,
        ps5_compat_mode=False,
    )
    assert row_id > 0
    with sqlite3.connect(store._db_path) as conn:
        row = conn.execute(
            "SELECT signal_source, signal_type, led_rgb, haptic_duration, "
            "terminal_output, controller_fired, ps5_compat_mode "
            "FROM live_presence_signaling_log WHERE id = ?",
            (row_id,),
        ).fetchone()
    assert row[0] == "persona_break"
    assert row[1] == "PERSONA_BREAK_DETECTED"
    assert row[2] == "255,220,0"
    assert row[3] == 150
    assert "persona break" in row[4]
    assert row[5] == 1   # controller_fired=True
    assert row[6] == 0   # ps5_compat_mode=False


# ---------------------------------------------------------------------------
# T190-3: get_presence_signal_status returns zeros when empty
# ---------------------------------------------------------------------------

def test_t190_3_status_empty(store):
    """T190-3: get_presence_signal_status returns zero totals when empty."""
    status = store.get_presence_signal_status()
    assert status["total_signals"] == 0
    assert status["controller_fired_count"] == 0
    assert status["ps5_suppressed_count"] == 0
    assert status["latest_signal_source"] == ""
    assert status["latest_signal_type"] == ""
    assert status["latest_terminal_output"] == ""


# ---------------------------------------------------------------------------
# T190-4: controller_fired_count counts only controller_fired=1 rows
# ---------------------------------------------------------------------------

def test_t190_4_controller_fired_count(store):
    """T190-4: controller_fired_count counts only rows where controller_fired=True."""
    store.insert_presence_signal("a", "CERTIFY_ADJUDICATION", (0, 80, 255), 100,
                                  "[VAPI] CERTIFY adjudication", True, False)
    store.insert_presence_signal("b", "CHAIN_MILESTONE", (0, 255, 200), 0,
                                  "[VAPI] PoAC chain milestone", False, True)
    store.insert_presence_signal("c", "BIOMETRIC_ANOMALY", (255, 140, 0), 80,
                                  "[VAPI] biometric anomaly signal", True, False)

    status = store.get_presence_signal_status()
    assert status["total_signals"] == 3
    assert status["controller_fired_count"] == 2   # rows a and c
    assert status["ps5_suppressed_count"] == 1    # row b


# ---------------------------------------------------------------------------
# T190-5: ps5_suppressed_count counts ps5_compat_mode=1 rows
# ---------------------------------------------------------------------------

def test_t190_5_ps5_suppressed_count(store):
    """T190-5: ps5_suppressed_count counts only rows where ps5_compat_mode=True."""
    for _ in range(3):
        store.insert_presence_signal("src", "CHAIN_MILESTONE", (0, 255, 200), 0,
                                      "[VAPI] chain", False, True)
    store.insert_presence_signal("src", "CERTIFY_ADJUDICATION", (0, 80, 255), 100,
                                  "[VAPI] certify", True, False)

    status = store.get_presence_signal_status()
    assert status["ps5_suppressed_count"] == 3
    assert status["controller_fired_count"] == 1


# ---------------------------------------------------------------------------
# T190-6: Config fields present with correct defaults
# ---------------------------------------------------------------------------

def test_t190_6_config_fields_default(cfg):
    """T190-6: Phase 190 config fields present with correct infrastructure-first defaults."""
    assert hasattr(cfg, "live_presence_signaling_enabled")
    assert cfg.live_presence_signaling_enabled is False

    assert hasattr(cfg, "live_presence_haptic_enabled")
    assert cfg.live_presence_haptic_enabled is True

    assert hasattr(cfg, "live_presence_chain_milestone_interval")
    assert cfg.live_presence_chain_milestone_interval == 100


# ---------------------------------------------------------------------------
# T190-7: _event_to_signal_type maps bus events correctly
# ---------------------------------------------------------------------------

def test_t190_7_event_to_signal_type(agent):
    """T190-7: _event_to_signal_type maps each bus event_type correctly."""
    # persona_break with detected=True
    assert agent._event_to_signal_type("persona_break", {"persona_break_detected": True}) == \
        "PERSONA_BREAK_DETECTED"

    # persona_break with detected=False returns None (no signal)
    assert agent._event_to_signal_type("persona_break", {"persona_break_detected": False}) is None

    # biometric_window_alert always fires BIOMETRIC_ANOMALY
    assert agent._event_to_signal_type("biometric_window_alert", {}) == "BIOMETRIC_ANOMALY"

    # reenrollment_authorized → ENROLLMENT_MILESTONE
    assert agent._event_to_signal_type("reenrollment_authorized", {}) == "ENROLLMENT_MILESTONE"

    # enrollment_guidance_update only when overall_ready=True
    assert agent._event_to_signal_type("enrollment_guidance_update", {"overall_ready": True}) == \
        "ENROLLMENT_MILESTONE"
    assert agent._event_to_signal_type("enrollment_guidance_update", {"overall_ready": False}) is None

    # ratio_recovery_needed → BIOMETRIC_ANOMALY
    assert agent._event_to_signal_type("ratio_recovery_needed", {}) == "BIOMETRIC_ANOMALY"

    # maturity_elevation_available → MATURITY_ELEVATION
    assert agent._event_to_signal_type("maturity_elevation_available", {}) == "MATURITY_ELEVATION"

    # separation_ratio_breakthrough → SEPARATION_BREAKTHROUGH
    assert agent._event_to_signal_type("separation_ratio_breakthrough", {}) == \
        "SEPARATION_BREAKTHROUGH"

    # pir_chain_broken → HARD_CHEAT_DETECTED
    assert agent._event_to_signal_type("pir_chain_broken", {}) == "HARD_CHEAT_DETECTED"

    # unknown event → None
    assert agent._event_to_signal_type("unknown_event_xyz", {}) is None


# ---------------------------------------------------------------------------
# T190-8: _dispatch_signal persists to DB (no controller when ds=None)
# ---------------------------------------------------------------------------

def test_t190_8_dispatch_persists_to_db(store, cfg):
    """T190-8: _dispatch_signal persists signal to DB; controller_fired=False when ds=None."""
    _agent = LivePresenceSignalingAgent(store=store, cfg=cfg, bus=None, ds_integration=None)
    _agent._dispatch_signal("maturity_elevation_available", "MATURITY_ELEVATION")

    status = store.get_presence_signal_status()
    assert status["total_signals"] == 1
    assert status["latest_signal_source"] == "maturity_elevation_available"
    assert status["latest_signal_type"] == "MATURITY_ELEVATION"
    # No ds_integration → controller_fired=False
    assert status["controller_fired_count"] == 0
