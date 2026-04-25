"""Phase 235-ANALYTICS SDK tests.

T235-ANL-SDK-1: GrindAnalyticsResult instantiates with correct field types
T235-ANL-SDK-2: VAPIGrindAnalytics.status() parses success_rate from response body
T235-ANL-SDK-3: VAPIGrindAnalytics.status() populates error slot on exception
T235-ANL-SDK-4: VAPIGrindAnalytics endpoint URL path is /grind/analytics
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import VAPIGrindAnalytics, GrindAnalyticsResult


# ---------------------------------------------------------------------------
# T235-ANL-SDK-1: dataclass fields and defaults
# ---------------------------------------------------------------------------

def test_t235_anl_sdk_1_dataclass_instantiation():
    """GrindAnalyticsResult has the correct 8 slots with defaults."""
    r = GrindAnalyticsResult()
    assert r.grind_session_id == ""
    assert r.total_validated == 0
    assert r.stamped_count == 0
    assert r.success_rate == 0.0
    assert isinstance(r.blocking_reason_counts, dict)
    assert r.sessions_per_day == 0.0
    assert r.projected_gic100_date == "unknown"
    assert r.error == ""


# ---------------------------------------------------------------------------
# T235-ANL-SDK-2: status() parses all fields from HTTP response
# ---------------------------------------------------------------------------

def test_t235_anl_sdk_2_status_parses_response(monkeypatch):
    """VAPIGrindAnalytics.status() parses success_rate and blocking_reason_counts."""
    body = {
        "grind_session_id":       "grind_phase235_v1",
        "total_validated":        20,
        "stamped_count":          12,
        "success_rate":           0.6,
        "blocking_reason_counts": {"MENU_DETECTED": 4, "PCC_NOT_NOMINAL:DISCONNECTED": 4},
        "sessions_per_day":       3.5,
        "projected_gic100_date":  "2026-05-15",
        "timestamp":              1714076500.0,
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

    client = VAPIGrindAnalytics("http://localhost:8080", "test-key")
    result = client.status()

    assert result.error == ""
    assert result.grind_session_id == "grind_phase235_v1"
    assert result.total_validated == 20
    assert result.stamped_count == 12
    assert abs(result.success_rate - 0.6) < 0.001
    assert result.blocking_reason_counts["MENU_DETECTED"] == 4
    assert abs(result.sessions_per_day - 3.5) < 0.001
    assert result.projected_gic100_date == "2026-05-15"


# ---------------------------------------------------------------------------
# T235-ANL-SDK-3: status() returns error slot on exception
# ---------------------------------------------------------------------------

def test_t235_anl_sdk_3_error_slot_on_exception(monkeypatch):
    """VAPIGrindAnalytics.status() populates error and returns defaults on failure."""
    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(
        Exception("connection refused")
    ))

    client = VAPIGrindAnalytics("http://localhost:8080", "test-key")
    result = client.status()

    assert "connection refused" in result.error
    assert result.stamped_count == 0
    assert result.success_rate == 0.0


# ---------------------------------------------------------------------------
# T235-ANL-SDK-4: endpoint URL path contains /grind/analytics
# ---------------------------------------------------------------------------

def test_t235_anl_sdk_4_endpoint_path(monkeypatch):
    """VAPIGrindAnalytics uses /grind/analytics as its endpoint path."""
    captured_url = []

    class _FakeResp:
        def read(self):
            return json.dumps({"grind_session_id": "", "total_validated": 0,
                               "stamped_count": 0, "success_rate": 0.0,
                               "blocking_reason_counts": {}, "sessions_per_day": 0.0,
                               "projected_gic100_date": "unknown"}).encode()
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass

    def _fake_urlopen(req, timeout=None):
        captured_url.append(req.full_url if hasattr(req, "full_url") else req.get_full_url())
        return _FakeResp()

    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", _fake_urlopen)

    client = VAPIGrindAnalytics("http://localhost:8080", "test-key")
    client.status()

    assert len(captured_url) == 1
    assert "/grind/analytics" in captured_url[0]
