"""Tests for session_continuum composition (RWM × U1 × ioID × PoEP × stack).

Pins: multi-bit never OR-merge; device/session mismatch → UNVERIFIABLE;
optical alone ≠ identity/presence; stack_cited never mints SYNCHRONIZED;
no commitment primitive; advances_* always False.
"""
from __future__ import annotations

import hashlib

from l9_presence import session_continuum as sc

_DEV = sc.EDGE_DEVICE_ID_LIVE
_OTHER = "20b37e1c" + "ab" * 28
_SID = hashlib.sha256(b"cfb_rwm_live_10_1784953588").hexdigest()
_DISPLAY = "cfb_rwm_live_10_1784953588"
_TIP = "e7" * 32


def _rwm(*, verified=True, sid=_SID, dev=_DEV, tip=_TIP):
    return {
        "session_id": sid,
        "device_id_hex": dev,
        "l0_chain_tip_hex": tip,
        "l0_verified": verified,
        "n_frames": 367,
        "schema": "qortroller-rwm-session-chain-v0",
    }


def _ioid(dev=_DEV, token_id=498):
    return {
        "token_id": token_id,
        "did": "did:io:0x0cf36db5",
        "tba": "0xFCee237789FA91a141781aFB574ADAbcA2660e7b",
        "registered_device_id": dev,
    }


def _poep(dev=_DEV, ok=True, sid=_SID):
    return {
        "presence_session_candidate_ok": ok,
        "device_id": dev,
        "session_id": sid,
        "live_seal": "ab" * 32,
    }


def _stack_nov2(sid=_SID, tip=_TIP, ok=True):
    return {
        "nov2_bind": {
            "session_id": sid,
            "bind_ok": ok,
            "ok": ok,
            "l0_chain_tip_hex": tip,
            "bind_kind": "none",
        }
    }


def test_optical_session_rwm_only():
    r = sc.build_session_continuum(rwm=_rwm(), session_display=_DISPLAY)
    assert r.verdict == sc.OPTICAL_SESSION
    assert r.optical_rwm is True
    assert r.session_join is True
    assert r.device_join is True
    assert r.identity_bound is False
    assert r.presence_candidate is False
    assert any("does NOT imply identity" in n for n in r.notes)
    d = r.to_dict()
    assert d["advances_poep_enabled"] is False
    assert d["advances_l6b_enabled"] is False
    assert d["advisory"] is True


def test_optical_identity_does_not_imply_presence():
    r = sc.build_session_continuum(
        rwm=_rwm(), session_display=_DISPLAY, ioid=_ioid()
    )
    assert r.verdict == sc.OPTICAL_IDENTITY
    assert r.identity_bound is True
    assert r.presence_candidate is False
    assert r.verdict != sc.SYNCHRONIZED_CONTINUUM


def test_optical_presence_does_not_imply_identity():
    r = sc.build_session_continuum(
        rwm=_rwm(), session_display=_DISPLAY, poep_live_summary=_poep()
    )
    assert r.verdict == sc.OPTICAL_PRESENCE
    assert r.presence_candidate is True
    assert r.identity_bound is False


def test_synchronized_continuum_all_bits():
    r = sc.build_session_continuum(
        rwm=_rwm(),
        session_display=_DISPLAY,
        ioid=_ioid(),
        poep_live_summary=_poep(),
    )
    assert r.verdict == sc.SYNCHRONIZED_CONTINUUM
    assert r.optical_rwm and r.identity_bound and r.presence_candidate


def test_stack_cited_does_not_mint_synchronized():
    r = sc.build_session_continuum(
        rwm=_rwm(),
        session_display=_DISPLAY,
        stack=_stack_nov2(),
    )
    assert r.verdict == sc.OPTICAL_SESSION
    assert r.stack_cited is True
    assert r.verdict != sc.SYNCHRONIZED_CONTINUUM
    assert any("does NOT OR-merge" in n for n in r.notes)


def test_device_mismatch_unverifiable():
    r = sc.build_session_continuum(
        rwm=_rwm(dev=_DEV),
        ioid=_ioid(dev=_OTHER),
        session_display=_DISPLAY,
    )
    assert r.verdict == sc.UNVERIFIABLE
    assert r.optical_rwm is False
    assert r.identity_bound is False
    assert any("MISMATCH" in n for n in r.notes)


def test_session_mismatch_unverifiable():
    r = sc.build_session_continuum(
        rwm=_rwm(sid=_SID),
        poep_live_summary=_poep(sid="deadbeef" * 8),
        session_display=_DISPLAY,
    )
    assert r.verdict == sc.UNVERIFIABLE
    assert any("session_id MISMATCH" in n for n in r.notes)


def test_u1_display_mismatch_breaks_join():
    r = sc.build_session_continuum(
        rwm=_rwm(),
        session_display="wrong_label_0",
    )
    assert r.verdict == sc.UNVERIFIABLE
    assert any("session_display MISMATCH" in n for n in r.notes)


def test_unverified_l0_not_optical():
    r = sc.build_session_continuum(rwm=_rwm(verified=False), session_display=_DISPLAY)
    assert r.optical_rwm is False
    assert r.verdict in (sc.PARTIAL, sc.STACK_WITHOUT_OPTICAL, sc.UNVERIFIABLE)


def test_stack_without_optical():
    r = sc.build_session_continuum(
        device_id=_DEV,
        session_id=_SID,
        ioid=_ioid(),
        stack=_stack_nov2(),
    )
    assert r.optical_rwm is False
    assert r.verdict == sc.STACK_WITHOUT_OPTICAL
    assert r.identity_bound is True


def test_fail_closed_empty():
    r = sc.build_session_continuum()
    assert r.verdict == sc.UNVERIFIABLE


def test_verify_continuum_stable():
    r = sc.build_session_continuum(
        rwm=_rwm(),
        session_display=_DISPLAY,
        ioid=_ioid(),
        stack=_stack_nov2(),
    )
    vr = sc.verify_continuum(r)
    assert vr["ok"] is True, vr
    vr2 = sc.verify_continuum(r.to_dict())
    assert vr2["ok"] is True


def test_no_commitment_method():
    r = sc.build_session_continuum(rwm=_rwm(), session_display=_DISPLAY)
    assert not hasattr(r, "commitment")
    assert r.schema == sc.SCHEMA
