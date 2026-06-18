"""MarketplaceMixin ? D-DECON-2 marketplace domain extraction.

Houses the Phase 238-MARKETPLACE LISTING-v1 + curator-review methods,
extracted verbatim from store/_core.py following the ZkbaVpmMixin precedent.
CREATE TABLE statements stay centralized in _core.py._init_schema per D-DECON-2.
Daemon-drafted, operator-reviewed (AGENT-COMMIT chain link #2).
"""
from __future__ import annotations


class MarketplaceMixin:
    """marketplace_listing_log / curator_listing_review_log / pending_listings access."""
    # --- Phase 238-MARKETPLACE: LISTING-v1 anchor history ---

    def insert_marketplace_listing(
        self,
        listing_commitment: str,
        seller_address: str,
        sepproof_commitment: str,
        biometric_snapshot_hash: str,
        corpus_snapshot_hash: str,
        gic_hash: str,
        consent_bitmask: int,
        data_class: int,
        price_iotx: float,
        ipfs_cid: str,
        ipfs_cid_hash: str,
        ts_ns: int,
        anchors_present_count: int = 0,
        trigger_reason: str = "",
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
    ) -> int:
        """Insert one LISTING-v1 row.  Returns row id.

        UNIQUE(listing_commitment) enforces idempotency: re-inserting the
        same commitment returns the existing row id (matches
        biometric_snapshot_log precedent).
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO marketplace_listing_log "
                    "(listing_commitment, seller_address, sepproof_commitment, "
                    " biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
                    " consent_bitmask, data_class, price_iotx, ipfs_cid, ipfs_cid_hash, "
                    " ts_ns, on_chain_confirmed, tx_hash, anchors_present_count, "
                    " trigger_reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(listing_commitment),
                        str(seller_address),
                        str(sepproof_commitment),
                        str(biometric_snapshot_hash),
                        str(corpus_snapshot_hash),
                        str(gic_hash),
                        int(consent_bitmask),
                        int(data_class),
                        float(price_iotx),
                        str(ipfs_cid),
                        str(ipfs_cid_hash),
                        int(ts_ns),
                        1 if on_chain_confirmed else 0,
                        str(tx_hash),
                        int(anchors_present_count),
                        str(trigger_reason)[:128],
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM marketplace_listing_log WHERE listing_commitment = ?",
                    (str(listing_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_latest_marketplace_listing(self) -> dict:
        """Return the most recent listing or empty dict.

        Returned keys mirror insert columns (parsed JSON-friendly).
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT listing_commitment, seller_address, sepproof_commitment, "
                "       biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
                "       consent_bitmask, data_class, price_iotx, ipfs_cid, "
                "       ipfs_cid_hash, ts_ns, on_chain_confirmed, tx_hash, "
                "       anchors_present_count, trigger_reason "
                "FROM marketplace_listing_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {}
        return {
            "listing_commitment":      str(row["listing_commitment"]),
            "seller_address":          str(row["seller_address"]),
            "sepproof_commitment":     str(row["sepproof_commitment"]),
            "biometric_snapshot_hash": str(row["biometric_snapshot_hash"]),
            "corpus_snapshot_hash":    str(row["corpus_snapshot_hash"]),
            "gic_hash":                str(row["gic_hash"]),
            "consent_bitmask":         int(row["consent_bitmask"]),
            "data_class":              int(row["data_class"]),
            "price_iotx":              float(row["price_iotx"]),
            "ipfs_cid":                str(row["ipfs_cid"]),
            "ipfs_cid_hash":           str(row["ipfs_cid_hash"]),
            "ts_ns":                   int(row["ts_ns"]),
            "on_chain_confirmed":      bool(row["on_chain_confirmed"]),
            "tx_hash":                 str(row["tx_hash"]),
            "anchors_present_count":   int(row["anchors_present_count"]),
            "trigger_reason":          str(row["trigger_reason"]),
        }

    def get_marketplace_listing_status(self) -> dict:
        """Return summary of marketplace_listing_log: total + latest.

        Mirrors get_biometric_snapshot_status shape so the operator
        endpoint can return both with consistent keys.
        """
        import time as _t238ls
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM marketplace_listing_log"
            ).fetchone() or (0,))[0]
            anchored = (conn.execute(
                "SELECT COUNT(*) FROM marketplace_listing_log "
                "WHERE on_chain_confirmed = 1"
            ).fetchone() or (0,))[0]
        latest = self.get_latest_marketplace_listing()
        return {
            "total_listings":         int(total),
            "anchored_listings":      int(anchored),
            "latest_commitment":      latest.get("listing_commitment", ""),
            "latest_seller":          latest.get("seller_address", ""),
            "latest_data_class":      latest.get("data_class", 0),
            "latest_price_iotx":      latest.get("price_iotx", 0.0),
            "latest_anchors_present": latest.get("anchors_present_count", 0),
            "latest_ts_ns":           latest.get("ts_ns", 0),
            "latest_on_chain":        latest.get("on_chain_confirmed", False),
            "latest_tx_hash":         latest.get("tx_hash", ""),
            "timestamp":              _t238ls.time(),
        }

    def get_marketplace_listings_by_seller(
        self, seller_address: str, limit: int = 20
    ) -> list[dict]:
        """Return last N listings by seller_address (DESC ts_ns)."""
        if not seller_address:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT listing_commitment, data_class, price_iotx, ipfs_cid, "
                "       ts_ns, on_chain_confirmed, tx_hash, anchors_present_count "
                "FROM marketplace_listing_log "
                "WHERE seller_address = ? "
                "ORDER BY ts_ns DESC LIMIT ?",
                (str(seller_address), int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- Phase 238 Step I — Curator Shadow Infrastructure ---

    def insert_curator_review(
        self,
        listing_commitment: str,
        verdict: str,
        severity: str,
        anchors_recorded_count: int,
        anchors_breakdown_json: str,
        consent_marketplace_bit_set: bool,
        ipfs_resolvable,  # bool | None
        declared_tier: int,
        tier_at_review_time: int,
        tier_changed: bool,
        shadow_mode: bool,
        reason_detail: str,
        trigger_reason: str,
        ts_ns: int,
    ) -> int:
        """Insert one Curator review row.  Returns row id.

        No UNIQUE constraint on listing_commitment — Curator may re-review the
        same listing any number of times (timeline-style ledger).
        """
        ipfs_int = None if ipfs_resolvable is None else (1 if ipfs_resolvable else 0)
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO curator_listing_review_log "
                    "(listing_commitment, verdict, severity, anchors_recorded_count, "
                    " anchors_breakdown_json, consent_marketplace_bit_set, ipfs_resolvable, "
                    " declared_tier, tier_at_review_time, tier_changed, shadow_mode, "
                    " reason_detail, trigger_reason, ts_ns, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(listing_commitment),
                        str(verdict),
                        str(severity),
                        int(anchors_recorded_count),
                        str(anchors_breakdown_json)[:512],
                        1 if consent_marketplace_bit_set else 0,
                        ipfs_int,
                        int(declared_tier),
                        int(tier_at_review_time),
                        1 if tier_changed else 0,
                        1 if shadow_mode else 0,
                        str(reason_detail)[:256],
                        str(trigger_reason)[:128],
                        int(ts_ns),
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            return 0

    def get_curator_review_status(self) -> dict:
        """Return aggregated Curator review summary.

        Shape matches CuratorStatusResult SDK dataclass + GET
        /agent/curator-status endpoint wire contract (10 keys).
        """
        import time as _t238cur
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log"
            ).fetchone() or (0,))[0]
            approved = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log WHERE verdict = 'APPROVED'"
            ).fetchone() or (0,))[0]
            flagged = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log WHERE verdict LIKE 'FLAGGED_%'"
            ).fetchone() or (0,))[0]
            rejected = (conn.execute(
                "SELECT COUNT(*) FROM curator_listing_review_log WHERE verdict LIKE 'REJECTED_%'"
            ).fetchone() or (0,))[0]
            latest = conn.execute(
                "SELECT verdict, listing_commitment, ts_ns "
                "FROM curator_listing_review_log "
                "ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        latest_d = dict(latest) if latest else {}
        return {
            "total_reviews":             int(total),
            "approved_reviews":          int(approved),
            "flagged_reviews":           int(flagged),
            "rejected_reviews":          int(rejected),
            "latest_verdict":            str(latest_d.get("verdict", "")),
            "latest_listing_commitment": str(latest_d.get("listing_commitment", "")),
            "latest_review_ts_ns":       int(latest_d.get("ts_ns", 0)),
            "shadow_mode":               True,  # FROZEN True in O1
            "timestamp":                 _t238cur.time(),
        }

    def get_curator_reviews_for_listing(
        self, listing_commitment: str, limit: int = 50
    ) -> list[dict]:
        """Return all Curator reviews for one listing, DESC ts_ns."""
        if not listing_commitment:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, verdict, severity, anchors_recorded_count, "
                "       anchors_breakdown_json, consent_marketplace_bit_set, "
                "       ipfs_resolvable, declared_tier, tier_at_review_time, "
                "       tier_changed, shadow_mode, reason_detail, "
                "       trigger_reason, ts_ns "
                "FROM curator_listing_review_log "
                "WHERE listing_commitment = ? "
                "ORDER BY ts_ns DESC LIMIT ?",
                (str(listing_commitment), int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_curator_flagged_listings(
        self, since_minutes: int = 1440, limit: int = 50
    ) -> list[dict]:
        """Return distinct listings with at least one FLAGGED_* / REJECTED_*
        verdict within the lookback window.  DESC by latest review ts_ns.

        Caps: limit <= 100; since_minutes <= 30d (43200).
        """
        limit = max(1, min(int(limit), 100))
        since_minutes = max(1, min(int(since_minutes), 43200))
        cutoff_ns = int((time.time() - since_minutes * 60) * 1e9)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT listing_commitment, verdict, severity, "
                "       anchors_recorded_count, declared_tier, tier_at_review_time, "
                "       tier_changed, reason_detail, ts_ns "
                "FROM curator_listing_review_log "
                "WHERE ts_ns >= ? "
                "  AND (verdict LIKE 'FLAGGED_%' OR verdict LIKE 'REJECTED_%') "
                "ORDER BY ts_ns DESC LIMIT ?",
                (cutoff_ns, limit),
            ).fetchall()
        return [dict(r) for r in rows]
