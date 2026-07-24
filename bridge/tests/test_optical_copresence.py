"""Thesis C optical co-presence tests — football-regime spacing, empirical null, fail-closed gate.

grok optical r04 fixes: F8 (circular period = n*mean_gap, no grid collapse), F10 (event spacing
~30s like real NCAA snaps, where a pure-phase null actually discriminates), F6/F9 (flag is
fail-closed until calibrated=True).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.optical_copresence import (  # noqa: E402
    TimedEvent, optical_copresence, optical_consistent_flag, REACTION_WINDOW_MS,
)

SNAP_MS = 30_000.0   # football-realistic event spacing (~30s between snaps) — grok F10


def _events(n, spacing=SNAP_MS, t0=0.0):
    return [TimedEvent(t0 + spacing * i, "snap") for i in range(n)]


def _locked(events, offset_ms=300.0):
    return [TimedEvent(e.ts_ms + offset_ms, "resp") for e in events]


# ---- F8: circular null keeps all n points distinct on a regular grid ----

def test_circular_null_no_point_collapse_on_regular_grid():
    # 16 responses on a perfectly regular grid; after the internal shift the null must be built from
    # n distinct points (this is what the F8 period=n*mean_gap fix guarantees). We verify indirectly:
    # a true event-locked stream at football spacing is coupled, and its null_q is < 1.0 (not corrupted).
    ev = _events(16)
    r = optical_copresence(ev, _locked(ev, 300.0))
    assert r.event_coupled is True
    assert r.null_q < 1.0           # a collapsed null would pin null_q at 1.0 and this would be flaky
    assert r.hit_rate > r.null_q


# ---- event-locked live stream at football spacing -> coupled ----

def test_football_spacing_locked_is_coupled():
    ev = _events(16)
    r = optical_copresence(ev, _locked(ev, 250.0))
    assert r.event_coupled is True


# ---- F1/F8: periodic macro (shares nothing with event phase) not coupled ----

def test_periodic_macro_far_off_phase_not_coupled():
    ev = _events(16)                                  # snaps at 0,30s,60s...
    macro = [TimedEvent(15_000.0 + SNAP_MS * i, "mash") for i in range(16)]  # 15s off-phase
    r = optical_copresence(ev, macro)
    assert r.event_coupled is False


def test_dense_mash_not_coupled():
    ev = _events(16)
    span = ev[-1].ts_ms + SNAP_MS
    dense = [TimedEvent(float(t), "mash") for t in range(0, int(span), 1000)]  # 1 press/sec
    r = optical_copresence(ev, dense)
    assert r.event_coupled is False


# ---- dump replay against wrong session (responses precede events) -> not coupled ----

def test_replay_preceding_events_not_coupled():
    ev = _events(16)
    replay = [TimedEvent(e.ts_ms - 5_000.0, "resp") for e in ev]   # 5s before each -> outside window
    r = optical_copresence(ev, replay)
    assert r.event_coupled is False


# ---- fail-closed ----

def test_too_few_events_fail_closed():
    ev = _events(4)
    assert optical_copresence(ev, _locked(ev)).event_coupled is False


def test_no_responses_fail_closed():
    ev = _events(16)
    assert optical_copresence(ev, []).event_coupled is False


# ---- F6/F9: the flag is fail-closed until calibrated=True ----

def test_flag_fail_closed_until_calibrated():
    ev = _events(16)
    resp = _locked(ev, 300.0)
    # underlying result is coupled...
    assert optical_copresence(ev, resp).event_coupled is True
    # ...but the flag that can flip CONTINUOUS stays False until explicitly calibrated (post-U3)
    assert optical_consistent_flag(ev, resp) is False                 # default uncalibrated
    assert optical_consistent_flag(ev, resp, calibrated=False) is False
    assert optical_consistent_flag(ev, resp, calibrated=True) is True  # only after U3


def test_claim_language_session_not_humanity():
    ev = _events(16)
    d = optical_copresence(ev, _locked(ev)).to_dict()
    assert d["claim"] == "session_co_presence_not_humanity"
    assert "event_coupled" in d


# ---- end-to-end: uncalibrated optical => CONTINUOUS unreachable (fail-closed), caps at PARTIAL ----

def test_end_to_end_uncalibrated_optical_caps_at_partial():
    from l9_presence.realplay_liveness import (
        evaluate_realplay_liveness, WindowFeatures, RealPlayVerdict, DEVICE_TICKS_PER_MS,
    )

    def window(optical):
        return WindowFeatures(
            capture_nominal=True, host_exclusive_usb_or_unknown=True,
            gameplay_active_fraction=0.8, menu_detected=False,
            tremor_peak_hz=9.5, tremor_band_power=0.01,
            l2b_coupled_fraction=0.7, press_events=40, l5_macro_quantized=False,
            device_ts_span_ticks=int(DEVICE_TICKS_PER_MS * 130_000), wall_span_ms=130_000.0,
            window_s=130.0, optical_consistent=optical,
        )

    ev = _events(16)
    resp = _locked(ev, 300.0)
    # production (uncalibrated) flag -> False -> PARTIAL (CONTINUOUS fail-closed unreachable)
    assert optical_consistent_flag(ev, resp) is False
    assert evaluate_realplay_liveness(window(optical_consistent_flag(ev, resp))).verdict \
        is RealPlayVerdict.PARTIAL_PRESENT
    # post-U3 (calibrated) coupled flag -> True -> CONTINUOUS reachable
    assert evaluate_realplay_liveness(window(optical_consistent_flag(ev, resp, calibrated=True))).verdict \
        is RealPlayVerdict.CONTINUOUS_PRESENT
