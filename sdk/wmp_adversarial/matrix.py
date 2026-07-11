"""AH-1 adversarial matrix runner — the `run_forgery_matrix.py` analog.

`holds == True` iff every registered attack hit its EXPECTED outcome. A vector's
`ok` is True when its classification matches the design's expectation:

  * CAUGHT               — forgery REJECTED at the expected check (logic-level kill)
  * OUT-OF-SCOPE-DOCUMENTED — not WMP-3's job (strata/manifest) or a crypto/chain assumption
  * GAP-FOUND            — logic-level forgery PASSED at bar → a real finding (holds -> False
                           until the verifier is fixed and the attack re-proven)

C1 registers A1 (matrix-swap). Later cycles append A2..A17 constructors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sdk.wmp_verify import verify_bundle  # noqa: E402
from . import attacks  # noqa: E402

CAUGHT = "CAUGHT"
GAP_FOUND = "GAP-FOUND"
GAP_FIXED = "GAP-FOUND-AND-FIXED"
OUT_OF_SCOPE = "OUT-OF-SCOPE-DOCUMENTED"


@dataclass
class AttackResult:
    id: str
    vector: str
    target_check: str
    expected: str
    result: str
    evidence: str
    ok: bool

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "vector": self.vector,
            "target_check": self.target_check,
            "expected": self.expected,
            "result": self.result,
            "evidence": self.evidence,
            "ok": self.ok,
        }


@dataclass
class MatrixResult:
    results: list = field(default_factory=list)

    @property
    def holds(self) -> bool:
        return bool(self.results) and all(r.ok for r in self.results)

    def to_dict(self) -> dict:
        return {
            "holds": self.holds,
            "banked": sum(1 for r in self.results if r.ok),
            "total": len(self.results),
            "results": [r.to_dict() for r in self.results],
        }


# ── vector runners ───────────────────────────────────────────────────────

def _run_a1(base: dict) -> AttackResult:
    """A1 matrix-swap — expected CAUGHT at matrix_root_rehash."""
    kw = attacks.honest_kwargs(base)
    forged = attacks.matrix_swap(base)
    res = verify_bundle(forged, **kw)
    rehash = res.checks.get("matrix_root_rehash", {})
    caught = (res.overall == "REJECTED") and (rehash.get("passed") is False)
    return AttackResult(
        id="A1",
        vector="matrix-swap",
        target_check="matrix_root_rehash",
        expected="REJECTED @ matrix_root_rehash (Poseidon mismatch)",
        result=CAUGHT if caught else GAP_FOUND,
        evidence="test_A1_matrix_swap_rejected + UC-1 full-path drill "
                 "(audits/wmp-phase2-first-real-bundle-2026-07-11.md L25)",
        ok=caught,
    )


def _run_a3(base: dict) -> AttackResult:
    """A3 gamer-address swap — expected CAUGHT at consent (oracle says not-granted)."""
    kw = attacks.honest_kwargs(base)
    forged = attacks.gamer_address_swap(base)
    res = verify_bundle(forged, **kw)
    consent = res.checks.get("consent", {})
    # CAUGHT only at the real bar: the injected oracle actually ran (stubbed False)
    # AND returned not-granted (passed False).
    caught = (
        res.overall == "REJECTED"
        and consent.get("passed") is False
        and consent.get("stubbed") is False
    )
    return AttackResult(
        id="A3",
        vector="gamer-address-swap",
        target_check="consent",
        expected="REJECTED @ consent (on-chain consent not granted for the swapped gamer)",
        result=CAUGHT if caught else GAP_FOUND,
        evidence="test_A3_gamer_swap_rejected (+ surgical + gap-watch tests); consent oracle "
                 "injected — runner w/o --consent-registry is honest misconfig, not caught",
        ok=caught,
    )


def _run_a15(base: dict) -> AttackResult:
    """A15 forbidden-key smuggle — GAP-FOUND-AND-FIXED.

    Was a real gap (probe 2026-07-11: a raw biometric key rode through to
    VERIFIED). Fixed C3b: check_scope_honesty now scans the payload for the
    published FORBIDDEN_COLUMNS. Caught across all three placements.
    """
    kw = attacks.honest_kwargs(base)
    caught = True
    for where in ("top", "extra_metadata", "channel"):
        res = verify_bundle(attacks.forbidden_key_smuggle(base, where=where), **kw)
        scope = res.checks.get("scope_honesty", {})
        if not (res.overall == "REJECTED" and scope.get("passed") is False):
            caught = False
            break
    return AttackResult(
        id="A15",
        vector="forbidden-key-smuggle",
        target_check="scope_honesty",
        expected="REJECTED @ scope_honesty (post-phi data-floor breach)",
        result=GAP_FIXED if caught else GAP_FOUND,
        evidence="F-AH1-A15: real gap (probe 2026-07-11) fixed by the payload forbidden-key "
                 "scan in check_scope_honesty; test_A15_* (top / extra_metadata / channel)",
        ok=caught,
    )


# id -> runner. Later cycles append the remaining A2..A17.
VECTORS = {
    "A1": _run_a1,
    "A3": _run_a3,
    "A15": _run_a15,
}


def run_one(vector_id: str, base: dict | None = None) -> AttackResult:
    if vector_id not in VECTORS:
        raise KeyError(f"unknown vector {vector_id!r}; registered: {sorted(VECTORS)}")
    base = base if base is not None else attacks.load_uc1_bundle()
    return VECTORS[vector_id](base)


def run_all(base: dict | None = None) -> MatrixResult:
    base = base if base is not None else attacks.load_uc1_bundle()
    return MatrixResult(results=[fn(base) for fn in VECTORS.values()])
