"""
Phase 215 SDK Tests
T215-SDK-1..4: L4DimSyncResult / VAPIL4DimSync
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ── T215-SDK-1: L4DimSyncResult has required slots ───────────────────────────
def test_T215_sdk_1_dataclass_fields():
    """L4DimSyncResult has required slots (Phase 215)."""
    from vapi_sdk import L4DimSyncResult
    import dataclasses
    fields = {f.name for f in dataclasses.fields(L4DimSyncResult)}
    assert "l4_dim_sync_enabled"  in fields
    assert "sync_completed"       in fields
    assert "from_dim"             in fields
    assert "to_dim"               in fields
    assert "anomaly_threshold"    in fields
    assert "continuity_threshold" in fields
    assert "error"                in fields


# ── T215-SDK-2: L4DimSyncResult instantiation ────────────────────────────────
def test_T215_sdk_2_result_instantiation():
    """L4DimSyncResult can be created with sync data."""
    from vapi_sdk import L4DimSyncResult
    r = L4DimSyncResult(
        l4_dim_sync_enabled  = True,
        sync_completed       = True,
        from_dim             = 12,
        to_dim               = 13,
        anomaly_threshold    = 7.009,
        continuity_threshold = 5.367,
    )
    assert r.l4_dim_sync_enabled is True
    assert r.sync_completed is True
    assert r.from_dim == 12
    assert r.to_dim == 13
    assert r.anomaly_threshold == pytest.approx(7.009)
    assert r.continuity_threshold == pytest.approx(5.367)
    assert r.error is None


# ── T215-SDK-3: VAPIL4DimSync returns error on network failure ────────────────
def test_T215_sdk_3_client_network_error():
    """VAPIL4DimSync returns L4DimSyncResult with error on connection failure."""
    from vapi_sdk import VAPIL4DimSync, L4DimSyncResult
    client = VAPIL4DimSync("http://localhost:19999", api_key="test")
    result = client.get_status()
    assert isinstance(result, L4DimSyncResult)
    assert result.error is not None
    assert result.sync_completed is False
    assert result.l4_dim_sync_enabled is False
    assert result.from_dim is None
    assert result.to_dim is None


# ── T215-SDK-4: VAPIL4DimSync.get_status() parses response ───────────────────
def test_T215_sdk_4_get_status_parses_response():
    """VAPIL4DimSync.get_status() parses all fields from a 200 response."""
    import json
    from unittest.mock import MagicMock, patch
    from vapi_sdk import VAPIL4DimSync, L4DimSyncResult

    body = json.dumps({
        "l4_dim_sync_enabled":   True,
        "sync_completed":        True,
        "from_dim":              12,
        "to_dim":                13,
        "anomaly_threshold":     7.009,
        "continuity_threshold":  5.367,
        "timestamp":             1712400000.0,
    }).encode()

    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = body

    with patch("urllib.request.urlopen", return_value=mock_resp):
        client = VAPIL4DimSync("http://localhost:8080", api_key="test")
        result = client.get_status()

    assert isinstance(result, L4DimSyncResult)
    assert result.l4_dim_sync_enabled is True
    assert result.sync_completed is True
    assert result.from_dim == 12
    assert result.to_dim == 13
    assert result.anomaly_threshold == pytest.approx(7.009)
    assert result.continuity_threshold == pytest.approx(5.367)
    assert result.error is None
