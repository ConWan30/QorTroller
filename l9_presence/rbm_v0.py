"""RBM-v0 — Reflex Baseline Model (A2A-POEP-P2, grok round-09 design).

A population reflex-CONSISTENCY scorer for ONE certified Edge under one operator's campaign. NOT an
identity model, NOT a liveness verdict, NOT PoEP issuance -- a device-local baseline building block.
Pure Python (math only; no numpy/sklearn).

Two layers, one scalar (grok RBM-v0-DEF-01):
  1. hard_floor  -- boolean fail-closed gate: latency in [80,300]ms AND peak >= 1000 LSB. Out -> 0.0.
  2. score_row   -- diagonal-covariance Mahalanobis-lite on (latency, peak) vs frozen population
                    moments: d2 = ((L-muL)/sdL)^2 + ((P-muP)/sdP)^2 ; score = exp(-0.5*d2) in [0,1].

Moments are FROZEN in rbm_v0_params.json (computed once at calibration; no online update). The score
is ranked consistency with that snapshot; `above_operating_point` compares to a frozen tau* -- and is
NEVER mapped to HUMAN/LIVE/PASS by any product surface (grok RBM-v0-NULL-02 / SCOPE-01).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Optional

SCOPE = "single_operator_single_edge_N52"

# Hard-floor bounds (grok RBM-v0-DEF-01: p5/p95 with margin off the measured edges).
LAT_FLOOR_MS = 80.0
LAT_CEIL_MS = 300.0
PEAK_FLOOR_LSB = 1000.0


@dataclass(frozen=True)
class RBMV0Params:
    mu_latency: float
    sd_latency: float
    mu_peak: float
    sd_peak: float
    operating_threshold: float          # frozen tau* (lowest score with TPR>=0.90 on positives)
    n_positives: int
    lat_floor: float = LAT_FLOOR_MS
    lat_ceil: float = LAT_CEIL_MS
    peak_floor: float = PEAK_FLOOR_LSB
    scope: str = SCOPE

    def params_hash(self) -> str:
        """Content address (grok RBM-v0-DEF-01 (e)): SHA-256 of canonical params -- no silent retrain."""
        body = {k: v for k, v in asdict(self).items()}
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def hard_floor(latency_ms: Optional[float], peak_lsb: Optional[float], p: RBMV0Params) -> bool:
    """Fail-closed membership gate. None / out-of-band / low-peak -> False (CCO physics + junk rejected)."""
    if latency_ms is None or peak_lsb is None:
        return False
    return (p.lat_floor <= latency_ms <= p.lat_ceil) and (peak_lsb >= p.peak_floor)


def score_row(latency_ms: Optional[float], peak_lsb: Optional[float], p: RBMV0Params) -> float:
    """Reflex-consistency score in [0,1]. Floor-fail -> 0.0. Diagonal Mahalanobis, exp-mapped."""
    if not hard_floor(latency_ms, peak_lsb, p):
        return 0.0
    sdl = p.sd_latency if p.sd_latency > 1e-9 else 1e-9
    sdp = p.sd_peak if p.sd_peak > 1e-9 else 1e-9
    d2 = ((latency_ms - p.mu_latency) / sdl) ** 2 + ((peak_lsb - p.mu_peak) / sdp) ** 2
    return max(0.0, min(1.0, math.exp(-0.5 * d2)))


RBM_VERSION = "RBM-v0"


def evaluate(latency_ms: Optional[float], peak_lsb: Optional[float], p: RBMV0Params) -> dict[str, Any]:
    """RBM-v0 PRODUCT surface (grok round-11 fix (b)): BOOLEAN ONLY -- band_member +
    operating_point_fire. The continuous exp(-0.5*d^2) score is DEFERRED to v0.1 (it failed the
    nested-LOO CV<=0.35 stability bar: over-precise per-sample at N=52). Ships what the numbers
    support -- classification at a frozen operating point (TPR~0.90, FAR=0) -- NOT a density score,
    NOT a liveness verdict. score is absent by construction (schema test forbids it)."""
    member = hard_floor(latency_ms, peak_lsb, p)
    fire = member and score_row(latency_ms, peak_lsb, p) >= p.operating_threshold
    return {"band_member": member, "operating_point_fire": fire, "rbm_version": RBM_VERSION,
            "score_status": "deferred_v0_1", "scope": p.scope, "is_liveness_verdict": False}


def load_params(path: str) -> RBMV0Params:
    d = json.load(open(path, encoding="utf-8"))
    return RBMV0Params(**{k: d[k] for k in (
        "mu_latency", "sd_latency", "mu_peak", "sd_peak", "operating_threshold", "n_positives",
        "lat_floor", "lat_ceil", "peak_floor", "scope") if k in d})


# --- pure-Python calibration math (used by the calibrate script; kept here so it's tested) ----------

def fit_moments(latencies: list[float], peaks: list[float]) -> tuple[float, float, float, float]:
    def mean(a): return sum(a) / len(a)
    def sd(a, m): return math.sqrt(sum((x - m) ** 2 for x in a) / len(a))
    ml, mp = mean(latencies), mean(peaks)
    return ml, sd(latencies, ml), mp, sd(peaks, mp)


def roc_auc(pos_scores: list[float], neg_scores: list[float]) -> float:
    """Mann-Whitney-U AUC (pure Python; ties count 0.5). AUC = P(pos > neg)."""
    if not pos_scores or not neg_scores:
        return float("nan")
    wins = 0.0
    for ps in pos_scores:
        for ns in neg_scores:
            wins += 1.0 if ps > ns else (0.5 if ps == ns else 0.0)
    return wins / (len(pos_scores) * len(neg_scores))


def dprime(pos_scores: list[float], neg_scores: list[float]) -> float:
    mp, mn = fit_moments(pos_scores, [0])[0], fit_moments(neg_scores, [0])[0]
    _, sp, _, _ = fit_moments(pos_scores, pos_scores)
    _, sn, _, _ = fit_moments(neg_scores, neg_scores)
    denom = math.sqrt(0.5 * (sp ** 2 + sn ** 2)) or 1e-9
    return (mp - mn) / denom


def operating_threshold(pos_scores: list[float], tpr_target: float = 0.90) -> float:
    """Lowest score achieving TPR>=target on positives (prefer higher tau among ties -> pick the
    score at the (1-target) quantile from the bottom)."""
    s = sorted(pos_scores)
    if not s:
        return 0.0
    idx = int(math.floor((1.0 - tpr_target) * len(s)))
    return s[min(idx, len(s) - 1)]


def far_at(neg_scores: list[float], tau: float) -> float:
    if not neg_scores:
        return 0.0
    return sum(1 for x in neg_scores if x >= tau) / len(neg_scores)
