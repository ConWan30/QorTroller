"""QorTroller anti-cheat detector — CANDIDATE, ADVISORY (ASM-Loop r02+r04).

Naming (F10): "exclusive" here means HARDWARE-CLASS exclusivity to the certified DualSense Edge (silicon
clock + adaptive-trigger haptic + device-clock binding), NOT a shipped/unbreakable product anti-cheat. This
is a voluntary-reaction liveness CANDIDATE that emits an advisory verdict and gates nothing. The DEFAULT config
is the MEASURED N=5 population band (195,416] + a 120ms anticipation sub-floor (not a single-operator guess).


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
  (N,ISI) worst case for the DEFAULT population config (sub_floor 120 < go_lo, the F5 fix) is ~0.069 for the
  measured (195,416] band — and that is what worst_case_true_far() returns BY DEFAULT (grok F6). The single-op
  reference (band/GO_HI)^K at N=K, ISI=GO_HI (~0.042) requires an EXPLICIT worst_case_true_far(sub_floor_ms=
  go_lo). Widening the band to accept all real humans RAISES the per-shot FAR ~200x vs the old default;
  K-compounding + more challenges LOWER the per-session FAR below this single-shot worst case, but the residual
  stays well ABOVE the strict single-op FAR — the honest cost of not false-rejecting fast humans (advisory).

VERDICTS (fail-closed): HUMAN_PRESENT / SUSPECTED_BOT / DEAD_FEED / INSUFFICIENT. This module EMITS a verdict
and gates NOTHING — poep_enabled / L6B / L6_CHALLENGES stay False; no on-chain, no presence-API flip.

CLAIM CEILING: voluntary-reaction liveness CANDIDATE on a MEASURED N=5 population band (195,416] (Con/Fari/
Khamari/Roy/Pookie in-sample; 4 held-out exercises across 4 people — ConHeldout/Khamari/Pookie/Roy, NOT Fari;
widen + re-fit as slower cohorts are sampled — all 5 are fast-to-moderate reactors); hardware-class
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
from poep_r2onset_adversarial import detect_voluntary_go, GO_LO_MS, GO_HI_MS, SUB_FLOOR_MS  # noqa: E402

K_REQUIRED_DEFAULT = 5          # absolute in-band GO floor to assert HUMAN_PRESENT (operator r01 default)
RATE_MIN_DEFAULT = 0.20         # GO-rate floor: the threshold SCALES with N. NOTE (F15): this makes the FAR
                                # CONCENTRATE downward ONLY once the rate term binds (N >~ 25); while the K
                                # floor binds the FAR RISES with N. The FAR is non-monotone, not "shrinking".
DEFAULT_ISI_MS = 3000.0         # inter-stimulus interval assumed for the blind-bot FAR
_BAND_MS = GO_HI_MS - GO_LO_MS


def blind_bot_probs(isi_ms: float = DEFAULT_ISI_MS, go_lo_ms: float = GO_LO_MS,
                    go_hi_ms: float = GO_HI_MS, sub_floor_ms: float | None = None) -> tuple[float, float]:
    """Per-challenge (p_GO, p_SUB_FLOOR) of a fire-time-BLIND uniform-timing bot: its press latency vs the
    UNKNOWN fire is ~Unif[0, ISI]. INTERSECTION measure (F18) so p_go+p_fast <= 1 even for ISI < go_hi:
    p_go = |(go_lo, min(go_hi,ISI)]| / ISI ; p_fast = |[0, min(sub, ISI)]| / ISI where sub is the FATAL
    sub-floor. sub_floor DEFAULTS to the anticipation floor SUB_FLOOR_MS (120ms) — the DETECTOR'S default
    POPULATION config, so worst_case_true_far()/blind_bot_far() with no sub arg report the DETECTOR-DEFAULT
    envelope, not an understated single-op figure (grok r03 F6). Pass sub_floor_ms=go_lo for the single-op
    reference. A smaller fatal zone (sub < go_lo) makes the (sub, go_lo] 'soft' band p_OTHER (non-fatal,
    non-GO), which RAISES the TRUE FAR (F4) — surfaced through the smaller p_fast, not hidden."""
    if isi_ms <= 0:
        return 1.0, 0.0
    sub = SUB_FLOOR_MS if sub_floor_ms is None else sub_floor_ms
    p_go = max(0.0, (min(go_hi_ms, isi_ms) - go_lo_ms)) / isi_ms
    p_fast = min(sub, isi_ms) / isi_ms
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


def blind_bot_far(n: int, k: int, isi_ms: float = DEFAULT_ISI_MS,
                  go_lo_ms: float = GO_LO_MS, go_hi_ms: float = GO_HI_MS,
                  sub_floor_ms: float | None = None) -> float:
    """TRUE blind-bot false-accept probability for a uniform-timing bot = P(>= k GOs AND ZERO sub-floor).
    HUMAN_PRESENT requires n_go>=k AND n_sub_floor==0, so every non-GO press must be OTHER (not FAST):
    sum_{i=k}^{n} C(n,i) p_go^i * p_other^(n-i), p_other = 1 - p_go - p_fast. Always <= the binomial UB.
    NON-MONOTONE in ISI (F16/F19): rapid cadence raises BOTH p_go AND p_fast. At LARGE fixed N the sub-floor
    trap lowers the TRUE FAR at short ISI; but the JOINT adversary picks SMALL N + ISI near go_hi, where the
    TRUE FAR is MAXIMAL (see worst_case_true_far). Do NOT read 'short ISI is safer'. go_lo/go_hi default to
    the MEASURED band; a WIDER band RAISES the FAR (band grows). sub_floor DEFAULTS to the anticipation floor
    (population config, grok r03 F6); pass sub_floor=go_lo for the single-op reference. A sub_floor < go_lo
    shrinks the fatal zone (soft escape) -> RAISES the FAR (F4)."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    p_go, p_fast = blind_bot_probs(isi_ms, go_lo_ms, go_hi_ms, sub_floor_ms)
    p_other = max(0.0, 1.0 - p_go - p_fast)
    return sum(math.comb(n, i) * (p_go ** i) * (p_other ** (n - i)) for i in range(k, n + 1))


def worst_case_true_far(k_required: int = K_REQUIRED_DEFAULT, rate_min: float = RATE_MIN_DEFAULT,
                        isi_hi_ms: float = 4000.0, isi_step_ms: float = 5.0, n_max: int = 80,
                        go_lo_ms: float = GO_LO_MS, go_hi_ms: float = GO_HI_MS,
                        sub_floor_ms: float | None = None) -> tuple[int, float, float]:
    """JOINT worst-case TRUE FAR over (N, ISI) — the honest security number (F19). BY DEFAULT (sub_floor=None
    -> the anticipation floor, the DETECTOR'S default population config) this returns the DETECTOR-DEFAULT
    envelope (~0.069 for the measured (195,416] band at N~=7, ISI~=go_hi) — NOT an understated single-op
    figure (grok r03 F6). Pass sub_floor=go_lo for the SINGLE-OP reference: then it is (band/go_hi)^K at
    ISI=go_hi, N=K (p_other=0 forces every non-GO press sub-floor -> the only HUMAN_PRESENT path is ALL-K-GO).
    A population sub_floor < go_lo has p_other > 0 even at ISI=go_hi (soft escape) -> HIGHER max, argmax can
    shift off N=K; the grid finds it (F4). Grid includes ISI=go_hi exactly.
    Returns (n, isi_ms, far). Do NOT publish a slice as the envelope max."""
    best = (0, 0.0, 0.0)
    grid = [go_hi_ms]                                  # the analytic argmax (single-op); then sweep above it
    x = go_lo_ms + 1.0
    while x <= isi_hi_ms:
        grid.append(x)
        x += isi_step_ms
    for isi in grid:
        for n in range(1, n_max):
            f = blind_bot_far(n, go_threshold(n, k_required, rate_min), isi, go_lo_ms, go_hi_ms, sub_floor_ms)
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
                   rate_min: float = RATE_MIN_DEFAULT, isi_ms: float = DEFAULT_ISI_MS,
                   go_lo_ms: float = GO_LO_MS, go_hi_ms: float = GO_HI_MS,
                   sub_floor_ms: float | None = None) -> dict[str, Any]:
    """Emit a session-level anti-cheat verdict from a list of nonce-bound fire dumps. Gates nothing. go_lo/
    go_hi DEFAULT to the MEASURED N=5 population band (195,416]; sub_floor_ms DEFAULTS to the anticipation
    floor SUB_FLOOR_MS (120ms) — the F5 fix is ON by default (a fast human below the band retries, is not
    bot-flagged). Pass sub_floor_ms=go_lo for the old strict single-operator behavior. All FAR is recomputed
    for the effective (band, sub-floor)."""
    # eff_sub: the effective sub-floor. DEFAULT is the population anticipation floor (120), NOT go_lo — the
    # detector is population-config by default (the old (320,400]/sub=320 default flagged real humans as bots).
    eff_sub = SUB_FLOOR_MS if sub_floor_ms is None else sub_floor_ms
    per = [detect_voluntary_go(r, go_lo_ms, go_hi_ms, eff_sub) for r in recs]
    n = len(recs)
    n_go = sum(1 for v in per if v["verdict"] == "GO")
    n_soft = sum(1 for v in per if v["verdict"] in ("SOFT_TOO_SLOW", "SOFT_TOO_FAST"))
    n_fast = sum(1 for v in per if v["verdict"] == "REJECT_TOO_FAST")
    n_noreact = sum(1 for v in per if v["verdict"] == "REJECT_NO_REACTION")
    n_badref = sum(1 for v in per if v["verdict"] == "REJECT")

    thr = go_threshold(n, k_required, rate_min)
    obs_isi = observed_isi_ms(recs)
    # FAR threads the EFFECTIVE sub-floor (grok r05 F8): a population sub_floor < go_lo shrinks the fatal
    # zone -> RAISES this session's blind-bot FAR (the honest cost of not false-rejecting fast humans).
    p_go, p_fast = blind_bot_probs(isi_ms, go_lo_ms, go_hi_ms, eff_sub)   # FAR at ASSUMED ISI + band + sub
    far_true = blind_bot_far(n, thr, isi_ms, go_lo_ms, go_hi_ms, eff_sub) if n > 0 else 1.0  # TRUE multinom
    far_binom_ub = binom_tail_ge(n, thr, p_go) if n > 0 else 1.0           # loose upper bound (F2)
    go_rate = (n_go / n) if n else 0.0

    # fail-closed verdict ladder
    if n == 0:
        verdict, why = "INSUFFICIENT", "no challenges in the session window"
    elif n_fast > 0:
        # a press below the EFFECTIVE sub-floor. Heuristic bot signal, NOT a proof of non-humanity (F5). By
        # DEFAULT eff_sub is the ~120ms anticipation floor, so only sub-human (anticipation) presses trip it;
        # a fast human above 120 is SOFT_TOO_FAST (retry), never bot-flagged. Pass sub_floor_ms=go_lo for the
        # old strict behavior. Message reports the ACTUAL sub-floor in force (grok r03 F5).
        verdict, why = "SUSPECTED_BOT", (
            f"{n_fast} press(es) below the configured sub-floor {eff_sub:.0f}ms (heuristic, not proof)")
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
        "n_go": n_go, "n_soft": n_soft, "n_sub_floor": n_fast,   # n_soft aggregates SOFT_TOO_SLOW + SOFT_TOO_FAST
        "n_no_reaction": n_noreact, "n_bad_reference": n_badref,
        "k_required": k_required, "rate_min": rate_min, "go_threshold": thr,
        "go_rate": round(go_rate, 3),
        "assumed_isi_ms": isi_ms,
        "observed_isi_ms": round(obs_isi, 1) if obs_isi is not None else None,
        "blind_bot_p_go": round(p_go, 5), "blind_bot_p_sub_floor": round(p_fast, 5),
        "blind_bot_far": far_true,               # TRUE multinomial FALSE-ACCEPT vs a fire-time-BLIND bot
        "blind_bot_far_binom_ub": far_binom_ub,  # loose upper bound (counts sub-floor paths -> SUSPECTED_BOT; F2)
        # far_note is CONFIG-CONDITIONAL (grok r05 F9) and keys on the EFFECTIVE sub-floor. By DEFAULT eff_sub
        # is the 120ms anticipation floor (< go_lo), so the DEFAULT note is the POPULATION one — the single-op
        # (band/GO_HI)^K analytic does NOT apply. Single-op note only when eff_sub >= go_lo (grok r07 F12).
        "far_note": (
            ("TRUE FAR at the ASSUMED ISI; NON-MONOTONE in ISI (F16/F19). At large fixed N a short ISI LOWERS "
             "the TRUE FAR (sub-floor trap); the JOINT worst case is SMALL N + ISI near GO_HI: max TRUE FAR = "
             "(band/GO_HI)^K at N=K, ISI=GO_HI (worst_case_true_far). observed_isi_ms is advisory.")
            if eff_sub >= go_lo_ms else
            (f"TRUE FAR at the ASSUMED ISI for the POPULATION config (sub-floor {eff_sub:.0f}ms < go_lo "
             f"{go_lo_ms:.0f}ms — the DEFAULT). The single-op (band/GO_HI)^K analytic does NOT apply — the "
             f"smaller fatal zone RAISES the joint worst-case AND shifts its argmax off N=K; compute the exact "
             f"envelope with worst_case_true_far(go_lo={go_lo_ms:.0f}, go_hi={go_hi_ms:.0f}, "
             f"sub_floor_ms={eff_sub:.0f}). observed_isi_ms is advisory.")),
        "advisory": True,                         # emits a verdict; gates nothing
        "residual_note": ("blind-bot FAR only, and assumes a TIMING-ONLY adversary that already produces gold "
                          "device-clock dumps (synthetic privilege, F13); a fire-time-OBSERVING bot (host APIs "
                          "/ hardware injector) defeats it -> rig/crypto residual, defended by "
                          "HMAC(nonce||t0||onset), not this module"),
        "gate_note": "poep_enabled/L6B/L6_CHALLENGES stay False; no on-chain; candidate/advisory only",
    }
