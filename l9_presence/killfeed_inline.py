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


# R2 is the ONLY enabled channel. l2_ads is now SCAFFOLDED (l9_presence/ads_coupling.py) but stays
# enabled=False until calibrated on real center-ROI ADS data AND adversarially splice-paired; the other two
# remain documented-not-built. Each channel is its own decision block, never a rewrite of this mechanism.
CHANNEL_REGISTRY = (
    TriggerChannel("r2_onset", "r2_trigger >= 40 (rising edge)", "panel: feed+roster",
                   "AUTHORED_PRESENT", R2_WINDOW_MS, True),
    # --- l2_ads: SCAFFOLDED in ads_coupling.py (AdsCouplingMonitor); enabled=False, detector ABSTAINS until
    #     calibrated + splice-paired. Second anti-splice channel — binds live L2 to a live scoped transition
    #     the replay can't supply; tight (0,300)ms window is the parametric lever (vs R2's 5000ms). ---
    TriggerChannel("l2_ads", "l2_trigger >= 40 (rising edge)", "scope-overlay / center-ROI",
                   "ADS_TRANSITION_BOUND", (0.0, 300.0), False),   # narrow claim (a bound transition), NOT presence
    # --- documented, enabled=False, NOT implemented ---
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
    min-gap throttle, the background-score tracker, the counters status() surfaces, AND the Phase-1
    max-over-window composite (see WindowComposite below). No async / cv2 / I/O — the caller injects
    classify results via record_result/observe_window and performs the actual classify + persist.

    PHASE 1 (2026-07-01, floor-transfer diagnostic D-FLOOR-1=branch-b, docs/floor-transfer-diagnostic-
    2026-07-01.md): the archive-confirmed cause of AUTHORED=0 was a SINGLE-SAMPLE MISS, not a floor/
    capture-condition problem (real kills peaked 0.70-0.84 above match_floor=0.66; a single per-classify
    sample sometimes landed off-peak). The fix composites the MAX score seen at killer/victim position
    ACROSS an R2 window and resolves ONE verdict when the window closes, instead of trusting any single
    sample's already-thresholded verdict. This lives ENTIRELY in the scheduling layer (here) — it reads
    match_floor/killer_max_frac/feed_region_max_yfrac from the caller (sourced from killfeed_cv's frozen
    constants) but never redefines them. record_result's existing per-sample telemetry (near-boundary log,
    background tracker, per-crop _authored/_deaths/_roster) is UNCHANGED — the composite is an ADDITIVE
    signal (status_dict's composite_* fields), not a replacement of the existing counters."""
    window_ms: tuple = R2_WINDOW_MS
    min_gap_ms: float = DEFAULT_MIN_GAP_MS
    match_floor: float = 0.66            # mirror of killfeed_cv.DEFAULT_MATCH_FLOOR (monitor does NOT set it)
    killer_max_frac: float = 0.28        # mirror of killfeed_cv.KILLER_MAX_FRAC_PANEL (read-only mirror)
    feed_region_max_yfrac: float = 0.42  # mirror of killfeed_cv.FEED_REGION_MAX_YFRAC (read-only mirror)
    near_epsilon: float = DEFAULT_NEAR_EPSILON
    refresh_k: int = DEFAULT_BG_REFRESH_K
    anchor_id: str = "roster_v1"         # PROVENANCE: which anchor produced these scores (roster_v1|feed_v1).
    #   Score semantics are anchor-specific (roster p95~0.66 vs feed re-validated 0 killer-slot FP over the
    #   1200-crop archive 2026-07-02) — stamped on every record so a corpus spanning an anchor swap stays
    #   interpretable, same lesson as ts_source. Default roster_v1; the live caller passes feed_v1.
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
    # --- Phase 1 max-over-window composite state ---
    _win_best_killer: float = field(default=-1.0, init=False)
    _win_best_victim: float = field(default=-1.0, init=False)
    _win_victim_first_ms: float = field(default=-1.0, init=False)   # ts the victim row FIRST appeared this window
    _win_members: int = field(default=0, init=False)
    _win_resolved: bool = field(default=True, init=False)      # True = nothing pending (no open window yet)
    _composite_authored: int = field(default=0, init=False)
    _composite_windows: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._tracker = BackgroundScoreTracker(self.refresh_k)

    def mark_onset(self, now_ms: float) -> Optional[dict]:
        """R2 rising-edge onset at now_ms: open/extend the classification window [now+lag_min, now+lag_max].
        Sustained fire keeps the window open so combat is sampled continuously (min-gap bounded). If this
        onset starts a genuinely NEW window (the prior one had already ended), the prior window's composite
        is resolved FIRST and returned (restart semantics — mirrors DeathWindowMonitor.mark_death) so the
        caller can log it before the new window's state resets."""
        lo, hi = self.window_ms
        resolved = None
        if now_ms > self._window_end_ms:          # not currently active -> reset the gate (NEW window)
            resolved = self._resolve_window(now_ms)
            self._window_gate_ms = now_ms + lo
            self._reset_window()
        self._window_end_ms = now_ms + hi         # extend the end on every onset
        return resolved

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
        scores feed the tracker; AUTHORED does not (it's the signal, not the noise floor). UNCHANGED by
        Phase 1 — this is the existing per-sample accounting; see observe_window for the composite."""
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
                    "region": region, "slot": slot, "floor": self.match_floor, "anchor": self.anchor_id}
        return None

    # --- Phase 1: max-over-window composite ---------------------------------------------------------
    def _classify_position(self, x_frac: Optional[float], y_frac: Optional[float]):
        """Derive the would-be region/slot from x_frac/y_frac using the SAME frozen thresholds
        classify_panel uses. Works even on BELOW-FLOOR samples — classify_panel omits region/slot from its
        evidence dict when score<match_floor, but x_frac/y_frac are always present, so the composite can see
        'this sample would have been killer-position' even when the single-sample verdict was UNVERIFIABLE."""
        if x_frac is None or y_frac is None:
            return None, None
        if y_frac >= self.feed_region_max_yfrac:
            return "roster", None
        return "feed", ("killer" if x_frac < self.killer_max_frac else "victim")

    def observe_window(self, score: float, x_frac: Optional[float], y_frac: Optional[float],
                       now_ms: float) -> Optional[dict]:
        """Fold ONE classify's raw score + position into the CURRENT window's running max — regardless of
        whether this single sample's own verdict cleared the floor. Call once per classify, after
        record_result. Returns a resolved composite record only if THIS call's timestamp is already past
        the window end (the window quietly expired without a following onset — see flush_if_expired for the
        no-further-classify case); normally returns None (composite resolves on the NEXT mark_onset)."""
        region, slot = self._classify_position(x_frac, y_frac)
        self._win_members += 1
        self._win_resolved = False
        if region == "feed" and slot == "killer":
            self._win_best_killer = max(self._win_best_killer, float(score))
        elif region == "feed" and slot == "victim":
            self._win_best_victim = max(self._win_best_victim, float(score))
            if self._win_victim_first_ms < 0.0:            # anchor the death-row APPEARANCE (first victim obs)
                self._win_victim_first_ms = float(now_ms)  # confirmation lag = resolve ts - this; see mark_death
        return self.flush_if_expired(now_ms)

    def flush_if_expired(self, now_ms: float) -> Optional[dict]:
        """Resolve + return the current window's composite if it has members, hasn't been resolved yet, and
        now_ms is past the window end (no further onset extended it). Call once per consumption tick
        (independent of whether a classify happened) so a window that goes cold still resolves promptly
        instead of waiting indefinitely for the next R2 onset."""
        if self._win_members > 0 and not self._win_resolved and now_ms > self._window_end_ms:
            rec = self._resolve_window(now_ms)
            self._win_resolved = True
            return rec
        return None

    def _resolve_window(self, now_ms: float) -> Optional[dict]:
        """Composite verdict for the (about-to-close) window: AUTHORED_PRESENT iff the window's BEST killer-
        position score cleared match_floor at any point; else OWN_DEATH if the best VICTIM-position score
        cleared it; else UNVERIFIABLE. None if the window had no members (nothing to resolve).

        NAMING NOTE: this victim-position resolution is deliberately named OWN_DEATH — own handle in the
        VICTIM slot means YOU died. The per-crop path (classify_panel / AuthorshipVerdict) still labels the
        same event OWN_KILL_UNBOUND, a token conflated at the enum level with the OCR oracle's genuine
        'own-kill not lag-bound' meaning (killfeed_authorship.py:43). That broader enum rename touches
        loop 1's classify API + the OCR oracle's distinct kill-meaning and is a flagged follow-up; here we
        only rename the string this composite owns, so the loop-2 death trigger reads honestly."""
        if self._win_members == 0:
            return None
        self._composite_windows += 1
        if self._win_best_killer >= self.match_floor:
            verdict, score = "AUTHORED_PRESENT", self._win_best_killer
            self._composite_authored += 1
        elif self._win_best_victim >= self.match_floor:
            verdict, score = "OWN_DEATH", self._win_best_victim
        else:
            verdict, score = "UNVERIFIABLE", max(self._win_best_killer, self._win_best_victim, 0.0)
        return {"ts_ms": round(now_ms, 1), "verdict": verdict, "composite_score": round(float(score), 4),
                "window_members": self._win_members, "anchor": self.anchor_id,
                "window_gate_ms": round(self._window_gate_ms, 1),
                "window_end_ms": round(self._window_end_ms, 1),
                # death-row appearance anchor (None if no victim obs) — lets loop 2 record the confirmation
                # lag so a confirmation-gated settle_ts_ms is normalizable to the death instant offline.
                "victim_first_ms": (round(self._win_victim_first_ms, 1)
                                    if self._win_victim_first_ms >= 0.0 else None)}

    def _reset_window(self) -> None:
        self._win_best_killer = -1.0
        self._win_best_victim = -1.0
        self._win_victim_first_ms = -1.0
        self._win_members = 0
        self._win_resolved = True

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
            # Phase 1 — max-over-window composite (additive; does not replace inline_authored above)
            "inline_composite_authored": self._composite_authored,
            "inline_composite_windows": self._composite_windows,
        }


def now_ms() -> float:
    return time.time() * 1000.0


# ============================================================================================
# LOOP 2 — Death-Window Reactive Presence (oracle-in-training; corpus-only, NO verdict)
# ============================================================================================
# Consumes loop 1's DISCARDED victim-slot branch (own-handle in the feed VICTIM slot = "you died",
# structurally unambiguous — same own-handle anchor as the killer/AUTHORED case). On that trigger it
# measures whether natural controller (stick) activity CONTINUES through the death-cam/respawn window
# (a live human keeps fidgeting/navigating) vs the silence an idle controller in front of a replay
# would show — the INVERSE causal direction (screen -> input) from every input->screen channel.
#
# HONESTY: this is an oracle-in-training. It logs RAW measurements only (variance, range, settle-point).
# NO PRESENT/ABSENT/verdict field — calibration is future work, pending a real corpus (N=few tonight).

# Idle-stick std noise floor for settle detection. Grounded in the DualSense 8-bit stick's idle ADC
# noise (still stick ~128 +/- 1-2 LSB), env-overridable, and re-derivable offline from the raw
# variance/range this also logs. NOT a cold guess: measured live from the baseline segment refines it.
DEFAULT_STICK_NOISE_FLOOR = float(os.getenv("RETINA_DEATH_STICK_NOISE_FLOOR", "2.5"))   # LSB std
DEFAULT_DEATH_WINDOW_MS = float(os.getenv("RETINA_DEATH_WINDOW_MS", "4000"))
_SETTLE_SUBWIN_MS = 300.0     # rolling sub-window for the "activity" estimate used by settle detection


def _stick_settle_ts(samples, win_start_ms: float, noise_floor: float,
                     subwin_ms: float = _SETTLE_SUBWIN_MS):
    """Relative timestamp (ms from window start) where rx/ry activity FIRST drops below the noise floor
    AND stays below for the remainder of the window. Activity = rolling std of rx and ry over subwin_ms.
    Returns None if it never settles (distinct from settling at the window end). Pure."""
    if len(samples) < 3:
        return None
    import numpy as np
    ts = np.array([s[0] for s in samples], float)
    rx = np.array([s[1] for s in samples], float)
    ry = np.array([s[2] for s in samples], float)
    settle_rel = None
    for i in range(len(samples)):
        lo = ts[i] - subwin_ms
        m = ts <= ts[i]
        m &= ts >= lo
        if m.sum() < 2:
            continue
        active = max(float(rx[m].std()), float(ry[m].std()))
        if active < noise_floor:
            if settle_rel is None:
                settle_rel = ts[i] - win_start_ms      # candidate first-below
        else:
            settle_rel = None                          # rose back above -> not sustained; reset
    return None if settle_rel is None else round(float(settle_rel), 1)


@dataclass
class DeathWindowMonitor:
    """PURE state machine for the post-death stick-activity window. mark_death opens/RESTARTS a window
    (a second death inside an open window closes the first early with truncated=True, then opens fresh —
    never extend/merge, never drop); feed_stick accumulates rx/ry; a window closing (expiry or restart)
    RETURNS a raw corpus record for the caller to JSONL-append. No async / I/O / verdict."""
    window_ms: float = DEFAULT_DEATH_WINDOW_MS
    noise_floor: float = DEFAULT_STICK_NOISE_FLOOR
    _active: bool = field(default=False, init=False)
    _win_start_ms: float = field(default=0.0, init=False)
    _win_end_ms: float = field(default=0.0, init=False)
    _samples: list = field(default_factory=list, init=False)
    _crop_ref: Optional[str] = field(default=None, init=False)
    _death_anchor_ms: Optional[float] = field(default=None, init=False)   # victim-row first-seen ts (raw)
    _events: int = field(default=0, init=False)
    _last_settle_ts: Optional[float] = field(default=None, init=False)
    _last_truncated: bool = field(default=False, init=False)

    def _close(self, now_ms: float, truncated: bool) -> Optional[dict]:
        if not self._active:
            return None
        rec = self._build_record(now_ms, truncated)
        self._active = False
        self._samples = []
        self._events += 1
        self._last_settle_ts = rec.get("settle_ts_ms")
        self._last_truncated = truncated
        return rec

    def _build_record(self, now_ms: float, truncated: bool) -> dict:
        import numpy as np
        rx = np.array([s[1] for s in self._samples], float) if self._samples else np.array([])
        ry = np.array([s[2] for s in self._samples], float) if self._samples else np.array([])
        settle = _stick_settle_ts(self._samples, self._win_start_ms, self.noise_floor)
        return {
            "ts_ms": round(self._win_start_ms, 1),
            "window_ms": round(now_ms - self._win_start_ms, 1),        # actual (truncated windows < nominal)
            "nominal_window_ms": self.window_ms,
            "n_stick_samples": len(self._samples),
            "rx_var": (round(float(rx.var()), 3) if rx.size else None),
            "ry_var": (round(float(ry.var()), 3) if ry.size else None),
            "rx_range": (round(float(rx.max() - rx.min()), 1) if rx.size else None),
            "ry_range": (round(float(ry.max() - ry.min()), 1) if ry.size else None),
            "settle_ts_ms": settle,               # relative to window start; None = NEVER settled (!= end)
            "noise_floor": self.noise_floor,
            "truncated": truncated,               # True = a second death cut this window short
            "source_crop_ref": self._crop_ref,
            # RAW death-row-first-seen ts (None if unknown). The window OPENS at confirmation (composite
            # resolve = ts_ms), which is ~lag AFTER the death instant; confirmation lag = ts_ms -
            # death_anchor_ms, so a confirmation-gated settle_ts_ms is normalizable to the death instant.
            "death_anchor_ms": self._death_anchor_ms,
        }

    def mark_death(self, now_ms: float, crop_ref: Optional[str] = None,
                   death_anchor_ms: Optional[float] = None) -> Optional[dict]:
        """Own-death detected (victim-slot). RESTART semantics: if a window is open, close it early
        (truncated) and RETURN its record; then open a fresh window. Caller JSONL-appends any returned
        record. death_anchor_ms = the death-row-first-seen ts (set AFTER _close so the truncated prior
        record keeps ITS own anchor); recorded raw so the confirmation lag stays recoverable offline."""
        truncated_rec = self._close(now_ms, truncated=True) if self._active else None
        self._active = True
        self._win_start_ms = float(now_ms)
        self._win_end_ms = float(now_ms) + self.window_ms
        self._samples = []
        self._crop_ref = crop_ref
        self._death_anchor_ms = (float(death_anchor_ms) if death_anchor_ms is not None else None)
        return truncated_rec

    def feed_stick(self, now_ms: float, rx: float, ry: float) -> Optional[dict]:
        """Feed one rx/ry sample. If the window has expired, close it and RETURN its record (caller
        appends). No-op (returns None) when no window is active."""
        if not self._active:
            return None
        if now_ms >= self._win_end_ms:
            return self._close(now_ms, truncated=False)
        self._samples.append((float(now_ms), float(rx), float(ry)))
        return None

    def status_dict(self) -> dict:
        return {
            "death_window_enabled": True,
            "death_events": self._events,
            "death_window_active": self._active,
            "death_last_settle_ts_ms": self._last_settle_ts,
            "death_last_truncated": self._last_truncated,
        }
