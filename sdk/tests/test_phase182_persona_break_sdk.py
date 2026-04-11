"""Phase 182 SDK tests — PersonaBreakDetectorAgent (WIF-028 deeper mitigation).

4 tests:
  T182-SDK-1  PersonaBreakResult has 6 slots; error=None default
  T182-SDK-2  persona_break_detected=True populated from response body
  T182-SDK-3  error path returns persona_break_detected=False (fail-open)
  T182-SDK-4  get_status with player_id= passes player_id param in URL
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sdk"))


# ---------------------------------------------------------------------------
# T182-SDK-1  PersonaBreakResult has 6 slots; error=None default
# ---------------------------------------------------------------------------

def test_t182_sdk_1_persona_break_result_slots():
    from vapi_sdk import PersonaBreakResult
    r = PersonaBreakResult(
        persona_break_detected=False,
        player_id="P1",
        loo_accuracy_trend=0.85,
        tdi_current=0.05,
        re_enrollment_urgency="MEDIUM",
    )
    assert r.persona_break_detected is False
    assert r.player_id == "P1"
    assert r.loo_accuracy_trend == 0.85
    assert r.tdi_current == 0.05
    assert r.re_enrollment_urgency == "MEDIUM"
    assert r.error is None


# ---------------------------------------------------------------------------
# T182-SDK-2  persona_break_detected=True populated from response body
# ---------------------------------------------------------------------------

def test_t182_sdk_2_persona_break_detected_true_from_body():
    from unittest.mock import patch, MagicMock
    import json as _j
    from vapi_sdk import VAPIPersonaBreakDetector, PersonaBreakResult

    body = {
        "persona_break_detection_enabled": True,
        "player_id":              "P1",
        "loo_accuracy_trend":     0.12,
        "tdi_current":            0.18,
        "persona_break_detected": True,
        "re_enrollment_urgency":  "CRITICAL",
        "n_snapshots_used":       5,
        "timestamp":              1.0,
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = _j.dumps(body).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        pb = VAPIPersonaBreakDetector("http://localhost:8080", "test-key")
        result = pb.get_status(player_id="P1")

    assert isinstance(result, PersonaBreakResult)
    assert result.persona_break_detected is True
    assert result.re_enrollment_urgency == "CRITICAL"
    assert result.error is None


# ---------------------------------------------------------------------------
# T182-SDK-3  error path returns persona_break_detected=False (fail-open)
# ---------------------------------------------------------------------------

def test_t182_sdk_3_error_path_fail_open():
    from unittest.mock import patch
    from vapi_sdk import VAPIPersonaBreakDetector

    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        pb = VAPIPersonaBreakDetector("http://localhost:8080", "test-key")
        result = pb.get_status()

    assert result.persona_break_detected is False
    assert result.re_enrollment_urgency == "MEDIUM"
    assert result.error is not None
    assert "timeout" in result.error


# ---------------------------------------------------------------------------
# T182-SDK-4  get_status with player_id passes param in URL
# ---------------------------------------------------------------------------

def test_t182_sdk_4_player_id_in_url():
    from unittest.mock import patch, MagicMock
    import json as _j
    from vapi_sdk import VAPIPersonaBreakDetector

    captured_urls = []

    def fake_urlopen(url, timeout=10):
        captured_urls.append(url)
        resp = MagicMock()
        resp.read.return_value = _j.dumps({
            "persona_break_detected": False,
            "player_id": "P3",
            "loo_accuracy_trend": 0.90,
            "tdi_current": 0.01,
            "re_enrollment_urgency": "MEDIUM",
        }).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        pb = VAPIPersonaBreakDetector("http://localhost:8080", "test-key")
        pb.get_status(player_id="P3")

    assert captured_urls, "urlopen not called"
    assert "player_id=P3" in captured_urls[0]
