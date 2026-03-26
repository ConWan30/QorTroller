"""
Hardware Calibration Progress Tests — Phase 108 Support
========================================================
Tests read from calibration_sessions/hardware_calibration_progress.json
which is populated by scripts/hardware_calibration_watcher.py while the
operator plays NCAA CFB 26 on DualShock Edge.

These tests verify TOURNAMENT READINESS CONDITIONS for hardware calibration:
  - Enough sessions collected (≥50) across multiple players (≥3)
  - touch_position_variance is nonzero (touchpad data captured — touchpad recapture)
  - Separation ratio > 1.0 (enables tournament deployment)
  - No false positives in live-mode sessions
  - Full 12-feature space active

Run:
  python scripts/hardware_calibration_watcher.py   # Start watcher while playing
  pytest tests/hardware/test_hardware_calibration.py -v -m hardware -s

Skip condition: calibration_sessions/hardware_calibration_progress.json absent.

Hardware count: 28 -> 36 (+8)
"""

import json
import pathlib

import pytest

_REPO_ROOT = pathlib.Path(__file__).parents[2]
_PROGRESS_FILE = _REPO_ROOT / "calibration_sessions" / "hardware_calibration_progress.json"


@pytest.fixture(scope="module")
def progress() -> dict:
    """Load calibration progress JSON. Skip entire module if file absent."""
    if not _PROGRESS_FILE.exists():
        pytest.skip(
            "calibration_sessions/hardware_calibration_progress.json not found. "
            "Run: python scripts/hardware_calibration_watcher.py "
            "while playing NCAA CFB 26 on DualShock Edge."
        )
    return json.loads(_PROGRESS_FILE.read_text())


# ---------------------------------------------------------------------------
# 1. Progress file schema integrity
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_1_progress_file_has_required_keys(progress):
    """Progress file contains all required calibration tracking fields."""
    required = [
        "last_updated", "db_path", "n_sessions", "n_players",
        "sessions_with_touch_variance", "touch_variance_mean", "touch_variance_max",
        "touch_variance_nonzero_fraction", "false_positive_count", "false_positive_rate",
        "separation_ratio_current", "separation_ratio_required",
        "players", "recent_sessions",
    ]
    for key in required:
        assert key in progress, f"Missing key in progress file: {key}"


# ---------------------------------------------------------------------------
# 2. Session volume gate
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_2_minimum_50_sessions_collected(progress):
    """At least 50 calibration sessions required for interperson_separation_analyzer.py."""
    n = progress["n_sessions"]
    assert n >= 50, (
        f"Only {n}/50 sessions collected. "
        "Keep playing NCAA CFB 26 — interperson_separation_analyzer.py "
        "requires N>=50 sessions across >=3 players before ratio can be recomputed."
    )


# ---------------------------------------------------------------------------
# 3. Player diversity gate (inter-person separation prerequisite)
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_3_minimum_3_players_for_separation_ratio(progress):
    """Inter-person separation ratio requires >=3 distinct players (device IDs)."""
    n_players = progress["n_players"]
    assert n_players >= 3, (
        f"Only {n_players}/3 players captured. "
        "Separation ratio is meaningless with <3 players. "
        "Run calibration sessions as Player 1, Player 2, and Player 3 "
        "using distinct DualShock Edge devices or device registrations."
    )


# ---------------------------------------------------------------------------
# 4. Touchpad recapture — any nonzero variance
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_4_touch_position_variance_nonzero_in_at_least_one_session(progress):
    """touch_position_variance must be nonzero in >=1 session (touchpad recapture started)."""
    nonzero_count = progress["sessions_with_touch_variance"]
    n = progress["n_sessions"]
    assert nonzero_count > 0, (
        f"touch_position_variance is ZERO across all {n} sessions. "
        "This is the Post-Phase-17 touchpad recapture blocker. "
        "During NCAA CFB 26 gameplay, touch the touchpad >=3 times per session. "
        "touch_position_variance = np.var(touch_xs) requires >=3 distinct touch X positions."
    )


# ---------------------------------------------------------------------------
# 5. Touchpad recapture — sustained coverage
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_5_touch_variance_nonzero_in_majority_of_sessions(progress):
    """touch_position_variance nonzero in >=50% of sessions (touchpad consistently used)."""
    fraction = progress["touch_variance_nonzero_fraction"]
    nonzero_count = progress["sessions_with_touch_variance"]
    n = progress["n_sessions"]
    assert fraction >= 0.5, (
        f"touch_position_variance nonzero in only {nonzero_count}/{n} sessions "
        f"({fraction:.0%} < 50%). "
        "Play more sessions with consistent touchpad use. "
        "Target: touchpad contact on every session for reliable inter-person variance."
    )


# ---------------------------------------------------------------------------
# 6. False positive gate (live mode safety)
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_6_zero_false_positives_in_live_sessions(progress):
    """Zero false positive BLOCK verdicts in non-dry-run sessions."""
    fp_count = progress["false_positive_count"]
    fp_rate = progress["false_positive_rate"]
    assert fp_count == 0, (
        f"{fp_count} false positive BLOCK(s) detected in live-mode sessions "
        f"(rate={fp_rate:.3f}). "
        "Investigate via GET /agent/rulings before tournament deployment. "
        "All human sessions must return CERTIFY in live mode."
    )


# ---------------------------------------------------------------------------
# 7. 12-feature space active
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_7_twelve_feature_space_active(progress):
    """touch_variance_max > 0 confirms 12-feature L4 space is active (not 10-feature)."""
    max_variance = progress["touch_variance_max"]
    assert max_variance > 0.0, (
        f"touch_variance_max={max_variance}. "
        "12-feature space requires non-zero touch_position_variance in >=1 session. "
        "Currently running in 10-feature space (2 excluded: "
        "trigger_resistance_change_rate + touch_position_variance). "
        "Touchpad recapture unlocks the full 12-feature biometric fingerprint "
        "and enables tremor FFT widening for improved inter-person separation."
    )


# ---------------------------------------------------------------------------
# 8. Separation ratio tournament gate
# ---------------------------------------------------------------------------

@pytest.mark.hardware
def test_8_separation_ratio_exceeds_tournament_threshold(progress):
    """separation_ratio_current > 1.0 — the TOURNAMENT BLOCKER gate.

    This test will FAIL until:
      1. Sessions with nonzero touch_position_variance are collected (tests 4-5)
      2. scripts/interperson_separation_analyzer.py is run
      3. SEPARATION_RATIO_CURRENT env var is set to the new value
      4. Watcher is re-run to update the progress file
    """
    ratio = progress["separation_ratio_current"]
    required = progress["separation_ratio_required"]
    assert ratio > required, (
        f"separation_ratio_current={ratio:.3f} <= required={required:.1f}. "
        "TOURNAMENT BLOCKER: L4 cannot distinguish between players at this ratio. "
        "Steps to unlock: "
        "(1) Collect >=50 sessions with nonzero touch_position_variance. "
        "(2) Run: python scripts/interperson_separation_analyzer.py. "
        "(3) Set SEPARATION_RATIO_CURRENT=<new_value> in environment. "
        "(4) Re-run watcher to update progress file. "
        f"Phase 57 baseline: 0.362. Required: >1.0."
    )
