"""A2A-STEWARD-EVOLVE B5 — Steward Challenge Graph tests. Pins the 3 authorized edges, the operator-only
resolution, the SEL-label production, and the load-bearing rail: resolving a challenge scores the TARGET
steward (sourced by the challenger) — issuing a challenge can NEVER raise the challenger's own score.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from bridge.vapi_bridge.steward_challenge_graph import (
    SCHEMA,
    issue_challenge,
    issue_challenges_from_store,
    may_challenge,
    resolve_challenge,
)
from bridge.vapi_bridge.steward_sel import is_external_label


class _Cfg:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _open(challenger="guardian", target="sentry", task="MPJA", draft="d1", basis="join looks overclaimed"):
    return issue_challenge(challenger=challenger, target_steward=target, target_task_class=task,
                           target_draft_id=draft, basis=basis)


# --- edges -----------------------------------------------------------------------------------------

def test_the_three_authorized_edges():
    assert may_challenge("guardian", "sentry", "MPJA")
    assert may_challenge("sentry", "curator", "DPIG")
    assert may_challenge("curator", "guardian", "PCRA")


def test_reverse_and_wrong_task_edges_denied():
    assert not may_challenge("sentry", "guardian", "MPJA")   # reverse direction
    assert not may_challenge("guardian", "sentry", "PCRA")   # wrong task on a real edge
    assert not may_challenge("guardian", "curator", "DPIG")  # non-adjacent in the cycle


# --- issue -----------------------------------------------------------------------------------------

def test_issue_open_on_authorized_edge():
    c = _open()
    assert c["status"] == "OPEN" and c["kind"] == "CHALLENGE"
    assert "changes NO score" in c["note"] and "NOT approval" in c["note"]


def test_issue_refuses_self_challenge():
    c = issue_challenge(challenger="guardian", target_steward="Guardian", target_task_class="PCRA",
                        target_draft_id="d", basis="x")
    assert c["status"] == "REFUSED" and "self-challenge" in c["refused_reason"]


def test_issue_refuses_unauthorized_edge():
    c = issue_challenge(challenger="guardian", target_steward="curator", target_task_class="DPIG",
                        target_draft_id="d", basis="x")
    assert c["status"] == "REFUSED" and "no authorized edge" in c["refused_reason"]


# --- resolve (operator only) -----------------------------------------------------------------------

def test_only_operator_resolves():
    r = resolve_challenge(_open(), resolver="sentry", outcome="FELL")
    assert r["status"] == "REFUSED" and r["sel_label"] is None
    assert "only the operator" in r["refused_reason"]


def test_cannot_resolve_a_refused_challenge():
    refused = issue_challenge(challenger="guardian", target_steward="curator", target_task_class="DPIG",
                              target_draft_id="d", basis="x")
    r = resolve_challenge(refused, resolver="operator", outcome="SURVIVED")
    assert r["status"] == "REFUSED" and r["sel_label"] is None   # absence != approval


def test_unknown_outcome_refused():
    r = resolve_challenge(_open(), resolver="operator", outcome="MEH")
    assert r["status"] == "REFUSED" and r["sel_label"] is None


def test_forged_open_unauthorized_edge_cannot_mint_a_label():
    # grok round-09 F1: resolve is the label MINT — a hand-forged OPEN dict with an edge that
    # issue_challenge would never produce (reverse direction) must NOT resolve into a valid label
    forged = {"schema": SCHEMA, "kind": "CHALLENGE", "status": "OPEN",
              "challenger": "sentry", "target_steward": "guardian", "target_task_class": "PCRA",
              "target_draft_id": "d", "basis": "forged"}
    r = resolve_challenge(forged, resolver="operator", outcome="SURVIVED")
    assert r["status"] == "REFUSED" and r["sel_label"] is None
    assert "authorized graph edge" in r["refused_reason"]


def test_forged_open_self_edge_cannot_mint_a_label():
    forged = {"schema": SCHEMA, "kind": "CHALLENGE", "status": "OPEN",
              "challenger": "guardian", "target_steward": "guardian", "target_task_class": "PCRA",
              "target_draft_id": "d", "basis": "forged self"}
    r = resolve_challenge(forged, resolver="operator", outcome="SURVIVED")
    assert r["status"] == "REFUSED" and r["sel_label"] is None


def test_survived_produces_positive_sel_label():
    r = resolve_challenge(_open(), resolver="operator", outcome="SURVIVED", resolved_ts_ns=42)
    lbl = r["sel_label"]
    assert r["status"] == "RESOLVED" and lbl["label"] == "CHALLENGE_SURVIVED"
    assert lbl["label_source"] == "challenge_graph" and lbl["ts_ns"] == 42


def test_fell_produces_negative_sel_label():
    r = resolve_challenge(_open(), resolver="operator", outcome="FELL")
    assert r["sel_label"]["label"] == "CHALLENGE_FELL"


# --- load-bearing rail: challenge cannot raise the challenger's own score --------------------------

def test_resolution_scores_target_not_challenger():
    # guardian challenges sentry's MPJA -> resolving scores SENTRY, sourced by GUARDIAN, never guardian
    r = resolve_challenge(_open(challenger="guardian", target="sentry", task="MPJA"),
                          resolver="operator", outcome="SURVIVED")
    lbl = r["sel_label"]
    assert lbl["steward"] == "sentry"                    # label is ABOUT the target
    assert lbl["label_source_agent"] == "guardian"       # sourced by the challenger
    assert lbl["steward"] != "guardian"                  # NEVER about the challenger


def test_resolved_label_is_a_valid_sel_external_label():
    # cross-module: a resolved challenge must be a valid external label for the TARGET in SEL
    r = resolve_challenge(_open(challenger="curator", target="guardian", task="PCRA"),
                          resolver="operator", outcome="SURVIVED")
    assert is_external_label(r["sel_label"]) is True


# --- adapter ---------------------------------------------------------------------------------------

def test_adapter_disabled_by_default():
    assert issue_challenges_from_store(store=None, cfg=_Cfg(sel_enabled=False))["enabled"] is False


def test_adapter_enabled_is_honest_stub():
    r = issue_challenges_from_store(store=None, cfg=_Cfg(sel_enabled=True))
    assert r["enabled"] is True and r["schema"] == SCHEMA and "STUB" in r["adapter_scope"]
