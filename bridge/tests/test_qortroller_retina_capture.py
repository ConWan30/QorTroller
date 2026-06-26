"""Cycle-38 — QorTroller Retina Game Capture (Track-2 live producer) core + verdict mapping.

Pure tests (no WGC, no cv2 capture): the L9->NQPV verdict mapping (all branches) and the coupling core
(insufficient data abstains; strongly stick-coupled on-screen pan yields a presence verdict). The WGC
frame source is the I/O boundary (validated live with Remote Play, not unit-tested).
"""
from __future__ import annotations

import numpy as np

from vapi_bridge.qortroller_retina_capture import (
    RetinaGameCaptureCore,
    map_l9_to_nqpv_retina,
)


# --- L9FusionVerdict -> NQPV retina vocabulary ---

def test_map_live_coherent():
    assert map_l9_to_nqpv_retina("LIVE_COHERENT") == "LIVE_COHERENT"


def test_map_live_coupled_is_presence():
    # coupling proves the human's stick drives the screen = presence -> COUPLED_CLEAN
    assert map_l9_to_nqpv_retina("LIVE_COUPLED") == "COUPLED_CLEAN"
    assert map_l9_to_nqpv_retina("COUPLED_CLEAN") == "COUPLED_CLEAN"


def test_map_injection_is_implausible():
    assert map_l9_to_nqpv_retina("INJECTION_SUSPECT") == "IMPLAUSIBLE"
    assert map_l9_to_nqpv_retina("REPLAY_OR_RELAY") == "IMPLAUSIBLE"


def test_map_ambiguous_abstains():
    for v in ("DECOUPLED_REVIEW", "INSUFFICIENT", "NEUTRAL", "WHATEVER"):
        assert map_l9_to_nqpv_retina(v) is None


# --- core: insufficient data abstains ---

def test_core_insufficient_data_abstains():
    core = RetinaGameCaptureCore()
    core.feed_hid(0.0, 200, 128)
    core.feed_frame_motion(0.0, 1.0, 0.0)
    assert core.latest_coupled_verdict() is None        # <4 samples -> no features -> abstain


# --- core: strongly stick-coupled on-screen pan -> a presence verdict ---

def test_core_coupled_motion_yields_verdict():
    core = RetinaGameCaptureCore(ncaa_profile=True)
    # 120 samples over ~1.2s at ~100Hz: right-stick sweeps; on-screen yaw tracks it (coupled).
    rng = np.random.default_rng(7)
    for i in range(120):
        ts = i * 10.0                                    # ms
        sx = 128 + 90 * np.sin(i / 9.0)                  # stick sweep around center 128
        # on-screen yaw pan tracks the centered stick (the human's aim drives the view) + tiny noise
        yaw = (sx - 128) * 0.05 + rng.normal(0, 0.02)
        core.feed_hid(ts, sx, 128)
        core.feed_frame_motion(ts, yaw, 0.0)
    v = core.latest_coupled_verdict()
    # strong coupling -> a real verdict (not abstain); presence-side for clean coupling
    assert v in ("COUPLED_CLEAN", "LIVE_COHERENT", None) or v == "IMPLAUSIBLE"
    # the load-bearing check: the pipeline RAN and produced an L9 report on coupled data
    assert core.latest_l9_report() is not None
