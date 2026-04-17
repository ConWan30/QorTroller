"""
Phase 202 + 203 SDK Tests
T202-SDK-1..6: TremorConvergenceResult / VAPITremorConvergence (T202-SDK-5/6 Phase 206)
T203-SDK-1..4: AgentContextIntegrityResult / VAPIAgentContextIntegrity
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# Phase 202 SDK tests
# ---------------------------------------------------------------------------

def test_T202_sdk_1_dataclass_fields():
    """TremorConvergenceResult has required slots."""
    from vapi_sdk import TremorConvergenceResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(TremorConvergenceResult)}
    assert "tremor_convergence_enabled"  in fields
    assert "convergence_stable"          in fields
    assert "velocity"                    in fields
    assert "ratio"                       in fields
    assert "consecutive_positive"        in fields
    assert "sessions_to_target_estimate" in fields
    assert "error"                       in fields


def test_T202_sdk_2_result_instantiation_stable():
    """TremorConvergenceResult can be created with stable=True."""
    from vapi_sdk import TremorConvergenceResult
    r = TremorConvergenceResult(
        tremor_convergence_enabled  = True,
        convergence_stable          = True,
        velocity                    = 0.033,
        ratio                       = 1.05,
        consecutive_positive        = 2,
        sessions_to_target_estimate = 0,
    )
    assert r.convergence_stable is True
    assert r.velocity > 0
    assert r.ratio > 1.0
    assert r.error is None


def test_T202_sdk_3_result_instantiation_declining():
    """TremorConvergenceResult correctly represents declining velocity."""
    from vapi_sdk import TremorConvergenceResult
    r = TremorConvergenceResult(
        tremor_convergence_enabled  = True,
        convergence_stable          = False,
        velocity                    = -0.099,
        ratio                       = 0.80,
        consecutive_positive        = 0,
        sessions_to_target_estimate = 5,
    )
    assert r.convergence_stable is False
    assert r.velocity < 0
    assert r.consecutive_positive == 0


def test_T202_sdk_4_client_network_error():
    """VAPITremorConvergence returns TremorConvergenceResult with error on failure."""
    from vapi_sdk import VAPITremorConvergence, TremorConvergenceResult
    client = VAPITremorConvergence("http://localhost:19999", api_key="test")
    result = client.get_status()
    assert isinstance(result, TremorConvergenceResult)
    assert result.error is not None
    assert result.convergence_stable is None


# ---------------------------------------------------------------------------
# Phase 206 SDK tests (TremorConvergenceResult non-convergence fields)
# ---------------------------------------------------------------------------

def test_T202_sdk_5_non_convergence_detected_field_present():
    """Phase 206: TremorConvergenceResult has non_convergence_detected and consecutive_negative slots."""
    from vapi_sdk import TremorConvergenceResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(TremorConvergenceResult)}
    assert "non_convergence_detected" in fields, (
        "TremorConvergenceResult missing non_convergence_detected slot (Phase 206)"
    )
    assert "consecutive_negative" in fields, (
        "TremorConvergenceResult missing consecutive_negative slot (Phase 206)"
    )
    # Verify defaults
    r = TremorConvergenceResult(
        tremor_convergence_enabled  = False,
        convergence_stable          = None,
        velocity                    = None,
        ratio                       = None,
        consecutive_positive        = 0,
        sessions_to_target_estimate = 0,
    )
    assert r.non_convergence_detected is False
    assert r.consecutive_negative == 0


def test_T202_sdk_6_non_convergence_detected_parses_from_response():
    """Phase 206: VAPITremorConvergence.get_status() parses non_convergence_detected
    and consecutive_negative from a 200 response body."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPITremorConvergence, TremorConvergenceResult

    body = json.dumps({
        "tremor_convergence_enabled": True,
        "convergence_stable":         False,
        "velocity":                   -0.04,
        "ratio":                      0.72,
        "consecutive_positive":       0,
        "sessions_to_target_estimate": 8,
        "non_convergence_detected":   True,
        "consecutive_negative":       5,
        "timestamp":                  1712200000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPITremorConvergence("http://localhost:8080", "test-key")
        result = client.get_status()

    assert result.error is None
    assert result.non_convergence_detected is True, (
        f"Expected non_convergence_detected=True; got {result.non_convergence_detected}"
    )
    assert result.consecutive_negative == 5, (
        f"Expected consecutive_negative=5; got {result.consecutive_negative}"
    )
    assert result.convergence_stable is False
    assert result.velocity == pytest.approx(-0.04)


# ---------------------------------------------------------------------------
# Phase 203 SDK tests
# ---------------------------------------------------------------------------

def test_T203_sdk_1_dataclass_fields():
    """AgentContextIntegrityResult has required slots."""
    from vapi_sdk import AgentContextIntegrityResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(AgentContextIntegrityResult)}
    assert "agent_context_on_chain_enabled" in fields
    assert "all_registered"                 in fields
    assert "agents"                         in fields
    assert "error"                          in fields


def test_T203_sdk_2_result_instantiation_all_registered():
    """AgentContextIntegrityResult with all_registered=True."""
    from vapi_sdk import AgentContextIntegrityResult
    agents = [
        {"agent_id": "bridge_agent",                  "registered": True, "prompt_sha256": "abc", "phase_number": 203},
        {"agent_id": "session_adjudicator",            "registered": True, "prompt_sha256": "def", "phase_number": 203},
        {"agent_id": "calibration_intelligence_agent", "registered": True, "prompt_sha256": "ghi", "phase_number": 203},
    ]
    r = AgentContextIntegrityResult(
        agent_context_on_chain_enabled = False,
        all_registered                 = True,
        agents                         = agents,
    )
    assert r.all_registered is True
    assert len(r.agents) == 3
    assert r.error is None


def test_T203_sdk_3_result_instantiation_not_registered():
    """AgentContextIntegrityResult correctly represents missing registrations."""
    from vapi_sdk import AgentContextIntegrityResult
    agents = [
        {"agent_id": "bridge_agent",       "registered": False, "prompt_sha256": None},
        {"agent_id": "session_adjudicator", "registered": False, "prompt_sha256": None},
    ]
    r = AgentContextIntegrityResult(
        agent_context_on_chain_enabled = False,
        all_registered                 = False,
        agents                         = agents,
    )
    assert r.all_registered is False
    assert all(not a["registered"] for a in r.agents)


def test_T203_sdk_4_client_network_error():
    """VAPIAgentContextIntegrity returns AgentContextIntegrityResult with error on failure."""
    from vapi_sdk import VAPIAgentContextIntegrity, AgentContextIntegrityResult
    client = VAPIAgentContextIntegrity("http://localhost:19999", api_key="test")
    result = client.get_all_status()
    assert isinstance(result, AgentContextIntegrityResult)
    assert result.error is not None
    assert result.all_registered is False
    assert result.agents == []
