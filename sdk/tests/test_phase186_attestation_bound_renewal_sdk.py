"""Phase 186 SDK tests — AttestationBoundRenewalAgent (WIF-032 W2 closure).

4 tests:
  T186-SDK-1  AttestationBoundRenewalResult has 6 slots; enabled=False/renewal_approved=False
              defaults; error=None default
  T186-SDK-2  VAPIAttestationBoundRenewal.get_status signature has player_id kwarg
  T186-SDK-3  get_status populates result fields correctly from mock response body
  T186-SDK-4  Error path returns safe defaults (enabled=False, empty hash, error set)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T186-SDK-1  6 slots; enabled=False default; error=None default
# ---------------------------------------------------------------------------

def test_t186_sdk_1_result_slots_and_defaults():
    from vapi_sdk import AttestationBoundRenewalResult

    assert len(AttestationBoundRenewalResult.__slots__) == 6, \
        f"Expected 6 slots; got {len(AttestationBoundRenewalResult.__slots__)}"

    r = AttestationBoundRenewalResult(
        attestation_bound_renewal_enabled=False,
        attestation_hash="",
        renewal_approved=False,
        denial_reason="",
        total_blocked=0,
    )
    assert r.error is None
    assert r.attestation_bound_renewal_enabled is False
    assert r.renewal_approved is False
    assert r.total_blocked == 0


# ---------------------------------------------------------------------------
# T186-SDK-2  VAPIAttestationBoundRenewal.get_status signature has player_id kwarg
# ---------------------------------------------------------------------------

def test_t186_sdk_2_get_status_signature():
    import inspect
    from vapi_sdk import VAPIAttestationBoundRenewal

    sig = inspect.signature(VAPIAttestationBoundRenewal.get_status)
    assert "player_id" in sig.parameters, \
        f"player_id not in get_status signature; params={list(sig.parameters)}"


# ---------------------------------------------------------------------------
# T186-SDK-3  get_status populates fields from body correctly
# ---------------------------------------------------------------------------

def test_t186_sdk_3_get_status_populates_from_body():
    import json
    from unittest.mock import patch, MagicMock
    from vapi_sdk import VAPIAttestationBoundRenewal, AttestationBoundRenewalResult

    mock_body = {
        "attestation_bound_renewal_enabled": True,
        "player_id":                "P1",
        "latest_attestation_hash":  "hmac:abcdef1234567890",
        "latest_renewal_approved":  True,
        "denial_reason":            "",
        "total_approved":           3,
        "total_blocked":            1,
        "timestamp":                1744200001.0,
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIAttestationBoundRenewal("http://localhost:8080", "test-key")
        result = client.get_status(player_id="P1")

    assert isinstance(result, AttestationBoundRenewalResult)
    assert result.attestation_bound_renewal_enabled is True
    assert result.attestation_hash   == "hmac:abcdef1234567890"
    assert result.renewal_approved   is True
    assert result.denial_reason      == ""
    assert result.total_blocked      == 1
    assert result.error              is None


# ---------------------------------------------------------------------------
# T186-SDK-4  Error path returns safe defaults (enabled=False, empty hash, error set)
# ---------------------------------------------------------------------------

def test_t186_sdk_4_error_path_safe_defaults():
    from unittest.mock import patch
    from vapi_sdk import VAPIAttestationBoundRenewal, AttestationBoundRenewalResult

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("no bridge")):
        client = VAPIAttestationBoundRenewal("http://localhost:9999", "key")
        result = client.get_status(player_id="P1")

    assert isinstance(result, AttestationBoundRenewalResult)
    assert result.attestation_bound_renewal_enabled is False
    assert result.attestation_hash   == ""
    assert result.renewal_approved   is False
    assert result.total_blocked      == 0
    assert result.error is not None
    assert "no bridge" in result.error or "Connection" in result.error
