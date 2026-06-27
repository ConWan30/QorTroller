"""Cycle-25 tether — TetherPulseGenerator decision logic (amplitude + duty cycle).

Pure unit test over the hardened decision path (`due()`) + amplitude clamping. No controller,
no HID: the actual setForce write + restore is `_emit_tether_pulse_hw` in dualshock_integration,
run OFF the event loop via asyncio.to_thread. due() is decision-only and records the pulse time.
"""
from __future__ import annotations

from vapi_bridge.tether_pulse_generator import TetherConfig, TetherPulseGenerator


def _gen(amp_max: int = 12, interval: float = 1.2, enabled: bool = True) -> TetherPulseGenerator:
    return TetherPulseGenerator(
        TetherConfig(enabled=enabled, amplitude_max=amp_max, min_interval_s=interval)
    )


def test_disabled_never_fires():
    g = _gen(enabled=False)
    g.feed_biomarker(200.0, 0.0)
    assert g.due(100.0) == 0


def test_no_recent_force_no_pulse():
    g = _gen()  # no feed_biomarker -> empty rhythm -> amp 0
    assert g.due(100.0) == 0


def test_fires_after_force_and_interval():
    g = _gen()
    g.feed_biomarker(200.0, 0.0)
    assert g.due(100.0) > 0  # now=100 well past last_pulse(0)+interval, with recent force


def test_duty_cycle_blocks_rapid_pulses():
    g = _gen(interval=1.2)
    g.feed_biomarker(200.0, 0.0)
    assert g.due(100.0) > 0    # fires, records last_pulse=100.0
    assert g.due(100.5) == 0   # 0.5s < 1.2s -> blocked by duty cycle
    g.feed_biomarker(200.0, 101.3)
    assert g.due(101.3) > 0    # 1.3s >= 1.2s -> fires again


def test_amplitude_clamped_to_max():
    g = _gen(amp_max=12)
    g.feed_biomarker(10000.0, 0.0)  # huge force
    assert g.due(100.0) == 12       # clamped to amplitude_max


def test_amplitude_floor_is_two():
    g = _gen(amp_max=12)
    g.feed_biomarker(5.0, 0.0)      # int(5*0.06)=0 -> floored to 2
    assert g.due(100.0) == 2
