"""CCO Phase D — dormant CCO → PoEP bridge wiring.

Assembles ``CapabilityReport`` fields into PoEP runner inputs and exposes
read-only presence status for session surfaces. Never emits ``PRESENT`` when
``poep_enabled=False`` (default). Design: ``wiki/methodology/CCO_POEP_FUSION_v4.md`` §Phase D.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_POEP_MIN_N = 50


@dataclass(frozen=True, slots=True)
class PoepRunnerInputs:
    """Inputs the l9_presence PoEP runner consumes from CCO (Phase D)."""

    challenge_type: str | None
    presence_ceiling_candidate: str | None
    characterization_status: str | None
    profile_id: str | None
    t2_t3_engine: str
    policy_ref: str | None
    device_id: str | None


def build_poep_runner_inputs(
    capability_report: Any | None,
    *,
    device_id: str | None = None,
) -> PoepRunnerInputs:
    """Map CCO oracle output → PoEP session runner parameters (pure, no I/O)."""
    if capability_report is None:
        return PoepRunnerInputs(
            challenge_type=None,
            presence_ceiling_candidate=None,
            characterization_status=None,
            profile_id=None,
            t2_t3_engine="POEP",
            policy_ref=None,
            device_id=device_id,
        )
    return PoepRunnerInputs(
        challenge_type=getattr(capability_report, "challenge_type_candidate", None),
        presence_ceiling_candidate=getattr(
            capability_report, "presence_ceiling_candidate", None,
        ),
        characterization_status=getattr(
            capability_report, "characterization_status", None,
        ),
        profile_id=getattr(capability_report, "profile_id", None),
        t2_t3_engine=getattr(capability_report, "t2_t3_engine", "POEP") or "POEP",
        policy_ref=getattr(capability_report, "policy_ref", None),
        device_id=device_id,
    )


def _poep_corpus_readiness(
    corpus_dir: str,
    min_n: int,
) -> dict[str, Any]:
    try:
        from l9_presence.poep_calibration import poep_readiness

        return poep_readiness(corpus_dir, min_n)
    except Exception:
        return {
            "calibration_complete": False,
            "total_in_band_reactions": 0,
            "min_n": min_n,
            "corpus_dir": corpus_dir,
        }


def build_poep_telemetry_from_probe(
    challenge_type: str | None,
    latest_probe: dict[str, Any] | None,
) -> dict[str, Any | None]:
    """Map ``l6b_probe_log`` latest row → PoEP runner telemetry (pure, no I/O).

    ``rumble_imu`` — latency + accel peak + classification from L6B desk path.
    ``adaptive_force`` — liveness latency only from probe; force signature still
    requires live adaptive-trigger capture (probe log has no slope/delta fields).
    """
    if not latest_probe or not challenge_type:
        return {
            "device_auth": None,
            "reaction_features": None,
            "device_auth_note": None,
        }

    lat = latest_probe.get("latency_ms")
    if lat is None:
        return {
            "device_auth": None,
            "reaction_features": None,
            "device_auth_note": None,
        }

    reaction_features: dict[str, Any] = {
        "reaction_latency_ms": float(lat),
        "reacted": True,
        "in_band": True,
    }

    if challenge_type == "rumble_imu":
        peak = latest_probe.get("accel_delta_peak")
        if peak is None:
            return {
                "device_auth": None,
                "reaction_features": None,
                "device_auth_note": None,
            }
        classification = latest_probe.get("classification") or latest_probe.get(
            "reflex_verdict",
        )
        device_auth: dict[str, Any] = {
            "classification": classification,
            "latency_ms": float(lat),
            "accel_delta_peak": float(peak),
        }
        return {
            "device_auth": device_auth,
            "reaction_features": reaction_features,
            "device_auth_note": None,
        }

    if challenge_type == "adaptive_force":
        # Probe log lacks adaptive-trigger force signature; liveness-only partial.
        return {
            "device_auth": None,
            "reaction_features": reaction_features,
            "device_auth_note": (
                "probe_log provides liveness latency only; adaptive-trigger "
                "force signature requires live adaptive_force capture"
            ),
        }

    return {"device_auth": None, "reaction_features": None, "device_auth_note": None}


def _evaluate_poep_verdict(
    *,
    poep_enabled: bool,
    runner: PoepRunnerInputs,
    device_auth: dict[str, Any] | None,
    reaction_features: dict[str, Any] | None,
    corpus_dir: str,
    min_n: int,
) -> dict[str, Any] | None:
    if not poep_enabled:
        return None
    if device_auth is None or reaction_features is None:
        return None
    challenge_type = runner.challenge_type or "adaptive_force"
    try:
        from l9_presence.poep_calibration import (
            load_enrollment_sessions,
            population_reflex_model,
            poep_verify,
        )

        model = population_reflex_model(
            load_enrollment_sessions(corpus_dir), min_n,
        )
        return poep_verify(
            reaction_features,
            device_auth,
            model,
            device_id=runner.device_id,
            challenge_type=challenge_type,
        )
    except Exception:
        return None


def assemble_poep_presence_status(
    *,
    poep_enabled: bool,
    capability_report: Any | None,
    device_id: str | None = None,
    l6b_probe_count: int = 0,
    l6b_gate_reached: bool = False,
    corpus_dir: str = "poep_l9",
    min_n: int = _POEP_MIN_N,
    device_auth: dict[str, Any] | None = None,
    reaction_features: dict[str, Any] | None = None,
    device_auth_note: str | None = None,
) -> dict[str, Any]:
    """Build ``presence.poep`` block for GET /player/session-status (Phase D).

    When ``poep_enabled=False`` (default): returns routing + corpus readiness only;
    ``verdict`` is always ``None`` — Option C keeps ``PRESENT`` operator-gated.
    """
    runner = build_poep_runner_inputs(capability_report, device_id=device_id)
    corpus = _poep_corpus_readiness(corpus_dir, min_n)
    n_reactions = int(corpus.get("total_in_band_reactions", 0))
    corpus_complete = bool(corpus.get("calibration_complete", False))

    if poep_enabled:
        status = "active (PoEP_ENABLED=true)"
    elif l6b_gate_reached and not corpus_complete:
        status = (
            f"L6B gate reached (N={l6b_probe_count}); "
            f"PoEP corpus pending (N={n_reactions}/{min_n}); operator-gated"
        )
    elif l6b_gate_reached:
        status = "L6B gate reached; PoEP corpus ready; operator-gated (PoEP_ENABLED=false)"
    else:
        status = f"pending L6B calibration (N={l6b_probe_count}/{min_n}); PoEP operator-gated"

    verdict_payload = _evaluate_poep_verdict(
        poep_enabled=poep_enabled,
        runner=runner,
        device_auth=device_auth,
        reaction_features=reaction_features,
        corpus_dir=corpus_dir,
        min_n=min_n,
    )

    return {
        "enabled": poep_enabled,
        "dormant": not poep_enabled,
        "status": status,
        "challenge_type": runner.challenge_type,
        "presence_ceiling_candidate": runner.presence_ceiling_candidate,
        "characterization_status": runner.characterization_status,
        "l6b_probe_count": l6b_probe_count,
        "l6b_gate_reached": l6b_gate_reached,
        "corpus": {
            "dir": corpus_dir,
            "calibration_complete": corpus_complete,
            "n_reactions": n_reactions,
            "min_n": min_n,
        },
        "runner": {
            "t2_t3_engine": runner.t2_t3_engine,
            "profile_id": runner.profile_id,
            "policy_ref": runner.policy_ref,
            "device_id": runner.device_id,
        },
        "verdict": (
            verdict_payload.get("verdict") if verdict_payload else None
        ),
        "device_auth_available": device_auth is not None,
        "reaction_features_available": reaction_features is not None,
        "device_auth_note": device_auth_note,
    }
