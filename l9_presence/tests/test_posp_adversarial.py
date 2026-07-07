"""G4 Adversarial Harness — session-identity nonce properties, anti-splice rail,
verdict-integrity fix, and live-artifact cross-validation.

Four attack layers:
  Layer 1 — Session-identity nonce properties (T-ADV-SID-1..4)
  Layer 2 — Anti-splice rail on build_posp (T-ADV-SPLICE-1..4)
  Layer 3 — Verdict-integrity / is_synchronized() fix (T-ADV-VERDICT-1..2)
  Layer 4 — Live artifact cross-validation (T-ADV-LIVE-1..2)
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

from l9_presence.posp import PARTIAL_SURFACES, SYNCHRONIZED, UNVERIFIABLE, build_posp
from l9_presence.session_identity import derive_session_id, parse_daemon_log_name
from sdk.vapi_sdk import VAPIPoSPRecord

AUDITS = pathlib.Path(__file__).parents[2] / "audits"
M13_POSP = AUDITS / "posp_record_match13_hdmi_direct_2026-07-06.json"
M11_POSP = AUDITS / "posp_record_match11_kas_validation_2026-07-06.json"


# --- Layer 1: Session-identity nonce properties ---


def test_adv_sid_1_determinism():
    """T-ADV-SID-1: derive_session_id is pure — same inputs always yield same id."""
    sid_a = derive_session_id("match13", 1783385280)
    sid_b = derive_session_id("match13", 1783385280)
    assert sid_a == sid_b
    expected = hashlib.sha256("match13_1783385280".encode("utf-8")).hexdigest()
    assert sid_a == expected


def test_adv_sid_2_adjacent_stamp_uniqueness():
    """T-ADV-SID-2: adjacent stamps (differing by 1 second) produce distinct ids."""
    sid_a = derive_session_id("match", 1783385280)
    sid_b = derive_session_id("match", 1783385281)
    assert sid_a != sid_b


def test_adv_sid_3_log_name_round_trip():
    """T-ADV-SID-3: parse_daemon_log_name -> derive_session_id matches direct derivation."""
    log = "retina_daemon_match13_hdmi_direct_1783385280.log"
    parsed = parse_daemon_log_name(log)
    assert parsed is not None
    label, stamp = parsed
    sid_from_log = derive_session_id(label, stamp)
    sid_direct = derive_session_id("match13_hdmi_direct", 1783385280)
    assert sid_from_log == sid_direct


def test_adv_sid_4_label_is_load_bearing():
    """T-ADV-SID-4: same stamp, different labels -> distinct ids."""
    sid_a = derive_session_id("match11", 1783385280)
    sid_b = derive_session_id("match13", 1783385280)
    assert sid_a != sid_b


# --- Layer 2: Anti-splice rail ---


def _make_kas(session_id: str, authored_kills: int = 3) -> dict:
    return {
        "commitment": "a" * 64,
        "verdict": "VERIFIED_KILLS",
        "authored_kills": authored_kills,
        "events_root": "b" * 64,
        "session_id": session_id,
        "id_verified": True,
    }


def _make_fusion_row(session_id: str) -> dict:
    return {"session_id": session_id, "record_hash_hex": "c" * 64}


def _make_archive(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "schema": "qortroller-session-archive-v1",
        "count": 1,
        "dir": "retina_kf_archive/test",
    }


def test_adv_splice_1_kas_nqpv_cross_session():
    """T-ADV-SPLICE-1: KAS from session A + NQPV fusion rows from session B -> UNVERIFIABLE."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_b), _make_fusion_row(sid_b)]
    record = build_posp(
        session_id=sid_a,
        session_display="session_a_1000000",
        kas_record=kas,
        fusion_rows=fusion_rows,
    )
    assert record.verdict == UNVERIFIABLE, (
        f"Cross-session surface mix must be UNVERIFIABLE, got {record.verdict}"
    )


def test_adv_splice_2_partial_injection():
    """T-ADV-SPLICE-2: majority rows from session A + ONE row from session B -> UNVERIFIABLE."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_a)] * 4 + [_make_fusion_row(sid_b)]
    record = build_posp(
        session_id=sid_a,
        session_display="session_a_1000000",
        kas_record=kas,
        fusion_rows=fusion_rows,
    )
    assert record.verdict == UNVERIFIABLE, (
        f"Single foreign fusion row must poison to UNVERIFIABLE, got {record.verdict}"
    )


def test_adv_splice_3_archive_swap():
    """T-ADV-SPLICE-3: correct KAS + fusion (session A) + archive from session B -> UNVERIFIABLE."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_a)] * 3
    archive = _make_archive(sid_b)
    record = build_posp(
        session_id=sid_a,
        session_display="session_a_1000000",
        kas_record=kas,
        fusion_rows=fusion_rows,
        archive_manifest=archive,
    )
    assert record.verdict == UNVERIFIABLE, (
        f"Archive session_id mismatch must poison to UNVERIFIABLE, got {record.verdict}"
    )


def test_adv_splice_4_three_way_cross():
    """T-ADV-SPLICE-4: KAS=A, fusion=B, archive=C (three distinct sessions) -> UNVERIFIABLE."""
    sid_a = derive_session_id("session_a", 1000000)
    sid_b = derive_session_id("session_b", 2000000)
    sid_c = derive_session_id("session_c", 3000000)
    kas = _make_kas(sid_a)
    fusion_rows = [_make_fusion_row(sid_b)]
    archive = _make_archive(sid_c)
    record = build_posp(
        session_id=sid_a,
        session_display="session_a_1000000",
        kas_record=kas,
        fusion_rows=fusion_rows,
        archive_manifest=archive,
    )
    assert record.verdict == UNVERIFIABLE, (
        f"Three-way cross-session splice must be UNVERIFIABLE, got {record.verdict}"
    )


# --- Layer 3: Verdict-integrity (is_synchronized() fix) ---


def test_adv_verdict_1_forged_kas_not_verified():
    """T-ADV-VERDICT-1: forged dict claiming SYNCHRONIZED but kas_id_verified=False."""
    forged = {
        "verdict": "SYNCHRONIZED",
        "session_id": "a" * 64,
        "session_display": "forged_0",
        "device_id": None,
        "span_ms": None,
        "kas": {
            "commitment": "b" * 64,
            "verdict": "VERIFIED_KILLS",
            "authored_kills": 5,
            "id_verified": False,
        },
        "fusion": {
            "n_rows": 10,
            "n_id_verified": 10,
            "record_hashes": [],
            "id_verified": True,
        },
        "events_roots": {},
        "archive": None,
        "notes": [],
        "schema": "qortroller-posp-v0",
        "advisory": True,
    }
    record = VAPIPoSPRecord.from_dict(forged)
    assert not record.is_synchronized(), (
        "is_synchronized() must return False when kas_id_verified=False, "
        "regardless of the verdict string"
    )


def test_adv_verdict_2_forged_fusion_not_verified():
    """T-ADV-VERDICT-2: forged dict claiming SYNCHRONIZED but fusion_id_verified=False."""
    forged = {
        "verdict": "SYNCHRONIZED",
        "session_id": "a" * 64,
        "session_display": "forged_0",
        "device_id": None,
        "span_ms": None,
        "kas": {
            "commitment": "b" * 64,
            "verdict": "VERIFIED_KILLS",
            "authored_kills": 5,
            "id_verified": True,
        },
        "fusion": {
            "n_rows": 10,
            "n_id_verified": 0,
            "record_hashes": [],
            "id_verified": False,
        },
        "events_roots": {},
        "archive": None,
        "notes": [],
        "schema": "qortroller-posp-v0",
        "advisory": True,
    }
    record = VAPIPoSPRecord.from_dict(forged)
    assert not record.is_synchronized(), (
        "is_synchronized() must return False when fusion_id_verified=False, "
        "regardless of the verdict string"
    )


# --- Layer 4: Live artifact cross-validation ---


@pytest.mark.skipif(not M13_POSP.exists(), reason="M13 PoSP artifact not present (CI)")
def test_adv_live_1_m13_satisfies_predicate():
    """T-ADV-LIVE-1: M13 PoSP artifact (from_file) -> is_synchronized() True."""
    record = VAPIPoSPRecord.from_file(str(M13_POSP))
    assert record.is_synchronized(), "M13 must be SYNCHRONIZED"
    assert record.kas_id_verified is True
    assert record.fusion_id_verified is True
    assert record.kas_authored_kills == 8
    assert record.n_fusion_rows > 0


@pytest.mark.skipif(
    not M13_POSP.exists() or not M11_POSP.exists(),
    reason="Live PoSP artifacts not present (CI)",
)
def test_adv_live_2_cross_match_session_id_mismatch():
    """T-ADV-LIVE-2: M11 session_id as wrapper + M13 data -> UNVERIFIABLE."""
    d11 = json.loads(M11_POSP.read_text(encoding="utf-8"))
    d13 = json.loads(M13_POSP.read_text(encoding="utf-8"))
    sid_11 = d11["session_id"]
    sid_13 = d13["session_id"]
    assert sid_11 != sid_13, "Test premise: M11 and M13 must have distinct session_ids"
    kas_m13 = dict(d13["kas"])
    kas_m13["session_id"] = sid_13
    fusion_rows = [{"session_id": sid_13, "record_hash_hex": "0" * 64}]
    record = build_posp(
        session_id=sid_11,
        session_display="match11_wrapper",
        kas_record=kas_m13,
        fusion_rows=fusion_rows,
    )
    assert record.verdict == UNVERIFIABLE, (
        f"Cross-match session_id mismatch must be UNVERIFIABLE, got {record.verdict}"
    )