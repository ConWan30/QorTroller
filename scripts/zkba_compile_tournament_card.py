"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Tournament Eligibility Card artifact builder.

Fifth ZKBA artifact target after:
  - GIC Continuity Ledger Alpha  (commit 3b3081d3; class 2, CHAIN_ONLY; 1 primitive)
  - VHP Verification Card        (commit 4f399282; class 3, CHAIN_ONLY; 1 primitive)
  - AIT Separation Snapshot      (commit bdbcf67f; class 1, CALIBRATION_PLUS_CONTEXT; 1 primitive)
  - Marketplace Listing Card     (commit 269e439c; class 7, MARKETPLACE_DERIVED; 2 primitives)

Strategic value of this artifact (deepest composition test to date):

1. **First artifact composing 3+ primitives in one preimage.**
   The Marketplace Listing Card (commit 269e439c) shipped the first
   cross-primitive composition with 2 primitive references (LISTING-v1
   + CONSENT v1). Tournament Eligibility Cards reference THREE FROZEN
   primitive surfaces simultaneously:
     - VHP v1   (Verified Human Proof; ERC-4671 soulbound token state)
     - GIC v1   (Grind Integrity Chain; cognitive-session continuity)
     - VAPIProtocolLens.isFullyEligible() (the singular on-chain
       composability gate the entire protocol design hinges on, which
       itself transitively composes PoAC + L4 + L2B + L2C + L5 over the
       9-level PITL stack)
   This empirically proves Layer 7 composes primitives at depth,
   not just pairwise. The same architectural pattern will scale to
   future HARDWARE + CONSENT cards.

2. **First artifact transitively anchored to the full PITL stack.**
   Every prior ZKBA artifact referenced state from one or two primitive
   outputs in isolation. Tournament Eligibility Cards anchor to
   `is_fully_eligible` — a single bit summarizing the verdict of the
   entire VAPI anti-cheat protocol at a moment in time. The ZKBA
   pipeline now produces artifacts whose meaning is co-extensive with
   the protocol's central claim: "this controller, at this time, under
   this human, is tournament-eligible."

3. **Operator-facing artifact at the natural tournament-gate surface.**
   This artifact's audience is tournament organizers and adjudicators.
   When a tournament needs to verify a player's eligibility off-chain
   (e.g. for dispute resolution months after the match), this is the
   exact projection they consult. The cryptographic commitment is
   reproducible from on-chain state alone, making it a non-repudiable
   off-chain record bound to on-chain truth.

Composition profile:
  - ZKBAClass.TOURNAMENT                   (= 6 in the FROZEN-v1 enum)
  - ProofWeightClass.CHAIN_ONLY            (matches the default per
                                            DEFAULT_PROOF_WEIGHT_BY_CLASS;
                                            all referenced state is
                                            on-chain anchored)
  - Single 32-byte component hash composed from:
        SHA-256(
            vhp_token_id_be(32)        # uint256 BE; VHP soulbound token ID
            || vhp_is_valid_byte(1)    # chain.is_vhp_valid(token_id) result
            || gic_chain_head(32)      # raw 32B; GIC chain head per Phase 235-A
            || gic_chain_length_be(8)  # uint64 BE; e.g. 100 for GIC_100
            || is_fully_eligible_byte(1) # VAPIProtocolLens.isFullyEligible
            || device_id_hash(32)      # raw 32B; canonical hardware binding
            || tournament_id_be(8)     # uint64 BE; tournament identifier
        )                              # = 114 bytes preimage → 32B after SHA-256

Owning agent: **Sentry** (canonical name "anchor_sentry"). Tournament
Eligibility Cards write to the `zk_artifacts/` lane (same as VHP +
GIC + AIT — operator/sentry-facing surface, not Curator).

Track 1 invariants enforced:
  - No on-chain submission (anchor_tx_hash stays NULL in zkba_artifact_log)
  - Caller-supplied state inputs (no live chain reads from this script;
    operator workflow fetches VHP + GIC + isFullyEligible state first
    and passes the snapshot in)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs → same output bytes)

Real input fixture (per CLAUDE.md anchored state, 2026-05-09):
  vhp_token_id        = 2                                 (Session 3 mint commit 76c92e9b)
  vhp_is_valid        = True                              (verified at mint)
  gic_chain_head      = 0x0e9d453d904220...1ab48da        (Phase 239 G3 permanent anchor 2026-05-06)
  gic_chain_length    = 100                               (GIC_100 milestone)
  is_fully_eligible   = True                              (bridge wallet currently eligible)
  device_id_hash      = 0x10e0169446ba3320...             (Sony DualShock Edge CFI-ZCP1)
  tournament_id       = caller-supplied (synthetic; e.g. 20260601001 for first official tournament)

Run via CLI (offline; uses provided inputs):
    python scripts/zkba_compile_tournament_card.py \\
        --vhp-token-id 2 --vhp-is-valid \\
        --gic-chain-head 0x0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da \\
        --gic-chain-length 100 --is-fully-eligible \\
        --device-id-hash 10e0169446ba3320...0 \\
        --tournament-id 20260601001 \\
        --ts-ns 1778900000000000000

Author: VAPI Architect (post-MARKET fifth-artifact ship 2026-05-12)
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
from vsd_ui_compiler import ZKBAManifest, compile_artifact  # noqa: E402


# ---------------------------------------------------------------------------
# Deterministic component composition
# ---------------------------------------------------------------------------

def _parse_hex32(s: str, field_name: str) -> bytes:
    """Parse a 32-byte hex value (with or without 0x prefix)."""
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


def _compose_tournament_component(
    *,
    vhp_token_id: int,
    vhp_is_valid: bool,
    gic_chain_head: bytes,
    gic_chain_length: int,
    is_fully_eligible: bool,
    device_id_hash: bytes,
    tournament_id: int,
) -> bytes:
    """Compose a single 32-byte ZKBA component from tournament eligibility state.

    Byte layout (FROZEN at v1; downstream verifiers reproduce this exact order):

        SHA-256(
            vhp_token_id_be(32)         # 32 bytes (uint256 BE)
            || vhp_is_valid_byte(1)     # 1 byte: 0x01 if valid else 0x00
            || gic_chain_head(32)       # 32 bytes (raw — Phase 235-A GIC head)
            || gic_chain_length_be(8)   # 8 bytes (uint64 BE — e.g. 100 for GIC_100)
            || is_fully_eligible_byte(1) # 1 byte: 0x01 if eligible else 0x00
            || device_id_hash(32)       # 32 bytes (raw — canonical hardware)
            || tournament_id_be(8)      # 8 bytes (uint64 BE — tournament identifier)
        )                               # = 114 bytes preimage → 32 bytes after SHA-256

    The composition is intentionally flat (no sub-hash trees) so the
    preimage layout is auditable by a verifier with only the seven
    component values and a SHA-256 implementation. The cost is a
    larger preimage (114 vs ~96 for tree-based composition), but the
    payoff is reproducibility from on-chain state alone with zero
    extra-protocol machinery.
    """
    if not isinstance(vhp_token_id, int) or vhp_token_id < 0 or vhp_token_id > (2**256 - 1):
        raise ValueError(f"vhp_token_id must be uint256; got {vhp_token_id!r}")
    if not isinstance(gic_chain_head, (bytes, bytearray)) or len(gic_chain_head) != 32:
        raise ValueError(
            f"gic_chain_head must be 32 raw bytes; got {len(gic_chain_head)} bytes"
        )
    if not isinstance(gic_chain_length, int) or gic_chain_length < 0 or gic_chain_length > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"gic_chain_length must be uint64; got {gic_chain_length!r}")
    if not isinstance(device_id_hash, (bytes, bytearray)) or len(device_id_hash) != 32:
        raise ValueError(
            f"device_id_hash must be 32 raw bytes; got {len(device_id_hash)} bytes"
        )
    if not isinstance(tournament_id, int) or tournament_id < 0 or tournament_id > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"tournament_id must be uint64; got {tournament_id!r}")

    preimage = (
        vhp_token_id.to_bytes(32, "big")
        + (b"\x01" if vhp_is_valid else b"\x00")
        + bytes(gic_chain_head)
        + gic_chain_length.to_bytes(8, "big")
        + (b"\x01" if is_fully_eligible else b"\x00")
        + bytes(device_id_hash)
        + tournament_id.to_bytes(8, "big")
    )
    assert len(preimage) == 32 + 1 + 32 + 8 + 1 + 32 + 8 == 114
    return hashlib.sha256(preimage).digest()


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_tournament_card_html(inputs: dict) -> str:
    """Deterministic HTML rendering of a Tournament Eligibility Card.

    Inputs dict shape (all keys required; all values deterministic):
      - "vhp_token_id":        int (uint256)
      - "vhp_is_valid":        bool
      - "gic_chain_head_hex":  str (64 lowercase hex)
      - "gic_chain_length":    int (uint64)
      - "is_fully_eligible":   bool
      - "device_id_hash_hex":  str (64 lowercase hex)
      - "tournament_id":       int (uint64)
      - "zkba_commitment_hex": str (64 lowercase hex)
      - "ts_ns":               int (uint64; caller-supplied)
    """
    vhp_token_id = int(inputs["vhp_token_id"])
    vhp_is_valid = bool(inputs["vhp_is_valid"])
    gic_head = inputs["gic_chain_head_hex"]
    gic_length = int(inputs["gic_chain_length"])
    is_eligible = bool(inputs["is_fully_eligible"])
    did = inputs["device_id_hash_hex"]
    tournament_id = int(inputs["tournament_id"])
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])

    eligible_label = "ELIGIBLE" if is_eligible else "INELIGIBLE"
    eligible_color = "#5bd6a3" if is_eligible else "#d65b78"
    vhp_label = "VALID" if vhp_is_valid else "EXPIRED / REVOKED"
    vhp_color = "#5bd6a3" if vhp_is_valid else "#d65b78"

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>Tournament Eligibility Card - tournament {tournament_id}</title>\n"
        "  <style>\n"
        "    body { font-family: 'Courier New', monospace; "
        "background: #020408; color: #cfe8ff; margin: 0; padding: 1.5em; }\n"
        "    h1 { color: #5a8fb8; border-bottom: 1px solid #1a2a40; "
        "padding-bottom: 0.3em; }\n"
        "    h2 { color: #93a5b8; font-size: 1em; margin-top: 1em; "
        "border-bottom: 1px dashed #1a2a40; padding-bottom: 0.2em; }\n"
        "    .meta { color: #93a5b8; font-size: 0.9em; line-height: 1.6; }\n"
        "    code { color: #d4f0ff; background: #0a0e14; padding: 1px 4px; "
        "border-radius: 2px; word-break: break-all; }\n"
        "    .footer { margin-top: 2em; color: #607a93; font-size: 0.8em; "
        "border-top: 1px solid #1a2a40; padding-top: 0.5em; }\n"
        "    .weight { background: #1a2a40; color: #93a5b8; padding: 2px 8px; "
        "border-radius: 4px; }\n"
        f"    .eligible-badge {{ background: {eligible_color}; color: #020408; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; "
        "font-size: 1.1em; }}\n"
        f"    .vhp-badge {{ background: {vhp_color}; color: #020408; "
        "padding: 2px 8px; border-radius: 4px; font-weight: bold; }}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>Tournament Eligibility Card</h1>\n"
        "  <div class=\"meta\">\n"
        f"    <div style=\"font-size:1.1em; margin: 0.5em 0;\">"
        f"Overall: <span class=\"eligible-badge\">{eligible_label}</span></div>\n"
        f"    <h2>VHP (Verified Human Proof)</h2>\n"
        f"    <div>Token ID: <code>{vhp_token_id}</code></div>\n"
        f"    <div>Validity: <span class=\"vhp-badge\">{vhp_label}</span></div>\n"
        f"    <h2>GIC (Grind Integrity Chain)</h2>\n"
        f"    <div>Chain head: <code>0x{gic_head}</code></div>\n"
        f"    <div>Chain length: <code>{gic_length}</code></div>\n"
        f"    <h2>Hardware Binding</h2>\n"
        f"    <div>Device ID hash: <code>0x{did}</code></div>\n"
        f"    <h2>Tournament Context</h2>\n"
        f"    <div>Tournament ID: <code>{tournament_id}</code></div>\n"
        f"    <h2>ZKBA Commitment</h2>\n"
        f"    <div>Commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">CHAIN_ONLY</span> "
        "(VHP + GIC + isFullyEligible all on-chain anchored)</div>\n"
        "  </div>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "ZKBA class TOURNAMENT (= 6 in PATTERN-017 FROZEN-v1 enum). "
        "Phase O3-ZKBA-TRACK1 Track 2 fifth-artifact ship — Sentry "
        "lane authority via Cedar v2 zk_artifacts/. "
        "Cross-primitive composition: VHP v1 + GIC v1 + "
        "VAPIProtocolLens.isFullyEligible() — transitively anchored "
        "to the full 9-level PITL stack. "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_tournament_card_artifact(
    *,
    store,
    vhp_token_id: int,
    vhp_is_valid: bool,
    gic_chain_head_hex: str,
    gic_chain_length: int,
    is_fully_eligible: bool,
    device_id_hash_hex: str,
    tournament_id: int,
    output_dir: Path,
    ts_ns: int,
) -> ZKBAManifest:
    """Build a Tournament Eligibility Card ZKBA artifact deterministically.

    Composes the ZKBA commitment from VHP token state, GIC chain state,
    VAPIProtocolLens.isFullyEligible() verdict, and hardware/tournament
    context. Calls compile_artifact() to emit HTML + manifest and inserts
    a row into zkba_artifact_log.

    Args:
        store:               bridge.vapi_bridge.store.Store instance.
        vhp_token_id:        VHP soulbound token ID (uint256).
        vhp_is_valid:        chain.is_vhp_valid(token_id) result.
        gic_chain_head_hex:  32-byte GIC chain head as hex string (with or
                             without 0x prefix).
        gic_chain_length:    GIC chain depth (uint64; e.g. 100 for GIC_100).
        is_fully_eligible:   VAPIProtocolLens.isFullyEligible() result.
        device_id_hash_hex:  32-byte canonical device ID hash as hex.
        tournament_id:       Tournament identifier (uint64; caller-supplied).
        output_dir:          Directory under which to write artifact + manifest.
        ts_ns:               Caller-supplied uint64 timestamp.

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    gic_chain_head = _parse_hex32(gic_chain_head_hex, "gic_chain_head")
    device_id_hash = _parse_hex32(device_id_hash_hex, "device_id_hash")

    # Normalize hex inputs (drop 0x prefix, lowercase) for rendering
    gic_norm = gic_chain_head_hex.lower()
    if gic_norm.startswith("0x"):
        gic_norm = gic_norm[2:]
    did_norm = device_id_hash_hex.lower()
    if did_norm.startswith("0x"):
        did_norm = did_norm[2:]

    # Compose component hash
    component = _compose_tournament_component(
        vhp_token_id=vhp_token_id,
        vhp_is_valid=vhp_is_valid,
        gic_chain_head=gic_chain_head,
        gic_chain_length=gic_chain_length,
        is_fully_eligible=is_fully_eligible,
        device_id_hash=device_id_hash,
        tournament_id=tournament_id,
    )

    # Compute the ZKBA commitment
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.TOURNAMENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    inputs = {
        "vhp_token_id":         int(vhp_token_id),
        "vhp_is_valid":         bool(vhp_is_valid),
        "gic_chain_head_hex":   gic_norm,
        "gic_chain_length":     int(gic_chain_length),
        "is_fully_eligible":    bool(is_fully_eligible),
        "device_id_hash_hex":   did_norm,
        "tournament_id":        int(tournament_id),
        "zkba_commitment_hex":  zkba_hex,
        "ts_ns":                int(ts_ns),
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.TOURNAMENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_tournament_card_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.TOURNAMENT),
        "proof_weight": int(ProofWeightClass.CHAIN_ONLY),
        "component_hashes_hex": [component.hex()],
        "ts_ns": int(ts_ns),
        "vhp_token_id": int(vhp_token_id),
        "vhp_is_valid": bool(vhp_is_valid),
        "gic_chain_head_hex": gic_norm,
        "gic_chain_length": int(gic_chain_length),
        "is_fully_eligible": bool(is_fully_eligible),
        "device_id_hash_hex": did_norm,
        "tournament_id": int(tournament_id),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.TOURNAMENT),
        proof_weight=int(ProofWeightClass.CHAIN_ONLY),
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
        description="Build a Tournament Eligibility Card ZKBA artifact (Phase O3-ZKBA-TRACK1 Track 2 fifth-artifact)."
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--vhp-token-id",
        type=int,
        required=True,
        help="VHP soulbound token ID (uint256).",
    )
    parser.add_argument(
        "--vhp-is-valid",
        action="store_true",
        help="VHP is currently valid (chain.is_vhp_valid result).",
    )
    parser.add_argument(
        "--gic-chain-head",
        required=True,
        help="32-byte GIC chain head as hex string (with or without 0x prefix).",
    )
    parser.add_argument(
        "--gic-chain-length",
        type=int,
        required=True,
        help="GIC chain depth (uint64; e.g. 100 for GIC_100).",
    )
    parser.add_argument(
        "--is-fully-eligible",
        action="store_true",
        help="VAPIProtocolLens.isFullyEligible() returned True.",
    )
    parser.add_argument(
        "--device-id-hash",
        required=True,
        help="32-byte canonical device ID hash as hex string.",
    )
    parser.add_argument(
        "--tournament-id",
        type=int,
        required=True,
        help="Tournament identifier (uint64; caller-supplied).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "tournament_eligibility_card",
        )),
        help="Output directory (default: frontend/src/artifacts/tournament_eligibility_card/).",
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
    manifest = build_tournament_card_artifact(
        store=store,
        vhp_token_id=args.vhp_token_id,
        vhp_is_valid=args.vhp_is_valid,
        gic_chain_head_hex=args.gic_chain_head,
        gic_chain_length=args.gic_chain_length,
        is_fully_eligible=args.is_fully_eligible,
        device_id_hash_hex=args.device_id_hash,
        tournament_id=args.tournament_id,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"Tournament Eligibility Card compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_class:            TOURNAMENT (= {int(ZKBAClass.TOURNAMENT)})")
    print(f"  proof_weight:          CHAIN_ONLY")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
