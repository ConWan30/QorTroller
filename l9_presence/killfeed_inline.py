"""QorTroller L9 — Trigger-gated INLINE kill-feed authorship (scheduling + live telemetry; advisory).

Runs the calibrated `killfeed_cv.classify_panel` LIVE during play, gated by the R2 fire onset, so the
same labelled corpus grows in real time and near-margin scores surface as they happen (instead of an
offline recompute after the session). This is a CLASSIFICATION-scheduling burst, NOT a capture burst:
capture stays continuous; only which already-arriving frames get classified is trigger-gated.

Design constraints baked in (from this session's findings):
  * Burst-on-demand CAPTURE was tried + abandoned (WGC needs warm-up; per-press start/stop missed it).
    This schedules classification off the CONSUMPTION side; it never touches the WGC frame callback.
  * `classify_panel` is ~100ms/call (8-scale template match) -> the caller runs it off the event loop
    (asyncio.to_thread) with SINGLE-FLIGHT; this module holds the window/single-flight/min-gap decision
    as a PURE state machine (no async, no cv2, no I/O) so it is unit-testable.
  * Thresholds are FROZEN here: it schedules + monitors, it does NOT recalibrate. match_floor (0.66),
    killer/victim 0.28, feed/roster 0.42 all live in killfeed_cv and are untouched.

PURE: no bridge/cv2/async import. The caller injects classify results (record_result) and does the
actual classify (killfeed_cv), crop-persist (killfeed_cv.save_crop_bounded), and JSONL append.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

# R2 onset -> classification window. The kill row appears 50ms after the R2 (render latency) AND PERSISTS
# ~5s in the Warzone feed. The consumption loop iterates ~1-1.5s, so a tight 50-900ms window closes BETWEEN
# iterations and is never sampled (found live in segment-2 testing 2026-07-01). Widened to 5000ms so a
# ~1.5s iteration lands inside it and classifies the (still-visible) feed row; sustained fire extends it,
# giving continuous combat sampling (min-gap bounded). Lower bound 50ms keeps "row not instant".
R2_WINDOW_MS = (50.0, 5000.0)
# R2 fire-onset threshold (~40/255) — the same value the consumption side already uses
# (retina_combat_r2_threshold default 40); env-overridable at the caller.
DEFAULT_R2_THRESHOLD = 40
# near-boundary epsilon: flag any classified score within this of match_floor (D-CAPTURE-2 -> [0.64,0.68]).
DEFAULT_NEAR_EPSILON = float(os.getenv("KILLFEED_CV_NEAR_EPSILON", "0.02"))
# min gap between inline classifications (bounds cost under sustained fire; each classify is ~100ms).
DEFAULT_MIN_GAP_MS = float(os.getenv("KILLFEED_CV_INLINE_MIN_GAP_MS", "200"))
# exact numpy.percentile refreshed every K background samples (D-CAPTURE-3 — no streaming sketch at this
# scale; proportionate, no new dependency).
DEFAULT_BG_REFRESH_K = int(os.getenv("KILLFEED_CV_BG_REFRESH_K", "25"))


@dataclass(frozen=True)
class TriggerChannel:
    """One input-triggered classification channel. Future channels = a new entry + its own decision block,
    NOT a rewrite of this mechanism. Only R2 is enabled; the rest are documented, not built."""
    name: str
    hid_signal: str
    roi_or_target: str
    verdict_label: str
    window_ms: tuple
    enabled: bool


# R2 is the ONLY enabled channel. The other three are documented-not-built (comment/doc only) so the
# extensibility shape is explicit; each is its own future decision block, never implemented here.
CHANNEL_REGISTRY = (
    TriggerChannel("r2_onset", "r2_trigger >= 40 (rising edge)", "panel: feed+roster",
                   "AUTHORED_PRESENT", R2_WINDOW_MS, True),
    # --- documented, enabled=False, NOT implemented ---
    TriggerChannel("l2_ads", "l2_trigger >= 40 (rising edge)", "scope-overlay / center-ROI",
                   "ADS_PRESENT", (0.0, 300.0), False),        # second anti-splice channel
    TriggerChannel("weapon_switch", "L1/R1 or buttons-bitmask press", "weapon-switch / ammo-counter HUD",
                   "SWITCH_PRESENT", (0.0, 500.0), False),
    TriggerChannel("r2_release", "r2_trigger < 40 (falling edge)", "panel: feed",
                   "RELEASE_BOUND", (0.0, 900.0), False),       # tighter render-latency bound, same signal
)


def enabled_channels() -> tuple:
    return tuple(c for c in CHANNEL_REGISTRY if c.enabled)


def near_boundary(score: float, match_floor: float, epsilon: float = DEFAULT_NEAR_EPSILON) -> bool:
    """True iff a classified score is within epsilon of the match floor (the [floor-eps, floor+eps] band)."""
    return abs(float(score) - float(match_floor)) <= float(epsilon)


def append_near_boundary_jsonl(path: str, record: dict) -> bool:
    """Append one near-boundary event to a JSONL sink (D-CAPTURE-4). Fail-open: any error -> False, never
    raises (advisory telemetry must never break capture)."""
    try:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return True
    except Exception:
        return False


class BackgroundScoreTracker:
    """Live p95 of inline BACKGROUND/neutral match scores. Exact numpy.percentile recomputed every
    refresh_k new samples (not per-sample) — proportionate to the corpus scale, no approximation, no new
    dependency. Read-only telemetry: it is NEVER a threshold input."""

    def __init__(self, refresh_k: int = DEFAULT_BG_REFRESH_K, pct: float = 95.0) -> None:
        self._scores: list[float] = []
        self._k = max(1, int(refresh_k))
        self._pct = float(pct)
        self._since_refresh = 0
        self._cached: Optional[float] = None
        self._cached_max: Optional[float] = None

    def add(self, score: float) -> None:
        self._scores.append(float(score))
        self._since_refresh += 1
        if self._since_refresh >= self._k:
            self.refresh()

    def refresh(self) -> None:
        if self._scores:
            import numpy as np
            arr = np.asarray(self._scores, dtype=float)
            self._cached = float(np.percentile(arr, self._pct))
            self._cached_max = float(arr.max())
        self._since_refresh = 0

    @property
    def n(self) -> int:
        return len(self._scores)

    def percentile(self) -> Optional[float]:
        return self._cached

    def max(self) -> Optional[float]:
        return self._cached_max


@dataclass
class InlineAuthorshipMonitor:
    """PURE state machine for R2-gated inline classification: holds the active window, single-flight flag,
    min-gap throttle, the background-score tracker, and the counters status() surfaces. No async / cv2 / I/O
    — the caller injects classify results via record_result and performs the actual classify + persist."""
    window_ms: tuple = R2_WINDOW_MS
    min_gap_ms: float = DEFAULT_MIN_GAP_MS
    match_floor: float = 0.66            # mirror of killfeed_cv.DEFAULT_MATCH_FLOOR (monitor does NOT set it)
    near_epsilon: float = DEFAULT_NEAR_EPSILON
    refresh_k: int = DEFAULT_BG_REFRESH_K
    _window_gate_ms: float = field(default=0.0, init=False)   # earliest classify time (onset + lag_min)
    _window_end_ms: float = field(default=0.0, init=False)    # latest classify time (onset + lag_max)
    _inflight: bool = field(default=False, init=False)
    _last_classify_ms: float = field(default=-1e18, init=False)
    _classifications: int = field(default=0, init=False)
    _authored: int = field(default=0, init=False)
    _deaths: int = field(default=0, init=False)
    _roster: int = field(default=0, init=False)
    _near_boundary: int = field(default=0, init=False)
    _last_verdict: Optional[str] = field(default=None, init=False)

    def __post_init__(self) -> None:
        self._tracker = BackgroundScoreTracker(self.refresh_k)

    def mark_onset(self, now_ms: float) -> None:
        """R2 rising-edge onset at now_ms: open/extend the classification window [now+lag_min, now+lag_max].
        Sustained fire keeps the window open so combat is sampled continuously (min-gap bounded)."""
        lo, hi = self.window_ms
        if now_ms > self._window_end_ms:          # not currently active -> reset the gate
            self._window_gate_ms = now_ms + lo
        self._window_end_ms = now_ms + hi         # extend the end on every onset

    def should_classify(self, now_ms: float) -> bool:
        """PURE decision: are we inside an active window, not already classifying, and past the min gap?"""
        if self._inflight:
            return False
        if not (self._window_gate_ms <= now_ms <= self._window_end_ms):
            return False
        return (now_ms - self._last_classify_ms) >= self.min_gap_ms

    def begin(self, now_ms: float) -> None:
        self._inflight = True
        self._last_classify_ms = now_ms

    def end(self) -> None:
        self._inflight = False

    def record_result(self, verdict: str, score: float, region: Optional[str], slot: Optional[str],
                      now_ms: float) -> Optional[dict]:
        """Fold one classify result into the live telemetry. Returns a near-boundary event dict (for the
        caller to JSONL-append) iff the score is within epsilon of the floor, else None. BACKGROUND/neutral
        scores feed the tracker; AUTHORED does not (it's the signal, not the noise floor)."""
        self._classifications += 1
        self._last_verdict = verdict
        if verdict == "AUTHORED_PRESENT":
            self._authored += 1
        elif region == "feed" and slot == "victim":
            self._deaths += 1
            self._tracker.add(score)          # a death is a non-authored match -> part of the neutral field
        elif region == "roster":
            self._roster += 1
            self._tracker.add(score)
        else:
            self._tracker.add(score)          # true background
        if near_boundary(score, self.match_floor, self.near_epsilon):
            self._near_boundary += 1
            return {"ts_ms": round(now_ms, 1), "score": round(float(score), 4), "verdict": verdict,
                    "region": region, "slot": slot, "floor": self.match_floor}
        return None

    def status_dict(self) -> dict:
        """Read-only inline telemetry for status() (alongside kf_verdict/kf_own_kills/kf_other_kills)."""
        return {
            "inline_enabled": True,
            "inline_classifications": self._classifications,
            "inline_authored": self._authored,
            "inline_deaths": self._deaths,
            "inline_roster": self._roster,
            "inline_near_boundary": self._near_boundary,
            "inline_last_verdict": self._last_verdict,
            "inline_bg_p95": (round(self._tracker.percentile(), 4)
                              if self._tracker.percentile() is not None else None),
            "inline_bg_max": (round(self._tracker.max(), 4)
                              if self._tracker.max() is not None else None),
            "inline_bg_n": self._tracker.n,
        }


def now_ms() -> float:
    return time.time() * 1000.0
