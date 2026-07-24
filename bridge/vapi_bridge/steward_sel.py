"""A2A-STEWARD-EVOLVE B4 — SEL-v0 (Steward Evolution Ledger).

The cross-cutting primitive that lets the stewards EVOLVE their autonomy safely. B1/B2/B3 gave Guardian /
Sentry / Curator three new drafting task-classes (PCRA / MPJA / DPIG), all default-OFF, all draft-only.
SEL answers the next question mechanically: "may steward S auto-persist drafts of task-class T WITHOUT
operator pre-review yet?" — graduated TASK-CLASS autonomy, scored ONLY by external labels.

Three hard boundaries (grok-agreed, round-03 lock; hardened round-07):
  1. EXTERNAL LABELS ONLY, source-authority-bound. A draft's outcome is labeled by operator_decision
     (only the `operator` may source it), adversarial_holdout (a non-steward holdout oracle, never a peer
     steward), or challenge_graph (any peer agent that is NOT the scored steward). A label from the scored
     steward — or from a source class the labeler isn't authorized for — is REJECTED. This blocks both
     self-scoring AND peer-collusion (Sentry rubber-stamping Guardian's drafts) at the scorer layer.
  2. TASK-CLASS autonomy, NOT spend autonomy. Graduation only ever grants "auto-persist the draft
     ARTIFACT without pre-review." It can NEVER grant IOTX spend, and it NEVER auto-arms an act — the
     anchor/suspend act path stays TWO-KEY + estimate-first forever (distinct from the O3-SUPERSEDE phase
     ladder, a different chain-anchored primitive). SEL never flips an executor flag.
  3. Graduation is itself a DRAFT the operator accepts. SEL never auto-applies a graduation.

WHAT SEL DOES NOT DEFEND (honest limit, grok round-07 F3): the scorer trusts the CLAIMED `label_source`
and `label_source_agent` fields. It cannot verify a label's authenticity — a forged row claiming
`label_source_agent="operator"` would pass. The load-bearing invariant is therefore an INGESTION-layer
guarantee (v0.1): external labels are written only from trusted sources (the operator's own decision log,
a holdout-oracle run, resolved challenge edges) and stewards never write label rows. The agent-source
binding here REDUCES forgery surface; it does not replace ingestion authenticity.

CANDIDATE domain tag `VAPI-SEL-v0` — NOT a FROZEN-v1 family, no governance seal in this arc. The
length-prefixed hash-chain makes the label ledger tamper-evident; it is a candidate, not a frozen
commitment family. This module is the pure scorer + candidate chain over INJECTED labels; real ingestion
is v0.1.
"""
from __future__ import annotations

import hashlib

SCHEMA = "qortroller-sel-v0"
_DOMAIN = b"VAPI-SEL-v0"   # CANDIDATE — not FROZEN-v1, no governance seal

STEWARDS = ("guardian", "sentry", "curator")
_STEWARD_SET = frozenset(s.casefold() for s in STEWARDS)
LABEL_SOURCES = ("operator_decision", "adversarial_holdout", "challenge_graph")
_OPERATOR_AGENT = "operator"   # the only authorized source for operator_decision labels

# positive vs negative outcome labels
_POSITIVE = ("ACCEPTED", "HOLDOUT_TP", "CHALLENGE_SURVIVED")
_NEGATIVE = ("OVERTURNED", "HOLDOUT_FP", "CHALLENGE_FELL")
LABELS = _POSITIVE + _NEGATIVE

_LABEL_CODE = {lbl: i for i, lbl in enumerate(LABELS)}
_SOURCE_CODE = {src: i for i, src in enumerate(LABEL_SOURCES)}

GRADUATION_VERDICTS = ("GRADUATE_TASK_CLASS", "HOLD_INSUFFICIENT_SAMPLES", "HOLD_NO_OPERATOR_LABELS",
                       "HOLD_BELOW_PRECISION", "HOLD_NO_CHALLENGE_SURVIVAL")


def is_external_label(entry: dict) -> bool:
    """A label counts ONLY if it is (a) a known label + source, (b) NOT sourced by the scored steward
    (case-insensitive), and (c) sourced by an agent AUTHORIZED for that source class:
       operator_decision -> only the `operator`
       adversarial_holdout -> a non-steward holdout oracle (never a peer steward)
       challenge_graph -> any peer agent that is not the scored steward
    This is the anti-self-scoring AND anti-peer-collusion rail (grok round-07 F1/F2)."""
    label = entry.get("label")
    source = entry.get("label_source")
    steward = str(entry.get("steward") or "").strip().casefold()
    src_agent = str(entry.get("label_source_agent") or "").strip().casefold()
    if label not in LABELS or source not in LABEL_SOURCES or not steward or not src_agent:
        return False
    if src_agent == steward:
        return False                                  # never self-score (case-folded)
    if source == "operator_decision":
        return src_agent == _OPERATOR_AGENT           # only the operator sources operator decisions
    if source == "adversarial_holdout":
        return src_agent not in _STEWARD_SET          # a peer steward is NOT a holdout oracle
    if source == "challenge_graph":
        return True                                   # any peer != scored steward (ensured above)
    return False


def partition_labels(entries: list, *, steward: str, task_class: str) -> tuple:
    """Split entries for (steward, task_class) into (external_valid, rejected). `rejected` holds entries
    dropped for ANY reason — self-source, unauthorized source class, or unknown label/source."""
    valid, rejected = [], []
    scored = str(steward).strip().casefold()
    for e in entries:
        if str(e.get("steward") or "").strip().casefold() != scored or e.get("task_class") != task_class:
            continue
        (valid if is_external_label(e) else rejected).append(e)
    return valid, rejected


def score_task_class(entries: list, *, steward: str, task_class: str) -> dict:
    """Pure external-label precision score for one (steward, task_class). Self-sourced labels are excluded
    from the numerator/denominator and reported separately."""
    valid, rejected = partition_labels(entries, steward=steward, task_class=task_class)
    positives = sum(1 for e in valid if e["label"] in _POSITIVE)
    negatives = sum(1 for e in valid if e["label"] in _NEGATIVE)
    denom = positives + negatives
    precision = (positives / denom) if denom else None
    challenge_survived = sum(1 for e in valid if e["label"] == "CHALLENGE_SURVIVED")
    challenge_fell = sum(1 for e in valid if e["label"] == "CHALLENGE_FELL")
    return {
        "schema": SCHEMA, "steward": steward, "task_class": task_class,
        "n_external_labels": len(valid),
        # rejected for ANY reason (self-source / unauthorized source class / unknown), not only self
        "n_rejected_labels": len(rejected),
        "positives": positives, "negatives": negatives, "precision": precision,
        "challenge_survived": challenge_survived, "challenge_fell": challenge_fell,
        "sources_seen": sorted({e["label_source"] for e in valid}),
    }


def recommend_graduation(entries: list, *, steward: str, task_class: str,
                         min_samples: int = 20, precision_floor: float = 0.90,
                         require_challenge_survival: bool = False) -> dict:
    """Draft a graduation recommendation from the external-label score. NEVER auto-applies; NEVER grants
    spend. `require_challenge_survival` stays False in v0 (the Challenge Graph is B5) — B5 flips it on so
    graduation additionally requires surviving a peer challenge."""
    s = score_task_class(entries, steward=steward, task_class=task_class)
    n, prec = s["n_external_labels"], s["precision"]

    if n < min_samples:
        verdict = "HOLD_INSUFFICIENT_SAMPLES"
    elif "operator_decision" not in s["sources_seen"]:
        # a steward can never graduate without ANY operator label — the human-in-the-loop anchor
        # (grok round-07 F4: blocks graduating purely on holdout/challenge with zero operator acceptance)
        verdict = "HOLD_NO_OPERATOR_LABELS"
    elif prec is None or prec < precision_floor:
        verdict = "HOLD_BELOW_PRECISION"
    elif require_challenge_survival and (s["challenge_survived"] < 1 or s["challenge_fell"] > 0):
        verdict = "HOLD_NO_CHALLENGE_SURVIVAL"
    else:
        verdict = "GRADUATE_TASK_CLASS"

    return {
        "schema": SCHEMA, "domain_tag": _DOMAIN.decode(), "candidate": True,
        "steward": steward, "task_class": task_class,
        "score": s,
        "thresholds": {"min_samples": min_samples, "precision_floor": precision_floor,
                       "require_challenge_survival": require_challenge_survival},
        "graduation_recommendation": verdict,
        "grants_if_accepted": ("auto-persist the DRAFT ARTIFACT of this task-class WITHOUT operator "
                               "pre-review — NEVER any IOTX spend and NEVER auto-arming an act; the "
                               "anchor/suspend act path stays TWO-KEY + estimate-first (distinct from "
                               "O3-SUPERSEDE)"),
        "note": "DRAFT — graduation is itself a recommendation the operator accepts; SEL never auto-"
                "applies it, never grants spend autonomy, never flips an executor flag, never self-scores "
                "(self-sourced + collusion + unauthorized-source labels are rejected). Requires >=1 "
                "operator_decision label to graduate. Scorer trusts CLAIMED source fields — authenticity "
                "is an ingestion-layer guarantee (v0.1). CANDIDATE tag VAPI-SEL-v0 — not FROZEN, no seal.",
    }


def _lp(b: bytes) -> bytes:
    """4-byte big-endian length prefix — removes delimiter ambiguity between variable-length fields
    (grok round-07 F6: a bare '|' separator collides steward='a|b' with task='b|c')."""
    return len(b).to_bytes(4, "big") + b


def chain_head(entries: list) -> str:
    """Tamper-evident CANDIDATE hash-chain over the label ledger (order-sensitive). Genesis is
    SHA-256(domain||b'-GENESIS'); each link folds the prior head + the label's length-prefixed fields.
    Not a FROZEN-v1 commitment family — a candidate integrity chain for the evolution ledger."""
    h = hashlib.sha256(_DOMAIN + b"-GENESIS").digest()
    for e in entries:
        body = (h + _lp(_DOMAIN)
                + _lp(str(e.get("steward", "")).encode())
                + _lp(str(e.get("task_class", "")).encode())
                + bytes([_LABEL_CODE.get(e.get("label"), 255)])
                + bytes([_SOURCE_CODE.get(e.get("label_source"), 255)])
                + _lp(str(e.get("label_source_agent", "")).encode())
                + int(e.get("ts_ns", 0)).to_bytes(8, "big"))
        h = hashlib.sha256(body).digest()
    return h.hex()


def graduation_report_from_store(store, cfg, *, steward=None, task_class=None) -> dict:  # pragma: no cover - read-only adapter STUB
    """Read-only label-ingestion adapter, gated by cfg.sel_enabled (default False).

    HONEST SCOPE (mirrors B1/B2/B3): this is a STUB. It does NOT yet ingest real external labels — operator
    accept/overturn decisions, adversarial-holdout TP/FP, challenge-graph survived/fell. Those ingestion
    paths are v0.1. The pure score/graduation/chain functions over injected labels are real and tested;
    this adapter does not fabricate labels. Never grants autonomy, never spends, never git/chain write."""
    if not bool(getattr(cfg, "sel_enabled", False)):
        return {"schema": SCHEMA, "enabled": False, "note": "sel_enabled=False (opt-in capability)"}
    return {"schema": SCHEMA, "enabled": True, "candidate": True,
            "adapter_scope": "STUB — no operator-decision / holdout / challenge-graph label ingestion yet "
                             "(v0.1). The pure score/graduation/chain functions work; this adapter does not.",
            "note": "STUB adapter — refuses to fabricate labels. Wire real external-label ingestion in "
                    "v0.1. Graduation is a draft; never spend; never git/chain."}
