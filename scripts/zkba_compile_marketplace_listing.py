"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Marketplace Listing Card artifact builder.

Fourth ZKBA artifact target after:
  - GIC Continuity Ledger Alpha (commit 3b3081d3; class 2, CHAIN_ONLY)
  - VHP Verification Card        (commit 4f399282; class 3, CHAIN_ONLY)
  - AIT Separation Snapshot      (commit bdbcf67f; class 1, CALIBRATION_PLUS_CONTEXT)

Strategic value of this artifact:

1. **First Curator-lane artifact.** All prior ZKBA artifacts wrote to
   `zk_artifacts/` under Sentry's Cedar v2 lane authority. Marketplace
   Listing Cards write to `zk_listings/` under Curator's authority —
   the first ZKBA artifact to exercise a non-Sentry lane. This is the
   structural test that the cross-fleet skill-separation invariant
   (CFSS) under the Cedar v2 bundles works across agents in practice,
   not just in the audit harness's lane matrix.

2. **First MARKETPLACE_DERIVED proof weight.** Matches
   DEFAULT_PROOF_WEIGHT_BY_CLASS[MARKET] in the G4 validator. Third
   distinct proof weight through the Layer 7 pipeline (CHAIN_ONLY,
   CALIBRATION_PLUS_CONTEXT, MARKETPLACE_DERIVED).

3. **Cross-primitive composition.** The Marketplace Listing Card
   composes state from TWO existing FROZEN-v1 primitives:
     - LISTING-v1 (Phase 238 — listing_commitment is the 32B hash from
       VAPIDataMarketplaceListings.sol's anchored listing state)
     - CONSENT v1 (Phase 237 — consent_hash binds the buyer-visible
       MARKETPLACE category consent state)
   This is the first ZKBA artifact whose preimage includes more than
   one primitive's output. It demonstrates that PATTERN-017 composes
   primitives compositionally, not just in isolation.

Composition profile:
  - ZKBAClass.MARKET                       (= 7 in the FROZEN-v1 enum)
  - ProofWeightClass.MARKETPLACE_DERIVED   (matches the default per
                                            DEFAULT_PROOF_WEIGHT_BY_CLASS)
  - Single 32-byte component hash composed from:
        SHA-256(
            listing_commitment(32)
            || tier_multiplier_milli_be(8)   # tier × 1000 as uint64
            || ipfs_cid_root(32)             # SHA-256 of canonical CID bytes
            || consent_hash(32)              # MARKETPLACE consent commitment
            || suspended_byte(1)             # 0x01 if suspended, 0x00 if active
        )

Owning agent: **Curator** (canonical name "curator"). Marketplace Listing
Cards write to the `zk_listings/` lane authorized by
curator_o2_suggest_v2.json (Cedar v2 LIVE since commit ad0f7d11).

Track 1 invariants enforced:
  - No on-chain submission (anchor_tx_hash stays NULL in zkba_artifact_log)
  - Caller-supplied state inputs (no live chain reads)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs → same output bytes)

Tier multiplier encoding (uint64 milli):
  Tier 1.0x → 1000
  Tier 1.5x → 1500
  Tier 2.0x → 2000
  Tier 3.0x → 3000
Other tiers permitted at v1.0; downstream verifiers MUST NOT assume the
4-tier closed set holds for future listing classes.

Run via CLI (offline; uses provided inputs):
    python scripts/zkba_compile_marketplace_listing.py \\
        --listing-commitment 0xabc1...64chars \\
        --tier-multiplier-milli 2000 \\
        --ipfs-cid bafybeig... \\
        --consent-hash 0xdef2...64chars \\
        --suspended 0 \\
        --ts-ns 1778900000000000000

Author: VAPI Architect (post-AIT fourth-artifact ship 2026-05-12)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE_DIR = os.path.normpath(os.path.join(_HERE, "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from vapi_bridge.zkba_artifact import (  # noqa: E402
    ZKBAClass,
    ProofWeightClass,
    compute_zkba_commitment,
)
from vsd_ui_compiler import ZKBAManifest, brand_card_css_v2, compile_artifact  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic component composition
# ---------------------------------------------------------------------------

def _parse_hex32(s: str, field_name: str) -> bytes:
    """Parse a 32-byte hex value (with or without 0x prefix) — defensive."""
    if not isinstance(s, str):
        raise ValueError(f"{field_name} must be hex string; got {type(s).__name__}")
    s2 = s.lower()
    if s2.startswith("0x"):
        s2 = s2[2:]
    if len(s2) != 64:
        raise ValueError(
            f"{field_name} must be 64 hex chars (32 bytes); got {len(s2)} chars"
        )
    try:
        return bytes.fromhex(s2)
    except ValueError as exc:
        raise ValueError(f"{field_name} not valid hex: {exc}") from exc


def _compose_market_component(
    *,
    listing_commitment: bytes,
    tier_multiplier_milli: int,
    ipfs_cid: str,
    consent_hash: bytes,
    suspended: bool,
) -> bytes:
    """Compose a single 32-byte ZKBA component from marketplace listing state.

    Byte layout (FROZEN at v1; downstream verifiers reproduce this exact order):

        SHA-256(
            listing_commitment(32)        # 32 bytes (raw)
            || tier_multiplier_milli_be(8) # 8 bytes (uint64 BE; tier × 1000)
            || ipfs_cid_root(32)           # 32 bytes (SHA-256 of canonical CID
                                           #           UTF-8 bytes)
            || consent_hash(32)            # 32 bytes (raw)
            || suspended_byte(1)           # 1 byte: 0x01 if suspended, else 0x00
        )                                  # = 32 bytes after SHA-256

    The IPFS CID is hashed (rather than included verbatim) so the
    preimage size is fixed-length regardless of v0 vs v1 CID encoding;
    downstream verifiers reproduce the SHA-256 of the canonical CID
    UTF-8 bytes (no normalization beyond UTF-8 encoding).
    """
    if not isinstance(listing_commitment, (bytes, bytearray)) or len(listing_commitment) != 32:
        raise ValueError(
            f"listing_commitment must be 32 raw bytes; got {len(listing_commitment)} bytes"
        )
    if not isinstance(tier_multiplier_milli, int) or tier_multiplier_milli < 0 or tier_multiplier_milli > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(
            f"tier_multiplier_milli must be uint64; got {tier_multiplier_milli!r}"
        )
    if not isinstance(ipfs_cid, str) or not ipfs_cid:
        raise ValueError(f"ipfs_cid must be non-empty str; got {ipfs_cid!r}")
    if not isinstance(consent_hash, (bytes, bytearray)) or len(consent_hash) != 32:
        raise ValueError(
            f"consent_hash must be 32 raw bytes; got {len(consent_hash)} bytes"
        )

    ipfs_cid_root = hashlib.sha256(ipfs_cid.encode("utf-8")).digest()
    suspended_byte = b"\x01" if suspended else b"\x00"

    preimage = (
        bytes(listing_commitment)
        + tier_multiplier_milli.to_bytes(8, "big")
        + ipfs_cid_root
        + bytes(consent_hash)
        + suspended_byte
    )
    assert len(preimage) == 32 + 8 + 32 + 32 + 1 == 105
    return hashlib.sha256(preimage).digest()


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_market_listing_html(inputs: dict) -> str:
    """Deterministic HTML rendering of a Marketplace Listing Card.

    Inputs dict shape (all keys required; all values deterministic):
      - "listing_commitment_hex":   str (64 lowercase hex)
      - "tier_multiplier_milli":    int (uint64; tier × 1000)
      - "ipfs_cid":                 str (canonical CID)
      - "consent_hash_hex":         str (64 lowercase hex)
      - "suspended":                bool
      - "zkba_commitment_hex":      str (64 lowercase hex)
      - "ts_ns":                    int (uint64; caller-supplied)
    """
    listing_hex = inputs["listing_commitment_hex"]
    tier_milli = int(inputs["tier_multiplier_milli"])
    ipfs_cid = inputs["ipfs_cid"]
    consent_hex = inputs["consent_hash_hex"]
    suspended = bool(inputs["suspended"])
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])

    tier_display = f"{tier_milli / 1000.0:.2f}x"
    status_label = "SUSPENDED" if suspended else "ACTIVE"
    status_color = "#d65b78" if suspended else "#5bd6a3"

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>Marketplace Listing - {listing_hex[:12]}</title>\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "  <meta name=\"vpm-template-version\" content=\"2\">\n"
        "  <style>\n"
        f"{brand_card_css_v2()}"
        "    .weight { background: #1b2433; color: #8a98ab; padding: 2px 8px; "
        "border-radius: 4px; }\n"
        f"    .status-badge {{ background: {status_color}; color: #04060a; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; }}\n"
        "    .tier-badge { background: #f0a868; color: #04060a; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>Marketplace Listing Card</h1>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Listing commitment: <code>0x{listing_hex}</code></div>\n"
        f"    <div>Tier multiplier: <span class=\"tier-badge\">{tier_display}</span> "
        f"(milli = {tier_milli})</div>\n"
        f"    <div>IPFS CID: <code>{ipfs_cid}</code></div>\n"
        f"    <div>Consent hash (MARKETPLACE category): <code>0x{consent_hex}</code></div>\n"
        f"    <div>Status: <span class=\"status-badge\">{status_label}</span></div>\n"
        f"    <div>ZKBA commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">MARKETPLACE_DERIVED</span></div>\n"
        "  </div>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "ZKBA class MARKET (= 7 in PATTERN-017 FROZEN-v1 enum). "
        "Phase O3-ZKBA-TRACK1 Track 2 fourth-artifact ship — Curator "
        "lane authority via Cedar v2 zk_listings/. "
        "Cross-primitive composition: LISTING-v1 (Phase 238) + "
        "CONSENT v1 (Phase 237 MARKETPLACE category). "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_marketplace_listing_artifact(
    *,
    store,
    listing_commitment_hex: str,
    tier_multiplier_milli: int,
    ipfs_cid: str,
    consent_hash_hex: str,
    suspended: bool,
    output_dir: Path,
    ts_ns: int,
) -> ZKBAManifest:
    """Build a Marketplace Listing Card ZKBA artifact deterministically.

    Composes the ZKBA commitment from on-chain marketplace listing state
    + MARKETPLACE-category consent hash, calls compile_artifact() to
    emit HTML + manifest, and inserts a row into zkba_artifact_log.

    Args:
        store:                  bridge.vapi_bridge.store.Store instance.
        listing_commitment_hex: 32-byte listing commitment from
                                VAPIDataMarketplaceListings as hex (with
                                or without 0x prefix).
        tier_multiplier_milli:  Tier multiplier × 1000 (uint64; e.g. 2000
                                for tier 2.0x).
        ipfs_cid:               Canonical IPFS CID string (v0 or v1).
        consent_hash_hex:       32-byte CONSENT v1 commitment hash for the
                                seller's MARKETPLACE category (Phase 237).
        suspended:              bool — VAPIDataMarketplaceListings's
                                listing.suspended state.
        output_dir:             Directory under which to write artifact +
                                manifest.
        ts_ns:                  Caller-supplied uint64 timestamp.

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    listing_commitment = _parse_hex32(listing_commitment_hex, "listing_commitment")
    consent_hash = _parse_hex32(consent_hash_hex, "consent_hash")

    # Normalize the input hex strings (drop 0x prefix, lowercase) for
    # downstream rendering + preimage_json.
    listing_norm = listing_commitment_hex.lower()
    if listing_norm.startswith("0x"):
        listing_norm = listing_norm[2:]
    consent_norm = consent_hash_hex.lower()
    if consent_norm.startswith("0x"):
        consent_norm = consent_norm[2:]

    # Compose component hash from marketplace + consent state
    component = _compose_market_component(
        listing_commitment=listing_commitment,
        tier_multiplier_milli=tier_multiplier_milli,
        ipfs_cid=ipfs_cid,
        consent_hash=consent_hash,
        suspended=suspended,
    )

    # Compute the ZKBA commitment
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.MARKET,
        proof_weight=ProofWeightClass.MARKETPLACE_DERIVED,
        component_hashes=(component,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    inputs = {
        "listing_commitment_hex":  listing_norm,
        "tier_multiplier_milli":   int(tier_multiplier_milli),
        "ipfs_cid":                str(ipfs_cid),
        "consent_hash_hex":        consent_norm,
        "suspended":               bool(suspended),
        "zkba_commitment_hex":     zkba_hex,
        "ts_ns":                   int(ts_ns),
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.MARKET,
        proof_weight=ProofWeightClass.MARKETPLACE_DERIVED,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_market_listing_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.MARKET),
        "proof_weight": int(ProofWeightClass.MARKETPLACE_DERIVED),
        "component_hashes_hex": [component.hex()],
        "ts_ns": int(ts_ns),
        "listing_commitment_hex": listing_norm,
        "tier_multiplier_milli": int(tier_multiplier_milli),
        "ipfs_cid": str(ipfs_cid),
        "consent_hash_hex": consent_norm,
        "suspended": bool(suspended),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.MARKET),
        proof_weight=int(ProofWeightClass.MARKETPLACE_DERIVED),
        commitment_hex=zkba_hex,
        preimage_json=preimage_json,
        ts_ns=int(ts_ns),
        manifest_uri=manifest.output_path.replace("\\", "/"),
        compiler_output_hash_hex=manifest.output_hash_hex,
    )

    return manifest


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a Marketplace Listing Card ZKBA artifact (Phase O3-ZKBA-TRACK1 Track 2 fourth-artifact)."
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--listing-commitment",
        required=True,
        help="32-byte listing commitment as hex string (with or without 0x prefix).",
    )
    parser.add_argument(
        "--tier-multiplier-milli",
        type=int,
        required=True,
        help="Tier multiplier × 1000 (uint64; e.g. 2000 for tier 2.0x).",
    )
    parser.add_argument(
        "--ipfs-cid",
        required=True,
        help="Canonical IPFS CID string (v0 or v1).",
    )
    parser.add_argument(
        "--consent-hash",
        required=True,
        help="32-byte CONSENT v1 commitment hash for MARKETPLACE category.",
    )
    parser.add_argument(
        "--suspended",
        type=int,
        choices=(0, 1),
        default=0,
        help="VAPIDataMarketplaceListings suspended state (0 = active, 1 = suspended).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "marketplace_listing_card",
        )),
        help="Output directory (default: frontend/src/artifacts/marketplace_listing_card/).",
    )
    parser.add_argument(
        "--ts-ns",
        type=int,
        required=True,
        help="Caller-supplied uint64 timestamp (no wall-clock; provide explicitly).",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    from vapi_bridge.store import Store  # noqa: E402
    store = Store(args.db)
    manifest = build_marketplace_listing_artifact(
        store=store,
        listing_commitment_hex=args.listing_commitment,
        tier_multiplier_milli=args.tier_multiplier_milli,
        ipfs_cid=args.ipfs_cid,
        consent_hash_hex=args.consent_hash,
        suspended=bool(args.suspended),
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"Marketplace Listing Card compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_class:            MARKET (= {int(ZKBAClass.MARKET)})")
    print(f"  proof_weight:          MARKETPLACE_DERIVED")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
