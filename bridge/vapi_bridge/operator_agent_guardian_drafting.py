"""Phase O2-DRAFT-GENERATION (Guardian) -- 2026-05-10.

Guardian's three O2_SUGGEST drafting primitives. Sibling of
operator_agent_sentry_drafting.py; same store interface (operator_agent_drafts
schema 1005 + 5 helpers from Phase O2-DRAFT-GENERATION Sentry).

PERMITTED RESOURCE PATHS at O2_SUGGEST per `guardian_o2_suggest_v1.json`:
  tool:kms-sign                  -> draft://commit_hashes/*
  skill:audit-drafting           -> draft://audit_entries/*
  skill:operational-diagnostic   -> draft://audit_entries/*
  tool:audit-entry-draft         -> draft://audit_entries/*
  tool:git-add                   -> draft://audit_entries/*
  tool:git-commit                -> draft://audit_entries/*
  tool:git-pr                    -> draft://audit_entries/*
  tool:ipfs-pin                  -> draft://audit_entries/*

This module ships the three highest-leverage primitives (kms-sign on commit
hashes; audit-drafting and operational-diagnostic on audit entries). git
operations + ipfs-pin are follow-up phases that bind to the same draft
persistence primitive.

PARALLEL-FLEET INVARIANT (per operator_initiative_advancement.py docstring):
Sentry + Guardian + Curator MUST advance through the Phase O ladder
together. Guardian's drafting primitives MUST exist alongside Sentry's so
both agents can accumulate the >=50-draft signal that drives the watcher's
PHASE_O3_DRAFT_PAYLOAD_MIN gate per agent. Without Guardian primitives,
the parallel anchor would be permanently blocked at Gate 4 (watcher veto).

INVARIANTS (mirror Sentry's; preserve cross-fleet symmetry):
  - draft_uri MUST start with "draft://" (Cedar VALID_SCHEMES gate)
  - payload_hash is SHA-256 lowercase hex of canonical-JSON body
  - agent_id passed to store is the Q9 hex when cfg fields populated;
    canonical name "guardian" fallback for test stubs (matches watcher's
    _resolve_agent_id_for_store contract)
  - Idempotent: same agent+payload_hash twice returns existing row id
  - Fail-open: store insertion failures return draft_id=0 with error populated
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from .operator_agent_sentry_drafting import (
    DraftResult,
    _normalize_commit_hash,
    _sha256_canonical_json,
)
from .operator_initiative_advancement import _resolve_agent_id_for_store

log = logging.getLogger(__name__)


# Guardian's canonical name in INITIATIVE_AGENTS (matches watcher convention).
GUARDIAN_CANONICAL = "guardian"

# Guardian's permitted draft URI prefixes per guardian_o2_suggest_v1.json.
# Re-asserted at module level so a future bundle edit lifting these paths
# does not silently change the draft URI scheme without a code update.
GUARDIAN_KMS_SIGN_DRAFT_PREFIX = "draft://commit_hashes/"
GUARDIAN_AUDIT_DRAFT_PREFIX    = "draft://audit_entries/"


def _safe_id_segment(raw: str) -> str:
    """Sanitize an operator-meaningful identifier for use in a draft URI.
    Keeps alphanumerics + dash + underscore + dot; collapses everything
    else to '_'. Mirrors the helper used by Sentry's draft_provenance_record."""
    return "".join(
        c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in raw
    )


class GuardianDraftGenerator:
    """Phase O2-DRAFT-GENERATION primitive surface for Guardian.

    All three methods are synchronous (pure-Python + sqlite3 writes).
    Higher-level call sites decide WHEN to invoke them; this module is
    the storage primitive.
    """

    def __init__(self, *, cfg: Any, store: Any) -> None:
        self._cfg = cfg
        self._store = store
        # Resolve agent_id once -- canonical name in tests, Q9 hex in production.
        self._agent_id_used = _resolve_agent_id_for_store(GUARDIAN_CANONICAL, cfg)

    # ------------------------------------------------------------------
    # 1. tool:kms-sign on draft://commit_hashes/*
    # ------------------------------------------------------------------
    #
    # Guardian signs commit hashes for the audit-trail PRs that go through
    # its lane (audits/ + invariants/ + ops/ + sweeps/). The signature
    # payload is the input to Guardian's downstream git-pr workflow at O3.
    # ------------------------------------------------------------------
    def draft_kms_sign(
        self,
        *,
        commit_hash: str,
        signer_pubkey_hex: str = "",
        signature_payload: Optional[dict] = None,
    ) -> DraftResult:
        """Produce a Guardian kms-sign draft for a git commit hash.

        Mirrors Sentry's draft_kms_sign signature. Difference: agent_id is
        Guardian's identifier (resolved from cfg.operator_agent_guardian_id
        in production; canonical 'guardian' fallback in tests).
        """
        try:
            ch = _normalize_commit_hash(commit_hash)
        except ValueError as exc:
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="kms-sign",
                agent_id_used=self._agent_id_used,
                error=str(exc),
            )

        payload = signature_payload if isinstance(signature_payload, dict) else {}
        payload.setdefault("commit_hash", ch)
        payload.setdefault("ts_ns", time.time_ns())
        if signer_pubkey_hex:
            payload["signer_pubkey_hex"] = str(signer_pubkey_hex)

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        draft_uri = f"{GUARDIAN_KMS_SIGN_DRAFT_PREFIX}{ch}"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="tool",
                action_name="kms-sign",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=bool(signer_pubkey_hex),
            )
        except Exception as exc:
            log.warning("GuardianDraftGenerator.draft_kms_sign persist failed: %s", exc)
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="tool",
                action_name="kms-sign",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="tool",
            action_name="kms-sign",
            agent_id_used=self._agent_id_used,
        )

    # ------------------------------------------------------------------
    # 2. skill:audit-drafting on draft://audit_entries/*
    # ------------------------------------------------------------------
    #
    # Guardian's headline O2 skill. Audit drafts are the inputs to the
    # audit-trail PRs Guardian opens against the audits/ lane. At O3
    # ACTING the same skill graduates to lane://audits/** (live writes).
    # ------------------------------------------------------------------
    def draft_audit_entry(
        self,
        *,
        audit_id: str,
        audit_payload: dict,
        audit_kind: str = "audit",
    ) -> DraftResult:
        """Produce a Guardian audit-drafting draft.

        audit_kind: free-form short tag distinguishing the audit category
        (e.g. 'audit', 'sweep', 'invariant_drift', 'consent_revocation').
        Stored in the canonical payload but not embedded in the URI;
        URI uses the sanitized audit_id only so the same logical audit
        re-drafts to the same URI even if the kind tag changes.

        action_name is fixed at 'audit-drafting' (Cedar permits the
        skill:audit-drafting action; the URI is the resource).
        """
        if not audit_id or not isinstance(audit_id, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="audit-drafting",
                agent_id_used=self._agent_id_used,
                error="audit_id must be non-empty string",
            )
        if not isinstance(audit_payload, dict):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="audit-drafting",
                agent_id_used=self._agent_id_used,
                error="audit_payload must be dict",
            )

        payload = dict(audit_payload)
        payload.setdefault("audit_id", audit_id)
        payload.setdefault("audit_kind", str(audit_kind))
        payload.setdefault("ts_ns", time.time_ns())

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        safe = _safe_id_segment(audit_id)
        draft_uri = f"{GUARDIAN_AUDIT_DRAFT_PREFIX}{safe}"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="skill",
                action_name="audit-drafting",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=False,
            )
        except Exception as exc:
            log.warning(
                "GuardianDraftGenerator.draft_audit_entry persist failed: %s", exc
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="skill",
                action_name="audit-drafting",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="skill",
            action_name="audit-drafting",
            agent_id_used=self._agent_id_used,
        )

    # ------------------------------------------------------------------
    # 3. skill:operational-diagnostic on draft://audit_entries/*
    # ------------------------------------------------------------------
    #
    # Guardian-exclusive skill: drafts diagnostic findings about the
    # protocol's operational state (e.g. sweep summaries, capture-health
    # anomalies, watchdog events that warranted human attention). At O3
    # ACTING this skill graduates to lane://ops/** (live ops-lane writes).
    # ------------------------------------------------------------------
    def draft_operational_diagnostic(
        self,
        *,
        diagnostic_id: str,
        diagnostic_payload: dict,
        severity: str = "info",
    ) -> DraftResult:
        """Produce a Guardian operational-diagnostic draft.

        severity: 'info' | 'warn' | 'error' | 'critical'. Stored in the
        canonical payload; lifted to lane://ops/** at O3 where downstream
        consumers (FSCA + ops dashboards) read it.
        """
        if not diagnostic_id or not isinstance(diagnostic_id, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="operational-diagnostic",
                agent_id_used=self._agent_id_used,
                error="diagnostic_id must be non-empty string",
            )
        if not isinstance(diagnostic_payload, dict):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="operational-diagnostic",
                agent_id_used=self._agent_id_used,
                error="diagnostic_payload must be dict",
            )
        if severity not in ("info", "warn", "error", "critical"):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="operational-diagnostic",
                agent_id_used=self._agent_id_used,
                error=f"severity must be info/warn/error/critical; got {severity!r}",
            )

        payload = dict(diagnostic_payload)
        payload.setdefault("diagnostic_id", diagnostic_id)
        payload.setdefault("severity", severity)
        payload.setdefault("ts_ns", time.time_ns())

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        safe = _safe_id_segment(diagnostic_id)
        # Distinguish operational-diagnostic URIs from audit-drafting URIs
        # at the prefix level so operators can disambiguate at-a-glance
        # while both still anchor under the same Cedar-permitted lane.
        draft_uri = f"{GUARDIAN_AUDIT_DRAFT_PREFIX}diag-{safe}"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="skill",
                action_name="operational-diagnostic",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=False,
            )
        except Exception as exc:
            log.warning(
                "GuardianDraftGenerator.draft_operational_diagnostic persist failed: %s",
                exc,
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="skill",
                action_name="operational-diagnostic",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="skill",
            action_name="operational-diagnostic",
            agent_id_used=self._agent_id_used,
        )
