"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Hardware Participation Card artifact builder.

Seventh and FINAL ZKBA artifact target. Closes Layer 7 (Methodology Layer)
coverage to 7 of 7 classes in the FROZEN-v1 ZKBAClass enum after:

  - AIT Separation Snapshot       (class 1, CALIBRATION_PLUS_CONTEXT, commit bdbcf67f)
  - GIC Continuity Ledger Alpha   (class 2, CHAIN_ONLY,               commit 3b3081d3)
  - VHP Verification Card         (class 3, CHAIN_ONLY,               commit 4f399282)
  - HARDWARE Participation Card   (class 4, CHAIN_ONLY,               THIS COMMIT)
  - Consent Receipt Card          (class 5, CHAIN_ONLY,               commit 9bfa981e)
  - Tournament Eligibility Card   (class 6, CHAIN_ONLY,               commit 25e7f8f2)
  - Marketplace Listing Card      (class 7, MARKETPLACE_DERIVED,      commit 269e439c)

Strategic value of this artifact:

1. **Closes 7-of-7 Layer 7 ZKBAClass coverage.** External reviewers comparing
   the Pass 2C activation matrix against shipped artifacts can no longer flag
   `class 4 = HARDWARE` as unverified. The §9.29 whitepaper integration claim
   becomes "all 7 ZKBAClass values empirically composable through the same
   PATTERN-017 primitive + compiler + wrapper + validator + audit pipeline"
   without an exception clause.

2. **First MANUFACTURER-bound audience artifact.** Prior 6 artifacts targeted
   gamers (CONSENT), operators (AIT/GIC/VHP/TOURNAMENT), or buyers (MARKET).
   HARDWARE Participation Card binds the certifying MANUFACTURER's on-chain
   address into the preimage — first ZKBA artifact whose commitment depends
   on which manufacturer certified the device, not just on the device or
   gamer state. Surfaces manufacturer-attestation as a cryptographic surface
   for partner programs (Sony Partner / GuliKit aftermarket / etc.).

3. **References live Phase 99A on-chain primitive.** VAPIHardwareCertRegistry
   is LIVE on IoTeX testnet (Phase 99A, contracts/deployed-addresses.json).
   `chain.isCertified(profile_hash)` is a zero-gas view call; the artifact
   composes that view result with the static device_id_hash + certifying
   manufacturer address to produce a tamper-evident manufacturer-attestation
   audit surface.

Composition profile:
  - ZKBAClass.HARDWARE              (= 4 in the FROZEN-v1 enum at zkba_artifact.py)
  - ProofWeightClass.CHAIN_ONLY     (all referenced state on-chain anchored at
                                     certification time; no fresh capture)
  - Single 32-byte component hash composed from:
        SHA-256(
            profile_hash(32)          # keccak256(mfr || model || firmwareVersion)
            || device_id_hash(32)     # SHA-256(canonical device name UTF-8 bytes)
            || cert_level_be(1)       # uint8 (1=controller, 2=controller+GSR)
            || manufacturer_addr(20)  # 20-byte Ethereum address (certifying address)
            || is_certified_byte(1)   # 0x01 if active, 0x00 if revoked/never-certified
        )                             # = 86 bytes preimage → 32 bytes after SHA-256

Owning agent: **Sentry** (canonical name "anchor_sentry"). HARDWARE cards
write to the `zk_artifacts/` lane authorized by anchor_sentry_o2_suggest_v2.json
(Cedar v2 LIVE since commit ad0f7d11 dual-anchored on AgentScope +
AgentRegistry 2026-05-12). Mirrors VHP / AIT / GIC / TOURNAMENT lane authority.

Track 1 invariants enforced:
  - No on-chain submission (anchor_tx_hash stays NULL in zkba_artifact_log)
  - Caller-supplied state inputs (no live chain reads at compile time;
    chain.isCertified is consulted ONCE by the caller and the bool is passed in)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs → same output bytes)

Canonical fixture: bridge wallet (the operator/manufacturer in current testnet
deployment) certifying the Sony DualShock Edge CFI-ZCP1 at cert_level=1
(controller-only tier per VAPIHardwareCertRegistry §35 schema).

Run via CLI (offline; uses provided inputs):
    python scripts/zkba_compile_hardware_card.py \
        --profile-hash 0x... \
        --device-id-hash 0x10e0169446ba3320... \
        --cert-level 1 \
        --manufacturer-address 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692 \
        --is-certified \
        --ts-ns 1778900000000000000

Pairs with G4 manifest validator + VPM wrapper at scripts/vsd_vpm_wrapper.py
for the end-to-end Layer 7 pipeline.

Author: VAPI Architect (post-Track-2 seventh-artifact ship — completes Layer 7)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
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

def _compose_hardware_component(
    *,
    profile_hash: bytes,
    device_id_hash: bytes,
    cert_level: int,
    manufacturer_addr: bytes,
    is_certified: bool,
) -> bytes:
    """Compose a single 32-byte ZKBA component from hardware cert state.

    Byte layout (FROZEN at v1; downstream verifiers reproduce this exact order):

        SHA-256(
            profile_hash(32)          # 32 bytes raw — keccak256(mfr||model||fw)
            || device_id_hash(32)     # 32 bytes raw — SHA-256(canonical name)
            || cert_level_be(1)       # 1 byte uint8 BE (1 or 2 per Phase 99A enum)
            || manufacturer_addr(20)  # 20 bytes raw — Ethereum address
            || is_certified_byte(1)   # 1 byte: 0x01 if active, 0x00 otherwise
        )                             # = 86 bytes total → 32 bytes after SHA-256

    Manufacturer address is the certifying party's 20-byte Ethereum address,
    NOT hashed — surface it in clear in the preimage so downstream verifiers
    can attribute the certification to a specific on-chain actor without an
    additional pre-image lookup. (Mirrors how `gamer_address_hash` is hashed
    in CONSENT v1 for privacy: hardware certification is publicly attributable
    by design, so no privacy hashing applies.)
    """
    if not isinstance(profile_hash, (bytes, bytearray)) or len(profile_hash) != 32:
        raise ValueError(
            f"profile_hash must be 32 raw bytes; got {len(profile_hash)} bytes"
        )
    if not isinstance(device_id_hash, (bytes, bytearray)) or len(device_id_hash) != 32:
        raise ValueError(
            f"device_id_hash must be 32 raw bytes; got {len(device_id_hash)} bytes"
        )
    if not isinstance(cert_level, int) or cert_level < 0 or cert_level > 255:
        raise ValueError(f"cert_level must be uint8; got {cert_level!r}")
    if not isinstance(manufacturer_addr, (bytes, bytearray)) or len(manufacturer_addr) != 20:
        raise ValueError(
            f"manufacturer_addr must be 20 raw bytes; got {len(manufacturer_addr)} bytes"
        )

    cert_byte = struct.pack(">B", cert_level)
    is_certified_byte = b"\x01" if is_certified else b"\x00"

    preimage = (
        bytes(profile_hash)
        + bytes(device_id_hash)
        + cert_byte
        + bytes(manufacturer_addr)
        + is_certified_byte
    )
    assert len(preimage) == 32 + 32 + 1 + 20 + 1 == 86
    return hashlib.sha256(preimage).digest()


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


def _parse_address(s: str) -> bytes:
    """Parse a 20-byte Ethereum address (with or without 0x prefix).

    Returns raw 20 bytes (lowercase). Does NOT enforce EIP-55 checksum —
    the artifact commitment is over raw bytes; case differences in the
    input string produce identical preimages.
    """
    if not isinstance(s, str):
        raise ValueError(f"manufacturer_address must be hex string; got {type(s).__name__}")
    s2 = s.lower()
    if s2.startswith("0x"):
        s2 = s2[2:]
    if len(s2) != 40:
        raise ValueError(
            f"manufacturer_address must be 40 hex chars (20 bytes); got {len(s2)} chars"
        )
    try:
        return bytes.fromhex(s2)
    except ValueError as exc:
        raise ValueError(f"manufacturer_address not valid hex: {exc}") from exc


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

_CERT_LEVEL_LABELS = {
    1: "TIER 1 — CONTROLLER ONLY",
    2: "TIER 2 — CONTROLLER + GSR",
}


def _render_hardware_card_html(inputs: dict) -> str:
    """Deterministic HTML rendering of a Hardware Participation Card.

    Inputs dict shape (all keys required; all values deterministic):
      - "profile_hash_hex":         str (64 lowercase hex)
      - "device_id_hash_hex":       str (64 lowercase hex)
      - "cert_level":               int (uint8; 1 or 2 per Phase 99A schema)
      - "manufacturer_address_hex": str (40 lowercase hex, no 0x prefix)
      - "is_certified":             bool
      - "zkba_commitment_hex":      str (64 lowercase hex)
      - "ts_ns":                    int (uint64; caller-supplied)
    """
    profile_hex = inputs["profile_hash_hex"]
    did_hex = inputs["device_id_hash_hex"]
    cert = int(inputs["cert_level"])
    mfr_hex = inputs["manufacturer_address_hex"]
    certified = bool(inputs["is_certified"])
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])

    status_label = "CERTIFIED" if certified else "REVOKED / UNREGISTERED"
    status_color = "#5bd6a3" if certified else "#d65b78"
    cert_label = _CERT_LEVEL_LABELS.get(cert, f"TIER {cert} (out of Phase 99A canonical range)")

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>Hardware Participation Card - {profile_hex[:12]}</title>\n"
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
        "    .mfr-badge { background: #5bd6a3; color: #04060a; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>Hardware Participation Card</h1>\n"
        "  <h2>Hardware Profile</h2>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Profile hash (keccak256 of mfr || model || firmwareVersion): "
        f"<code>0x{profile_hex}</code></div>\n"
        f"    <div>Device ID hash (SHA-256 of canonical name): "
        f"<code>0x{did_hex}</code></div>\n"
        f"    <div>Certification tier: <span class=\"tier-badge\">{cert_label}</span></div>\n"
        "  </div>\n"
        "  <h2>Certifying Manufacturer</h2>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Manufacturer address: <span class=\"mfr-badge\">0x{mfr_hex}</span></div>\n"
        f"    <div>Status: <span class=\"status-badge\">{status_label}</span></div>\n"
        "  </div>\n"
        "  <h2>ZKBA Commitment</h2>\n"
        "  <div class=\"meta\">\n"
        f"    <div>Commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">CHAIN_ONLY</span> "
        "(VAPIHardwareCertRegistry state on-chain anchored at certification time)</div>\n"
        "  </div>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "ZKBA class HARDWARE (= 4 in PATTERN-017 FROZEN-v1 enum). "
        "Phase O3-ZKBA-TRACK1 Track 2 seventh-artifact ship — closes Layer 7 "
        "coverage to 7-of-7 ZKBAClass values. Sentry lane authority via "
        "Cedar v2 zk_artifacts/. Manufacturer-attestation audit surface for "
        "tournament organizer + partner-program verification. "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_hardware_card_artifact(
    *,
    store,
    profile_hash_hex: str,
    device_id_hash_hex: str,
    cert_level: int,
    manufacturer_address_hex: str,
    is_certified: bool,
    output_dir: Path,
    ts_ns: int,
) -> ZKBAManifest:
    """Build a Hardware Participation Card ZKBA artifact deterministically.

    Composes the ZKBA commitment from VAPIHardwareCertRegistry state (Phase
    99A LIVE on IoTeX testnet) + canonical device_id_hash + certifying
    manufacturer address, calls compile_artifact() to emit HTML + manifest,
    and inserts a row into zkba_artifact_log.

    Args:
        store:                     bridge.vapi_bridge.store.Store instance.
        profile_hash_hex:          32-byte profile hash as hex string (with or
                                   without 0x prefix). Should match
                                   keccak256(manufacturer || model || firmwareVersion)
                                   for the certified hardware profile.
        device_id_hash_hex:        32-byte device ID hash as hex string (with
                                   or without 0x prefix). Canonical:
                                   SHA-256("Sony_DualShock_Edge_CFI-ZCP1") =
                                   0x10e0169446ba3320...
        cert_level:                uint8 hardware certification tier (1=controller,
                                   2=controller+GSR per VAPIHardwareCertRegistry §35).
        manufacturer_address_hex:  20-byte Ethereum address (40 hex chars) of
                                   the certifying party. NOT hashed — surfaced
                                   in clear in the preimage for public attribution.
        is_certified:              bool — chain.isCertified(profile_hash) result.
                                   Caller MUST consult the on-chain view BEFORE
                                   calling this builder; compile path is offline.
        output_dir:                Directory under which to write artifact +
                                   manifest.
        ts_ns:                     Caller-supplied uint64 timestamp (NO wall-clock).

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    # Validate + parse inputs
    profile_hash = _parse_hex32(profile_hash_hex, "profile_hash")
    device_id_hash = _parse_hex32(device_id_hash_hex, "device_id_hash")
    manufacturer_addr = _parse_address(manufacturer_address_hex)

    # Normalize hex inputs (drop 0x prefix, lowercase) for downstream renderer
    # + preimage_json — keep them consistent regardless of input format.
    def _normalize(s: str) -> str:
        s2 = s.lower()
        return s2[2:] if s2.startswith("0x") else s2

    profile_norm = _normalize(profile_hash_hex)
    did_norm = _normalize(device_id_hash_hex)
    mfr_norm = _normalize(manufacturer_address_hex)

    # Compose component hash from hardware cert + manufacturer state
    component = _compose_hardware_component(
        profile_hash=profile_hash,
        device_id_hash=device_id_hash,
        cert_level=cert_level,
        manufacturer_addr=manufacturer_addr,
        is_certified=is_certified,
    )

    # Compute the ZKBA commitment
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.HARDWARE,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    inputs = {
        "profile_hash_hex":         profile_norm,
        "device_id_hash_hex":       did_norm,
        "cert_level":               int(cert_level),
        "manufacturer_address_hex": mfr_norm,
        "is_certified":             bool(is_certified),
        "zkba_commitment_hex":      zkba_hex,
        "ts_ns":                    int(ts_ns),
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.HARDWARE,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_hardware_card_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.HARDWARE),
        "proof_weight": int(ProofWeightClass.CHAIN_ONLY),
        "component_hashes_hex": [component.hex()],
        "ts_ns": int(ts_ns),
        "profile_hash_hex": profile_norm,
        "device_id_hash_hex": did_norm,
        "cert_level": int(cert_level),
        "manufacturer_address_hex": mfr_norm,
        "is_certified": bool(is_certified),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.HARDWARE),
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
        description="Build a Hardware Participation Card ZKBA artifact "
                    "(Phase O3-ZKBA-TRACK1 Track 2 seventh-artifact — "
                    "completes Layer 7 7-of-7 ZKBAClass coverage).",
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--profile-hash",
        required=True,
        help="32-byte profile hash as hex string (with or without 0x prefix). "
             "Should match keccak256(manufacturer || model || firmwareVersion).",
    )
    parser.add_argument(
        "--device-id-hash",
        required=True,
        help="32-byte device ID hash as hex string (with or without 0x prefix). "
             "Canonical: SHA-256 of canonical device name UTF-8 bytes.",
    )
    parser.add_argument(
        "--cert-level",
        type=int,
        default=1,
        help="uint8 hardware certification tier (default 1; 1=controller, "
             "2=controller+GSR per VAPIHardwareCertRegistry §35).",
    )
    parser.add_argument(
        "--manufacturer-address",
        required=True,
        help="20-byte Ethereum address (40 hex chars, with or without 0x) "
             "of the certifying party.",
    )
    parser.add_argument(
        "--is-certified",
        action="store_true",
        help="VAPIHardwareCertRegistry.isCertified(profile_hash) result; "
             "set this flag if certification is active on chain.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "hardware_participation_card",
        )),
        help="Output directory "
             "(default: frontend/src/artifacts/hardware_participation_card/).",
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
    manifest = build_hardware_card_artifact(
        store=store,
        profile_hash_hex=args.profile_hash,
        device_id_hash_hex=args.device_id_hash,
        cert_level=args.cert_level,
        manufacturer_address_hex=args.manufacturer_address,
        is_certified=args.is_certified,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print("Hardware Participation Card compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_class:            HARDWARE (= {int(ZKBAClass.HARDWARE)})")
    print(f"  proof_weight:          CHAIN_ONLY")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
