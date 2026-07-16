"""A2A-STEWARD-EVOLVE — PCRA evidence-loop Inc-1: persist Guardian PCRA findings as reviewable drafts.

This is the FIRST wiring of a steward drafter into a live loop (grok round-11 design A'): PCRA findings
persist via Guardian's EXISTING `draft_audit_entry(audit_kind="pcra")` → `action_name="audit-drafting"`,
which routes to a LOCAL handler (`local:audit:<id>`, cost 0.0) — never the chain path. The operator then
reviews each draft via the EXISTING `/operator/operator-agent-draft-review` endpoint (accept/reject),
which is operator-authenticated by construction — that decision becomes the SEL `operator_decision` label
(Inc-2). No new draft ledger, no executor change, no spend surface. Gated by `cfg.pcra_enabled` (default
False). 0-IOTX, no rig, no chain.

DEDUP RAIL (grok round-11 F1 — highest-risk footgun): `draft_audit_entry` injects a wall-clock ts_ns via
`payload.setdefault("ts_ns", ...)`, and `operator_agent_drafts` dedups on `(agent_id, payload_hash)`. So a
time-varying payload makes every re-scan a NEW row → the SEL denominator inflates → graduation is gamed.
We therefore build a DETERMINISTIC, content-addressed payload (pinned `ts_ns=0`, no wall-clock) keyed on
the finding's stable `claim_id`. Re-scanning the same finding produces the same `payload_hash` → the store
dedups to ONE row. A STALE_ANCHOR whose live value genuinely changes IS a new finding (new
measured_vs_claimed → new hash) — correct; SEL then aggregates one label per claim_id (Inc-2).
"""
from __future__ import annotations

from dataclasses import asdict

from .steward_pcra import detect_stale_anchor

TASK_CLASS = "PCRA"
STEWARD = "guardian"


def stale_anchor_findings(claimed_anchors: dict, live_anchors: dict) -> list[dict]:
    """STALE_ANCHOR adapter (grok round-11 Inc-1): run the existing pure detector over claimed-vs-live
    anchor dicts and return finding DICTS ready for persist_pcra_findings. The runner produces the
    claimed/live dicts from the live oracles (sensor_a_live_drift: wallet / PV-CI / contract count)."""
    return [asdict(f) for f in detect_stale_anchor(claimed_anchors, live_anchors)]


def build_pcra_draft_payload(finding: dict) -> dict:
    """Deterministic, content-addressed payload for one PCRA finding. NO wall-clock — pinning ts_ns=0
    means `draft_audit_entry`'s setdefault does not inject time, so re-scans of the same finding hash
    identically and dedup in the store."""
    return {
        "task_class": TASK_CLASS,
        "steward": STEWARD,
        "residue_class": finding.get("residue_class"),
        "claim_id": finding.get("claim_id"),
        "severity": finding.get("severity"),
        "measured_vs_claimed": finding.get("measured_vs_claimed"),
        "evidence_refs": finding.get("evidence_refs"),
        "note": finding.get("note"),
        # content-addressed identity, NOT a timestamp — the row's created_at records real insert time.
        "ts_ns": 0,
    }


def persist_pcra_findings(generator, findings: list, *, cfg) -> dict:
    """Persist each PCRA finding as a Guardian audit-drafting draft. The audit_id is f"pcra:{claim_id}";
    draft_audit_entry sanitizes it, so the real persisted URI is draft://audit_entries/pcra_<sanitized>.
    Gated by cfg.pcra_enabled. `generator` is a GuardianDraftGenerator (real) or a fake in tests. Draft
    only — never acts, never spends, never git/chain."""
    findings = list(findings or [])
    if not bool(getattr(cfg, "pcra_enabled", False)):
        return {"schema": "qortroller-pcra-draft-v0", "enabled": False,
                "n_findings": len(findings), "n_persisted": 0,
                "note": "pcra_enabled=False (opt-in capability)"}

    results = []
    for f in findings:
        claim_id = str(f.get("claim_id") or "").strip()
        if not claim_id:
            continue   # a finding with no stable id cannot dedup — skip rather than mint a churny draft
        res = generator.draft_audit_entry(
            audit_id=f"pcra:{claim_id}",
            audit_payload=build_pcra_draft_payload(f),
            audit_kind="pcra",
        )
        results.append(res)

    persisted = [r for r in results if getattr(r, "draft_id", 0)]
    return {
        "schema": "qortroller-pcra-draft-v0", "enabled": True, "steward": STEWARD, "task": TASK_CLASS,
        "n_findings": len(findings), "n_persisted": len(persisted),
        "draft_uris": [getattr(r, "draft_uri", "") for r in results],
        "note": "DRAFT ONLY via Guardian audit-drafting (LOCAL handler local:audit:*, cost 0.0 — never "
                "the chain path). Operator reviews via the existing draft-review endpoint; that decision "
                "becomes the SEL operator_decision label (Inc-2). 0-IOTX; no chain; no git write.",
    }


# --- Inc-2: PCRA reviewed-draft decisions -> SEL external labels ------------------------------------
# Layering: this PCRA-loop module knows the operator_agent_drafts schema + PCRA URIs and CALLS the
# generic steward_sel scorer. steward_sel stays task-agnostic (reusable for MPJA/DPIG ingestion later).

# The persist side passes audit_id=f"pcra:{claim_id}" to draft_audit_entry, which SANITIZES it via
# _safe_id_segment (":" "#" "/" -> "_"). So the real persisted URI is "draft://audit_entries/pcra_<sanitized
# claim>", NOT "...pcra:<claim_id>" — the ingestion filter MUST match the post-sanitization prefix (grok
# round-12 CRITICAL: a "pcra:" filter matched zero real rows; Inc-2 was a silent no-op).
_PCRA_URI_PREFIX = "draft://audit_entries/pcra_"
_DECISION_TO_LABEL = {"accept": "ACCEPTED", "reject": "OVERTURNED"}
# excluded on purpose: "overturn_curator" (a Curator-FP metric, not PCRA residue) + "none"/"" (unreviewed).


def pcra_labels_from_draft_rows(rows: list) -> list[dict]:
    """Map reviewed PCRA audit-drafting rows -> SEL external labels. Operator-sourced by construction (the
    review endpoint is the operator), so label_source='operator_decision' / label_source_agent='operator'
    — an AUTHENTIC label that satisfies SEL's source-authority binding. Deduped to ONE label per draft_uri
    (the stable per-claim key), keeping the LATEST decision (grok round-11: one label per claim_id)."""
    latest: dict = {}   # draft_uri -> (sort_key, decision)
    for r in rows or []:
        uri = str(r.get("draft_uri") or "")
        if not uri.startswith(_PCRA_URI_PREFIX):
            continue
        if str(r.get("action_name") or "") != "audit-drafting":
            continue
        decision = str(r.get("operator_decision") or "").strip().lower()
        if decision not in _DECISION_TO_LABEL:
            continue    # excludes overturn_curator / none / null / unreviewed
        sort_key = float(r.get("operator_decision_at") or r.get("created_at") or 0.0)
        if uri not in latest or sort_key >= latest[uri][0]:
            latest[uri] = (sort_key, decision)

    labels = []
    for uri, (sort_key, decision) in latest.items():
        labels.append({
            "steward": STEWARD, "task_class": TASK_CLASS,
            "label": _DECISION_TO_LABEL[decision],
            "label_source": "operator_decision", "label_source_agent": "operator",
            "ts_ns": int(sort_key * 1_000_000_000) if sort_key else 0,
            "claim_uri": uri,
        })
    return labels


def pcra_graduation_report(store, cfg, *, min_samples: int = 20,
                           precision_floor: float = 0.90) -> dict:  # pragma: no cover - store read adapter
    """Close the PCRA evidence loop: read reviewed PCRA drafts -> SEL labels -> score + graduation
    recommendation. Gated by cfg.sel_enabled (default False). Graduation is a DRAFT the operator accepts —
    never auto-applied, never grants spend (task-class autonomy only)."""
    if not bool(getattr(cfg, "sel_enabled", False)):
        return {"schema": "qortroller-pcra-sel-v0", "enabled": False,
                "note": "sel_enabled=False (opt-in capability)"}
    from . import steward_sel
    from .operator_agent_guardian_drafting import GUARDIAN_CANONICAL
    from .operator_initiative_advancement import _resolve_agent_id_for_store
    agent_id = _resolve_agent_id_for_store(GUARDIAN_CANONICAL, cfg)
    rows = store.get_operator_agent_drafts(agent_id=agent_id, limit=500)
    labels = pcra_labels_from_draft_rows(rows)
    score = steward_sel.score_task_class(labels, steward=STEWARD, task_class=TASK_CLASS)
    grad = steward_sel.recommend_graduation(labels, steward=STEWARD, task_class=TASK_CLASS,
                                            min_samples=min_samples, precision_floor=precision_floor)
    return {
        "schema": "qortroller-pcra-sel-v0", "enabled": True, "n_labels": len(labels),
        "score": score, "graduation": grad,
        "note": "PCRA reviewed-draft decisions -> SEL external labels (operator-sourced by construction). "
                "One label per draft_uri (latest decision). Graduation is a DRAFT the operator accepts; "
                "never auto-applied, never spend.",
    }
