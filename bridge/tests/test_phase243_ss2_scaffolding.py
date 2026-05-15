"""Phase 243-SS2 Stream 1 tests — Sensor Stack v2 Stage-A scaffolding.

The TGE-blocker-clearance phase per the approved plan. This stream ships
ONLY the foundation: probe-type registration + analyzer entry point.
Feature schema is deliberately DEFERRED to Stream 2 (post-Stage-A capture)
per the canonical anchor's empirical-first discipline.

T-PHASE243-1  trigger_force_curve registered in STRUCTURED_PROBE_TYPES
T-PHASE243-2  insert_separation_defensibility_log accepts the new probe type (Phase 151 P0)
T-PHASE243-3  _detect_session_type returns 'trigger_force_curve' for matching prefix
T-PHASE243-4  _extract_trigger_force_features_from_file returns None (scaffolding stub)
T-PHASE243-5  run_analysis_trigger_force_curve returns status=no_data on empty corpus
T-PHASE243-6  TRIGGER_FORCE_CURVE_FEATURE_NAMES is empty in Stream 1 (schema not yet committed)
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))


# ----- T-PHASE243-1 -------------------------------------------------------

def test_t_phase243_1_probe_type_registered():
    """`trigger_force_curve` MUST be in STRUCTURED_PROBE_TYPES frozenset."""
    from vapi_bridge.store import Store
    assert "trigger_force_curve" in Store.STRUCTURED_PROBE_TYPES


# ----- T-PHASE243-2 -------------------------------------------------------

def test_t_phase243_2_defensibility_log_accepts_trigger_force_curve():
    """Phase 151 P0 — insert_separation_defensibility_log raises ValueError
    on unknown session_types. Verify the new trigger_force_curve type is
    accepted (no ValueError) so Stage-A captures can be logged."""
    from vapi_bridge.store import Store
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = Store(db_path=os.path.join(td, "test_p243.db"))
        # Should not raise on the new probe type:
        rid = store.insert_separation_defensibility_log(
            session_type="trigger_force_curve",
            n_sessions_total=0,
            n_per_player={"Player 1": 0, "Player 2": 0, "Player 3": 0},
            min_n_per_player=10,
            defensible=False,
            ratio=0.0,
            all_pairs_above_1=False,
        )
        assert rid > 0
        # Sanity: still rejects unknown types
        with pytest.raises(ValueError):
            store.insert_separation_defensibility_log(
                session_type="not_a_real_probe",
                n_sessions_total=0,
                n_per_player={},
                min_n_per_player=10,
                defensible=False,
                ratio=0.0,
                all_pairs_above_1=False,
            )


# ----- T-PHASE243-3 -------------------------------------------------------

def test_t_phase243_3_detect_session_type_prefix():
    """_detect_session_type returns 'trigger_force_curve' for sessions
    whose filename stem starts with 'trigger_force_curve_'. This is the
    capture-session routing key the operator's hardware-capture sessions
    rely on."""
    import analyze_interperson_separation as analyzer
    assert analyzer._detect_session_type("trigger_force_curve_001.json") == "trigger_force_curve"
    assert analyzer._detect_session_type("terminal_cal_P1/trigger_force_curve_2026-05-15.json") == "trigger_force_curve"
    # Negative: a different session type must NOT be misclassified.
    assert analyzer._detect_session_type("ait_001.json") == "ait"
    assert analyzer._detect_session_type("touchpad_corners_001.json") == "touchpad_corners"
    # _TERMINAL_CAL_ONLY_TYPES inclusion (fast-path skip routing).
    assert "trigger_force_curve" in analyzer._TERMINAL_CAL_ONLY_TYPES


# ----- T-PHASE243-4 -------------------------------------------------------

def test_t_phase243_4_feature_extractor_stub_returns_none():
    """Stream 1 scaffolding: _extract_trigger_force_features_from_file
    returns None for any current session (no force-curve data exists in
    current session schema). Stream 2 replaces this with real extraction
    post-Stage-A capture."""
    import analyze_interperson_separation as analyzer
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        # Synthesize a session JSON like the existing terminal-cal format.
        fpath = Path(td) / "trigger_force_curve_001.json"
        fpath.write_text(
            '{"session_name": "test", "reports": []}',
            encoding="utf-8",
        )
        result = analyzer._extract_trigger_force_features_from_file(fpath)
        assert result is None, (
            "Stream 1 stub MUST return None; Stream 2 will replace this "
            "with real extraction once Stage-A captures inform the schema"
        )


# ----- T-PHASE243-5 -------------------------------------------------------

def test_t_phase243_5_analyzer_no_data_status():
    """run_analysis_trigger_force_curve handles the no-captures-yet state
    gracefully (status=no_data, separation_ratio=0.0, never raises). This
    is the operator-facing surface a frontend/dashboard binds to during
    Stage-A capture."""
    import analyze_interperson_separation as analyzer
    result = analyzer.run_analysis_trigger_force_curve()
    assert isinstance(result, dict)
    assert result["session_type"] == "trigger_force_curve"
    # In the current repo state (no captures yet), status MUST be no_data.
    # If Stream 2 ships + captures land, the status transitions to
    # captures_present_but_schema_pending or stage_a_in_progress — this
    # test then needs updating (a deliberate forcing function).
    assert result["status"] == "no_data"
    assert result["n_sessions"] == 0
    assert result["stage_a_complete"] is False
    assert result["feature_schema_committed"] is False
    assert result["separation_ratio"] == 0.0
    assert result["all_pairs_above_1"] is False
    assert "Stage-A target" in result["note"]


# ----- T-PHASE243-6 -------------------------------------------------------

def test_t_phase243_6_feature_schema_empty_in_stream_1():
    """The FROZEN-feature-set discipline says Stage-A measurements MUST
    inform feature selection — Stream 1 deliberately ships an empty
    TRIGGER_FORCE_CURVE_FEATURE_NAMES. Stream 2 (post-Stage-A) commits
    the final set. This test pins the empty state so a future PR that
    prematurely adds features fails CI loudly, forcing the canonical-
    anchor-anchored design pass to happen explicitly."""
    import analyze_interperson_separation as analyzer
    assert analyzer.TRIGGER_FORCE_CURVE_FEATURE_NAMES == [], (
        "Stream 1 ships an empty feature set by design — Stage-A captures "
        "inform feature selection per the canonical anchor's empirical-"
        "first discipline. If Stream 2 has shipped, update this test."
    )
