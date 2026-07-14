"""WA-R04 (Q-C2) — bound_kills rides KAS to_dict ONLY, commitment byte-stable.

The middle authorship layer (WITNESSED ⊂ BOUND ⊂ AUTHORED) gets a durable home on the KAS record so
the scorecard can show `bound: N [MEASURED]` instead of ABSENT — WITHOUT moving any commitment. This
is the same byte-stable pattern session_id used; these tests are the guardrail that keeps bound_kills
out of the frozen preimage forever.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from l9_presence.kill_authorship_session import build_session_record


def _rec(bound):
    return build_session_record(
        session_label="wa_r04", handle="Qortrola30",
        composites=[{"verdict": "AUTHORED_PRESENT", "composite_score": 0.9, "anchor": "seg3", "ts_ms": 1000}],
        hygiene={"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "screen_ntp"},
        bound_kills=bound)


def test_commitment_byte_identical_regardless_of_bound_kills():
    # THE guardrail: adding/changing bound_kills must NEVER move the commitment.
    none_rec = _rec(None)
    set_rec = _rec(3)
    assert none_rec.commitment() == set_rec.commitment()
    assert none_rec.canonical_bytes() == set_rec.canonical_bytes()


def test_bound_kills_absent_from_body_dict_present_in_to_dict():
    rec = _rec(3)
    assert "bound_kills" not in rec.body_dict()          # NEVER in the commitment preimage
    assert rec.to_dict()["bound_kills"] == 3             # present in the reporting projection


def test_bound_kills_defaults_none_backward_compatible():
    # A record built without the kwarg (pre-R04 call shape) reads None, not a fabricated 0.
    rec = build_session_record(
        session_label="legacy", handle="Qortrola30",
        composites=[], hygiene={"frame_errs": 0, "frame_stall_s": 0.0, "ts_source": "screen_ntp"})
    assert rec.to_dict()["bound_kills"] is None


def test_commitment_matches_pre_r04_shape():
    # A record with bound_kills set must commit identically to the SAME record with the field never
    # touched — proving pre-R04 on-disk commitments stay valid.
    import dataclasses
    with_bound = _rec(7)
    stripped = dataclasses.replace(with_bound, bound_kills=None)
    assert with_bound.commitment() == stripped.commitment()
