"""Tests for PoEP P2 calibration (no hardware)."""
from l9_presence.poep import PoEPSession, save_poep_session
from l9_presence.poep_calibration import (
    device_auth_score, liveness_score, poep_readiness, poep_verify, population_reflex_model,
)


def _session(player="P1", device="Edge", k=10, lat=290.0, seed=0):
    import random
    rng = random.Random(seed)
    recs = []
    for i in range(k):
        recs.append({"nonce": f"{i:032x}", "stim_t_ms": 0.0, "features": {
            "reaction_latency_ms": lat + rng.uniform(-25, 25), "reacted": True, "in_band": True,
            "peak_stick_deflection": 70.0, "peak_r2": 180.0 + rng.uniform(-10, 10),
            "grip_micro_adjustment": 0.5 + rng.uniform(-0.05, 0.05),
            "force_response_auc": 5000.0 + rng.uniform(-200, 200)}})
    da = {"slope_on": 1.15, "slope_off": 4.48, "delta": 0.743, "adaptive_response_detected": True}
    return PoEPSession(player, device, recs, "deadbeef", 1, False, da)


_REACTION = {"reaction_latency_ms": 290}                              # in-band liveness
_GENUINE_DA = {"slope_on": 1.15, "slope_off": 4.48, "delta": 0.743,   # real Edge force-challenge
               "adaptive_response_detected": True}
_EMULATOR_DA = {"slope_on": 4.4, "slope_off": 4.4, "delta": 0.0,      # no adaptive trigger -> ON==OFF
                "adaptive_response_detected": False}


def test_model_counts_and_band():
    m = population_reflex_model([_session(k=30)], min_n=50)
    assert m["n_reactions"] == 30
    assert m["calibration_complete"] is False        # 30 < 50
    assert m["band_lo_ms"] < m["latency_mean_ms"] < m["band_hi_ms"]
    assert "Edge" in m["device_signatures"]


def test_model_complete_at_threshold():
    m = population_reflex_model([_session(player="P1", k=30, seed=1),
                                 _session(player="P2", k=30, seed=2)], min_n=50)
    assert m["n_reactions"] == 60 and m["calibration_complete"] is True
    assert m["per_player"] == {"P1": 30, "P2": 30}


def test_readiness_needs_more(tmp_path):
    save_poep_session(str(tmp_path / "P1_01.poep.json"), _session(k=20))
    r = poep_readiness(str(tmp_path), min_n=50)
    assert r["calibration_complete"] is False
    assert r["reactions_needed"] == 30


def test_liveness_gated_until_calibrated():
    incomplete = population_reflex_model([_session(k=10)], min_n=50)
    assert liveness_score({"reaction_latency_ms": 290}, incomplete)["status"] == "calibration_incomplete"


def test_liveness_pass_and_fail_when_calibrated():
    m = population_reflex_model([_session(k=60)], min_n=50)
    assert m["calibration_complete"] is True
    assert liveness_score({"reaction_latency_ms": 290, "peak_r2": 180}, m, "Edge")["liveness_pass"] is True
    # anticipation-fast reaction outside the population band -> fail
    assert liveness_score({"reaction_latency_ms": 30, "peak_r2": 180}, m, "Edge")["liveness_pass"] is False


def test_device_auth_passes_genuine_fails_emulator():
    m = population_reflex_model([_session(k=60)], min_n=50)
    assert "Edge" in m["device_signatures"]
    assert device_auth_score(_GENUINE_DA, m, "Edge")["device_auth_pass"] is True
    assert device_auth_score(_EMULATOR_DA, m, "Edge")["device_auth_pass"] is False  # ON==OFF, no adaptive trigger


def test_poep_verify_present_and_reject():
    m = population_reflex_model([_session(k=60)], min_n=50)
    assert poep_verify(_REACTION, _GENUINE_DA, m, "Edge")["verdict"] == "PRESENT"
    assert poep_verify({"reaction_latency_ms": 45}, _GENUINE_DA, m, "Edge")["verdict"] == "REJECT"  # liveness fail
    assert poep_verify(_REACTION, _EMULATOR_DA, m, "Edge")["verdict"] == "REJECT"                   # device-auth fail


def test_poep_verify_gated_until_calibrated():
    incomplete = population_reflex_model([_session(k=10)], min_n=50)
    assert poep_verify(_REACTION, _GENUINE_DA, incomplete, "Edge")["status"] == "calibration_incomplete"
