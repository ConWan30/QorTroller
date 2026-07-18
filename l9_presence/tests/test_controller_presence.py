"""Tests for controller_presence composition (ioID × PoEP live dual-bit postcard).

Pins: dual bits never OR-merge; device mismatch → UNVERIFIABLE; identity alone ≠ presence;
presence alone ≠ identity; no commitment primitive; advances_poep_enabled always False.
"""
from __future__ import annotations

from l9_presence import controller_presence as cp

_DEV = cp.EDGE_DEVICE_ID_LIVE
_OTHER = "20b37e1c" + "ab" * 28  # different 64-hex shape


def _ioid(dev=_DEV, token_id=498):
    return {
        "token_id": token_id,
        "did": "did:io:0x0cf36db5",
        "tba": "0xFCee237789FA91a141781aFB574ADAbcA2660e7b",
        "registered_device_id": dev,
    }


def _poep(dev=_DEV, ok=True, sid="sess1"):
    return {
        "presence_session_candidate_ok": ok,
        "device_id": dev,
        "session_id": sid,
        "live_seal": "ab" * 32,
    }


def test_synchronized_both_bits_same_device():
    r = cp.build_controller_presence(
        device_id=_DEV, session_id="sess1", ioid=_ioid(), poep_live_summary=_poep()
    )
    assert r.verdict == cp.SYNCHRONIZED_CONTROLLER
    assert r.identity_bound is True
    assert r.presence_candidate is True
    assert r.ioid["token_id"] == 498
    assert r.poep_live["id_verified"] is True
    d = r.to_dict()
    assert d["advances_poep_enabled"] is False
    assert d["advances_presence_session_candidate"] is False
    assert d["advisory"] is True


def test_identity_only_does_not_imply_presence():
    """Banked ioID ceremony alone must NEVER mint presence_candidate."""
    r = cp.build_controller_presence(device_id=_DEV, ioid=_ioid())
    assert r.verdict == cp.IDENTITY_ONLY
    assert r.identity_bound is True
    assert r.presence_candidate is False
    assert any("does NOT imply presence" in n for n in r.notes)
    # Anti-OR: no hidden combined green
    assert not (r.identity_bound and r.presence_candidate)


def test_presence_only_does_not_imply_identity():
    r = cp.build_controller_presence(device_id=_DEV, poep_live_summary=_poep())
    assert r.verdict == cp.PRESENCE_ONLY
    assert r.identity_bound is False
    assert r.presence_candidate is True
    assert any("does NOT imply ioID" in n for n in r.notes)


def test_identity_true_presence_false_never_synchronized():
    r = cp.build_controller_presence(
        device_id=_DEV, ioid=_ioid(), poep_live_summary=_poep(ok=False)
    )
    assert r.verdict == cp.IDENTITY_ONLY
    assert r.verdict != cp.SYNCHRONIZED_CONTROLLER
    assert r.presence_candidate is False


def test_device_mismatch_is_unverifiable_never_partial_success():
    r = cp.build_controller_presence(
        device_id=_DEV,
        ioid=_ioid(dev=_OTHER),
        poep_live_summary=_poep(dev=_DEV),
    )
    assert r.verdict == cp.UNVERIFIABLE
    assert r.identity_bound is False
    assert r.presence_candidate is False
    assert any("MISMATCH" in n for n in r.notes)


def test_poep_device_mismatch_clears_presence_bit():
    r = cp.build_controller_presence(
        device_id=_DEV,
        ioid=_ioid(dev=_DEV),
        poep_live_summary=_poep(dev=_OTHER, ok=True),
    )
    assert r.verdict == cp.UNVERIFIABLE
    assert r.presence_candidate is False


def test_session_id_mismatch_poisons_join():
    r = cp.build_controller_presence(
        device_id=_DEV,
        session_id="sessA",
        ioid=_ioid(),
        poep_live_summary=_poep(sid="sessB", ok=True),
    )
    assert r.verdict == cp.UNVERIFIABLE
    assert any("session_id MISMATCH" in n for n in r.notes)


def test_fail_closed_nothing_to_bind():
    r = cp.build_controller_presence()
    assert r.verdict == cp.UNVERIFIABLE
    assert r.identity_bound is False
    assert r.presence_candidate is False


def test_no_commitment_primitive_and_deterministic():
    a = cp.build_controller_presence(
        device_id=_DEV, ioid=_ioid(), poep_live_summary=_poep()
    )
    b = cp.build_controller_presence(
        device_id=_DEV, ioid=_ioid(), poep_live_summary=_poep()
    )
    assert a.to_json() == b.to_json()
    assert not hasattr(a, "commitment")
    assert "domain_tag" not in a.to_dict()
    assert a.schema == cp.SCHEMA


def test_or_merge_refused_even_if_caller_wants_single_ok():
    """There is no API for a merged bool — dual fields are the only truth."""
    r = cp.build_controller_presence(device_id=_DEV, ioid=_ioid())
    d = r.to_dict()
    assert "ok" not in d
    assert "overall_pass" not in d
    # Callers must AND themselves; IDENTITY_ONLY must not look like full join
    assert d["identity_bound"] is True
    assert d["presence_candidate"] is False
    assert d["verdict"] == cp.IDENTITY_ONLY
