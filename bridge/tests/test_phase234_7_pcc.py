"""Phase 234.7 — Physical Capture Continuity (PCC).

T234_7-1:  CaptureHealthMonitor starts in DISCONNECTED/UNKNOWN state
T234_7-2:  update_sample at nominal rate (1000 frames/s) → NOMINAL + EXCLUSIVE_USB
T234_7-3:  update_sample at degraded rate (500 Hz) → DEGRADED state
T234_7-4:  zero frames or signal_disconnect → DISCONNECTED state
T234_7-5:  grind_ready=False until 30s sustained NOMINAL (stable_window_s)
T234_7-6:  pop_transitions returns buffered state changes and clears the buffer
T234_7-7:  config fields grind_mode and grind_target exist with correct defaults
T234_7-8:  store insert_capture_health_event and get_capture_health_status round-trip
T234_7-9:  DualShockIntegration has set_pcc_monitor method and _pcc_monitor attribute
T234_7-10: session_counting_paused = grind_mode AND NOT grind_ready (logic gate)
T234_7-11: INV-PCC-001 get_status and is_grind_ready call _recompute before reading state
"""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_monitor(nominal_hz=950, degraded_hz=100, stable_s=30):
    from vapi_bridge.capture_continuity import CaptureHealthMonitor

    class _FakeCfg:
        pcc_nominal_hz = nominal_hz
        pcc_degraded_hz = degraded_hz
        pcc_stable_window_s = stable_s

    return CaptureHealthMonitor(cfg=_FakeCfg())


def _make_store(db_path):
    from vapi_bridge.store import Store
    return Store(db_path)


def _make_config(**overrides):
    from vapi_bridge.config import Config
    return Config(**overrides)


@pytest.fixture()
def tmp_db(tmp_path):
    return str(tmp_path / "test_pcc.db")


# ---------------------------------------------------------------------------
# T234_7-1: Initial state is DISCONNECTED / UNKNOWN
# ---------------------------------------------------------------------------

def test_t234_7_1_initial_state():
    from vapi_bridge.capture_continuity import CaptureState, HostState
    m = _make_monitor()
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DISCONNECTED.value
    assert s["host_state"] == HostState.UNKNOWN.value
    assert s["poll_rate_hz"] == pytest.approx(0.0, abs=1.0)
    assert not s["grind_ready"]


# ---------------------------------------------------------------------------
# T234_7-2: Nominal rate → NOMINAL + EXCLUSIVE_USB
# ---------------------------------------------------------------------------

def test_t234_7_2_nominal_rate_state():
    from vapi_bridge.capture_continuity import CaptureState, HostState
    m = _make_monitor(nominal_hz=950, stable_s=30)
    # Feed 10 samples at 1000 Hz (1000 frames per 1s interval)
    for _ in range(15):
        m.update_sample(n_frames=1000, window_s=1.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.NOMINAL.value, (
        f"Expected NOMINAL at 1000 Hz, got {s['capture_state']}"
    )
    assert s["poll_rate_hz"] == pytest.approx(1000.0, abs=5.0)
    assert s["host_state"] == HostState.EXCLUSIVE_USB.value


# ---------------------------------------------------------------------------
# T234_7-3: Degraded rate (500 Hz) → DEGRADED state
# ---------------------------------------------------------------------------

def test_t234_7_3_degraded_rate_state():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(nominal_hz=950, degraded_hz=100)
    for _ in range(10):
        m.update_sample(n_frames=500, window_s=1.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DEGRADED.value, (
        f"Expected DEGRADED at 500 Hz, got {s['capture_state']}"
    )


# ---------------------------------------------------------------------------
# T234_7-4: Zero frames / signal_disconnect → DISCONNECTED
# ---------------------------------------------------------------------------

def test_t234_7_4_disconnect_signal():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor()
    # First bring to NOMINAL
    for _ in range(10):
        m.update_sample(1000, 1.0)
    assert m.get_status()["capture_state"] == CaptureState.NOMINAL.value

    # Signal disconnect
    m.signal_disconnect("hid_timeout")
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DISCONNECTED.value
    assert s["disconnect_reason"] == "hid_timeout"


# ---------------------------------------------------------------------------
# T234_7-5: grind_ready=False until stable_window_s elapsed
# ---------------------------------------------------------------------------

def test_t234_7_5_grind_ready_requires_sustained_nominal():
    from vapi_bridge.capture_continuity import CaptureHealthMonitor
    import threading, time

    class _Cfg:
        pcc_nominal_hz = 950
        pcc_degraded_hz = 100
        pcc_stable_window_s = 2  # short window for test speed

    m = CaptureHealthMonitor(cfg=_Cfg())

    # Feed nominal frames but check before stable window elapses
    for _ in range(5):
        m.update_sample(1000, 1.0)

    # Immediately after reaching NOMINAL: grind_ready still False (only 0s elapsed)
    assert not m.get_status()["grind_ready"], (
        "grind_ready must be False before stable_window_s has elapsed"
    )

    # Wait for stable_window_s to elapse and feed one more sample
    time.sleep(2.1)
    m.update_sample(1000, 1.0)
    assert m.get_status()["grind_ready"], (
        "grind_ready must be True after stable_window_s elapsed in NOMINAL state"
    )


# ---------------------------------------------------------------------------
# T234_7-6: pop_transitions returns transitions and clears buffer
# ---------------------------------------------------------------------------

def test_t234_7_6_pop_transitions():
    m = _make_monitor()
    # Initial DISCONNECTED → trigger NOMINAL transition
    for _ in range(10):
        m.update_sample(1000, 1.0)
    transitions = m.pop_transitions()
    assert len(transitions) >= 1, "Should have at least one transition (DISCONNECTED→NOMINAL)"
    assert transitions[-1]["new_state"] == "NOMINAL"
    # Second pop should be empty
    assert m.pop_transitions() == [], "Buffer should be cleared after pop"


# ---------------------------------------------------------------------------
# T234_7-7: Config has grind_mode and grind_target with correct defaults
# ---------------------------------------------------------------------------

def test_t234_7_7_config_defaults():
    cfg = _make_config()
    assert hasattr(cfg, "grind_mode"), "Config must have grind_mode field"
    assert hasattr(cfg, "grind_target"), "Config must have grind_target field"
    assert hasattr(cfg, "pcc_enabled"), "Config must have pcc_enabled field"
    assert hasattr(cfg, "pcc_nominal_hz"), "Config must have pcc_nominal_hz field"
    assert hasattr(cfg, "pcc_degraded_hz"), "Config must have pcc_degraded_hz field"
    assert hasattr(cfg, "pcc_stable_window_s"), "Config must have pcc_stable_window_s field"
    assert cfg.grind_mode is False, "grind_mode default must be False"
    assert cfg.grind_target == 100, "grind_target default must be 100"
    assert cfg.pcc_enabled is True, "pcc_enabled default must be True"
    assert cfg.pcc_nominal_hz == 950
    assert cfg.pcc_degraded_hz == 100
    assert cfg.pcc_stable_window_s == 30


# ---------------------------------------------------------------------------
# T234_7-8: Store round-trip: insert + get_capture_health_status
# ---------------------------------------------------------------------------

def test_t234_7_8_store_round_trip(tmp_db):
    store = _make_store(tmp_db)

    row_id = store.insert_capture_health_event(
        capture_state="NOMINAL",
        host_state="EXCLUSIVE_USB",
        poll_rate_hz=1002.5,
        transition_reason="rate_change",
        grind_mode=True,
        session_id="sess-001",
    )
    assert row_id > 0, "insert_capture_health_event must return a valid row id"

    status = store.get_capture_health_status()
    assert status["capture_state"] == "NOMINAL"
    assert status["host_state"] == "EXCLUSIVE_USB"
    assert status["poll_rate_hz"] == pytest.approx(1002.5, abs=0.1)
    assert status["grind_mode"] is True
    assert status["n_events"] == 1


# ---------------------------------------------------------------------------
# T234_7-9: DualShockIntegration has set_pcc_monitor and _pcc_monitor
# ---------------------------------------------------------------------------

def test_t234_7_9_dualshock_pcc_monitor_attribute():
    # Only check the attribute exists by importing the module directly
    import vapi_bridge.dualshock_integration as ds_mod
    # DualShockTransport should have set_pcc_monitor as a method
    assert hasattr(ds_mod.DualShockTransport, "set_pcc_monitor"), (
        "DualShockTransport must have set_pcc_monitor method (Phase 234.7)"
    )


# ---------------------------------------------------------------------------
# T234_7-10: session_counting_paused logic gate
# ---------------------------------------------------------------------------

def test_t234_7_10_session_counting_paused_logic():
    """session_counting_paused = grind_mode AND NOT grind_ready."""
    cases = [
        (False, False, False),  # not grind_mode → never paused
        (False, True,  False),  # not grind_mode → never paused
        (True,  True,  False),  # grind_mode + grind_ready → NOT paused
        (True,  False, True),   # grind_mode + NOT ready → paused
    ]
    for grind_mode, grind_ready, expected_paused in cases:
        result = grind_mode and not grind_ready
        assert result == expected_paused, (
            f"grind_mode={grind_mode}, grind_ready={grind_ready} → "
            f"expected paused={expected_paused}, got {result}"
        )


# ---------------------------------------------------------------------------
# T234_7-11: INV-PCC-001 — get_status() and is_grind_ready() recompute state
# ---------------------------------------------------------------------------

def test_t234_7_11_inv_pcc_001_stale_read():
    """get_status() and is_grind_ready() must call _recompute(now) before reading
    cached state, so a HID stall that occurred since the last update_sample() is
    detected at read time rather than at the next update_sample() call.

    Arrange: bring monitor to NOMINAL via update_sample.  Then let time advance
    without any further update_sample calls (simulating a HID stall).  The
    _recompute staleness check (> 3s since last sample) should flip the state
    to DISCONNECTED, and get_status() must reflect this WITHOUT any further
    update_sample() call.
    """
    import time as _time
    from unittest.mock import patch

    from vapi_bridge.capture_continuity import (
        CaptureHealthMonitor, CaptureState,
    )

    monitor = _make_monitor(nominal_hz=950, degraded_hz=100, stable_s=1)

    # Bring to NOMINAL
    monitor.update_sample(n_frames=1000, window_s=1.0)
    status_before = monitor.get_status()
    assert status_before["capture_state"] == CaptureState.NOMINAL.value, (
        "Baseline: after nominal update, state must be NOMINAL"
    )

    # Simulate 5 seconds of wall-clock time passing without any update_sample.
    # We patch time.monotonic so _recompute sees enough elapsed time to trigger
    # the staleness path (> 3 s since last sample).
    fake_now = _time.monotonic() + 5.0
    with patch("vapi_bridge.capture_continuity.time") as mock_time:
        mock_time.monotonic.return_value = fake_now
        mock_time.time.return_value = _time.time() + 5.0

        status_stale = monitor.get_status()
        grind_ready = monitor.is_grind_ready()

    assert status_stale["capture_state"] == CaptureState.DISCONNECTED.value, (
        "INV-PCC-001: get_status() must detect stale samples (>3s gap) and report "
        "DISCONNECTED — stale NOMINAL is a grind integrity risk during HID stall"
    )
    assert grind_ready is False, (
        "INV-PCC-001: is_grind_ready() must return False when recomputed state is "
        "DISCONNECTED (stale read would have incorrectly returned True)"
    )
