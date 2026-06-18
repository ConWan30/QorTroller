"""ConsentMixin ? D-DECON-2 consent domain extraction (diff-oracle reconstructed).

Extracted verbatim from store/_core.py via the diff-oracle pattern
(removal diff is the canonical source). CREATE TABLE statements stay
centralized in _core.py._init_schema per D-DECON-2.
"""
from __future__ import annotations

import time


class ConsentMixin:
    """Domain methods extracted from Store; resolved via MRO."""
    def _check_consent_gate(
        self,
        device_id: str,
        operation: str,
        category: str | None = None,
    ) -> None:
        """Raise ValueError + log if device has revoked consent or erasure_requested.

        Callers must check self._consent_ledger_enabled before calling this method.
        Fails open for unknown devices (no record = allowed) to avoid blocking new
        devices before consent is registered via POST /agent/register-consent.

        Phase 237-CONSENT extension: when `category` is provided, the gate checks
        the per-category record (consent_type=category) instead of the default
        biometric_processing record. Backward-compatible: callers omitting
        `category` retain Phase 161 semantics exactly.
        """
        consent_type = category if category else "biometric_processing"
        status = self.get_consent_status(device_id, consent_type)
        if status["erasure_requested"] or status["revoked"]:
            reason = "erasure_requested" if status["erasure_requested"] else "consent_revoked"
            with self._conn() as con:
                con.execute(
                    "INSERT INTO consent_gate_violation_log"
                    " (device_id, operation, blocked_reason, created_at)"
                    " VALUES (?,?,?,?)",
                    (device_id, operation, reason, time.time()),
                )
            raise ValueError(
                f"Consent gate: device {device_id!r} blocked for operation "
                f"{operation!r} (category={consent_type!r}) — reason: {reason} "
                f"(GDPR Art.7/17, Phase 161 BP-002 / Phase 237-CONSENT)."
            )

    # --- Phase 237-CONSENT: per-category consent helpers ---
    #
    # Thin wrappers over the Phase 160 consent_ledger primitives. Each helper
    # accepts a category (string name from consent_categories.CATEGORY_NAMES)
    # and writes/reads `consent_ledger` with `consent_type=category`. The
    # UNIQUE(device_id, consent_type) constraint plus the existing UPSERT in
    # insert_consent_record means re-grant on the same category just updates
    # the existing row.

    def grant_category_consent(
        self,
        device_id: str,
        category: str,
        ttl_s: int = 0,
        consent_hash: str = "",
        ts_ns: int | None = None,
    ) -> int:
        """Grant per-category consent (Phase 237-CONSENT).

        Args:
            device_id:    Device identifier.
            category:     Category name from consent_categories.CATEGORY_NAMES
                          (TOURNAMENT_GATE / ANONYMIZED_RESEARCH / MANUFACTURER_CERT / MARKETPLACE).
            ttl_s:        Consent TTL in seconds. 0 = no expiry. Stored as the
                          consent_ts offset for now (full expiry enforcement at
                          gate-check time is Phase 238 work).
            consent_hash: Optional FROZEN-v1 hex commitment from
                          consent_categories.compute_consent_hash() — 64 hex chars or "".
            ts_ns:        Grant time in ns. Defaults to time.time_ns().

        Returns:
            Row id from the underlying consent_ledger.
        """
        from ..consent_categories import NAME_TO_CATEGORY  # validate category name
        if category not in NAME_TO_CATEGORY:
            raise ValueError(
                f"unknown consent category: {category!r}. "
                f"Valid: {sorted(NAME_TO_CATEGORY.keys())}"
            )
        if consent_hash and len(consent_hash) != 64:
            raise ValueError(f"consent_hash must be 64 hex chars or empty, got {len(consent_hash)}")
        # Reuse Phase 160 UPSERT — re-grant updates the existing row.
        # consent_ts persists the grant timestamp; ttl_s is advisory metadata
        # for now (full expiry-at-gate-check is Phase 238 work).
        consent_ts = (ts_ns / 1e9) if ts_ns is not None else None
        row_id = self.insert_consent_record(
            device_id=device_id,
            consent_type=category,
            consent_given=True,
            consent_ts=consent_ts,
        )
        # F1 2026-06-05 — append-only event log side-effect. consent_ledger
        # upsert remains authoritative for current-state lookups; the event
        # log records the IMMUTABLE event stream so a re-grant after revoke
        # cannot erase intermediate transitions. Fail-open per
        # insert_consent_event's contract.
        try:
            self.insert_consent_event(
                device_id=device_id,
                category=category,
                action="GRANT",
                ts=consent_ts,
            )
        except Exception:
            pass  # fail-open: ledger upsert succeeded; event log is secondary
        return row_id

    def revoke_category_consent(
        self,
        device_id: str,
        category: str,
        reason: str = "",
    ) -> bool:
        """Revoke per-category consent (Phase 237-CONSENT). Returns True if a row updated.

        Wraps Phase 160 revoke_consent() with category enum validation.
        Also appends a REVOKE row to the F1 consent_event_log so the
        action appears in regulator-facing receipt timelines (the
        consent_ledger row is mutated in place and would otherwise lose
        the historical action on a subsequent re-grant).
        """
        from ..consent_categories import NAME_TO_CATEGORY
        if category not in NAME_TO_CATEGORY:
            raise ValueError(f"unknown consent category: {category!r}")
        updated = self.revoke_consent(
            device_id=device_id,
            consent_type=category,
            reason=reason,
        )
        if updated:
            try:
                self.insert_consent_event(
                    device_id=device_id,
                    category=category,
                    action="REVOKE",
                    reason=reason,
                )
            except Exception:
                pass  # fail-open: ledger update succeeded; event log is secondary
        return updated

    def get_category_consent_status(
        self,
        device_id: str,
        category: str | None = None,
    ) -> dict:
        """Return per-category consent state for a device (Phase 237-CONSENT).

        When `category` is provided, returns the single-category status dict
        (same shape as Phase 160 get_consent_status, with `category` key added).

        When `category` is None, returns aggregated status across all four
        categories: {"device_id": ..., "categories": {NAME: status_dict, ...}}.
        Any category with no record reports `granted=False, found=False`
        (fail-closed by absence — operationally safe).
        """
        from ..consent_categories import ALL_CATEGORIES, CATEGORY_NAMES, NAME_TO_CATEGORY

        if category is not None:
            if category not in NAME_TO_CATEGORY:
                raise ValueError(f"unknown consent category: {category!r}")
            base = self.get_consent_status(device_id, consent_type=category)
            return {
                **base,
                "category": category,
                "granted": bool(base["consent_given"]) and not base["revoked"]
                                                       and not base["erasure_requested"],
            }

        out: dict[str, dict] = {}
        for cat in ALL_CATEGORIES:
            name = CATEGORY_NAMES[cat]
            base = self.get_consent_status(device_id, consent_type=name)
            out[name] = {
                **base,
                "category": name,
                "granted": bool(base["consent_given"]) and not base["revoked"]
                                                       and not base["erasure_requested"],
            }
        return {
            "device_id":  device_id,
            "categories": out,
        }

    def get_consent_gate_status(self) -> dict:
        """Return consent gate violation summary (Phase 161 BP-002)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT COUNT(*) as total, MAX(created_at) as last_ts,"
                " MAX(device_id) as last_device"
                " FROM consent_gate_violation_log"
            ).fetchone()
        d = dict(row) if row else {}
        return {
            "violations_total":      int(d.get("total") or 0),
            "last_violation_ts":     d.get("last_ts"),
            "last_violation_device": d.get("last_device"),
        }

    def get_active_consent_devices(self) -> list:
        """Return devices with active consent (Phase 162 WIF-021)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT device_id, consent_type, consent_ts FROM consent_ledger"
                " WHERE consent_given=1 AND erasure_requested=0"
                "   AND (revoked_at IS NULL)"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_consent_corpus_coverage(self) -> dict:
        """Return consent coverage statistics for corpus defensibility (Phase 162 WIF-021)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT"
                "  COUNT(*) as total,"
                "  SUM(CASE WHEN consent_given=1 AND erasure_requested=0"
                "           AND revoked_at IS NULL THEN 1 ELSE 0 END) as active_count,"
                "  SUM(CASE WHEN revoked_at IS NOT NULL THEN 1 ELSE 0 END) as revoked_count,"
                "  SUM(CASE WHEN erasure_requested=1 THEN 1 ELSE 0 END) as erasure_count"
                " FROM consent_ledger"
            ).fetchone()
        d = dict(row) if row else {}
        total   = int(d.get("total",        0) or 0)
        active  = int(d.get("active_count", 0) or 0)
        revoked = int(d.get("revoked_count", 0) or 0)
        erasure = int(d.get("erasure_count", 0) or 0)
        return {
            "total_registered":        total,
            "active_consent_count":    active,
            "revoked_count":           revoked,
            "erasure_requested_count": erasure,
            "consent_corpus_defensible": (revoked == 0 and erasure == 0 and total > 0),
        }

    def insert_consent_snapshot(
        self,
        commit_hash: str,
        n_consented_at_commit: int,
        revoked_count_at_commit: int,
        erasure_count_at_commit: int,
    ) -> None:
        """Record consent coverage snapshot linked to a ratio commit (Phase 164 WIF-023).

        Called immediately after insert_separation_ratio_registry_log so that
        post-commit revocations produce a verifiable delta chain.
        commit_hash links to separation_ratio_registry_log.commit_hash.
        """
        with self._conn() as con:
            con.execute(
                "INSERT INTO consent_snapshot_log"
                " (commit_hash, n_consented_at_commit, revoked_count_at_commit,"
                "  erasure_count_at_commit, snapshot_ts, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    commit_hash,
                    n_consented_at_commit,
                    revoked_count_at_commit,
                    erasure_count_at_commit,
                    time.time(),
                    time.time(),
                ),
            )

    # ------------------------------------------------------------------
    # Phase 165 — Post-Erasure Separation Ratio Recompute (WIF-024)
    # ------------------------------------------------------------------
