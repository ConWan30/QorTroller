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


# --- Stage 2: developer-self single-subject band + liveness-only verdict ---

from l9_presence.poep_calibration import (  # noqa: E402
    developer_self_liveness_verdict, single_subject_reflex_model,
)


def test_single_subject_band_filters_to_one_player(tmp_path):
    save_poep_session(str(tmp_path / "DEV_01.poep.json"), _session(player="DEV", k=20, seed=1))
    save_poep_session(str(tmp_path / "DEV_02.poep.json"), _session(player="DEV", k=20, seed=2))
    save_poep_session(str(tmp_path / "P9_01.poep.json"), _session(player="P9", k=20, seed=3))
    m = single_subject_reflex_model(str(tmp_path), "DEV", min_n=30)
    assert m["single_subject"] is True and m["player"] == "DEV"
    assert m["n_reactions"] == 40                 # only DEV's 2x20, NOT the other player
    assert m["calibration_complete"] is True       # 40 >= 30 (developer-scoped gate)
    assert set(m["per_player"]) == {"DEV"}


def _complete_dev_model():
    return population_reflex_model([_session(player="DEV", k=30, seed=1),
                                    _session(player="DEV", k=30, seed=2)], min_n=30)


def test_dev_liveness_verdict_gated_until_calibrated():
    incomplete = population_reflex_model([_session(k=5)], min_n=30)
    v = developer_self_liveness_verdict([{"reacted": True, "reaction_latency_ms": 290}], incomplete)
    assert v["status"] == "calibration_incomplete"


def test_dev_liveness_present_when_in_band():
    v = developer_self_liveness_verdict(
        [{"reacted": True, "reaction_latency_ms": 290} for _ in range(8)], _complete_dev_model())
    assert v["verdict"] == "PRESENT" and v["liveness_pass"] is True
    assert v["channel"] == "liveness_only"          # device-auth deferred (explicit)
    assert v["in_band_fraction"] == 1.0


def test_dev_liveness_reject_when_out_of_band():
    v = developer_self_liveness_verdict(
        [{"reacted": True, "reaction_latency_ms": 1500} for _ in range(8)], _complete_dev_model())
    assert v["verdict"] == "REJECT" and v["liveness_pass"] is False


def test_dev_liveness_reject_no_reactions():
    v = developer_self_liveness_verdict(
        [{"reacted": False, "reaction_latency_ms": None}], _complete_dev_model())
    assert v["verdict"] == "REJECT" and v["n_reacted"] == 0


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


def test_device_auth_uncharacterized_non_adaptive_force():
    m = population_reflex_model([_session(k=60)], min_n=50)
    for ctype in ("generic_input_timing", "button_timing"):
        out = device_auth_score(_GENUINE_DA, m, "Edge", challenge_type=ctype)
        assert out["device_auth_pass"] is False
        assert out["reason"] == "UNCHARACTERIZED"
        assert out["score"] == 0.0


def test_rumble_imu_requires_imu_features_not_edge_force_dict():
    m = population_reflex_model([_session(k=60)], min_n=50)
    out = device_auth_score(_GENUINE_DA, m, "Edge", challenge_type="rumble_imu")
    assert out["device_auth_pass"] is False
    assert out["reason"] == "missing_rumble_imu_features"


def test_poep_verify_present_and_reject():
    m = population_reflex_model([_session(k=60)], min_n=50)
    assert poep_verify(_REACTION, _GENUINE_DA, m, "Edge")["verdict"] == "PRESENT"
    assert poep_verify({"reaction_latency_ms": 45}, _GENUINE_DA, m, "Edge")["verdict"] == "REJECT"  # liveness fail
    assert poep_verify(_REACTION, _EMULATOR_DA, m, "Edge")["verdict"] == "REJECT"                   # device-auth fail


def test_poep_verify_gated_until_calibrated():
    incomplete = population_reflex_model([_session(k=10)], min_n=50)
    assert poep_verify(_REACTION, _GENUINE_DA, incomplete, "Edge")["status"] == "calibration_incomplete"


def test_poep_verify_routes_challenge_type():
    m = population_reflex_model([_session(k=60)], min_n=50)
    rumble_da = {
        "classification": "HUMAN",
        "latency_ms": 290.0,
        "accel_delta_peak": 1000.0,
    }
    out = poep_verify(
        _REACTION,
        rumble_da,
        m,
        "Edge",
        challenge_type="rumble_imu",
    )
    assert out["challenge_type"] == "rumble_imu"
    assert out["verdict"] == "PRESENT"
    # Edge force dict must not pass rumble_imu device-auth
    assert poep_verify(
        _REACTION, _GENUINE_DA, m, "Edge", challenge_type="rumble_imu",
    )["verdict"] == "REJECT"
