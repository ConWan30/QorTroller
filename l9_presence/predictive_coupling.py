"""LUMEN-3 / N5 -- Predictive-coupling increment 1: LAG-STRUCTURE COHERENCE.

THE DIRECTION (trio alignment doc N5): a world model that knows expected-screen-given-
input turns coupling from correlation into physics. Increment 1 measures the cheapest
physical invariant on data already in hand: THE LAG STRUCTURE. Genuine causation
(input -> pipeline -> screen) has a lag that is (a) non-negative and bounded by the
pipeline band, and (b) CONSISTENT within a session-channel (one pipeline, one latency).
Spurious coupling on decoupled content (spectate/replay) has no pipeline behind it, so
its lag estimates should be UNSTABLE across windows and/or pinned at degenerate values.

PRE-REGISTERED HYPOTHESIS + BAR (stated 2026-07-08 BEFORE any class statistic was
computed -- the pre-registration discipline):
  metric   consistency(session, channel) = fraction of windows whose lag_ms lies within
           +/- LAG_TOL_MS of that session-channel MEDIAN lag, among windows with
           coupling >= MIN_COUPLING (weak-coupling windows carry no lag information)
  bar      genuine consistency >= 0.60 AND decoupled consistency <= genuine - 0.25,
           on >= 1 channel with N >= MIN_WINDOWS in both classes
  outcome  bar met  -> "lag-coherence SEPARATES" (advisory finding; feeds the
                        latency-consistency fuser of the multi-channel gate)
           bar miss -> honest negative, published identically.

Known instrument caveat (stated up front): lag estimates are frame-quantized (~33ms at
30fps capture), so LAG_TOL_MS = 35.0 (one frame period). A degenerate all-zero lag on
near-zero coupling is NOT coherence -- the MIN_COUPLING gate exists exactly for that.

ADVISORY. Never gates a verdict; UNCALIBRATED until this study + a live re-run pass.
PURE stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

LAG_TOL_MS = 35.0          # one ~30fps frame period (instrument quantum)
MIN_COUPLING = 0.15        # windows below carry no causal lag information
MIN_WINDOWS = 8            # per session-channel; below -> INSUFFICIENT

LAG_COHERENT = "LAG_COHERENT"
LAG_INCOHERENT = "LAG_INCOHERENT"
INSUFFICIENT = "INSUFFICIENT"


@dataclass
class ChannelLagStats:
    channel: str
    n_total: int
    n_informative: int          # coupling >= MIN_COUPLING
    median_lag_ms: Optional[float]
    consistency: Optional[float]  # fraction of informative windows within +/-tol of median
    verdict: str = INSUFFICIENT

    def to_dict(self) -> dict:
        return {"channel": self.channel, "n_total": self.n_total,
                "n_informative": self.n_informative,
                "median_lag_ms": self.median_lag_ms, "consistency": self.consistency,
                "verdict": self.verdict}


def _median(xs: list) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def channel_lag_stats(windows: list, channel: str, *,
                      min_coupling: float = MIN_COUPLING,
                      lag_tol_ms: float = LAG_TOL_MS,
                      min_windows: int = MIN_WINDOWS) -> ChannelLagStats:
    """Lag-structure statistics for one channel of one session's windows.
    windows: [{channel, coupling, null, lag_ms}, ...]. Fail-open: too few informative
    windows -> INSUFFICIENT (never a guessed verdict)."""
    chan = [w for w in (windows or []) if w.get("channel") == channel]
    inf = [w for w in chan
           if w.get("lag_ms") is not None and (w.get("coupling") or 0.0) >= min_coupling]
    if len(inf) < min_windows:
        return ChannelLagStats(channel=channel, n_total=len(chan),
                               n_informative=len(inf), median_lag_ms=None,
                               consistency=None, verdict=INSUFFICIENT)
    lags = [float(w["lag_ms"]) for w in inf]
    med = _median(lags)
    cons = sum(1 for x in lags if abs(x - med) <= lag_tol_ms) / len(lags)
    verdict = LAG_COHERENT if (cons >= 0.60 and med >= 0.0) else LAG_INCOHERENT
    return ChannelLagStats(channel=channel, n_total=len(chan), n_informative=len(inf),
                           median_lag_ms=round(med, 1), consistency=round(cons, 3),
                           verdict=verdict)


@dataclass
class LagSeparationResult:
    channel: str
    genuine: dict
    decoupled: dict
    separates: bool
    note: str


def assess_separation(genuine_windows: list, decoupled_windows: list,
                      channels=("geometric", "b1_flash", "b2_killmark")) -> dict:
    """Apply the PRE-REGISTERED bar per channel. Returns {separates_any, channels: [...]}.
    Honest on both outcomes; INSUFFICIENT on either class disqualifies that channel."""
    out: list = []
    for ch in channels:
        g = channel_lag_stats(genuine_windows, ch)
        d = channel_lag_stats(decoupled_windows, ch)
        if g.verdict == INSUFFICIENT or d.verdict == INSUFFICIENT:
            out.append(LagSeparationResult(ch, g.to_dict(), d.to_dict(), False,
                                           "insufficient informative windows in a class"))
            continue
        sep = (g.consistency >= 0.60 and d.consistency <= g.consistency - 0.25)
        note = ("bar met" if sep else
                f"bar missed (genuine {g.consistency} vs decoupled {d.consistency})")
        out.append(LagSeparationResult(ch, g.to_dict(), d.to_dict(), sep, note))
    return {"separates_any": any(r.separates for r in out),
            "channels": [{"channel": r.channel, "separates": r.separates, "note": r.note,
                          "genuine": r.genuine, "decoupled": r.decoupled} for r in out],
            "pre_registered_bar": "genuine>=0.60 AND decoupled<=genuine-0.25, N>=8/class",
            "advisory": True}


# =====================================================================================
# LUMEN-3 / N5 increment 2 -- LAG DIRECTIONALITY (2026-07-11, TRL-1 A1)
#
# Increment 1 measured lag COHERENCE (stability of the lag within a session-channel).
# Increment 2 measures a DISTINCT, orthogonal invariant: DIRECTIONALITY. Genuine
# causation is one-way in time -- input precedes screen (lag >= 0). The recoil-
# precognition signature of a replay/injection is a NON-CAUSAL lag: the on-screen
# event at or BEFORE the input (lag <= 0), impossible for a screen-reactive human at
# the human reaction band. This is the alignment-doc N5 core (a trigger-synced macro's
# compensation LEADS the on-screen kick) generalized to a standalone metric.
#
# PRE-REGISTERED (stated 2026-07-11 BEFORE any real class statistic was computed):
#   metric   leading_fraction(session, channel) = fraction of INFORMATIVE windows
#            (coupling >= MIN_COUPLING) whose lag_ms < -LEAD_EPS_MS (screen precedes
#            input beyond the instrument quantum -> non-causal)
#   bar      genuine leading_fraction <= 0.10 AND decoupled >= genuine + 0.25,
#            on >= 1 channel with N >= MIN_WINDOWS in both classes
#   outcome  bar met  -> "directionality SEPARATES" (advisory; feeds the latency fuser)
#            bar miss -> honest negative, published identically.
#
# OFFLINE SCOPE (the synthetic -> archive -> live ladder): the metric is proven-to-
# SEPARATE on SYNTHETIC classes here (the ladder's first rung); the GENUINE baseline
# runs on archive windows; the DECOUPLED (replay/injection) class needs a CONTROLLED
# stimulus -- card-gated (RP-4). Advisory; never gates a verdict, never feeds
# presence_score (the anti-GCAP weight rail).

LEAD_EPS_MS = 35.0     # one ~30fps frame period; screen-before-input beyond this = non-causal
DIR_CAUSAL = "DIR_CAUSAL"
DIR_NONCAUSAL = "DIR_NONCAUSAL"


@dataclass
class ChannelDirStats:
    channel: str
    n_total: int
    n_informative: int
    leading_fraction: Optional[float]   # fraction of informative windows with non-causal lag
    verdict: str = INSUFFICIENT

    def to_dict(self) -> dict:
        return {"channel": self.channel, "n_total": self.n_total,
                "n_informative": self.n_informative,
                "leading_fraction": self.leading_fraction, "verdict": self.verdict}


def channel_directionality_stats(windows: list, channel: str, *,
                                 min_coupling: float = MIN_COUPLING,
                                 lead_eps_ms: float = LEAD_EPS_MS,
                                 min_windows: int = MIN_WINDOWS) -> ChannelDirStats:
    """Directionality statistics for one channel of one session. Fail-open: too few
    informative windows -> INSUFFICIENT (never a guessed verdict)."""
    chan = [w for w in (windows or []) if w.get("channel") == channel]
    inf = [w for w in chan
           if w.get("lag_ms") is not None and (w.get("coupling") or 0.0) >= min_coupling]
    if len(inf) < min_windows:
        return ChannelDirStats(channel=channel, n_total=len(chan),
                               n_informative=len(inf), leading_fraction=None,
                               verdict=INSUFFICIENT)
    lead = sum(1 for w in inf if float(w["lag_ms"]) < -lead_eps_ms) / len(inf)
    verdict = DIR_CAUSAL if lead <= 0.10 else DIR_NONCAUSAL
    return ChannelDirStats(channel=channel, n_total=len(chan), n_informative=len(inf),
                           leading_fraction=round(lead, 3), verdict=verdict)


def assess_directionality(genuine_windows: list, decoupled_windows: list,
                          channels=("geometric", "b1_flash", "b2_killmark")) -> dict:
    """Apply the PRE-REGISTERED increment-2 bar per channel. Honest on both outcomes;
    INSUFFICIENT in either class disqualifies that channel."""
    out: list = []
    for ch in channels:
        g = channel_directionality_stats(genuine_windows, ch)
        d = channel_directionality_stats(decoupled_windows, ch)
        if g.verdict == INSUFFICIENT or d.verdict == INSUFFICIENT:
            out.append({"channel": ch, "separates": False,
                        "note": "insufficient informative windows in a class",
                        "genuine": g.to_dict(), "decoupled": d.to_dict()})
            continue
        sep = (g.leading_fraction <= 0.10 and d.leading_fraction >= g.leading_fraction + 0.25)
        note = ("bar met" if sep else
                f"bar missed (genuine {g.leading_fraction} vs decoupled {d.leading_fraction})")
        out.append({"channel": ch, "separates": sep, "note": note,
                    "genuine": g.to_dict(), "decoupled": d.to_dict()})
    return {"separates_any": any(r["separates"] for r in out),
            "channels": out,
            "pre_registered_bar": "genuine leading_fraction<=0.10 AND decoupled>=genuine+0.25, N>=8/class",
            "offline_scope": "synthetic separation proven here; genuine baseline on archive; "
                             "decoupled (replay) class is card-gated (RP-4)",
            "advisory": True}
