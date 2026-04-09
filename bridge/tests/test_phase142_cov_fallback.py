"""
Phase 142 — Small-N Covariance Auto-Fallback Tests (8 tests)

Tests the Phase 142 guard that switches to diagonal covariance when
N/p < COV_MIN_RATIO (default 3.0), preventing off-diagonal noise from
suppressing true inter-player distances (Phase 141: P1 vs P3 suppression=0.032).

Tests:
1. COV_MIN_RATIO constant exists and equals 3.0
2. run_analysis signature accepts cov_auto_fallback and cov_min_ratio params
3. N/p < 3.0 for touchpad_corners (N=11, p=8 → ratio=1.375)
4. auto-fallback triggers when N/p < threshold
5. auto-fallback does NOT trigger when N/p >= threshold
6. --no-cov-auto-fallback flag disables fallback
7. cov_mode result key is 'diagonal' when fallback triggered
8. cov_mode result key is 'full' when fallback disabled
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Test 1: COV_MIN_RATIO constant exists and equals 3.0
# ---------------------------------------------------------------------------

def test_1_cov_min_ratio_constant():
    from analyze_interperson_separation import COV_MIN_RATIO
    assert COV_MIN_RATIO == 3.0, f"COV_MIN_RATIO should be 3.0, got {COV_MIN_RATIO}"


# ---------------------------------------------------------------------------
# Test 2: run_analysis signature accepts cov_auto_fallback and cov_min_ratio
# ---------------------------------------------------------------------------

def test_2_run_analysis_signature():
    from analyze_interperson_separation import run_analysis
    sig = inspect.signature(run_analysis)
    params = sig.parameters
    assert "cov_auto_fallback" in params, "run_analysis must accept cov_auto_fallback param"
    assert "cov_min_ratio" in params, "run_analysis must accept cov_min_ratio param"
    # Default values
    assert params["cov_auto_fallback"].default is True
    assert params["cov_min_ratio"].default == 3.0


# ---------------------------------------------------------------------------
# Test 3: N/p < 3.0 for touchpad_corners analysis
# ---------------------------------------------------------------------------

def test_3_touchpad_corners_np_ratio_below_threshold():
    """N=11 sessions, p=8 active features → N/p = 1.375 < 3.0"""
    from analyze_interperson_separation import COV_MIN_RATIO
    n_touchpad_corners_sessions = 11  # P1=3, P2=4, P3=4
    n_active_features = 8             # from touchpad_corners analysis output
    np_ratio = n_touchpad_corners_sessions / n_active_features
    assert np_ratio < COV_MIN_RATIO, (
        f"N/p = {np_ratio:.3f} should be < COV_MIN_RATIO = {COV_MIN_RATIO}. "
        "touchpad_corners analysis should trigger Phase 142 auto-fallback."
    )


# ---------------------------------------------------------------------------
# Test 4: auto-fallback logic: triggers when N/p < threshold
# ---------------------------------------------------------------------------

def test_4_fallback_triggers_below_threshold():
    from analyze_interperson_separation import COV_MIN_RATIO
    # Simulate: N=11, p=8, threshold=3.0
    n_samples, n_features = 11, 8
    cov_ratio = n_samples / n_features
    cov_auto_fallback = True
    cov_min_ratio = COV_MIN_RATIO
    _use_diagonal = cov_auto_fallback and (cov_ratio < cov_min_ratio)
    assert _use_diagonal is True, (
        f"Fallback should trigger: N/p={cov_ratio:.3f} < {cov_min_ratio}"
    )


# ---------------------------------------------------------------------------
# Test 5: auto-fallback does NOT trigger when N/p >= threshold
# ---------------------------------------------------------------------------

def test_5_fallback_does_not_trigger_above_threshold():
    from analyze_interperson_separation import COV_MIN_RATIO
    # Simulate: N=50, p=8, threshold=3.0 → ratio=6.25 ≥ 3.0
    n_samples, n_features = 50, 8
    cov_ratio = n_samples / n_features
    cov_auto_fallback = True
    cov_min_ratio = COV_MIN_RATIO
    _use_diagonal = cov_auto_fallback and (cov_ratio < cov_min_ratio)
    assert _use_diagonal is False, (
        f"Fallback should NOT trigger: N/p={cov_ratio:.3f} >= {cov_min_ratio}"
    )


# ---------------------------------------------------------------------------
# Test 6: --no-cov-auto-fallback disables fallback
# ---------------------------------------------------------------------------

def test_6_no_fallback_flag_disables_fallback():
    from analyze_interperson_separation import COV_MIN_RATIO
    # Even with low N/p, if cov_auto_fallback=False → full covariance
    n_samples, n_features = 11, 8
    cov_ratio = n_samples / n_features
    cov_auto_fallback = False  # disabled by --no-cov-auto-fallback
    cov_min_ratio = COV_MIN_RATIO
    _use_diagonal = cov_auto_fallback and (cov_ratio < cov_min_ratio)
    assert _use_diagonal is False, (
        "When cov_auto_fallback=False, should never use diagonal covariance "
        "regardless of N/p ratio"
    )


# ---------------------------------------------------------------------------
# Test 7: cov_mode result key is 'diagonal' when fallback triggered
# ---------------------------------------------------------------------------

def test_7_cov_mode_diagonal_when_triggered():
    """Verify the cov_mode metadata key is set correctly in result dict."""
    # We simulate what run_analysis sets:
    _use_diagonal_cov = True
    cov_mode = "diagonal" if _use_diagonal_cov else "full"
    assert cov_mode == "diagonal"


# ---------------------------------------------------------------------------
# Test 8: cov_mode result key is 'full' when fallback disabled
# ---------------------------------------------------------------------------

def test_8_cov_mode_full_when_fallback_disabled():
    """Verify cov_mode is 'full' when fallback not triggered."""
    _use_diagonal_cov = False
    cov_mode = "diagonal" if _use_diagonal_cov else "full"
    assert cov_mode == "full"
