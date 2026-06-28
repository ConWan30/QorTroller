"""Channel B1 live-wiring (P2): RetinaGameCaptureCore feeds R2 trigger (feed_trigger, from the HID loop)
and center-ROI luminance (feed_roi, from the retina frames) into the trigger->HUD oracle, and surfaces
the verdict via latest_trigger_hud(). Pure core (no WGC) — locks the live feed path that
dualshock_integration + WgcFrameSource drive in production.
"""
from __future__ import annotations

import numpy as np

from vapi_bridge.qortroller_retina_capture import RetinaGameCaptureCore


def _pulses(ts, times, width_ms=35.0, amp=255.0):
    sig = np.zeros_like(ts)
    for t in times:
        sig = sig + amp * np.exp(-0.5 * ((ts - t) / (width_ms / 2.0)) ** 2)
    return sig


def _feed(core, *, decoupled, lag_ms=120.0, seed=0):
    rng = np.random.default_rng(seed)
    tr_ts = np.arange(0.0, 4000.0, 1.0)                              # ~1 kHz trigger (HID loop)
    fires = np.sort(rng.uniform(250.0, 3750.0, 14))
    for t, v in zip(tr_ts, _pulses(tr_ts, fires)):
        core.feed_trigger(float(t), float(v))
    roi_ts = np.arange(0.0, 4000.0, 1000.0 / 60.0)                  # 60 fps center-ROI (frames)
    flash_times = np.sort(rng.uniform(250.0, 3750.0, 14)) if decoupled else (fires + lag_ms)
    roi = _pulses(roi_ts, flash_times) + 20.0 + 6.0 * rng.standard_normal(roi_ts.size)
    for t, v in zip(roi_ts, roi):
        core.feed_roi(float(t), float(v))


def test_live_wired_genuine_fire_couples():
    core = RetinaGameCaptureCore()
    assert core._th_oracle is not None                              # Channel B1 oracle wired
    _feed(core, decoupled=False)
    rep = core.latest_trigger_hud()
    assert rep is not None
    f, nc = rep
    assert f.coupled is True
    assert f.coupling_score > 0.6
    assert f.coupling_score - nc > 0.3                              # real causal margin over the shuffled null


def test_live_wired_decoupled_replay_does_not_couple():
    core = RetinaGameCaptureCore()
    _feed(core, decoupled=True)
    rep = core.latest_trigger_hud()
    assert rep is not None
    f, _ = rep
    assert f.coupled is False
    assert f.coupling_score < 0.45                                  # someone else's flashes don't bind to your R2


def test_live_wired_no_fire_abstains():
    core = RetinaGameCaptureCore()
    for t in np.arange(0.0, 4000.0, 1.0):
        core.feed_trigger(float(t), 0.0)                            # not firing
    for t in np.arange(0.0, 4000.0, 1000.0 / 60.0):
        core.feed_roi(float(t), 20.0)
    assert core.latest_trigger_hud() is None                       # abstain (neutral, not a false accusation)


def test_live_wired_b2_hit_couples_independently_of_b1():
    """B2 (trigger->RED hitmarker) runs on its own oracle: feed_trigger feeds both, feed_roi_red drives
    B2 only. Genuine hits -> red spikes synced to your trigger -> B2 couples; B1 (no luminance fed) abstains."""
    core = RetinaGameCaptureCore()
    assert core._th2_oracle is not None
    rng = np.random.default_rng(3)
    tr_ts = np.arange(0.0, 4000.0, 1.0)
    fires = np.sort(rng.uniform(250.0, 3750.0, 14))
    for t, v in zip(tr_ts, _pulses(tr_ts, fires)):
        core.feed_trigger(float(t), float(v))                      # feeds BOTH B1 + B2 oracles
    roi_ts = np.arange(0.0, 4000.0, 1000.0 / 60.0)
    red = _pulses(roi_ts, fires + 120.0) + 5.0 + 4.0 * rng.standard_normal(roi_ts.size)  # red hitmarkers follow hits
    for t, v in zip(roi_ts, red):
        core.feed_roi_red(float(t), float(v))                      # B2 channel only
    rep = core.latest_hit_hud()
    assert rep is not None
    f, nc = rep
    assert f.coupled is True and f.coupling_score > 0.6 and f.coupling_score - nc > 0.3
    assert core.latest_trigger_hud() is None                       # B1 got no luminance feed -> abstains
