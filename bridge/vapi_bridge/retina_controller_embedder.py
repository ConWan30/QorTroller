"""QorTroller × Trio-Retina — controller HID → WorldState + events (Phase A).

Pure-function encoder: maps DualSense-style HID windows into trio-retina's
``WorldState`` / ``Event`` schema without touching the FROZEN 228-byte PoAC wire
format. Network and I/O live in runners / bridge hooks only.

Domain tag for latent vectors (distinct from PoAC ``world_model_hash`` EWC field):
  ``qortroller-controller-v1``
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

import numpy as np

try:
    from retina import Event, WorldState
    from retina.export import to_jsonl
    from retina.worldstate import Entity, Vec
except ImportError:  # pragma: no cover — tests mock or skip when absent
    Event = None  # type: ignore[misc, assignment]
    WorldState = None  # type: ignore[misc, assignment]
    to_jsonl = None  # type: ignore[misc, assignment]
    Entity = None  # type: ignore[misc, assignment]
    Vec = None  # type: ignore[misc, assignment]

CONTROLLER_VEC_MODEL = "qortroller-controller-v1"
CONTROLLER_VEC_DIM = 16
DEFAULT_WINDOW = 120
DEFAULT_DYNAMICS_HORIZON = 5
TRAJECTORY_RESIDUAL_THRESHOLD = 0.35  # normalized stick units / step

# Custom event types (namespace in ``ext`` when not in retina.event/0.1 core vocab)
EVT_TRIGGER_ONSET = "controller.trigger.onset"
EVT_STICK_RADIAL_JUMP = "controller.stick.radial_jump"
EVT_TREMOR_ANOMALOUS = "controller.tremor.anomalous"
EVT_TRAJECTORY_ANOMALOUS = "controller.trajectory.anomalous"


class _SnapLike(Protocol):
    right_stick_x: int
    right_stick_y: int
    left_stick_x: int
    left_stick_y: int
    l2_trigger: int
    r2_trigger: int
    gyro_x: float
    gyro_y: float
    gyro_z: float
    accel_x: float
    accel_y: float
    accel_z: float


@dataclass(frozen=True, slots=True)
class DynamicsViolation:
    frame: int
    t: float
    axis: str
    predicted: float
    actual: float
    residual: float


@dataclass(slots=True)
class EmbedResult:
    world_state: Any
    events: list[Any] = field(default_factory=list)
    latent_vec: np.ndarray = field(default_factory=lambda: np.zeros(CONTROLLER_VEC_DIM))
    dynamics_violations: list[DynamicsViolation] = field(default_factory=list)

    @property
    def anomaly_count(self) -> int:
        return len(self.dynamics_violations) + sum(
            1 for e in self.events
            if getattr(e, "type", "") in (
                EVT_TREMOR_ANOMALOUS,
                EVT_TRAJECTORY_ANOMALOUS,
                EVT_STICK_RADIAL_JUMP,
            )
        )


def _g(obj: Mapping[str, Any] | _SnapLike, key: str, default: float | int = 0) -> float:
    if isinstance(obj, Mapping):
        return float(obj.get(key, default))
    return float(getattr(obj, key, default))


def snap_to_feature_vector(snap: Mapping[str, Any] | _SnapLike) -> np.ndarray:
    """16-D normalized controller state for the Retina latent channel."""
    rx = _g(snap, "right_stick_x") / 255.0
    ry = _g(snap, "right_stick_y") / 255.0
    lx = _g(snap, "left_stick_x") / 255.0
    ly = _g(snap, "left_stick_y") / 255.0
    l2 = _g(snap, "l2_trigger") / 255.0
    r2 = _g(snap, "r2_trigger") / 255.0
    gx, gy, gz = _g(snap, "gyro_x"), _g(snap, "gyro_y"), _g(snap, "gyro_z")
    ax, ay, az = _g(snap, "accel_x"), _g(snap, "accel_y"), _g(snap, "accel_z")
    gyro_mag = math.sqrt(gx * gx + gy * gy + gz * gz)
    accel_mag = math.sqrt(ax * ax + ay * ay + az * az)
    stick_radial = math.sqrt(rx * rx + ry * ry)
    return np.array(
        [
            rx, ry, lx, ly, l2, r2,
            gx, gy, gz, ax, ay, az,
            gyro_mag, accel_mag, stick_radial,
            1.0 if l2 > 0.05 or r2 > 0.05 else 0.0,
        ],
        dtype=np.float64,
    )


def _stick_delta(prev: Mapping[str, Any] | _SnapLike, curr: Mapping[str, Any] | _SnapLike) -> float:
    prx, pry = _g(prev, "right_stick_x"), _g(prev, "right_stick_y")
    crx, cry = _g(curr, "right_stick_x"), _g(curr, "right_stick_y")
    return math.hypot(crx - prx, cry - pry) / 255.0


def _trigger_onset(prev: Mapping[str, Any] | _SnapLike, curr: Mapping[str, Any] | _SnapLike, side: str) -> bool:
    key = f"{side}_trigger"
    return _g(prev, key) < 10 and _g(curr, key) >= 10


def _tremor_proxy(snaps: Sequence[Mapping[str, Any] | _SnapLike]) -> float:
    if len(snaps) < 3:
        return 0.0
    mags = [
        math.sqrt(_g(s, "accel_x") ** 2 + _g(s, "accel_y") ** 2 + _g(s, "accel_z") ** 2)
        for s in snaps
    ]
    return float(np.var(mags))


def _predict_linear(series: np.ndarray, horizon: int) -> float:
    """One-step linear extrapolation from the last ``horizon`` samples."""
    if len(series) < 2:
        return float(series[-1]) if len(series) else 0.0
    tail = series[-horizon:] if len(series) >= horizon else series
    if len(tail) < 2:
        return float(tail[-1])
    x = np.arange(len(tail), dtype=np.float64)
    slope, intercept = np.polyfit(x, tail, 1)
    return float(slope * len(tail) + intercept)


def _check_dynamics(
    snaps: Sequence[Mapping[str, Any] | _SnapLike],
    frame_idx: int,
    t: float,
    horizon: int = DEFAULT_DYNAMICS_HORIZON,
) -> list[DynamicsViolation]:
    if len(snaps) < horizon + 1:
        return []
    rx = np.array([_g(s, "right_stick_x") / 255.0 for s in snaps], dtype=np.float64)
    ry = np.array([_g(s, "right_stick_y") / 255.0 for s in snaps], dtype=np.float64)
    out: list[DynamicsViolation] = []
    for axis, series in (("rx", rx), ("ry", ry)):
        pred = _predict_linear(series[:-1], horizon)
        actual = float(series[-1])
        residual = abs(actual - pred)
        if residual > TRAJECTORY_RESIDUAL_THRESHOLD:
            out.append(
                DynamicsViolation(
                    frame=frame_idx,
                    t=t,
                    axis=axis,
                    predicted=pred,
                    actual=actual,
                    residual=residual,
                )
            )
    return out


def _make_event(
    event_type: str,
    t: float,
    source_id: str,
    frame: int,
    *,
    label: str | None = None,
    conf: float | None = None,
    ext: dict[str, Any] | None = None,
    vec_values: list[float] | None = None,
) -> Any:
    if Event is None:
        raise RuntimeError("trio-retina is not installed (pip install trio-retina)")
    kw: dict[str, Any] = dict(type=event_type, t=t, src=source_id, frame=frame)
    if label is not None:
        kw["label"] = label
    if conf is not None:
        kw["conf"] = conf
    if ext:
        kw["ext"] = ext
    if vec_values is not None:
        kw["vec"] = Vec(model=CONTROLLER_VEC_MODEL, dim=len(vec_values), values=vec_values)
    return Event(**kw)


def embed_controller_window(
    snaps: Sequence[Mapping[str, Any] | _SnapLike],
    *,
    source_id: str = "qortroller_hid",
    start_t: float = 0.0,
    hz: float = 1000.0,
    dynamics_horizon: int = DEFAULT_DYNAMICS_HORIZON,
    tremor_var_threshold: float = 0.02,
    radial_jump_threshold: float = 0.25,
) -> EmbedResult:
    """Encode one HID window → WorldState + symbolic events + dynamics violations."""
    if WorldState is None or Entity is None or Vec is None:
        raise RuntimeError("trio-retina is not installed (pip install trio-retina)")
    if not snaps:
        ws = WorldState(src=source_id, t=start_t)
        return EmbedResult(world_state=ws, latent_vec=np.zeros(CONTROLLER_VEC_DIM))

    events: list[Any] = []
    violations: list[DynamicsViolation] = []
    dt = 1.0 / hz

    for i in range(1, len(snaps)):
        t = start_t + i * dt
        prev, curr = snaps[i - 1], snaps[i]
        if _trigger_onset(prev, curr, "l2"):
            events.append(_make_event(EVT_TRIGGER_ONSET, t, source_id, i, label="l2", conf=0.9))
        if _trigger_onset(prev, curr, "r2"):
            events.append(_make_event(EVT_TRIGGER_ONSET, t, source_id, i, label="r2", conf=0.9))
        delta = _stick_delta(prev, curr)
        if delta >= radial_jump_threshold:
            events.append(
                _make_event(
                    EVT_STICK_RADIAL_JUMP,
                    t,
                    source_id,
                    i,
                    conf=min(1.0, delta),
                    ext={"delta_norm": round(delta, 4)},
                )
            )
        if i >= dynamics_horizon:
            frame_violations = _check_dynamics(snaps[: i + 1], i, t, dynamics_horizon)
            for v in frame_violations:
                if not any(
                    e.type == EVT_TRAJECTORY_ANOMALOUS
                    and e.frame == v.frame
                    and (e.ext or {}).get("axis") == v.axis
                    for e in events
                ):
                    violations.append(v)
                    events.append(
                        _make_event(
                            EVT_TRAJECTORY_ANOMALOUS,
                            v.t,
                            source_id,
                            v.frame,
                            label=v.axis,
                            conf=min(1.0, v.residual / TRAJECTORY_RESIDUAL_THRESHOLD),
                            ext={
                                "axis": v.axis,
                                "predicted": round(v.predicted, 4),
                                "actual": round(v.actual, 4),
                                "residual": round(v.residual, 4),
                            },
                        )
                    )

    last_t = start_t + (len(snaps) - 1) * dt
    latent = snap_to_feature_vector(snaps[-1])
    tremor_var = _tremor_proxy(snaps)
    if tremor_var > tremor_var_threshold:
        events.append(
            _make_event(
                EVT_TREMOR_ANOMALOUS,
                last_t,
                source_id,
                len(snaps) - 1,
                conf=min(1.0, tremor_var / max(tremor_var_threshold, 1e-9)),
                ext={"accel_mag_var": round(tremor_var, 6)},
                vec_values=latent.tolist(),
            )
        )

    entity = Entity(
        id="controller_0",
        type="game_controller",
        conf=1.0,
        attrs={
            "right_stick_x": int(_g(snaps[-1], "right_stick_x")),
            "right_stick_y": int(_g(snaps[-1], "right_stick_y")),
            "l2": int(_g(snaps[-1], "l2_trigger")),
            "r2": int(_g(snaps[-1], "r2_trigger")),
        },
        vec=Vec(model=CONTROLLER_VEC_MODEL, dim=CONTROLLER_VEC_DIM, values=latent.tolist()),
    )
    ws = WorldState(
        src=source_id,
        t=last_t,
        entities=[entity],
        scene=Vec(model=CONTROLLER_VEC_MODEL, dim=CONTROLLER_VEC_DIM, values=latent.tolist()),
    )
    return EmbedResult(
        world_state=ws,
        events=events,
        latent_vec=latent,
        dynamics_violations=violations,
    )


def write_events_jsonl(events: Sequence[Any], path: str) -> int:
    if to_jsonl is None:
        raise RuntimeError("trio-retina is not installed")
    return int(to_jsonl(events, path))


def snaps_from_session_json(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Load HID-like dicts from a calibration ``hw_*.json`` session file."""
    out: list[dict[str, Any]] = []
    for report in data.get("reports", []):
        f = report.get("features", report)
        out.append(
            {
                "right_stick_x": int(f.get("right_stick_x", 128)),
                "right_stick_y": int(f.get("right_stick_y", 128)),
                "left_stick_x": int(f.get("left_stick_x", 128)),
                "left_stick_y": int(f.get("left_stick_y", 128)),
                "l2_trigger": int(f.get("l2_trigger", 0)),
                "r2_trigger": int(f.get("r2_trigger", 0)),
                "gyro_x": float(f.get("gyro_x", 0.0)),
                "gyro_y": float(f.get("gyro_y", 0.0)),
                "gyro_z": float(f.get("gyro_z", 0.0)),
                "accel_x": float(f.get("accel_x", 0.0)),
                "accel_y": float(f.get("accel_y", 0.0)),
                "accel_z": float(f.get("accel_z", 1.0)),
            }
        )
    return out


def synthetic_snaps(
    n: int = 200,
    *,
    aimbot_snap_at: int | None = None,
    macro_flat: bool = False,
) -> list[dict[str, Any]]:
    """Deterministic HID replay for tests when ``sessions/hw_*.json`` is absent."""
    snaps: list[dict[str, Any]] = []
    for i in range(n):
        if macro_flat:
            rx = 128
        elif aimbot_snap_at is not None and i == aimbot_snap_at:
            rx = 240
        else:
            rx = int(128 + 20 * math.sin(i * 0.08))
        snaps.append(
            {
                "right_stick_x": rx,
                "right_stick_y": 128,
                "left_stick_x": 128,
                "left_stick_y": 128,
                "l2_trigger": min(255, max(0, (i % 80) * 3)),
                "r2_trigger": 0,
                "gyro_x": 0.01 * math.sin(i * 0.1),
                "gyro_y": 0.01 * math.cos(i * 0.1),
                "gyro_z": 0.0,
                "accel_x": 0.001 * math.sin(i * 0.5),
                "accel_y": 0.001 * math.cos(i * 0.3),
                "accel_z": 1.0,
            }
        )
    return snaps
