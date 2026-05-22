"""Tests for the PoEP de-risk decision logic (no hardware)."""
from l9_presence.poep_derisk import assess_control, in_human_band, reaction_detected

_CENTER = {"RX": 128, "RY": 128, "R2": 0, "L2": 0, "buttons": 0}


def test_human_band_accepts_voluntary_reaction():
    assert in_human_band(200.0) is True
    assert in_human_band(120.0) is True and in_human_band(450.0) is True


def test_human_band_rejects_anticipation_and_inattention():
    assert in_human_band(50.0) is False     # too fast -> anticipation / bot
    assert in_human_band(800.0) is False    # too slow -> not a reflex


def test_reaction_detected_on_trigger_press():
    assert reaction_detected(_CENTER, {**_CENTER, "R2": 200}) is True


def test_reaction_detected_on_stick_flick():
    assert reaction_detected(_CENTER, {**_CENTER, "RX": 220}) is True
    assert reaction_detected(_CENTER, {**_CENTER, "RY": 40}) is True


def test_reaction_detected_on_button():
    assert reaction_detected(_CENTER, {**_CENTER, "buttons": 1}) is True


def test_no_reaction_when_idle():
    assert reaction_detected(_CENTER, {**_CENTER, "RX": 130, "R2": 5}) is False  # tiny drift, not a reaction


def test_control_genuine_when_buzz_drives_and_sham_quiet():
    # buzz reactions in human band; gameplay (sham) rarely trips the detector
    r = assess_control(buzz_lats=[260, 290, 310, 275, 300], sham_lats=[],
                       n_buzz=5, n_sham=5)
    assert r["genuine_buzz_driven"] is True


def test_control_confounded_when_sham_trips_too():
    # gameplay trips the detector on most sham trials too -> in-game confounded
    r = assess_control(buzz_lats=[200, 180, 220, 190, 210],
                       sham_lats=[150, 170, 160, 180], n_buzz=5, n_sham=5)
    assert r["genuine_buzz_driven"] is False
    assert "confounded" in r["verdict"]
