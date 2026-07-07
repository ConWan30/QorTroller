"""Arc A — PoSP record verifier tests.

Pins: SYNCHRONIZED=VERIFIED; wrong schema=SCHEMA_ERROR; missing kas_commitment=FAILED;
PARTIAL_SURFACES=PARTIAL; SYNCHRONIZED with kas_id=False=FAILED; missing session_id=FAILED.
"""
from __future__ import annotations

from l9_presence.posp_verifier import verify_posp_record, EXPECTED_SCHEMA


def _record(verdict="SYNCHRONIZED", kas_id=True, fusion_id=True,
            kas_commitment="ab" * 32, n_rows=358, n_id=358,
            session_id="a" * 64):
    """Synthetic PoSP record factory matching the qortroller-posp-v0 schema."""
    return {
        "schema": EXPECTED_SCHEMA,
        "verdict": verdict,
        "session_id": session_id,
        "kas": {
            "id_verified": kas_id,
            "commitment": kas_commitment,
            "verdict": "AUTHORED_SESSION",
            "authored_kills": 8,
        },
        "fusion": {
            "id_verified": fusion_id,
            "n_id_verified": n_id,
            "n_rows": n_rows,
            "record_hashes": ["r01", "r02"],
        },
        "archive": {"id_verified": True, "count": 524},
        "events_roots": {"kas_session_root": "cd" * 32, "retina_perception_root": None},
        "notes": [],
    }


def test_synchronized_is_verified():
    """Happy path: SYNCHRONIZED + both id_verified + commitment → VERIFIED."""
    rep = verify_posp_record(_record())
    assert rep.overall == "VERIFIED"
    assert rep.passed()


def test_wrong_schema_is_schema_error():
    r = _record()
    r["schema"] = "unknown-schema-v99"
    rep = verify_posp_record(r)
    assert rep.overall == "SCHEMA_ERROR"
    assert not rep.passed()


def test_missing_kas_commitment_fails():
    """SYNCHRONIZED with empty kas.commitment → FAILED (the binding artifact is absent)."""
    rep = verify_posp_record(_record(kas_commitment=""))
    assert rep.overall == "FAILED"
    assert not rep.passed()
    commitment_check = next(c for c in rep.checks if c.name == "kas_commitment_present")
    assert not commitment_check.passed


def test_partial_surfaces_is_partial():
    """PARTIAL_SURFACES: kas id-verified but fusion not → PARTIAL."""
    rep = verify_posp_record(_record(verdict="PARTIAL_SURFACES", fusion_id=False, n_id=0))
    assert rep.overall == "PARTIAL"
    assert not rep.passed()


def test_synchronized_without_kas_id_fails():
    """SYNCHRONIZED claimed but kas.id_verified=False → inconsistent → FAILED."""
    rep = verify_posp_record(_record(verdict="SYNCHRONIZED", kas_id=False))
    assert rep.overall == "FAILED"
    consistency_check = next(c for c in rep.checks if c.name == "verdict_consistent")
    assert not consistency_check.passed


def test_missing_session_id_fails():
    """Missing session_id (the U1 join key) → FAILED."""
    rep = verify_posp_record(_record(session_id=None))
    assert rep.overall == "FAILED"
    sid_check = next(c for c in rep.checks if c.name == "session_id_present")
    assert not sid_check.passed
