"""Phase 0.1 R1 — `_check_dynamics` bounded-window equivalence.

R1 changes the embed call site from the growing ``snaps[:i+1]`` to the bounded
``snaps[i-horizon:i+1]`` (O(window^2) -> O(window)). ``_check_dynamics`` only consumes the
last ``horizon+1`` samples (``_predict_linear`` uses ``series[:-1][-horizon:]``; actual is
``series[-1]``), so the bounded slice MUST yield byte-identical ``DynamicsViolation``s.

Pure unit test over ``_check_dynamics`` + ``_predict_linear`` — numpy only, no trio-retina,
no controller. Float equality is exact: both paths run identical np arithmetic on the same
last ``horizon+1`` samples.
"""
from __future__ import annotations

import pytest

from vapi_bridge.retina_controller_embedder import DEFAULT_DYNAMICS_HORIZON, _check_dynamics


def _snaps(n: int = 40) -> list[dict]:
    """Deterministic right-stick trajectory with large single-frame spikes that the linear
    predictor cannot anticipate -> residual far exceeds TRAJECTORY_RESIDUAL_THRESHOLD (0.35
    normalized), so the violation branch genuinely trips. Spikes are ~0.78 (rx) / ~0.55 (ry)
    of full scale, well above threshold."""
    out = []
    for k in range(n):
        rx = 230 if (k % 6 == 0) else 30   # flat 30 with periodic spike to 230 (delta ~0.78)
        ry = 200 if (k % 5 == 0) else 60   # flat 60 with periodic spike to 200 (delta ~0.55)
        out.append({
            "right_stick_x": rx, "right_stick_y": ry,
            "left_stick_x": 128, "left_stick_y": 128,
            "l2_trigger": 0, "r2_trigger": 0,
            "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
            "accel_x": 0.0, "accel_y": 0.0, "accel_z": 1.0,
        })
    return out


@pytest.mark.parametrize("h", [DEFAULT_DYNAMICS_HORIZON, 3, 8])
def test_bounded_slice_equals_full_slice(h):
    snaps = _snaps(40)
    compared = 0
    for i in range(h, len(snaps)):
        full = _check_dynamics(snaps[: i + 1], i, float(i), h)
        bounded = _check_dynamics(snaps[i - h : i + 1], i, float(i), h)
        assert full == bounded, f"mismatch at i={i}, h={h}: {full!r} != {bounded!r}"
        compared += 1
    assert compared > 0


def test_bounded_slice_actually_surfaces_violations():
    """Guard against a vacuous pass: the fixture must trip at least one violation, so the
    equivalence above is comparing non-empty results, not just two empty lists."""
    snaps = _snaps(40)
    h = DEFAULT_DYNAMICS_HORIZON
    total = sum(len(_check_dynamics(snaps[i - h : i + 1], i, float(i), h))
                for i in range(h, len(snaps)))
    assert total > 0
