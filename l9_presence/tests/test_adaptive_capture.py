"""Tests for the Adaptive Capture Governor (pure logic; no capture I/O)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from l9_presence.adaptive_capture import (  # noqa: E402
    AdaptiveCaptureGovernor,
    CaptureControls,
    CaptureTelemetry,
    GovernorConfig,
    compute_telemetry,
    decide,
)

CFG = GovernorConfig()


def _ts(fps: float, n: int = 20, jitter_ms: float = 0.0):
    """Frame timestamps (ms) at a steady fps, optional alternating jitter."""
    dt = 1000.0 / fps
    out = [0.0]
    for i in range(1, n):
        j = jitter_ms if i % 2 else -jitter_ms
        out.append(out[-1] + dt + j)
    return out


# ---- compute_telemetry ----

def test_telemetry_fps_and_cv():
    t = compute_telemetry(_ts(60.0, n=30))
    assert abs(t.measured_fps - 60.0) < 0.5
    assert t.fps_cv < 0.01  # steady -> near-zero jitter


def test_telemetry_jitter_raises_cv():
    steady = compute_telemetry(_ts(60.0, n=30, jitter_ms=0.0))
    jittery = compute_telemetry(_ts(60.0, n=30, jitter_ms=8.0))
    assert jittery.fps_cv > steady.fps_cv > -1
    assert jittery.fps_cv > 0.2


def test_telemetry_stale_ms():
    t = compute_telemetry([0.0, 16.0, 32.0], now_ms=132.0)
    assert t.stale_ms == 100.0


def test_telemetry_empty_is_safe():
    t = compute_telemetry([])
    assert t.measured_fps == 0.0 and t.fps_cv == 0.0 and t.n_frames == 0


# ---- decide: steady-video priority ----

def test_low_fps_raises_downscale():
    t = CaptureTelemetry(measured_fps=20.0, fps_cv=0.05)
    d = decide(t, CaptureControls(downscale=4, target_fps=60.0), CFG)
    assert d.changed and d.after.downscale == 5 and "recover_fps" in d.reason
    assert "unsteady_fps" in d.flags


def test_high_jitter_raises_downscale():
    t = CaptureTelemetry(measured_fps=58.0, fps_cv=0.40)
    d = decide(t, CaptureControls(downscale=4, target_fps=60.0), CFG)
    assert d.changed and d.after.downscale == 5


def test_fps_recovery_shrinks_region_when_downscale_maxed():
    t = CaptureTelemetry(measured_fps=20.0, fps_cv=0.05)
    d = decide(t, CaptureControls(downscale=8, region_scale=1.0, target_fps=60.0), CFG)
    assert d.changed and abs(d.after.region_scale - 0.9) < 1e-9 and "region_shrink" in d.reason


def test_fps_at_floor_reports_no_change():
    t = CaptureTelemetry(measured_fps=20.0, fps_cv=0.05)
    d = decide(t, CaptureControls(downscale=8, region_scale=0.5, target_fps=60.0), CFG)
    assert not d.changed and "fps_floor_reached" in d.flags


# ---- decide: estimator validity ----

def test_lag_near_ceiling_widens_window():
    t = CaptureTelemetry(measured_fps=60.0, fps_cv=0.05, coupling_lag_ms=440.0)
    d = decide(t, CaptureControls(lag_window_ms=500.0), CFG)
    assert d.changed and d.after.lag_window_ms == 650.0 and "lag_near_ceiling" in d.flags


def test_lag_window_maxed_flags():
    t = CaptureTelemetry(measured_fps=60.0, fps_cv=0.05, coupling_lag_ms=1150.0)
    d = decide(t, CaptureControls(lag_window_ms=1200.0), CFG)
    assert not d.changed and "lag_window_maxed" in d.flags


def test_grid_short_raises_resample():
    t = CaptureTelemetry(measured_fps=60.0, fps_cv=0.05, grid_samples=80)
    d = decide(t, CaptureControls(resample_hz=120.0), CFG)
    assert d.changed and d.after.resample_hz == 150.0 and "grid_short" in d.flags


# ---- decide: opportunistic sharpening + steady ----

def test_high_stable_fps_sharpens_flow():
    t = CaptureTelemetry(measured_fps=80.0, fps_cv=0.05)
    d = decide(t, CaptureControls(downscale=4, target_fps=60.0), CFG)
    assert d.changed and d.after.downscale == 3 and "sharpen_flow" in d.reason


def test_steady_no_change():
    t = CaptureTelemetry(measured_fps=62.0, fps_cv=0.05, coupling_lag_ms=120.0, grid_samples=300)
    d = decide(t, CaptureControls(downscale=4, target_fps=60.0), CFG)
    assert not d.changed and d.reason == "steady"


def test_steady_priority_fps_over_sharpen():
    # both unsteady AND would-be-sharpen: steadiness wins
    t = CaptureTelemetry(measured_fps=80.0, fps_cv=0.40)
    d = decide(t, CaptureControls(downscale=4, target_fps=60.0), CFG)
    assert "recover_fps" in d.reason  # not sharpen


# ---- bounds ----

def test_downscale_clamped_to_bounds():
    t = CaptureTelemetry(measured_fps=80.0, fps_cv=0.05)
    d = decide(t, CaptureControls(downscale=2, target_fps=60.0), CFG)
    assert not d.changed  # already at min downscale -> can't sharpen further


# ---- governor: cooldown + EMA + no oscillation ----

def test_governor_cooldown_prevents_back_to_back_changes():
    g = AdaptiveCaptureGovernor(CaptureControls(downscale=4, target_fps=60.0),
                                GovernorConfig(cooldown_frames=3, ema_alpha=1.0))
    d1 = g.observe(_ts(20.0))            # low fps -> change
    assert d1.changed and g.controls.downscale == 5
    d2 = g.observe(_ts(20.0))            # cooldown -> no change
    assert not d2.changed and d2.reason == "cooldown"
    assert g.controls.downscale == 5


def test_governor_no_oscillation_on_steady_stream():
    g = AdaptiveCaptureGovernor(CaptureControls(downscale=4, target_fps=60.0),
                                GovernorConfig(ema_alpha=1.0))
    changes = 0
    for _ in range(20):
        d = g.observe(_ts(62.0, n=20), coupling_lag_ms=120.0, grid_samples=300)
        changes += int(d.changed)
    assert changes == 0  # a steady, in-regime stream never thrashes the controls


def test_governor_telemetry_summary_shape():
    g = AdaptiveCaptureGovernor(CaptureControls(downscale=4, target_fps=60.0),
                                GovernorConfig(cooldown_frames=0, ema_alpha=1.0))
    g.observe(_ts(20.0))
    s = g.telemetry_summary()
    assert s["observations"] == 1 and s["changes"] == 1
    assert s["final_controls"]["downscale"] == 5
    assert "recover_fps:downscale_up" in s["reasons"]
