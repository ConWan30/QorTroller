"""
Phase 190 SDK tests — LivePresenceSignalingResult + VAPILivePresenceSignaling.

Tests:
  T190S-1: LivePresenceSignalingResult has correct 6 slots with safe defaults
  T190S-2: live_presence_signaling_enabled=False default (infrastructure-first)
  T190S-3: get_status populates result from HTTP response body
  T190S-4: error path returns safe defaults on network failure
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import LivePresenceSignalingResult, VAPILivePresenceSignaling  # noqa: E402


# ---------------------------------------------------------------------------
# T190S-1: dataclass slots and defaults
# ---------------------------------------------------------------------------

def test_t190s_1_result_slots_and_defaults():
    """T190S-1: LivePresenceSignalingResult has correct 6 slots with safe defaults."""
    r = LivePresenceSignalingResult()
    assert r.live_presence_signaling_enabled is False
    assert r.total_signals == 0
    assert r.controller_fired_count == 0
    assert r.ps5_suppressed_count == 0
    assert r.latest_signal_type == ""
    assert r.error == ""
    # Confirm slots present
    assert hasattr(r, "__slots__")
    assert "live_presence_signaling_enabled" in r.__slots__
    assert "total_signals" in r.__slots__
    assert "controller_fired_count" in r.__slots__
    assert "ps5_suppressed_count" in r.__slots__
    assert "latest_signal_type" in r.__slots__
    assert "error" in r.__slots__


# ---------------------------------------------------------------------------
# T190S-2: enabled=False default
# ---------------------------------------------------------------------------

def test_t190s_2_enabled_default_false():
    """T190S-2: live_presence_signaling_enabled=False by default (infrastructure-first)."""
    r = LivePresenceSignalingResult()
    assert r.live_presence_signaling_enabled is False


# ---------------------------------------------------------------------------
# T190S-3: get_status populates from body
# ---------------------------------------------------------------------------

def test_t190s_3_get_status_populates_from_body(monkeypatch):
    """T190S-3: get_status populates LivePresenceSignalingResult from HTTP response body."""
    import json

    _body = {
        "live_presence_signaling_enabled": True,
        "total_signals":          42,
        "controller_fired_count": 15,
        "ps5_suppressed_count":   27,
        "latest_signal_source":   "persona_break",
        "latest_signal_type":     "PERSONA_BREAK_DETECTED",
        "latest_terminal_output": "[VAPI] persona break detected",
        "timestamp":              1744234567.0,
    }

    class _FakeResp:
        def read(self):
            return json.dumps(_body).encode()
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    import urllib.request as _req
    monkeypatch.setattr(_req, "urlopen", lambda *a, **kw: _FakeResp())

    client = VAPILivePresenceSignaling(base_url="http://localhost:8000", api_key="test")
    result = client.get_status()

    assert result.live_presence_signaling_enabled is True
    assert result.total_signals == 42
    assert result.controller_fired_count == 15
    assert result.ps5_suppressed_count == 27
    assert result.latest_signal_type == "PERSONA_BREAK_DETECTED"
    assert result.error == ""


# ---------------------------------------------------------------------------
# T190S-4: error path returns safe defaults
# ---------------------------------------------------------------------------

def test_t190s_4_error_path_safe_defaults(monkeypatch):
    """T190S-4: get_status returns safe zero defaults on network failure."""
    import urllib.request as _req

    def _raise(*a, **kw):
        raise ConnectionRefusedError("no bridge")

    monkeypatch.setattr(_req, "urlopen", _raise)

    client = VAPILivePresenceSignaling(base_url="http://localhost:9999", api_key="")
    result = client.get_status()

    assert result.live_presence_signaling_enabled is False
    assert result.total_signals == 0
    assert result.controller_fired_count == 0
    assert result.ps5_suppressed_count == 0
    assert result.latest_signal_type == ""
    assert "no bridge" in result.error
