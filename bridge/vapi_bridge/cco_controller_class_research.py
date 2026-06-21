"""CCO Phase G — controller-class research scaffold (UNVALIDATED by default).

Maps registered CCO profiles to the three empirical research tiers from
``CCO_POEP_FUSION_v4.md`` §Phase G (minimal pad / mid-tier / premium Edge).
Surfaces measurement grade honestly — no partner claim above what corpus supports.

Design: ``wiki/methodology/CCO_PHASE_G_RESEARCH_v1.md``
"""
from __future__ import annotations

from typing import Any, Literal

_SCHEMA = "qortroller-controller-class-research-v1"
_POLICY_REF = "CCO_POEP_FUSION_v4_PHASE_G"
PHASE_G_TARGET_N = 50

ControllerClassTier = Literal["MINIMAL_PAD", "MID_TIER", "PREMIUM_EDGE"]
MeasurementGrade = Literal["UNVALIDATED", "PARTIAL", "VALIDATED"]
MeasurementStatus = Literal["pending", "reached", "deferred"]

_TIER_VALUES: frozenset[str] = frozenset({"MINIMAL_PAD", "MID_TIER", "PREMIUM_EDGE"})

_DEFERRED_REASON = (
    "Operator-deferred: no reference hardware available for this tier. "
    "P-T0 minimal-pad claims remain blocked."
)

_PROFILE_TIER: dict[str, ControllerClassTier] = {
    "hori_fighting_commander_ps5_v1": "MINIMAL_PAD",
    "xbox_elite_s2_v1": "MID_TIER",
    "sony_dualsense_v1": "MID_TIER",
    "scuf_reflex_pro_v1": "MID_TIER",
    "sony_dualshock_edge_v1": "PREMIUM_EDGE",
    "battle_beaver_dualshock_edge_v1": "PREMIUM_EDGE",
}

_TIER_MEASUREMENT_GRADE: dict[ControllerClassTier, MeasurementGrade] = {
    "MINIMAL_PAD": "UNVALIDATED",
    "MID_TIER": "UNVALIDATED",
    "PREMIUM_EDGE": "PARTIAL",
}

_TIER_PARTNER_CEILING: dict[ControllerClassTier, str] = {
    "MINIMAL_PAD": "P-T0",
    "MID_TIER": "P-T1",
    "PREMIUM_EDGE": "P-T3",
}

_TIER_EMPIRICAL_GATES: dict[ControllerClassTier, tuple[str, ...]] = {
    "MINIMAL_PAD": (
        "Per-class L6B reflex corpus N>=50",
        "PoEP device-auth verifier characterization",
        "Inter-player separability not assumed transferable",
    ),
    "MID_TIER": (
        "Per-class L6B reflex corpus N>=50",
        "IMU/rumble challenge verifier measurement",
        "PoEP device-auth verifier characterization",
    ),
    "PREMIUM_EDGE": (
        "Empirical Unknown #1 adaptive-trigger separability >=20% rank-1",
        "PoEP adaptive_force regression parity (Edge fixtures)",
        "L6B Gate 1 closed; class-wide FAR/FRR still UNVALIDATED",
    ),
}


def _parse_phase_g_tier_set(raw: str | None) -> frozenset[ControllerClassTier]:
    """Parse comma-separated tier names from a Phase G env var."""
    if not raw:
        return frozenset()
    out: set[ControllerClassTier] = set()
    for part in str(raw).split(","):
        token = part.strip().upper()
        if token in _TIER_VALUES:
            out.add(token)  # type: ignore[arg-type]
    return frozenset(out)


def parse_phase_g_deferred_tiers(raw: str | None) -> frozenset[ControllerClassTier]:
    """Parse comma-separated tier names from ``CCO_PHASE_G_DEFERRED_TIERS`` env."""
    return _parse_phase_g_tier_set(raw)


def parse_phase_g_validated_tiers(raw: str | None) -> frozenset[ControllerClassTier]:
    """Parse operator-attested VALIDATED tiers from ``CCO_PHASE_G_VALIDATED_TIERS`` env."""
    return _parse_phase_g_tier_set(raw)


def resolve_tier_measurement_grade(
    tier: ControllerClassTier,
    tier_probe_count: int,
    *,
    deferred_tiers: frozenset[ControllerClassTier] | None = None,
    validated_tiers: frozenset[ControllerClassTier] | None = None,
) -> MeasurementGrade:
    """Tier grade with operator deferral + attestation overlays.

    VALIDATED is never inferred from corpus count alone — only when the tier
    appears in ``validated_tiers`` (``CCO_PHASE_G_VALIDATED_TIERS``).
    """
    if validated_tiers and tier in validated_tiers:
        return "VALIDATED"
    if deferred_tiers and tier in deferred_tiers:
        return "UNVALIDATED"
    return resolve_corpus_measurement_grade(tier, tier_probe_count)


def enrich_phase_g_progress(
    progress: dict[str, Any],
    *,
    deferred_tiers: frozenset[ControllerClassTier] | None = None,
    validated_tiers: frozenset[ControllerClassTier] | None = None,
) -> dict[str, Any]:
    """Annotate ``get_cco_phase_g_corpus_progress`` with status + measurement grade."""
    deferred_tiers = deferred_tiers or frozenset()
    validated_tiers = validated_tiers or frozenset()
    by_tier = progress.get("by_tier") or {}
    for tier in _TIER_VALUES:
        block = by_tier.get(tier)
        if block is None:
            continue
        probe_count = int(block.get("probe_count") or 0)
        block["measurement_grade"] = resolve_tier_measurement_grade(
            tier,  # type: ignore[arg-type]
            probe_count,
            deferred_tiers=deferred_tiers,
            validated_tiers=validated_tiers,
        )
        block["operator_validated"] = tier in validated_tiers
        if tier in deferred_tiers:
            block["measurement_status"] = "deferred"
            block["deferred"] = True
            block["deferred_reason"] = _DEFERRED_REASON
        elif block.get("gate_reached"):
            block["measurement_status"] = "reached"
            block["deferred"] = False
        else:
            block["measurement_status"] = "pending"
            block["deferred"] = False
    if deferred_tiers:
        progress["deferred_tiers"] = sorted(deferred_tiers)
    if validated_tiers:
        progress["validated_tiers"] = sorted(validated_tiers)
    return progress


def enrich_phase_g_progress_deferred(
    progress: dict[str, Any],
    deferred_tiers: frozenset[ControllerClassTier],
) -> dict[str, Any]:
    """Mark operator-deferred tiers on a ``get_cco_phase_g_corpus_progress`` payload."""
    return enrich_phase_g_progress(progress, deferred_tiers=deferred_tiers)


def resolve_controller_class_tier(profile_id: str | None) -> ControllerClassTier:
    """Return research tier for a CCO profile_id; unknown → MINIMAL_PAD (conservative)."""
    if not profile_id:
        return "MINIMAL_PAD"
    return _PROFILE_TIER.get(profile_id, "MINIMAL_PAD")


def resolve_corpus_measurement_grade(
    tier: ControllerClassTier,
    tier_probe_count: int,
) -> MeasurementGrade:
    """Dynamic grade from tier baseline + per-tier L6B corpus count.

    UNVALIDATED tiers promote to PARTIAL at N>=PHASE_G_TARGET_N.
    PREMIUM_EDGE baseline stays PARTIAL regardless of count.
    VALIDATED is never assigned automatically — operator-fired only.
    """
    baseline = _TIER_MEASUREMENT_GRADE[tier]
    if tier_probe_count >= PHASE_G_TARGET_N and baseline == "UNVALIDATED":
        return "PARTIAL"
    return baseline


def assemble_controller_class_research(
    *,
    enabled: bool,
    profile_id: str | None = None,
    characterization_status: str | None = None,
    tier_probe_count: int | None = None,
    validated_tiers: frozenset[ControllerClassTier] | None = None,
    deferred_tiers: frozenset[ControllerClassTier] | None = None,
) -> dict[str, Any]:
    """Build Phase G research block for session-status (default-OFF activation gate)."""
    if not enabled:
        return {
            "schema": _SCHEMA,
            "enabled": False,
            "grade": "DISABLED",
        }

    tier = resolve_controller_class_tier(profile_id)
    validated_tiers = validated_tiers or frozenset()
    deferred_tiers = deferred_tiers or frozenset()
    if tier_probe_count is not None:
        measurement_grade = resolve_tier_measurement_grade(
            tier,
            tier_probe_count,
            deferred_tiers=deferred_tiers,
            validated_tiers=validated_tiers,
        )
        corpus_n = tier_probe_count
        corpus_gate_reached = tier_probe_count >= PHASE_G_TARGET_N
    else:
        measurement_grade = resolve_tier_measurement_grade(
            tier,
            0,
            deferred_tiers=deferred_tiers,
            validated_tiers=validated_tiers,
        )
        if measurement_grade == "UNVALIDATED" and tier not in deferred_tiers:
            measurement_grade = _TIER_MEASUREMENT_GRADE[tier]
        corpus_n = None
        corpus_gate_reached = None

    return {
        "schema": _SCHEMA,
        "enabled": True,
        "grade": measurement_grade,
        "controller_class_tier": tier,
        "profile_id": profile_id,
        "characterization_status": characterization_status,
        "partner_claim_ceiling": _TIER_PARTNER_CEILING[tier],
        "measurement_gates_pending": list(_TIER_EMPIRICAL_GATES[tier]),
        "policy_ref": _POLICY_REF,
        "corpus_n": corpus_n,
        "corpus_target_n": PHASE_G_TARGET_N,
        "corpus_gate_reached": corpus_gate_reached,
        "honesty_rail": (
            "UNVALIDATED tiers MUST NOT claim tournament-grade presence; "
            "PARTIAL applies to Edge-only partial corpus, not universal partner language."
        ),
    }
