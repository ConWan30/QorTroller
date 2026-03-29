"""
Phase 121 — SeparationRatioResult + VAPISeparationStatus SDK tests.
4 tests total.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sdk.vapi_sdk import SeparationRatioResult, VAPISeparationStatus


# ---------------------------------------------------------------------------
# Test 1 — SeparationRatioResult __slots__ has exactly 6 fields
# ---------------------------------------------------------------------------

def test_separation_ratio_result_slots():
    slots = SeparationRatioResult.__slots__
    expected = {
        "pooled_ratio", "battery_stratified_ratio", "tournament_blocker",
        "gap_to_target", "tournament_ready", "error",
    }
    assert set(slots) == expected


# ---------------------------------------------------------------------------
# Test 2 — VAPISeparationStatus initializes without raising
# ---------------------------------------------------------------------------

def test_vapi_separation_status_init():
    sep = VAPISeparationStatus("http://localhost:18080", "test-key")
    assert sep._base == "http://localhost:18080"
    assert sep._key == "test-key"


# ---------------------------------------------------------------------------
# Test 3 — get_status() on bad URL returns error SeparationRatioResult
# ---------------------------------------------------------------------------

def test_get_status_bad_url_returns_error():
    sep = VAPISeparationStatus("http://localhost:1", "test-key")
    result = sep.get_status()
    assert result.error is not None
    assert isinstance(result.error, str)
    assert len(result.error) > 0


# ---------------------------------------------------------------------------
# Test 4 — error result has correct blocker/ready/ratio defaults
# ---------------------------------------------------------------------------

def test_get_status_error_defaults():
    sep = VAPISeparationStatus("http://localhost:1", "test-key")
    result = sep.get_status()
    assert result.tournament_blocker is True
    assert result.tournament_ready is False
    assert result.pooled_ratio == 0.0
    assert result.gap_to_target == 1.0
    assert result.battery_stratified_ratio == -1.0
