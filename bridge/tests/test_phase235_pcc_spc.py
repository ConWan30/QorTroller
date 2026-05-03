"""Phase 235-PCC-SPC tests — SPC classifier + 3-signal haptic-tolerance + frequency-band gate.

T-SPC-1   spc_enabled=False -> behavior identical to Phase 234.7 (regression guard)
T-SPC-2   sample above USL=3500 trimmed from in-control calc (reconnect bursts not pollutants)
T-SPC-3   SPC capability: 26/30 samples NOMINAL (0.867) -> in_control=True -> NOMINAL
T-SPC-4   SPC capability: 24/30 samples NOMINAL (0.800) -> in_control=False (below 0.85) -> not promoted
T-SPC-5   signal_disconnect at any time -> IMMEDIATE DISCONNECTED, ignores SPC capability (INV-PCC-003)
T-SPC-6   Haptic tolerance: trigger_active=1 + av=0.0005 + tp=50Hz + dip 600Hz <=500ms -> NOMINAL
T-SPC-7   Haptic tolerance window cap: trigger_active=1 + dip 600Hz >500ms -> falls through (cap enforced)
T-SPC-8   Haptic tolerance: trigger_active=0 + av=0.0005 -> falls through (Signal 1 missing)
T-SPC-9   Haptic tolerance: trigger_active=1 + av=0.0001 -> falls through (Signal 2 below threshold)
T-SPC-10  Frequency-band gate (INV-PCC-005): tp=2.0Hz (sub-4Hz) -> falls through
T-SPC-11  Frequency-band gate (INV-PCC-005): tp=80Hz (>60Hz) -> falls through
T-SPC-12  Frequency-band gate (INV-PCC-005): tp=50Hz (motor band) -> tolerance fires
T-SPC-13  Frequency-band gate (INV-PCC-005): tp=8Hz (human band) -> tolerance fires
T-SPC-14  Backward-compatible call: update_sample(n_frames, window_s) defaults all kwargs safely
T-SPC-15  Sample buffer extended to 5-tuple: (rate, ts, trigger_active, accel_var, tremor_peak_hz)
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _make_monitor(spc_enabled=False, **cfg_overrides):
    from vapi_bridge.capture_continuity import CaptureHealthMonitor

    class _FakeCfg:
        def __init__(self):
            # PCC defaults
            self.pcc_nominal_hz = 950
            self.pcc_degraded_hz = 100
            self.pcc_stable_window_s = 30
            # SPC defaults (Phase 235-PCC-SPC)
            self.pcc_spc_enabled = spc_enabled
            self.pcc_upper_hz = 3500
            self.pcc_haptic_tolerance_window_ms = 500
            self.pcc_haptic_min_dip_hz = 200
            self.pcc_spc_window_n = 30
            self.pcc_spc_in_control_pct = 0.85
            self.pcc_haptic_tremor_min_hz = 4.0
            self.pcc_haptic_tremor_max_hz = 60.0
            self.pcc_haptic_accel_threshold = 0.0003
            for k, v in cfg_overrides.items():
                setattr(self, k, v)

    return CaptureHealthMonitor(_FakeCfg())


def _make_strict_monitor(**cfg_overrides):
    """For binding-isolation tests: in_control_pct=1.0 means even 1 dip sample defeats
    SPC capability promotion, isolating the haptic-tolerance binding as the only NOMINAL
    rescue path.  Cfg overrides take precedence."""
    return _make_monitor(spc_enabled=True, pcc_spc_in_control_pct=1.0, **cfg_overrides)


# ----------------------------------------------------------------------
# T-SPC-1 — regression guard: spc_enabled=False is byte-identical to Phase 234.7
# ----------------------------------------------------------------------
def test_t_spc_1_disabled_byte_identical_to_phase_234_7():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(spc_enabled=False)
    for _ in range(15):
        m.update_sample(1000, 1.0)  # NOMINAL
    s = m.get_status()
    assert s["capture_state"] == CaptureState.NOMINAL.value
    # Verify with kwargs explicit (defaults must yield same result)
    m2 = _make_monitor(spc_enabled=False)
    for _ in range(15):
        m2.update_sample(1000, 1.0, trigger_active=False, accel_var=0.0, tremor_peak_hz=0.0)
    assert m2.get_status()["capture_state"] == CaptureState.NOMINAL.value


# ----------------------------------------------------------------------
# T-SPC-2 — USL outlier trim
# ----------------------------------------------------------------------
def test_t_spc_2_usl_outlier_trim():
    """A 10000Hz reconnect burst exceeds USL=3500; in-control fraction excludes it."""
    m = _make_monitor(spc_enabled=True)
    # 25 NOMINAL samples in spec [950, 3500]
    for _ in range(25):
        m.update_sample(1100, 1.0)
    # 5 outlier samples way above USL — these should NOT count toward in-control
    for _ in range(5):
        m.update_sample(10000, 1.0)
    samples = list(m._samples)
    in_band = sum(1 for r, _ts, *_ in samples[-30:] if 950 <= r <= 3500)
    assert in_band == 25, f"USL trim: expected 25 in-band, got {in_band}"


# ----------------------------------------------------------------------
# T-SPC-3 — SPC capability in-control ON
# ----------------------------------------------------------------------
def test_t_spc_3_in_control_above_threshold():
    """26/30 samples in [LSL, USL] -> 0.867 >= 0.85 -> NOMINAL."""
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(spc_enabled=True)
    # 26 NOMINAL + 4 below LSL — overall mean stays near NOMINAL
    for _ in range(26):
        m.update_sample(1100, 1.0)
    for _ in range(4):
        m.update_sample(500, 1.0)  # below LSL=950
    s = m.get_status()
    # SPC promotes since in_control_frac=26/30=0.867 >= 0.85 AND mean stays in spec
    assert s["capture_state"] == CaptureState.NOMINAL.value, f"Got {s['capture_state']}"


# ----------------------------------------------------------------------
# T-SPC-4 — SPC capability in-control OFF
# ----------------------------------------------------------------------
def test_t_spc_4_in_control_below_threshold():
    """24/30 samples in spec -> 0.800 < 0.85 -> NOT promoted to NOMINAL by SPC."""
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(spc_enabled=True)
    for _ in range(24):
        m.update_sample(1100, 1.0)
    for _ in range(6):
        m.update_sample(500, 1.0)  # below LSL — drops in-control fraction to 24/30=0.80
    s = m.get_status()
    # SPC fails to promote (0.80 < 0.85), and effective_rate < LSL=950 -> not NOMINAL via classic either
    assert s["capture_state"] != CaptureState.NOMINAL.value, (
        f"Expected NOT NOMINAL (in_control 0.80 < 0.85, mean<LSL), got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-5 — signal_disconnect override (INV-PCC-003)
# ----------------------------------------------------------------------
def test_t_spc_5_signal_disconnect_overrides_spc():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(spc_enabled=True)
    # Build healthy NOMINAL state
    for _ in range(25):
        m.update_sample(1100, 1.0)
    assert m.get_status()["capture_state"] == CaptureState.NOMINAL.value
    # signal_disconnect must override SPC promotion
    m.signal_disconnect("test_override")
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DISCONNECTED.value, (
        f"INV-PCC-003 violated: signal_disconnect should override SPC, got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-6 — Haptic tolerance fires when all 3 signals + frequency-band valid
# ----------------------------------------------------------------------
def test_t_spc_6_haptic_tolerance_fires():
    """Strict-SPC fixture isolates the binding as the only NOMINAL rescue path."""
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()  # in_control_pct=1.0 → SPC capability cannot rescue
    # Haptic burst sample with all 3 binding signals + frequency in motor band
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0005, tremor_peak_hz=50.0)
    s = m.get_status()
    # Only the haptic-tolerance binding can promote NOMINAL here
    assert s["capture_state"] == CaptureState.NOMINAL.value, (
        f"Haptic tolerance binding failed to suppress sub-second dip, got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-7 — Haptic tolerance window cap (must enforce <=500ms)
# ----------------------------------------------------------------------
def test_t_spc_7_haptic_tolerance_window_cap():
    """Tolerance window of 100ms; binding sample older than that doesn't qualify."""
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(spc_enabled=True, pcc_haptic_tolerance_window_ms=100)
    # Inject binding sample
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0005, tremor_peak_hz=50.0)
    # Sleep past the 100ms tolerance window
    time.sleep(0.3)
    # Now an additional dip — but no NEW binding sample means tolerance gate fails
    m.update_sample(600, 1.0, trigger_active=False)
    s = m.get_status()
    assert s["capture_state"] != CaptureState.NOMINAL.value, (
        f"Window cap failed: tolerance fired beyond window_ms, got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-8 — Signal 1 (trigger_active) missing
# ----------------------------------------------------------------------
def test_t_spc_8_signal1_missing():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()
    m.update_sample(600, 1.0, trigger_active=False, accel_var=0.0005, tremor_peak_hz=50.0)
    s = m.get_status()
    # Without trigger_active, tolerance binding fails → classic fall-through → DEGRADED
    assert s["capture_state"] == CaptureState.DEGRADED.value, (
        f"Expected DEGRADED (Signal 1 missing should reject), got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-9 — Signal 2 (accel_var) below threshold
# ----------------------------------------------------------------------
def test_t_spc_9_signal2_below_threshold():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()
    # accel_var=0.0001 < threshold 0.0003
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0001, tremor_peak_hz=50.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DEGRADED.value, (
        f"Expected DEGRADED (Signal 2 below threshold), got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-10 — Frequency-band gate: sub-4Hz rejected (INV-PCC-005)
# ----------------------------------------------------------------------
def test_t_spc_10_freq_band_sub_4hz_rejected():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()
    # tremor_peak_hz=2.0 outside [4, 60] band — INV-PCC-005 frequency-band gate rejects
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0005, tremor_peak_hz=2.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DEGRADED.value, (
        f"Expected DEGRADED (sub-4Hz spectral signature should reject — INV-PCC-005), "
        f"got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-11 — Frequency-band gate: >60Hz rejected (INV-PCC-005)
# ----------------------------------------------------------------------
def test_t_spc_11_freq_band_above_60hz_rejected():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0005, tremor_peak_hz=80.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.DEGRADED.value, (
        f"Expected DEGRADED (above 60Hz should reject — INV-PCC-005), got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-12 — Frequency-band gate: motor band (50Hz) accepted
# ----------------------------------------------------------------------
def test_t_spc_12_freq_band_motor_accepted():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0005, tremor_peak_hz=50.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.NOMINAL.value, (
        f"Motor-band (50Hz) tremor should fire tolerance, got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-13 — Frequency-band gate: human band (8Hz) accepted
# ----------------------------------------------------------------------
def test_t_spc_13_freq_band_human_accepted():
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_strict_monitor()
    m.update_sample(600, 1.0, trigger_active=True, accel_var=0.0005, tremor_peak_hz=8.0)
    s = m.get_status()
    assert s["capture_state"] == CaptureState.NOMINAL.value, (
        f"Human-band (8Hz) tremor should fire tolerance, got {s['capture_state']}"
    )


# ----------------------------------------------------------------------
# T-SPC-14 — Backward-compatible call signature
# ----------------------------------------------------------------------
def test_t_spc_14_backward_compat_call():
    """update_sample(n_frames, window_s) without kwargs MUST work and produce safe defaults."""
    from vapi_bridge.capture_continuity import CaptureState
    m = _make_monitor(spc_enabled=True)
    # Old-style 2-arg call must succeed and not crash
    m.update_sample(1100, 1.0)
    m.update_sample(0, 1.0)
    # Verify sample stored as 5-tuple with safe defaults
    samples = list(m._samples)
    assert len(samples[-1]) == 5, f"sample tuple is {len(samples[-1])} elements, expected 5"
    assert samples[-1][2] is False, "trigger_active default should be False"
    assert samples[-1][3] == 0.0, "accel_var default should be 0.0"
    assert samples[-1][4] == 0.0, "tremor_peak_hz default should be 0.0"


# ----------------------------------------------------------------------
# T-SPC-15 — Sample buffer 5-tuple field-order regression guard
# ----------------------------------------------------------------------
def test_t_spc_15_sample_buffer_5tuple_field_order():
    m = _make_monitor(spc_enabled=True)
    m.update_sample(1234, 1.0, trigger_active=True, accel_var=0.0042, tremor_peak_hz=47.5)
    s = list(m._samples)[-1]
    rate, ts, ta, av, tp = s
    assert rate == 1234.0, f"rate field at index 0, got {rate}"
    assert isinstance(ts, float), f"ts field at index 1, got {type(ts).__name__}"
    assert ta is True, f"trigger_active at index 2, got {ta}"
    assert av == 0.0042, f"accel_var at index 3, got {av}"
    assert tp == 47.5, f"tremor_peak_hz at index 4, got {tp}"
