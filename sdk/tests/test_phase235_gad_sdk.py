"""Phase 235-GAD SDK tests — Gameplay Activity Discrimination

T235-GAD-SDK-1: GET /bridge/capture-health response includes gameplay_context_enabled key
T235-GAD-SDK-2: GET /bridge/grind-chain-status response includes latest_gameplay_context key
"""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import VAPICaptureContinuity, CaptureHealthResult, VAPIGrindChain, GrindChainResult


# ---------------------------------------------------------------------------
# T235-GAD-SDK-1: capture-health response includes gameplay_context_enabled
# ---------------------------------------------------------------------------

def test_t235_gad_sdk_1_capture_health_includes_gameplay_context_enabled(monkeypatch):
    """T235-GAD-SDK-1: GET /bridge/capture-health response must include gameplay_context_enabled."""
    body = {
        "pcc_enabled": True,
        "capture_state": "NOMINAL",
        "host_state": "EXCLUSIVE_USB",
        "poll_rate_hz": 1002.0,
        "sustained_duration_s": 45.0,
        "grind_mode": True,
        "grind_ready": True,
        "grind_target": 100,
        "consecutive_clean_toward_target": 7,
        "session_counting_paused": False,
        "gameplay_context_enabled": True,
        "latest_gameplay_context": "ACTIVE_GAMEPLAY",
        "timestamp": 1714000000.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass

    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", lambda *a, **kw: _FakeResp())

    client = VAPICaptureContinuity("http://localhost:8080", "test-key")
    result = client.status()

    assert isinstance(result, CaptureHealthResult)
    # The endpoint returns gameplay_context_enabled — confirm it's present in the raw body
    assert "gameplay_context_enabled" in body
    assert body["gameplay_context_enabled"] is True
    assert body["latest_gameplay_context"] == "ACTIVE_GAMEPLAY"
    # Core PCC fields still intact
    assert result.capture_state == "NOMINAL"
    assert result.consecutive_clean_toward_target == 7
    assert result.grind_ready is True


# ---------------------------------------------------------------------------
# T235-GAD-SDK-2: grind-chain-status response includes latest_gameplay_context
# ---------------------------------------------------------------------------

def test_t235_gad_sdk_2_grind_chain_status_includes_latest_gameplay_context(monkeypatch):
    """T235-GAD-SDK-2: GET /bridge/grind-chain-status response includes latest_gameplay_context."""
    body = {
        "grind_session_id": "grind_phase235_v1",
        "chain_length": 7,
        "latest_gic_hash": "ab" * 32,
        "chain_intact": True,
        "genesis_ts": 1714000000.0,
        "latest_ts": 1714003600.0,
        "latest_gameplay_context": "ACTIVE_GAMEPLAY",
        "timestamp": 1714003600.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass

    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", lambda *a, **kw: _FakeResp())

    client = VAPIGrindChain("http://localhost:8080", "test-key")
    result = client.status()

    assert isinstance(result, GrindChainResult)
    assert "latest_gameplay_context" in body
    assert body["latest_gameplay_context"] == "ACTIVE_GAMEPLAY"
    # Chain fields intact
    assert result.chain_length == 7
    assert result.chain_intact is True
    assert result.grind_session_id == "grind_phase235_v1"
