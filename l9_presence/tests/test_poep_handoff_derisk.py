"""Tests for the device-handoff de-risk verdict logic (no hardware)."""
from l9_presence.poep_handoff_derisk import assess_handoff

_CLEAN = {"read1_ok": True, "acquire_ok": True, "reacquire_ok": True}


def test_all_clean_is_go_option_a():
    r = assess_handoff([dict(_CLEAN) for _ in range(5)])
    assert r["go"] is True and r["clean_rounds"] == 5
    assert "Option A" in r["recommendation"]


def test_reacquire_failure_is_nogo_option_b():
    rounds = [dict(_CLEAN), {**_CLEAN, "reacquire_ok": False}, dict(_CLEAN)]
    r = assess_handoff(rounds)
    assert r["go"] is False                       # one reacquire fail -> not viable in-process
    assert r["reacquire_after_pydualsense"] == 2
    assert "Option B" in r["recommendation"]


def test_acquire_failure_is_nogo():
    r = assess_handoff([{**_CLEAN, "acquire_ok": False}])
    assert r["go"] is False


def test_empty_is_nogo():
    r = assess_handoff([])
    assert r["go"] is False and r["rounds"] == 0
