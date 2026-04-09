"""Phase 178 SDK tests — BiometricCredentialAgeResult + VAPIBiometricCredentialTTL.

4 tests:
  T178-SDK-1  BiometricCredentialAgeResult has expected 7 slots + error
  T178-SDK-2  Default error is None; ttl_expired defaults to False
  T178-SDK-3  VAPIBiometricCredentialTTL.get_status() populates all fields from body
  T178-SDK-4  Error path returns ttl_expired=False with error set (fail-open)
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

import pytest


# ---------------------------------------------------------------------------
# T178-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t178_sdk_1_result_has_expected_slots():
    from vapi_sdk import BiometricCredentialAgeResult
    r = BiometricCredentialAgeResult(
        ttl_enabled            = True,
        commit_hash            = "sha256:abc123",
        commit_ts              = 1744000000.0,
        age_days               = 6.3,
        ttl_days               = 90.0,
        ttl_expired            = False,
        recalibration_required = False,
    )
    assert r.ttl_enabled is True
    assert r.commit_hash == "sha256:abc123"
    assert abs(r.commit_ts - 1744000000.0) < 1e-3
    assert abs(r.age_days - 6.3) < 1e-9
    assert abs(r.ttl_days - 90.0) < 1e-9
    assert r.ttl_expired is False
    assert r.recalibration_required is False
    assert r.error is None


# ---------------------------------------------------------------------------
# T178-SDK-2  Default error is None; ttl_expired defaults to False
# ---------------------------------------------------------------------------

def test_t178_sdk_2_default_error_none():
    from vapi_sdk import BiometricCredentialAgeResult
    r = BiometricCredentialAgeResult(
        ttl_enabled            = True,
        commit_hash            = "",
        commit_ts              = 0.0,
        age_days               = 0.0,
        ttl_days               = 90.0,
        ttl_expired            = False,
        recalibration_required = False,
    )
    assert r.error is None
    assert r.ttl_expired is False


# ---------------------------------------------------------------------------
# T178-SDK-3  get_status() populates all fields from API body
# ---------------------------------------------------------------------------

def test_t178_sdk_3_get_status_populates_from_body():
    from vapi_sdk import VAPIBiometricCredentialTTL

    mock_body = {
        "ttl_enabled":            True,
        "commit_hash":            "sha256:abc123deadbeef",
        "commit_ts":              1744000000.0,
        "age_days":               6.3,
        "ttl_days":               90.0,
        "ttl_expired":            False,
        "recalibration_required": False,
        "timestamp":              1744567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPIBiometricCredentialTTL("http://localhost:8080", "k")
        result = client.get_status()

    assert result.ttl_enabled is True
    assert result.commit_hash == "sha256:abc123deadbeef"
    assert abs(result.age_days - 6.3) < 1e-9
    assert abs(result.ttl_days - 90.0) < 1e-9
    assert result.ttl_expired is False
    assert result.recalibration_required is False
    assert result.error is None


# ---------------------------------------------------------------------------
# T178-SDK-4  Error path returns ttl_expired=False with error set (fail-open)
# ---------------------------------------------------------------------------

def test_t178_sdk_4_error_path_fail_open():
    from vapi_sdk import VAPIBiometricCredentialTTL

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPIBiometricCredentialTTL("http://localhost:8080", "k")
        result = client.get_status()

    assert result.error is not None
    assert "conn refused" in result.error
    # Fail-open: must NOT block tournament on error
    assert result.ttl_expired is False
    assert result.recalibration_required is False
    assert result.ttl_enabled is True
    assert result.ttl_days == 90.0
