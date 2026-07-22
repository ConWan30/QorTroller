"""Football event<->response coupling (CANDIDATE) — grok A2A football-coupling r02 BUILD-NOW.

Advisory / offline measurement only. Does NOT flip optical_consistent calibrated=True,
poep_enabled, L6B, or any FROZEN surface. Pure functions + optical_copresence reuse.

STEER (see docs/a2a/football-coupling/round-02-grok-expand.md):
  PRIMARY = D1+D3 merge: field-motion-onset as game event; multi-input onset (L2/R2/stick
  burst) as response; FIXED reaction window; empirical circular-shift null from
  optical_copresence (matched procedure).
  SECONDARY = D2 lag-conditioned density peak, ONLY with matched adaptive search on every
  null shift (look-ahead bias guard).

#1 statistical risk (pinned):
  * D1/D3: circular event definition (player stick pans camera -> motion spike counted as
    "game event") AND window-density saturation (dense HID onsets inflate both real and null).
  * D2: look-ahead bias if adaptive lag is chosen on the real series without applying the
    SAME adaptive procedure to each circular-shift null replicate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from l9_presence.optical_copresence import (
    TimedEvent,
    OpticalCoPresenceResult,
    optical_copresence,
    _hit_rate,
    _quantile,
    NULL_SHIFTS,
    NULL_QUANTILE,
    NULL_MIN_EXCESS,
    MIN_ABS_HIT_RATE,
    MIN_EVENTS,
)

# Default FIXED reaction window for D1/D3 (ms). Tighter than the naive 0.5-8s that saturated
# the null on run1_cfb27; still a CANDIDATE hypothesis, not calibrated.
DEFAULT_REACTION_WINDOW_MS: tuple[float, float] = (100.0, 1500.0)

# Field-motion onset defaults (operate on precomputed energy samples — pure, no frame I/O)
DEFAULT_DEBOUNCE_S: float = 2.0
DEFAULT_LOCAL_MAX_RADIUS_S: float = 0.4
DEFAULT_PERCENTILE_THR: float = 90.0  # only for offline thr suggestion; prefer fixed thr in eval

# Multi-input onset thresholds (DualSense/Edge raw ADC; center stick = 128)
TRIGGER_ONSET_LSB: int = 20
STICK_BURST_LSB: int = 40
STICK_CENTER: int = 128


@dataclass(frozen=True, slots=True)
class MotionSample:
    """Precomputed field-region frame-diff energy at ts_s (seconds from capture start)."""
    ts_s: float
    energy: float


@dataclass(frozen=True, slots=True)
class HidSample:
    """Minimal HID row for multi-input onset extraction. t_ms is session-relative milliseconds."""
    t_ms: float
    l2: int = 0
    r2: int = 0
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128


@dataclass(frozen=True, slots=True)
class AdaptiveLagResult:
    """D2 lag-conditioned coupling with MATCHED adaptive procedure on null shifts.

    peak_lag_ms is the lag bin center that maximized real density; null_peak_lags lists the
    lag chosen under the identical search for each circular shift (diagnostic only).
    """
    event_coupled: bool
    reason: str
    n_events: int
    real_peak_density: float
    null_q: float
    null_median: float
    peak_lag_ms: float
    lag_search_ms: tuple[float, float]
    bin_width_ms: float

    def to_dict(self) -> dict:
        return {
            "event_coupled": self.event_coupled,
            "reason": self.reason,
            "n_events": self.n_events,
            "real_peak_density": round(self.real_peak_density, 4),
            "null_q": round(self.null_q, 4),
            "null_median": round(self.null_median, 4),
            "peak_lag_ms": round(self.peak_lag_ms, 1),
            "lag_search_ms": list(self.lag_search_ms),
            "bin_width_ms": self.bin_width_ms,
            "claim": "session_co_presence_not_humanity",
            "null_procedure": "matched_adaptive_lag_search_per_shift",
        }


def detect_field_motion_onsets(
    samples: Sequence[MotionSample],
    *,
    energy_threshold: float,
    debounce_s: float = DEFAULT_DEBOUNCE_S,
    local_max_radius_s: float = DEFAULT_LOCAL_MAX_RADIUS_S,
) -> list[TimedEvent]:
    """PURE: field-motion onsets from precomputed energy series.

    Fires when energy >= energy_threshold, is a local max within +/- local_max_radius_s,
    and is at least debounce_s after the previous onset. Returns TimedEvent.ts_ms in ms.

    Callers MUST supply a fixed energy_threshold (not a full-session percentile of the
    series under test) for honest eval — training thr on the full capture is look-ahead.
    """
    if not samples:
        return []
    ordered = sorted(samples, key=lambda s: s.ts_s)
    thr = float(energy_threshold)
    if thr < 0:
        raise ValueError("energy_threshold must be >= 0")
    onsets: list[TimedEvent] = []
    last_ts = -1e18
    for i, s in enumerate(ordered):
        if s.energy < thr:
            continue
        if (s.ts_s - last_ts) < debounce_s:
            continue
        # local max in radius
        lo, hi = s.ts_s - local_max_radius_s, s.ts_s + local_max_radius_s
        local_max = s.energy
        for j in range(max(0, i - 20), min(len(ordered), i + 21)):
            o = ordered[j]
            if lo <= o.ts_s <= hi and o.energy > local_max:
                local_max = o.energy
        if s.energy < local_max:
            continue
        onsets.append(TimedEvent(ts_ms=s.ts_s * 1000.0, kind="field_motion_onset"))
        last_ts = s.ts_s
    return onsets


def suggest_energy_threshold(
    samples: Sequence[MotionSample],
    percentile: float = DEFAULT_PERCENTILE_THR,
) -> float:
    """Offline helper: suggest a fixed thr from a *held-out* or *prior* series only.

    Do NOT call this on the same samples you will then score without a train/test split —
    that is look-ahead. Exposed for operators building a thr from capture A to evaluate B.
    """
    if not samples:
        return 0.0
    xs = sorted(float(s.energy) for s in samples)
    if percentile <= 0:
        return xs[0]
    if percentile >= 100:
        return xs[-1]
    idx = min(len(xs) - 1, max(0, int(round((percentile / 100.0) * (len(xs) - 1)))))
    return xs[idx]


def extract_multi_input_onsets(
    rows: Sequence[HidSample],
    *,
    trigger_onset_lsb: int = TRIGGER_ONSET_LSB,
    stick_burst_lsb: int = STICK_BURST_LSB,
    stick_center: int = STICK_CENTER,
    min_gap_ms: float = 50.0,
) -> list[TimedEvent]:
    """PURE: multi-input onsets — L2 rising edge, R2 rising edge, or stick-burst from neutral.

    Defense-appropriate (D3): does not assume the player is on offense (R2 sprint only).
    """
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: r.t_ms)
    out: list[TimedEvent] = []
    last_t = -1e18
    prev = ordered[0]
    # start from second sample so prev is defined; first row alone cannot form an edge
    for cur in ordered[1:]:
        onset = False
        kind = ""
        if prev.r2 < trigger_onset_lsb and cur.r2 >= trigger_onset_lsb:
            onset = True
            kind = "r2_onset"
        elif prev.l2 < trigger_onset_lsb and cur.l2 >= trigger_onset_lsb:
            onset = True
            kind = "l2_onset"
        else:
            def stick_mag(r: HidSample) -> int:
                return max(
                    abs(r.lx - stick_center),
                    abs(r.ly - stick_center),
                    abs(r.rx - stick_center),
                    abs(r.ry - stick_center),
                )
            if stick_mag(prev) < stick_burst_lsb and stick_mag(cur) >= stick_burst_lsb:
                onset = True
                kind = "stick_burst"
        if onset and (cur.t_ms - last_t) >= min_gap_ms:
            out.append(TimedEvent(ts_ms=cur.t_ms, kind=kind))
            last_t = cur.t_ms
        prev = cur
    return out


def extract_r2_onsets(
    rows: Sequence[HidSample],
    *,
    trigger_onset_lsb: int = TRIGGER_ONSET_LSB,
    min_gap_ms: float = 50.0,
) -> list[TimedEvent]:
    """R2-only onsets (legacy naive path for A/B comparison against multi-input)."""
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: r.t_ms)
    out: list[TimedEvent] = []
    last_t = -1e18
    prev_r2 = ordered[0].r2
    for cur in ordered[1:]:
        if prev_r2 < trigger_onset_lsb and cur.r2 >= trigger_onset_lsb:
            if (cur.t_ms - last_t) >= min_gap_ms:
                out.append(TimedEvent(ts_ms=cur.t_ms, kind="r2_onset"))
                last_t = cur.t_ms
        prev_r2 = cur.r2
    return out


def football_fixed_window_coupling(
    game_events: Iterable[TimedEvent],
    input_responses: Iterable[TimedEvent],
    *,
    reaction_window_ms: tuple[float, float] = DEFAULT_REACTION_WINDOW_MS,
    min_events: int = MIN_EVENTS,
    min_abs_hit_rate: float = MIN_ABS_HIT_RATE,
    n_shifts: int = NULL_SHIFTS,
    null_quantile: float = NULL_QUANTILE,
    null_min_excess: float = NULL_MIN_EXCESS,
) -> OpticalCoPresenceResult:
    """D1/D3 primary path: fixed window + existing empirical circular-shift null.

    Thin wrapper so the football coupling entrypoint is explicit and versionable without
    mutating optical_copresence thresholds.
    """
    return optical_copresence(
        game_events,
        input_responses,
        reaction_window_ms=reaction_window_ms,
        min_events=min_events,
        min_abs_hit_rate=min_abs_hit_rate,
        n_shifts=n_shifts,
        null_quantile=null_quantile,
        null_min_excess=null_min_excess,
    )


def _peak_lag_density(
    event_ts: list[float],
    resp_ts: list[float],
    lag_lo: float,
    lag_hi: float,
    bin_width: float,
) -> tuple[float, float]:
    """Return (peak_density, peak_lag_center_ms) over fixed lag bins in [lag_lo, lag_hi].

    density = fraction of events that have at least one response in that lag bin.
    Deterministic: first bin wins ties (lowest lag).
    """
    if not event_ts or bin_width <= 0 or lag_hi <= lag_lo:
        return 0.0, lag_lo
    n_bins = int((lag_hi - lag_lo) / bin_width)
    if n_bins < 1:
        n_bins = 1
    best_d = -1.0
    best_lag = lag_lo + 0.5 * bin_width
    for b in range(n_bins):
        lo = lag_lo + b * bin_width
        hi = lo + bin_width
        d = _hit_rate(event_ts, resp_ts, lo, hi)
        if d > best_d:
            best_d = d
            best_lag = lo + 0.5 * bin_width
    return max(0.0, best_d), best_lag


def football_adaptive_lag_coupling(
    game_events: Iterable[TimedEvent],
    input_responses: Iterable[TimedEvent],
    *,
    lag_search_ms: tuple[float, float] = (0.0, 8000.0),
    bin_width_ms: float = 500.0,
    min_events: int = MIN_EVENTS,
    min_abs_hit_rate: float = MIN_ABS_HIT_RATE,
    n_shifts: int = NULL_SHIFTS,
    null_quantile: float = NULL_QUANTILE,
    null_min_excess: float = NULL_MIN_EXCESS,
) -> AdaptiveLagResult:
    """D2 path with MATCHED adaptive lag search on every null shift (look-ahead guard).

    Procedure (identical for real and each null replicate):
      1. Search lag bins in [lag_lo, lag_hi] of width bin_width_ms.
      2. Peak density = max over bins of hit-rate in that bin.
      3. Real peak density must beat null_q of the peak densities from circular-shifted
         responses (each shift re-runs the full lag search — NOT a fixed lag from real).

    Without step 3 matching the adaptive search, any dense response stream "finds" a lag
    and would falsely beat a non-adaptive null. That is the #1 D2 statistical risk.
    """
    events = sorted(e.ts_ms for e in game_events)
    responses = sorted(r.ts_ms for r in input_responses)
    lag_lo, lag_hi = lag_search_ms

    if len(events) < min_events:
        return AdaptiveLagResult(
            False, f"too few game events ({len(events)}<{min_events})",
            len(events), 0.0, 0.0, 0.0, 0.0, lag_search_ms, bin_width_ms,
        )
    if not responses:
        return AdaptiveLagResult(
            False, "no input responses", len(events), 0.0, 0.0, 0.0, 0.0,
            lag_search_ms, bin_width_ms,
        )

    real_peak, real_lag = _peak_lag_density(events, responses, lag_lo, lag_hi, bin_width_ms)

    r_span = responses[-1] - responses[0]
    if r_span <= 0:
        return AdaptiveLagResult(
            False, "degenerate response span", len(events), real_peak, 0.0, 0.0, real_lag,
            lag_search_ms, bin_width_ms,
        )

    r0 = responses[0]
    n_resp = len(responses)
    mean_gap = r_span / (n_resp - 1) if n_resp > 1 else r_span
    period = r_span + mean_gap
    null_peaks: list[float] = []
    for k in range(1, n_shifts + 1):
        off = (k / (n_shifts + 1)) * period
        shifted = sorted(r0 + ((r - r0 + off) % period) for r in responses)
        # MATCHED procedure: re-run adaptive lag search on this shift
        peak_d, _ = _peak_lag_density(events, shifted, lag_lo, lag_hi, bin_width_ms)
        null_peaks.append(peak_d)

    null_q = _quantile(null_peaks, null_quantile)
    null_med = _quantile(null_peaks, 0.5)
    coupled = (
        real_peak >= min_abs_hit_rate
        and real_peak > null_q
        and real_peak >= null_med + null_min_excess
    )
    reason = (
        f"adapt_peak={real_peak:.2f}@lag={real_lag:.0f}ms vs null_q{null_quantile:.2f}={null_q:.2f} "
        f"null_med={null_med:.2f} floor={min_abs_hit_rate} matched_search=True -> "
        f"{'session-coupled (not human-proof)' if coupled else 'at-null (dump-replay/uncoupled)'}"
    )
    return AdaptiveLagResult(
        coupled, reason, len(events), real_peak, null_q, null_med, real_lag,
        lag_search_ms, bin_width_ms,
    )


def events_from_ts_s(ts_s: Sequence[float], kind: str = "event") -> list[TimedEvent]:
    """Convenience: seconds -> TimedEvent list (ms)."""
    return [TimedEvent(ts_ms=float(t) * 1000.0, kind=kind) for t in ts_s]
