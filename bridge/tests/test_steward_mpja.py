"""A2A-STEWARD-EVOLVE B2 — Sentry MPJA tests. Pins the join-completeness verdict + the load-bearing
false-anchored rail (ANCHORED-without-tx = JOIN_BROKEN, never proposed for anchoring) + draft-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_mpja import SCHEMA, evaluate_join

_ROOT = "ab" * 32          # 64-hex
_TX = "0x" + "cd" * 32     # 0x + 64-hex, real tx-hash shape


def _complete(**over):
    base = dict(session_id="s1", kas_verdict="AUTHORED_SESSION", posp_verdict="SYNCHRONIZED",
                ledger_status="PENDING", scorecard_root=_ROOT, w3s_mechanical_ok=True)
    base.update(over)
    return evaluate_join(**base)


def test_complete_join_proposes_anchor_preimage():
    r = _complete()
    assert r["join_verdict"] == "JOIN_COMPLETE"
    assert r["missing"] == [] and r["broken_reasons"] == []
    assert r["proposed_anchor_preimage_hash"] is not None and len(r["proposed_anchor_preimage_hash"]) == 64
    assert r["completeness_bitmap"]["posp_synchronized"] is True
    assert r["completeness_bitmap"]["ledger_anchored"] is False   # pre-anchor complete join is valid


def test_partial_join_when_a_required_surface_missing():
    r = _complete(w3s_mechanical_ok=None)
    assert r["join_verdict"] == "JOIN_PARTIAL"
    assert "w3s_mechanical_ok" in r["missing"]
    assert r["proposed_anchor_preimage_hash"] is None            # never propose anchoring an incomplete join


def test_posp_partial_surfaces_is_not_synchronized():
    r = _complete(posp_verdict="PARTIAL_SURFACES")
    assert r["completeness_bitmap"]["posp_synchronized"] is False
    assert "posp_synchronized" in r["missing"] and r["join_verdict"] == "JOIN_PARTIAL"


def test_false_anchored_is_broken():
    # the load-bearing rail: ledger claims ANCHORED but carries no anchor tx -> BROKEN, never anchored
    r = _complete(ledger_status="ANCHORED", ledger_anchor_tx=None)
    assert r["join_verdict"] == "JOIN_BROKEN"
    assert any("false-anchored" in x for x in r["broken_reasons"])
    assert r["proposed_anchor_preimage_hash"] is None


def test_genuinely_anchored_join_is_complete():
    r = _complete(ledger_status="ANCHORED", ledger_anchor_tx=_TX)
    assert r["join_verdict"] == "JOIN_COMPLETE"
    assert r["completeness_bitmap"]["ledger_anchored"] is True


def test_garbage_anchor_tx_is_broken():
    # grok round-05: a non-tx-shaped "anchor tx" is still a false-anchored claim, not COMPLETE
    r = _complete(ledger_status="ANCHORED", ledger_anchor_tx="not-a-tx")
    assert r["join_verdict"] == "JOIN_BROKEN"
    assert any("malformed anchor tx" in x for x in r["broken_reasons"])
    assert r["proposed_anchor_preimage_hash"] is None


def test_0x_prefixed_root_is_accepted():
    # grok round-05: real roots carry a 0x prefix — must NOT be flagged malformed
    r = _complete(scorecard_root="0x" + _ROOT)
    assert r["join_verdict"] == "JOIN_COMPLETE"
    assert r["completeness_bitmap"]["scorecard_root_bound"] is True


def test_malformed_root_is_broken():
    r = _complete(scorecard_root="not-hex")
    assert r["join_verdict"] == "JOIN_BROKEN"
    assert any("malformed" in x for x in r["broken_reasons"])


def test_preimage_is_deterministic_and_binds_session():
    a = _complete(session_id="sX")
    b = _complete(session_id="sX")
    c = _complete(session_id="sY")
    assert a["proposed_anchor_preimage_hash"] == b["proposed_anchor_preimage_hash"]
    assert a["proposed_anchor_preimage_hash"] != c["proposed_anchor_preimage_hash"]


def test_draft_only_rail_and_schema():
    r = _complete()
    assert r["schema"] == SCHEMA and r["steward"] == "sentry" and r["task"] == "MPJA"
    assert "DRAFT ONLY" in r["note"] and "TWO-KEY" in r["note"] and "never spends IOTX" in r["note"]
    # grok round-05 honesty: note must scope v0 to completeness + structural rails, not content-consistency
    assert "structural" in r["note"] and "v0.1" in r["note"]
