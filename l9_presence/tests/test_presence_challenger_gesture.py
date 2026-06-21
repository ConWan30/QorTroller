"""Tests for the challenger's dual-gesture acceptance (pure; no controller/pydualsense)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.presence_challenger import (  # noqa: E402
    gesture_active_from_state,
    parse_accepted,
)


def _state(*, l5=False, r5=False, l4=False, r4=False, touch=False):
    return SimpleNamespace(
        L5=l5, R5=r5, L4=l4, R4=r4,
        trackPadTouch0=SimpleNamespace(isActive=touch),
    )


# ---- parse_accepted ----

def test_parse_single():
    assert parse_accepted("l5") == ["l5"]


def test_parse_dual_plus():
    assert parse_accepted("l5+touch") == ["l5", "touch"]


def test_parse_comma_and_swipe_alias():
    assert parse_accepted("r5,swipe") == ["r5", "touch"]
    assert parse_accepted("touchpad") == ["touch"]


def test_parse_dedupes_and_defaults():
    assert parse_accepted("l5+l5") == ["l5"]
    assert parse_accepted("") == ["l5"]      # back-compat default
    assert parse_accepted("  ") == ["l5"]


def test_parse_rejects_unknown():
    with pytest.raises(ValueError):
        parse_accepted("cross")
    with pytest.raises(ValueError):
        parse_accepted("l5+square")


# ---- gesture_active_from_state (the dual OR) ----

def test_l5_only_accepts_l5_not_touch():
    acc = ["l5"]
    assert gesture_active_from_state(_state(l5=True), acc) is True
    assert gesture_active_from_state(_state(touch=True), acc) is False
    assert gesture_active_from_state(_state(), acc) is False


def test_dual_accepts_either():
    acc = ["l5", "touch"]
    assert gesture_active_from_state(_state(l5=True), acc) is True     # paddle
    assert gesture_active_from_state(_state(touch=True), acc) is True  # touchpad
    assert gesture_active_from_state(_state(l5=True, touch=True), acc) is True
    assert gesture_active_from_state(_state(), acc) is False           # neither


def test_dual_does_not_accept_unlisted_button():
    # r5 not in the accepted set -> pressing R5 is NOT a response
    assert gesture_active_from_state(_state(r5=True), ["l5", "touch"]) is False


def test_missing_touch_attr_is_safe():
    bare = SimpleNamespace(L5=False)  # no trackPadTouch0 attribute at all
    assert gesture_active_from_state(bare, ["l5", "touch"]) is False
