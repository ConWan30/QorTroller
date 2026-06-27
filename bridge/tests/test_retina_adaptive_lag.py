"""Cycle-39 — meticulous adaptive lag adjustment for the QorTroller Retina Game Capture.

Proves (1) the coupling oracle's lag-search window is now instance-tunable + backward-compatible, and
(2) RetinaGameCapture.tune() applies the AdaptiveCaptureGovernor live — widening the oracle's causal-lag
search window when the measured Remote Play lag nears the ceiling.
"""
from __future__ import annotations

import time
from types import SimpleNamespace


def test_oracle_lag_window_backward_compatible_and_tunable():
    from l9_presence.coupling import COMMON_RATE_HZ, LAG_MAX_MS, InputOutputCouplingOracle
    # default construction reads the module constants (every existing call site is byte-identical)
    o = InputOutputCouplingOracle()
    assert o.lag_max_ms == LAG_MAX_MS
    assert o.common_rate_hz == COMMON_RATE_HZ
    # explicit override is honored (this is what the governor mutates)
    o2 = InputOutputCouplingOracle(lag_max_ms=900.0, common_rate_hz=180.0)
    assert o2.lag_max_ms == 900.0
    assert o2.common_rate_hz == 180.0


def test_tune_widens_oracle_lag_window_when_lag_near_ceiling():
    from l9_presence.adaptive_capture import AdaptiveCaptureGovernor, CaptureControls
    from vapi_bridge.qortroller_retina_capture import (
        RetinaGameCapture,
        RetinaGameCaptureCore,
        WgcFrameSource,
    )
    # build the tie WITHOUT starting WGC (no Windows capture in CI)
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)
    rgc.core = RetinaGameCaptureCore(ncaa_profile=False)
    rgc._source = WgcFrameSource(rgc.core, "x")
    rgc.started = True
    rgc._governor = AdaptiveCaptureGovernor(CaptureControls())

    # steady 60fps frame cadence so the governor passes the "steady video" priority and reaches the lag rule
    base = time.time() * 1000.0
    for i in range(60):
        rgc._source._frame_ts.append(base + i * 16.7)
    # measured lag near the 500ms ceiling (>= 500-80 headroom) -> governor should widen
    rgc.core._last_feats = SimpleNamespace(lag_ms=460.0, grid_samples=300, coupling_score=0.6)

    before = rgc.core._oracle.lag_max_ms
    decision = rgc.tune()
    assert decision is not None
    assert rgc.core._oracle.lag_max_ms > before, "lag window must widen when measured lag nears the ceiling"
    assert "lag_near_ceiling" in decision.get("flags", []) or decision.get("reason") == "widen_lag_window"


def test_tune_noop_with_too_few_frames():
    from l9_presence.adaptive_capture import AdaptiveCaptureGovernor, CaptureControls
    from vapi_bridge.qortroller_retina_capture import (
        RetinaGameCapture,
        RetinaGameCaptureCore,
        WgcFrameSource,
    )
    rgc = RetinaGameCapture.__new__(RetinaGameCapture)
    rgc.core = RetinaGameCaptureCore(ncaa_profile=False)
    rgc._source = WgcFrameSource(rgc.core, "x")
    rgc.started = True
    rgc._governor = AdaptiveCaptureGovernor(CaptureControls())
    assert rgc.tune() is None  # no frames yet -> safe no-op
