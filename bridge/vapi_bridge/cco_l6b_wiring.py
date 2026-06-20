"""CCO Phase B — L6B T0 wiring helpers.

Pure module: applicability gate, L6B→REFLEX_OBSERVED mapping, skip reasons.
Design: ``wiki/methodology/CCO_PHASE_B_DESIGN_v1.md``.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

REFLEX_OBSERVED = "REFLEX_OBSERVED"
T0_ENGINE_L6B = "L6B"
HUMAN_CLASSIFICATION = "HUMAN"
# Matches L6 active-challenge ``_r2_at_rest`` gate (dualshock_integration.py).
DEFAULT_L6B_R2_QUIET_THRESHOLD = 15
L6B_R2_QUIET_SAMPLE_TAIL = 10
# F-L6B-CAL-005: motor spin-up / actuation precursor (read-only diagnostic).
DEFAULT_L6B_PRECURSOR_THRESHOLD_LSB = 50.0
DEFAULT_L6B_RESPONSE_THRESHOLD_LSB = 500.0


class L6bSkipReason(str, Enum):
    NO_IMU = "NO_IMU"
    NO_ADAPTIVE_TRIGGER_PATH = "NO_ADAPTIVE_TRIGGER_PATH"
    NO_L6_DRIVER = "NO_L6_DRIVER"
    NO_DUALSENSE_HANDLE = "NO_DUALSENSE_HANDLE"
    T0_ENGINE_MISMATCH = "T0_ENGINE_MISMATCH"
    NO_CAPABILITY_REPORT = "NO_CAPABILITY_REPORT"


@dataclass(frozen=True, slots=True)
class L6bApplicability:
    applicable: bool
    skip_reason: L6bSkipReason | None = None


def check_l6b_applicability(
    report: Any | None,
    *,
    l6_driver_present: bool,
    dualsense_handle_present: bool,
) -> L6bApplicability:
    """Return whether the existing L6B stack may run for this session."""
    if report is None:
        return L6bApplicability(False, L6bSkipReason.NO_CAPABILITY_REPORT)
    if getattr(report, "t0_engine", None) != T0_ENGINE_L6B:
        return L6bApplicability(False, L6bSkipReason.T0_ENGINE_MISMATCH)
    caps = getattr(report, "capabilities", None) or {}
    if not caps.get("has_accelerometer", False):
        return L6bApplicability(False, L6bSkipReason.NO_IMU)
    if not caps.get("has_adaptive_triggers", False):
        return L6bApplicability(False, L6bSkipReason.NO_ADAPTIVE_TRIGGER_PATH)
    if not l6_driver_present:
        return L6bApplicability(False, L6bSkipReason.NO_L6_DRIVER)
    if not dualsense_handle_present:
        return L6bApplicability(False, L6bSkipReason.NO_DUALSENSE_HANDLE)
    return L6bApplicability(True)


def map_l6b_classification_to_reflex_verdict(classification: str) -> str | None:
    """Map L6b analyzer output to CCO telemetry verdict (non-gating)."""
    if classification == HUMAN_CLASSIFICATION:
        return REFLEX_OBSERVED
    return None


def format_l6b_skip_log(skip_reason: L6bSkipReason) -> str:
    return f"L6B_SKIPPED/{skip_reason.value}"


def evaluate_l6b_r2_quiet_gate(
    frames: list[Any],
    *,
    quiet_threshold: int = DEFAULT_L6B_R2_QUIET_THRESHOLD,
    sample_tail: int = L6B_R2_QUIET_SAMPLE_TAIL,
) -> tuple[bool, int | None]:
    """Return (quiet_ok, r2_at_probe) for L6B dispatch gating.

    ``quiet_ok`` is True when every R2 ADC sample in the trailing window is
    strictly below ``quiet_threshold`` (0–255). ``r2_at_probe`` is the max R2
    in that window for audit logging.
    """
    if not frames:
        return False, None
    samples = [
        int(getattr(f, "r2_trigger", 0) or 0)
        for f in frames[-sample_tail:]
    ]
    if not samples:
        return False, None
    r2_at_probe = max(samples)
    quiet_ok = all(r < quiet_threshold for r in samples)
    return quiet_ok, r2_at_probe


def _l6b_accel_mag(report: dict) -> float:
    ax = float(report.get("ax", 0.0))
    ay = float(report.get("ay", 0.0))
    az = float(report.get("az", 0.0))
    return math.sqrt(ax * ax + ay * ay + az * az)


def _l6b_accel_mean(reports: list[dict]) -> float:
    if not reports:
        return 0.0
    return sum(_l6b_accel_mag(r) for r in reports) / len(reports)


@dataclass(frozen=True, slots=True)
class L6bProbeDiagnostic:
    """Read-only F-L6B-CAL-005 latency instrumentation (does not affect classification)."""

    probe_ts: float
    pre_accel_mean: float
    legacy_index_latency_ms: float
    response_threshold_lsb: float
    precursor_threshold_lsb: float
    crossing_index: int | None
    crossing_t_mono: float | None
    true_latency_ms: float | None
    precursor_index: int | None
    precursor_t_mono: float | None
    precursor_gap_ms: float | None
    reflex_gap_ms: float | None
    probe_r2_force: int | None
    probe_mode: str | None
    probe_hold_ms: int | None
    samples: tuple[dict[str, float | int], ...]


def compute_l6b_probe_diagnostic(
    pre_reports: list[dict],
    post_reports: list[dict],
    probe_ts: float,
    *,
    legacy_latency_ms: float = -1.0,
    response_threshold_lsb: float = DEFAULT_L6B_RESPONSE_THRESHOLD_LSB,
    precursor_threshold_lsb: float = DEFAULT_L6B_PRECURSOR_THRESHOLD_LSB,
    probe_r2_force: int | None = None,
    probe_mode: str | None = None,
    probe_hold_ms: int | None = None,
) -> L6bProbeDiagnostic:
    """Ground-truth latency from monotonic sample times vs legacy index×8ms."""
    pre_mean = _l6b_accel_mean(pre_reports)
    sample_rows: list[dict[str, float | int]] = []
    precursor_index: int | None = None
    precursor_t_mono: float | None = None
    crossing_index: int | None = None
    crossing_t_mono: float | None = None

    for i, report in enumerate(post_reports):
        mag = _l6b_accel_mag(report)
        delta = abs(mag - pre_mean)
        t_mono = float(report.get("t_mono", 0.0) or 0.0)
        sample_rows.append(
            {"i": i, "t_mono": t_mono, "mag": mag, "delta": delta},
        )
        if precursor_index is None and delta > precursor_threshold_lsb:
            if t_mono > 0.0 and t_mono >= probe_ts:
                precursor_index = i
                precursor_t_mono = t_mono
        if crossing_index is None and delta >= response_threshold_lsb:
            if t_mono > 0.0 and t_mono >= probe_ts:
                crossing_index = i
                crossing_t_mono = t_mono

    true_latency_ms: float | None = None
    if crossing_t_mono is not None:
        true_latency_ms = (crossing_t_mono - probe_ts) * 1000.0

    precursor_gap_ms: float | None = None
    if precursor_t_mono is not None:
        precursor_gap_ms = (precursor_t_mono - probe_ts) * 1000.0

    reflex_gap_ms: float | None = None
    if precursor_t_mono is not None and crossing_t_mono is not None:
        reflex_gap_ms = (crossing_t_mono - precursor_t_mono) * 1000.0

    return L6bProbeDiagnostic(
        probe_ts=probe_ts,
        pre_accel_mean=pre_mean,
        legacy_index_latency_ms=legacy_latency_ms,
        response_threshold_lsb=response_threshold_lsb,
        precursor_threshold_lsb=precursor_threshold_lsb,
        crossing_index=crossing_index,
        crossing_t_mono=crossing_t_mono,
        true_latency_ms=true_latency_ms,
        precursor_index=precursor_index,
        precursor_t_mono=precursor_t_mono,
        precursor_gap_ms=precursor_gap_ms,
        reflex_gap_ms=reflex_gap_ms,
        probe_r2_force=probe_r2_force,
        probe_mode=probe_mode,
        probe_hold_ms=probe_hold_ms,
        samples=tuple(sample_rows),
    )


def l6b_probe_diagnostic_to_json(diag: L6bProbeDiagnostic) -> str:
    """Serialize diagnostic for SQLite / JSONL storage."""
    return json.dumps(
        {
            "probe_ts": diag.probe_ts,
            "pre_accel_mean": diag.pre_accel_mean,
            "legacy_index_latency_ms": diag.legacy_index_latency_ms,
            "response_threshold_lsb": diag.response_threshold_lsb,
            "precursor_threshold_lsb": diag.precursor_threshold_lsb,
            "crossing_index": diag.crossing_index,
            "crossing_t_mono": diag.crossing_t_mono,
            "true_latency_ms": diag.true_latency_ms,
            "precursor_index": diag.precursor_index,
            "precursor_t_mono": diag.precursor_t_mono,
            "precursor_gap_ms": diag.precursor_gap_ms,
            "reflex_gap_ms": diag.reflex_gap_ms,
            "probe_r2_force": diag.probe_r2_force,
            "probe_mode": diag.probe_mode,
            "probe_hold_ms": diag.probe_hold_ms,
            "samples": list(diag.samples),
        },
        separators=(",", ":"),
    )


def assemble_cco_session_status(
    *,
    capability_report: Any | None,
    l6b_calibration_progress: dict[str, Any] | None,
    l6b_enabled: bool,
    controller_connected: bool,
) -> dict[str, Any]:
    """Build read-only CCO block for GET /player/session-status (Phase B.2).

    Oracle fields come from ``CapabilityReport`` when resolve succeeds.
    Applicability uses the same predicate as ``dualshock_integration`` with
    HTTP-safe proxies: L6 driver assumed present when ``l6b_enabled``,
    DualSense handle inferred from ``controller_connected``.
    """
    prog = l6b_calibration_progress or {}
    calibration = {
        "probe_count": int(prog.get("probe_count", 0)),
        "target_n": int(prog.get("target_n", 50)),
        "gate_reached": bool(prog.get("gate_reached", False)),
        "reflex_verdict_distribution": dict(
            prog.get("reflex_verdict_distribution") or {},
        ),
    }

    reflex_verdict: str | None = None
    latest = prog.get("latest_probe") or {}
    if isinstance(latest, dict):
        rv = latest.get("reflex_verdict")
        if rv:
            reflex_verdict = str(rv)
        else:
            reflex_verdict = map_l6b_classification_to_reflex_verdict(
                str(latest.get("classification", "")),
            )

    out: dict[str, Any] = {
        "t0_engine": None,
        "presence_ceiling_candidate": None,
        "identity_class": None,
        "profile_id": None,
        "challenge_type_candidate": None,
        "policy_ref": None,
        "reflex_verdict": reflex_verdict,
        "l6b_enabled": l6b_enabled,
        "l6b_applicable": False,
        "l6b_skip": None,
        "calibration": calibration,
    }

    if capability_report is None:
        return out

    out["t0_engine"] = getattr(capability_report, "t0_engine", None)
    out["presence_ceiling_candidate"] = getattr(
        capability_report, "presence_ceiling_candidate", None,
    )
    out["identity_class"] = getattr(capability_report, "identity_class", None)
    out["profile_id"] = getattr(capability_report, "profile_id", None)
    out["challenge_type_candidate"] = getattr(
        capability_report, "challenge_type_candidate", None,
    )
    out["policy_ref"] = getattr(capability_report, "policy_ref", None)

    if l6b_enabled:
        app = check_l6b_applicability(
            capability_report,
            l6_driver_present=True,
            dualsense_handle_present=controller_connected,
        )
        out["l6b_applicable"] = app.applicable
        out["l6b_skip"] = app.skip_reason.value if app.skip_reason else None

    return out


def append_l6b_probe_diagnostic_jsonl(
    probe_log_id: int,
    device_id: str,
    diagnostic_json: str,
    *,
    logs_dir: Path | None = None,
) -> None:
    """Append one diagnostic line to logs/l6b_probe_diagnostic.jsonl (fail-open)."""
    try:
        base = logs_dir
        if base is None:
            base = Path(__file__).resolve().parents[2] / "logs"
        base.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "probe_log_id": probe_log_id,
                "device_id": device_id,
                "diagnostic": json.loads(diagnostic_json),
            },
            separators=(",", ":"),
        )
        with (base / "l6b_probe_diagnostic.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
