"""QorTroller anti-cheat detector — CANDIDATE, ADVISORY (ASM-Loop r02+r04).

Naming (F10): "exclusive" here means HARDWARE-CLASS exclusivity to the certified DualSense Edge (silicon
clock + adaptive-trigger haptic + device-clock binding), NOT a shipped/unbreakable product anti-cheat. This
is a single-operator voluntary-reaction liveness CANDIDATE that emits an advisory verdict and gates nothing.


Session-level live-human detector from a sequence of nonce-bound R2-onset haptic challenges. It composes the
per-fire verdict `detect_voluntary_go` (gold read-at-fire t0 + real R2 reaction + lat in the human band) with
a MULTI-CHALLENGE aggregator whose anti-bot strength comes from UNOBSERVABLE-CHALLENGE COMPOUNDING, not from
reaction consistency:

  The adaptive-trigger buzz is a PHYSICAL event on the certified DualSense Edge that a bot's software cannot
  observe. A fire-time-BLIND bot can only GUESS when to react, so per challenge its press-vs-fire latency is
  ~Unif[0,ISI]: p_go = band/ISI (2.67% for an 80 ms band at a 3 s ISI) AND p_fast = GO_LO/ISI (a sub-floor
  press that trips SUSPECTED_BOT). The TRUE session false-accept probability is the MULTINOMIAL
  P(n_go >= threshold AND n_sub_floor == 0) = sum C(N,i) p_go^i p_other^(N-i) (blind_bot_far); the binomial
  tail P(Bin(N,p_go) >= threshold) is only a LOOSE UPPER BOUND (it counts sub-floor paths the ladder catches).
  This is small — not "astronomically" universally — while a live human who FEELS each buzz clears it. The
  FAR is NON-MONOTONE in both N (worst-in-N at the K-floor crossover N~=25 AT FIXED ISI) and ISI; the JOINT
  (N,ISI) worst case is (band/GO_HI)^K = 3.2e-4 at N=K, ISI=GO_HI (see worst_case_true_far / the audit).

VERDICTS (fail-closed): HUMAN_PRESENT / SUSPECTED_BOT / DEAD_FEED / INSUFFICIENT. This module EMITS a verdict
and gates NOTHING — poep_enabled / L6B / L6_CHALLENGES stay False; no on-chain, no presence-API flip.

CLAIM CEILING: voluntary-reaction liveness CANDIDATE on a single-operator provisional band; hardware-class
"exclusive" to the certified Edge (silicon-clock + adaptive-trigger haptic + device-clock binding), NOT
"unbreakable". The reported FAR is against a fire-time-BLIND bot ONLY. A bot that OBSERVES the fire time
(host APIs / hardware injector) defeats the compounding and is a PUBLISHED rig/crypto residual — its defense
is HMAC(nonce||t0||onset) frame-commitment (a named follow-on), not this module. sigma is NOT anti-bot by
itself; the strength is the unobservable-challenge compounding.
"""
from __future__ import annotations

import math
import os
import statistics
import sys
from typing import Any

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
from poep_r2onset_adversarial import detect_voluntary_go, GO_LO_MS, GO_HI_MS  # noqa: E402

K_REQUIRED_DEFAULT = 5          # absolute in-band GO floor to assert HUMAN_PRESENT (operator r01 default)
RATE_MIN_DEFAULT = 0.20         # GO-rate floor: the threshold SCALES with N. NOTE (F15): this makes the FAR
                                # CONCENTRATE downward ONLY once the rate term binds (N >~ 25); while the K
                                # floor binds the FAR RISES with N. The FAR is non-monotone, not "shrinking".
DEFAULT_ISI_MS = 3000.0         # inter-stimulus interval assumed for the blind-bot FAR
_BAND_MS = GO_HI_MS - GO_LO_MS


def blind_bot_probs(isi_ms: float = DEFAULT_ISI_MS) -> tuple[float, float]:
    """Per-challenge (p_GO, p_SUB_FLOOR) of a fire-time-BLIND uniform-timing bot: its press latency vs the
    UNKNOWN fire is ~Unif[0, ISI]. INTERSECTION measure (F18) so p_go+p_fast <= 1 even for ISI < GO_HI:
    p_go = |(GO_LO, min(GO_HI,ISI)]| / ISI ; p_fast = min(GO_LO, ISI) / ISI."""
    if isi_ms <= 0:
        return 1.0, 0.0
    p_go = max(0.0, (min(GO_HI_MS, isi_ms) - GO_LO_MS)) / isi_ms
    p_fast = min(GO_LO_MS, isi_ms) / isi_ms
    return p_go, p_fast


def blind_bot_p(isi_ms: float = DEFAULT_ISI_MS) -> float:
    """Per-challenge in-band GO rate of a fire-time-BLIND bot = band_width / ISI."""
    return blind_bot_probs(isi_ms)[0]


def binom_tail_ge(n: int, k: int, p: float) -> float:
    """P(Binomial(n, p) >= k). LOOSE UPPER BOUND on the blind-bot false-accept rate — it counts paths that
    ALSO contain sub-floor presses, which the session ladder actually catches as SUSPECTED_BOT (F2)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return sum(math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i)) for i in range(k, n + 1))


def blind_bot_far(n: int, k: int, isi_ms: float = DEFAULT_ISI_MS) -> float:
    """TRUE blind-bot false-accept probability for a uniform-timing bot = P(>= k GOs AND ZERO sub-floor).
    HUMAN_PRESENT requires n_go>=k AND n_sub_floor==0, so every non-GO press must be OTHER (not FAST):
    sum_{i=k}^{n} C(n,i) p_go^i * p_other^(n-i), p_other = 1 - p_go - p_fast. Always <= the binomial UB.
    NON-MONOTONE in ISI (F16/F19): rapid cadence raises BOTH p_go AND p_fast. At LARGE fixed N the sub-floor
    trap lowers the TRUE FAR at short ISI; but the JOINT adversary picks SMALL N + ISI near GO_HI, where the
    TRUE FAR is MAXIMAL = (band/GO_HI)^K = 3.2e-4 at N=K=5, ISI=GO_HI=400ms (see worst_case_true_far). Do NOT
    read 'short ISI is safer' — the joint worst case IS a short ISI."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    p_go, p_fast = blind_bot_probs(isi_ms)
    p_other = max(0.0, 1.0 - p_go - p_fast)
    return sum(math.comb(n, i) * (p_go ** i) * (p_other ** (n - i)) for i in range(k, n + 1))


def worst_case_true_far(k_required: int = K_REQUIRED_DEFAULT, rate_min: float = RATE_MIN_DEFAULT,
                        isi_hi_ms: float = 4000.0, isi_step_ms: float = 5.0,
                        n_max: int = 80) -> tuple[int, float, float]:
    """JOINT worst-case TRUE FAR over (N, ISI) — the honest security number (F19). Analytically it is
    (band/GO_HI)^K at ISI=GO_HI, N=K: p_go is MAXIMAL there (= band/GO_HI) and p_other=0 forces every
    non-GO press to be sub-floor, so the only HUMAN_PRESENT path is ALL-K-GO. Grid-verified (the grid
    includes ISI=GO_HI exactly). Returns (n, isi_ms, far). Do NOT publish a slice as the envelope max."""
    best = (0, 0.0, 0.0)
    isi = GO_HI_MS                                     # the analytic argmax; then sweep above it
    grid = [GO_HI_MS]
    x = GO_LO_MS + 1.0
    while x <= isi_hi_ms:
        grid.append(x)
        x += isi_step_ms
    for isi in grid:
        for n in range(1, n_max):
            f = blind_bot_far(n, go_threshold(n, k_required, rate_min), isi)
            if f > best[2]:
                best = (n, isi, f)
    return best


def observed_isi_ms(recs: list[dict]) -> float | None:
    """Median gap (ms) between consecutive fires from probe_ts_mono. None if unavailable. CAVEAT: if the dir
    concatenates multiple sessions the gaps between sessions inflate this — treat as advisory context, not a
    per-session cadence guarantee."""
    ts = sorted(float(r["probe_ts_mono"]) for r in recs
                if isinstance(r, dict) and r.get("probe_ts_mono") is not None)
    gaps = [(ts[i + 1] - ts[i]) * 1000.0 for i in range(len(ts) - 1) if ts[i + 1] > ts[i]]
    return statistics.median(gaps) if gaps else None


def go_threshold(n: int, k_required: int = K_REQUIRED_DEFAULT,
                 rate_min: float = RATE_MIN_DEFAULT) -> int:
    """In-band GOs needed to assert HUMAN_PRESENT over N challenges = max(K floor, ceil(rate_min * N)).
    The rate term makes the required count SCALE with N. NOTE (F3): the blind-bot FAR is NON-MONOTONE in N
    — while the K floor binds (N <~ 25) it RISES with N; only once the rate term binds (N >~ 25) does it
    CONCENTRATE downward. The true worst case is at the crossover (~N=25), not at large N."""
    return max(k_required, math.ceil(rate_min * n)) if n > 0 else k_required


def detect_session(recs: list[dict], k_required: int = K_REQUIRED_DEFAULT,
                   rate_min: float = RATE_MIN_DEFAULT, isi_ms: float = DEFAULT_ISI_MS) -> dict[str, Any]:
    """Emit a session-level anti-cheat verdict from a list of nonce-bound fire dumps. Gates nothing."""
    per = [detect_voluntary_go(r) for r in recs]
    n = len(recs)
    n_go = sum(1 for v in per if v["verdict"] == "GO")
    n_soft = sum(1 for v in per if v["verdict"] == "SOFT_TOO_SLOW")
    n_fast = sum(1 for v in per if v["verdict"] == "REJECT_TOO_FAST")
    n_noreact = sum(1 for v in per if v["verdict"] == "REJECT_NO_REACTION")
    n_badref = sum(1 for v in per if v["verdict"] == "REJECT")

    thr = go_threshold(n, k_required, rate_min)
    obs_isi = observed_isi_ms(recs)
    p_go, p_fast = blind_bot_probs(isi_ms)                                 # FAR at the ASSUMED (stated) ISI
    far_true = blind_bot_far(n, thr, isi_ms) if n > 0 else 1.0             # TRUE multinomial (zero sub-floor)
    far_binom_ub = binom_tail_ge(n, thr, p_go) if n > 0 else 1.0           # loose upper bound (F2)
    go_rate = (n_go / n) if n else 0.0

    # fail-closed verdict ladder
    if n == 0:
        verdict, why = "INSUFFICIENT", "no challenges in the session window"
    elif n_fast > 0:
        # a press below the SINGLE-OPERATOR PROVISIONAL floor. Heuristic bot signal, NOT a proof of
        # non-humanity (F5): a population human faster than the floor would trip this -> a known residual.
        verdict, why = "SUSPECTED_BOT", (
            f"{n_fast} press(es) below the provisional floor {GO_LO_MS:.0f}ms (heuristic, not proof)")
    elif n < k_required:
        verdict, why = "INSUFFICIENT", f"only {n} challenges (< K={k_required}); keep challenging"
    elif n_go >= thr:
        verdict, why = "HUMAN_PRESENT", (
            f"{n_go} in-band GOs >= threshold {thr} (=max(K={k_required}, {rate_min:.0%}*N)); "
            f"blind-bot FAR={far_true:.2e} (true) <= {far_binom_ub:.2e} (binom UB) at ISI={isi_ms:.0f}ms")
    elif n_noreact >= n and n_go == 0:
        # no reaction on ANY challenge -> dead feed OR a non-reacting bot; indistinguishable offline -> not human
        verdict, why = "DEAD_FEED", "no reaction observed on any challenge (dead feed or non-reacting bot)"
    else:
        verdict, why = "INSUFFICIENT", (
            f"{n_go} in-band GOs < threshold {thr}; keep challenging (not yet human, not clearly a bot)")

    return {
        "schema": "qortroller-anticheat-v0",
        "verdict": verdict,
        "why": why,
        "n_challenges": n,
        "n_go": n_go, "n_soft_slow": n_soft, "n_sub_floor": n_fast,
        "n_no_reaction": n_noreact, "n_bad_reference": n_badref,
        "k_required": k_required, "rate_min": rate_min, "go_threshold": thr,
        "go_rate": round(go_rate, 3),
        "assumed_isi_ms": isi_ms,
        "observed_isi_ms": round(obs_isi, 1) if obs_isi is not None else None,
        "blind_bot_p_go": round(p_go, 5), "blind_bot_p_sub_floor": round(p_fast, 5),
        "blind_bot_far": far_true,               # TRUE multinomial FALSE-ACCEPT vs a fire-time-BLIND bot
        "blind_bot_far_binom_ub": far_binom_ub,  # loose upper bound (counts sub-floor paths -> SUSPECTED_BOT; F2)
        "far_note": ("TRUE FAR at the ASSUMED ISI; NON-MONOTONE in ISI (F16/F19). At large fixed N a short "
                     "ISI LOWERS the TRUE FAR (sub-floor trap); but the JOINT worst case is SMALL N + ISI near "
                     "GO_HI: max TRUE FAR = (band/GO_HI)^K = 3.2e-4 at N=K=5, ISI=400ms (worst_case_true_far). "
                     "observed_isi_ms is advisory context (inflated if the dir concatenates sessions)"),
        "advisory": True,                         # emits a verdict; gates nothing
        "residual_note": ("blind-bot FAR only, and assumes a TIMING-ONLY adversary that already produces gold "
                          "device-clock dumps (synthetic privilege, F13); a fire-time-OBSERVING bot (host APIs "
                          "/ hardware injector) defeats it -> rig/crypto residual, defended by "
                          "HMAC(nonce||t0||onset), not this module"),
        "gate_note": "poep_enabled/L6B/L6_CHALLENGES stay False; no on-chain; candidate/advisory only",
    }
