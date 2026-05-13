"""Phase O4-VPM-INTEGRATION Stream A.2.b — MARKET-LISTING-v1 VPM compiler.

Second consumer-facing VPM per Phase O4 plan section 3 Stream A.2. The
buyer-and-Curator-facing front-of-house surface for VAPIDataMarketplaceListings
entries. Renders the listing as a deterministic VPM with **procedural
geometric art derived from the SHA-256 hash bytes** of the underlying
listing commitment — a visual cryptographic fingerprint that makes every
distinct listing identifiable at a glance without revealing the underlying
biometric content.

Registered VPM ID per VBDIP-0002A section 10 registry: `MARKET-LISTING-v1`
Lifecycle status after this commit (per plan section 2.3 table): `Compiler Target`
Owning agent lane: Curator (writes to `zk_listings/` via existing v2 bundle
permit `tool:zk-marketplace-listing`)

CFSS lane discipline (asserted by T-VPM-ML-CFSS-1):
  Curator        PERMIT on tool:zk-marketplace-listing at draft://zk_listings/*
  Sentry         FORBID on tool:zk-marketplace-listing at any resource
  Guardian       FORBID on tool:zk-marketplace-listing at any resource

Sentry CANNOT compile a MARKET-LISTING-v1 VPM at the Cedar policy level.
This is the architectural enforcement that "marketplace artifacts belong
to the Curator lane" — codified in the Cedar v2 bundles anchored
2026-05-12 and verified empirically by the CFSS assertion test in this
module.

Procedural Geometric Art — VBDIP-0002 ZKBA Market Card Spec compliance:

  The marketplace listing's visual fingerprint is generated DETERMINISTICALLY
  from the bytes of the underlying ZKBA manifest hash (the same
  zkba_manifest_hash_hex that the wrapper schema vapi-vpm-manifest-v1
  carries). Algorithm (FROZEN at v1):

    1. Parse zkba_manifest_hash_hex into 32 raw bytes.
    2. Split into 8 four-byte chunks. Each chunk drives one geometric tile.
    3. For each chunk (b0, b1, b2, b3):
         x_center      = 32 + (b0 & 0x7F)            // 32..159
         y_center      = 32 + (b1 & 0x7F)            // 32..159
         size_radius   = 12 + (b2 & 0x3F)            // 12..75
         hue_degrees   = (b3 << 1) & 0xFF * 360 / 256 // 0..360
         shape_kind    = (b0 ^ b3) & 0x03            // 0=triangle / 1=square /
                                                     //   2=pentagon / 3=hexagon
         rotation_deg  = ((b1 ^ b2) & 0xFF) * 360 / 256
    4. Each tile is rendered as a regular polygon centered at (x_center,
       y_center) with given size_radius, hue, shape, and rotation.
    5. Tiles are drawn in order (tile 0 first, tile 7 on top); overlapping
       tiles compose visually deterministically.
    6. The art is rendered inside a 192x192 SVG viewBox (offset by margins
       so all tiles fit). No xmlns attribute (HTML5 inline-SVG; preserves
       compiler discipline "no https?://" guard).

  Determinism: two identical zkba_manifest_hash_hex inputs produce
  byte-identical SVG output. The art is a visual hash; collision resistance
  inherits from SHA-256.

  The procedural art appears alongside the standard listing metadata
  (tier multiplier / IPFS CID / consent status / suspended flag). A buyer
  scanning a list of marketplace listings can visually distinguish them
  before reading any text.

Composition profile:
  Inputs (caller-supplied, deterministic):
    listing_commitment_hex    str (64-char hex; Phase 238 LISTING-v1
                              primitive output)
    listing_title             str (operator-supplied display title)
    tier_multiplier_milli     int (tier x 1000; uint64; e.g. 2000 for 2.0x)
    ipfs_cid                  str (canonical IPFS CID)
    consent_hash_hex          str (64-char hex; Phase 237 MARKETPLACE
                              consent commitment)
    suspended                 bool
    listing_owner_address     str (20-byte hex; seller/manufacturer)
    price_iotx_milli          int (uint64; price x 1000 IOTX)
  Wrapped ZKBA primitive reference:
    zkba_manifest_hash_hex    str (64-char hex; drives the procedural art)

ZKBA class: MARKET (= 7). Proof weight: MARKETPLACE_DERIVED.

Author: VAPI Architect (Phase O4 Commit 5)
Date: 2026-05-13
"""
from __future__ import annotations

import argparse
import html
import math
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_BRIDGE_DIR = os.path.normpath(os.path.join(_HERE, "..", "bridge"))
if _BRIDGE_DIR not in sys.path:
    sys.path.insert(0, _BRIDGE_DIR)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from vapi_bridge.zkba_artifact import ZKBAClass, ProofWeightClass  # noqa: E402
from vsd_ui_compiler import (  # noqa: E402
    VPMArtifactManifest,
    compile_vpm_artifact,
)
from vpm_visual_grammar import (  # noqa: E402
    VISUAL_STATES,
    assemble_vpm_head,
    integrity_label_html,
    visual_state_aria_block,
    visual_state_overlay,
    vpm_body_class,
)


_VPM_ID = "MARKET-LISTING-v1"


# ---------------------------------------------------------------------------
# Procedural Geometric Art Renderer — FROZEN at v1
#
# Generates a deterministic SVG visual fingerprint from 32 SHA-256 hash bytes
# per VBDIP-0002 ZKBA Market Card spec. Same hash bytes always produce the
# same SVG; different hashes produce visually different art.
# ---------------------------------------------------------------------------

_ART_TILES = 8           # number of geometric tiles drawn per artwork
_ART_VIEW_W = 192        # SVG viewBox width
_ART_VIEW_H = 192        # SVG viewBox height


def _regular_polygon_points(
    cx: float, cy: float, radius: float, n_sides: int, rotation_deg: float,
) -> str:
    """Compute SVG points string for a regular polygon with n_sides at
    (cx, cy), radius, rotation (degrees). Deterministic; numpy-free."""
    rotation_rad = math.radians(rotation_deg)
    angle_step = 2 * math.pi / n_sides
    pts: list[str] = []
    for i in range(n_sides):
        theta = rotation_rad + i * angle_step
        x = cx + radius * math.cos(theta)
        y = cy + radius * math.sin(theta)
        # 2 decimal places for byte-stability without floating-point format drift
        pts.append(f"{x:.2f},{y:.2f}")
    return " ".join(pts)


_SHAPE_N_SIDES = {0: 3, 1: 4, 2: 5, 3: 6}
_SHAPE_NAMES = {0: "triangle", 1: "square", 2: "pentagon", 3: "hexagon"}


def render_procedural_art_svg(zkba_manifest_hash_hex: str) -> str:
    """Render the procedural geometric art SVG from the ZKBA manifest hash.

    FROZEN algorithm v1 per module docstring. Returns inline SVG snippet
    (no xmlns attribute — HTML5 inline-SVG inheritance; preserves
    compile_vpm_artifact's "no https?://" static guard).

    Each tile carries `data-art-tile-N=` attributes documenting the
    parameters that drove it — used by T-VPM-ML-ART-* tests to verify
    procedural determinism + per-byte sensitivity.
    """
    normalized = zkba_manifest_hash_hex.lower()
    if normalized.startswith("0x"):
        normalized = normalized[2:]
    if len(normalized) != 64:
        raise ValueError(
            f"zkba_manifest_hash_hex must be 64 hex chars; got {len(normalized)}"
        )
    raw = bytes.fromhex(normalized)
    assert len(raw) == 32

    tiles_svg: list[str] = []
    for tile_idx in range(_ART_TILES):
        offset = tile_idx * 4
        b0, b1, b2, b3 = raw[offset], raw[offset + 1], raw[offset + 2], raw[offset + 3]

        # Geometric parameters (all deterministic functions of bytes)
        x_center = 32 + (b0 & 0x7F)         # 32..159 in 192-wide viewBox
        y_center = 32 + (b1 & 0x7F)         # 32..159 in 192-tall viewBox
        size_radius = 12 + (b2 & 0x3F)      # 12..75
        # Hue: scale b3 (0..255) -> 0..360 degrees
        hue_degrees = (b3 * 360) // 256
        shape_kind = (b0 ^ b3) & 0x03
        # Rotation: scale (b1 ^ b2) -> 0..360
        rotation_deg = ((b1 ^ b2) * 360) // 256

        n_sides = _SHAPE_N_SIDES[shape_kind]
        shape_name = _SHAPE_NAMES[shape_kind]
        # HSL hue with FROZEN saturation 70% and lightness 55% for visual
        # variety while keeping contrast against the dark VPM background.
        fill = f"hsl({hue_degrees}, 70%, 55%)"

        pts = _regular_polygon_points(
            x_center, y_center, size_radius, n_sides, rotation_deg,
        )
        tiles_svg.append(
            f'<polygon class="market-art-tile" '
            f'data-art-tile-index="{tile_idx}" '
            f'data-art-tile-shape="{shape_name}" '
            f'data-art-tile-x="{x_center}" '
            f'data-art-tile-y="{y_center}" '
            f'data-art-tile-radius="{size_radius}" '
            f'data-art-tile-hue="{hue_degrees}" '
            f'data-art-tile-rotation="{rotation_deg}" '
            f'points="{pts}" fill="{fill}" '
            'stroke="#020408" stroke-width="1.5" '
            'opacity="0.85"/>'
        )

    return (
        f'<svg class="market-listing-art" width="192" height="192" '
        f'viewBox="0 0 {_ART_VIEW_W} {_ART_VIEW_H}" '
        f'aria-label="Procedural geometric visual fingerprint derived from '
        f'ZKBA manifest hash">\n'
        f'  <rect x="0" y="0" width="{_ART_VIEW_W}" height="{_ART_VIEW_H}" '
        'fill="#0a0e14"/>\n'
        + '\n'.join(f'  {tile}' for tile in tiles_svg) + '\n'
        '</svg>'
    )


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_market_listing_html(inputs: dict) -> str:
    state = inputs["visual_state"]
    head = assemble_vpm_head(
        title=f"VAPI Market Listing — {html.escape(str(inputs['listing_title']))[:40]} — {state.upper()}",
        visual_state=state,
        extra_style=(
            ".market-listing-art { display: block; margin: 1em auto; "
            "border: 1px solid #1a2a40; }\n"
            ".tier-badge { background: #f0a868; color: #020408; "
            "padding: 4px 12px; border-radius: 4px; font-weight: bold; }\n"
            ".price-badge { background: #5bd6a3; color: #020408; "
            "padding: 4px 12px; border-radius: 4px; font-weight: bold; }\n"
            ".suspend-badge { background: #d65b78; color: #020408; "
            "padding: 4px 12px; border-radius: 4px; font-weight: bold; }\n"
        ),
    )

    overlay = visual_state_overlay(state)
    aria_block = visual_state_aria_block(state)
    integrity_block = integrity_label_html(inputs["integrity_label"])
    body_class = vpm_body_class(state)

    listing_commitment = html.escape(str(inputs["listing_commitment_hex"]))
    title = html.escape(str(inputs["listing_title"]))
    tier_milli = int(inputs["tier_multiplier_milli"])
    tier_display = f"{tier_milli / 1000.0:.2f}x"
    ipfs_cid = html.escape(str(inputs["ipfs_cid"]))
    consent_hash = html.escape(str(inputs["consent_hash_hex"]))
    suspended = bool(inputs["suspended"])
    suspended_label = "SUSPENDED" if suspended else "ACTIVE"
    suspended_class = "suspend-badge" if suspended else "price-badge"
    owner = html.escape(str(inputs["listing_owner_address"]))
    price_milli = int(inputs["price_iotx_milli"])
    price_display = f"{price_milli / 1000.0:.3f} IOTX"
    ts_ns = int(inputs["ts_ns"])
    zkba_hash = html.escape(inputs["zkba_manifest_hash_hex"])

    art_svg = render_procedural_art_svg(zkba_manifest_hash_hex=inputs["zkba_manifest_hash_hex"])

    body = (
        '<body>\n'
        f'  <div class="{body_class}" data-listing-id="{listing_commitment}">\n'
        f'  {overlay}\n'
        f'  <h1>{title}</h1>\n'
        f'  {aria_block}\n'
        '  <h2>Visual Fingerprint</h2>\n'
        f'  {art_svg}\n'
        '  <p class="market-art-explain">Procedural geometric art rendered '
        'deterministically from the SHA-256 hash of the underlying ZKBA '
        'manifest. Two listings with identical underlying hashes show '
        'identical art; any change to the hash produces visually distinct art.</p>\n'
        '  <h2>Listing Details</h2>\n'
        '  <table class="vpm-status">\n'
        f'    <tr><td>Listing commitment:</td><td><code data-listing-field="commitment">{listing_commitment}</code></td></tr>\n'
        f'    <tr><td>Tier multiplier:</td><td><span class="tier-badge" data-listing-field="tier">{tier_display}</span></td></tr>\n'
        f'    <tr><td>Price:</td><td><span class="{suspended_class}" data-listing-field="price">{price_display}</span></td></tr>\n'
        f'    <tr><td>Status:</td><td><span class="{suspended_class}" data-listing-field="status">{suspended_label}</span></td></tr>\n'
        f'    <tr><td>Owner address:</td><td><code data-listing-field="owner">{owner}</code></td></tr>\n'
        '  </table>\n'
        '  <h2>Buyer Verification Material</h2>\n'
        '  <table class="vpm-status">\n'
        f'    <tr><td>IPFS CID:</td><td><code data-listing-field="ipfs_cid">{ipfs_cid}</code></td></tr>\n'
        f'    <tr><td>Consent commitment:</td><td><code data-listing-field="consent">{consent_hash}</code></td></tr>\n'
        f'    <tr><td>ZKBA manifest hash:</td><td><code data-listing-field="zkba_manifest">{zkba_hash}</code></td></tr>\n'
        '  </table>\n'
        f'  {integrity_block}\n'
        '  <div class="vpm-footer">\n'
        f'    VPM ID: <code>{_VPM_ID}</code>. Lifecycle: Compiler Target. '
        'Curator-lane buyer-facing surface. Sentry + Guardian FORBIDDEN at '
        'Cedar policy level. Self-contained projection. compile-time ts_ns: '
        f'<code>{ts_ns}</code>.\n'
        '  </div>\n'
        '  </div>\n'
        '</body>\n'
    )

    return (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        f'{head}\n'
        f'{body}'
        '</html>\n'
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_market_listing_artifact(
    *,
    listing_commitment_hex: str,
    listing_title: str,
    tier_multiplier_milli: int,
    ipfs_cid: str,
    consent_hash_hex: str,
    suspended: bool,
    listing_owner_address: str,
    price_iotx_milli: int,
    integrity_label: dict,
    zkba_manifest_hash_hex: str,
    visual_state: str,
    capture_mode: str,
    output_dir: Path,
    ts_ns: int,
) -> VPMArtifactManifest:
    """Build a MARKET-LISTING-v1 VPM artifact deterministically with
    procedural geometric art derived from the ZKBA manifest hash.

    ZKBA class: MARKET (= 7). Proof weight: MARKETPLACE_DERIVED.

    Validates:
      - visual_state against VISUAL_STATES
      - listing_commitment_hex + consent_hash_hex as 64-char hex
      - tier_multiplier_milli >= 0 and <= uint64 max
      - price_iotx_milli >= 0 and <= uint64 max
      - listing_title + ipfs_cid + listing_owner_address are non-empty strings
    """
    if visual_state not in VISUAL_STATES:
        raise ValueError(
            f"visual_state must be one of {VISUAL_STATES}; got {visual_state!r}"
        )
    if not isinstance(listing_title, str) or not listing_title:
        raise ValueError(f"listing_title must be non-empty str; got {listing_title!r}")
    if not isinstance(ipfs_cid, str) or not ipfs_cid:
        raise ValueError(f"ipfs_cid must be non-empty str; got {ipfs_cid!r}")
    if not isinstance(listing_owner_address, str) or not listing_owner_address:
        raise ValueError(
            f"listing_owner_address must be non-empty str; got {listing_owner_address!r}"
        )
    if not isinstance(tier_multiplier_milli, int) or tier_multiplier_milli < 0 or tier_multiplier_milli > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(
            f"tier_multiplier_milli must be uint64; got {tier_multiplier_milli!r}"
        )
    if not isinstance(price_iotx_milli, int) or price_iotx_milli < 0 or price_iotx_milli > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(
            f"price_iotx_milli must be uint64; got {price_iotx_milli!r}"
        )
    for field_name, hex_val in [
        ("listing_commitment_hex", listing_commitment_hex),
        ("consent_hash_hex", consent_hash_hex),
    ]:
        normalized = hex_val.lower()
        if normalized.startswith("0x"):
            normalized = normalized[2:]
        if len(normalized) != 64:
            raise ValueError(
                f"{field_name} must be 64 hex chars (32 bytes); "
                f"got {len(normalized)} chars"
            )
        try:
            int(normalized, 16)
        except ValueError:
            raise ValueError(f"{field_name} not valid hex: {hex_val!r}")

    inputs = {
        "listing_commitment_hex":  str(listing_commitment_hex),
        "listing_title":           str(listing_title),
        "tier_multiplier_milli":   int(tier_multiplier_milli),
        "ipfs_cid":                str(ipfs_cid),
        "consent_hash_hex":        str(consent_hash_hex),
        "suspended":               bool(suspended),
        "listing_owner_address":   str(listing_owner_address),
        "price_iotx_milli":        int(price_iotx_milli),
        "visual_state":            str(visual_state),
        "integrity_label":         dict(integrity_label),
        "zkba_manifest_hash_hex":  str(zkba_manifest_hash_hex),
        "ts_ns":                   int(ts_ns),
    }

    return compile_vpm_artifact(
        vpm_id=_VPM_ID,
        zkba_class=ZKBAClass.MARKET,
        proof_weight=ProofWeightClass.MARKETPLACE_DERIVED,
        visual_state=visual_state,
        capture_mode=capture_mode,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=zkba_manifest_hash_hex,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_market_listing_html,
    )


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a MARKET-LISTING-v1 VPM artifact "
                    "(Phase O4-VPM-INTEGRATION Stream A.2.b). Generates "
                    "procedural geometric art deterministically from the "
                    "underlying ZKBA manifest hash."
    )
    parser.add_argument("--listing-commitment-hex", required=True)
    parser.add_argument("--listing-title", required=True)
    parser.add_argument("--tier-multiplier-milli", type=int, default=2000)
    parser.add_argument("--ipfs-cid", required=True)
    parser.add_argument("--consent-hash-hex", required=True)
    parser.add_argument("--suspended", action="store_true")
    parser.add_argument("--listing-owner-address", required=True)
    parser.add_argument("--price-iotx-milli", type=int, default=1000)
    parser.add_argument("--zkba-manifest-hash-hex", required=True)
    parser.add_argument("--visual-state", default="live", choices=list(VISUAL_STATES))
    parser.add_argument("--capture-mode", default="live")
    parser.add_argument("--ts-ns", type=int, required=True)
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "market_listing",
        )),
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    integrity_label = {
        "proof_type":             "VPM-MARKET-LISTING",
        "capture_mode":           args.capture_mode,
        "raw_biometrics_exposed": False,
        "consent_active":         True,
        "zk_verified":            False,
        "on_chain_anchor":        True,
        "proof_weight":           "MARKETPLACE_DERIVED",
        "revocation_status":      "active" if not args.suspended else "revoked",
        "limitations":            [
            "Buyer-facing listing surface; visual art is a hash fingerprint "
            "not a humanity proof",
        ],
    }

    manifest = build_market_listing_artifact(
        listing_commitment_hex=args.listing_commitment_hex,
        listing_title=args.listing_title,
        tier_multiplier_milli=args.tier_multiplier_milli,
        ipfs_cid=args.ipfs_cid,
        consent_hash_hex=args.consent_hash_hex,
        suspended=args.suspended,
        listing_owner_address=args.listing_owner_address,
        price_iotx_milli=args.price_iotx_milli,
        integrity_label=integrity_label,
        zkba_manifest_hash_hex=args.zkba_manifest_hash_hex,
        visual_state=args.visual_state,
        capture_mode=args.capture_mode,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"MARKET-LISTING-v1 compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  visual_state:          {manifest.visual_state}")
    print(f"  procedural_art_seed:   {args.zkba_manifest_hash_hex[:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
