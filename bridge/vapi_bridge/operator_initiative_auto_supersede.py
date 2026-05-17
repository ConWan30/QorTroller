"""Phase O1-D-AUTO-SUPERSEDE — Empirical-Evidence Supersession primitive.

VAPI-O3-SUPERSEDE-v1 FROZEN-v1 attestation primitive (11th in the
PATTERN-017 family after GIC + WEC + VAME + CORPUS-SNAPSHOT + CONSENT +
BIOMETRIC-SNAPSHOT + LISTING-v1 + FRR + ZKBA + POSEIDON-AS).

═════════════════════════════════════════════════════════════════════════
Architectural intent
═════════════════════════════════════════════════════════════════════════

The Phase O1 D Operator Initiative advancement watcher gates the
O2_SUGGEST → O3_ACTING transition on a 504h (3-week) calendar floor
(PHASE_O3_SUGGEST_MIN_HOURS). That floor was designed as DEFENSE-IN-
DEPTH when no empirical evidence existed about VAPI's draft-generation
pace, drift detection latency, or operator-review behavior — a
conservative placeholder for the pre-deployment case.

When empirical evidence DOES exist — every empirically-clearable gate
demonstrably cleared — the 504h placeholder has no remaining empirical
role. Drift detection latency runs on minute-cadence polling; FSCA
contradiction surfacing runs every 15 minutes; operator review velocity
is real-time. The 504h floor's safety claim ("we haven't observed long
enough") becomes structurally vacuous when continuous-clean observation
of the OTHER gates is the actual safety signal.

This primitive codifies that principle as a cryptographically-attested
event: when supersession eligibility is met, the watcher records a
SHA-256 commitment to the gate-state evidence at the moment of
supersession. The attestation hash makes the supersession decision
auditable + reproducible by any third party with the underlying gate-
state values.

═════════════════════════════════════════════════════════════════════════
FROZEN FORMULA v1
═════════════════════════════════════════════════════════════════════════

  attestation_hash = SHA-256(
      b"VAPI-O3-SUPERSEDE-v1"            (20 bytes)
   || agent_id_be(32)                    (32 bytes) — canonical agent name padded
   || draft_count_be(8)                  (8 bytes)  — uint64
   || disagreement_rate_milli_be(4)      (4 bytes)  — uint32 milli (rate × 1e6)
   || bundle_drift_count_30d_be(4)       (4 bytes)
   || scope_drift_count_30d_be(4)        (4 bytes)
   || operator_dual_key_byte(1)          (1 byte)   — bool
   || kms_hsm_production_byte(1)         (1 byte)
   || github_app_oauth_byte(1)           (1 byte)
   || marketplace_curator_role_byte(1)   (1 byte)
   || false_positive_rate_milli_be(4)    (4 bytes)
   || shadow_age_at_supersede_hours_be(4)(4 bytes)  — uint32 hours (capped)
   || ts_ns_be(8)                        (8 bytes)
  )                                     = 92 bytes → 32 bytes

Total preimage: 92 bytes. Same SHA-256 family as the other PATTERN-017
primitives. Domain tag VAPI-O3-SUPERSEDE-v1 distinguishes from all
other commitment families.

═════════════════════════════════════════════════════════════════════════
ELIGIBILITY CRITERIA
═════════════════════════════════════════════════════════════════════════

Supersession is eligible for an agent when ALL of these hold:

  1. draft_count >= PHASE_O3_DRAFT_PAYLOAD_MIN (50)
  2. disagreement_rate <= PHASE_O3_DISAGREEMENT_RATE_MAX (5%) — using
     STRICTER target 0% for supersession justification (cleaner evidence)
  3. bundle_hash_drift_count_30d == 0
  4. scope_hash_governance_drift_count_30d == 0
  5. operator_dual_key_present == True
  6. Agent-specific operator flags True (kms_hsm for Sentry+Guardian;
     +github_app_oauth for Guardian; +marketplace_curator_role for
     Curator; false_positive_rate == 0% for Curator)

When eligibility is met, the supersession EVENT may be recorded by
writing to `operator_initiative_auto_supersede_log` with the
attestation hash + the gate-state evidence dict. The watcher's
o3_ready logic THEN treats the calendar gate as satisfied IF the
operator-controlled cfg flag `phase_o3_auto_supersede_enabled` is True
(default False — conservative opt-in).

═════════════════════════════════════════════════════════════════════════
PRIMITIVE INVARIANTS (PV-CI candidates)
═════════════════════════════════════════════════════════════════════════

INV-O3-SUPERSEDE-001 — Domain tag `b"VAPI-O3-SUPERSEDE-v1"` literal
INV-O3-SUPERSEDE-002 — `compute_supersede_attestation_hash` function
                        signature preserved
INV-O3-SUPERSEDE-003 — `operator_initiative_auto_supersede_log` table
                        schema + insert helper

═════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional


# FROZEN-v1 domain tag — distinguishes this primitive's commitments from
# all other PATTERN-017 family members. Length = 20 bytes.
SUPERSEDE_DOMAIN_TAG = b"VAPI-O3-SUPERSEDE-v1"

# Stricter-than-watcher rate target for supersession justification.
# The watcher's gate is <= 0.05 (5%); supersession evidence requires
# 0.0 (zero disagreement observed). Codified to make the attestation
# unambiguous — "supersession was earned by ZERO disagreement, not
# barely under threshold."
SUPERSEDE_DISAGREEMENT_RATE_STRICT_MAX = 0.0

# Curator-specific: false positive rate must be exactly 0 for
# supersession (matches the gate's hard zero-tolerance for FP).
SUPERSEDE_FALSE_POSITIVE_RATE_STRICT_MAX = 0.0

# Minimum draft count for supersession evidence (matches gate threshold).
SUPERSEDE_DRAFT_PAYLOAD_MIN = 50


@dataclass(frozen=True, slots=True)
class SupersedeEvidence:
    """Per-agent gate-state snapshot at the moment of supersession evaluation.

    All fields are inputs to the FROZEN attestation hash. Tampering with
    any field would produce a different hash; the hash MUST be reproducible
    by any third party with this same evidence record.
    """

    agent_id: str  # canonical name: anchor_sentry / guardian / curator
    draft_count: int
    disagreement_rate: float
    bundle_drift_count_30d: int
    scope_drift_count_30d: int
    operator_dual_key_present: bool
    kms_hsm_production_ready: bool
    github_app_oauth_tokens_valid: bool
    marketplace_curator_role_assigned: bool
    false_positive_rate: float
    shadow_age_at_supersede_hours: float
    ts_ns: int


@dataclass(frozen=True, slots=True)
class SupersedeEligibilityResult:
    """Result of evaluating supersession eligibility for one agent."""

    agent_id: str
    eligible: bool
    blockers: tuple[str, ...]
    evidence: SupersedeEvidence
    attestation_hash_hex: str  # only meaningful when eligible=True
    error: Optional[str] = None


def _canonical_agent_id_bytes(agent_id: str) -> bytes:
    """Convert canonical agent_id name to 32-byte field for hashing.

    Pads with NUL bytes to 32 bytes; truncates if name > 32 chars
    (would never happen in practice — names are <16 chars). Lowercase
    ASCII normalization.
    """
    raw = agent_id.lower().encode("ascii", errors="replace")
    if len(raw) > 32:
        raw = raw[:32]
    return raw.ljust(32, b"\x00")


def compute_supersede_attestation_hash(evidence: SupersedeEvidence) -> str:
    """FROZEN-v1 attestation hash.

    See module docstring for byte layout. Returns 64-char lowercase hex.
    """
    # Encode each field deterministically. Floats → uint via milli scaling.
    disagreement_milli = int(round(max(0.0, evidence.disagreement_rate) * 1_000_000))
    if disagreement_milli > 0xFFFFFFFF:
        disagreement_milli = 0xFFFFFFFF  # cap at uint32 max
    fp_milli = int(round(max(0.0, evidence.false_positive_rate) * 1_000_000))
    if fp_milli > 0xFFFFFFFF:
        fp_milli = 0xFFFFFFFF
    shadow_age_hours_int = int(round(max(0.0, evidence.shadow_age_at_supersede_hours)))
    if shadow_age_hours_int > 0xFFFFFFFF:
        shadow_age_hours_int = 0xFFFFFFFF

    preimage = b"".join([
        SUPERSEDE_DOMAIN_TAG,                            # 20 B
        _canonical_agent_id_bytes(evidence.agent_id),    # 32 B
        evidence.draft_count.to_bytes(8, "big"),         # 8 B
        disagreement_milli.to_bytes(4, "big"),           # 4 B
        evidence.bundle_drift_count_30d.to_bytes(4, "big"),  # 4 B
        evidence.scope_drift_count_30d.to_bytes(4, "big"),   # 4 B
        bytes([1 if evidence.operator_dual_key_present else 0]),         # 1 B
        bytes([1 if evidence.kms_hsm_production_ready else 0]),          # 1 B
        bytes([1 if evidence.github_app_oauth_tokens_valid else 0]),     # 1 B
        bytes([1 if evidence.marketplace_curator_role_assigned else 0]), # 1 B
        fp_milli.to_bytes(4, "big"),                     # 4 B
        shadow_age_hours_int.to_bytes(4, "big"),         # 4 B
        evidence.ts_ns.to_bytes(8, "big"),               # 8 B
    ])
    # Sanity: preimage MUST be 92 bytes (INV-O3-SUPERSEDE-002 guards
    # against silent byte-layout drift). 20+32+8+4+4+4+1+1+1+1+4+4+8=92.
    if len(preimage) != 92:
        raise ValueError(
            f"VAPI-O3-SUPERSEDE-v1 preimage length drift: {len(preimage)} != 92 "
            "— byte layout was changed without bumping the domain tag"
        )
    return hashlib.sha256(preimage).hexdigest()


def evaluate_supersede_eligibility_for_agent(
    *,
    agent_id: str,
    draft_count: int,
    disagreement_rate: float,
    bundle_drift_count_30d: int,
    scope_drift_count_30d: int,
    operator_dual_key_present: bool,
    kms_hsm_production_ready: bool,
    github_app_oauth_tokens_valid: bool,
    marketplace_curator_role_assigned: bool,
    false_positive_rate: float,
    shadow_age_at_supersede_hours: float,
    ts_ns: int,
) -> SupersedeEligibilityResult:
    """Per-agent supersede eligibility evaluation.

    Returns SupersedeEligibilityResult with attestation hash computed if
    eligible. Never raises — returns ineligible result with error field
    populated on any exception.
    """
    try:
        ev = SupersedeEvidence(
            agent_id=agent_id,
            draft_count=int(draft_count),
            disagreement_rate=float(disagreement_rate),
            bundle_drift_count_30d=int(bundle_drift_count_30d),
            scope_drift_count_30d=int(scope_drift_count_30d),
            operator_dual_key_present=bool(operator_dual_key_present),
            kms_hsm_production_ready=bool(kms_hsm_production_ready),
            github_app_oauth_tokens_valid=bool(github_app_oauth_tokens_valid),
            marketplace_curator_role_assigned=bool(marketplace_curator_role_assigned),
            false_positive_rate=float(false_positive_rate),
            shadow_age_at_supersede_hours=float(shadow_age_at_supersede_hours),
            ts_ns=int(ts_ns),
        )

        blockers: list[str] = []
        if ev.draft_count < SUPERSEDE_DRAFT_PAYLOAD_MIN:
            blockers.append(
                f"draft_count_{ev.draft_count}_under_supersede_min_{SUPERSEDE_DRAFT_PAYLOAD_MIN}"
            )
        if ev.disagreement_rate > SUPERSEDE_DISAGREEMENT_RATE_STRICT_MAX:
            blockers.append(
                f"disagreement_rate_{ev.disagreement_rate:.6f}_over_supersede_strict_max_"
                f"{SUPERSEDE_DISAGREEMENT_RATE_STRICT_MAX}"
            )
        if ev.bundle_drift_count_30d != 0:
            blockers.append(f"bundle_drift_30d_{ev.bundle_drift_count_30d}_not_zero")
        if ev.scope_drift_count_30d != 0:
            blockers.append(f"scope_drift_30d_{ev.scope_drift_count_30d}_not_zero")
        if not ev.operator_dual_key_present:
            blockers.append("operator_dual_key_not_present")

        # Agent-specific flag requirements
        aid_lower = agent_id.lower()
        if aid_lower in ("anchor_sentry", "guardian"):
            if not ev.kms_hsm_production_ready:
                blockers.append("kms_hsm_production_not_ready")
        if aid_lower == "guardian":
            if not ev.github_app_oauth_tokens_valid:
                blockers.append("github_app_oauth_tokens_not_valid")
        if aid_lower == "curator":
            if not ev.marketplace_curator_role_assigned:
                blockers.append("marketplace_curator_role_not_assigned")
            if ev.false_positive_rate > SUPERSEDE_FALSE_POSITIVE_RATE_STRICT_MAX:
                blockers.append(
                    f"false_positive_rate_{ev.false_positive_rate:.6f}_over_strict_max"
                )

        eligible = len(blockers) == 0
        hash_hex = compute_supersede_attestation_hash(ev) if eligible else ""

        return SupersedeEligibilityResult(
            agent_id=agent_id,
            eligible=eligible,
            blockers=tuple(blockers),
            evidence=ev,
            attestation_hash_hex=hash_hex,
        )
    except Exception as exc:  # fail-open: ineligible on any error
        # Defensive: produce a non-eligible result with error populated.
        dummy_ev = SupersedeEvidence(
            agent_id=agent_id, draft_count=0, disagreement_rate=1.0,
            bundle_drift_count_30d=999, scope_drift_count_30d=999,
            operator_dual_key_present=False, kms_hsm_production_ready=False,
            github_app_oauth_tokens_valid=False, marketplace_curator_role_assigned=False,
            false_positive_rate=1.0, shadow_age_at_supersede_hours=0.0, ts_ns=0,
        )
        return SupersedeEligibilityResult(
            agent_id=agent_id,
            eligible=False,
            blockers=("evaluation_error",),
            evidence=dummy_ev,
            attestation_hash_hex="",
            error=f"{type(exc).__name__}: {exc}",
        )
