"""CCO Phase C — ChallengeVerifier protocol and per-class stubs.

Edge ``adaptive_force`` verifier preserves regression parity with
``adaptive_response_detected`` in ``poep_force.summarize_force_auth``.
Non-Edge challenge types return UNCHARACTERIZED until per-class measurement.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

_UNCHARACTERIZED = {"device_auth_pass": False, "reason": "UNCHARACTERIZED", "score": 0.0}


@runtime_checkable
class ChallengeVerifier(Protocol):
    """Verify device-auth for one CCO ``challenge_type_candidate`` value."""

    challenge_type: str

    def verify(
        self,
        device_auth: dict,
        model: dict,
        device_id: str,
    ) -> dict[str, Any]: ...


class AdaptiveForceVerifier:
    """Edge adaptive-trigger force-challenge (P4a regression path)."""

    challenge_type = "adaptive_force"

    def verify(
        self,
        device_auth: dict,
        model: dict,
        device_id: str,
    ) -> dict[str, Any]:
        sig = model.get("device_signatures", {}).get(device_id)
        if not sig:
            return {
                "device_auth_pass": False,
                "reason": "device_not_registered",
                "score": 0.0,
            }
        detected = bool((device_auth or {}).get("adaptive_response_detected"))
        delta = float((device_auth or {}).get("delta", 0.0))
        return {
            "device_auth_pass": detected,
            "score": round(min(1.0, delta), 3),
            "delta": round(delta, 3),
        }


class UncharacterizedVerifier:
    """Stub for challenge types without per-class measurement yet."""

    def __init__(self, challenge_type: str) -> None:
        self.challenge_type = challenge_type

    def verify(
        self,
        device_auth: dict,
        model: dict,
        device_id: str,
    ) -> dict[str, Any]:
        return dict(_UNCHARACTERIZED)


_VERIFIERS: dict[str, ChallengeVerifier] = {
    "adaptive_force": AdaptiveForceVerifier(),
    "rumble_imu": UncharacterizedVerifier("rumble_imu"),
    "stick_timing": UncharacterizedVerifier("stick_timing"),
    "button_timing": UncharacterizedVerifier("button_timing"),
    "generic_input_timing": UncharacterizedVerifier("generic_input_timing"),
}


def get_challenge_verifier(challenge_type: str) -> ChallengeVerifier:
    """Return verifier for ``challenge_type``; unknown types → UNCHARACTERIZED stub."""
    return _VERIFIERS.get(
        challenge_type,
        UncharacterizedVerifier(challenge_type),
    )
