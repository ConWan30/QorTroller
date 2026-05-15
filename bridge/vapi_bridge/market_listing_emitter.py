"""Phase O5-MLGA Stage 10 (MARKET-LISTING autonomy) — fires on Curator review.

Seventh + final autonomous VPM artifact class — completing the
operator's /goal directive (Tasks #85-#90). Fires when the Curator
agent computes a verdict against a marketplace listing (manual
operator trigger OR autonomous Curator loop). Each review auto-
emits a MARKET-LISTING-v1 VPM artifact summarizing the listing's
state at verdict time.

The MARKET-LISTING-v1 compiler is the only one in the family that
emits PROCEDURAL GEOMETRIC ART derived from the ZKBA manifest hash —
the artifact's visual surface is cryptographic in itself.

Design:
  • Event-driven (no polling). Called from _curator_compute_verdict
    which is shared by the operator-triggered endpoint AND the
    autonomous Curator polling loop.
  • Fail-open: any failure logs + returns None; never affects the
    Curator verdict response.

ZKBA class: MARKET (= 7). Proof weight: MARKETPLACE_DERIVED (= 4).
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def _build_integrity_label(*, suspended: bool, verdict: str) -> Dict[str, Any]:
    return {
        "proof_type":             "VPM-MARKET-LISTING",
        "capture_mode":           "live",
        "raw_biometrics_exposed": False,
        "consent_active":         "n/a",
        "zk_verified":            False,
        "on_chain_anchor":        False,
        "proof_weight":           "MARKETPLACE_DERIVED",
        "revocation_status":      "revoked" if suspended else "active",
        "limitations":            [
            f"Autonomous emission on Curator review (verdict={verdict}); "
            "supplements Curator audit-trail surface; procedural "
            "geometric art derived from ZKBA manifest hash (Phase O4 "
            "MARKET-LISTING-v1 visual grammar).",
        ],
    }


def emit_market_listing(
    *,
    store,
    cfg,
    commitment_hex: str,
    listing: Dict[str, Any],
    verdict: str = "APPROVED",
) -> Optional[Dict[str, Any]]:
    """Emit one MARKET-LISTING-v1 VPM artifact for the just-reviewed
    listing. Returns the manifest dict on success, None on failure.
    Never raises.

    Args:
      commitment_hex: 64-char hex listing commitment (already
        validated by caller).
      listing: dict from DataMarketplace.get_listing(...) carrying
        the marketplace_listing_log row fields.
      verdict: Curator verdict label (advisory; encoded in
        integrity label limitations + preimage).
    """
    try:
        h = (commitment_hex or "").lower().removeprefix("0x")
        if len(h) != 64:
            log.warning("MARKET-LISTING emit: invalid commitment_hex")
            return None

        ts_ns = time.time_ns()
        listing = dict(listing or {})

        seller = str(listing.get("seller_address") or
                     ("0x" + "0" * 40))
        ipfs_cid = str(listing.get("ipfs_cid") or "ipfs-unknown")
        tier_milli = int(listing.get("tier_multiplier_milli") or 1000)
        price_iotx = float(listing.get("price_iotx") or 0.0)
        price_milli = int(price_iotx * 1000)
        consent_hex = str(listing.get("consent_hash") or
                          listing.get("consent_hash_hex") or "").lower()
        if consent_hex.startswith("0x"):
            consent_hex = consent_hex[2:]
        if len(consent_hex) != 64:
            # synthesize a stable consent hash placeholder
            consent_hex = hashlib.sha256(
                f"consent_placeholder:{seller}:{h}".encode("utf-8")
            ).hexdigest()
        suspended = bool(listing.get("suspended", False))
        # listing_title is a renderer-only field — default to a stable
        # snippet derived from the commitment if not on the row
        listing_title = str(listing.get("listing_title") or
                            f"Listing {h[:8]}")

        integrity_label = _build_integrity_label(
            suspended=suspended, verdict=verdict,
        )

        snapshot = {
            "vpm_id":                "MARKET-LISTING-v1",
            "listing_commitment_hex": h,
            "listing_title":         listing_title,
            "tier_multiplier_milli": tier_milli,
            "ipfs_cid":              ipfs_cid,
            "consent_hash_hex":      consent_hex,
            "suspended":             suspended,
            "listing_owner_address": seller,
            "price_iotx_milli":      price_milli,
            "verdict":               verdict,
            "ts_ns":                 ts_ns,
        }
        digest = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
            .encode("utf-8")
        ).hexdigest()

        output_dir = (
            Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "artifacts" / "market_listing"
        )
        import sys as _sys
        _scripts_path = str(
            Path(__file__).resolve().parents[2] / "scripts"
        )
        if _scripts_path not in _sys.path:
            _sys.path.insert(0, _scripts_path)
        from vpm_compile_market_listing import (
            build_market_listing_artifact,
        )

        manifest = build_market_listing_artifact(
            listing_commitment_hex=h,
            listing_title=listing_title,
            tier_multiplier_milli=tier_milli,
            ipfs_cid=ipfs_cid,
            consent_hash_hex=consent_hex,
            suspended=suspended,
            listing_owner_address=seller,
            price_iotx_milli=price_milli,
            integrity_label=integrity_label,
            zkba_manifest_hash_hex=digest,
            visual_state="live",
            capture_mode="live",
            output_dir=output_dir,
            ts_ns=ts_ns,
        )

        # commitment_hex disambiguation: the same listing reviewed
        # multiple times would emit the same output_hash. Suffix by
        # ts_ns to give each review a unique commitment_hex row.
        unique_commit = hashlib.sha256(
            (manifest.output_hash_hex + ":" + str(ts_ns))
            .encode("utf-8")
        ).hexdigest()

        preimage_json = json.dumps(snapshot, sort_keys=True,
                                    separators=(",", ":"))
        row_id = store.insert_vpm_artifact(
            commitment_hex=unique_commit,
            vpm_id="MARKET-LISTING-v1",
            zkba_class=7,             # ZKBAClass.MARKET
            proof_weight=4,           # MARKETPLACE_DERIVED
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
            "MARKET-LISTING emitted: listing=%s... verdict=%s row=%d "
            "suspended=%s",
            h[:16], verdict, row_id, suspended,
        )
        return {
            "action": "emitted",
            "row": row_id,
            "commitment_hex": unique_commit,
            "listing_commitment_hex": h,
            "verdict": verdict,
        }
    except Exception as exc:  # noqa: BLE001
        import traceback as _tb
        log.warning(
            "MARKET-LISTING emit failed for commit=%s: %s\n%s",
            commitment_hex[:16] if commitment_hex else "?",
            exc, _tb.format_exc(),
        )
        return None
