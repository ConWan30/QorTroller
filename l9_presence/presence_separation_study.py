"""P0-A — presence-oracle separation study (human vs modeled automation).

Design: docs/p0a-presence-separation-study-design.md (loop cycle 1, grok design / Claude audit+build).

Scores the L9 causal-presence oracle (input-stick -> rendered-camera coupling) on:
  POSITIVE  = real human aim sessions (developer_self, sessions_l9/*.npz)
  NEGATIVE  = DERIVED modeled automation — synth_adversary full camera injection (injection=1.0)
              x {static, snap, track} over the SAME human stick tracks (no independent cheat corpus)
  FLOOR     = per-human time-shuffle negative_control (causality honesty gate M6; NOT in C_auto)
and returns a pre-registered separation operating point: median gap + the M1-M6 decision rule.

HONEST SCOPE (design §1/§7): human-vs-MODELED-automation, single-operator, constructed negative.
NOT human-vs-real-cheat-hardware · NOT identity · NOT population-certified · NOT host-trustless.
`advisory=True`, `cert_scope=developer_self`, `population_certified=False` on every report.

Constants (§3.3) are FROZEN at study schema `p0a-presence-op-v1`. Changing them post-run requires a
schema version bump — never emit SEPARATED under changed constants (§6 rule, pinned by test).

PURE analysis: imports only the l9_presence scoring path (session_recorder.analyze_session_data +
synth_adversary.synthesize). ZERO capture-path / daemon / dualshock imports (acceptance test T9).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

from .session_recorder import SessionData, analyze_session_data
from .synth_adversary import MODES, synthesize

STUDY_SCHEMA = "p0a-presence-op-v1"

# ---- pre-registered decision constants (§3.3) — FROZEN at this schema version ----
TAU_HUMAN = 0.20        # = coupling.COUPLING_THRESHOLD; real presence must clear the runtime floor
TAU_AUTO = 0.10         # modeled automation must sit below threshold (banked full-injection ~0.05)
GAP_MIN = 0.15          # pre-registered separation magnitude (conservative vs banked ~0.24-0.40)
TAU_NC = 0.10           # time-shuffle causality floor must collapse (banked ~0.02)
N_MIN_POS = 8           # first honest OP floor (developer_self)
N_MIN_NEG = 24          # 8 human seeds x 3 injection modes

AUTO_MODES = tuple(MODES)          # ("static", "snap", "track") — sourced from synth_adversary
DEFAULT_SEED = 0

# ---- closed-enum verdicts (§6) ----
SEPARATED = "SEPARATED"
INSUFFICIENT_N = "INSUFFICIENT_N"
INCONCLUSIVE = "INCONCLUSIVE"
UNVERIFIABLE = "UNVERIFIABLE"
CAUSALITY_FAIL = "CAUSALITY_FAIL"   # sub-label folded into UNVERIFIABLE output


def _median(xs) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _quartiles(xs):
    xs = sorted(x for x in xs if x is not None)
    if len(xs) < 2:
        return (xs[0] if xs else None, xs[0] if xs else None)
    q = statistics.quantiles(xs, n=4)          # [q25, q50, q75]
    return (round(q[0], 4), round(q[2], 4))


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.mean(xs), 4) if xs else None


@dataclass
class _Scored:
    coupling_score: float
    negative_control: Optional[float]
    neg_control_margin: Optional[float]
    label: str
    mode: Optional[str] = None          # auto mode (static/snap/track); None for human


def _score(sessions, *, mode: Optional[str] = None):
    """Score a list of SessionData through the SAME oracle path (T1). Returns
    (scored, n_skipped, scored_sessions) — scored_sessions are the SessionData that produced a score,
    so callers can derive negatives without re-scoring. Insufficient-aim sessions are dropped from the
    class and counted as skipped (T5)."""
    scored, skipped, scored_sessions = [], 0, []
    for s in sessions:
        r = analyze_session_data(s)          # the ONLY scoring path — identical for both classes
        if r.get("status") == "insufficient_aim_activity" or r.get("coupling_score") is None:
            skipped += 1
            continue
        scored.append(_Scored(coupling_score=float(r["coupling_score"]),
                              negative_control=r.get("negative_control"),
                              neg_control_margin=r.get("neg_control_margin"),
                              label=r.get("label", ""), mode=mode))
        scored_sessions.append(s)
    return scored, skipped, scored_sessions


def _derive_negatives(human_sessions, seed: int):
    """Paired modeled-automation construction (§4.1): for each human session i, synthesize 3 scripted
    sessions (injection=1.0, one per mode). Stick preserved, camera replaced. Never rewrites disk (T2)."""
    out = []
    for i, s in enumerate(human_sessions):
        for m in AUTO_MODES:
            out.append((m, synthesize(s, injection=1.0, mode=m, seed=seed + i)))
    return out


def decide_verdict(*, n_pos: int, n_neg: int, med_human, med_auto, gap,
                   med_nc, med_margin) -> tuple:
    """Pure decision rule (§3.2 M1-M6 + §6 verdict precedence). Returns (verdict, gates, reason).
    Precedence: no-human/causality-fail -> UNVERIFIABLE; N floor -> INSUFFICIENT_N; M3-5 -> SEPARATED;
    else INCONCLUSIVE. INSUFFICIENT_N beats INCONCLUSIVE; causality (M6) is a hard UNVERIFIABLE gate."""
    m1 = n_pos >= N_MIN_POS
    m2 = n_neg >= N_MIN_NEG
    m3 = med_human is not None and med_human >= TAU_HUMAN
    m4 = med_auto is not None and med_auto <= TAU_AUTO
    m5 = gap is not None and gap >= GAP_MIN
    m6 = (med_nc is not None and med_nc <= TAU_NC
          and med_margin is not None and med_margin >= GAP_MIN)
    gates = {"M1_n_pos": m1, "M2_n_neg": m2, "M3_human_floor": m3,
             "M4_auto_ceiling": m4, "M5_gap": m5, "M6_causality": m6}

    if n_pos == 0 or med_human is None:
        return UNVERIFIABLE, gates, "no scorable human sessions"
    if not m6:
        return UNVERIFIABLE, gates, f"{CAUSALITY_FAIL}: human coupling not causally validated (M6)"
    if not (m1 and m2):
        return INSUFFICIENT_N, gates, f"n_human={n_pos}(<{N_MIN_POS}) or n_auto={n_neg}(<{N_MIN_NEG})"
    if m3 and m4 and m5:
        return SEPARATED, gates, "M1-M6 all hold under pre-registered constants"
    fails = [k for k, v in {"M3_human_floor": m3, "M4_auto_ceiling": m4, "M5_gap": m5}.items() if not v]
    return INCONCLUSIVE, gates, f"N met, causality held, but failed {fails}"


@dataclass
class StudyReport:
    verdict: str
    gates: dict
    reason: str
    n: dict
    medians: dict
    gap: Optional[float]
    diagnostics: dict
    constants: dict
    seed: int
    player_histogram: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema": STUDY_SCHEMA,
            "advisory": True, "cert_scope": "developer_self", "population_certified": False,
            "verdict": self.verdict, "gates": self.gates, "reason": self.reason,
            "n": self.n, "medians": self.medians, "gap": self.gap,
            "diagnostics": self.diagnostics, "constants": self.constants, "seed": self.seed,
            "player_histogram": self.player_histogram,
        }

    def to_markdown(self) -> str:
        d = self.to_dict()
        lines = [
            "# P0-A Presence-Oracle Separation OP", "",
            f"**VERDICT: {d['verdict']}** — {d['reason']}", "",
            "*human-vs-**modeled**-automation · developer_self · advisory · "
            "population_certified=False · NOT real-cheat / identity / host-trustless (design §7)*", "",
            f"- schema: `{d['schema']}`  seed: {d['seed']}",
            f"- N: human_scored={d['n']['n_human_scored']} (skipped {d['n']['n_human_skipped']} of "
            f"{d['n']['n_human_available']}) · auto_scored={d['n']['n_auto_scored']}",
            f"- median coupling: human={d['medians']['human']} · auto={d['medians']['auto']} · "
            f"**gap={d['gap']}** (GAP_MIN={d['constants']['GAP_MIN']})",
            f"- causality: median NC={d['medians']['negative_control']} (<= {d['constants']['TAU_NC']}) · "
            f"median margin={d['medians']['neg_control_margin']} (>= {d['constants']['GAP_MIN']})",
            "", "| gate | pass |", "|---|---|",
        ]
        for k, v in d["gates"].items():
            lines.append(f"| {k} | {'yes' if v else '**NO**'} |")
        pm = d["diagnostics"].get("per_mode_auto_median", {})
        lines += ["", f"- per-mode auto median: static={pm.get('static')} snap={pm.get('snap')} "
                  f"track={pm.get('track')}",
                  f"- separation_ratio (diagnostic): {d['diagnostics'].get('separation_ratio')}",
                  f"- human p25/p75={d['diagnostics'].get('human_p25_p75')} · "
                  f"auto p25/p75={d['diagnostics'].get('auto_p25_p75')}"]
        return "\n".join(lines)


def run_separation_study(human_sessions, *, seed: int = DEFAULT_SEED) -> StudyReport:
    """Full pipeline (§3-§6). human_sessions: list[SessionData] (real human positives, already loaded).
    Scores positives, derives+scores the paired modeled-automation negatives, computes the median gap +
    M1-M6, returns a StudyReport. Pure: no I/O, no capture-path (the runner does file loading)."""
    n_available = len(human_sessions)
    human_scored, human_skipped, scored_human_sessions = _score(human_sessions)
    # derive negatives ONLY from the sessions that scored (T7: n_auto = n_human_scored x 3 when all score)
    negatives = _derive_negatives(scored_human_sessions, seed)
    auto_scored = []
    for m, s in negatives:
        sc, _, _ = _score([s], mode=m)
        auto_scored.extend(sc)

    C_human = [r.coupling_score for r in human_scored]
    C_auto = [r.coupling_score for r in auto_scored]
    NC_human = [r.negative_control for r in human_scored]
    margin_human = [r.neg_control_margin for r in human_scored]

    med_human, med_auto = _median(C_human), _median(C_auto)
    med_nc, med_margin = _median(NC_human), _median(margin_human)
    gap = (med_human - med_auto) if (med_human is not None and med_auto is not None) else None

    verdict, gates, reason = decide_verdict(
        n_pos=len(human_scored), n_neg=len(auto_scored), med_human=med_human,
        med_auto=med_auto, gap=gap, med_nc=med_nc, med_margin=med_margin)

    per_mode = {m: _median([r.coupling_score for r in auto_scored if r.mode == m]) for m in AUTO_MODES}
    sep_ratio = (round(med_human / max(med_auto, 1e-6), 3)
                 if (med_human is not None and med_auto is not None) else None)
    hist: dict = {}
    for r in human_scored:
        # human label may carry player; count labels (developer_self -> typically one)
        hist[r.label] = hist.get(r.label, 0) + 1

    return StudyReport(
        verdict=verdict, gates=gates, reason=reason,
        n={"n_human_available": n_available, "n_human_scored": len(human_scored),
           "n_human_skipped": human_skipped, "n_auto_scored": len(auto_scored)},
        medians={"human": round(med_human, 4) if med_human is not None else None,
                 "auto": round(med_auto, 4) if med_auto is not None else None,
                 "negative_control": round(med_nc, 4) if med_nc is not None else None,
                 "neg_control_margin": round(med_margin, 4) if med_margin is not None else None},
        gap=round(gap, 4) if gap is not None else None,
        diagnostics={"separation_ratio": sep_ratio,
                     "per_mode_auto_median": {m: (round(v, 4) if v is not None else None)
                                              for m, v in per_mode.items()},
                     "human_mean": _mean(C_human), "auto_mean": _mean(C_auto),
                     "human_p25_p75": _quartiles(C_human), "auto_p25_p75": _quartiles(C_auto)},
        constants={"TAU_HUMAN": TAU_HUMAN, "TAU_AUTO": TAU_AUTO, "GAP_MIN": GAP_MIN,
                   "TAU_NC": TAU_NC, "N_MIN_POS": N_MIN_POS, "N_MIN_NEG": N_MIN_NEG},
        seed=seed, player_histogram=hist)
