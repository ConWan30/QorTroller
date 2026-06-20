"""Tests for CCO Phase C ChallengeVerifier protocol."""
from l9_presence.challenge_verifier import (
    AdaptiveForceVerifier,
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


def test_non_adaptive_force_returns_uncharacterized():
    m = _model()
    for ctype in ("rumble_imu", "button_timing", "unknown_type"):
        out = get_challenge_verifier(ctype).verify(_GENUINE_DA, m, "Edge")
        assert out["device_auth_pass"] is False
        assert out["reason"] == "UNCHARACTERIZED"
        assert out["score"] == 0.0


def test_uncharacterized_verifier_exposes_challenge_type():
    v = UncharacterizedVerifier("stick_timing")
    assert v.challenge_type == "stick_timing"
