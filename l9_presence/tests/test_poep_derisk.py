"""Tests for the PoEP de-risk decision logic (no hardware)."""
from l9_presence.poep_derisk import in_human_band, reaction_detected

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
