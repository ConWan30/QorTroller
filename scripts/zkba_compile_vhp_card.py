"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — VHP Verification Card artifact builder.

Second ZKBA artifact target per Operator authorization "proceed with 1" (ship
2nd ZKBA artifact target — proves Layer 7 works under real load against the
newly-anchored Cedar v2 lane authority).

VHP Verification Card composes the existing on-chain VHP (Verified Human Proof)
soulbound token state into a ZKBA commitment + VPM-wrapped projection.

Composition profile:
  - ZKBAClass.VHP                 (= 3 in the FROZEN-v1 enum at zkba_artifact.py)
  - ProofWeightClass.CHAIN_ONLY   (matches GIC Continuity Ledger precedent;
                                   no fresh biometric capture — VHP token state
                                   is on-chain anchored at mint time)
  - Single 32-byte component hash composed from:
        SHA-256( token_id_be(32) || device_id_hash(32) ||
                 expires_at_be(32) || cert_level_be(1) || is_valid_byte(1) )

Owning agent: **Sentry** (canonical name "anchor_sentry"). VHP cards write
to the `zk_artifacts/` lane authorized by anchor_sentry_o2_suggest_v2.json
(Cedar v2 LIVE since commit ad0f7d11 dual-anchored on AgentScope +
AgentRegistry 2026-05-12).

Track 1 invariants enforced:
  - No on-chain submission (anchor_tx_hash stays NULL in zkba_artifact_log)
  - No fresh biometric capture (CHAIN_ONLY proof weight)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs → same output bytes)

Real input fixture (canonical VHP for VAPI bridge wallet per Session 3
2026-05-09 mint at commit 76c92e9b):
  token_id          = 2
  device_id_hash    = 0x10e0169446ba3320... (canonical Sony DualShock Edge
                                              CFI-ZCP1 SHA-256 hash)
  expires_at        = mint_ts + 90 days TTL
  cert_level        = 1
  is_valid          = True (verified by chain.is_vhp_valid(2))

Run via CLI (offline; uses provided inputs):
    python scripts/zkba_compile_vhp_card.py --token-id 2 \\
        --device-id-hash 0x10e0169446ba3320... \\
        --expires-at 1786080000 \\
        --cert-level 1 \\
        --is-valid \\
        --ts-ns 1778900000000000000

Or via Python:
    from scripts.zkba_compile_vhp_card import build_vhp_card_artifact
    from bridge.vapi_bridge.store import Store
    store = Store(db_path)
    manifest = build_vhp_card_artifact(
        store=store,
        token_id=2,
        device_id_hash_hex="0x10e0169446ba3320...",
        expires_at=1786080000,
        cert_level=1,
        is_valid=True,
        output_dir=Path("frontend/src/artifacts/vhp_verification_card"),
        ts_ns=1778900000000000000,
    )

Pairs with G4 manifest validator + VPM wrapper at scripts/vsd_vpm_wrapper.py
for the end-to-end Layer 7 pipeline.

Author: VAPI Architect (post-Track-2 second-artifact ship 2026-05-12)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
from pathlib import Path
from typing import Optional

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
from vsd_ui_compiler import (  # noqa: E402
    ZKBAManifest,
    brand_card_css_v2,
    compile_artifact,
)


# ---------------------------------------------------------------------------
# Deterministic component composition
# ---------------------------------------------------------------------------

def _compose_vhp_component(
    *,
    token_id: int,
    device_id_hash: bytes,
    expires_at: int,
    cert_level: int,
    is_valid: bool,
) -> bytes:
    """Compose a single 32-byte ZKBA component from VHP token state.

    Byte layout (FROZEN at v1; downstream verifiers reproduce this exact order):

        SHA-256(
            token_id_be(32)        # 32 bytes (uint256 BE)
            || device_id_hash(32)  # 32 bytes (raw)
            || expires_at_be(32)   # 32 bytes (uint256 BE)
            || cert_level_be(1)    # 1 byte (uint8)
            || is_valid_byte(1)    # 1 byte: 0x01 if valid, 0x00 otherwise
        )                          # = 32 bytes after SHA-256
    """
    if not isinstance(token_id, int) or token_id < 0 or token_id > (2**256 - 1):
        raise ValueError(f"token_id must be uint256; got {token_id!r}")
    if not isinstance(device_id_hash, (bytes, bytearray)) or len(device_id_hash) != 32:
        raise ValueError(f"device_id_hash must be 32 raw bytes; got {len(device_id_hash)} bytes")
    if not isinstance(expires_at, int) or expires_at < 0 or expires_at > (2**256 - 1):
        raise ValueError(f"expires_at must be uint256; got {expires_at!r}")
    if not isinstance(cert_level, int) or cert_level < 0 or cert_level > 255:
        raise ValueError(f"cert_level must be uint8; got {cert_level!r}")

    token_id_be = token_id.to_bytes(32, "big")
    expires_be = expires_at.to_bytes(32, "big")
    cert_byte = struct.pack(">B", cert_level)
    is_valid_byte = b"\x01" if is_valid else b"\x00"

    preimage = token_id_be + bytes(device_id_hash) + expires_be + cert_byte + is_valid_byte
    return hashlib.sha256(preimage).digest()


def _parse_device_id_hash(s: str) -> bytes:
    """Parse a 32-byte device_id_hash from hex (with or without 0x prefix)."""
    if not isinstance(s, str):
        raise ValueError(f"device_id_hash must be hex string; got {type(s).__name__}")
    s2 = s.lower()
    if s2.startswith("0x"):
        s2 = s2[2:]
    if len(s2) != 64:
        raise ValueError(f"device_id_hash must be 64 hex chars (32 bytes); got {len(s2)} chars")
    try:
        return bytes.fromhex(s2)
    except ValueError as exc:
        raise ValueError(f"device_id_hash not valid hex: {exc}") from exc


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_vhp_card_html(inputs: dict) -> str:
    """Deterministic HTML rendering of a VHP Verification Card.

    Inputs dict shape (all keys required; all values deterministic):
      - "token_id":            int (uint256)
      - "device_id_hash_hex":  str (64 lowercase hex)
      - "expires_at":          int (unix timestamp; 90-day TTL from mint)
      - "cert_level":          int (uint8; 1 = canonical hardware tier)
      - "is_valid":            bool (chain.is_vhp_valid(token_id) result)
      - "zkba_commitment_hex": str (64 lowercase hex)
      - "ts_ns":               int (uint64; caller-supplied, no wall-clock)
    """
    token_id = int(inputs["token_id"])
    did = inputs["device_id_hash_hex"]
    expires = int(inputs["expires_at"])
    cert = int(inputs["cert_level"])
    valid = bool(inputs["is_valid"])
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])

    valid_label = "VALID" if valid else "EXPIRED / REVOKED"
    valid_color = "#5bd6a3" if valid else "#d65b78"

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>VHP Verification Card - token {token_id}</title>\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "  <meta name=\"vpm-template-version\" content=\"2\">\n"
        "  <style>\n"
        f"{brand_card_css_v2()}"
        "    .weight { background: #1b2433; color: #8a98ab; padding: 2px 8px; "
        "border-radius: 4px; }\n"
        f"    .valid-badge {{ background: {valid_color}; color: #04060a; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; }}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>VHP Verification Card</h1>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Token ID: <code>{token_id}</code></div>\n"
        f"    <div>Device ID hash: <code>0x{did}</code></div>\n"
        f"    <div>Expires at: <code>{expires}</code> (unix ts)</div>\n"
        f"    <div>Cert level: <code>{cert}</code></div>\n"
        f"    <div>Status: <span class=\"valid-badge\">{valid_label}</span></div>\n"
        f"    <div>ZKBA commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">CHAIN_ONLY</span> "
        "(VHP token state on-chain anchored; no fresh biometric capture)</div>\n"
        "  </div>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "ZKBA class VHP (= 3 in PATTERN-017 FROZEN-v1 enum). "
        "Phase O3-ZKBA-TRACK1 Track 2 second-artifact ship — Sentry "
        "lane authority via Cedar v2 zk_artifacts/. "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_vhp_card_artifact(
    *,
    store,
    token_id: int,
    device_id_hash_hex: str,
    expires_at: int,
    cert_level: int,
    is_valid: bool,
    output_dir: Path,
    ts_ns: int,
) -> ZKBAManifest:
    """Build a VHP Verification Card ZKBA artifact deterministically.

    Composes the ZKBA commitment from VHP token state, calls compile_artifact()
    to emit HTML + manifest, and inserts a row into zkba_artifact_log.

    Args:
        store:              bridge.vapi_bridge.store.Store instance.
        token_id:           VHP soulbound token ID (uint256; e.g. 2 for the
                            bridge wallet's canonical mint).
        device_id_hash_hex: 32-byte device ID hash as hex string (with or
                            without 0x prefix).
        expires_at:         Unix timestamp for VHP TTL expiration.
        cert_level:         uint8 hardware certification tier (1 = canonical).
        is_valid:           bool — chain.is_vhp_valid(token_id) result.
        output_dir:         Directory under which to write artifact + manifest.
        ts_ns:              Caller-supplied uint64 timestamp (NO wall-clock).

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    # Validate + parse inputs
    device_id_hash = _parse_device_id_hash(device_id_hash_hex)
    if device_id_hash_hex.lower().startswith("0x"):
        did_normalized = device_id_hash_hex.lower()[2:]
    else:
        did_normalized = device_id_hash_hex.lower()

    # Compose component hash from VHP token state
    component = _compose_vhp_component(
        token_id=token_id,
        device_id_hash=device_id_hash,
        expires_at=expires_at,
        cert_level=cert_level,
        is_valid=is_valid,
    )

    # Compute the ZKBA commitment: single 32B component = VHP composition hash
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.VHP,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    # Compile the artifact
    inputs = {
        "token_id":            int(token_id),
        "device_id_hash_hex":  did_normalized,
        "expires_at":          int(expires_at),
        "cert_level":          int(cert_level),
        "is_valid":            bool(is_valid),
        "zkba_commitment_hex": zkba_hex,
        "ts_ns":               int(ts_ns),
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.VHP,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_vhp_card_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.VHP),
        "proof_weight": int(ProofWeightClass.CHAIN_ONLY),
        "component_hashes_hex": [component.hex()],
        "ts_ns": int(ts_ns),
        "vhp_token_id": int(token_id),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.VHP),
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
        description="Build a VHP Verification Card ZKBA artifact (Phase O3-ZKBA-TRACK1 Track 2 follow-up)."
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--token-id",
        type=int,
        required=True,
        help="VHP soulbound token ID (uint256).",
    )
    parser.add_argument(
        "--device-id-hash",
        required=True,
        help="32-byte device ID hash as hex string (with or without 0x prefix).",
    )
    parser.add_argument(
        "--expires-at",
        type=int,
        required=True,
        help="Unix timestamp for VHP TTL expiration.",
    )
    parser.add_argument(
        "--cert-level",
        type=int,
        default=1,
        help="uint8 hardware certification tier (default 1 = canonical).",
    )
    parser.add_argument(
        "--is-valid",
        action="store_true",
        help="VHP is currently valid (chain.is_vhp_valid result).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "vhp_verification_card",
        )),
        help="Output directory (default: frontend/src/artifacts/vhp_verification_card/).",
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
    manifest = build_vhp_card_artifact(
        store=store,
        token_id=args.token_id,
        device_id_hash_hex=args.device_id_hash,
        expires_at=args.expires_at,
        cert_level=args.cert_level,
        is_valid=args.is_valid,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"VHP Verification Card compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_class:            VHP (= {int(ZKBAClass.VHP)})")
    print(f"  proof_weight:          CHAIN_ONLY")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
