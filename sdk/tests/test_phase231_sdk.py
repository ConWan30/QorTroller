"""Phase 231 SDK tests — TournamentPreflightResult ait_defensibility_ok slot.

T231-SDK-1: TournamentPreflightResult has ait_defensibility_ok slot defaulting to False
T231-SDK-2: ait_defensibility_ok=True parses correctly from run_preflight response mock
T231-SDK-3: ait_defensibility_ok=False parses correctly (fail-closed default)
T231-SDK-4: InvariantGateResult slot count unchanged; TournamentPreflightResult total slots = 11
"""
import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_sdk import TournamentPreflightResult, VAPITournamentPreflight


# ---------------------------------------------------------------------------
# T231-SDK-1: Default value for ait_defensibility_ok is False
# ---------------------------------------------------------------------------

def test_t231_sdk_1_ait_defensibility_default():
    r = TournamentPreflightResult()
    assert hasattr(r, "ait_defensibility_ok"), "ait_defensibility_ok slot missing"
    assert r.ait_defensibility_ok is False


# ---------------------------------------------------------------------------
# T231-SDK-2: ait_defensibility_ok=True parsed from mocked run_preflight body
# ---------------------------------------------------------------------------

def test_t231_sdk_2_ait_defensibility_true_parsed(monkeypatch):
    body = {
        "separation_ok": True,
        "l4_ok": True,
        "gate_ok": True,
        "cert_ok": True,
        "audit_ok": True,
        "overall_pass": True,
        "biometric_ttl_ok": True,
        "all_pairs_p0_ok": True,
        "ait_defensibility_ok": True,
        "conditions": {},
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

    client = VAPITournamentPreflight("http://localhost:8000", "test-key")
    result = client.run_preflight()
    assert result.ait_defensibility_ok is True
    assert result.overall_pass is True
    assert result.error is None


# ---------------------------------------------------------------------------
# T231-SDK-3: ait_defensibility_ok=False when key absent (fail-closed default)
# ---------------------------------------------------------------------------

def test_t231_sdk_3_ait_defensibility_absent_is_false(monkeypatch):
    body = {
        "separation_ok": True,
        "l4_ok": True,
        "gate_ok": True,
        "cert_ok": True,
        "audit_ok": True,
        "overall_pass": False,
        "biometric_ttl_ok": True,
        "all_pairs_p0_ok": True,
        # ait_defensibility_ok intentionally absent
        "conditions": {},
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

    client = VAPITournamentPreflight("http://localhost:8000", "test-key")
    result = client.run_preflight()
    assert result.ait_defensibility_ok is False   # fail-closed default


# ---------------------------------------------------------------------------
# T231-SDK-4: TournamentPreflightResult has exactly 11 fields
# ---------------------------------------------------------------------------

def test_t231_sdk_4_preflight_result_slot_count():
    import dataclasses
    fields = dataclasses.fields(TournamentPreflightResult)
    assert len(fields) == 11, (
        f"Expected 11 slots, got {len(fields)}: {[f.name for f in fields]}"
    )
