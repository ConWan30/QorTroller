"""Phase 234.7 SDK tests — CaptureHealthResult + VAPICaptureContinuity.

T234_7-SDK-1: CaptureHealthResult has all 11 slots with correct defaults
T234_7-SDK-2: status() parses NOMINAL capture_state from mocked response
T234_7-SDK-3: status() returns fail-safe CaptureHealthResult on network error
T234_7-SDK-4: session_counting_paused parsed correctly from response body
"""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import CaptureHealthResult, VAPICaptureContinuity


# ---------------------------------------------------------------------------
# T234_7-SDK-1: CaptureHealthResult defaults
# ---------------------------------------------------------------------------

def test_t234_7_sdk_1_result_defaults():
    r = CaptureHealthResult()
    assert r.pcc_enabled is True
    assert r.capture_state == "DISCONNECTED"
    assert r.host_state == "UNKNOWN"
    assert r.poll_rate_hz == pytest.approx(0.0)
    assert r.sustained_duration_s == pytest.approx(0.0)
    assert r.grind_mode is False
    assert r.grind_ready is False
    assert r.grind_target == 100
    assert r.consecutive_clean_toward_target == 0
    assert r.session_counting_paused is False
    assert r.error == ""
    import dataclasses
    assert len(dataclasses.fields(CaptureHealthResult)) == 11


# ---------------------------------------------------------------------------
# T234_7-SDK-2: status() parses NOMINAL capture_state
# ---------------------------------------------------------------------------

def test_t234_7_sdk_2_status_nominal_parsed(monkeypatch):
    body = {
        "pcc_enabled": True,
        "capture_state": "NOMINAL",
        "host_state": "EXCLUSIVE_USB",
        "poll_rate_hz": 1002.5,
        "sustained_duration_s": 45.0,
        "grind_mode": True,
        "grind_ready": True,
        "grind_target": 100,
        "consecutive_clean_toward_target": 37,
        "session_counting_paused": False,
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

    assert result.capture_state == "NOMINAL"
    assert result.host_state == "EXCLUSIVE_USB"
    assert result.poll_rate_hz == pytest.approx(1002.5)
    assert result.grind_ready is True
    assert result.grind_mode is True
    assert result.consecutive_clean_toward_target == 37
    assert result.session_counting_paused is False
    assert result.error == ""


# ---------------------------------------------------------------------------
# T234_7-SDK-3: status() returns fail-safe result on network error
# ---------------------------------------------------------------------------

def test_t234_7_sdk_3_status_network_error(monkeypatch):
    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(
        ConnectionRefusedError("no server")
    ))

    client = VAPICaptureContinuity("http://localhost:8080", "test-key")
    result = client.status()

    assert result.error != "", "error field must be non-empty on connection failure"
    assert result.capture_state == "DISCONNECTED"
    assert result.grind_ready is False


# ---------------------------------------------------------------------------
# T234_7-SDK-4: session_counting_paused parsed correctly
# ---------------------------------------------------------------------------

def test_t234_7_sdk_4_session_counting_paused_parsed(monkeypatch):
    body = {
        "pcc_enabled": True,
        "capture_state": "DEGRADED",
        "host_state": "CONTESTED",
        "poll_rate_hz": 450.0,
        "sustained_duration_s": 12.0,
        "grind_mode": True,
        "grind_ready": False,
        "grind_target": 100,
        "consecutive_clean_toward_target": 22,
        "session_counting_paused": True,  # grind_mode=True, grind_ready=False
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

    assert result.session_counting_paused is True
    assert result.capture_state == "DEGRADED"
    assert result.grind_mode is True
    assert result.grind_ready is False
    assert result.consecutive_clean_toward_target == 22
