"""
sdk/tests/test_phase229_sdk.py
Phase 229 — SDK VAPIAITSeparation.status() (4 tests)

T229-SDK-1: status() parses all 7 fields from a successful response
T229-SDK-2: status() returns AITSeparationResult with error on HTTP failure
T229-SDK-3: AITSeparationResult has correct dataclass slots
T229-SDK-4: all_pairs_above_1=True correctly parsed when response field is True
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


def make_ait():
    from vapi_sdk import VAPIAITSeparation
    obj = VAPIAITSeparation.__new__(VAPIAITSeparation)
    obj._base = "http://localhost:8765"
    obj._key  = "test"
    return obj


# ---------------------------------------------------------------------------
# T229-SDK-1: status() parses all 7 data fields from a successful response
# ---------------------------------------------------------------------------

def test_t229_sdk_1_parses_all_fields():
    """VAPIAITSeparation.status() correctly parses all result fields."""
    ait = make_ait()

    import json, unittest.mock

    payload = {
        "ait_separation_enabled": True,
        "n_sessions":             24,
        "separation_ratio":       1.199,
        "all_pairs_above_1":      True,
        "inter_player_mean":      1.682,
        "intra_player_mean":      0.991,
        "loo_accuracy":           0.667,
        "pair_distances":         {"P1vP2": 1.850, "P1vP3": 1.846, "P2vP3": 1.349},
        "analysis_date":          "2026-04-18",
        "last_run_ts":            1713427200.0,
        "timestamp":              1713427201.0,
    }

    class MockResp:
        def read(self): return json.dumps(payload).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    with unittest.mock.patch("urllib.request.urlopen", return_value=MockResp()):
        result = ait.status()

    assert result.ait_separation_enabled is True
    assert result.n_sessions == 24
    assert abs(result.separation_ratio - 1.199) < 1e-4
    assert result.all_pairs_above_1 is True
    assert abs(result.inter_player_mean - 1.682) < 1e-4
    assert abs(result.intra_player_mean - 0.991) < 1e-4
    assert abs(result.loo_accuracy - 0.667) < 1e-4
    assert result.error == ""


# ---------------------------------------------------------------------------
# T229-SDK-2: status() returns AITSeparationResult with error on HTTP failure
# ---------------------------------------------------------------------------

def test_t229_sdk_2_returns_error_on_failure():
    """VAPIAITSeparation.status() returns AITSeparationResult with error on connection failure."""
    ait = make_ait()

    import unittest.mock
    with unittest.mock.patch(
        "urllib.request.urlopen", side_effect=RuntimeError("connection refused")
    ):
        result = ait.status()

    from vapi_sdk import AITSeparationResult
    assert isinstance(result, AITSeparationResult)
    assert "connection refused" in result.error
    assert result.separation_ratio == 0.0
    assert result.all_pairs_above_1 is False


# ---------------------------------------------------------------------------
# T229-SDK-3: AITSeparationResult has correct dataclass slots
# ---------------------------------------------------------------------------

def test_t229_sdk_3_dataclass_slots():
    """AITSeparationResult is a dataclass with the expected 8 slots."""
    from vapi_sdk import AITSeparationResult
    import dataclasses

    assert dataclasses.is_dataclass(AITSeparationResult)
    slots = set(AITSeparationResult.__dataclass_fields__.keys())
    expected = {
        "ait_separation_enabled",
        "n_sessions",
        "separation_ratio",
        "all_pairs_above_1",
        "inter_player_mean",
        "intra_player_mean",
        "loo_accuracy",
        "error",
    }
    assert expected == slots, f"Slot mismatch: {expected.symmetric_difference(slots)}"


# ---------------------------------------------------------------------------
# T229-SDK-4: all_pairs_above_1=True correctly parsed from response
# ---------------------------------------------------------------------------

def test_t229_sdk_4_all_pairs_above_1_parsed():
    """all_pairs_above_1=True from response is parsed as bool True in AITSeparationResult."""
    ait = make_ait()

    import json, unittest.mock

    payload = {
        "ait_separation_enabled": True,
        "n_sessions":             24,
        "separation_ratio":       1.199,
        "all_pairs_above_1":      True,
        "inter_player_mean":      1.682,
        "intra_player_mean":      0.991,
        "loo_accuracy":           0.667,
        "timestamp":              1713427201.0,
    }

    class MockResp:
        def read(self): return json.dumps(payload).encode()
        def __enter__(self): return self
        def __exit__(self, *a): pass

    with unittest.mock.patch("urllib.request.urlopen", return_value=MockResp()):
        result = ait.status()

    assert result.all_pairs_above_1 is True
    assert isinstance(result.all_pairs_above_1, bool)
    # This is the Phase 229 breakthrough: first probe type to achieve all_pairs_above_1=True
    # AIT 4-feature pipeline: [accel_tremor_peak_hz, roll_cos, roll_sin, pitch_cos]
    assert result.separation_ratio > 1.0
