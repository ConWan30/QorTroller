"""CCO Phase C — ChallengeVerifier protocol and per-class verifiers.

Edge ``adaptive_force`` verifier preserves regression parity with
``adaptive_response_detected`` in ``poep_force.summarize_force_auth``.
Mid-tier ``rumble_imu`` verifier is measured from DualSense L6B desk corpus
(``sony_dualsense_v1``, N=50 HUMAN @ 2026-06-20). Other challenge types
return UNCHARACTERIZED until per-class measurement.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

_UNCHARACTERIZED = {"device_auth_pass": False, "reason": "UNCHARACTERIZED", "score": 0.0}

# Measured from ``scripts/cco_phase_g_far_frr_report.py`` on live bridge.db
# (sony_dualsense_v1 HUMAN rows, desk human_max=350 policy).
RUMBLE_IMU_BASELINE_V1: dict[str, float | int | str] = {
    "schema": "qortroller-rumble-imu-baseline-v1",
    "measured_profile": "sony_dualsense_v1",
    "measured_at": "2026-06-20",
    "corpus_human_n": 50,
    "human_latency_min_ms": 80.0,
    "human_latency_max_ms": 350.0,
    "min_accel_delta_peak_lsb": 500.0,
    "human_peak_p50_lsb": 972.79,
    "human_latency_p50_ms": 185.97,
}


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


class RumbleImuVerifier:
    """Mid-tier rumble+IMU reflex path (DualSense L6B desk measurement)."""

    challenge_type = "rumble_imu"

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

        auth = device_auth or {}
        baseline = model.get("rumble_imu_baseline") or RUMBLE_IMU_BASELINE_V1
        lat_min = float(baseline["human_latency_min_ms"])
        lat_max = float(baseline["human_latency_max_ms"])
        peak_min = float(baseline["min_accel_delta_peak_lsb"])
        peak_p50 = float(baseline.get("human_peak_p50_lsb") or 1000.0)

        classification = auth.get("classification")
        if classification == "HUMAN":
            peak = float(auth.get("accel_delta_peak") or peak_p50)
            lat = float(auth.get("latency_ms") or auth.get("reaction_latency_ms") or 0.0)
            return {
                "device_auth_pass": True,
                "reason": "human_classification",
                "score": round(min(1.0, peak / peak_p50), 3),
                "latency_ms": round(lat, 2),
                "accel_delta_peak": round(peak, 2),
            }

        lat_raw = auth.get("latency_ms", auth.get("reaction_latency_ms"))
        peak_raw = auth.get("accel_delta_peak", auth.get("peak_lsb"))
        if lat_raw is None or peak_raw is None:
            return {
                "device_auth_pass": False,
                "reason": "missing_rumble_imu_features",
                "score": 0.0,
            }

        lat = float(lat_raw)
        peak = float(peak_raw)

        if peak < peak_min:
            return {
                "device_auth_pass": False,
                "reason": "no_imu_response",
                "score": 0.0,
                "accel_delta_peak": round(peak, 2),
            }

        if lat < 15.0:
            return {
                "device_auth_pass": False,
                "reason": "bot_latency",
                "score": 0.0,
                "latency_ms": round(lat, 2),
            }

        if lat_min <= lat <= lat_max:
            return {
                "device_auth_pass": True,
                "reason": "measured_human_band",
                "score": round(min(1.0, peak / peak_p50), 3),
                "latency_ms": round(lat, 2),
                "accel_delta_peak": round(peak, 2),
            }

        return {
            "device_auth_pass": False,
            "reason": "latency_out_of_band",
            "score": 0.0,
            "latency_ms": round(lat, 2),
            "accel_delta_peak": round(peak, 2),
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
    "rumble_imu": RumbleImuVerifier(),
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
