"""Tests for l9_presence.posp — PoSP (QORTROLLER-POSP-v0 CANDIDATE), the U2a reference-and-bind wrapper.

Pins: the closed fail-closed verdict enum; the ANTI-ASSERTION rail (an id MISMATCH is UNVERIFIABLE, never
papered into PARTIAL — PoSP refuses to assert a join it cannot verify); pre-U1 artifacts (null id) bind
honestly as PARTIAL with a note; both events_roots are NAMED fields (design §2.3); determinism; and the
no-commitment-primitive design (the record deliberately has no commitment()/domain tag — its integrity is
the commitments it REFERENCES)."""
from __future__ import annotations

from l9_presence import posp


_SID = "a" * 64


def _kas(sid=_SID, root="cd" * 32):
    return {"commitment": "fb" * 32, "verdict": "AUTHORED_SESSION", "authored_kills": 15,
            "kas_domain_tag": "QORTROLLER-KAS-v0", "session_id": sid, "span_ms": [1000.0, 2000.0],
            "events_root": root}


def _rows(sid=_SID, n=3, device="dev1"):
    return [{"session_id": sid, "record_hash_hex": f"r{i:02d}", "device_id": device} for i in range(n)]


def test_synchronized_happy_path_and_named_roots():
    r = posp.build_posp(session_id=_SID, session_display="lbl_1", kas_record=_kas(),
                        fusion_rows=_rows(), archive_manifest={"schema": "qortroller-session-archive-v1",
                                                               "session_id": _SID, "count": 600})
    assert r.verdict == posp.SYNCHRONIZED
    assert r.kas["id_verified"] and r.fusion["id_verified"] and r.archive["id_verified"]
    assert r.device_id == "dev1" and r.span_ms == [1000.0, 2000.0]
    # §2.3: BOTH roots named; perception honestly None when that stack didn't run
    assert r.events_roots == {"kas_session_root": "cd" * 32, "retina_perception_root": None}
    d = r.to_dict()
    assert d["schema"] == "qortroller-posp-v0" and d["fusion"]["record_hashes"] == ["r00", "r01", "r02"]


def test_mismatch_is_unverifiable_never_partial():
    # THE anti-assertion rail: a WRONG id on either surface poisons the whole record.
    bad_kas = posp.build_posp(session_id=_SID, kas_record=_kas(sid="b" * 64), fusion_rows=_rows())
    assert bad_kas.verdict == posp.UNVERIFIABLE and any("MISMATCH" in n for n in bad_kas.notes)
    bad_row = posp.build_posp(session_id=_SID, kas_record=_kas(),
                              fusion_rows=_rows() + [{"session_id": "c" * 64, "record_hash_hex": "rX"}])
    assert bad_row.verdict == posp.UNVERIFIABLE
    bad_arch = posp.build_posp(session_id=_SID, kas_record=_kas(), fusion_rows=_rows(),
                               archive_manifest={"schema": "s", "session_id": "d" * 64})
    assert bad_arch.verdict == posp.UNVERIFIABLE


def test_pre_u1_artifacts_bind_as_partial_with_note():
    # A pre-U1 KAS record (session_id None) is bound by label/span HONESTLY: PARTIAL, never SYNCHRONIZED.
    r = posp.build_posp(session_id=_SID, kas_record=_kas(sid=None), fusion_rows=_rows())
    assert r.verdict == posp.PARTIAL_SURFACES
    assert r.kas["id_verified"] is False and r.fusion["id_verified"] is True
    assert any("pre-U1" in n for n in r.notes)
    # and single-surface sessions are PARTIAL too (one surface present, honest)
    only_kas = posp.build_posp(session_id=_SID, kas_record=_kas())
    assert only_kas.verdict == posp.PARTIAL_SURFACES


def test_fail_closed_on_nothing_to_bind():
    assert posp.build_posp(session_id=None).verdict == posp.UNVERIFIABLE
    assert posp.build_posp(session_id=_SID).verdict == posp.UNVERIFIABLE          # no surfaces at all
    arch_only = posp.build_posp(session_id=_SID,
                                archive_manifest={"schema": "s", "session_id": _SID, "count": 1})
    assert arch_only.verdict == posp.UNVERIFIABLE     # archive is provenance, not a proof surface


def test_deterministic_and_no_commitment_primitive():
    a = posp.build_posp(session_id=_SID, kas_record=_kas(), fusion_rows=_rows())
    b = posp.build_posp(session_id=_SID, kas_record=_kas(), fusion_rows=_rows())
    assert a.to_json() == b.to_json()                 # deterministic
    # REFERENCE-AND-BIND design: deliberately NO commitment()/domain tag on the record itself.
    assert not hasattr(a, "commitment") and "domain_tag" not in a.to_dict()


def test_multi_device_rows_are_flagged():
    rows = _rows(n=2, device="dev1") + _rows(n=1, device="dev2")
    r = posp.build_posp(session_id=_SID, kas_record=_kas(), fusion_rows=rows)
    assert r.device_id is None and any("distinct device_ids" in n for n in r.notes)
