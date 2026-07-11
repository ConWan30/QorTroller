"""P1 anomaly diagnostic (F-P0A-V2-1) — why does labeled player P1 stay below TAU_HUMAN on aim-active
sessions? Classifies into a CLOSED set of capture/protocol/style explanations. Design:
docs/p1-anomaly-diagnostic-design-2026-07-10.md (grok design, Claude audit).

Does NOT: reopen/amend P0-A v2 SEPARATED · change TAU_*/GAP_MIN/aim gate · call P1 a bot/cheat/automation
(P1 is a labeled human in the developer corpus — low coupling != automation class).

CLOSED-ENUM labels (evaluated in a PRE-REGISTERED order H1->H2->H3->H5->H4 — environment/protocol before
"genuine player difference"; first True = primary, rest = secondaries/notes):
  MARGINAL_AIM (H1)          clears the 10.2 aim gate but near the floor -> low coupling is mostly weak aim
  HIGH_RESIDUAL (H2)         stick material but decoupled_energy high (camera not explained by stick)
  LAG_REGIME (H3)            P1 best-lag band differs from peers by >= 100 ms (stream/backend/search edge)
  PROTOCOL_MIX (H5)          a recordable discrete protocol field differs P1 vs peers
  GENUINE_LOW_COUPLING (H4)  low even after aim-matching to peers -> residual player/style difference
  INCONCLUSIVE (H0)          n < 5 or no test True / no aim-matched comparator
  UNVERIFIABLE               harness/IO failure

AUDIT SCOPE NOTES (Claude, 2026-07-10): (1) the .npz carry NO backend/region/protocol field
(`capture_governor` is a bare ndarray; `hud_json` is non-uniform) — T-H5 runs only on the discrete
fields that EXIST (label, duration_bin), reported in `protocol_fields_available`. (2) P1's aim band
(~14.8) does not overlap peers' (~50), so T-H4 typically has NO aim-matched comparator (honest: we
cannot establish genuine-low-coupling-after-matching when the aim distributions don't overlap).

PURE offline analysis over existing `.npz` via the SAME scoring path as P0-A. Zero capture-path.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .presence_separation_study import AIM_ACTIVITY_MIN, TAU_HUMAN
from .session_recorder import SessionData, analyze_session_data

STUDY_SCHEMA = "p1-anomaly-diagnostic-v0"

MARGINAL_AIM = "MARGINAL_AIM"
HIGH_RESIDUAL = "HIGH_RESIDUAL"
LAG_REGIME = "LAG_REGIME"
PROTOCOL_MIX = "PROTOCOL_MIX"
GENUINE_LOW_COUPLING = "GENUINE_LOW_COUPLING"
INCONCLUSIVE = "INCONCLUSIVE"
UNVERIFIABLE = "UNVERIFIABLE"

# pre-registered thresholds (§4.3 / §9; frozen — not outcome-tuned)
MARGINAL_AIM_BAND = 2.0 * AIM_ACTIVITY_MIN     # = 20.4 LSB (T-H1)
HIGH_RESIDUAL_MIN = 0.95                        # T-H2
HIGH_RESIDUAL_MARGIN = 0.05                     # T-H2
LAG_REGIME_GAP_MS = 100.0                       # T-H3
MIN_FOCUS_N = 5                                 # below this -> INCONCLUSIVE (§4 algorithm)
_AIM_MATCH_BAND = 0.20                          # T-H4 P1 aim band +/-20%


def _median(xs) -> Optional[float]:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def session_metrics(s: SessionData) -> Optional[dict]:
    """All diagnostic metrics for one session, or None if the oracle doesn't score it. Same
    coupling/lag/decoupled_energy path as P0-A (T1); the rest are pure stick/camera geometry."""
    r = analyze_session_data(s)
    if r.get("coupling_score") is None:
        return None
    sx, sy = np.asarray(s.in_sx, float), np.asarray(s.in_sy, float)
    aim = float(max(np.std(sx - np.median(sx)), np.std(sy - np.median(sy)))) if sx.size else 0.0
    p90 = (float(np.percentile(np.maximum(np.abs(sx - np.median(sx)), np.abs(sy - np.median(sy))), 90))
           if sx.size else 0.0)
    dur = float((s.in_ts[-1] - s.in_ts[0]) / 1000.0) if len(s.in_ts) > 1 else 0.0
    moy, mop = np.asarray(s.mo_yaw, float), np.asarray(s.mo_pitch, float)
    return {
        "player": s.player or "?", "label": s.label or "",
        "coupling": round(float(r["coupling_score"]), 4), "aim": round(aim, 2),
        "lag_ms": r.get("lag_ms"), "decoupled_energy": r.get("decoupled_energy"),
        "stick_range": round(float(max(sx.max() - sx.min(), sy.max() - sy.min())) if sx.size else 0.0, 1),
        "stick_p90_abs": round(p90, 1), "duration_s": round(dur, 1),
        "duration_bin": int(round(dur / 30.0) * 30), "n_in": len(s.in_ts), "n_mo": len(s.mo_ts),
        "mo_energy": round(float(np.std(moy) + np.std(mop)), 3),
        "aim_active": aim >= AIM_ACTIVITY_MIN,
    }


@dataclass
class DiagnosticReport:
    primary: str
    secondaries: list
    reason: str
    tests: dict                     # T-H1..T-H5 -> {pass: bool|None, detail: str}
    per_player: dict
    focus_sessions: list
    protocol_fields_available: list
    n_focus_aim_active: int
    p0a_v2_separated_unchanged: bool = True

    def to_dict(self) -> dict:
        return {"schema": STUDY_SCHEMA, "advisory": True, "cert_scope": "developer_self",
                "population_certified": False, "p0a_v2_separated_unchanged": True,
                "primary": self.primary, "secondaries": self.secondaries, "reason": self.reason,
                "tests": self.tests, "per_player": self.per_player,
                "n_focus_aim_active": self.n_focus_aim_active,
                "protocol_fields_available": self.protocol_fields_available,
                "focus_sessions": self.focus_sessions}

    def to_markdown(self) -> str:
        d = self.to_dict()
        lines = [f"# P1 Anomaly Diagnostic (F-P0A-V2-1) — `{d['schema']}`", "",
                 f"**PRIMARY: {d['primary']}** — {d['reason']}",
                 f"secondaries: {d['secondaries'] or 'none'}",
                 f"**p0a_v2_separated_unchanged: {d['p0a_v2_separated_unchanged']}** · "
                 "advisory · developer_self · P1 is a labeled human (low coupling != automation)", "",
                 f"- focus P1 aim-active n={d['n_focus_aim_active']} · "
                 f"protocol fields available: {d['protocol_fields_available']}", "",
                 "| player | n | med coupling | med aim | med lag | med dec |", "|---|---|---|---|---|---|"]
        for p, v in d["per_player"].items():
            lines.append(f"| {p} | {v['n']} | {v['med_coupling']} | {v['med_aim']} | "
                         f"{v['med_lag']} | {v['med_dec']} |")
        lines += ["", "| test | pass | detail |", "|---|---|---|"]
        for t, r in d["tests"].items():
            p = "yes" if r["pass"] else ("—" if r["pass"] is None else "no")
            lines.append(f"| {t} | {p} | {r['detail']} |")
        return "\n".join(lines)


def _pp(rows):
    return {"n": len(rows), "med_coupling": round(_median([r["coupling"] for r in rows]) or 0, 4),
            "med_aim": round(_median([r["aim"] for r in rows]) or 0, 2),
            "med_lag": round(_median([r["lag_ms"] for r in rows]) or 0, 1),
            "med_dec": round(_median([r["decoupled_energy"] for r in rows]) or 0, 4)}


def classify_p1_anomaly(metrics, *, focus: str = "P1",
                        comparators=("P2", "P3")) -> DiagnosticReport:
    """metrics: list[session_metrics dict]. Groups by player, restricts to aim-active, applies the
    pre-registered T-H1..T-H5 in order (§4). Pure — no I/O."""
    aim_active = [m for m in metrics if m and m.get("aim_active")]
    by = {}
    for m in aim_active:
        by.setdefault(m["player"], []).append(m)
    P1 = by.get(focus, [])
    peers = [m for c in comparators for m in by.get(c, [])]     # P2 u P3 (untagged excluded, §5)
    per_player = {p: _pp(by[p]) for p in sorted(by)}

    def T(passed, detail):
        return {"pass": passed, "detail": detail}

    tests: dict = {}
    # T-H1 MARGINAL_AIM
    m_p1_aim, m_pe_aim = _median([r["aim"] for r in P1]), _median([r["aim"] for r in peers])
    th1 = (m_p1_aim is not None and m_pe_aim is not None
           and m_p1_aim < m_pe_aim and m_p1_aim < MARGINAL_AIM_BAND)
    tests["T-H1_MARGINAL_AIM"] = T(th1, f"P1 med_aim {round(m_p1_aim or 0,1)} < peers "
                                   f"{round(m_pe_aim or 0,1)} and < {MARGINAL_AIM_BAND}")
    # T-H2 HIGH_RESIDUAL
    m_p1_dec, m_pe_dec = _median([r["decoupled_energy"] for r in P1]), _median([r["decoupled_energy"] for r in peers])
    th2 = (m_p1_dec is not None and m_pe_dec is not None
           and m_p1_dec >= HIGH_RESIDUAL_MIN and m_pe_dec <= m_p1_dec - HIGH_RESIDUAL_MARGIN)
    tests["T-H2_HIGH_RESIDUAL"] = T(th2, f"P1 med_dec {round(m_p1_dec or 0,3)} (>= {HIGH_RESIDUAL_MIN}) "
                                    f"vs peers {round(m_pe_dec or 0,3)}")
    # T-H3 LAG_REGIME
    m_p1_lag, m_pe_lag = _median([r["lag_ms"] for r in P1]), _median([r["lag_ms"] for r in peers])
    th3 = (m_p1_lag is not None and m_pe_lag is not None and abs(m_p1_lag - m_pe_lag) >= LAG_REGIME_GAP_MS)
    tests["T-H3_LAG_REGIME"] = T(th3, f"|P1 {round(m_p1_lag or 0)} - peers {round(m_pe_lag or 0)}| "
                                 f"vs {LAG_REGIME_GAP_MS}ms gap")
    # T-H5 PROTOCOL_MIX — only on discrete fields that EXIST (audit: no backend/region)
    fields = ["label", "duration_bin"]
    th5, th5_detail = False, "no discrete protocol field differs (only label/duration_bin available)"
    for f in fields:
        p1v = _dominant(P1, f)
        pev = _dominant(peers, f)
        if p1v is not None and pev is not None and p1v[0] != pev[0] and p1v[1] >= 0.5 and pev[1] >= 0.5:
            th5, th5_detail = True, f"{f}: P1={p1v[0]}({p1v[1]:.0%}) vs peers={pev[0]}({pev[1]:.0%})"
            break
    tests["T-H5_PROTOCOL_MIX"] = T(th5, th5_detail)
    # T-H4 GENUINE_LOW_COUPLING — aim-matched (P1 aim band +/-20%); honest None if no matched comparator
    th4, th4_detail = _test_h4(P1, peers, m_p1_aim)
    tests["T-H4_GENUINE_LOW"] = T(th4, th4_detail)

    n_focus = len(P1)
    if n_focus < MIN_FOCUS_N:
        return DiagnosticReport(INCONCLUSIVE, [], f"P1 aim-active n={n_focus} < {MIN_FOCUS_N}",
                                tests, per_player, [dict(r) for r in P1], fields, n_focus)

    order = [("T-H1_MARGINAL_AIM", MARGINAL_AIM), ("T-H2_HIGH_RESIDUAL", HIGH_RESIDUAL),
             ("T-H3_LAG_REGIME", LAG_REGIME), ("T-H5_PROTOCOL_MIX", PROTOCOL_MIX),
             ("T-H4_GENUINE_LOW", GENUINE_LOW_COUPLING)]
    hits = [(lbl, key) for key, lbl in order if tests[key]["pass"]]
    if not hits:
        return DiagnosticReport(INCONCLUSIVE, [], "no pre-registered test True", tests, per_player,
                                [dict(r) for r in P1], fields, n_focus)
    primary = hits[0][0]
    secondaries = [lbl for lbl, _ in hits[1:]]
    reason = f"first-True in pre-registered order (env/protocol before genuine); {len(hits)} test(s) True"
    return DiagnosticReport(primary, secondaries, reason, tests, per_player,
                            [dict(r) for r in P1], fields, n_focus)


def _dominant(rows, field_name):
    """(most-common value, fraction) for a discrete field over rows, or None."""
    if not rows:
        return None
    from collections import Counter
    c = Counter(r.get(field_name) for r in rows)
    val, cnt = c.most_common(1)[0]
    return (val, cnt / len(rows))


def _test_h4(P1, peers, m_p1_aim):
    """Aim-matched residual: sessions with aim in P1's band +/-20%. Genuine-low iff P1 median coupling
    < TAU AND matched non-P1 median coupling >= TAU. None (honest) if no non-P1 lands in P1's aim band."""
    if m_p1_aim is None or not P1:
        return None, "no P1 aim to match"
    lo, hi = m_p1_aim * (1 - _AIM_MATCH_BAND), m_p1_aim * (1 + _AIM_MATCH_BAND)
    p1_band = [r["coupling"] for r in P1 if lo <= r["aim"] <= hi]
    peer_band = [r["coupling"] for r in peers if lo <= r["aim"] <= hi]
    if not peer_band:
        return None, (f"no aim-matched comparator (P1 aim band [{lo:.1f},{hi:.1f}] has 0 peer "
                      "sessions — P1 aim does not overlap peers; genuine-low UNTESTABLE)")
    mp1, mpe = _median(p1_band), _median(peer_band)
    passed = mp1 is not None and mpe is not None and mp1 < TAU_HUMAN and mpe >= TAU_HUMAN
    return passed, (f"aim-matched P1 coupling {round(mp1 or 0,3)} (<{TAU_HUMAN}?) vs peers "
                    f"{round(mpe or 0,3)} (>={TAU_HUMAN}?), n_peer_matched={len(peer_band)}")
