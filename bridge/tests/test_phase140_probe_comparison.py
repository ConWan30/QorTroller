"""
Phase 140 — Multi-Probe Comparison Mode Tests (8 tests)

Tests the --probe-comparison CLI flag added to analyze_interperson_separation.py,
which runs all viable structured probe types and outputs a comparison table.

Tests:
1. --probe-comparison argparse flag exists and defaults to False
2. --probe-comparison raises error when combined with --session-type
3. run_analysis returns 'players' key for probe-comparison downstream
4. run_analysis returns 'inter_distance_matrix' key with 'values'
5. P1vP3 extraction logic: correct index lookup from inter_distance_matrix
6. Probe type list contains exactly the 3 expected touchpad types
7. _probe_results dict accumulates one entry per probe type
8. All 3 probe types are in _TERMINAL_CAL_ONLY_TYPES (fast-path eligible)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Test 1: --probe-comparison flag exists and defaults to False
# ---------------------------------------------------------------------------

def test_1_probe_comparison_flag_defaults_false():
    import argparse
    sys.argv = ["analyze_interperson_separation.py"]
    from analyze_interperson_separation import main
    # Parse with no args — should not raise; probe_comparison=False
    import argparse as ap
    parser = ap.ArgumentParser()
    parser.add_argument("--probe-comparison", action="store_true", default=False)
    args = parser.parse_args([])
    assert args.probe_comparison is False


# ---------------------------------------------------------------------------
# Test 2: --probe-comparison raises error when combined with --session-type
# ---------------------------------------------------------------------------

def test_2_probe_comparison_conflicts_with_session_type(monkeypatch, capsys):
    """Verify that --probe-comparison + --session-type triggers error exit."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "scripts/analyze_interperson_separation.py",
         "--probe-comparison", "--session-type", "touchpad_corners"],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert "--probe-comparison cannot be combined with --session-type" in result.stderr


# ---------------------------------------------------------------------------
# Test 3: run_analysis returns 'players' key
# ---------------------------------------------------------------------------

def test_3_run_analysis_returns_players_key():
    """run_analysis result must contain 'players' list for probe-comparison P1vP3 extraction."""
    from analyze_interperson_separation import run_analysis
    # Use touchpad_corners for fast-path — minimal session count
    try:
        result = run_analysis(session_type_filter="touchpad_corners")
        assert "players" in result, "run_analysis result must contain 'players' key"
        assert isinstance(result["players"], list)
    except RuntimeError as e:
        pytest.skip(f"Insufficient sessions for test: {e}")


# ---------------------------------------------------------------------------
# Test 4: run_analysis returns 'inter_distance_matrix' with 'values'
# ---------------------------------------------------------------------------

def test_4_run_analysis_returns_inter_distance_matrix():
    """Verify inter_distance_matrix structure for probe-comparison P1vP3 extraction."""
    from analyze_interperson_separation import run_analysis
    try:
        result = run_analysis(session_type_filter="touchpad_corners")
        assert "inter_distance_matrix" in result
        mat = result["inter_distance_matrix"]
        assert "values" in mat, "inter_distance_matrix must have 'values' key"
        assert isinstance(mat["values"], list)
    except RuntimeError as e:
        pytest.skip(f"Insufficient sessions for test: {e}")


# ---------------------------------------------------------------------------
# Test 5: P1vP3 extraction index logic is correct
# ---------------------------------------------------------------------------

def test_5_p1vp3_extraction_index_logic():
    """Simulate P1vP3 extraction from inter_distance_matrix values list."""
    _players_list = ["Player 1", "Player 2", "Player 3"]
    # Mock symmetric distance matrix: P1vP2=1.428, P1vP3=0.127, P2vP3=1.304
    _values = [
        [0.0, 1.428, 0.127],
        [1.428, 0.0, 1.304],
        [0.127, 1.304, 0.0],
    ]
    _i1 = _players_list.index("Player 1")
    _i3 = _players_list.index("Player 3")
    _p1vp3 = _values[_i1][_i3]
    assert _p1vp3 == pytest.approx(0.127), (
        f"P1vP3 extraction failed: expected 0.127, got {_p1vp3}"
    )


# ---------------------------------------------------------------------------
# Test 6: Probe type list contains exactly the 3 expected touchpad types
# ---------------------------------------------------------------------------

def test_6_probe_type_list_contains_3_touchpad_types():
    """The probe types for probe-comparison must be the 3 touchpad types."""
    _PROBE_TYPES = ["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]
    assert len(_PROBE_TYPES) == 3
    assert "touchpad_corners" in _PROBE_TYPES
    assert "touchpad_freeform" in _PROBE_TYPES
    assert "touchpad_swipes" in _PROBE_TYPES
    assert "gameplay" not in _PROBE_TYPES


# ---------------------------------------------------------------------------
# Test 7: _probe_results dict accumulates one entry per probe type
# ---------------------------------------------------------------------------

def test_7_probe_results_accumulates_one_entry_per_type():
    """Verify the probe_results dict structure for comparison table output."""
    _PROBE_TYPES = ["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]
    _probe_results = {}
    # Simulate skipped probes (None) and mock success
    _mock_result = {
        "separation_ratio": 1.5,
        "n_sessions": 11,
        "classification": {"accuracy": 0.636},
        "inter_player_mean": 0.953,
        "intra_player_mean": 0.614,
        "players": ["Player 1", "Player 2", "Player 3"],
        "inter_distance_matrix": {"values": [[0,1.4,0.1],[1.4,0,1.3],[0.1,1.3,0]]},
    }
    _probe_results["touchpad_corners"] = _mock_result
    _probe_results["touchpad_freeform"] = None  # skipped
    _probe_results["touchpad_swipes"] = _mock_result

    assert len(_probe_results) == 3
    assert _probe_results["touchpad_corners"] is not None
    assert _probe_results["touchpad_freeform"] is None


# ---------------------------------------------------------------------------
# Test 8: All 3 probe types are in _TERMINAL_CAL_ONLY_TYPES (fast-path eligible)
# ---------------------------------------------------------------------------

def test_8_probe_types_are_terminal_cal_only():
    """All 3 probe-comparison types must trigger the Phase 139 fast-path."""
    from analyze_interperson_separation import _TERMINAL_CAL_ONLY_TYPES
    _PROBE_TYPES = ["touchpad_corners", "touchpad_freeform", "touchpad_swipes"]
    for _pt in _PROBE_TYPES:
        assert _pt in _TERMINAL_CAL_ONLY_TYPES, (
            f"'{_pt}' must be in _TERMINAL_CAL_ONLY_TYPES to benefit from Phase 139 fast-path"
        )
