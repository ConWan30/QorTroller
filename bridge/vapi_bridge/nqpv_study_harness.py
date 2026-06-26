"""NQPV PILOT study harness (RETINA-EXCL-2 defensibility study, critical-path step 6).

Consumes a labeled corpus (human positives from ``nqpv_corpus_loader`` + adversary negatives from
``nqpv_adversary_synth``), fuses every record through ``NovelPresenceFusionOrchestrator.fuse()``, and
computes the defensibility readout the RETINA-EXCL-2 spec mandates:

  * TAR (true-accept rate)  = fraction of HUMAN records that fuse to a human-side verdict.
  * FAR (false-accept rate) = fraction of ADVERSARY records that fuse to a human-side verdict.
  * ROC sweep over the threshold grid.
  * The ANTI-GCAP RAIL: fused human-TAR must be >= the best single-oracle human-TAR (fusion must NOT
    collapse human acceptance below what one oracle alone achieves -- the banked GCAP trap where a
    conjunctive multi-oracle vote drove human TAR 0.806 -> 0.581). A point that lowers human TAR is
    disqualified no matter how good its FAR.
  * PILOT PROJECTION: optionally abstain the oracles that are not yet live (PoEP, coupled-retina),
    leaving only what the live USB loop actually co-captures. This is how the harness surfaces the
    load-bearing finding -- in the single-live-oracle pilot regime the fusion CANNOT separate a
    replay/macro-with-human-physics from a human, so defensibility REQUIRES the presence oracles to
    go live. The harness reports that honestly as FAIL (measurable but no qualifying operating
    point), distinct from INSUFFICIENT_DATA (not measurable).

The harness sets NO certified operating point -- it produces the evidence; the operator/study sets
weights+threshold. ADVISORY until a FULL-tier run on real adversary captures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from vapi_bridge.novel_presence_fusion import NQPVVerdict, NovelPresenceFusionOrchestrator
from vapi_bridge.nqpv_corpus_loader import (
    LABEL_ADVERSARY,
    LABEL_HUMAN,
    NqpvCorpusRecord,
    fuse_record,
)

# Verdicts that count as "accepted as a present human".
HUMAN_SIDE: frozenset[NQPVVerdict] = frozenset(
    {NQPVVerdict.CONSISTENT_HUMAN, NQPVVerdict.CONSISTENT_HUMAN_VERIFIED_HARDWARE}
)

# Oracles that the live USB loop actually co-captures today (used as the default PILOT live set).
PILOT_LIVE_ORACLES: frozenset[str] = frozenset({"l4l5l6"})
# Oracles available once the co-capture sidecar (cco_presence_ceiling_candidate) is persisted.
COCAPTURE_LIVE_ORACLES: frozenset[str] = frozenset({"l4l5l6", "cco"})

_DEFAULT_GRID: tuple[float, ...] = tuple(round(0.05 * i, 2) for i in range(0, 21))  # 0.00 .. 1.00


def is_human_side(verdict: NQPVVerdict) -> bool:
    return verdict in HUMAN_SIDE


def _project(rec: NqpvCorpusRecord, live: Optional[frozenset[str]]) -> NqpvCorpusRecord:
    """Return a copy of ``rec`` with oracles outside ``live`` abstained (None). ``live=None`` = full."""
    if live is None:
        return rec
    from dataclasses import replace
    return replace(
        rec,
        cco_tier=rec.cco_tier if "cco" in live else None,
        l4_l5_l6_ok=rec.l4_l5_l6_ok if "l4l5l6" in live else None,
        poep_present=rec.poep_present if "poep" in live else None,
        retina_coupled_verdict=rec.retina_coupled_verdict if "retina" in live else None,
    )


def _retina_accepts(coupled: Optional[str]) -> bool:
    if not coupled:
        return False
    v = coupled.upper()
    return ("COUPLED_CLEAN" in v or "LIVE_COHERENT" in v or "PLAUSIBLE" in v) and "IMPLAUSIBLE" not in v


def _single_oracle_accepts(rec: NqpvCorpusRecord, oracle: str) -> Optional[bool]:
    """Would THIS one oracle alone accept the record as human? None = oracle abstains (can't accept)."""
    if oracle == "l4l5l6":
        return rec.l4_l5_l6_ok
    if oracle == "poep":
        return rec.poep_present
    if oracle == "cco":
        return None if rec.cco_tier is None else ("FAIL" not in rec.cco_tier.upper())
    if oracle == "retina":
        return None if rec.retina_coupled_verdict is None else _retina_accepts(rec.retina_coupled_verdict)
    return None


@dataclass(frozen=True, slots=True)
class RocPoint:
    threshold: float
    tar: float
    far: float
    anti_gcap_ok: bool          # fused TAR >= best single-oracle TAR at this regime
    best_single_tar: float


@dataclass(frozen=True, slots=True)
class StudyReport:
    regime: str                 # "full" | "pilot" | "cocapture"
    n_human: int
    n_adversary: int
    measurable: bool            # at least one human record has a live (non-abstaining) oracle
    best_single_tar: float
    best_single_oracle: str
    roc: list[RocPoint] = field(default_factory=list)
    operating_point: Optional[RocPoint] = None   # the qualifying point, if any
    feasibility: str = "INSUFFICIENT_DATA"       # PASS | FAIL | INSUFFICIENT_DATA
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "regime": self.regime,
            "n_human": self.n_human,
            "n_adversary": self.n_adversary,
            "measurable": self.measurable,
            "best_single_tar": round(self.best_single_tar, 4),
            "best_single_oracle": self.best_single_oracle,
            "feasibility": self.feasibility,
            "operating_point": (
                None if self.operating_point is None else {
                    "threshold": self.operating_point.threshold,
                    "tar": round(self.operating_point.tar, 4),
                    "far": round(self.operating_point.far, 4),
                    "anti_gcap_ok": self.operating_point.anti_gcap_ok,
                }
            ),
            "roc": [
                {"threshold": p.threshold, "tar": round(p.tar, 4), "far": round(p.far, 4),
                 "anti_gcap_ok": p.anti_gcap_ok}
                for p in self.roc
            ],
            "notes": self.notes,
        }


def _rate(records: list[NqpvCorpusRecord], threshold: float, weights, orch) -> float:
    if not records:
        return 0.0
    hits = sum(1 for r in records if is_human_side(fuse_record(r, orch, weights=weights, threshold=threshold).verdict))
    return hits / len(records)


def _best_single_tar(humans: list[NqpvCorpusRecord], live: Optional[frozenset[str]]) -> tuple[float, str]:
    """Best human-TAR achievable by any single LIVE oracle alone (the anti-GCAP comparison floor)."""
    candidates = live if live is not None else frozenset({"l4l5l6", "poep", "cco", "retina"})
    best, best_oracle = 0.0, "none"
    for oracle in sorted(candidates):
        accepts = [_single_oracle_accepts(r, oracle) for r in humans]
        considered = [a for a in accepts if a is not None]
        if not considered:
            continue
        tar = sum(1 for a in considered if a) / len(humans)  # abstain counts as non-accept for that oracle
        if tar > best:
            best, best_oracle = tar, oracle
    return best, best_oracle


def run_study(
    records: Iterable[NqpvCorpusRecord],
    *,
    weights: Optional[dict[str, float]] = None,
    live_oracles: Optional[frozenset[str]] = None,
    far_target: float = 0.05,
    tar_floor: float = 0.80,
    grid: tuple[float, ...] = _DEFAULT_GRID,
    regime_name: Optional[str] = None,
) -> StudyReport:
    """Run the defensibility study over a labeled corpus.

    ``live_oracles``: None = full regime (all captured oracles); a set = project to that live set
    (e.g. ``PILOT_LIVE_ORACLES``). ``far_target`` / ``tar_floor`` define a qualifying operating point;
    a point also MUST satisfy the anti-GCAP rail (fused TAR >= best single-oracle TAR).
    """
    recs = [_project(r, live_oracles) for r in records]
    humans = [r for r in recs if r.label == LABEL_HUMAN]
    advs = [r for r in recs if r.label == LABEL_ADVERSARY]
    regime = regime_name or ("full" if live_oracles is None
                             else "pilot" if live_oracles == PILOT_LIVE_ORACLES
                             else "cocapture" if live_oracles == COCAPTURE_LIVE_ORACLES
                             else "projected")
    best_single, best_oracle = _best_single_tar(humans, live_oracles)
    measurable = any(r.live_oracle_count > 0 for r in humans) and bool(advs)

    if not humans or not advs or not measurable:
        return StudyReport(
            regime=regime, n_human=len(humans), n_adversary=len(advs), measurable=measurable,
            best_single_tar=best_single, best_single_oracle=best_oracle,
            feasibility="INSUFFICIENT_DATA",
            notes=("no human records" if not humans else "no adversary records" if not advs
                   else "all human oracles abstain in this regime -- not measurable"),
        )

    orch = NovelPresenceFusionOrchestrator()
    roc: list[RocPoint] = []
    for thr in grid:
        tar = _rate(humans, thr, weights, orch)
        far = _rate(advs, thr, weights, orch)
        roc.append(RocPoint(threshold=thr, tar=tar, far=far,
                            anti_gcap_ok=(tar >= best_single - 1e-9), best_single_tar=best_single))

    # Qualifying operating point: FAR<=target AND TAR>=floor AND anti-GCAP holds. Prefer lowest FAR,
    # then highest TAR.
    qualifying = [p for p in roc if p.far <= far_target and p.tar >= tar_floor and p.anti_gcap_ok]
    op = min(qualifying, key=lambda p: (p.far, -p.tar)) if qualifying else None
    if op is not None:
        feasibility, notes = "PASS", (
            f"qualifying operating point at threshold={op.threshold} (TAR={op.tar:.3f}, "
            f"FAR={op.far:.3f}, anti-GCAP holds vs best-single {best_oracle}={best_single:.3f})"
        )
    else:
        feasibility, notes = "FAIL", (
            f"no operating point meets FAR<={far_target} AND TAR>={tar_floor} AND anti-GCAP "
            f"(best-single {best_oracle}={best_single:.3f}) in the '{regime}' regime"
        )
    return StudyReport(
        regime=regime, n_human=len(humans), n_adversary=len(advs), measurable=True,
        best_single_tar=best_single, best_single_oracle=best_oracle, roc=roc,
        operating_point=op, feasibility=feasibility, notes=notes,
    )
