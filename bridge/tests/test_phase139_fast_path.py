"""
Phase 139 — Session-Loading Fast-Path Tests (8 tests)

Tests the _TERMINAL_CAL_ONLY_TYPES constant and the hw_* skip-path
that reduces --session-type filter runtime from 120 s → <20 s
by avoiding loading gameplay sessions that would be discarded anyway.

Tests:
1. _TERMINAL_CAL_ONLY_TYPES is a frozenset
2. 'gameplay' NOT in _TERMINAL_CAL_ONLY_TYPES
3. 'touchpad_corners' IN _TERMINAL_CAL_ONLY_TYPES
4. All expected structured-probe types present
5. Fast-path activates when filter is touchpad_corners
6. Fast-path does NOT activate when filter is None
7. Fast-path does NOT activate when filter is 'gameplay'
8. _detect_session_type returns 'gameplay' for hw_* stem
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Test 1: _TERMINAL_CAL_ONLY_TYPES is a frozenset (immutable)
# ---------------------------------------------------------------------------

def test_1_terminal_cal_only_types_is_frozenset():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    assert isinstance(_TERMINAL_CAL_ONLY_TYPES, frozenset), (
        "_TERMINAL_CAL_ONLY_TYPES must be a frozenset for immutability"
    )


# ---------------------------------------------------------------------------
# Test 2: 'gameplay' is NOT in _TERMINAL_CAL_ONLY_TYPES
# ---------------------------------------------------------------------------

def test_2_gameplay_not_in_terminal_cal_only_types():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    assert "gameplay" not in _TERMINAL_CAL_ONLY_TYPES, (
        "'gameplay' must NOT be in _TERMINAL_CAL_ONLY_TYPES — "
        "hw_* sessions ARE gameplay and must not be skipped when filtering to gameplay"
    )


# ---------------------------------------------------------------------------
# Test 3: 'touchpad_corners' IN _TERMINAL_CAL_ONLY_TYPES
# ---------------------------------------------------------------------------

def test_3_touchpad_corners_in_terminal_cal_only_types():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    assert "touchpad_corners" in _TERMINAL_CAL_ONLY_TYPES, (
        "'touchpad_corners' must be in _TERMINAL_CAL_ONLY_TYPES — "
        "it only appears in terminal_cal_P* directories"
    )


# ---------------------------------------------------------------------------
# Test 4: All expected structured-probe types are present
# ---------------------------------------------------------------------------

def test_4_all_structured_probe_types_present():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    expected = {
        "touchpad_corners", "touchpad_freeform", "touchpad_swipes",
        "trigger_rhythm", "button_sequence", "resting_baseline",
    }
    missing = expected - _TERMINAL_CAL_ONLY_TYPES
    assert not missing, f"Missing types in _TERMINAL_CAL_ONLY_TYPES: {missing}"


# ---------------------------------------------------------------------------
# Test 5: Fast-path activates when session_type_filter is 'touchpad_corners'
# ---------------------------------------------------------------------------

def test_5_fast_path_activates_for_touchpad_corners():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    session_type_filter = "touchpad_corners"
    _skip_hw = session_type_filter in _TERMINAL_CAL_ONLY_TYPES
    assert _skip_hw is True, (
        "Fast-path must activate for 'touchpad_corners' filter — "
        "hw_* sessions are all 'gameplay' and would be discarded"
    )


# ---------------------------------------------------------------------------
# Test 6: Fast-path does NOT activate when filter is None (full corpus)
# ---------------------------------------------------------------------------

def test_6_fast_path_inactive_when_filter_none():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    session_type_filter = None
    _skip_hw = session_type_filter in _TERMINAL_CAL_ONLY_TYPES
    assert _skip_hw is False, (
        "Fast-path must NOT activate when filter is None — "
        "full corpus analysis must load hw_* sessions"
    )


# ---------------------------------------------------------------------------
# Test 7: Fast-path does NOT activate when filter is 'gameplay'
# ---------------------------------------------------------------------------

def test_7_fast_path_inactive_for_gameplay_filter():
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    session_type_filter = "gameplay"
    _skip_hw = session_type_filter in _TERMINAL_CAL_ONLY_TYPES
    assert _skip_hw is False, (
        "Fast-path must NOT activate for 'gameplay' filter — "
        "hw_* sessions ARE gameplay and must be loaded"
    )


# ---------------------------------------------------------------------------
# Test 8: _detect_session_type returns 'gameplay' for hw_* stem
# ---------------------------------------------------------------------------

def test_8_detect_session_type_gameplay_for_hw_stem():
    from analyze_interperson_separation import _detect_session_type
    # hw_* sessions have stems like 'hw_005', 'hw_042' — should be 'gameplay'
    for stem in ("hw_005", "hw_042", "hw_073", "human_baseline_001"):
        result = _detect_session_type(stem)
        assert result == "gameplay", (
            f"_detect_session_type('{stem}') returned '{result}', expected 'gameplay' — "
            "hw_* sessions must be classified as gameplay to justify the fast-path skip"
        )
