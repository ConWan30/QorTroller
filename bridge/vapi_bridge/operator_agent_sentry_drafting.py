"""Phase O2-DRAFT-GENERATION (Sentry) -- 2026-05-10.

Sentry's three O2_SUGGEST drafting primitives. Each method produces a draft
payload under one of Sentry's permitted O2_SUGGEST resource paths, computes
a SHA-256 payload hash, and persists to operator_agent_drafts (Phase 1005)
via store.insert_operator_agent_draft.

Drafts that survive operator review (operator_decision='accept') become the
input to O3_ACTING live writes. Until O3 ACTING anchors, drafts sit in the
table for operator review and are counted toward the
PHASE_O3_DRAFT_PAYLOAD_MIN gate (50 drafts in 30-day window).

PERMITTED RESOURCE PATHS at O2_SUGGEST per `anchor_sentry_o2_suggest_v1.json`:
  tool:kms-sign                  -> draft://commit_hashes/*
  skill:provenance-recording     -> draft://attestations/*
  tool:pda-attestation-anchor    -> draft://attestations/*
  tool:ipfs-pin                  -> draft://attestations/*
  tool:git-add                   -> draft://attestations/*
  tool:git-commit                -> draft://attestations/*
  tool:git-pr                    -> draft://attestations/*

This module ships the three highest-leverage skills (kms-sign,
provenance-recording, pda-attestation-anchor); git operations + ipfs-pin are
follow-up phases that bind to the same draft persistence primitive.

INVARIANTS:
  - draft_uri MUST start with "draft://" (Cedar VALID_SCHEMES gate)
  - payload_hash is SHA-256 lowercase hex (canonical)
  - agent_id passed to store is the Q9 hex when cfg fields populated;
    canonical name fallback for test stubs (matches watcher's
    _resolve_agent_id_for_store contract -- INV-INITIATIVE-ADVANCEMENT-J)
  - Idempotent: inserting the same agent+payload_hash twice returns the
    existing row id (UNIQUE INDEX idx_oad_payload_hash)
  - Fail-open: store insertion failures return draft_id=0; caller can retry
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from .operator_initiative_advancement import _resolve_agent_id_for_store

log = logging.getLogger(__name__)


# Sentry's canonical name in INITIATIVE_AGENTS (matches watcher convention).
SENTRY_CANONICAL = "anchor_sentry"

# Sentry's permitted draft URI prefixes per anchor_sentry_o2_suggest_v1.json.
# Re-asserted here so a future bundle edit that lifts these paths does not
# silently change the draft URI scheme without a corresponding code update.
SENTRY_KMS_SIGN_DRAFT_PREFIX        = "draft://commit_hashes/"
SENTRY_PROVENANCE_DRAFT_PREFIX      = "draft://attestations/"
SENTRY_PDA_ANCHOR_DRAFT_PREFIX      = "draft://attestations/"


@dataclass(frozen=True, slots=True)
class DraftResult:
    """Result of one draft-generation call."""
    draft_id: int           # store row id (0 on failure)
    draft_uri: str          # full draft://... URI
    payload_hash: str       # SHA-256 lowercase hex of payload
    payload_bytes: int
    action_category: str    # 'skill' or 'tool'
    action_name: str
    agent_id_used: str      # Q9 hex or canonical (whatever was passed to store)
    error: Optional[str] = None


def _sha256_canonical_json(obj: Any) -> tuple[str, int]:
    """Compute SHA-256 of an object's canonical-JSON encoding.
    Returns (hex_digest, bytes_length)."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    raw = canonical.encode("utf-8")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _normalize_commit_hash(commit_hash: str) -> str:
    """Strip 0x prefix; lowercase. Raises ValueError if not a 40-char SHA-1
    hex (git commit hash). Sentry's kms-sign on commit_hashes is bound to
    git commit identifiers."""
    h = commit_hash.lower().strip()
    if h.startswith("0x"):
        h = h[2:]
    if len(h) != 40:
        raise ValueError(
            f"commit_hash must be 40-char SHA-1 hex; got len={len(h)}"
        )
    try:
        int(h, 16)
    except ValueError as exc:
        raise ValueError(f"commit_hash must be hex; {exc}") from None
    return h


class SentryDraftGenerator:
    """Phase O2-DRAFT-GENERATION primitive surface for Sentry.

    All three methods are synchronous (pure-Python + sqlite3 writes).
    Higher-level call sites (e.g., the eventual O2 polling loop or an
    operator-triggered endpoint) decide WHEN to invoke them; this module
    is the storage primitive.
    """

    def __init__(self, *, cfg: Any, store: Any) -> None:
        self._cfg = cfg
        self._store = store
        # Resolve agent_id once -- canonical name in tests, Q9 hex in production.
        self._agent_id_used = _resolve_agent_id_for_store(SENTRY_CANONICAL, cfg)

    # ------------------------------------------------------------------
    # 1. tool:kms-sign on draft://commit_hashes/*
    # ------------------------------------------------------------------
    def draft_kms_sign(
        self,
        *,
        commit_hash: str,
        signer_pubkey_hex: str = "",
        signature_payload: Optional[dict] = None,
    ) -> DraftResult:
        """Produce a Sentry kms-sign draft for a git commit hash.

        The signature_payload dict captures the signing context (typically:
        {"commit_hash": ..., "repo": ..., "branch": ..., "ts_ns": ...}).
        Stored as canonical JSON; payload_hash = SHA-256 of canonical bytes.
        kms_sig_present is set to True when signer_pubkey_hex is non-empty
        (caller has at least produced a signature; signature itself NOT
        stored in store -- only its presence flag).
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
        # Canonical fields: ts_ns auto-populated if absent so each draft
        # round-trip is deterministic for the caller.
        payload.setdefault("commit_hash", ch)
        payload.setdefault("ts_ns", time.time_ns())
        if signer_pubkey_hex:
            payload["signer_pubkey_hex"] = str(signer_pubkey_hex)

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        draft_uri = f"{SENTRY_KMS_SIGN_DRAFT_PREFIX}{ch}"

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
            log.warning("SentryDraftGenerator.draft_kms_sign persist failed: %s", exc)
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
    # 2. skill:provenance-recording on draft://attestations/*
    # ------------------------------------------------------------------
    def draft_provenance_record(
        self,
        *,
        record_id: str,
        attestation_payload: dict,
    ) -> DraftResult:
        """Produce a Sentry provenance-recording draft.

        The attestation_payload dict is the canonical attestation body
        (typically: {"event_type": ..., "subject": ..., "evidence_hash": ...,
        "ts_ns": ...}). record_id is the operator-meaningful identifier
        (e.g., a PoAC chain head hash, a session_id, etc.) that becomes
        the draft URI suffix.
        """
        if not record_id or not isinstance(record_id, str):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="provenance-recording",
                agent_id_used=self._agent_id_used,
                error="record_id must be non-empty string",
            )
        if not isinstance(attestation_payload, dict):
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="skill",
                action_name="provenance-recording",
                agent_id_used=self._agent_id_used,
                error="attestation_payload must be dict",
            )

        payload = dict(attestation_payload)
        payload.setdefault("record_id", record_id)
        payload.setdefault("ts_ns", time.time_ns())

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        # Sanitize record_id for URI (keep alphanumerics + dash + underscore;
        # collapse anything else to '_'). This prevents pathological URIs
        # while preserving operator-meaningful identifiers.
        safe = "".join(c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in record_id)
        draft_uri = f"{SENTRY_PROVENANCE_DRAFT_PREFIX}{safe}"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="skill",
                action_name="provenance-recording",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=False,
            )
        except Exception as exc:
            log.warning(
                "SentryDraftGenerator.draft_provenance_record persist failed: %s", exc
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="skill",
                action_name="provenance-recording",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="skill",
            action_name="provenance-recording",
            agent_id_used=self._agent_id_used,
        )

    # ------------------------------------------------------------------
    # 3. tool:pda-attestation-anchor on draft://attestations/*
    # ------------------------------------------------------------------
    #
    # SCAFFOLD ONLY at O2 SUGGEST: this method produces a draft of the
    # PDA anchor payload but does NOT submit any chain transaction. The
    # actual on-chain anchor happens at O3 ACTING (or via operator-
    # authorized direct anchor through chain.record_adjudication).
    # Drafts produced here count toward the O3 readiness gate.
    # ------------------------------------------------------------------
    def draft_pda_anchor(
        self,
        *,
        device_id_hash_hex: str,    # bytes32 hex
        poad_hash_hex: str,         # bytes32 hex
        dual_veto: bool = False,
        anchor_payload: Optional[dict] = None,
    ) -> DraftResult:
        """Produce a Sentry pda-attestation-anchor SCAFFOLD draft.

        The draft captures the inputs that WILL be passed to
        chain.record_adjudication() at O3 ACTING time. No chain call is
        made here -- this is observability + the count_operator_agent_drafts
        signal that drives O3 readiness."""
        if not device_id_hash_hex or not poad_hash_hex:
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="pda-attestation-anchor",
                agent_id_used=self._agent_id_used,
                error="device_id_hash_hex and poad_hash_hex are required",
            )

        # Strip 0x; require 64-char hex (32B)
        def _hex32(h: str, label: str) -> str:
            v = h.lower().strip()
            if v.startswith("0x"):
                v = v[2:]
            if len(v) != 64:
                raise ValueError(f"{label} must be 64-char hex (32B); got len={len(v)}")
            int(v, 16)  # validate
            return v

        try:
            dev_h = _hex32(device_id_hash_hex, "device_id_hash_hex")
            poad_h = _hex32(poad_hash_hex, "poad_hash_hex")
        except ValueError as exc:
            return DraftResult(
                draft_id=0,
                draft_uri="",
                payload_hash="",
                payload_bytes=0,
                action_category="tool",
                action_name="pda-attestation-anchor",
                agent_id_used=self._agent_id_used,
                error=str(exc),
            )

        payload = dict(anchor_payload) if isinstance(anchor_payload, dict) else {}
        payload.setdefault("device_id_hash", dev_h)
        payload.setdefault("poad_hash", poad_h)
        payload.setdefault("dual_veto", bool(dual_veto))
        payload.setdefault("ts_ns", time.time_ns())
        payload.setdefault("scaffold_only", True)  # O2 marker; lifts at O3

        payload_hash, payload_bytes = _sha256_canonical_json(payload)
        draft_uri = f"{SENTRY_PDA_ANCHOR_DRAFT_PREFIX}pda-{poad_h[:16]}"

        try:
            row_id = self._store.insert_operator_agent_draft(
                agent_id=self._agent_id_used,
                action_category="tool",
                action_name="pda-attestation-anchor",
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                kms_sig_present=False,
            )
        except Exception as exc:
            log.warning(
                "SentryDraftGenerator.draft_pda_anchor persist failed: %s", exc
            )
            return DraftResult(
                draft_id=0,
                draft_uri=draft_uri,
                payload_hash=payload_hash,
                payload_bytes=payload_bytes,
                action_category="tool",
                action_name="pda-attestation-anchor",
                agent_id_used=self._agent_id_used,
                error=f"{type(exc).__name__}: {exc}",
            )

        return DraftResult(
            draft_id=int(row_id),
            draft_uri=draft_uri,
            payload_hash=payload_hash,
            payload_bytes=payload_bytes,
            action_category="tool",
            action_name="pda-attestation-anchor",
            agent_id_used=self._agent_id_used,
        )
