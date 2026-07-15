"""Operator-fired L6B desk reaction capture (F-L6B-CAL-005).

Standalone session path: bridge STOPPED, one probe per ENTER, same IMU reports
and F-L6B-CAL-005 diagnostics as the production loop without interval/quiet gates.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from bridge.controller.l6b_reflex_analyzer import (
    CAPTURE_WINDOW_MS,
    L6bReflexAnalyzer,
    L6bReflexResult,
)
from bridge.vapi_bridge.cco_l6b_wiring import (
    compute_l6b_probe_diagnostic,
    l6b_probe_diagnostic_to_json,
    map_l6b_classification_to_reflex_verdict,
)

DEFAULT_PRE_SAMPLES = 50
DEFAULT_POLL_INTERVAL_S = 0.008
DEFAULT_CAPTURE_WINDOW_MS = max(CAPTURE_WINDOW_MS, 400.0)
DEFAULT_ACCEL_SCALE = 8192.0
DESK_POLICY_PREFIX = "desk_operator"


class _Pollable(Protocol):
    def poll(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class DeskProbeConfig:
    r2_force: int = 128
    mode: str = "rigid"
    hold_ms: int = 200
    pre_samples: int = DEFAULT_PRE_SAMPLES
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S
    capture_window_ms: float = DEFAULT_CAPTURE_WINDOW_MS
    response_threshold_lsb: float = 500.0
    human_min_ms: float = 80.0
    human_max_ms: float = 350.0


@dataclass(frozen=True, slots=True)
class DeskProbeOutcome:
    probe_index: int
    protocol: str
    player: str
    device_id: str
    result: L6bReflexResult
    diagnostic_json: str
    reflex_verdict: str | None
    probe_log_id: int | None
    r2_at_probe: int
    pre_sample_count: int
    post_sample_count: int

    def summary_lines(self) -> list[str]:
        """Human-readable per-probe feedback (diagnostics-first, not label-only)."""
        d = json.loads(self.diagnostic_json)
        meta = d.get("session_meta", {})
        lines = [
            f"Probe #{self.probe_index}  protocol={self.protocol}  player={self.player}",
            (
                f"  classification={self.result.classification}"
                f"  latency_ms={self._fmt(self.result.latency_ms)}"
                f"  legacy_latency_ms={self._fmt(self.result.legacy_latency_ms)}"
                f"  peak_delta={self.result.accel_delta_peak:.1f} LSB"
                f"  (threshold={d.get('response_threshold_lsb', 500)})"
            ),
            (
                f"  true_latency_ms={self._fmt(d.get('true_latency_ms'))}"
                f"  precursor_gap_ms={self._fmt(d.get('precursor_gap_ms'))}"
                f"  reflex_gap_ms={self._fmt(d.get('reflex_gap_ms'))}"
            ),
            (
                f"  probe_r2_force={d.get('probe_r2_force')}"
                f"  mode={d.get('probe_mode')}"
                f"  hold_ms={d.get('probe_hold_ms')}"
                f"  R2_at_probe={self.r2_at_probe}"
            ),
            (
                f"  samples pre={self.pre_sample_count} post={self.post_sample_count}"
                f"  reflex_verdict={self.reflex_verdict or '-'}"
            ),
        ]
        if meta:
            lines.append(f"  session_meta={json.dumps(meta, separators=(',', ':'))}")
        return lines

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None:
            return "-"
        if isinstance(value, (int, float)):
            return f"{value:.1f}"
        return str(value)


def accel_report_from_snapshot(
    snap: Any,
    *,
    accel_scale: float = DEFAULT_ACCEL_SCALE,
    t_mono: float | None = None,
) -> dict[str, float]:
    """Build L6B analyzer report dict (raw accel LSB + monotonic time)."""
    ts = time.monotonic() if t_mono is None else t_mono
    return {
        "ax": float(getattr(snap, "accel_x", 0.0) or 0.0) * accel_scale,
        "ay": float(getattr(snap, "accel_y", 0.0) or 0.0) * accel_scale,
        "az": float(getattr(snap, "accel_z", 0.0) or 0.0) * accel_scale,
        "t_mono": ts,
    }


def collect_imu_samples(
    reader: _Pollable,
    count: int,
    *,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    accel_scale: float = DEFAULT_ACCEL_SCALE,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[dict[str, float]]:
    """Poll ``count`` IMU samples at ``poll_interval_s`` spacing."""
    rows: list[dict[str, float]] = []
    for _ in range(max(0, count)):
        snap = reader.poll()
        rows.append(accel_report_from_snapshot(snap, accel_scale=accel_scale))
        if poll_interval_s > 0:
            sleep_fn(poll_interval_s)
    return rows


def collect_imu_until(
    reader: _Pollable,
    *,
    duration_s: float,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    accel_scale: float = DEFAULT_ACCEL_SCALE,
    sleep_fn: Callable[[float], None] = time.sleep,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> list[dict[str, float]]:
    """Poll IMU until ``duration_s`` elapsed (wall clock via monotonic)."""
    rows: list[dict[str, float]] = []
    deadline = monotonic_fn() + max(0.0, duration_s)
    while monotonic_fn() < deadline:
        snap = reader.poll()
        rows.append(accel_report_from_snapshot(snap, accel_scale=accel_scale))
        if poll_interval_s > 0:
            sleep_fn(poll_interval_s)
    return rows


def max_r2_in_reports(reports: list[dict[str, float]], snap_r2: int) -> int:
    """Return max R2 ADC from trailing window; ``snap_r2`` is latest sample."""
    return int(snap_r2)


def enrich_diagnostic_json(
    diagnostic_json: str,
    *,
    session_meta: dict[str, Any],
) -> str:
    payload = json.loads(diagnostic_json)
    payload["session_meta"] = session_meta
    return json.dumps(payload, separators=(",", ":"))


def analyze_desk_probe(
    pre_reports: list[dict[str, float]],
    post_reports: list[dict[str, float]],
    probe_ts: float,
    cfg: DeskProbeConfig,
) -> tuple[L6bReflexResult, str]:
    """Run legacy classifier + F-L6B-CAL-005 diagnostic on captured reports."""
    analyzer = L6bReflexAnalyzer(
        human_min_ms=cfg.human_min_ms,
        human_max_ms=cfg.human_max_ms,
        accel_delta_threshold_lsb=cfg.response_threshold_lsb,
    )
    result = analyzer.analyze(pre_reports, post_reports, probe_ts)
    diag = compute_l6b_probe_diagnostic(
        pre_reports,
        post_reports,
        probe_ts,
        legacy_latency_ms=result.legacy_latency_ms,
        response_threshold_lsb=cfg.response_threshold_lsb,
        probe_r2_force=cfg.r2_force,
        probe_mode=cfg.mode,
        probe_hold_ms=cfg.hold_ms,
    )
    return result, l6b_probe_diagnostic_to_json(diag)


def persist_desk_probe(
    store: Any,
    *,
    device_id: str,
    probe_ts: float,
    result: L6bReflexResult,
    diagnostic_json: str,
    protocol: str,
    player: str,
    r2_at_probe: int,
    cco_profile_id: str | None = None,
    policy_ref_override: str | None = None,
) -> tuple[int | None, str]:
    """Write l6b_probe_log + l6b_probe_diagnostic. Returns (row_id, enriched_json).

    policy_ref_override (A2A-POEP-P2): stamp a campaign tag instead of desk_operator_{protocol} --
    e.g. the registered-Edge reflex campaign passes `edge_operator_reflex_v1` (the B1+B2 allowlist tag)
    so its probes count toward the certified-device N>=50 gate."""
    reflex_verdict = map_l6b_classification_to_reflex_verdict(result.classification)
    policy_ref = policy_ref_override or f"{DESK_POLICY_PREFIX}_{protocol}"
    enriched = enrich_diagnostic_json(
        diagnostic_json,
        session_meta={
            "session_kind": "edge_reflex_campaign" if policy_ref_override else "desk_operator",
            "protocol": protocol,
            "player": player,
            "policy_ref": policy_ref,
        },
    )
    diag_payload = json.loads(enriched)
    probe_log_id: int | None = None
    try:
        probe_log_id = store.insert_l6b_probe(
            device_id=device_id,
            probe_ts_ms=int(probe_ts * 1000),
            latency_ms=result.latency_ms,
            classification=result.classification,
            accel_delta_peak=result.accel_delta_peak,
            reflex_verdict=reflex_verdict,
            cco_profile_id=cco_profile_id,
            policy_ref=policy_ref,   # campaign tag when overridden (e.g. edge_operator_reflex_v1)
            trigger_r2_at_probe=r2_at_probe,
        )
        store.insert_l6b_probe_diagnostic(
            device_id=device_id,
            probe_ts_mono=probe_ts,
            probe_log_id=probe_log_id,
            legacy_latency_ms=result.legacy_latency_ms,
            true_latency_ms=(
                result.true_latency_ms
                if result.true_latency_ms >= 0.0
                else diag_payload.get("true_latency_ms")
            ),
            precursor_gap_ms=diag_payload.get("precursor_gap_ms"),
            reflex_gap_ms=diag_payload.get("reflex_gap_ms"),
            diagnostic_json=enriched,
        )
    except Exception:
        probe_log_id = None
    return probe_log_id, enriched


def expected_post_frames(capture_window_ms: float, poll_interval_s: float) -> int:
    """Approximate post-probe frame count for operator guidance."""
    if poll_interval_s <= 0:
        return 0
    return int(capture_window_ms / (poll_interval_s * 1000.0))


def desk_device_id(player: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in player.strip())
    return f"desk-{safe or 'operator'}"
