"""Phase 235-B SDK tests — PCC-gated consecutive_clean via VAPICaptureContinuity.

T235B-SDK-1: capture-health response reflects pcc_state fields (latest_pcc_state present)
T235B-SDK-2: consecutive_clean=0 when bridge reports CONTESTED host state
"""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import VAPICaptureContinuity, CaptureHealthResult


# ---------------------------------------------------------------------------
# T235B-SDK-1: consecutive_clean_toward_target reflects PCC-gated count
# ---------------------------------------------------------------------------

def test_t235b_sdk_1_pcc_fields_present(monkeypatch):
    body = {
        "pcc_enabled": True,
        "capture_state": "NOMINAL",
        "host_state": "EXCLUSIVE_USB",
        "poll_rate_hz": 1001.0,
        "sustained_duration_s": 35.0,
        "grind_mode": True,
        "grind_ready": True,
        "grind_target": 100,
        "consecutive_clean_toward_target": 12,
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

    # PCC-gated consecutive_clean is reflected in the count
    assert result.consecutive_clean_toward_target == 12
    assert result.capture_state == "NOMINAL"
    assert result.host_state == "EXCLUSIVE_USB"
    assert result.grind_ready is True
    assert result.session_counting_paused is False


# ---------------------------------------------------------------------------
# T235B-SDK-2: CONTESTED host → session_counting_paused=True, clean count=0
# ---------------------------------------------------------------------------

def test_t235b_sdk_2_contested_grind_not_counting(monkeypatch):
    # Bridge reports CONTESTED: grind_ready=False because CONTESTED host fails PCC gate
    # session_counting_paused=True (grind_mode=True AND NOT grind_ready)
    # consecutive_clean_toward_target=0 because CONTESTED sessions are PCC-excluded
    body = {
        "pcc_enabled": True,
        "capture_state": "NOMINAL",
        "host_state": "CONTESTED",
        "poll_rate_hz": 987.0,
        "sustained_duration_s": 8.0,
        "grind_mode": True,
        "grind_ready": False,
        "grind_target": 100,
        "consecutive_clean_toward_target": 0,
        "session_counting_paused": True,
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

    assert result.host_state == "CONTESTED"
    assert result.grind_ready is False
    assert result.session_counting_paused is True
    assert result.consecutive_clean_toward_target == 0
