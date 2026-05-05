"""Phase 241-APOP: Active Play Occupancy Proof.

Controller-native gameplay occupancy classifier.  It is intentionally pure and
side-effect free so the validator, session-boundary agent, and tests can run it
without touching PoAC serialization or hardware transport state.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any


ACTIVE_MATCH_PLAY = "ACTIVE_MATCH_PLAY"
COMPETITIVE_CONTROL = "COMPETITIVE_CONTROL"
MATCH_TRANSITION = "MATCH_TRANSITION"
NON_COMPETITIVE_MENU = "NON_COMPETITIVE_MENU"
UNKNOWN_LOW_EVIDENCE = "UNKNOWN_LOW_EVIDENCE"

APOP_STATES = frozenset({
    ACTIVE_MATCH_PLAY,
    COMPETITIVE_CONTROL,
    MATCH_TRANSITION,
    NON_COMPETITIVE_MENU,
    UNKNOWN_LOW_EVIDENCE,
})

APOP_COMPETITIVE_STATES = frozenset({ACTIVE_MATCH_PLAY, COMPETITIVE_CONTROL})
APOP_STRICT_ELIGIBLE_STATES = frozenset({
    ACTIVE_MATCH_PLAY,
    COMPETITIVE_CONTROL,
    MATCH_TRANSITION,
})

GATE_MODE_SHADOW = "shadow"
GATE_MODE_HYBRID = "hybrid"
GATE_MODE_STRICT = "strict"
APOP_GATE_MODES = frozenset({GATE_MODE_SHADOW, GATE_MODE_HYBRID, GATE_MODE_STRICT})

_BUTTON_BITS = {
    "cross": 0,
    "circle": 1,
    "square": 2,
    "triangle": 3,
    "l1": 4,
    "r1": 5,
    "dpad_up": 8,
    "dpad_down": 9,
    "dpad_left": 10,
    "dpad_right": 11,
    "share": 12,
    "options": 13,
}

_BUTTON_NAMES = (
    "cross",
    "circle",
    "square",
    "triangle",
    "l1",
    "r1",
    "dpad",
    "options",
    "share",
    "touch",
)


@dataclass(frozen=True)
class ActivePlayOccupancyResult:
    """Classifier output stored as the Phase 241 shadow/hybrid gate artifact."""

    state: str
    score: float
    confidence: float
    evidence: dict[str, Any]

    def evidence_json(self) -> str:
        return json.dumps(self.evidence, sort_keys=True, separators=(",", ":"))


def normalize_active_play_gate_mode(mode: str | None) -> str:
    """Return a safe APOP gate mode, defaulting to shadow on invalid input."""
    value = (mode or GATE_MODE_SHADOW).strip().lower()
    return value if value in APOP_GATE_MODES else GATE_MODE_SHADOW


def active_play_gate_allows(
    state: str | None,
    confidence: float | None,
    legacy_gameplay_context: str | None,
    gate_mode: str | None,
) -> bool:
    """Resolve APOP + legacy GAD into the GIC gameplay eligibility decision."""
    mode = normalize_active_play_gate_mode(gate_mode)
    legacy_ok = legacy_gameplay_context != "MENU_DETECTED"
    state = state or UNKNOWN_LOW_EVIDENCE
    conf = _clamp(_safe_float(confidence, 0.0))

    if mode == GATE_MODE_SHADOW:
        return legacy_ok
    if mode == GATE_MODE_HYBRID:
        if state in APOP_COMPETITIVE_STATES:
            return True
        if state == NON_COMPETITIVE_MENU and conf >= 0.60:
            return False
        return legacy_ok
    return state in APOP_STRICT_ELIGIBLE_STATES


def classify_active_play_occupancy(
    records: list[dict[str, Any]] | None,
    checkpoints: list[dict[str, Any]] | None,
) -> ActivePlayOccupancyResult:
    """Classify whether recent controller evidence shows competitive occupancy."""
    records = records or []
    frames = _flatten_frames(checkpoints or [])

    if len(records) < 5 and len(frames) < 10:
        return ActivePlayOccupancyResult(
            state=UNKNOWN_LOW_EVIDENCE,
            score=0.0,
            confidence=0.20,
            evidence={
                "reason": "insufficient_records_and_frames",
                "n_records": len(records),
                "n_frames": len(frames),
            },
        )

    frame_metrics = _score_frames(frames)
    record_metrics = _score_records(records)
    physiology_score = record_metrics["physiology_score"]

    score = _clamp(
        0.35 * frame_metrics["stick_score"]
        + 0.20 * frame_metrics["button_score"]
        + 0.20 * frame_metrics["trigger_score"]
        + 0.15 * frame_metrics["imu_score"]
        + 0.10 * physiology_score
    )
    history_score = _clamp(
        0.45 * record_metrics["trigger_active_fraction"]
        + 0.30 * physiology_score
        + 0.25 * max(
            frame_metrics["stick_score"],
            frame_metrics["button_score"],
            frame_metrics["trigger_score"],
        )
    )

    state = UNKNOWN_LOW_EVIDENCE
    if (
        score >= 0.42
        and frame_metrics["stick_score"] >= 0.35
        and (
            frame_metrics["imu_score"] >= 0.08
            or frame_metrics["trigger_score"] >= 0.35
            or frame_metrics["button_score"] >= 0.25
        )
    ):
        state = ACTIVE_MATCH_PLAY
    elif score >= 0.22 and (
        frame_metrics["button_score"] >= 0.20
        or frame_metrics["trigger_score"] >= 0.35
        or frame_metrics["stick_score"] >= 0.25
    ):
        state = COMPETITIVE_CONTROL
    elif history_score >= 0.45 and score >= 0.14:
        state = MATCH_TRANSITION
    elif len(frames) >= 10 and len(records) >= 5 and score < 0.18 and history_score < 0.25:
        state = NON_COMPETITIVE_MENU

    confidence = _confidence_for_state(state, score, history_score, len(records), len(frames))
    evidence = {
        "n_records": len(records),
        "n_frames": len(frames),
        "score": round(score, 4),
        "history_score": round(history_score, 4),
        **{k: round(v, 4) for k, v in frame_metrics.items()},
        **{k: round(v, 4) for k, v in record_metrics.items()},
    }
    return ActivePlayOccupancyResult(
        state=state,
        score=round(score, 4),
        confidence=round(confidence, 4),
        evidence=evidence,
    )


def _flatten_frames(checkpoints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for checkpoint in checkpoints:
        chunk = checkpoint.get("frames", [])
        if isinstance(chunk, str):
            try:
                chunk = json.loads(chunk)
            except Exception:
                chunk = []
        if isinstance(chunk, list):
            frames.extend(f for f in chunk if isinstance(f, dict))
    return frames


def _score_records(records: list[dict[str, Any]]) -> dict[str, float]:
    n = len(records)
    if n <= 0:
        return {
            "record_trigger_active_fraction": 0.0,
            "physiology_score": 0.50,
            "humanity_mean": 0.50,
            "rhythm_humanity_mean": 0.50,
        }
    trigger_fraction = sum(
        1 for r in records if int(r.get("trigger_active", 0) or 0) == 1
    ) / n
    humanity_values = [
        _safe_float(r.get("pitl_humanity_prob"), 0.50)
        for r in records
        if r.get("pitl_humanity_prob") is not None
    ]
    rhythm_values = [
        _safe_float(r.get("pitl_l5_rhythm_humanity"), 0.50)
        for r in records
        if r.get("pitl_l5_rhythm_humanity") is not None
    ]
    humanity_mean = sum(humanity_values) / len(humanity_values) if humanity_values else 0.50
    rhythm_mean = sum(rhythm_values) / len(rhythm_values) if rhythm_values else 0.50
    physiology_score = _clamp(0.70 * humanity_mean + 0.30 * rhythm_mean)
    return {
        "record_trigger_active_fraction": trigger_fraction,
        "trigger_active_fraction": trigger_fraction,
        "physiology_score": physiology_score,
        "humanity_mean": humanity_mean,
        "rhythm_humanity_mean": rhythm_mean,
    }


def _score_frames(frames: list[dict[str, Any]]) -> dict[str, float]:
    n = len(frames)
    if n <= 0:
        return {
            "stick_score": 0.0,
            "button_score": 0.0,
            "trigger_score": 0.0,
            "imu_score": 0.0,
            "stick_active_fraction": 0.0,
            "button_active_fraction": 0.0,
            "trigger_hold_fraction": 0.0,
            "imu_energy": 0.0,
        }

    stick_mags: list[float] = []
    stick_angles: list[float] = []
    button_rows: list[tuple[int, ...]] = []
    trigger_values: list[float] = []
    gyro_values: list[float] = []
    accel_values: list[float] = []

    for frame in frames:
        lx = _axis_norm(frame.get("left_stick_x"))
        ly = _axis_norm(frame.get("left_stick_y"))
        rx = _axis_norm(frame.get("right_stick_x"))
        ry = _axis_norm(frame.get("right_stick_y"))
        left_mag = math.sqrt(lx * lx + ly * ly)
        right_mag = math.sqrt(rx * rx + ry * ry)
        mag = max(left_mag, right_mag)
        stick_mags.append(mag)
        if left_mag > 0.10:
            stick_angles.append(math.atan2(ly, lx))

        button_rows.append(tuple(_button_flag(frame, name) for name in _BUTTON_NAMES))
        trigger_values.append(max(
            _trigger_norm(frame.get("l2_trigger")),
            _trigger_norm(frame.get("r2_trigger")),
        ))
        gx = _safe_float(frame.get("gyro_x"), 0.0)
        gy = _safe_float(frame.get("gyro_y"), 0.0)
        gz = _safe_float(frame.get("gyro_z"), 0.0)
        gyro_values.append(math.sqrt(gx * gx + gy * gy + gz * gz))
        ax = _safe_float(frame.get("accel_x"), 0.0)
        ay = _safe_float(frame.get("accel_y"), 0.0)
        az = _safe_float(frame.get("accel_z"), 0.0)
        accel_values.append(math.sqrt(ax * ax + ay * ay + az * az))

    stick_active_fraction = sum(1 for v in stick_mags if v > 0.15) / n
    stick_mean = sum(stick_mags) / n
    angle_change_rate = _angle_change_rate(stick_angles)
    stick_score = _clamp(0.70 * stick_active_fraction + 0.20 * stick_mean + 0.10 * angle_change_rate)

    button_active_fraction = sum(1 for row in button_rows if any(row)) / n
    button_transition_rate = _row_transition_rate(button_rows)
    button_score = _clamp(0.70 * button_active_fraction + 0.30 * button_transition_rate)

    trigger_hold_fraction = sum(1 for v in trigger_values if v > 0.20) / n
    trigger_mean = sum(trigger_values) / n
    trigger_score = _clamp(0.72 * trigger_hold_fraction + 0.28 * trigger_mean)

    gyro_mean = sum(gyro_values) / n
    accel_var = _variance(accel_values)
    imu_score = _clamp((gyro_mean / 6.0) + min(1.0, accel_var * 40.0))

    return {
        "stick_score": stick_score,
        "button_score": button_score,
        "trigger_score": trigger_score,
        "imu_score": imu_score,
        "stick_active_fraction": stick_active_fraction,
        "button_active_fraction": button_active_fraction,
        "trigger_hold_fraction": trigger_hold_fraction,
        "trigger_mean": trigger_mean,
        "imu_energy": gyro_mean,
        "accel_mag_variance": accel_var,
        "button_transition_rate": button_transition_rate,
        "stick_angle_change_rate": angle_change_rate,
    }


def _button_flag(frame: dict[str, Any], name: str) -> int:
    if name == "dpad":
        keys = ("buttons_dpad_up", "buttons_dpad_down", "buttons_dpad_left", "buttons_dpad_right")
        if any(int(bool(frame.get(k, 0))) for k in keys):
            return 1
        raw = _safe_int(frame.get("buttons_raw", frame.get("buttons")), 0)
        return int(any((raw >> bit) & 1 for bit in (8, 9, 10, 11)))
    if name == "touch":
        return int(bool(frame.get("touch_active", False) or frame.get("buttons_touch", 0)))
    key = f"buttons_{name}"
    if key in frame:
        return int(bool(frame.get(key)))
    raw = _safe_int(frame.get("buttons_raw", frame.get("buttons")), 0)
    bit = _BUTTON_BITS.get(name)
    return int(bool(raw and bit is not None and ((raw >> bit) & 1)))


def _axis_norm(value: Any) -> float:
    v = _safe_float(value, 0.0)
    if 0.0 <= v <= 255.0:
        return _clamp((v - 128.0) / 128.0, -1.0, 1.0)
    if abs(v) <= 512.0:
        return _clamp(v / 128.0, -1.0, 1.0)
    return _clamp(v / 32768.0, -1.0, 1.0)


def _trigger_norm(value: Any) -> float:
    v = max(0.0, _safe_float(value, 0.0))
    if v <= 1.0:
        return _clamp(v)
    if v <= 255.0:
        return _clamp(v / 255.0)
    return _clamp(v / 1023.0)


def _angle_change_rate(angles: list[float]) -> float:
    if len(angles) < 2:
        return 0.0
    changes = 0
    prev = angles[0]
    for angle in angles[1:]:
        delta = abs(math.atan2(math.sin(angle - prev), math.cos(angle - prev)))
        if delta > 0.35:
            changes += 1
        prev = angle
    return _clamp(changes / max(1, len(angles) - 1))


def _row_transition_rate(rows: list[tuple[int, ...]]) -> float:
    if len(rows) < 2:
        return 0.0
    transitions = sum(1 for prev, cur in zip(rows, rows[1:]) if prev != cur)
    return _clamp(transitions / (len(rows) - 1))


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _confidence_for_state(state: str, score: float, history: float, n_records: int, n_frames: int) -> float:
    evidence_strength = _clamp(0.45 * min(1.0, n_frames / 60.0) + 0.55 * min(1.0, n_records / 100.0))
    if state == UNKNOWN_LOW_EVIDENCE:
        return 0.20 + 0.20 * evidence_strength
    if state == NON_COMPETITIVE_MENU:
        return _clamp(0.55 + (0.22 - min(score, 0.22)) + 0.20 * evidence_strength)
    return _clamp(0.45 + 0.38 * max(score, history) + 0.17 * evidence_strength)


def _safe_float(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))
