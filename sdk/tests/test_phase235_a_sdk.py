"""Phase 235-A SDK tests — GrindChainResult + VAPIGrindChain.

T235A-SDK-1: GrindChainResult has correct defaults (7 slots)
T235A-SDK-2: status() parses nominal intact chain from mock response
T235A-SDK-3: status() returns chain_intact=False on broken chain response
T235A-SDK-4: status() returns error field on network error, chain_intact=False
"""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import GrindChainResult, VAPIGrindChain


# ---------------------------------------------------------------------------
# T235A-SDK-1: GrindChainResult defaults
# ---------------------------------------------------------------------------

def test_t235a_sdk_1_result_defaults():
    r = GrindChainResult()
    assert r.grind_session_id == ""
    assert r.chain_length == 0
    assert r.latest_gic_hash == ""
    assert r.chain_intact is False
    assert r.genesis_ts == 0.0
    assert r.latest_ts == 0.0
    assert r.error == ""
    import dataclasses
    assert len(dataclasses.fields(GrindChainResult)) == 7


# ---------------------------------------------------------------------------
# T235A-SDK-2: status() parses intact chain
# ---------------------------------------------------------------------------

def test_t235a_sdk_2_intact_chain_parsed(monkeypatch):
    body = {
        "grind_session_id": "grind_20260422",
        "chain_length":     42,
        "latest_gic_hash":  "a" * 64,
        "chain_intact":     True,
        "genesis_ts":       1745000000.0,
        "latest_ts":        1745042000.0,
        "timestamp":        1745099999.0,
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

    assert result.grind_session_id == "grind_20260422"
    assert result.chain_length == 42
    assert result.latest_gic_hash == "a" * 64
    assert result.chain_intact is True
    assert result.genesis_ts == pytest.approx(1745000000.0)
    assert result.latest_ts == pytest.approx(1745042000.0)
    assert result.error == ""


# ---------------------------------------------------------------------------
# T235A-SDK-3: status() chain_intact=False on broken chain
# ---------------------------------------------------------------------------

def test_t235a_sdk_3_broken_chain_parsed(monkeypatch):
    body = {
        "grind_session_id": "grind_20260422",
        "chain_length":     5,
        "latest_gic_hash":  "b" * 64,
        "chain_intact":     False,
        "genesis_ts":       1745000000.0,
        "latest_ts":        1745005000.0,
        "timestamp":        1745009999.0,
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

    assert result.chain_intact is False
    assert result.chain_length == 5
    assert result.error == ""


# ---------------------------------------------------------------------------
# T235A-SDK-4: status() returns error on network failure
# ---------------------------------------------------------------------------

def test_t235a_sdk_4_network_error(monkeypatch):
    import urllib.request as _ur
    monkeypatch.setattr(_ur, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(
        ConnectionRefusedError("no bridge")
    ))

    client = VAPIGrindChain("http://localhost:8080", "test-key")
    result = client.status()

    assert result.error != "", "error must be non-empty on connection failure"
    assert result.chain_intact is False
    assert result.chain_length == 0
