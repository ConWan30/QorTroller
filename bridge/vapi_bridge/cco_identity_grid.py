"""CCO Phase E — two-axis identity grid session surfacing.

Read-only composition of identity (I-0 / Path B / I-1) and presence ceiling
(P-T0–P-T3 candidate) for GET /player/session-status. Design:
``wiki/methodology/CCO_POEP_FUSION_v4.md`` §4.1, §Phase E; F-V4-003 Path B honesty.
"""
from __future__ import annotations

from typing import Any, Literal

_SCHEMA = "qortroller-identity-grid-v1"
_PATH_B_HONESTY = (
    "Cryptographic device_id (keccak256 pubkey) without silicon sovereignty; "
    "not I-1 × P-T3 tournament narrative (F-V4-003)."
)

_IDENTITY_AXIS: dict[str, str] = {
    "I0_SOFTWARE": "I-0",
    "PATH_B_HOST_KEY": "Path B",
    "I1_SILICON": "I-1",
    "UNKNOWN": "UNKNOWN",
}


def _resolve_identity_class(
    capability_report: Any | None,
    signing_path: Literal["A", "B"] | None,
) -> str | None:
    """Live signing_path overrides oracle stub when chain/MFG read succeeds."""
    if signing_path == "A":
        return "I1_SILICON"
    if signing_path == "B":
        return "PATH_B_HOST_KEY"
    if capability_report is None:
        return None
    return getattr(capability_report, "identity_class", None) or "UNKNOWN"


def assemble_identity_grid(
    *,
    capability_report: Any | None = None,
    signing_path: Literal["A", "B"] | None = None,
    path_a_eligible: bool = False,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Build read-only identity×presence grid for session-status (Phase E).

    Top-level ``signing_path`` / ``path_a_eligible`` remain for backward
    compatibility; ``identity_grid`` is the canonical composable claim surface.
    """
    identity_class = _resolve_identity_class(capability_report, signing_path)
    presence_ceiling = (
        getattr(capability_report, "presence_ceiling_candidate", None)
        if capability_report is not None
        else None
    )
    characterization = (
        getattr(capability_report, "characterization_status", None)
        if capability_report is not None
        else None
    )
    policy_ref = (
        getattr(capability_report, "policy_ref", None)
        if capability_report is not None
        else None
    )
    profile_id = (
        getattr(capability_report, "profile_id", None)
        if capability_report is not None
        else None
    )

    axis_key = identity_class or "UNKNOWN"
    identity_axis = _IDENTITY_AXIS.get(axis_key, "UNKNOWN")

    return {
        "schema": _SCHEMA,
        "identity_class": identity_class,
        "identity_axis": identity_axis,
        "presence_ceiling_candidate": presence_ceiling,
        "presence_axis": presence_ceiling,
        "characterization_status": characterization,
        "profile_id": profile_id,
        "signing_path": signing_path,
        "path_a_eligible": bool(path_a_eligible),
        "path_b_honesty_note": (
            _PATH_B_HONESTY if identity_class == "PATH_B_HOST_KEY" else None
        ),
        "policy_ref": policy_ref,
        "device_id": device_id or None,
        "composable_on_chain": False,
    }
