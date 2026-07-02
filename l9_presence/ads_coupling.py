"""l2_ads — ADS (aim-down-sights) coupling channel. The SECOND anti-splice channel per CHANNEL_REGISTRY.

WHY THIS CHANNEL EXISTS
The killfeed authorship channel (loop 1) proves an own-handle kill row appeared while firing — but a
replay-splice defeats it: the forger replays their own archived gameplay (real kill rows) while pressing R2
live, and the composite fires AUTHORED on the timing coincidence (docs/composite-splice-far-2026-07-01.md —
simulated per-session FAR 0.75-1.0, and a MEASURED live splice hit on the one event that survived
re-capture). Authorship-alone is not cert-grade against splice.

l2_ads binds a LIVE controller input to a LIVE screen response the replay cannot supply on demand, at THREE
points, so the eventual adversarial pairing is a three-point alignment problem for the splicer:
  (1) ONSET   — press L2, the center-ROI transitions to a SCOPED view within the tight (0,300)ms window;
  (2) HELD    — the scope PERSISTS while L2 stays down (a continuous binding, not one instant); and
  (3) RELEASE — on L2 release, the scope EXITS within render latency.
A replayed screen shows scope transitions at RECORDING times, decoupled from the attacker's live L2 — so
all three fail on a splice. The tight window is the parametric lever from the splice doc made concrete
(300ms vs R2's 5000ms), so coincidence coverage rho is tiny.

NOT the refuted continuous coupling. The B1/B2/geometric channels used causal-lag Pearson over whole
timeseries and were refuted vs active-spectate-spam (FAR 0.46, cycle 56). l2_ads is a DISCRETE,
event-triggered transition + a held-STATE + a release-EXIT — a specific bistable response bound to a
specific input, closer to the killfeed authorship model than to continuous correlation.

SCAFFOLD — HONEST ABSTAIN + RAW-FIRST CORPUS
No center-ROI ADS data exists yet (the archive is killfeed panel-ROI crops), so the transition-magnitude
threshold is UNCALIBRATED. With no threshold the emitted verdict is ADS_ABSTAIN_UNCALIBRATED — it NEVER
fabricates a coupling claim. But the record is RAW-FIRST: every event stores its onset/held/exit center-ROI
sample sequences, so when a real ADS-capture session sets the threshold, the transition magnitude, held
interruptions, held-scoped fraction, and scope-exit latency are all DERIVABLE from stored signal — no
retroactive schema migration. enabled flips True in CHANNEL_REGISTRY only after calibration AND l2_ads's own
adversarial splice-pairing (the standing 'no genuine claim without its forgery attempt' discipline).

NAMING: the emitted claim is deliberately NARROW — ADS_TRANSITION_BOUND means only 'a scoped transition was
time-bound to this L2 input', NOT presence. PRESENT/ABSENT are avoided because PoEP/PoCP own them with
heavier (presence/causal) meanings; this channel's calibrated claim is smaller than either.

This module is pure: no I/O, no capture, no cert wiring; the center-ROI scalar is fed in by the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# Emitted verdicts — deliberately narrow (a screen transition bound to the L2 input), NOT presence claims.
ADS_TRANSITION_BOUND = "ADS_TRANSITION_BOUND"          # scoped transition was time-bound to the L2 onset
ADS_TRANSITION_ABSENT = "ADS_TRANSITION_ABSENT"        # no bound transition (the anti-splice negative)
ADS_ABSTAIN_UNCALIBRATED = "ADS_ABSTAIN_UNCALIBRATED"  # no calibrated opinion yet (honest default)

DEFAULT_L2_THRESHOLD = 40                 # L2 rising edge = ADS engage (matches DEFAULT_R2_THRESHOLD)
DEFAULT_ADS_WINDOW_MS = (0.0, 300.0)      # tight onset transition window per CHANNEL_REGISTRY l2_ads entry
DEFAULT_EXIT_WINDOW_MS = 500.0            # post-release window to observe the scope exit
DEFAULT_MAX_HOLD_MS = 8000.0             # cap event latency/size for long scoped holds (emit + truncate)
DEFAULT_MAX_SEQ = 400                     # cap stored raw samples per phase (bounds JSONL row size)


@dataclass
class AdsTransitionDetector:
    """Pluggable, self-referential ADS-transition detector — NO template, NO training data. A scope overlay
    is a large center-ROI shift, so 'scoped' means the scalar moved from its at-onset baseline by at least
    `threshold`. UNCALIBRATED by default (threshold None) -> abstains. A real ADS session sets `threshold`
    empirically, exactly as L4 thresholds are set against a corpus."""
    threshold: Optional[float] = None

    def is_scoped(self, baseline: Optional[float], scalar: float) -> Optional[bool]:
        """True/False if calibrated; None if uncalibrated or no baseline (caller treats None as abstain)."""
        if self.threshold is None or baseline is None:
            return None
        return abs(float(scalar) - float(baseline)) >= float(self.threshold)

    def verdict(self, baseline: Optional[float], onset_samples: list[float]) -> str:
        if self.threshold is None:
            return ADS_ABSTAIN_UNCALIBRATED
        if baseline is None or not onset_samples:
            return ADS_TRANSITION_ABSENT
        mag = max(abs(float(s) - float(baseline)) for s in onset_samples)
        return ADS_TRANSITION_BOUND if mag >= float(self.threshold) else ADS_TRANSITION_ABSENT


@dataclass
class AdsCouplingMonitor:
    """PURE complete-event state machine for L2 press->hold->release ADS coupling. Emits ONE raw-first
    record per event on release (or a max-hold timeout), capturing all three binding points so every derived
    metric is computable at calibration from stored signal. Mirrors the killfeed monitors: no async/I/O, no
    fabricated verdict; feed() RETURNS a record when an event completes, else None."""
    window_ms: tuple = DEFAULT_ADS_WINDOW_MS
    exit_window_ms: float = DEFAULT_EXIT_WINDOW_MS
    max_hold_ms: float = DEFAULT_MAX_HOLD_MS
    l2_threshold: int = DEFAULT_L2_THRESHOLD
    max_seq: int = DEFAULT_MAX_SEQ
    detector: AdsTransitionDetector = field(default_factory=AdsTransitionDetector)

    _l2_prev: int = field(default=0, init=False)
    _phase: str = field(default="IDLE", init=False)          # IDLE / ONSET / HELD / EXIT
    _onset_ts: float = field(default=0.0, init=False)
    _onset_end: float = field(default=0.0, init=False)
    _baseline: Optional[float] = field(default=None, init=False)
    _onset_samples: list = field(default_factory=list, init=False)   # scalars in the (0,300)ms window
    _held_seq: list = field(default_factory=list, init=False)        # [rel_ms, scalar] during hold
    _release_ts: Optional[float] = field(default=None, init=False)
    _exit_seq: list = field(default_factory=list, init=False)        # [rel_ms, scalar] after release
    _exit_end: float = field(default=0.0, init=False)
    _events: int = field(default=0, init=False)
    _last_verdict: Optional[str] = field(default=None, init=False)

    def feed(self, l2_value: int, center_roi_scalar: Optional[float], now_ms: float) -> Optional[dict]:
        l2 = int(l2_value or 0)
        rising = l2 >= self.l2_threshold and self._l2_prev < self.l2_threshold
        falling = l2 < self.l2_threshold and self._l2_prev >= self.l2_threshold
        s = center_roi_scalar
        rec = None

        if rising and self._phase in ("IDLE", "EXIT"):
            if self._phase == "EXIT":                        # re-press mid-exit -> close the prior event first
                rec = self._emit(now_ms)
            self._start(now_ms, s)
        elif self._phase == "ONSET":
            if s is not None and now_ms <= self._onset_end and len(self._onset_samples) < self.max_seq:
                self._onset_samples.append(float(s))
            if now_ms > self._onset_end:
                self._phase = "HELD"                         # onset window closed; hold begins
                if s is not None and len(self._held_seq) < self.max_seq:   # keep the boundary sample
                    self._held_seq.append([round(now_ms - self._onset_ts, 1), round(float(s), 4)])
            if falling:                                      # very short tap -> straight to exit
                self._begin_exit(now_ms)
        elif self._phase == "HELD":
            if s is not None and len(self._held_seq) < self.max_seq:
                self._held_seq.append([round(now_ms - self._onset_ts, 1), round(float(s), 4)])
            if falling:
                self._begin_exit(now_ms)
            elif now_ms - self._onset_ts >= self.max_hold_ms:   # long scoped hold -> emit truncated, no exit
                rec = self._emit(now_ms, hold_truncated=True)
        elif self._phase == "EXIT":
            if s is not None and now_ms <= self._exit_end and len(self._exit_seq) < self.max_seq:
                self._exit_seq.append([round(now_ms - self._release_ts, 1), round(float(s), 4)])
            if now_ms > self._exit_end:
                rec = self._emit(now_ms)

        self._l2_prev = l2
        return rec

    def _start(self, now_ms: float, s: Optional[float]) -> None:
        lo, hi = self.window_ms
        self._phase = "ONSET"
        self._onset_ts = now_ms
        self._onset_end = now_ms + hi
        self._baseline = s
        self._onset_samples = [] if s is None else [float(s)]
        self._held_seq = []
        self._release_ts = None
        self._exit_seq = []

    def _begin_exit(self, now_ms: float) -> None:
        self._phase = "EXIT"
        self._release_ts = now_ms
        self._exit_end = now_ms + self.exit_window_ms
        self._exit_seq = []

    def _emit(self, now_ms: float, hold_truncated: bool = False) -> dict:
        self._events += 1
        verdict = self.detector.verdict(self._baseline, self._onset_samples)
        self._last_verdict = verdict
        cal = self.detector.threshold is not None
        # derived-when-calibrated (None when not); raw sequences below make them re-derivable at any threshold
        held_scoped_frac = held_interruptions = scope_exit_latency = None
        if cal and self._held_seq:
            flags = [self.detector.is_scoped(self._baseline, v) for _, v in self._held_seq]
            n_scoped = sum(1 for f in flags if f)
            held_scoped_frac = round(n_scoped / len(flags), 3)
            # interruption = a scoped->unscoped transition within the hold (distinguishes one clean dip from
            # flicker at the SAME aggregate fraction)
            held_interruptions = sum(1 for a, b in zip(flags, flags[1:]) if a and b is False)
        if cal and self._release_ts is not None and self._exit_seq:
            for rel, v in self._exit_seq:                    # first post-release sample back under threshold
                if self.detector.is_scoped(self._baseline, v) is False:
                    scope_exit_latency = rel
                    break
        rec = {
            "onset_ts_ms": round(self._onset_ts, 1),
            "verdict": verdict,
            "calibrated": cal,
            "threshold": self.detector.threshold,
            "baseline": (round(self._baseline, 4) if self._baseline is not None else None),
            "onset_window_members": len(self._onset_samples),
            "transition_magnitude": (round(max((abs(x - self._baseline) for x in self._onset_samples),
                                               default=0.0), 4) if self._baseline is not None else None),
            # HELD binding — raw sequence (interruptions/frac derivable at any threshold) + derived-if-cal
            "held_seq": self._held_seq,
            "held_samples": len(self._held_seq),
            "held_scoped_frac": held_scoped_frac,
            "held_interruptions": held_interruptions,
            "hold_truncated": hold_truncated,
            # RELEASE binding — raw post-release sequence + derived exit latency (None if uncal/not-exited)
            "release_ts_ms": (round(self._release_ts, 1) if self._release_ts is not None else None),
            "exit_seq": self._exit_seq,
            "scope_exit_latency_ms": scope_exit_latency,
        }
        self._phase = "IDLE"
        self._baseline = None
        return rec

    def status_dict(self) -> dict:
        return {
            "ads_channel_enabled": True,
            "ads_calibrated": self.detector.threshold is not None,
            "ads_events": self._events,
            "ads_last_verdict": self._last_verdict,
        }
