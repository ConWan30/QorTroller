"""Tests for the bridge-context + screen lull sources (pure logic)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bridge.controller.probe_context import (  # noqa: E402
    ContextVerdict,
    classify_context,
    clear_to_fire_context,
)
from bridge.controller.probe_screen import (  # noqa: E402
    ScreenVerdict,
    classify_screen,
    clear_to_fire_screen,
)


# ---- context: APOP 5-state ----

def test_apop_match_transition_is_lull():
    assert classify_context({"latest_state": "MATCH_TRANSITION"}) is ContextVerdict.IN_MATCH_LULL


def test_apop_active_and_competitive_are_active():
    assert classify_context({"latest_state": "ACTIVE_MATCH_PLAY"}) is ContextVerdict.ACTIVE
    assert classify_context({"latest_state": "COMPETITIVE_CONTROL"}) is ContextVerdict.ACTIVE


def test_apop_menu_and_unknown():
    assert classify_context({"latest_state": "NON_COMPETITIVE_MENU"}) is ContextVerdict.MENU
    assert classify_context({"latest_state": "UNKNOWN_LOW_EVIDENCE"}) is ContextVerdict.UNKNOWN


# ---- context: GAD fallback + precedence ----

def test_gad_fallback_when_no_apop():
    assert classify_context({"latest_gameplay_context": "ACTIVE_GAMEPLAY"}) is ContextVerdict.ACTIVE
    assert classify_context({"latest_gameplay_context": "MENU_DETECTED"}) is ContextVerdict.MENU


def test_apop_takes_precedence_over_gad():
    s = {"latest_state": "MATCH_TRANSITION", "latest_gameplay_context": "ACTIVE_GAMEPLAY"}
    assert classify_context(s) is ContextVerdict.IN_MATCH_LULL


def test_none_and_empty_and_garbage_are_unknown():
    assert classify_context(None) is ContextVerdict.UNKNOWN
    assert classify_context({}) is ContextVerdict.UNKNOWN
    assert classify_context({"latest_state": "WAT"}) is ContextVerdict.UNKNOWN


# ---- context: gate policy ----

def test_context_gate_strict_vs_lenient():
    lull = {"latest_state": "MATCH_TRANSITION"}
    menu = {"latest_state": "NON_COMPETITIVE_MENU"}
    assert clear_to_fire_context(lull)[0] is True
    assert clear_to_fire_context(menu)[0] is False                 # strict: menu not allowed
    assert clear_to_fire_context(menu, allow_menu=True)[0] is True  # lenient
    assert clear_to_fire_context({"latest_state": "ACTIVE_MATCH_PLAY"}, allow_menu=True)[0] is False


# ---- screen: pure classifier ----

def test_screen_stoppage_banner():
    assert classify_screen("OFFICIAL TIMEOUT") is ScreenVerdict.STOPPAGE
    assert classify_screen("Booth Review in progress") is ScreenVerdict.STOPPAGE
    assert classify_screen("Two Minute Warning") is ScreenVerdict.STOPPAGE


def test_screen_playclock_from_text():
    assert classify_screen("PLAY CLOCK 21") is ScreenVerdict.PRE_SNAP
    assert classify_screen("play clock: 7") is ScreenVerdict.PRE_SNAP


def test_screen_playclock_from_value():
    assert classify_screen(None, playclock_value=18) is ScreenVerdict.PRE_SNAP
    assert classify_screen(None, playclock_value=40) is ScreenVerdict.PRE_SNAP


def test_screen_playclock_zero_is_not_presnap():
    # 0 = snap boundary, not a safe pre-snap window
    assert classify_screen(None, playclock_value=0) is ScreenVerdict.UNKNOWN
    assert classify_screen(None, playclock_value=99) is ScreenVerdict.UNKNOWN  # out of range


def test_screen_stoppage_beats_playclock():
    assert classify_screen("TIMEOUT  play clock 15") is ScreenVerdict.STOPPAGE


def test_screen_unknown_on_empty():
    assert classify_screen(None) is ScreenVerdict.UNKNOWN
    assert classify_screen("") is ScreenVerdict.UNKNOWN
    assert classify_screen("1st & 10") is ScreenVerdict.UNKNOWN  # no clock, no banner -> defer


def test_screen_gate_policy():
    assert clear_to_fire_screen("PLAY CLOCK 12")[0] is True
    assert clear_to_fire_screen("TIMEOUT")[0] is True
    assert clear_to_fire_screen("TIMEOUT", allow_stoppage=False)[0] is False
    assert clear_to_fire_screen("1st & 10")[0] is False
