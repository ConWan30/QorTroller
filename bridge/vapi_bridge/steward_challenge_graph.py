"""A2A-STEWARD-EVOLVE B5 — Steward Challenge Graph (SEL's assurance mode).

SEL-v0 (B4) graduates a steward's task-class on external-label precision, and its strongest external label
class is `challenge_graph`. This module is where those labels are PRODUCED — the peer-adversarial layer
that makes graduation earn its keep. It is the "the trio structurally enforces cross-agent skill
separation" invariant applied to the new drafting tasks: each steward may adversarially CHALLENGE exactly
one peer's task-class, in a 3-cycle so every steward is challenged by exactly one other.

Three directed, draft-only edges (round-03 lock):
    Guardian --challenges--> Sentry.MPJA     (does the claimed provenance join actually hold / overclaim?)
    Sentry   --challenges--> Curator.DPIG    (is the product's provenance whole for its sale claim?)
    Curator  --challenges--> Guardian.PCRA   (is the flagged claim-residue a real issue or noise?)

Hard rails (round-03 lock):
  1. DRAFT ONLY. issue_challenge produces a CHALLENGE draft; issuing it changes NO score by itself.
  2. ONLY THE OPERATOR RESOLVES. resolve_challenge refuses any resolver != operator. Resolution produces
     a SEL label (CHALLENGE_SURVIVED / CHALLENGE_FELL) ABOUT THE TARGET steward, sourced by the CHALLENGER
     — so issuing a challenge can NEVER raise the challenger's own score (the label is never about them).
  3. ABSENCE != APPROVAL. No path turns "no challenge" into a positive label; an unchallenged draft is
     simply unlabeled, not approved.
  4. No self-challenge; only authorized edges; casefolded identity checks.

Gated by `cfg.pgsw_enabled`? No — the graph itself is gated by `cfg.sel_enabled` (it is SEL's assurance
mode); default False. Pure edge logic + label production over injected challenges; the drafting-loop hook
(a steward autonomously issuing challenges) is v0.1.
"""
from __future__ import annotations

SCHEMA = "qortroller-challenge-graph-v0"

# 3 directed edges (challenger, target_steward, target_task_class) — a 3-cycle, no self-loops.
CHALLENGE_EDGES = (
    ("guardian", "sentry", "MPJA"),
    ("sentry", "curator", "DPIG"),
    ("curator", "guardian", "PCRA"),
)
_EDGE_SET = frozenset((c.casefold(), t.casefold(), tc) for c, t, tc in CHALLENGE_EDGES)

_OUTCOME_LABEL = {"SURVIVED": "CHALLENGE_SURVIVED", "FELL": "CHALLENGE_FELL"}


def may_challenge(challenger: str, target_steward: str, target_task_class: str) -> bool:
    """True iff (challenger -> target_steward on target_task_class) is one of the 3 authorized edges."""
    return (str(challenger).strip().casefold(),
            str(target_steward).strip().casefold(),
            target_task_class) in _EDGE_SET


def issue_challenge(*, challenger: str, target_steward: str, target_task_class: str,
                    target_draft_id: str, basis: str) -> dict:
    """Produce a draft-only CHALLENGE. status='OPEN' iff the edge is authorized and it isn't a
    self-challenge; else status='REFUSED' with a reason. Issuing changes NO score."""
    ch = str(challenger).strip().casefold()
    tg = str(target_steward).strip().casefold()
    base = {
        "schema": SCHEMA, "kind": "CHALLENGE", "challenger": challenger,
        "target_steward": target_steward, "target_task_class": target_task_class,
        "target_draft_id": target_draft_id, "basis": basis,
    }
    if ch == tg:
        return {**base, "status": "REFUSED", "refused_reason": "self-challenge is not allowed"}
    if not may_challenge(challenger, target_steward, target_task_class):
        return {**base, "status": "REFUSED",
                "refused_reason": f"no authorized edge {ch}->{tg} on {target_task_class}"}
    return {**base, "status": "OPEN",
            "note": "DRAFT ONLY — a challenge is a draft; issuing it changes NO score. Only the operator "
                    "resolves it. Absence of a challenge is NOT approval."}


def resolve_challenge(challenge: dict, *, resolver: str, outcome: str, resolved_ts_ns: int = 0) -> dict:
    """ONLY the operator resolves a challenge. On resolve, produce a SEL-compatible external label ABOUT
    THE TARGET steward, sourced by the CHALLENGER — never about the challenger (issuing a challenge can't
    raise your own score). Refuses non-operator resolvers, non-OPEN challenges, and unknown outcomes."""
    if str(resolver).strip().casefold() != "operator":
        return {"schema": SCHEMA, "status": "REFUSED", "sel_label": None,
                "refused_reason": "only the operator resolves a challenge"}
    if challenge.get("status") != "OPEN":
        return {"schema": SCHEMA, "status": "REFUSED", "sel_label": None,
                "refused_reason": "challenge is not OPEN"}
    # RE-VALIDATE the edge at the label-production site (grok round-09 F1): resolve is the SEL-label MINT,
    # so it must not trust that the OPEN dict came from issue_challenge — a hand-forged OPEN with an
    # unauthorized/self edge must never mint a valid label.
    _ch = str(challenge.get("challenger") or "").strip().casefold()
    _tg = str(challenge.get("target_steward") or "").strip().casefold()
    if _ch == _tg or not may_challenge(challenge.get("challenger", ""), challenge.get("target_steward", ""),
                                       challenge.get("target_task_class", "")):
        return {"schema": SCHEMA, "status": "REFUSED", "sel_label": None,
                "refused_reason": "challenge edge is not an authorized graph edge (self or not one of the 3)"}
    o = str(outcome).strip().upper()
    if o not in _OUTCOME_LABEL:
        return {"schema": SCHEMA, "status": "REFUSED", "sel_label": None,
                "refused_reason": f"unknown outcome {outcome!r} (expected SURVIVED or FELL)"}
    sel_label = {
        "steward": challenge["target_steward"],          # the label is ABOUT the target...
        "task_class": challenge["target_task_class"],
        "label": _OUTCOME_LABEL[o],
        "label_source": "challenge_graph",
        "label_source_agent": challenge["challenger"],   # ...sourced by the challenger (never the target)
        "ts_ns": int(resolved_ts_ns),
        "challenge_ref": challenge.get("target_draft_id"),
    }
    return {
        "schema": SCHEMA, "status": "RESOLVED", "outcome": o, "resolved_by": "operator",
        "sel_label": sel_label,
        "note": "operator-resolved — this SEL label scores the TARGET steward, sourced by the challenger; "
                "the challenger's own score is untouched. Feed into SEL score/graduation. Resolver "
                "identity ('operator') is caller/ingestion trust, not cryptographically enforced (same "
                "authenticity class as SEL label sources — an ingestion-layer guarantee, v0.1).",
    }


def issue_challenges_from_store(store, cfg, *, targets=None) -> dict:  # pragma: no cover - read-only adapter STUB
    """Read-only adapter, gated by cfg.sel_enabled (default False).

    HONEST SCOPE (mirrors B1-B4): STUB. It does NOT yet select recent peer drafts to challenge or auto-
    issue challenges from a steward drafting loop — that hook is v0.1. The pure edge/issue/resolve logic
    over injected challenges is real and tested; this adapter does not fabricate challenges. Never
    resolves (operator-only), never grants autonomy, never git/chain write."""
    if not bool(getattr(cfg, "sel_enabled", False)):
        return {"schema": SCHEMA, "enabled": False, "note": "sel_enabled=False (opt-in capability)"}
    return {"schema": SCHEMA, "enabled": True,
            "adapter_scope": "STUB — no peer-draft selection / auto-issue loop yet (v0.1). The pure "
                             "edge/issue/resolve logic works; this adapter does not.",
            "note": "STUB adapter — refuses to fabricate challenges. Wire peer-draft selection in v0.1. "
                    "operator resolves; no autonomy grant; no git/chain."}
