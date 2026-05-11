"""Phase O3-ZKBA-TRACK1 C4 — VAPIZKBA SDK tests (Stream Z6 + Z7).

T-ZKBA-14: VAPIZKBA.status fail-open when bridge unreachable
T-ZKBA-15: VAPIZKBA.get_artifact fail-open when bridge unreachable
T-ZKBA-16: VAPIZKBA.history fail-open when bridge unreachable

All three tests verify the SDK never raises on transport failure — instead
returning a Result dataclass with .error populated. This matches the
VAPIDraftReview / VAPIFleetReadinessRoot fail-open pattern.

Bridge HTTP endpoints (/operator/zkba-*) do not yet ship at C4; these
tests intentionally point at an unreachable port to exercise the
fail-open path.
"""
import os
import sys

import pytest


# Add sdk/ to sys.path
_HERE = os.path.dirname(__file__)
_SDK_DIR = os.path.normpath(os.path.join(_HERE, ".."))
if _SDK_DIR not in sys.path:
    sys.path.insert(0, _SDK_DIR)

from vapi_sdk import (  # noqa: E402
    VAPIZKBA,
    ZKBAStatusResult,
    ZKBAArtifactResult,
    ZKBAHistoryResult,
    SDK_VERSION,
)

# Deliberately-unreachable URL for fail-open verification
# (port 1 is reserved + cannot be bound, guaranteeing connection refused)
_UNREACHABLE_URL = "http://127.0.0.1:1"


# ---------------------------------------------------------------------------
# T-ZKBA-14: status fail-open
# ---------------------------------------------------------------------------

def test_t_zkba_14_sdk_vapi_zkba_status_fail_open():
    """VAPIZKBA.status() returns ZKBAStatusResult with .error populated
    when the bridge is unreachable. NEVER raises."""
    client = VAPIZKBA(_UNREACHABLE_URL, api_key="test_key")
    result = client.status()
    assert isinstance(result, ZKBAStatusResult)
    assert result.error is not None, "error field should be populated on connection failure"
    assert result.error != ""
    # Default values present
    assert result.total_artifacts == 0
    assert result.anchored_count == 0
    assert result.frozen_v1_position == 10
    assert result.domain_tag == "VAPI-ZKBA-ARTIFACT-v1"
    # No exception raised — we got here


# ---------------------------------------------------------------------------
# T-ZKBA-15: get_artifact fail-open
# ---------------------------------------------------------------------------

def test_t_zkba_15_sdk_vapi_zkba_get_artifact_fail_open():
    """VAPIZKBA.get_artifact(commitment_hex) returns ZKBAArtifactResult
    with .error populated when bridge is unreachable. NEVER raises."""
    client = VAPIZKBA(_UNREACHABLE_URL, api_key="test_key")
    result = client.get_artifact("0" * 64)
    assert isinstance(result, ZKBAArtifactResult)
    assert result.error is not None
    assert result.commitment_hex == "0" * 64
    assert result.found is False
    assert result.anchor_tx_hash is None


# ---------------------------------------------------------------------------
# T-ZKBA-16: history fail-open
# ---------------------------------------------------------------------------

def test_t_zkba_16_sdk_vapi_zkba_history_fail_open():
    """VAPIZKBA.history(limit=N) returns ZKBAHistoryResult with .error
    populated when bridge is unreachable. NEVER raises."""
    client = VAPIZKBA(_UNREACHABLE_URL, api_key="test_key")
    result = client.history(limit=10)
    assert isinstance(result, ZKBAHistoryResult)
    assert result.error is not None
    assert result.limit == 10
    assert result.row_count == 0
    assert result.rows == []


# ---------------------------------------------------------------------------
# Sanity: SDK_VERSION bumped to C4 marker
# ---------------------------------------------------------------------------

def test_sdk_version_bumped_for_zkba_c4():
    """SDK_VERSION reflects ZKBA C4 ship (Phase O3-ZKBA-TRACK1 C4)."""
    assert "zkba" in SDK_VERSION.lower(), f"SDK_VERSION={SDK_VERSION!r} does not mention zkba"
    assert SDK_VERSION.startswith("3.1.0"), f"SDK_VERSION={SDK_VERSION!r} should start with 3.1.0"
