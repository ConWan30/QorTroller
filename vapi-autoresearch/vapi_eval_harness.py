"""
vapi_eval_harness.py — IMMUTABLE
=================================
The fixed evaluation rubric for VAPI-AutoResearch improvement cycles.
NEVER modify this file. It is the ground truth that prevents drift.

Every proposed change to skill.md or the WHAT_IF corpus is scored
against these criteria. A change must PASS all mandatory checks and
achieve a weighted score >= 0.70 to be committed.

This file has no GPU or ML dependency. All evaluation is:
  1. Rule-based invariant checking (pass/fail)
  2. Weighted scoring against VAPI's documented gaps
  3. WHAT_IF quality assessment (grounded W1, novel W2)

Usage (from vapi_autoresearch.py):
    from vapi_eval_harness import evaluate_proposal
    result = evaluate_proposal(proposal_text, current_skill_md, experiment_log)
    if result.passed:
        commit_proposal(proposal_text)
    else:
        revert_and_log(result.reason)
"""

import re
import json
import time
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# IMMUTABLE INVARIANTS — from VAPI Phase 108 ground truth
# These must all be present and unmodified in any skill.md
# ============================================================

MANDATORY_INVARIANTS = [
    "228 bytes",                          # Wire format
    "SHA-256(raw[:164])",                 # Chain hash
    "NOMINAL sessions only",              # Stable EMA
    "7.009",                              # L4 anomaly threshold
    "5.367",                              # L4 continuity threshold
    "Poseidon(8)",                        # Phase 62 ZK
    "nPublic=5",                          # ZK public signals
    "0.60",                               # Phase 98 W1 threshold
    "0.362",                              # Separation ratio disclosure
    "ratio > 1.0",                        # TGE gate
    "GSR_ENABLED=false",                  # GSR not yet calibrated
    "L6B_ENABLED=false",                  # L6b not yet calibrated
    "dry_run=True",                       # Enforcement state
    "never hard gate",                    # GSR advisory only
    "soulbound",                          # VHP non-transferable
    "BLOCK_QUORUM=0.67",                  # ioSwarm quorum
    "W1",                                 # W1 must be documented
    "separation ratio 0.362",            # Explicit disclosure
    "non-negotiable",                     # Token launch gate
    "TOURNAMENT BLOCKER",                 # Honest gap labeling
]

# ============================================================
# SCORING WEIGHTS — reflect current improvement priorities
# ============================================================

SCORING_WEIGHTS = {
    "invariants_preserved":      0.30,  # Mandatory — all or nothing
    "gap_advancement":           0.25,  # Advances one of the 5 priorities
    "what_if_quality":           0.20,  # W1 grounded, W2 novel
    "phase_coherence":           0.15,  # Consistent with Phase 109–113
    "backward_compatibility":    0.10,  # No regression on Phase 62/66/67
}

# Minimum passing score
PASS_THRESHOLD = 0.70

# ============================================================
# KNOWN GAPS (ground truth from tournament readiness scorecard)
# ============================================================

KNOWN_GAPS = {
    "separation_ratio": {
        "current": 0.362,
        "target": 1.0,
        "status": "BLOCKER",
        "keywords": ["touchpad", "separation", "interperson", "terminal_touchpad"],
    },
    "w1_threshold": {
        "current": 0.60,
        "target": 0.65,
        "status": "DOCUMENTED",
        "keywords": ["W1", "quorum", "homogeneity", "distinct operators"],
    },
    "class_k": {
        "current": "undefined",
        "target": "defined detection approach",
        "status": "OPEN",
        "keywords": ["Class K", "GSR spoofer", "synthetic EDA", "challenge-response"],
    },
    "dry_run": {
        "current": "True",
        "target": "False (after N>=100 adjudications)",
        "status": "BLOCKED",
        "keywords": ["dry_run", "live mode", "enforcement", "adjudication"],
    },
    "vhp_quorum": {
        "current": "single operator",
        "target": "ioSwarm quorum",
        "status": "Phase 110 target",
        "keywords": ["VHP", "quorum", "mint", "ioSwarm", "decentralized"],
    },
}

# ============================================================
# WHAT_IF QUALITY CRITERIA
# ============================================================

WHAT_IF_W1_CRITERIA = [
    "physically grounded OR cryptographically grounded OR economically grounded",
    "not 'server crash' or generic infrastructure failure",
    "specific mechanism of failure described",
    "mitigation available and specified",
]

WHAT_IF_W2_CRITERIA = [
    "genuinely novel — not obvious incremental feature",
    "mechanism described concretely",
    "phase candidate specified",
    "exclusive to VAPI (not replicated by competitors)",
]


@dataclass
class EvalResult:
    passed: bool
    score: float
    subscores: dict
    reason: str
    invariant_failures: list = field(default_factory=list)
    gap_advances: list = field(default_factory=list)
    what_if_assessment: str = ""
    timestamp: float = field(default_factory=time.time)


def check_invariants(proposal_text: str, skill_md_after: str) -> tuple[bool, list]:
    """
    Check that all mandatory invariants are preserved in the post-change skill.md.
    Returns (all_passed, list_of_failures).
    """
    failures = []
    text_to_check = skill_md_after.lower()
    for invariant in MANDATORY_INVARIANTS:
        if invariant.lower() not in text_to_check:
            failures.append(f"MISSING: '{invariant}'")
    return len(failures) == 0, failures


def score_gap_advancement(proposal_text: str) -> tuple[float, list]:
    """
    Score whether the proposal advances one or more known gaps.
    Returns (score 0.0-1.0, list of gaps advanced).
    """
    proposal_lower = proposal_text.lower()
    advances = []
    for gap_name, gap_info in KNOWN_GAPS.items():
        if any(kw.lower() in proposal_lower for kw in gap_info["keywords"]):
            advances.append(gap_name)
    # Each gap advanced adds 0.25, capped at 1.0
    score = min(1.0, len(advances) * 0.25)
    return score, advances


def score_what_if_quality(proposal_text: str) -> tuple[float, str]:
    """
    If proposal contains a WHAT_IF section, score its quality.
    Returns (score 0.0-1.0, assessment string).
    """
    if "[WHAT_IF]" not in proposal_text and "W1 —" not in proposal_text:
        return 0.5, "No WHAT_IF section in proposal (neutral score)"

    assessment_parts = []
    score = 0.0

    # Check W1 quality
    if "W1" in proposal_text:
        w1_section = proposal_text[proposal_text.find("W1"):proposal_text.find("W2")
                                   if "W2" in proposal_text else len(proposal_text)]
        w1_quality_markers = [
            "implication" in w1_section.lower(),
            "mitigation" in w1_section.lower(),
            any(word in w1_section.lower() for word in
                ["cryptograph", "economic", "physical", "stake", "quorum"]),
            len(w1_section) > 200,  # Substantive length
        ]
        w1_score = sum(w1_quality_markers) / len(w1_quality_markers)
        score += w1_score * 0.5
        assessment_parts.append(f"W1 quality: {w1_score:.2f}")

    # Check W2 quality
    if "W2" in proposal_text:
        w2_section = proposal_text[proposal_text.find("W2"):]
        w2_quality_markers = [
            "mechanism" in w2_section.lower(),
            "phase" in w2_section.lower(),
            "exclusive" in w2_section.lower() or "novel" in w2_section.lower(),
            len(w2_section) > 200,
        ]
        w2_score = sum(w2_quality_markers) / len(w2_quality_markers)
        score += w2_score * 0.5
        assessment_parts.append(f"W2 quality: {w2_score:.2f}")

    return score, " | ".join(assessment_parts) if assessment_parts else "WHAT_IF assessed"


def score_phase_coherence(proposal_text: str) -> float:
    """
    Score coherence with Phase 109–113 architecture.
    """
    phase_109_113_markers = [
        "ioswarm", "ioSwarm", "IoSwarm",
        "quorum", "BLOCK_QUORUM",
        "VHP auth gate", "vhp_authorization",
        "AdjudicationRegistry", "PoAd",
        "SeparationRatioRegistry",
        "IoSwarmConsensusAggregator",
        "VAPISwarmOperatorGate",
        "Phase 109", "Phase 110", "Phase 111",
        "Phase 112", "Phase 113",
        "node emulator", "ioswarm_node_emulator",
    ]
    proposal_lower = proposal_text.lower()
    matches = sum(1 for m in phase_109_113_markers if m.lower() in proposal_lower)
    if matches == 0:
        return 0.5  # Neutral if not ioSwarm-related
    return min(1.0, 0.5 + matches * 0.1)


def score_backward_compatibility(proposal_text: str) -> float:
    """
    Check that proposal doesn't regress Phase 62/66/67 commitments.
    """
    regression_red_flags = [
        "change the wire format",
        "modify sha-256",
        "remove poseidon",
        "relax the threshold",
        "weaken the commitment",
        "bypass the ceremony",
        "skip the invariant",
    ]
    proposal_lower = proposal_text.lower()
    for flag in regression_red_flags:
        if flag in proposal_lower:
            return 0.0  # Hard fail
    return 1.0


def evaluate_proposal(
    proposal_text: str,
    skill_md_after: str,
    experiment_context: Optional[str] = None,
) -> EvalResult:
    """
    Main evaluation entry point. Called by vapi_autoresearch.py.

    Args:
        proposal_text: The proposed change description + any new content
        skill_md_after: The full skill.md text AFTER the proposed change
        experiment_context: Optional context from program.md

    Returns:
        EvalResult with pass/fail decision and detailed scoring
    """
    subscores = {}

    # 1. Invariant check (mandatory — failure here = immediate reject)
    inv_passed, inv_failures = check_invariants(proposal_text, skill_md_after)
    subscores["invariants_preserved"] = 1.0 if inv_passed else 0.0

    if not inv_passed:
        return EvalResult(
            passed=False,
            score=0.0,
            subscores=subscores,
            reason=f"INVARIANT FAILURE — {len(inv_failures)} violations: "
                   f"{'; '.join(inv_failures[:3])}",
            invariant_failures=inv_failures,
        )

    # 2. Gap advancement
    gap_score, gap_advances = score_gap_advancement(proposal_text)
    subscores["gap_advancement"] = gap_score

    # 3. WHAT_IF quality
    wif_score, wif_assessment = score_what_if_quality(proposal_text)
    subscores["what_if_quality"] = wif_score

    # 4. Phase coherence
    phase_score = score_phase_coherence(proposal_text)
    subscores["phase_coherence"] = phase_score

    # 5. Backward compatibility
    compat_score = score_backward_compatibility(proposal_text)
    subscores["backward_compatibility"] = compat_score

    if compat_score == 0.0:
        return EvalResult(
            passed=False,
            score=0.0,
            subscores=subscores,
            reason="BACKWARD COMPATIBILITY FAILURE — proposal regresses frozen invariants",
            invariant_failures=["backward compatibility red flag detected"],
        )

    # Weighted total
    total = sum(
        SCORING_WEIGHTS[k] * subscores[k]
        for k in SCORING_WEIGHTS
        if k in subscores
    )

    passed = total >= PASS_THRESHOLD
    reason = (
        f"PASS (score={total:.3f})" if passed
        else f"FAIL (score={total:.3f} < threshold={PASS_THRESHOLD})"
    )

    return EvalResult(
        passed=passed,
        score=total,
        subscores=subscores,
        reason=reason,
        invariant_failures=inv_failures,
        gap_advances=gap_advances,
        what_if_assessment=wif_assessment,
    )


if __name__ == "__main__":
    # Smoke test — verify harness is functional
    test_proposal = """
    Improve WHAT_IF mode for W1 ioSwarm node homogeneity risk.
    
    [WHAT_IF]
    W1 — Failure: ioSwarm node pool homogeneity collapses BLOCK_QUORUM=0.67 guarantee.
    Implication: if 4/5 nodes are operated by correlated entity, quorum is manipulable.
    Mitigation: VAPISwarmOperatorGate.sol enforces minimum 3 distinct staker addresses.
    Economic grounding: stake-weight cap at 1.5x prevents whale capture.
    
    W2 — Opportunity: Proof of Adjudication (PoAd) as second composable primitive.
    Mechanism: PoAd_hash = SHA-256(sorted_verdicts + quorum + ts_ns) anchored on-chain.
    Phase candidate: Phase 111, AdjudicationRegistry.sol.
    Exclusive to VAPI: presupposes PoAC as input — no other protocol has committed features.
    """

    test_skill_after = """
    This is a test skill.md containing:
    228 bytes wire format SHA-256(raw[:164]) NOMINAL sessions only
    7.009 anomaly threshold 5.367 continuity Poseidon(8) nPublic=5
    0.60 threshold W1 documented 0.362 separation ratio ratio > 1.0
    GSR_ENABLED=false L6B_ENABLED=false dry_run=True never hard gate
    soulbound VHP BLOCK_QUORUM=0.67 W1 separation ratio 0.362
    non-negotiable TOURNAMENT BLOCKER
    """

    result = evaluate_proposal(test_proposal, test_skill_after)
    print(f"Eval result: {'PASS' if result.passed else 'FAIL'}")
    print(f"Score: {result.score:.3f}")
    print(f"Subscores: {json.dumps(result.subscores, indent=2)}")
    print(f"Gap advances: {result.gap_advances}")
    print(f"WHAT_IF: {result.what_if_assessment}")
