"""Phase 185 SDK tests — ReEnrollmentAttestationAgent (WIF-032 W1 closure).

4 tests:
  T185-SDK-1  ReEnrollmentAttestationResult has 6 slots; active=False default; error=None default
  T185-SDK-2  VAPIReEnrollmentAttestation.get_status accepts player_id keyword in signature
  T185-SDK-3  get_status populates result fields correctly from mock body
  T185-SDK-4  Error path returns safe defaults (active=False, empty hash, error set)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T185-SDK-1  ReEnrollmentAttestationResult: 6 slots, active=False default, error=None
# ---------------------------------------------------------------------------

def test_t185_sdk_1_result_slots_and_defaults():
    from vapi_sdk import ReEnrollmentAttestationResult

    # Confirm 6 slots
    assert len(ReEnrollmentAttestationResult.__slots__) == 6, \
        f"Expected 6 slots; got {len(ReEnrollmentAttestationResult.__slots__)}"

    # Instantiate with required fields only
    r = ReEnrollmentAttestationResult(
        attestation_hash="hmac:abc",
        player_id="P1",
        issued_at=1000.0,
        expires_at=2000.0,
        active=False,
    )
    assert r.error is None
    assert r.active is False
    assert r.attestation_hash == "hmac:abc"


# ---------------------------------------------------------------------------
# T185-SDK-2  VAPIReEnrollmentAttestation.get_status signature has player_id kwarg
# ---------------------------------------------------------------------------

def test_t185_sdk_2_get_status_signature():
    import inspect
    from vapi_sdk import VAPIReEnrollmentAttestation

    sig = inspect.signature(VAPIReEnrollmentAttestation.get_status)
    assert "player_id" in sig.parameters, \
        f"player_id not in get_status signature; params={list(sig.parameters)}"


# ---------------------------------------------------------------------------
# T185-SDK-3  get_status populates fields from body correctly
# ---------------------------------------------------------------------------

def test_t185_sdk_3_get_status_populates_from_body():
    import json
    from unittest.mock import patch, MagicMock
    from vapi_sdk import VAPIReEnrollmentAttestation, ReEnrollmentAttestationResult

    mock_body = {
        "reauth_attestation_enabled": True,
        "player_id":        "P1",
        "attestation_hash": "hmac:deadbeefcafe1234",
        "issued_at":        1744200000.0,
        "expires_at":       1744804800.0,
        "active":           True,
        "hmac_mode":        True,
        "timestamp":        1744200001.0,
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIReEnrollmentAttestation("http://localhost:8080", "test-key")
        result = client.get_status(player_id="P1")

    assert isinstance(result, ReEnrollmentAttestationResult)
    assert result.player_id        == "P1"
    assert result.attestation_hash == "hmac:deadbeefcafe1234"
    assert result.issued_at        == 1744200000.0
    assert result.expires_at       == 1744804800.0
    assert result.active           is True
    assert result.error            is None


# ---------------------------------------------------------------------------
# T185-SDK-4  Error path returns safe defaults: active=False, empty hash, error set
# ---------------------------------------------------------------------------

def test_t185_sdk_4_error_path_safe_defaults():
    from unittest.mock import patch
    from vapi_sdk import VAPIReEnrollmentAttestation, ReEnrollmentAttestationResult

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("no bridge")):
        client = VAPIReEnrollmentAttestation("http://localhost:9999", "key")
        result = client.get_status(player_id="P1")

    assert isinstance(result, ReEnrollmentAttestationResult)
    assert result.active           is False
    assert result.attestation_hash == ""
    assert result.player_id        == "P1"
    assert result.error is not None
    assert "no bridge" in result.error or "Connection" in result.error
