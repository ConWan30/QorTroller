"""TRL-1 A3 - assertion-plane adversarial hardening (forge-your-own, AH-1 style).

We forge our own PoSP records against the tournament-operator verifier. Confirms
the structural/consistency attacks are CAUGHT, banks the two GAPS this cycle FOUND
AND FIXED (bogus commitment, impossible fusion counts), and pins the honest
OUT-OF-SCOPE ceiling: a fully-fabricated but internally-consistent record passes
STRUCTURAL verification - deep KAS re-derivation is deferred by design.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.posp_verifier import verify_posp_record

_M17 = REPO_ROOT / "audits" / "posp_record_match17_rp_fixb3_2026-07-08.json"


def _base() -> dict:
    return json.loads(_M17.read_text(encoding="utf-8"))


def _check(rep, name):
    for c in rep.checks:
        if c.name == name:
            return c.passed
    return None


# -- regression: the real record must stay VERIFIED (the I1 rung depends on it) --

def test_real_m17_still_verified():
    assert verify_posp_record(_base()).overall == "VERIFIED"


# -- CAUGHT: structural / consistency forgeries ----------------------------

def test_P1_wrong_schema_caught():
    b = _base(); b["schema"] = "qortroller-posp-v99"
    assert verify_posp_record(b).overall == "SCHEMA_ERROR"


def test_P2_unknown_verdict_caught():
    b = _base(); b["verdict"] = "TOTALLY_SYNCED"
    assert verify_posp_record(b).overall == "FAILED"


def test_P3_missing_session_id_caught():
    b = _base(); b["session_id"] = None
    assert verify_posp_record(b).overall == "FAILED"


def test_P4_synchronized_without_both_surfaces_caught():
    b = _base(); b["fusion"]["id_verified"] = False       # claim SYNCHRONIZED, only one surface
    rep = verify_posp_record(b)
    assert rep.overall == "FAILED"
    assert _check(rep, "verdict_consistent") is False


def test_P5_empty_commitment_caught():
    b = _base(); b["kas"]["commitment"] = ""
    assert verify_posp_record(b).overall == "FAILED"


# -- GAP-FOUND-AND-FIXED (this cycle) --------------------------------------

def test_P6_bogus_commitment_now_caught():
    """Was a gap: a non-empty but bogus 'commitment':'x' reached VERIFIED. Fixed by
    the 64-hex well-formedness check."""
    b = _base(); b["kas"]["commitment"] = "x"
    rep = verify_posp_record(b)
    assert rep.overall == "FAILED"
    assert _check(rep, "kas_commitment_wellformed") is False


def test_P7_impossible_fusion_counts_now_caught():
    """Was a gap: id_verified=True with n_id_verified=0 (or > n_rows) reached
    VERIFIED. Fixed by the count-sanity check."""
    b = _base(); b["fusion"]["n_id_verified"] = 0          # claims verified, but zero rows
    rep = verify_posp_record(b)
    assert rep.overall == "FAILED"
    assert _check(rep, "fusion_counts_sane") is False

    b2 = _base(); b2["fusion"]["n_id_verified"] = b2["fusion"]["n_rows"] + 5   # more than exist
    assert verify_posp_record(b2).overall == "FAILED"


# -- OUT-OF-SCOPE-DOCUMENTED (the honest ceiling) --------------------------

def test_P8_fabricated_but_consistent_passes_structural_by_design():
    """A hand-forged record with all the right booleans, a well-formed (but FAKE)
    commitment, and sane counts PASSES structural verification. This is the honest
    limit: the verifier is structural + consistency, NOT deep re-derivation (KAS
    file / archive SHA-256 cross-ref are deferred). Test-pinned so the limitation is
    never a silent gap."""
    forged = {
        "schema": "qortroller-posp-v0",
        "verdict": "SYNCHRONIZED",
        "session_id": "f" * 64,
        "kas": {"id_verified": True, "commitment": "ab" * 32, "verdict": "AUTHORED_SESSION"},
        "fusion": {"id_verified": True, "n_id_verified": 10, "n_rows": 10},
    }
    # VERIFIED at the structural bar - deep re-derivation (the real defense) is card/
    # chain-gated; documented in posp_verifier's OUT-OF-SCOPE note.
    assert verify_posp_record(forged).overall == "VERIFIED"
