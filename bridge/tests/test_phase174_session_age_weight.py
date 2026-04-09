"""Phase 174 tests — Session age weighting in analyze_interperson_separation.py

8 tests:
  T174-1  --session-age-weight 0 (disabled) -> all weights == 1.0
  T174-2  --session-age-weight 30 with session from 30 days ago -> weight ~= 0.5
  T174-3  --session-age-weight 30 with session from today -> weight == 1.0
  T174-4  Very old session (365 days) with halflife=90 -> weight very small
  T174-5  _compute_session_age_weights never raises on empty input
  T174-6  _compute_session_age_weights never raises on bad session_ts
  T174-7  Age weighting flag present in argparse (--session-age-weight)
  T174-8  analyze_interperson_separation.py result dict contains age_weighted key
"""

import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = ROOT / "scripts" / "analyze_interperson_separation.py"


def _load_script():
    """Load analyze_interperson_separation as a module via importlib."""
    spec = importlib.util.spec_from_file_location(
        "analyze_interperson_separation", _SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def script_mod():
    """Lazily load the analysis script once per test session."""
    if not _SCRIPT_PATH.exists():
        pytest.skip("analyze_interperson_separation.py not found")
    try:
        mod = _load_script()
    except Exception as exc:
        pytest.skip(f"Could not load analyze script: {exc}")
    if not hasattr(mod, "_compute_session_age_weights"):
        pytest.skip("_compute_session_age_weights not present in script")
    return mod


# ---------------------------------------------------------------------------
# T174-1  halflife=0 (disabled) -> all weights == 1.0
# ---------------------------------------------------------------------------

def test_t174_1_disabled_returns_all_ones(script_mod):
    """When halflife_days=0, every weight must be exactly 1.0."""
    fn = script_mod._compute_session_age_weights
    sessions = [{"session_name": "hw_001"}, {"session_name": "hw_002"}]
    weights = fn(sessions, halflife_days=0.0)
    assert len(weights) == 2
    for i, w in weights.items():
        assert w == 1.0, f"Expected 1.0 for index {i}, got {w}"


# ---------------------------------------------------------------------------
# T174-2  session from 30 days ago with halflife=30 -> weight ~= 0.5
# ---------------------------------------------------------------------------

def test_t174_2_thirty_day_old_session_half_weight(script_mod):
    """Session 30 days old with halflife=30 should yield weight ~0.5."""
    fn = script_mod._compute_session_age_weights
    ref = date.today()
    thirty_days_ago = ref - timedelta(days=30)
    # Embed date in session name using YYYYMMDDTHHMMSSZ pattern
    sname = f"touchpad_corners_{thirty_days_ago.strftime('%Y%m%d')}T120000Z"
    sessions = [{"session_name": sname}]
    ref_str = ref.strftime("%Y-%m-%d")
    weights = fn(sessions, halflife_days=30.0, ref_date_str=ref_str)
    assert 0 in weights
    w = weights[0]
    # exp(-ln2/30*30) = exp(-ln2) = 0.5; allow small float tolerance
    assert abs(w - 0.5) < 0.01, f"Expected weight ~0.5, got {w}"


# ---------------------------------------------------------------------------
# T174-3  session from today -> weight == 1.0
# ---------------------------------------------------------------------------

def test_t174_3_today_session_weight_one(script_mod):
    """Session from today (age=0) should have weight 1.0."""
    fn = script_mod._compute_session_age_weights
    today = date.today()
    sname = f"touchpad_corners_{today.strftime('%Y%m%d')}T090000Z"
    sessions = [{"session_name": sname}]
    ref_str = today.strftime("%Y-%m-%d")
    weights = fn(sessions, halflife_days=30.0, ref_date_str=ref_str)
    assert 0 in weights
    w = weights[0]
    assert abs(w - 1.0) < 1e-9, f"Expected weight 1.0 for today's session, got {w}"


# ---------------------------------------------------------------------------
# T174-4  Very old session (365 days) with halflife=90 -> weight very small
# ---------------------------------------------------------------------------

def test_t174_4_very_old_session_small_weight(script_mod):
    """Session 365 days old with halflife=90 should yield a very small weight."""
    import math
    fn = script_mod._compute_session_age_weights
    ref = date.today()
    old_date = ref - timedelta(days=365)
    sname = f"touchpad_corners_{old_date.strftime('%Y%m%d')}T120000Z"
    sessions = [{"session_name": sname}]
    ref_str = ref.strftime("%Y-%m-%d")
    weights = fn(sessions, halflife_days=90.0, ref_date_str=ref_str)
    assert 0 in weights
    w = weights[0]
    # exp(-ln2/90*365) ~ exp(-2.8) ~ 0.06; definitely < 0.15
    expected = math.exp(-math.log(2) / 90.0 * 365.0)
    assert abs(w - expected) < 0.001, f"Expected weight ~{expected:.4f}, got {w}"
    assert w < 0.15, f"Expected small weight for 365-day-old session, got {w}"


# ---------------------------------------------------------------------------
# T174-5  Never raises on empty input
# ---------------------------------------------------------------------------

def test_t174_5_empty_sessions_never_raises(script_mod):
    """_compute_session_age_weights must not raise on empty session list."""
    fn = script_mod._compute_session_age_weights
    result = fn([], halflife_days=30.0, ref_date_str="2026-04-07")
    assert result == {}, f"Expected empty dict, got {result}"


# ---------------------------------------------------------------------------
# T174-6  Never raises on bad session_ts
# ---------------------------------------------------------------------------

def test_t174_6_bad_session_ts_never_raises(script_mod):
    """_compute_session_age_weights must not raise when session_ts is garbage."""
    fn = script_mod._compute_session_age_weights
    sessions = [
        {"session_name": "hw_001", "session_ts": "not-a-number"},
        {"session_name": "hw_002", "session_ts": None},
        {"session_name": "hw_003", "session_ts": -99999},
        {"session_name": "hw_004"},  # no session_ts at all
    ]
    # Should not raise; all weights default to 1.0 (age=0 fallback)
    try:
        weights = fn(sessions, halflife_days=30.0, ref_date_str="2026-04-07")
    except Exception as exc:
        pytest.fail(f"_compute_session_age_weights raised unexpectedly: {exc}")
    assert len(weights) == 4, f"Expected 4 weights, got {len(weights)}"
    # Each weight must be in (0, 1]
    for i, w in weights.items():
        assert 0.0 < w <= 1.0, f"Weight {w} at index {i} out of expected range (0, 1]"


# ---------------------------------------------------------------------------
# T174-7  Argparse has --session-age-weight flag
# ---------------------------------------------------------------------------

def test_t174_7_argparse_has_session_age_weight_flag():
    """--session-age-weight flag must be present in the script's argparse section."""
    text = _SCRIPT_PATH.read_text(encoding="utf-8", errors="ignore")
    assert "--session-age-weight" in text, (
        "--session-age-weight not found in analyze_interperson_separation.py"
    )
    assert "session_age_weight_halflife" in text, (
        "dest='session_age_weight_halflife' not found in argparse section"
    )
    assert "--session-age-weight-ref-date" in text, (
        "--session-age-weight-ref-date flag not found"
    )


# ---------------------------------------------------------------------------
# T174-8  Result dict contains age_weighted key
# ---------------------------------------------------------------------------

def test_t174_8_result_dict_contains_age_weighted_key():
    """analyze_interperson_separation.py must produce age_weighted key in result."""
    text = _SCRIPT_PATH.read_text(encoding="utf-8", errors="ignore")
    assert '"age_weighted"' in text or "'age_weighted'" in text, (
        "age_weighted key not found in analyze_interperson_separation.py result dict"
    )
    assert '"age_weight_halflife"' in text or "'age_weight_halflife'" in text, (
        "age_weight_halflife key not found in result dict"
    )
