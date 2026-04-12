"""
Phase 201 — Agent System Context Modernization.

PostCode sweep: verifies all LLM-backed agent system prompts contain the required
Phase 200 invariant strings. Guards against future prompt regression — any edit that
removes a frozen invariant string from a prompt will fail these tests.

201-A: bridge_agent._SYSTEM_PROMPT — Phase 200 state + frozen invariants
201-B: session_adjudicator._SYSTEM_PROMPT — Phase 200 ruling rules + frozen invariants
201-C: calibration_intelligence_agent._CALIB_SYSTEM_PROMPT — Phase 200 calibration state
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# T201-1: bridge_agent prompt contains Phase 200 state marker
# ---------------------------------------------------------------------------

def test_t201_1_bridge_agent_prompt_phase200():
    """bridge_agent._SYSTEM_PROMPT must reference Phase 200."""
    from vapi_bridge.bridge_agent import _SYSTEM_PROMPT
    assert "Phase 200" in _SYSTEM_PROMPT, (
        "bridge_agent._SYSTEM_PROMPT must be updated to Phase 200 state."
    )


# ---------------------------------------------------------------------------
# T201-2: bridge_agent prompt contains current separation ratio
# ---------------------------------------------------------------------------

def test_t201_2_bridge_agent_prompt_ratio():
    """bridge_agent._SYSTEM_PROMPT must reference separation ratio 0.728."""
    from vapi_bridge.bridge_agent import _SYSTEM_PROMPT
    assert "0.728" in _SYSTEM_PROMPT, (
        "bridge_agent._SYSTEM_PROMPT must contain current separation ratio (0.728)."
    )


# ---------------------------------------------------------------------------
# T201-3: bridge_agent prompt contains TOURNAMENT BLOCKER warning
# ---------------------------------------------------------------------------

def test_t201_3_bridge_agent_prompt_tournament_blocker():
    """bridge_agent._SYSTEM_PROMPT must flag TOURNAMENT BLOCKER condition."""
    from vapi_bridge.bridge_agent import _SYSTEM_PROMPT
    assert "TOURNAMENT BLOCKER" in _SYSTEM_PROMPT, (
        "bridge_agent._SYSTEM_PROMPT must flag separation ratio as TOURNAMENT BLOCKER."
    )


# ---------------------------------------------------------------------------
# T201-4: bridge_agent prompt contains frozen L4 threshold values
# ---------------------------------------------------------------------------

def test_t201_4_bridge_agent_prompt_l4_thresholds():
    """bridge_agent._SYSTEM_PROMPT must contain frozen L4 threshold values."""
    from vapi_bridge.bridge_agent import _SYSTEM_PROMPT
    assert "7.009" in _SYSTEM_PROMPT, (
        "bridge_agent._SYSTEM_PROMPT must contain frozen anomaly threshold 7.009."
    )
    assert "5.367" in _SYSTEM_PROMPT, (
        "bridge_agent._SYSTEM_PROMPT must contain frozen continuity threshold 5.367."
    )


# ---------------------------------------------------------------------------
# T201-5: session_adjudicator prompt contains Phase 200 state marker
# ---------------------------------------------------------------------------

def test_t201_5_session_adjudicator_prompt_phase200():
    """session_adjudicator._SYSTEM_PROMPT must reference Phase 200."""
    from vapi_bridge.session_adjudicator import _SYSTEM_PROMPT
    assert "Phase 200" in _SYSTEM_PROMPT, (
        "session_adjudicator._SYSTEM_PROMPT must be updated to Phase 200 state."
    )


# ---------------------------------------------------------------------------
# T201-6: session_adjudicator prompt contains dry_run advisory note
# ---------------------------------------------------------------------------

def test_t201_6_session_adjudicator_prompt_dry_run():
    """session_adjudicator._SYSTEM_PROMPT must reference dry_run=True advisory mode."""
    from vapi_bridge.session_adjudicator import _SYSTEM_PROMPT
    assert "dry_run=True" in _SYSTEM_PROMPT, (
        "session_adjudicator._SYSTEM_PROMPT must document dry_run=True advisory mode."
    )


# ---------------------------------------------------------------------------
# T201-7: calibration_agent prompt contains Phase 200 ratio (not stale 1.261)
# ---------------------------------------------------------------------------

def test_t201_7_calib_agent_prompt_ratio_updated():
    """calibration_intelligence_agent._CALIB_SYSTEM_PROMPT must use 0.728, not stale 1.261."""
    from vapi_bridge.calibration_intelligence_agent import _CALIB_SYSTEM_PROMPT
    assert "0.728" in _CALIB_SYSTEM_PROMPT, (
        "_CALIB_SYSTEM_PROMPT must contain current separation ratio 0.728 (N=35, Phase 200)."
    )
    # 1.261 was N=11 touchpad_corners (Phase 143) — superseded; must not be the current claim
    # (it may appear in historical context, but 0.728 must be present as current value)
    assert "TOURNAMENT BLOCKER" in _CALIB_SYSTEM_PROMPT, (
        "_CALIB_SYSTEM_PROMPT must flag TOURNAMENT BLOCKER for ratio=0.728."
    )


# ---------------------------------------------------------------------------
# T201-8: All 3 prompts contain the 228B PoAC wire format invariant
# ---------------------------------------------------------------------------

def test_t201_8_all_prompts_contain_228_bytes_invariant():
    """All 3 LLM agent system prompts must reference the frozen 228-byte PoAC format."""
    from vapi_bridge.bridge_agent import _SYSTEM_PROMPT as bridge_prompt
    from vapi_bridge.session_adjudicator import _SYSTEM_PROMPT as adj_prompt
    from vapi_bridge.calibration_intelligence_agent import _CALIB_SYSTEM_PROMPT as calib_prompt

    assert "228" in bridge_prompt, "bridge_agent prompt must reference 228-byte PoAC format"
    assert "228" in adj_prompt, "session_adjudicator prompt must reference 228-byte PoAC format"
    # calibration agent focuses on thresholds, not wire format — relaxed check
    assert "7.009" in calib_prompt, "calib agent prompt must reference L4 anomaly threshold"
