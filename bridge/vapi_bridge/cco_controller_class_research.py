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

ControllerClassTier = Literal["MINIMAL_PAD", "MID_TIER", "PREMIUM_EDGE"]
MeasurementGrade = Literal["UNVALIDATED", "PARTIAL", "VALIDATED"]

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


def resolve_controller_class_tier(profile_id: str | None) -> ControllerClassTier:
    """Return research tier for a CCO profile_id; unknown → MINIMAL_PAD (conservative)."""
    if not profile_id:
        return "MINIMAL_PAD"
    return _PROFILE_TIER.get(profile_id, "MINIMAL_PAD")


def assemble_controller_class_research(
    *,
    enabled: bool,
    profile_id: str | None = None,
    characterization_status: str | None = None,
) -> dict[str, Any]:
    """Build Phase G research block for session-status (default-OFF activation gate)."""
    if not enabled:
        return {
            "schema": _SCHEMA,
            "enabled": False,
            "grade": "DISABLED",
        }

    tier = resolve_controller_class_tier(profile_id)
    measurement_grade = _TIER_MEASUREMENT_GRADE[tier]
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
        "honesty_rail": (
            "UNVALIDATED tiers MUST NOT claim tournament-grade presence; "
            "PARTIAL applies to Edge-only partial corpus, not universal partner language."
        ),
    }
