"""Phase 181 SDK tests — Consent-Bound Renewal Provenance (WIF-031 W1 mitigation).

4 tests:
  T181-SDK-1  BiometricRenewalResult has corpus_delta_detected slot; default False
  T181-SDK-2  corpus_delta_detected=True populated from response body
  T181-SDK-3  error path returns corpus_delta_detected=False (fail-safe)
  T181-SDK-4  VAPICeremonyAuditGate accepts ceremony_audit_registry_address kwarg
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T181-SDK-1  BiometricRenewalResult has corpus_delta_detected slot; default False
# ---------------------------------------------------------------------------

def test_t181_sdk_1_biometric_renewal_result_has_corpus_delta_slot():
    from vapi_sdk import BiometricRenewalResult
    r = BiometricRenewalResult(
        renewal_enabled=False,
        prev_commit_hash="",
        new_commit_hash="",
        ttl_days=90.0,
        dry_run=True,
        total_renewals=0,
    )
    assert hasattr(r, "corpus_delta_detected")
    assert r.corpus_delta_detected is False


# ---------------------------------------------------------------------------
# T181-SDK-2  corpus_delta_detected=True populated from response body
# ---------------------------------------------------------------------------

def test_t181_sdk_2_corpus_delta_populated_true():
    from unittest.mock import patch, MagicMock
    import json as _j
    from vapi_sdk import VAPIBiometricRenewal, BiometricRenewalResult

    body = {
        "renewal_enabled": True,
        "prev_commit_hash": "sha256:prev",
        "new_commit_hash": "sha256:new",
        "ttl_days": 90.0,
        "dry_run": False,
        "total_renewals": 2,
        "corpus_delta_detected": True,
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = _j.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        br = VAPIBiometricRenewal("http://localhost:8080", "test-key")
        result = br.get_status()

    assert isinstance(result, BiometricRenewalResult)
    assert result.corpus_delta_detected is True
    assert result.total_renewals == 2
    assert result.error is None


# ---------------------------------------------------------------------------
# T181-SDK-3  error path returns corpus_delta_detected=False (fail-safe)
# ---------------------------------------------------------------------------

def test_t181_sdk_3_error_path_corpus_delta_false():
    from unittest.mock import patch
    from vapi_sdk import VAPIBiometricRenewal

    with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        br = VAPIBiometricRenewal("http://localhost:8080", "test-key")
        result = br.get_status()

    assert result.corpus_delta_detected is False
    assert result.error is not None
    assert "connection refused" in result.error


# ---------------------------------------------------------------------------
# T181-SDK-4  VAPICeremonyAuditGate accepts ceremony_audit_registry_address kwarg
# ---------------------------------------------------------------------------

def test_t181_sdk_4_ceremony_audit_gate_registry_address():
    from vapi_sdk import VAPICeremonyAuditGate
    ca = VAPICeremonyAuditGate(
        "http://localhost:8080",
        "test-key",
        ceremony_audit_registry_address="0xDeadBeef",
    )
    assert ca.ceremony_audit_registry_address == "0xDeadBeef"

    # default is empty string
    ca2 = VAPICeremonyAuditGate("http://localhost:8080", "test-key")
    assert ca2.ceremony_audit_registry_address == ""
