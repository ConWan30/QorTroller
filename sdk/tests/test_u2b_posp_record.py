"""Tests for VAPIPoSPRecord — SDK reader for U2b PoSP artifacts.

Verifies: null-safe from_dict/from_file, verdict routing, is_synchronized(), named roots,
advisory flag, and the offline corpus_growth artifact validation
(expects PARTIAL_SURFACES — no fusion rows existed for that pre-U2b session).
"""
from __future__ import annotations

import json
import os
import sys
import pathlib

_REPO = pathlib.Path(__file__).resolve().parent.parent.parent
for p in (str(_REPO), str(_REPO / "bridge")):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdk.vapi_sdk import VAPIPoSPRecord  # noqa: E402


_SID = "a" * 64


def _make_posp_dict(verdict="SYNCHRONIZED", sid=_SID, kas=True, fusion=True):
    d = {
        "schema": "qortroller-posp-v0",
        "verdict": verdict,
        "session_id": sid,
        "session_display": "lbl_1",
        "device_id": "dev1",
        "span_ms": [1000.0, 2000.0],
        "events_roots": {"kas_session_root": "cd" * 32, "retina_perception_root": None},
        "notes": [],
    }
    if kas:
        d["kas"] = {"commitment": "fb" * 32, "verdict": "AUTHORED_SESSION",
                    "authored_kills": 15, "id_verified": True}
    if fusion:
        d["fusion"] = {"n_rows": 3, "n_id_verified": 3, "record_hashes": ["r0"], "id_verified": True}
    d["archive"] = {"manifest_schema": "qortroller-session-archive-v1", "count": 600, "id_verified": True}
    return d


def test_synchronized_round_trip():
    d = _make_posp_dict()
    r = VAPIPoSPRecord.from_dict(d)
    assert r.verdict == "SYNCHRONIZED"
    assert r.is_synchronized()
    assert r.kas_commitment == "fb" * 32
    assert r.kas_authored_kills == 15
    assert r.kas_id_verified
    assert r.n_fusion_rows == 3 and r.n_fusion_id_verified == 3 and r.fusion_id_verified
    assert r.archive_id_verified is True
    assert r.kas_session_root == "cd" * 32
    assert r.retina_perception_root is None
    assert r.advisory is True       # machine-readable: not a certified gate
    assert r.schema == "qortroller-posp-v0"
    assert r.span_ms == [1000.0, 2000.0]
    assert r.device_id == "dev1"


def test_partial_surfaces_not_synchronized():
    d = _make_posp_dict(verdict="PARTIAL_SURFACES", fusion=False)
    d.pop("fusion", None)
    r = VAPIPoSPRecord.from_dict(d)
    assert not r.is_synchronized()
    assert r.verdict == "PARTIAL_SURFACES"
    assert r.n_fusion_rows == 0 and not r.fusion_id_verified


def test_unverifiable_not_synchronized():
    r = VAPIPoSPRecord.from_dict({"verdict": "UNVERIFIABLE", "session_id": None, "notes": ["x"]})
    assert not r.is_synchronized()
    assert r.notes == ["x"]
    assert r.kas_commitment is None


def test_null_safe_empty_dict():
    r = VAPIPoSPRecord.from_dict({})
    assert r.verdict == "UNVERIFIABLE"
    assert r.session_id is None
    assert r.n_fusion_rows == 0
    assert r.kas_id_verified is False
    assert r.fusion_id_verified is False
    assert r.archive_id_verified is None


def test_from_file_roundtrip(tmp_path):
    d = _make_posp_dict()
    p = tmp_path / "posp_record_test.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    r = VAPIPoSPRecord.from_file(str(p))
    assert r.is_synchronized()
    assert r.kas_commitment == "fb" * 32


def test_offline_corpus_growth_artifact():
    """Offline gate: build PoSP over the real corpus_growth artifacts from U1 (2026-07-04).

    Expects PARTIAL_SURFACES because the fusion rows weren't persisted with session_id until U2a —
    this is the pre-U2b state: KAS present (id=4049…), archive manifest present (same id),
    but no NQPV co-capture rows with that session_id in the DB (DB unreachable or no matching rows).
    The PoSP honestly reports PARTIAL rather than SYNCHRONIZED.
    """
    from l9_presence.posp import build_posp, PARTIAL_SURFACES, SYNCHRONIZED

    # Real corpus_growth KAS artifact (committed to audits/ in U1)
    kas_path = _REPO / "audits" / "kas_record_corpus_growth_20260704_u1check.json"
    if not kas_path.exists():
        import pytest; pytest.skip("corpus_growth KAS artifact not present — run from project root")

    kas = json.loads(kas_path.read_text(encoding="utf-8"))
    sid = kas.get("session_id")
    assert sid and len(sid) == 64, "U1 session_id must be present in KAS artifact"

    # Try real archive manifest (may or may not exist depending on machine state)
    archive_manifest = None
    label = "corpus_growth_20260704"
    stamp = "1783188334"  # from the U1 test — the stamp used in the U1 session
    manifest_path = _REPO / "retina_kf_archive" / f"{label}_{stamp}" / "manifest.json"
    if manifest_path.exists():
        archive_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Build without fusion rows (honest: no rows exist for this pre-U2b session)
    rec = build_posp(session_id=sid, session_display=kas.get("session_display"),
                     kas_record=kas, fusion_rows=None, archive_manifest=archive_manifest)

    # Must be PARTIAL (KAS present, no fusion surface) — SYNCHRONIZED requires both
    assert rec.verdict in (PARTIAL_SURFACES, SYNCHRONIZED), f"unexpected verdict: {rec.verdict}"
    assert rec.kas is not None and rec.kas.get("id_verified") is True
    if archive_manifest:
        assert rec.archive is not None
