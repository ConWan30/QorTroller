"""Phase 179 SDK tests — CeremonyAuditResult + VAPICeremonyAudit.

4 tests:
  T179-SDK-1  CeremonyAuditResult has expected 6 slots + error
  T179-SDK-2  Default error is None; audit_passed defaults to True
  T179-SDK-3  VAPICeremonyAudit.get_status() populates all fields from body
  T179-SDK-4  Error path returns audit_passed=True with error set (fail-open)
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T179-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t179_sdk_1_result_has_expected_slots():
    from vapi_sdk import CeremonyAuditGateResult
    r = CeremonyAuditGateResult(
        ceremony_audit_enabled = False,
        total_entries          = 9,
        distinct_participants  = 3,
        circuits_audited       = 3,
        min_participants       = 3,
        audit_passed           = True,
    )
    assert r.ceremony_audit_enabled is False
    assert r.total_entries == 9
    assert r.distinct_participants == 3
    assert r.circuits_audited == 3
    assert r.min_participants == 3
    assert r.audit_passed is True
    assert r.error is None


# ---------------------------------------------------------------------------
# T179-SDK-2  Default error is None; audit_passed=True by default
# ---------------------------------------------------------------------------

def test_t179_sdk_2_default_error_none():
    from vapi_sdk import CeremonyAuditGateResult
    r = CeremonyAuditGateResult(
        ceremony_audit_enabled = False,
        total_entries          = 0,
        distinct_participants  = 0,
        circuits_audited       = 0,
        min_participants       = 3,
        audit_passed           = True,
    )
    assert r.error is None
    assert r.audit_passed is True


# ---------------------------------------------------------------------------
# T179-SDK-3  get_status() populates all fields from API body
# ---------------------------------------------------------------------------

def test_t179_sdk_3_get_status_populates_from_body():
    from vapi_sdk import VAPICeremonyAuditGate as VAPICeremonyAudit

    mock_body = {
        "ceremony_audit_enabled": True,
        "total_entries":          9,
        "distinct_participants":  3,
        "circuits_audited":       3,
        "min_participants":       3,
        "audit_passed":           True,
        "timestamp":              1744567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPICeremonyAudit("http://localhost:8080", "k")
        result = client.get_status()

    assert result.ceremony_audit_enabled is True
    assert result.total_entries == 9
    assert result.distinct_participants == 3
    assert result.circuits_audited == 3
    assert result.min_participants == 3
    assert result.audit_passed is True
    assert result.error is None


# ---------------------------------------------------------------------------
# T179-SDK-4  Error path returns audit_passed=True with error set (fail-open)
# ---------------------------------------------------------------------------

def test_t179_sdk_4_error_path_fail_open():
    from vapi_sdk import VAPICeremonyAuditGate as VAPICeremonyAudit

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPICeremonyAudit("http://localhost:8080", "k")
        result = client.get_status()

    assert result.error is not None
    assert "conn refused" in result.error
    # Fail-open: audit error must NOT block tournament gate
    assert result.audit_passed is True
    assert result.ceremony_audit_enabled is False
    assert result.min_participants == 3
