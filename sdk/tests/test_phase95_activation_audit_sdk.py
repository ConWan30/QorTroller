"""Phase 95 SDK tests — ActivationAuditResult + VAPITournamentGate.verify_activation_audit()

Tests:
  test_1  ActivationAuditResult defaults (audit_valid=False, all fields present)
  test_2  verify_activation_audit parses valid JSON response into ActivationAuditResult
  test_3  verify_activation_audit returns error result on bad URL (never raises)
  test_4  audit_valid=True propagated correctly from mocked response

SDK count: 73 → 77 (+4)
"""
import json
import sys
import os
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from sdk.vapi_sdk import VAPITournamentGate, ActivationAuditResult


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_1_activation_audit_result_defaults():
    """ActivationAuditResult has correct default field values."""
    r = ActivationAuditResult()
    assert r.audit_valid is False
    assert r.first_ready_check_at is None
    assert r.gate_attestation_count == 0
    assert r.latest_attestation_at is None
    assert r.audit_summary == ""
    assert r.error is None


def test_2_verify_activation_audit_parses_response():
    """verify_activation_audit() parses a valid JSON response into ActivationAuditResult."""
    payload = {
        "audit_valid": True,
        "first_ready_check_at": 1000000.0,
        "gate_attestation_count": 3,
        "latest_attestation_at": 1000500.0,
        "audit_summary": "VALID: Chronological sequence confirmed.",
        "timestamp": 1001000.0,
    }
    body = json.dumps(payload).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    gate = VAPITournamentGate(base_url="http://localhost:8000", api_key="test-key")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = gate.verify_activation_audit()

    assert isinstance(result, ActivationAuditResult)
    assert result.audit_valid is True
    assert result.gate_attestation_count == 3
    assert result.first_ready_check_at == 1000000.0
    assert result.latest_attestation_at == 1000500.0
    assert "Chronological sequence confirmed" in result.audit_summary
    assert result.error is None


def test_3_verify_activation_audit_bad_url_never_raises():
    """verify_activation_audit() returns error ActivationAuditResult on connection failure."""
    gate = VAPITournamentGate(base_url="http://127.0.0.1:1", api_key="test-key")
    result = gate.verify_activation_audit()
    assert isinstance(result, ActivationAuditResult)
    assert result.audit_valid is False
    assert result.error is not None
    assert len(result.error) > 0


def test_4_audit_valid_false_propagated():
    """audit_valid=False from server response propagated correctly."""
    payload = {
        "audit_valid": False,
        "first_ready_check_at": None,
        "gate_attestation_count": 0,
        "latest_attestation_at": None,
        "audit_summary": "NOT VALID: No ready_for_live_mode=True entry in activation log yet.",
        "timestamp": 1001000.0,
    }
    body = json.dumps(payload).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    gate = VAPITournamentGate(base_url="http://localhost:8000", api_key="test-key")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = gate.verify_activation_audit()

    assert result.audit_valid is False
    assert result.gate_attestation_count == 0
    assert result.first_ready_check_at is None
    assert result.error is None
