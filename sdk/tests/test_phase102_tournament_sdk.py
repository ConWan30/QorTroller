"""
Phase 102 — Developer Integration Layer: SDK Tests (6 tests)
SDK count: 87 → 93 (+6)
"""
from __future__ import annotations

import dataclasses
import sys
import os

# Ensure sdk directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_sdk import PlayerEligibility, VAPITournamentClient


# ── test_1: PlayerEligibility.__slots__ ──────────────────────────────────

def test_1_player_eligibility_slots():
    """PlayerEligibility.__slots__ has all 8 fields."""
    expected = {
        "device_id", "wallet", "is_eligible", "has_valid_vhp",
        "consecutive_clean", "cert_level", "expires_at", "error",
    }
    assert set(PlayerEligibility.__slots__) == expected


# ── test_2: PlayerEligibility defaults ───────────────────────────────────

def test_2_player_eligibility_defaults():
    """PlayerEligibility defaults — is_eligible=False, error=None."""
    e = PlayerEligibility(
        device_id="dev-x",
        wallet="0xwallet",
        is_eligible=False,
        has_valid_vhp=False,
        consecutive_clean=0,
        cert_level=0,
        expires_at=0.0,
    )
    assert e.is_eligible is False
    assert e.error is None
    assert e.device_id == "dev-x"


# ── test_3: check_player on bad URL never raises ──────────────────────────

def test_3_check_player_bad_url_never_raises():
    """check_player returns error on bad URL (never raises)."""
    client = VAPITournamentClient("http://localhost:19999", api_key="nokey")
    result = client.check_player("dev-bad", "0xwallet")
    assert result.is_eligible is False
    assert result.error is not None
    assert isinstance(result.error, str)


# ── test_4: check_player parses mocked response ────────────────────────────

def test_4_check_player_eligible(monkeypatch):
    """check_player parses mocked vhp-status response → is_eligible=True when is_valid+cc>0."""
    import urllib.request
    import json

    mock_data = json.dumps({
        "is_valid": True,
        "consecutive_clean": 3,
        "cert_level": 1,
        "expires_at": 9999999999.0,
    }).encode()

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return mock_data

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResp())

    client = VAPITournamentClient("http://localhost:8080", api_key="k")
    result = client.check_player("dev-ok", "0xwallet")
    assert result.is_eligible is True
    assert result.has_valid_vhp is True
    assert result.consecutive_clean == 3
    assert result.cert_level == 1


# ── test_5: check_player is_eligible=False when is_valid=False ────────────

def test_5_check_player_not_eligible(monkeypatch):
    """check_player returns is_eligible=False when is_valid=False."""
    import urllib.request
    import json

    mock_data = json.dumps({
        "is_valid": False,
        "consecutive_clean": 0,
        "cert_level": 0,
        "expires_at": 0.0,
    }).encode()

    class FakeResp:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self): return mock_data

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: FakeResp())

    client = VAPITournamentClient("http://localhost:8080", api_key="k")
    result = client.check_player("dev-no-vhp", "0xwallet")
    assert result.is_eligible is False
    assert result.has_valid_vhp is False


# ── test_6: check_player never raises on timeout ──────────────────────────

def test_6_check_player_never_raises_on_timeout(monkeypatch):
    """check_player never raises on timeout (urllib timeout=10)."""
    import urllib.request
    import socket
    import pytest

    def fake_urlopen(*a, **kw):
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client = VAPITournamentClient("http://localhost:8080", api_key="k")
    try:
        result = client.check_player("dev-timeout", "0xwallet")
    except Exception as exc:
        pytest.fail(f"check_player raised unexpectedly: {exc}")
    assert result.is_eligible is False
    assert result.error is not None
