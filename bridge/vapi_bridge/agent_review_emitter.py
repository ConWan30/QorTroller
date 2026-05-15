"""Phase O5-MLGA Stage 7 (AGENT-REVIEW autonomy) — fires on operator
decision.

Fourth autonomous VPM artifact class. Unlike the prior three trackers
(polling-based), AGENT-REVIEW-v1 is EVENT-driven: fires immediately
after the operator submits a review decision via POST
/operator/operator-agent-draft-review.

Design:
  • emit_agent_review_for_draft(store, cfg, draft_id) is the entry
    point. Called from operator_api.py after record_operator_decision
    succeeds.
  • Fail-open: any failure logs + returns None; never affects the
    operator's review response.
  • One artifact per operator decision (one click → one VPM row).

Snapshot semantics:
  • agent_canonical_name: reverse-lookup from draft.agent_id (Q9 hex
    or canonical string) via cfg.operator_agent_<name>_id attrs.
  • current_phase: assume O1_SHADOW for current deployment (agents
    haven't graduated yet); will pull from advancement watcher when
    operator advances.
  • shadow_log / drift_log counts: pulled via store helpers (fail-
    open to 0).
  • disagreement_rate / false_positive_rate: pulled via store helpers
    (compute_operator_agent_disagreement_rate +
    compute_operator_agent_false_positive_rate).
  • last_operator_decision: the just-recorded decision.
  • o2_ready / o3_ready: not gating emission; defaults False (will
    populate from advancement watcher when available).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


_VALID_AGENT_CANONICAL = ("anchor_sentry", "guardian", "curator")
_AGENT_ID_TO_CANONICAL_ATTR = {
    "anchor_sentry": "operator_agent_sentry_id",
    "guardian":      "operator_agent_guardian_id",
    "curator":       "operator_agent_curator_id",
}


def _resolve_canonical_from_agent_id(
    *, agent_id: str, cfg
) -> Optional[str]:
    """Reverse-lookup canonical agent name from store agent_id field.

    The draft row's agent_id may be the canonical name (test fixtures)
    or the Q9-hex agentId (production after Phase O1 C1 on-chain
    registration). Try canonical match first, then Q9 hex match.
    """
    if agent_id in _VALID_AGENT_CANONICAL:
        return agent_id
    for canonical, attr in _AGENT_ID_TO_CANONICAL_ATTR.items():
        cfg_val = getattr(cfg, attr, "") or ""
        if cfg_val and cfg_val.lower() == agent_id.lower():
            return canonical
    return None


def _safe_call(fn, *args, default=None, **kwargs):
    """Run a store helper inside a try/except; return default on any error."""
    try:
        return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        return default


def _build_integrity_label(*, decision: str) -> Dict[str, Any]:
    """FROZEN 9-field integrity label for AGENT-REVIEW-v1."""
    return {
        "proof_type":             "VPM-AGENT-REVIEW",
        "capture_mode":           "live",
        "raw_biometrics_exposed": False,
        "consent_active":         "n/a",
        "zk_verified":            False,
        "on_chain_anchor":        False,
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            f"Autonomous emission after operator decision={decision}; "
            "supplements Cedar shadow log, does not replace it.",
        ],
    }


def emit_agent_review_for_draft(
    *,
    store,
    cfg,
    draft_id: int,
) -> Optional[Dict[str, Any]]:
    """Emit one AGENT-REVIEW-v1 VPM artifact for the just-reviewed draft.

    Returns the manifest dict on success, None on any failure. Never
    raises. Caller (post_operator_agent_draft_review endpoint) wraps
    in try/except as defense-in-depth.
    """
    try:
        # 1. Find the draft row
        rows = _safe_call(
            store.get_operator_agent_drafts,
            agent_id=None, decision=None, since_seconds=None, limit=500,
            default=[],
        ) or []
        draft = next(
            (r for r in rows if int(r.get("id", 0)) == int(draft_id)),
            None,
        )
        if draft is None:
            log.warning(
                "AGENT-REVIEW emit: draft_id=%d not found", draft_id,
            )
            return None

        agent_id_raw = str(draft.get("agent_id") or "")
        canonical = _resolve_canonical_from_agent_id(
            agent_id=agent_id_raw, cfg=cfg,
        )
        if canonical is None:
            log.warning(
                "AGENT-REVIEW emit: cannot resolve agent_canonical_name "
                "from agent_id=%s", agent_id_raw[:24],
            )
            return None

        decision = str(draft.get("operator_decision") or "none")
        if decision not in ("accept", "reject", "overturn_curator", "none"):
            log.warning(
                "AGENT-REVIEW emit: invalid decision=%s; defaulting to 'none'",
                decision,
            )
            decision = "none"

        decision_at = draft.get("operator_decision_at") or 0
        try:
            last_decision_ts_ns = int(float(decision_at) * 1e9)
        except Exception:
            last_decision_ts_ns = 0

        # 2. Counts (fail-open to 0) — store-helper lookups
        shadow_count = int(_safe_call(
            store.count_cedar_shadow_evaluations,
            agent_id=agent_id_raw, since_seconds=2_592_000,
            default=0,
        ) or 0)
        drift_count = int(_safe_call(
            store.count_operator_agent_drift_findings,
            agent_id=agent_id_raw, since_seconds=2_592_000,
            default=0,
        ) or 0)
        disagreement_rate = float(_safe_call(
            store.compute_operator_agent_disagreement_rate,
            agent_id=agent_id_raw, since_seconds=2_592_000,
            default=0.0,
        ) or 0.0)
        fp_rate = float(_safe_call(
            store.compute_operator_agent_false_positive_rate,
            agent_id=agent_id_raw, since_seconds=2_592_000,
            default=0.0,
        ) or 0.0)

        # 3. Snapshot dict for preimage + zkba_manifest_hash
        ts_ns = time.time_ns()
        snapshot = {
            "vpm_id":                  "AGENT-REVIEW-v1",
            "agent_canonical_name":    canonical,
            "agent_id_hex":            agent_id_raw,
            "current_phase":           "O1_SHADOW",
            "shadow_log_row_count":    shadow_count,
            "drift_log_row_count":     drift_count,
            "last_operator_decision":  decision,
            "last_decision_ts_ns":     last_decision_ts_ns,
            "disagreement_rate_30d":   disagreement_rate,
            "false_positive_rate_30d": fp_rate,
            "o2_ready":                False,
            "o3_ready":                False,
            "draft_id":                int(draft_id),
            "ts_ns":                   ts_ns,
        }
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
        ).hexdigest()

        integrity_label = _build_integrity_label(decision=decision)

        # 4. Compile artifact
        output_dir = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "artifacts" / "agent_review"
        )
        import sys as _sys
        _scripts_path = str(
            Path(__file__).resolve().parents[2] / "scripts"
        )
        if _scripts_path not in _sys.path:
            _sys.path.insert(0, _scripts_path)
        from vpm_compile_agent_review import build_agent_review_artifact

        manifest = build_agent_review_artifact(
            agent_canonical_name=canonical,
            agent_id_hex=agent_id_raw,
            current_phase="O1_SHADOW",
            shadow_log_row_count=shadow_count,
            drift_log_row_count=drift_count,
            last_operator_decision=decision,
            last_decision_ts_ns=last_decision_ts_ns,
            disagreement_rate_30d=disagreement_rate,
            false_positive_rate_30d=fp_rate,
            o2_ready=False,
            o3_ready=False,
            integrity_label=integrity_label,
            zkba_manifest_hash_hex=digest,
            visual_state="live",
            capture_mode="live",
            output_dir=output_dir,
            ts_ns=ts_ns,
        )

        # 5. Persist row
        preimage_json = json.dumps(snapshot, sort_keys=True,
                                    separators=(",", ":"))
        row_id = store.insert_vpm_artifact(
            commitment_hex=manifest.output_hash_hex,
            vpm_id="AGENT-REVIEW-v1",
            zkba_class=5,             # ZKBAClass.CONSENT
            proof_weight=3,           # CHAIN_ONLY
            visual_state="live",
            capture_mode="live",
            integrity_label_hash_hex=manifest.integrity_label_hash_hex,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex=digest,
            manifest_uri=manifest.output_path,
            compiler_output_hash_hex=manifest.output_hash_hex,
            preimage_json=preimage_json,
            ts_ns=ts_ns,
        )
        log.info(
            "AGENT-REVIEW emitted: draft_id=%d agent=%s decision=%s row=%d "
            "commit=%s...",
            draft_id, canonical, decision, row_id,
            manifest.output_hash_hex[:16],
        )
        return {
            "action": "emitted",
            "row": row_id,
            "commitment_hex": manifest.output_hash_hex,
            "agent_canonical_name": canonical,
        }
    except Exception as exc:  # noqa: BLE001 — fail-open
        import traceback as _tb
        log.warning(
            "AGENT-REVIEW emit failed for draft_id=%d: %s\n%s",
            draft_id, exc, _tb.format_exc(),
        )
        return None
