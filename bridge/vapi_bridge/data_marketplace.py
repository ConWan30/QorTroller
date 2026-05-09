"""Phase 238-MARKETPLACE Step E — Bridge orchestration for the Provenance-Anchored
Listing Layer (PALL).

Composes:
  - listing_primitive.py            LISTING-v1 FROZEN commitment computation
  - chain.anchor_listing_commitment AdjudicationRegistry on-chain anchor (Step C)
  - store.insert_marketplace_listing local listing log persistence (Step B)
  - pinata_client.pin_json          IPFS metadata archive (reused — no rebuild)

Operator-triggered listing creation flow (called from POST /operator/list-data-session):

  1. Validate inputs + verify seller anchors are anchored on-chain (best-effort)
  2. Pin listing metadata JSON to IPFS via Pinata -> CIDv1 string
  3. Compute LISTING-v1 commitment from anchored fields + IPFS CID hash
  4. Anchor commitment on AdjudicationRegistry (best-effort, fail-open per kill-switch)
  5. Insert into marketplace_listing_log with on_chain_confirmed flag
  6. Return result dict with commitment + tier preview + tx_hash + cid

Tier preview (bridge-side computation):
  Mirrors Step D contract's _computeTier — counts non-zero anchors, returns
  bridge's best estimate.  The on-chain extension contract is the
  authoritative source post-deploy; bridge tier is informational pre-deploy.

Three-zone privacy (extends Phase 237 Step H):
  Zone 1 (this module / bridge): sees raw listing metadata + biometric session data
  Zone 2 (IPFS / Pinata): sees encrypted-at-rest archive (only the metadata
                          dict; not the underlying biometric raw data)
  Zone 3 (IoTeX chain via AdjudicationRegistry): sees only LISTING-v1
                                                   commitment (32 bytes)
  Zone 4 (buyer): sees CID -> retrieves archive off-chain after purchase

Each zone has strictly less information than the previous.  Three-zone
preserved (zones 1-3); listing adds zone 4 for buyer-side data delivery.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger(__name__)


# ── Tier enum (mirrors VAPIDataMarketplaceListings.sol Tier enum) ───────────

TIER_BASIC    = 0   # 1.0x — CONSENT only (or no anchored components)
TIER_VERIFIED = 1   # 1.5x — exactly 1 anchor present
TIER_ATTESTED = 2   # 2.0x — 2 or 3 anchors present
TIER_PREMIUM  = 3   # 3.0x — all 4 anchors present

_TIER_NAMES = {
    TIER_BASIC:    "Basic",
    TIER_VERIFIED: "Verified",
    TIER_ATTESTED: "Attested",
    TIER_PREMIUM:  "Premium",
}

_TIER_MULTIPLIERS_BPS = {
    TIER_BASIC:    10000,
    TIER_VERIFIED: 15000,
    TIER_ATTESTED: 20000,
    TIER_PREMIUM:  30000,
}


def _compute_tier_from_count(anchors_present: int) -> int:
    """Mirror the Step D contract's _computeTier logic.  Bridge-side preview
    only — on-chain contract is authoritative post-deploy."""
    if anchors_present <= 0:
        return TIER_BASIC
    if anchors_present == 1:
        return TIER_VERIFIED
    if anchors_present <= 3:
        return TIER_ATTESTED
    return TIER_PREMIUM


# ── DataMarketplace orchestration ──────────────────────────────────────────

class DataMarketplace:
    """Phase 238 PALL bridge orchestration.

    Composes IPFS pinning + commitment computation + on-chain anchor +
    local log persistence into a single create_listing call.

    Usage:
        marketplace = DataMarketplace(store, chain, cfg, pinata_client)
        result = await marketplace.create_listing(
            seller_address="0x...",
            sepproof_commitment=b"...",  # 32 bytes or None
            biometric_snapshot_hash=b"...",
            corpus_snapshot_hash=b"...",
            gic_hash=b"...",
            consent_bitmask=8,           # bit 3 = MARKETPLACE
            data_class=4,                 # BIOMETRIC
            price_iotx=5.0,
            listing_metadata={...},       # arbitrary dict, JSON-pinned to IPFS
            trigger_reason="post_session_pall_2026_05_09",
        )
    """

    def __init__(self, store, chain, cfg, pinata_client=None):
        self._store = store
        self._chain = chain
        self._cfg = cfg
        self._pinata = pinata_client  # may be None (testing or Pinata not configured)

    async def create_listing(
        self,
        seller_address: str,
        sepproof_commitment: Optional[bytes],
        biometric_snapshot_hash: Optional[bytes],
        corpus_snapshot_hash: Optional[bytes],
        gic_hash: Optional[bytes],
        consent_bitmask: int,
        data_class: int,
        price_iotx: float,
        listing_metadata: dict,
        trigger_reason: str = "",
    ) -> dict:
        """Orchestrate listing creation end-to-end.

        Returns dict with keys:
          - row_id (int): bridge log row id
          - listing_commitment (str): 64-char hex of LISTING-v1 commitment
          - ipfs_cid (str): CIDv1 string of pinned metadata, or "" if pinning skipped
          - ipfs_cid_hash (str): SHA-256 hex of CID string
          - tier (int): bridge-side tier preview (0..3)
          - tier_name (str): "Basic" / "Verified" / "Attested" / "Premium"
          - multiplier_bps (int): basis points multiplier (10000=1.0x)
          - anchors_present (int): count of non-zero anchor inputs
          - on_chain_confirmed (bool): AdjudicationRegistry anchor result
          - tx_hash (str): IoTeX testnet tx hash, or "" if not anchored
          - error (str): non-empty on failure; otherwise ""

        Never raises — all errors surface as result.error string.
        """
        import time as _t238dm

        result = {
            "row_id":              0,
            "listing_commitment":  "",
            "ipfs_cid":             "",
            "ipfs_cid_hash":        "",
            "tier":                 TIER_BASIC,
            "tier_name":            _TIER_NAMES[TIER_BASIC],
            "multiplier_bps":       _TIER_MULTIPLIERS_BPS[TIER_BASIC],
            "anchors_present":      0,
            "on_chain_confirmed":   False,
            "tx_hash":               "",
            "error":                 "",
        }

        try:
            from .listing_primitive import (
                compute_listing_commitment, compute_ipfs_cid_hash,
                count_anchors_present, _CONSENT_BIT_MARKETPLACE,
            )

            # Step 1: pre-flight bitmask check (fail-fast for nice error UX)
            if not (int(consent_bitmask) & _CONSENT_BIT_MARKETPLACE):
                result["error"] = (
                    "consent_bitmask missing MARKETPLACE bit (3) — "
                    "seller has not authorized marketplace distribution"
                )
                return result

            # Step 2: pin metadata to IPFS (best-effort; mock when Pinata unconfigured)
            ipfs_cid = ""
            if self._pinata is not None:
                try:
                    name = f"vapi-listing-{trigger_reason or 'unnamed'}-{int(_t238dm.time())}"
                    pin_result = await self._pinata.pin_json(
                        content=listing_metadata,
                        name=name,
                        cid_version=1,
                    )
                    ipfs_cid = pin_result.get("IpfsHash", "")
                    log.info(
                        "marketplace.create_listing: pinned to IPFS cid=%s name=%s",
                        ipfs_cid[:32], name,
                    )
                except Exception as exc:
                    log.warning(
                        "marketplace.create_listing: IPFS pinning failed (%s); "
                        "listing will record ipfs_cid=''", exc,
                    )
                    ipfs_cid = ""
            else:
                log.info(
                    "marketplace.create_listing: PinataClient not configured — "
                    "skipping IPFS pin (mock mode)"
                )

            ipfs_cid_hash_bytes = compute_ipfs_cid_hash(ipfs_cid) if ipfs_cid else b"\x00" * 32

            # Step 3: compute LISTING-v1 commitment
            ts_ns = _t238dm.time_ns()
            commitment = compute_listing_commitment(
                sepproof_commitment     = sepproof_commitment,
                biometric_snapshot_hash = biometric_snapshot_hash,
                corpus_snapshot_hash    = corpus_snapshot_hash,
                gic_hash                = gic_hash,
                consent_bitmask         = int(consent_bitmask),
                data_class              = int(data_class),
                price_iotx              = float(price_iotx),
                ipfs_cid                = ipfs_cid,
                ts_ns                   = ts_ns,
            )

            # Step 4: bridge-side tier preview
            anchors_count = count_anchors_present(
                sepproof_commitment, biometric_snapshot_hash,
                corpus_snapshot_hash, gic_hash,
            )
            tier = _compute_tier_from_count(anchors_count)

            # Step 5: anchor on AdjudicationRegistry (best-effort, fail-open)
            tx_hash_hex = ""
            anchored = False
            if self._chain is not None:
                try:
                    tx_hash_hex, anchored = await self._chain.anchor_listing_commitment(
                        commitment.hex(),
                    )
                except Exception as exc:
                    log.warning(
                        "marketplace.create_listing: anchor_listing_commitment "
                        "raised (%s); listing will record on_chain_confirmed=False",
                        exc,
                    )
                    tx_hash_hex = ""
                    anchored = False

            # Step 6: persist to local log
            import asyncio as _asyncio238dm
            row_id = await _asyncio238dm.to_thread(
                self._store.insert_marketplace_listing,
                commitment.hex(),
                str(seller_address),
                _bytes_to_hex(sepproof_commitment),
                _bytes_to_hex(biometric_snapshot_hash),
                _bytes_to_hex(corpus_snapshot_hash),
                _bytes_to_hex(gic_hash),
                int(consent_bitmask),
                int(data_class),
                float(price_iotx),
                ipfs_cid,
                ipfs_cid_hash_bytes.hex(),
                ts_ns,
                int(anchors_count),
                str(trigger_reason)[:128],
                bool(anchored),
                tx_hash_hex or "",
            )

            result.update({
                "row_id":              int(row_id),
                "listing_commitment":  commitment.hex(),
                "ipfs_cid":             ipfs_cid,
                "ipfs_cid_hash":        ipfs_cid_hash_bytes.hex(),
                "tier":                 tier,
                "tier_name":            _TIER_NAMES[tier],
                "multiplier_bps":       _TIER_MULTIPLIERS_BPS[tier],
                "anchors_present":      anchors_count,
                "on_chain_confirmed":   bool(anchored),
                "tx_hash":               tx_hash_hex or "",
                "ts_ns":                 ts_ns,
            })
            return result
        except ValueError as exc:
            # ValueError from compute_listing_commitment validation
            result["error"] = str(exc)
            return result
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
            return result

    def get_listing_status(self) -> dict:
        """Return the marketplace listing summary (delegates to store)."""
        return self._store.get_marketplace_listing_status()

    def get_listing(self, listing_commitment: str) -> dict:
        """Return a specific listing by commitment hex (latest row matching).

        For now we use latest-by-commitment via store filter; future caller can
        add a dedicated by-commitment store helper if needed.
        """
        with self._store._conn() as conn:
            row = conn.execute(
                "SELECT listing_commitment, seller_address, sepproof_commitment, "
                "       biometric_snapshot_hash, corpus_snapshot_hash, gic_hash, "
                "       consent_bitmask, data_class, price_iotx, ipfs_cid, "
                "       ipfs_cid_hash, ts_ns, on_chain_confirmed, tx_hash, "
                "       anchors_present_count, trigger_reason "
                "FROM marketplace_listing_log WHERE listing_commitment = ? LIMIT 1",
                (str(listing_commitment),),
            ).fetchone()
        if row is None:
            return {}
        d = dict(row)
        # Add tier + multiplier preview
        anchors = int(d.get("anchors_present_count", 0))
        tier = _compute_tier_from_count(anchors)
        d["tier"] = tier
        d["tier_name"] = _TIER_NAMES[tier]
        d["multiplier_bps"] = _TIER_MULTIPLIERS_BPS[tier]
        return d

    def get_listings_by_seller(
        self, seller_address: str, limit: int = 20
    ) -> list[dict]:
        """Return last N listings by seller (DESC ts_ns)."""
        rows = self._store.get_marketplace_listings_by_seller(
            seller_address, limit=limit
        )
        # Enrich with tier preview
        for r in rows:
            anchors = int(r.get("anchors_present_count", 0))
            tier = _compute_tier_from_count(anchors)
            r["tier"] = tier
            r["tier_name"] = _TIER_NAMES[tier]
            r["multiplier_bps"] = _TIER_MULTIPLIERS_BPS[tier]
        return rows


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bytes_to_hex(b: Optional[bytes]) -> str:
    """None / b'' -> "" (empty string), else hex string."""
    if b is None or b == b"":
        return ""
    if isinstance(b, (bytes, bytearray)):
        return bytes(b).hex()
    return str(b)
