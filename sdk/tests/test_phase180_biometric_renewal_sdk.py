"""Phase 180 SDK tests — BiometricRenewalResult + VAPIBiometricRenewal.

4 tests:
  T180-SDK-1  BiometricRenewalResult has expected 7 slots + error
  T180-SDK-2  Default error is None; renewal_enabled defaults to False
  T180-SDK-3  VAPIBiometricRenewal.get_status() populates all fields from body
  T180-SDK-4  Error path returns safe defaults with error set
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T180-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t180_sdk_1_result_has_expected_slots():
    from vapi_sdk import BiometricRenewalResult
    r = BiometricRenewalResult(
        renewal_enabled  = False,
        prev_commit_hash = "sha256:aabb",
        new_commit_hash  = "sha256:ccdd",
        ttl_days         = 90.0,
        dry_run          = True,
        total_renewals   = 1,
    )
    assert r.renewal_enabled is False
    assert r.prev_commit_hash == "sha256:aabb"
    assert r.new_commit_hash == "sha256:ccdd"
    assert r.ttl_days == 90.0
    assert r.dry_run is True
    assert r.total_renewals == 1
    assert r.error is None


# ---------------------------------------------------------------------------
# T180-SDK-2  Default error is None; renewal_enabled defaults to False
# ---------------------------------------------------------------------------

def test_t180_sdk_2_default_error_none():
    from vapi_sdk import BiometricRenewalResult
    r = BiometricRenewalResult(
        renewal_enabled  = False,
        prev_commit_hash = "",
        new_commit_hash  = "",
        ttl_days         = 90.0,
        dry_run          = True,
        total_renewals   = 0,
    )
    assert r.error is None
    assert r.renewal_enabled is False
    assert r.total_renewals == 0


# ---------------------------------------------------------------------------
# T180-SDK-3  VAPIBiometricRenewal.get_status() populates all fields from body
# ---------------------------------------------------------------------------

def test_t180_sdk_3_get_status_populates_from_body():
    from vapi_sdk import VAPIBiometricRenewal

    mock_body = {
        "renewal_enabled":   False,
        "total_renewals":    2,
        "latest_renewal_ts": 1744567890.0,
        "prev_commit_hash":  "sha256:aabb",
        "new_commit_hash":   "sha256:ccdd",
        "ttl_days":          90.0,
        "timestamp":         1744567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPIBiometricRenewal("http://localhost:8080", "k")
        result = client.get_status()

    assert result.renewal_enabled is False
    assert result.total_renewals == 2
    assert result.prev_commit_hash == "sha256:aabb"
    assert result.new_commit_hash == "sha256:ccdd"
    assert result.ttl_days == 90.0
    assert result.dry_run is True  # body has no dry_run key → defaults True
    assert result.error is None


# ---------------------------------------------------------------------------
# T180-SDK-4  Error path returns safe defaults with error set
# ---------------------------------------------------------------------------

def test_t180_sdk_4_error_path_returns_safe_defaults():
    from vapi_sdk import VAPIBiometricRenewal

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPIBiometricRenewal("http://localhost:8080", "k")
        result = client.get_status()

    assert result.error is not None
    assert "conn refused" in result.error
    # Error path: safe defaults — never blocks anything
    assert result.renewal_enabled is False
    assert result.total_renewals == 0
    assert result.prev_commit_hash == ""
    assert result.new_commit_hash == ""
    assert result.ttl_days == 90.0
    assert result.dry_run is True
