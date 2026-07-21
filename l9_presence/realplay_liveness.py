"""Composite-B v0 — zero-injection real-play human-liveness evaluator (CANDIDATE, advisory).

The adversary-tested design from the A2A ASM-Loop `docs/a2a/real-play-liveness/` (8 rounds, grok
r08 verdict PASS residual-accepted). This module is the **PARTIAL-tier** composition logic ONLY:
a pure function over already-extracted window features that returns an advisory liveness verdict.

WHAT IT IS
  A human on a real controller emits involuntary, causally-coupled signals the bridge already
  captures read-only at ~1 kHz. This composes them into a verdict WITHOUT writing anything to the
  controller (zero injection — the L6B force-probe path is exactly what this routes around).

THE HONEST CEILING (grok r08 F19 — accepted design ceiling, do NOT quietly over-claim past it)
  A pure passive HID stream is inherently REPLAYABLE: with zero injection there is no challenge the
  stream must causally respond to, so a faithful 1x re-injection of a real human's recorded dump
  passes the physiology gates AND the device-clock rate lock. Therefore:
    * WITHOUT optical co-presence  -> max verdict PARTIAL_PRESENT (replay_resistant=False, advisory)
    * WITH optical co-presence     -> CONTINUOUS_PRESENT (replay_resistant=True)
  This module does NOT compute optical consistency (that is Thesis C / the retina-killfeed surface,
  a separate future module). It only TIERS on an injected `optical_consistent` flag. So on its own,
  this v0 can only ever return PARTIAL_PRESENT or below — CONTINUOUS requires a real optical checker
  to pass `optical_consistent=True`. That is the point, not a limitation.

DISCIPLINE (all pinned by the design + tests)
  * Advisory only. Never maps to tournament CERTIFY/BLOCK hard codes. `advances_poep_enabled=False`.
  * Fail-closed: degraded capture / menu-only / sub-floor window / absent device ticks -> UNVERIFIABLE.
  * GIC non-mutation: this returns a verdict; it MUST NOT feed consecutive_clean / GIC / any grind
    chain. A parallel advisory counter is the only sanctioned aggregation (caller's responsibility).
  * Pure function, no bridge/hardware imports, deterministic — the leaf features are injected.
  * poep_enabled / L6B_ENABLED are untouched and irrelevant here (this is not a PoEP spike-reflex).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RealPlayVerdict(str, Enum):
    CONTINUOUS_PRESENT = "CONTINUOUS_PRESENT"   # human-shape + device-clock lock + optical (replay-resistant)
    PARTIAL_PRESENT = "PARTIAL_PRESENT"         # human-shape + device-clock lock, NO optical (replayable, advisory)
    UNVERIFIABLE = "UNVERIFIABLE"               # fail-closed: insufficient evidence is never a pass


# ---- CANDIDATE thresholds (hypotheses — measurement-gated per U2/U3, NOT calibrated) -------------
DEVICE_TICKS_PER_MS: float = 3000.0    # DualSense on-device sensor clock ~3 MHz (_DEVICE_TS_TICKS_PER_MS)
RATE_LOCK_EPSILON: float = 0.05        # d(device_ts)/d(wall) must be within [1±eps] of true rate  (H)
W_MIN_PARTIAL_S: float = 30.0          # H_W30 — below this -> UNVERIFIABLE                          (H)
W_MIN_CONTINUOUS_S: float = 120.0      # H_W120 — CONTINUOUS needs at least this window             (H)
F_MIN_GAMEPLAY: float = 0.30           # G2 fractional active-gameplay floor over W (F17)            (H)
TREMOR_BAND_HZ: tuple[float, float] = (8.0, 12.0)   # physiological tremor band                     (H)
TREMOR_MIN_BAND_POWER: float = 1e-6    # G3 lower bound — not frozen-DC / not full-band white        (H)
L2B_MIN_COUPLED_FRACTION: float = 0.55  # G4 — matches controller/l2b _COUPLED_FRACTION              (H)
L2B_MIN_PRESS_EVENTS: int = 15          # G4 — matches controller/l2b _MIN_PRESS_EVENTS              (H)


@dataclass(frozen=True, slots=True)
class WindowFeatures:
    """Already-extracted features for one evaluation window. Injected — this module captures nothing.

    Absent/unknown leaf -> pass None; the evaluator fails closed rather than inventing credit.
    """
    # G1 capture integrity
    capture_nominal: bool
    host_exclusive_usb_or_unknown: bool
    # G2 gameplay (fractional, per F17 — NOT binary taf>0)
    gameplay_active_fraction: Optional[float]      # None = pre-GAD / unknown -> no credit
    menu_detected: bool
    # G3 involuntary continuity
    tremor_peak_hz: Optional[float]
    tremor_band_power: Optional[float]
    # G4 causal binding
    l2b_coupled_fraction: Optional[float]          # coupling strength; None if < min presses / unknown
    press_events: int
    # G5 rhythm
    l5_macro_quantized: Optional[bool]             # True = timer-quantized macro flagged
    # anti-replay rail layer 1 — device clock vs wall clock
    device_ts_span_ticks: Optional[int]            # 0/None = ticks absent -> UNVERIFIABLE (no t_mono fallback)
    wall_span_ms: Optional[float]
    window_s: float
    # anti-replay rail layer 3 — optical co-presence (Thesis C). None/False -> cap at PARTIAL.
    optical_consistent: Optional[bool] = None


@dataclass(frozen=True, slots=True)
class RealPlayRecord:
    verdict: RealPlayVerdict
    reason: str
    gate_bitmap: dict = field(default_factory=dict)
    # pinned machine fields (grok F2/F14 — never a soft pass, never tournament-mapped)
    is_pass: bool = False
    advisory: bool = True
    maps_to_tournament_hard_code: bool = False
    advances_poep_enabled: bool = False
    streak_eligible: bool = False
    replay_resistant: bool = False
    display_tier: str = "amber"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict.value,
            "reason": self.reason,
            "gate_bitmap": dict(self.gate_bitmap),
            "is_pass": self.is_pass,
            "advisory": self.advisory,
            "maps_to_tournament_hard_code": self.maps_to_tournament_hard_code,
            "advances_poep_enabled": self.advances_poep_enabled,
            "streak_eligible": self.streak_eligible,
            "replay_resistant": self.replay_resistant,
            "display_tier": self.display_tier,
            "domain_tag": "QORTROLLER-REALPLAY-LIVE-v0",   # CANDIDATE — not FROZEN, no committed hash
        }


def _unverifiable(reason: str, bitmap: dict) -> RealPlayRecord:
    return RealPlayRecord(RealPlayVerdict.UNVERIFIABLE, reason, bitmap,
                          replay_resistant=False, streak_eligible=False, display_tier="grey")


def device_clock_rate_locked(span_ticks: Optional[int], wall_ms: Optional[float],
                             ticks_per_ms: float = DEVICE_TICKS_PER_MS,
                             eps: float = RATE_LOCK_EPSILON) -> Optional[bool]:
    """Anti-replay rail layer 1. Returns None if ticks absent (-> caller UNVERIFIABLE; NO t_mono
    fallback, F4). Else True iff d(device_ts)/d(wall) is within [1±eps] of the true tick rate."""
    if not span_ticks or span_ticks <= 0 or not wall_ms or wall_ms <= 0:
        return None
    observed = span_ticks / wall_ms
    lo, hi = ticks_per_ms * (1.0 - eps), ticks_per_ms * (1.0 + eps)
    return lo <= observed <= hi


def evaluate_realplay_liveness(f: WindowFeatures) -> RealPlayRecord:
    """Compose Composite-B v0 (PARTIAL-tier). Pure, deterministic, fail-closed.

    Order matters: fail-closed pre-conditions first (capture, ticks, window, menu), then the
    human-shape gates, then the optical tiering. CONTINUOUS is unreachable unless an external
    optical checker passes `optical_consistent=True`.
    """
    b: dict = {}

    # --- fail-closed pre-conditions ---
    b["G1_capture"] = bool(f.capture_nominal and f.host_exclusive_usb_or_unknown)
    if not b["G1_capture"]:
        return _unverifiable("capture degraded / host not exclusive-USB", b)

    rate_locked = device_clock_rate_locked(f.device_ts_span_ticks, f.wall_span_ms)
    b["layer1_device_ticks_present"] = rate_locked is not None
    if rate_locked is None:
        return _unverifiable("device-clock ticks absent — no t_mono fallback (F4)", b)
    b["layer1_rate_locked"] = bool(rate_locked)
    if not rate_locked:
        # ticks present but not tracking wall time -> cannot establish live-now; fail closed (F16/U2)
        return _unverifiable("device-clock rate not locked to wall clock (possible replay/RP artifact)", b)

    if f.window_s < W_MIN_PARTIAL_S:
        return _unverifiable(f"window {f.window_s:.0f}s < floor {W_MIN_PARTIAL_S:.0f}s", b)

    if f.menu_detected:
        return _unverifiable("menu-only window (GAD MENU_DETECTED)", b)
    # G2 fractional gate (F17) — None (pre-GAD) invents no credit
    b["G2_gameplay"] = f.gameplay_active_fraction is not None and f.gameplay_active_fraction >= F_MIN_GAMEPLAY
    if not b["G2_gameplay"]:
        return _unverifiable("active-gameplay fraction below floor or unknown (F17)", b)

    # --- human-shape gates (establish human-shaped, NOT live-now) ---
    b["G3_continuity"] = (
        f.tremor_peak_hz is not None
        and TREMOR_BAND_HZ[0] <= f.tremor_peak_hz <= TREMOR_BAND_HZ[1]
        and f.tremor_band_power is not None
        and f.tremor_band_power >= TREMOR_MIN_BAND_POWER
    )
    # G4 causal binding — press-gated (F6). N/A (too few presses) is not a fail, but caps at PARTIAL.
    if f.press_events < L2B_MIN_PRESS_EVENTS or f.l2b_coupled_fraction is None:
        b["G4_causal"] = None   # N/A
    else:
        b["G4_causal"] = f.l2b_coupled_fraction >= L2B_MIN_COUPLED_FRACTION
    # G5 rhythm — non-quantized is good; True quantized = fail
    b["G5_rhythm_ok"] = (f.l5_macro_quantized is False)

    # continuity must hold; a quantized-macro rhythm or absent tremor => not human-shaped enough
    if not b["G3_continuity"] or not b["G5_rhythm_ok"]:
        return _unverifiable("involuntary continuity / rhythm gate not satisfied", b)
    if b["G4_causal"] is False:
        return _unverifiable("causal binding present but not coupled (possible decoupled injection)", b)

    # --- optical tiering (grok F19/R-C9): optical MANDATORY for the replay-resistant verdict ---
    strong_shape = b["G3_continuity"] and b["G5_rhythm_ok"] and (b["G4_causal"] is True)
    b["optical_consistent"] = f.optical_consistent is True

    if (f.optical_consistent is True and strong_shape
            and f.window_s >= W_MIN_CONTINUOUS_S):
        return RealPlayRecord(
            RealPlayVerdict.CONTINUOUS_PRESENT,
            "human-shape + device-clock lock + optical co-presence (replay-resistant)",
            b, replay_resistant=True, display_tier="green",
        )

    # everything short of that is the honest pure-passive ceiling: PARTIAL, replayable, advisory
    return RealPlayRecord(
        RealPlayVerdict.PARTIAL_PRESENT,
        "human-shape + device-clock lock, no optical co-presence (replayable/advisory)",
        b, replay_resistant=False, display_tier="amber",
    )
