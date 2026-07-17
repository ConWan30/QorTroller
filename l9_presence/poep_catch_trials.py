"""PoEP catch trials (go / no-go) — FLIP-A ladder item 6 (round-18 bars).

Protocol (host-trusted presence vs always-fire macros):
  - GO:    real R2 force at CSPRNG time; human should react; live-verify may PASS.
  - NO_GO: same arm/delay/nonce schedule, **no force write**; a relaxed human should NOT
           produce a peak>=floor "response". An always-fire bot that still emits an in-band
           forged response is CAUGHT.

Bars (round-18, not a flip):
  - go:no_go ratio default 4:1 (20% catch)
  - human false-alarm on NO_GO: peak>=floor  <= 5% of no-go trials
  - always-fire bot catch rate on NO_GO: >= 90%

Pure scoring is offline/simulatable. Live capture wires stimulus on/off.
poep_enabled stays False — catch trials raise the bar; they do not alone authorize the flip.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Iterable, Literal, Optional

TrialKind = Literal["GO", "NO_GO"]

DEFAULT_GO_NO_GO_RATIO = 4  # go:no_go = 4:1
PEAK_FLOOR_LSB = 1000.0
HUMAN_FA_BUDGET = 0.05       # <=5% of no-go trials may show peak>=floor
ALWAYS_FIRE_CATCH_BAR = 0.90  # >=90% of no-go trials catch always-fire bot


def plan_trial_kinds(
    n: int,
    *,
    go_per_no_go: int = DEFAULT_GO_NO_GO_RATIO,
    seed: int | None = None,
    rng: random.Random | None = None,
) -> list[TrialKind]:
    """Build a mixed schedule with ~1/(go_per_no_go+1) NO_GO trials, shuffled.

    For n < (go_per_no_go+1), guarantee at least one NO_GO when n>=5; for small n
    use ceil proportion.
    """
    if n <= 0:
        return []
    r = rng or random.Random(seed if seed is not None else 0)
    period = max(1, int(go_per_no_go) + 1)
    n_nogo = max(1, n // period) if n >= period else (1 if n >= 5 else 0)
    if n_nogo > n:
        n_nogo = n
    n_go = n - n_nogo
    kinds: list[TrialKind] = (["GO"] * n_go) + (["NO_GO"] * n_nogo)
    r.shuffle(kinds)
    return kinds


@dataclass(frozen=True)
class TrialScore:
    kind: TrialKind
    peak_lsb: float
    latency_ms: float | None
    live_verify_ok: bool
    # Human-facing outcome for this trial under catch rules
    human_ok: bool
    reason: str
    # Always-fire bot: would this trial catch a bot that always forges in-band?
    always_fire_caught: bool


def score_trial(
    kind: TrialKind,
    *,
    peak_lsb: float,
    latency_ms: float | None,
    live_verify_ok: bool,
    peak_floor: float = PEAK_FLOOR_LSB,
) -> TrialScore:
    """Score one trial for human honesty + always-fire catch potential.

    GO: human_ok if live_verify_ok (or soft: peak>=floor and latency present — we use verify).
    NO_GO: human_ok if peak < floor (no false "response"); twitchy peak>=floor = FA.
    Always-fire bot on NO_GO: caught if we would reject a forged in-band response
    (protocol: any peak>=floor OR live_verify that claimed a GO on a NO_GO is bot-like;
    for simulation, always-fire always produces peak>=floor + verify-shaped response → caught).
    """
    pk = float(peak_lsb or 0.0)
    lat = float(latency_ms) if latency_ms is not None and latency_ms > 0 else None

    if kind == "GO":
        human_ok = bool(live_verify_ok)
        reason = "go_verify_pass" if human_ok else "go_verify_fail"
        # Always-fire on GO is not "caught" by catch logic (it may look human)
        always_fire_caught = False
        return TrialScore(
            kind=kind, peak_lsb=pk, latency_ms=lat, live_verify_ok=live_verify_ok,
            human_ok=human_ok, reason=reason, always_fire_caught=always_fire_caught,
        )

    # NO_GO
    false_positive = pk >= peak_floor
    human_ok = not false_positive
    reason = "nogo_clean" if human_ok else "nogo_human_fa_peak"
    # Always-fire bot always posts peak>=floor on no-go → caught by rule
    always_fire_caught = True  # structural: protocol rejects no-go with response claim
    if false_positive:
        # human FA; bot would also be "caught" (session flags no-go response)
        always_fire_caught = True
    return TrialScore(
        kind=kind, peak_lsb=pk, latency_ms=lat, live_verify_ok=live_verify_ok,
        human_ok=human_ok, reason=reason, always_fire_caught=always_fire_caught,
    )


def score_session(scores: Iterable[TrialScore], *, mode: str = "human") -> dict:
    """Aggregate session metrics.

    mode=human: report human FA on NO_GO (always-fire catch is harness-only).
    mode=always_fire_bot: report catch rate = fraction of NO_GO with peak>=floor (bot detected).
    """
    scores = list(scores)
    nogo = [s for s in scores if s.kind == "NO_GO"]
    go = [s for s in scores if s.kind == "GO"]
    n_nogo = len(nogo)
    n_fa = sum(1 for s in nogo if not s.human_ok)
    fa_rate = (n_fa / n_nogo) if n_nogo else None
    n_go_ok = sum(1 for s in go if s.human_ok)
    out = {
        "mode": mode,
        "n_trials": len(scores),
        "n_go": len(go),
        "n_nogo": n_nogo,
        "n_go_human_ok": n_go_ok,
        "go_human_pass_rate": (n_go_ok / len(go)) if go else None,
        "n_nogo_human_fa": n_fa,
        "human_fa_rate": fa_rate,
        "human_fa_budget": HUMAN_FA_BUDGET,
        "human_fa_ok": (fa_rate is None) or (fa_rate <= HUMAN_FA_BUDGET),
        "poep_enabled": False,
        "note": "Catch gate is necessary for FLIP-A consideration, not sufficient alone.",
    }
    if mode == "always_fire_bot":
        # Bot always posts peak>=floor → human_ok False on NO_GO = caught
        catch_rate = (n_fa / n_nogo) if n_nogo else None
        out["always_fire_catch_rate"] = catch_rate
        out["always_fire_catch_bar"] = ALWAYS_FIRE_CATCH_BAR
        out["always_fire_catch_ok"] = (catch_rate is not None) and (
            catch_rate >= ALWAYS_FIRE_CATCH_BAR
        )
    return out


def simulate_always_fire_on_schedule(
    kinds: list[TrialKind],
    *,
    peak_floor: float = PEAK_FLOOR_LSB,
) -> list[TrialScore]:
    """Always-fire bot: forges peak>=floor + live_verify_ok=True on every trial.

    On GO it looks like a pass; on NO_GO score_trial marks FA / catch.
    """
    out: list[TrialScore] = []
    for k in kinds:
        # Bot always claims a strong in-band response
        out.append(
            score_trial(
                k,
                peak_lsb=peak_floor + 500.0,
                latency_ms=200.0,
                live_verify_ok=True,  # forged commitment would pass if host accepted GO semantics
                peak_floor=peak_floor,
            )
        )
    return out


def simulate_honest_human_on_schedule(
    kinds: list[TrialKind],
    *,
    peak_floor: float = PEAK_FLOOR_LSB,
    go_pass_rate: float = 0.85,
    nogo_fa_rate: float = 0.02,
    seed: int = 0,
) -> list[TrialScore]:
    """Stochastic honest human: usually passes GO, rarely FA on NO_GO."""
    rng = random.Random(seed)
    out: list[TrialScore] = []
    for k in kinds:
        if k == "GO":
            ok = rng.random() < go_pass_rate
            out.append(
                score_trial(
                    k,
                    peak_lsb=(peak_floor + 800.0) if ok else 200.0,
                    latency_ms=280.0 if ok else 500.0,
                    live_verify_ok=ok,
                    peak_floor=peak_floor,
                )
            )
        else:
            fa = rng.random() < nogo_fa_rate
            out.append(
                score_trial(
                    k,
                    peak_lsb=(peak_floor + 200.0) if fa else 100.0,
                    latency_ms=150.0 if fa else None,
                    live_verify_ok=False,
                    peak_floor=peak_floor,
                )
            )
    return out


def schedule_commitment_tag(kinds: list[TrialKind]) -> str:
    """Stable digest of the go/no-go schedule for audit binding (local, not FROZEN)."""
    body = "|".join(kinds).encode()
    return hashlib.sha256(b"QORTROLLER-POEP-CATCH-SCHED-v0|" + body).hexdigest()[:16]
