"""Tests for CCO Phase C ChallengeVerifier protocol."""
from l9_presence.challenge_verifier import (
    AdaptiveForceVerifier,
    RUMBLE_IMU_BASELINE_V1,
    RumbleImuVerifier,
    UncharacterizedVerifier,
    get_challenge_verifier,
)
from l9_presence.poep_calibration import device_auth_score, population_reflex_model
from l9_presence.tests.test_poep_calibration import _GENUINE_DA, _session


def _model():
    return population_reflex_model([_session(k=60)], min_n=50)


def test_adaptive_force_verifier_matches_device_auth_score():
    m = _model()
    via_score = device_auth_score(_GENUINE_DA, m, "Edge", challenge_type="adaptive_force")
    via_verifier = AdaptiveForceVerifier().verify(_GENUINE_DA, m, "Edge")
    assert via_score == via_verifier
    assert via_score["device_auth_pass"] is True


def test_rumble_imu_measured_verifier_passes_human_band():
    m = _model()
    m["device_signatures"]["DualSense"] = {"registered": True}
    auth = {
        "latency_ms": 186.0,
        "accel_delta_peak": 980.0,
        "classification": "HUMAN",
    }
    out = RumbleImuVerifier().verify(auth, m, "DualSense")
    assert out["device_auth_pass"] is True
    assert out["reason"] == "human_classification"
    via_score = device_auth_score(auth, m, "DualSense", challenge_type="rumble_imu")
    assert via_score == out


def test_rumble_imu_rejects_bot_latency():
    m = _model()
    m["device_signatures"]["DualSense"] = {"registered": True}
    auth = {"latency_ms": 8.0, "accel_delta_peak": 900.0}
    out = get_challenge_verifier("rumble_imu").verify(auth, m, "DualSense")
    assert out["device_auth_pass"] is False
    assert out["reason"] == "bot_latency"


def test_rumble_imu_baseline_constants_documented():
    assert RUMBLE_IMU_BASELINE_V1["measured_profile"] == "sony_dualsense_v1"
    assert RUMBLE_IMU_BASELINE_V1["corpus_human_n"] == 50


def test_non_measured_types_return_uncharacterized():
    m = _model()
    for ctype in ("stick_timing", "button_timing", "unknown_type"):
        out = get_challenge_verifier(ctype).verify(_GENUINE_DA, m, "Edge")
        assert out["device_auth_pass"] is False
        assert out["reason"] == "UNCHARACTERIZED"
        assert out["score"] == 0.0


def test_uncharacterized_verifier_exposes_challenge_type():
    v = UncharacterizedVerifier("stick_timing")
    assert v.challenge_type == "stick_timing"
