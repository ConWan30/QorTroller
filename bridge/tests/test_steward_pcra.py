"""A2A-STEWARD-EVOLVE B1 — Guardian PCRA tests. Pins the three v0 residue detectors + the honest rails:
overclaim fires only when the oracle DENIES the asserted capability (no false positive when the claim is
backed); drafts are DRAFTS (the output says so, never an act); no self-grading.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_pcra import (
    SCHEMA,
    detect_ceiling_overclaim,
    detect_residue,
    detect_stale_anchor,
    detect_unbanked_build,
)


# --- CEILING_OVERCLAIM ------------------------------------------------------------------------------

def test_overclaim_fires_when_oracle_denies_the_claim():
    surfaces = [{"path": "docs/a2a/x.md", "text": "we can now say presence is proven and flip PoEP"}]
    out = detect_ceiling_overclaim(surfaces, {"poep_enabled": False})
    assert len(out) == 1
    f = out[0]
    assert f.residue_class == "CEILING_OVERCLAIM"
    assert f.measured_vs_claimed["oracle_value"] is False
    assert "poep_enabled" in f.claim_id


def test_no_overclaim_when_oracle_backs_the_claim():
    # if the flag were actually True, asserting it is NOT an overclaim -> zero false positive
    surfaces = [{"path": "d.md", "text": "presence is proven"}]
    assert detect_ceiling_overclaim(surfaces, {"poep_enabled": True}) == []


def test_honest_negative_prose_does_not_trip():
    # the dominant real-world false positive: honest-negative docs that NAME the flip while refusing it
    surfaces = [{"path": "d.md", "text": "poep_enabled stays False; the flip to true is NOT earned"}]
    assert detect_ceiling_overclaim(surfaces, {"poep_enabled": False}) == []


def test_definitional_hypothetical_context_does_not_trip():
    # discussing/defining the claim (not asserting it happened) must not trip -> the negation/hedge guard
    surfaces = [
        {"path": "a.md", "text": "**Claim at stake:** poep_enabled=True means CLAIM PRESENCE"},
        {"path": "b.md", "text": "for honest warrant to even propose poep_enabled=True to the operator"},
        {"path": "c.md", "text": "if we flip poep to true later, presence would be claimed"},
    ]
    assert detect_ceiling_overclaim(surfaces, {"poep_enabled": False}) == []


def test_clean_affirmative_assertion_still_trips():
    # a bald assertion with NO negation/hedge nearby is a real overclaim to draft
    surfaces = [{"path": "z.md", "text": "Milestone: presence is proven on the Edge. Shipping."}]
    out = detect_ceiling_overclaim(surfaces, {"poep_enabled": False})
    assert len(out) == 1 and out[0].residue_class == "CEILING_OVERCLAIM"


# --- STALE_ANCHOR ----------------------------------------------------------------------------------

def test_stale_anchor_detects_drift():
    out = detect_stale_anchor({"wallet_iotx": "32.078", "contracts": "66"},
                              {"wallet_iotx": "28.441", "contracts": "69"})
    classes = {f.measured_vs_claimed["anchor"] for f in out}
    assert classes == {"wallet_iotx", "contracts"}
    assert all(f.residue_class == "STALE_ANCHOR" for f in out)


def test_stale_anchor_clean_when_aligned():
    assert detect_stale_anchor({"contracts": "69"}, {"contracts": "69"}) == []


# --- UNBANKED_BUILD --------------------------------------------------------------------------------

def test_unbanked_build_flags_ship_without_banking():
    rounds = [{"path": "docs/a2a/r1.md", "ship": True, "tag": "UC-99"},
              {"path": "docs/a2a/r2.md", "ship": True, "tag": "UC-3"},
              {"path": "docs/a2a/r3.md", "ship": False, "tag": "UC-5"}]
    out = detect_unbanked_build(rounds, banked_tags={"UC-3"})
    tags = {f.measured_vs_claimed["tag"] for f in out}
    assert tags == {"UC-99"}          # UC-3 banked (skip); UC-5 not ship (skip)


# --- aggregate + rails -----------------------------------------------------------------------------

def test_detect_residue_orders_and_labels_drafts_only():
    r = detect_residue(
        surfaces=[{"path": "d.md", "text": "presence is proven"}],
        oracles={"poep_enabled": False},
        claimed_anchors={"contracts": "66"}, live_anchors={"contracts": "69"},
        a2a_rounds=[{"path": "r.md", "ship": True, "tag": "UC-99"}], banked_tags=set())
    assert r["schema"] == SCHEMA and r["steward"] == "guardian" and r["task"] == "PCRA"
    assert r["n_findings"] == 3
    # most-severe first (HIGH overclaim before MED anchor before LOW unbanked)
    sev = [f["severity"] for f in r["findings"]]
    assert sev == sorted(sev, key={"HIGH": 0, "MED": 1, "LOW": 2}.get)
    assert "DRAFTS ONLY" in r["note"] and "self-grading" in r["note"]
    assert r["by_class"]["CEILING_OVERCLAIM"] == 1


def test_empty_inputs_yield_no_findings():
    r = detect_residue(surfaces=[], oracles={}, claimed_anchors={}, live_anchors={},
                       a2a_rounds=[], banked_tags=set())
    assert r["n_findings"] == 0
