"""
Phase 187 — VHPReenrollmentBadgeResult + VAPIVHPReenrollmentBadge SDK tests (4 tests).

Tests:
  T187B-SDK-1: VHPReenrollmentBadgeResult has 6 slots; enabled=False; badge_token_id=0
  T187B-SDK-2: player_id kwarg in get_status URL
  T187B-SDK-3: get_status populates from mock body correctly
  T187B-SDK-4: error path returns safe defaults (enabled=False, badge_token_id=0, error set)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from unittest.mock import patch, MagicMock
import json

from vapi_sdk import VHPReenrollmentBadgeResult, VAPIVHPReenrollmentBadge


# T187B-SDK-1 — 6 slots, defaults
def test_1_result_has_6_slots_and_defaults():
    r = VHPReenrollmentBadgeResult()
    assert r.reenrollment_badge_enabled is False
    assert r.player_id == ""
    assert r.badge_token_id == 0
    assert r.re_enrollment_count == 0
    assert r.total_badges == 0
    assert r.error is None

    assert hasattr(r, "__slots__")
    expected_slots = {
        "reenrollment_badge_enabled", "player_id", "badge_token_id",
        "re_enrollment_count", "total_badges", "error",
    }
    assert expected_slots <= set(r.__slots__)


# T187B-SDK-2 — player_id kwarg in URL
def test_2_player_id_kwarg_in_url():
    client = VAPIVHPReenrollmentBadge("http://localhost:8000", api_key="k")
    captured_urls = []

    def fake_urlopen(url, timeout=10):
        captured_urls.append(str(url))
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        m.read.return_value = json.dumps({
            "reenrollment_badge_enabled": False,
            "player_id": "P1",
            "badge_token_id": 0,
            "re_enrollment_count": 0,
            "total_badges": 0,
        }).encode()
        return m

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        client.get_status(player_id="P1")

    assert "player_id=P1" in captured_urls[0]
    assert "api_key=k" in captured_urls[0]


# T187B-SDK-3 — populates from mock body
def test_3_populates_from_body():
    client = VAPIVHPReenrollmentBadge("http://localhost:8000")
    mock_body = {
        "reenrollment_badge_enabled": True,
        "player_id": "P1",
        "badge_token_id": 7,
        "re_enrollment_count": 2,
        "total_badges": 12,
        "dry_run": False,
    }

    def fake_urlopen(url, timeout=10):
        m = MagicMock()
        m.__enter__ = lambda s: s
        m.__exit__ = MagicMock(return_value=False)
        m.read.return_value = json.dumps(mock_body).encode()
        return m

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = client.get_status(player_id="P1")

    assert result.reenrollment_badge_enabled is True
    assert result.player_id == "P1"
    assert result.badge_token_id == 7
    assert result.re_enrollment_count == 2
    assert result.total_badges == 12
    assert result.error is None


# T187B-SDK-4 — error path safe defaults
def test_4_error_path_safe_defaults():
    client = VAPIVHPReenrollmentBadge("http://localhost:9999")

    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError("refused")):
        result = client.get_status()

    assert result.reenrollment_badge_enabled is False
    assert result.badge_token_id == 0
    assert result.re_enrollment_count == 0
    assert result.total_badges == 0
    assert result.error is not None
    assert len(result.error) > 0
