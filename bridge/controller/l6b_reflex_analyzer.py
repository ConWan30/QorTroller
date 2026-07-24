"""
L6b Neuromuscular Reflex Analyzer — Phase 63.

Measures the involuntary grip-tightening reflex latency after a sub-perceptual
haptic pulse (profile L6B_PROBE, amplitude ~24%). Human neuromotor loop: 80–280ms
(desk/USB calibration may widen upper bound to 350ms via human_max_ms).
Bot interrupt response: 0–15ms.

Unlike L6ResponseAnalyzer (which measures voluntary R2 press onset), this analyzer
measures ACCEL-MAGNITUDE delta — the involuntary IMU response to a tactile stimulus.
The player does not need to consciously press anything.

Detection logic:
  - Compute pre_accel_mean from pre_reports (baseline grip stillness)
  - Scan post_reports for first frame where |accel_mag - pre_mean| >= threshold
  - When reports carry ``t_mono`` (F-L6B-CAL-005): classify on true wall-clock latency
    (crossing_t_mono - probe_ts), not index×8ms
  - Legacy fallback: latency_ms = frame_index * MS_PER_REPORT when t_mono absent
  - Classify by latency bucket: BOT [0, 15ms), INCONCLUSIVE [15, 80ms), HUMAN [80, max],
    INCONCLUSIVE above max, NO_RESPONSE if no impulse detected in window

Physical grounding:
  - Human spinal reflex arc (stretch reflex): ~80–120ms
  - Human supra-spinal (cortical) loop: ~120–280ms (desk: up to ~350ms observed)
  - Interrupt-driven software bot: <5ms (OS interrupt latency)
  - Hardware loop-back bot: ~1–15ms (USB polling jitter; reflex_gap ≈ 0)
  - Cannot be spoofed without physical hardware responding to the haptic stimulus
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Bridge _poll_frames uses dt_ms=8 (~125 Hz); each buffered frame ≈ 8 ms wall time (legacy).
MS_PER_REPORT: float = 8.0
# Capture window after probe delivery — 350ms captures full human reflex range + margin.
CAPTURE_WINDOW_MS: float = 350.0
# F-L6B-CAL-005 precursor threshold (motor spin-up / actuation coupling).
PRECURSOR_THRESHOLD_LSB: float = 50.0
# Sub-min latency with reflex_gap below this → mechanical coupling, not neuromotor HUMAN.
MECHANICAL_REFLEX_GAP_MAX_MS: float = 50.0


@dataclass
class L6bReflexResult:
    """Output of a single L6b probe analysis."""

    latency_ms: float
    """Canonical latency for storage: true_latency_ms when available, else legacy index×8."""

    accel_delta_peak: float
    """Max |accel_mag - pre_mean| observed in the capture window (LSB). 0.0 if no response."""

    classification: str
    """One of: 'HUMAN', 'BOT', 'INCONCLUSIVE', 'NO_RESPONSE'."""

    confidence: float
    """[0.0, 1.0] — scales with accel_delta_peak relative to threshold. 0.5 when no response."""

    probe_ts: float
    """time.monotonic() timestamp at probe delivery."""

    valid: bool
    """False when no accel impulse was detected above threshold in the capture window."""

    legacy_latency_ms: float = -1.0
    """index×MS_PER_REPORT latency (-1 if no crossing). Audit / regression compare."""

    true_latency_ms: float = -1.0
    """Wall-clock (t_mono - probe_ts)×1000 when t_mono present on crossing (-1 otherwise)."""

    reflex_gap_ms: float | None = None
    """crossing_t_mono - precursor_t_mono in ms; None when precursor not detected."""

    crossing_device_ts: float = -1.0
    """F-RIG27-8 (ADDITIVE): the DEVICE sensor timestamp of the crossing frame as RAW uint32 ticks
    (@~3MHz), when reports carry `device_ts`. -1 when absent. The analyzer only CAPTURES it (no
    interpretation); the canonical latency_ms / classification are UNCHANGED — this is a robust-clock
    companion for the RP nonce-bound verify path (bridge t_mono is inflated under Remote Play's bursty
    frame reads; the device clock is immune to bridge processing lag). The caller wrap-diffs
    (crossing - probe) ticks and converts to ms for the true reaction latency; never gates the corpus."""


class L6bReflexAnalyzer:
    """Analyze IMU accel response after a sub-perceptual L6b haptic probe.

    Args:
        human_min_ms:              Minimum latency to classify as HUMAN (default 80ms).
        human_max_ms:              Maximum latency to classify as HUMAN (default 280ms;
                                   desk calibration recommends 350ms).
        accel_delta_threshold_lsb: Min |accel_mag - pre_mean| to count as a reflex impulse.
                                   Default 500 LSB — well above sensor noise floor (332.99 LSB
                                   95th-pct gyro noise, Phase 57 N=74 calibration), conservative
                                   pending hardware-validated L6b sessions.
    """

    BOT_MAX_MS: float = 15.0

    def __init__(
        self,
        human_min_ms: float = 80.0,
        human_max_ms: float = 280.0,
        accel_delta_threshold_lsb: float = 500.0,
    ) -> None:
        self.human_min_ms = human_min_ms
        self.human_max_ms = human_max_ms
        self.accel_delta_threshold_lsb = accel_delta_threshold_lsb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        pre_reports: list[dict],
        post_reports: list[dict],
        probe_ts: float,
    ) -> L6bReflexResult:
        """Detect first accel impulse above threshold in post_reports.

        Args:
            pre_reports:  HID report dicts captured before probe delivery.
                          Keys: 'ax', 'ay', 'az' (raw accel LSB values); optional 't_mono'.
            post_reports: HID report dicts captured after probe delivery (up to 350 frames).
            probe_ts:     time.monotonic() timestamp of probe delivery.

        Returns:
            L6bReflexResult with valid=False if no impulse detected.
        """
        pre_mean = self._accel_mean(pre_reports)
        peak = 0.0
        legacy_latency_ms = -1.0
        true_latency_ms = -1.0
        precursor_t_mono: float | None = None
        crossing_t_mono: float | None = None
        crossing_device_ts: float = -1.0   # F-RIG27-8 additive companion clock
        threshold = self.accel_delta_threshold_lsb

        for i, report in enumerate(post_reports):
            mag = self._accel_mag(report)
            delta = abs(mag - pre_mean)
            if delta > peak:
                peak = delta
            t_mono = float(report.get("t_mono", 0.0) or 0.0)
            if precursor_t_mono is None and delta > PRECURSOR_THRESHOLD_LSB:
                if t_mono > 0.0 and t_mono >= probe_ts:
                    precursor_t_mono = t_mono
            if legacy_latency_ms < 0 and delta >= threshold:
                legacy_latency_ms = float(i) * MS_PER_REPORT
                if t_mono > 0.0 and t_mono >= probe_ts:
                    crossing_t_mono = t_mono
                # F-RIG27-8 additive: capture the device sensor ts (raw uint32 ticks) at the SAME
                # crossing frame (robust clock; canonical latency stays t_mono-based). -1 stays if the
                # report has no device_ts (0 = absent). The caller wrap-diffs + converts ticks->ms.
                _dev_ts = float(report.get("device_ts", 0.0) or 0.0)
                if _dev_ts > 0.0:
                    crossing_device_ts = _dev_ts

        if crossing_t_mono is not None and probe_ts > 0.0:
            true_latency_ms = (crossing_t_mono - probe_ts) * 1000.0

        reflex_gap_ms: float | None = None
        if precursor_t_mono is not None and crossing_t_mono is not None:
            reflex_gap_ms = (crossing_t_mono - precursor_t_mono) * 1000.0

        valid = peak >= threshold and (legacy_latency_ms >= 0.0 or true_latency_ms >= 0.0)
        canonical_ms = true_latency_ms if true_latency_ms >= 0.0 else legacy_latency_ms
        classification = (
            self._classify(
                canonical_ms=canonical_ms,
                true_latency_ms=true_latency_ms,
                peak=peak,
                reflex_gap_ms=reflex_gap_ms,
            )
            if valid
            else "NO_RESPONSE"
        )
        confidence = self._confidence(peak) if valid else 0.5

        return L6bReflexResult(
            latency_ms=canonical_ms if valid else -1.0,
            legacy_latency_ms=legacy_latency_ms,
            true_latency_ms=true_latency_ms,
            reflex_gap_ms=reflex_gap_ms,
            accel_delta_peak=peak,
            classification=classification,
            confidence=confidence,
            probe_ts=probe_ts,
            valid=valid,
            crossing_device_ts=crossing_device_ts,
        )

    def classify(self, result: L6bReflexResult) -> float:
        """Map L6bReflexResult to p_human [0.0, 1.0].

        Returns:
            0.5  — NO_RESPONSE or INCONCLUSIVE (neutral prior — conservative)
            0.05 — BOT (latency < 15ms, interrupt-driven)
            0.90 — HUMAN (latency 80–human_max_ms, neuromotor loop)
        """
        if not result.valid or result.classification == "NO_RESPONSE":
            return 0.5
        if result.classification == "BOT":
            return 0.05
        if result.classification == "HUMAN":
            return 0.90
        return 0.5  # INCONCLUSIVE

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _classify(
        self,
        *,
        canonical_ms: float,
        true_latency_ms: float,
        peak: float,
        reflex_gap_ms: float | None,
    ) -> str:
        if peak < self.accel_delta_threshold_lsb or canonical_ms < 0.0:
            return "NO_RESPONSE"
        if canonical_ms < self.BOT_MAX_MS:
            return "BOT"
        if (
            true_latency_ms >= 0.0
            and reflex_gap_ms is not None
            and reflex_gap_ms < MECHANICAL_REFLEX_GAP_MAX_MS
            and true_latency_ms < self.human_min_ms
        ):
            return "INCONCLUSIVE"
        return self._classify_latency(canonical_ms)

    def _classify_latency(self, latency_ms: float) -> str:
        """Assign classification bucket from latency value."""
        if latency_ms < self.BOT_MAX_MS:
            return "BOT"
        if latency_ms < self.human_min_ms:
            return "INCONCLUSIVE"
        if latency_ms <= self.human_max_ms:
            return "HUMAN"
        return "INCONCLUSIVE"

    def _confidence(self, peak_delta: float) -> float:
        """Scale confidence by how far above threshold the peak delta is.

        Clamped to [0.5, 1.0] — minimum 0.5 for any detected impulse.
        """
        if self.accel_delta_threshold_lsb <= 0:
            return 0.5
        ratio = peak_delta / self.accel_delta_threshold_lsb
        return min(1.0, 0.5 + 0.5 * min(ratio - 1.0, 1.0))

    @staticmethod
    def _accel_mag(report: dict) -> float:
        """Compute ||accel|| from a HID report dict (keys: 'ax', 'ay', 'az')."""
        ax = float(report.get("ax", 0.0))
        ay = float(report.get("ay", 0.0))
        az = float(report.get("az", 0.0))
        return math.sqrt(ax * ax + ay * ay + az * az)

    @staticmethod
    def _accel_mean(reports: list[dict]) -> float:
        """Mean ||accel|| across a list of HID report dicts. Returns 0.0 for empty list."""
        if not reports:
            return 0.0
        total = sum(
            math.sqrt(
                float(r.get("ax", 0.0)) ** 2
                + float(r.get("ay", 0.0)) ** 2
                + float(r.get("az", 0.0)) ** 2
            )
            for r in reports
        )
        return total / len(reports)
