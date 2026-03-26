"""Phase 96 SDK tests — EnforcementReadinessCertificate + VAPITournamentGate methods.

Tests:
  test_1  EnforcementReadinessCertificate defaults (has_certificate=False, audit_valid=False)
  test_2  create_enforcement_certificate() parses POST response into ERC
  test_3  get_enforcement_certificate() parses GET response into ERC
  test_4  Bad URL never raises — returns ERC with error field set

SDK count: 77 → 81 (+4)
"""
import json
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from sdk.vapi_sdk import VAPITournamentGate, EnforcementReadinessCertificate


def test_1_erc_defaults():
    """EnforcementReadinessCertificate has correct default field values."""
    erc = EnforcementReadinessCertificate()
    assert erc.cert_id is None
    assert erc.audit_hash == ""
    assert erc.hmac_sig == ""
    assert erc.audit_valid is False
    assert erc.gate_attestation_count == 0
    assert erc.has_certificate is False
    assert erc.is_expired is False
    assert erc.error is None


def test_2_create_enforcement_certificate_parses_response():
    """create_enforcement_certificate() parses POST response into ERC."""
    payload = {
        "cert_id": 1,
        "audit_hash": "abc123def456",
        "hmac_sig": "sig_value_here",
        "audit_valid": True,
        "issued_at": 1000000.0,
        "expires_at": 1086400.0,
    }
    body = json.dumps(payload).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    gate = VAPITournamentGate(base_url="http://localhost:8000", api_key="test-key")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        erc = gate.create_enforcement_certificate()

    assert isinstance(erc, EnforcementReadinessCertificate)
    assert erc.audit_valid is True
    assert erc.audit_hash == "abc123def456"
    assert erc.hmac_sig == "sig_value_here"
    assert erc.issued_at == 1000000.0
    assert erc.expires_at == 1086400.0
    assert erc.has_certificate is True
    assert erc.error is None


def test_3_get_enforcement_certificate_parses_response():
    """get_enforcement_certificate() parses GET response into ERC."""
    payload = {
        "has_certificate": True,
        "is_expired": False,
        "certificate": {
            "id": 1,
            "audit_hash": "deadbeef",
            "hmac_sig": "hmac123",
            "audit_valid": 1,
            "gate_attestation_count": 3,
            "created_at": 1000000.0,
            "expires_at": 1086400.0,
        },
        "timestamp": 1001000.0,
    }
    body = json.dumps(payload).encode()

    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    gate = VAPITournamentGate(base_url="http://localhost:8000", api_key="test-key")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        erc = gate.get_enforcement_certificate()

    assert isinstance(erc, EnforcementReadinessCertificate)
    assert erc.has_certificate is True
    assert erc.is_expired is False
    assert erc.audit_hash == "deadbeef"
    assert erc.gate_attestation_count == 3
    assert erc.error is None


def test_4_bad_url_never_raises():
    """create_enforcement_certificate() and get_enforcement_certificate() never raise."""
    gate = VAPITournamentGate(base_url="http://127.0.0.1:1", api_key="test-key")

    erc_create = gate.create_enforcement_certificate()
    assert isinstance(erc_create, EnforcementReadinessCertificate)
    assert erc_create.audit_valid is False
    assert erc_create.error is not None

    erc_get = gate.get_enforcement_certificate()
    assert isinstance(erc_get, EnforcementReadinessCertificate)
    assert erc_get.has_certificate is False
    assert erc_get.error is not None
