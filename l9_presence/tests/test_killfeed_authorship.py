"""Tests for the kill-feed authorship oracle — the anti-spectate differentiator.

Validates the load-bearing claim: a kill credited to YOUR handle and bound to YOUR trigger reads AUTHORED;
kills crediting others read SPECTATED; OCR noise on the handle still matches; your handle as a VICTIM (your
death) is not counted as your kill.
"""
from __future__ import annotations

import pytest

from l9_presence.killfeed_authorship import (
    AuthorshipVerdict,
    KillfeedAuthorshipOracle,
    canon,
    default_handle,
)

_HANDLE = "QorTrola30"


def test_canon_tolerates_ocr_confusion():
    # the noisy read QorTroIa3O (capital-i for l, capital-O for 0) canonicalizes to the same token
    assert canon("QorTrola30") == canon("QorTroIa3O") == "q0rtr01a30"
    assert canon("  Qor Trola 30 ") == "q0rtr01a30"        # spaces/case stripped
    assert canon("SomeoneElse") != canon(_HANDLE)


def test_default_handle_env(monkeypatch):
    monkeypatch.setenv("QORTROLLER_HANDLE", "TestGamer7")
    assert default_handle() == "TestGamer7"


def test_authored_when_own_kill_bound_to_trigger():
    o = KillfeedAuthorshipOracle(_HANDLE)
    o.push_trigger(1000.0)                                  # you fired
    o.push_killfeed_line(1300.0, "QorTrola30 ☠ EnemyDude")  # your kill 300ms later (killer on the left)
    r = o.verdict()
    assert r.verdict is AuthorshipVerdict.AUTHORED_PRESENT
    assert r.own_kills == 1 and r.bound_kills == 1


def test_ocr_noisy_own_kill_still_authored():
    o = KillfeedAuthorshipOracle(_HANDLE)
    o.push_trigger(2000.0)
    o.push_killfeed_line(2250.0, "QorTroIa3O [AR] Victim99")   # noisy OCR of the handle, still the killer
    assert o.verdict().verdict is AuthorshipVerdict.AUTHORED_PRESENT


def test_spectated_when_kills_credit_others():
    o = KillfeedAuthorshipOracle(_HANDLE)
    o.push_trigger(500.0); o.push_trigger(900.0)            # you spammed R2 while spectating
    o.push_killfeed_line(1000.0, "TeammateBob ☠ EnemyA")   # teammate's kills, not yours
    o.push_killfeed_line(1400.0, "TeammateBob ☠ EnemyB")
    r = o.verdict()
    assert r.verdict is AuthorshipVerdict.SPECTATED_NOT_AUTHORED
    assert r.own_kills == 0 and r.other_kills == 2


def test_own_handle_as_victim_is_neutral_not_a_kill():
    o = KillfeedAuthorshipOracle(_HANDLE)
    o.push_killfeed_line(1000.0, "EnemySniper ☠ QorTrola30")  # YOU died (handle on the right = victim)
    r = o.verdict()
    # your death is neutral: not your kill, and NOT a spectating signal (deaths happen in genuine play too)
    assert r.own_kills == 0 and r.other_kills == 0
    assert r.verdict is AuthorshipVerdict.NO_KILL_EVENTS


def test_own_kill_unbound_without_trigger_in_window():
    o = KillfeedAuthorshipOracle(_HANDLE, lag_min_ms=50, lag_max_ms=900)
    o.push_trigger(0.0)                                      # trigger far in the past
    o.push_killfeed_line(5000.0, "QorTrola30 ☠ Enemy")  # own kill but no trigger within 50-900ms before
    assert o.verdict().verdict is AuthorshipVerdict.OWN_KILL_UNBOUND


def test_no_kills_and_unverifiable():
    assert KillfeedAuthorshipOracle(_HANDLE).verdict().verdict is AuthorshipVerdict.UNVERIFIABLE
    o = KillfeedAuthorshipOracle(_HANDLE)
    o.push_trigger(100.0)                                    # fired, but no feed rows at all
    assert o.verdict().verdict is AuthorshipVerdict.NO_KILL_EVENTS
