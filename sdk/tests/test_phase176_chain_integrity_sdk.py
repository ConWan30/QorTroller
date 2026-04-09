"""Phase 176 SDK tests — PoACChainIntegrityResult + VAPIPoACChainIntegrity.

4 tests:
  T176-SDK-1  PoACChainIntegrityResult has expected slots
  T176-SDK-2  Default error is None
  T176-SDK-3  VAPIPoACChainIntegrity.get_status() populates all fields from body
  T176-SDK-4  Error path returns audit_passed=True (fail-open) with error set
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))

import pytest


# ---------------------------------------------------------------------------
# T176-SDK-1  Result has expected slots
# ---------------------------------------------------------------------------

def test_t176_sdk_1_result_has_expected_slots():
    from vapi_sdk import PoACChainIntegrityResult
    r = PoACChainIntegrityResult(
        chain_integrity_enabled = True,
        total_records   = 50,
        valid_links     = 47,
        broken_links    = 3,
        integrity_score = 0.94,
        audit_passed    = False,
    )
    assert r.chain_integrity_enabled is True
    assert r.total_records == 50
    assert r.valid_links == 47
    assert r.broken_links == 3
    assert abs(r.integrity_score - 0.94) < 1e-9
    assert r.audit_passed is False
    assert r.error is None


# ---------------------------------------------------------------------------
# T176-SDK-2  Default error is None
# ---------------------------------------------------------------------------

def test_t176_sdk_2_default_error_none():
    from vapi_sdk import PoACChainIntegrityResult
    r = PoACChainIntegrityResult(
        chain_integrity_enabled = True,
        total_records   = 100,
        valid_links     = 100,
        broken_links    = 0,
        integrity_score = 1.0,
        audit_passed    = True,
    )
    assert r.error is None


# ---------------------------------------------------------------------------
# T176-SDK-3  get_status() populates all fields from API body
# ---------------------------------------------------------------------------

def test_t176_sdk_3_get_status_populates_from_body():
    from vapi_sdk import VAPIPoACChainIntegrity

    mock_body = {
        "chain_integrity_enabled": True,
        "device_id":       "dev_abc",
        "total_records":   50,
        "valid_links":     47,
        "broken_links":    3,
        "integrity_score": 0.94,
        "audit_passed":    False,
        "timestamp":       1234567890.0,
    }

    class _FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return json.dumps(mock_body).encode()

    with patch("urllib.request.urlopen", return_value=_FakeResp()):
        client = VAPIPoACChainIntegrity("http://localhost:8080", "k")
        result = client.get_status()

    assert result.chain_integrity_enabled is True
    assert result.total_records == 50
    assert result.broken_links == 3
    assert abs(result.integrity_score - 0.94) < 1e-9
    assert result.audit_passed is False
    assert result.error is None


# ---------------------------------------------------------------------------
# T176-SDK-4  Error path returns audit_passed=True (fail-open)
# ---------------------------------------------------------------------------

def test_t176_sdk_4_error_path_fail_open():
    from vapi_sdk import VAPIPoACChainIntegrity

    with patch("urllib.request.urlopen", side_effect=Exception("conn refused")):
        client = VAPIPoACChainIntegrity("http://localhost:8080", "k")
        result = client.get_status()

    assert result.error is not None
    assert "conn refused" in result.error
    # Fail-open: chain audit failure must not block tournament gate
    assert result.audit_passed is True
    assert abs(result.integrity_score - 1.0) < 1e-9
    assert result.broken_links == 0
