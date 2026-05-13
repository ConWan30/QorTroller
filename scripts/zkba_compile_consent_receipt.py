"""Phase O3-ZKBA-TRACK1 Track 2 follow-up — Consent Receipt Card artifact builder.

Sixth ZKBA artifact target after:
  - GIC Continuity Ledger Alpha      (commit 3b3081d3; Sentry lane; 1 primitive)
  - VHP Verification Card             (commit 4f399282; Sentry lane; 1 primitive)
  - AIT Separation Snapshot           (commit bdbcf67f; Sentry lane; 1 primitive)
  - Marketplace Listing Card          (commit 269e439c; Curator lane; 2 primitives)
  - Tournament Eligibility Card       (commit 25e7f8f2; Sentry lane; 3 primitives)

Strategic value of this artifact (closes the 3-agent lane coverage gap):

1. **First Guardian-lane artifact.** Prior ZKBA artifacts exercised
   Sentry's zk_artifacts/ (4 artifacts) and Curator's zk_listings/
   (1 artifact). Guardian's zk_verifications/ has been authorized
   on-chain via Cedar v2 (commit ad0f7d11) but never exercised by a
   concrete artifact. Consent Receipt Cards write to zk_verifications/
   under Guardian's audit-trail authority — closing the 3-agent CFSS
   coverage gap. All three Operator Initiative agents now have
   empirical lane utilization, not just policy-level lane authority.

2. **First gamer-facing artifact audience.** Prior artifacts were
   operator-facing (GIC/VHP/AIT/TOURNAMENT for Sentry observability
   + tournament organizers) or buyer-facing (MARKET for marketplace
   buyers). Consent Receipt Cards are explicitly for the gamer
   themselves — their own audit of their own consent state. This
   exercises the gamer-self-sovereignty invariant at the artifact
   surface: the bridge produces a READ-ONLY projection of consent
   state, never a grant or revocation action.

3. **First GDPR Article 17 compliance-bearing artifact.** The
   `revoked_at` field surfaces the right-to-be-forgotten semantically
   — a non-zero revoked_at means the gamer has exercised Art. 17
   erasure rights and the consent is no longer authoritative. Future
   regulators or auditors verifying GDPR compliance can request a
   Consent Receipt Card snapshot and verify cryptographically that
   the bridge's behavior at ts_ns matched the consent state declared
   in the card.

Composition profile:
  - ZKBAClass.CONSENT                  (= 5 in the FROZEN-v1 enum)
  - ProofWeightClass.CHAIN_ONLY        (matches DEFAULT_PROOF_WEIGHT_BY_CLASS;
                                        consent state lives in
                                        VAPIConsentRegistry on chain)
  - Single 32-byte component hash composed from:
        SHA-256(
            consent_hash(32)            # FROZEN-v1 Phase 237 CONSENT primitive output
            || category_bitmask_be(4)   # uint32 BE; 4-bit bitmask of granted categories
            || revoked_at_be(8)         # uint64 BE; 0 if active, else unix ts of revocation
            || gamer_address_hash(32)   # SHA-256(gamer_address); pseudonymous identifier
            || receipt_id_be(8)         # uint64 BE; receipt identifier (caller-supplied)
        )                               # = 84 bytes preimage → 32B after SHA-256

Owning agent: **Guardian** (canonical name "guardian"). Consent Receipt
Cards write to the `zk_verifications/` lane authorized by
guardian_o2_suggest_v2.json (Cedar v2 LIVE since commit ad0f7d11).

GDPR Article 17 semantic invariant: A non-zero `revoked_at` value
means the gamer has exercised right-to-be-forgotten. The artifact
remains as a permanent audit record of the revocation event itself
(not the data subject's identity — `gamer_address_hash` is a
pseudonym, not the address itself). Downstream verifiers MUST treat
revoked_at > 0 AS authoritative revocation; the bridge MUST NOT
re-process biometric data after revoked_at per Phase 160 erasure
pipeline.

Track 1 invariants enforced:
  - No on-chain submission (anchor_tx_hash stays NULL in zkba_artifact_log)
  - Caller-supplied state inputs (no live chain reads)
  - Caller-supplied ts_ns (no wall-clock read)
  - Deterministic compile (same inputs → same output bytes)
  - Bridge does NOT grant or revoke consent in this script
    (gamer-self-sovereignty invariant — the script is a READ-ONLY
    receipt projection)

Run via CLI (offline; uses provided inputs):
    python scripts/zkba_compile_consent_receipt.py \\
        --consent-hash 0xabcd...64chars \\
        --category-bitmask 5 \\
        --revoked-at 0 \\
        --gamer-address-hash 0xdef0...64chars \\
        --receipt-id 1 \\
        --ts-ns 1778900000000000000

Author: VAPI Architect (post-TOURNAMENT sixth-artifact ship 2026-05-12)
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


# Category names mirror bridge/vapi_bridge/consent_categories.py
# (re-stated here so the renderer can label the bitmask without a
# bridge import dependency)
_CATEGORY_LABELS = (
    "TOURNAMENT_GATE",      # bit 0
    "ANONYMIZED_RESEARCH",  # bit 1
    "MANUFACTURER_CERT",    # bit 2
    "MARKETPLACE",          # bit 3
)


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


def _compose_consent_component(
    *,
    consent_hash: bytes,
    category_bitmask: int,
    revoked_at: int,
    gamer_address_hash: bytes,
    receipt_id: int,
) -> bytes:
    """Compose a single 32-byte ZKBA component from consent receipt state.

    Byte layout (FROZEN at v1; downstream verifiers reproduce this exact order):

        SHA-256(
            consent_hash(32)            # FROZEN-v1 Phase 237 CONSENT primitive output
            || category_bitmask_be(4)   # uint32 BE; bitmask of granted categories
            || revoked_at_be(8)         # uint64 BE; 0 if active, else unix ts of revocation
            || gamer_address_hash(32)   # SHA-256(gamer_address); pseudonymous
            || receipt_id_be(8)         # uint64 BE; caller-supplied
        )                               # = 84 bytes preimage → 32B after SHA-256

    Note that consent_hash itself already commits to (device_id_b32 +
    bitmask + expires_at + ts_ns) per Phase 237 FROZEN FORMULA v1.
    Re-including the bitmask in the ZKBA preimage is intentional:
    it surfaces the category set explicitly so a verifier inspecting
    the ZKBA commitment can confirm the bitmask without re-deriving
    the CONSENT primitive. The redundancy strengthens audit clarity
    at the cost of 4 extra preimage bytes.
    """
    if not isinstance(consent_hash, (bytes, bytearray)) or len(consent_hash) != 32:
        raise ValueError(
            f"consent_hash must be 32 raw bytes; got {len(consent_hash)} bytes"
        )
    if not isinstance(category_bitmask, int) or category_bitmask < 0 or category_bitmask > 0xFFFFFFFF:
        raise ValueError(f"category_bitmask must be uint32; got {category_bitmask!r}")
    if not isinstance(revoked_at, int) or revoked_at < 0 or revoked_at > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"revoked_at must be uint64; got {revoked_at!r}")
    if not isinstance(gamer_address_hash, (bytes, bytearray)) or len(gamer_address_hash) != 32:
        raise ValueError(
            f"gamer_address_hash must be 32 raw bytes; got {len(gamer_address_hash)} bytes"
        )
    if not isinstance(receipt_id, int) or receipt_id < 0 or receipt_id > 0xFFFFFFFFFFFFFFFF:
        raise ValueError(f"receipt_id must be uint64; got {receipt_id!r}")

    preimage = (
        bytes(consent_hash)
        + category_bitmask.to_bytes(4, "big")
        + revoked_at.to_bytes(8, "big")
        + bytes(gamer_address_hash)
        + receipt_id.to_bytes(8, "big")
    )
    assert len(preimage) == 32 + 4 + 8 + 32 + 8 == 84
    return hashlib.sha256(preimage).digest()


def _bitmask_to_categories(bitmask: int) -> list:
    """Decode a 4-bit category bitmask into a list of category labels.

    Returns labels for the bits set in low-to-high order
    (TOURNAMENT_GATE = bit 0, MARKETPLACE = bit 3).
    """
    return [
        _CATEGORY_LABELS[i]
        for i in range(len(_CATEGORY_LABELS))
        if (bitmask >> i) & 1
    ]


# ---------------------------------------------------------------------------
# Deterministic HTML renderer
# ---------------------------------------------------------------------------

def _render_consent_receipt_html(inputs: dict) -> str:
    """Deterministic HTML rendering of a Consent Receipt Card.

    Inputs dict shape (all keys required; all values deterministic):
      - "consent_hash_hex":        str (64 lowercase hex)
      - "category_bitmask":        int (uint32)
      - "categories_active":       list of str (decoded from bitmask)
      - "revoked_at":              int (0 = active; else unix ts of revocation)
      - "gamer_address_hash_hex":  str (64 lowercase hex)
      - "receipt_id":              int (uint64)
      - "zkba_commitment_hex":     str (64 lowercase hex)
      - "ts_ns":                   int (uint64; caller-supplied)
    """
    consent_hex = inputs["consent_hash_hex"]
    bitmask = int(inputs["category_bitmask"])
    categories = inputs["categories_active"]
    revoked_at = int(inputs["revoked_at"])
    gamer_hex = inputs["gamer_address_hash_hex"]
    receipt_id = int(inputs["receipt_id"])
    zkba_hex = inputs["zkba_commitment_hex"]
    ts_ns = int(inputs["ts_ns"])

    is_revoked = revoked_at > 0
    status_label = "REVOKED (GDPR Art. 17 erasure invoked)" if is_revoked else "ACTIVE"
    status_color = "#d65b78" if is_revoked else "#5bd6a3"

    if categories:
        category_list_html = ", ".join(
            f"<code>{c}</code>" for c in categories
        )
    else:
        category_list_html = "<em>(none granted)</em>"

    revoked_label = (
        f"<code>{revoked_at}</code> (unix ts)"
        if is_revoked else "<em>(active; not revoked)</em>"
    )

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        f"  <title>Consent Receipt - receipt {receipt_id}</title>\n"
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
        "    em { color: #607a93; font-style: italic; }\n"
        "    .footer { margin-top: 2em; color: #607a93; font-size: 0.8em; "
        "border-top: 1px solid #1a2a40; padding-top: 0.5em; }\n"
        "    .weight { background: #1a2a40; color: #93a5b8; padding: 2px 8px; "
        "border-radius: 4px; }\n"
        f"    .status-badge {{ background: {status_color}; color: #020408; "
        "padding: 4px 12px; border-radius: 4px; font-weight: bold; }}\n"
        "    .gdpr-notice { background: #1a2a40; color: #cfe8ff; "
        "padding: 0.8em; margin: 1em 0; border-left: 3px solid #f0a868; "
        "font-size: 0.85em; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"  <h1>Consent Receipt Card</h1>\n"
        "  <div class=\"meta\">\n"
        f"    <div style=\"font-size:1.05em; margin: 0.5em 0;\">"
        f"Status: <span class=\"status-badge\">{status_label}</span></div>\n"
        f"    <h2>Consent State (Phase 237 FROZEN-v1 primitive)</h2>\n"
        f"    <div>Consent hash: <code>0x{consent_hex}</code></div>\n"
        f"    <div>Category bitmask: <code>{bitmask}</code> "
        f"(0b{bitmask:04b})</div>\n"
        f"    <div>Categories active: {category_list_html}</div>\n"
        f"    <h2>Revocation (GDPR Article 17)</h2>\n"
        f"    <div>Revoked at: {revoked_label}</div>\n"
        "    <div class=\"gdpr-notice\">"
        "<strong>GDPR Art. 17 notice.</strong> A non-zero revoked_at means "
        "the gamer has exercised right-to-be-forgotten. The bridge MUST NOT "
        "process biometric data under this consent after the revocation "
        "timestamp. This receipt remains as a permanent audit record of "
        "the revocation event itself (the gamer address is hashed for "
        "pseudonymity)."
        "</div>\n"
        f"    <h2>Gamer Pseudonym</h2>\n"
        f"    <div>SHA-256(gamer address): <code>0x{gamer_hex}</code></div>\n"
        f"    <div><em>The gamer address itself is not in this artifact; "
        f"only its hash, for pseudonymity.</em></div>\n"
        f"    <h2>Receipt Metadata</h2>\n"
        f"    <div>Receipt ID: <code>{receipt_id}</code></div>\n"
        f"    <div>ZKBA commitment: <code>{zkba_hex}</code></div>\n"
        f"    <div>ts_ns: <code>{ts_ns}</code></div>\n"
        "    <div>Proof weight: <span class=\"weight\">CHAIN_ONLY</span> "
        "(consent state via VAPIConsentRegistry)</div>\n"
        "  </div>\n"
        "  <div class=\"footer\">\n"
        "    Deterministic projection compiled by vsd_ui_compiler v0.1.0. "
        "Manifest schema vapi-zkba-manifest-v1. "
        "ZKBA class CONSENT (= 5 in PATTERN-017 FROZEN-v1 enum). "
        "Phase O3-ZKBA-TRACK1 Track 2 sixth-artifact ship — Guardian "
        "lane authority via Cedar v2 zk_verifications/. "
        "Gamer-facing audit surface; READ-ONLY projection — bridge "
        "never grants or revokes consent on behalf of the gamer "
        "(gamer-self-sovereignty invariant). "
        "No CDN; no network; no wall-clock; self-contained.\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Build orchestrator
# ---------------------------------------------------------------------------

def build_consent_receipt_artifact(
    *,
    store,
    consent_hash_hex: str,
    category_bitmask: int,
    revoked_at: int,
    gamer_address_hash_hex: str,
    receipt_id: int,
    output_dir: Path,
    ts_ns: int,
) -> ZKBAManifest:
    """Build a Consent Receipt Card ZKBA artifact deterministically.

    Composes the ZKBA commitment from Phase 237 CONSENT primitive output
    + GDPR-relevant context (revocation, pseudonymous gamer identity,
    receipt id). Calls compile_artifact() to emit HTML + manifest and
    inserts a row into zkba_artifact_log.

    READ-ONLY: this script does not write any consent state. It only
    projects an existing consent_hash + revocation status into a
    cryptographic artifact. Bridge consent state must be granted /
    revoked through Phase 237 endpoints + gamer-signed on-chain
    transactions; this script consumes that state for audit.

    Args:
        store:                   bridge.vapi_bridge.store.Store instance.
        consent_hash_hex:        32-byte CONSENT v1 commitment from
                                 Phase 237 compute_consent_hash() as hex.
        category_bitmask:        uint32 bitmask of granted categories.
        revoked_at:              0 if consent active; else unix ts of
                                 revocation (GDPR Art. 17 erasure event).
        gamer_address_hash_hex:  32-byte SHA-256 of gamer's address as
                                 hex (pseudonymous; never the address itself).
        receipt_id:              Receipt identifier (uint64; caller-supplied).
        output_dir:              Directory for artifact + manifest.
        ts_ns:                   Caller-supplied uint64 timestamp.

    Returns:
        ZKBAManifest describing the emitted artifact.
    """
    consent_hash = _parse_hex32(consent_hash_hex, "consent_hash")
    gamer_address_hash = _parse_hex32(gamer_address_hash_hex, "gamer_address_hash")

    # Normalize hex inputs (drop 0x prefix, lowercase) for rendering
    consent_norm = consent_hash_hex.lower()
    if consent_norm.startswith("0x"):
        consent_norm = consent_norm[2:]
    gamer_norm = gamer_address_hash_hex.lower()
    if gamer_norm.startswith("0x"):
        gamer_norm = gamer_norm[2:]

    # Compose component hash
    component = _compose_consent_component(
        consent_hash=consent_hash,
        category_bitmask=category_bitmask,
        revoked_at=revoked_at,
        gamer_address_hash=gamer_address_hash,
        receipt_id=receipt_id,
    )

    # Compute the ZKBA commitment
    zkba_commitment = compute_zkba_commitment(
        zkba_class=ZKBAClass.CONSENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        component_hashes=(component,),
        ts_ns=ts_ns,
    )
    zkba_hex = zkba_commitment.hex()

    categories_active = _bitmask_to_categories(category_bitmask)

    inputs = {
        "consent_hash_hex":         consent_norm,
        "category_bitmask":         int(category_bitmask),
        "categories_active":        categories_active,
        "revoked_at":               int(revoked_at),
        "gamer_address_hash_hex":   gamer_norm,
        "receipt_id":               int(receipt_id),
        "zkba_commitment_hex":      zkba_hex,
        "ts_ns":                    int(ts_ns),
    }

    manifest = compile_artifact(
        zkba_class=ZKBAClass.CONSENT,
        proof_weight=ProofWeightClass.CHAIN_ONLY,
        inputs=inputs,
        output_dir=Path(output_dir),
        html_renderer=_render_consent_receipt_html,
    )

    # Insert row into zkba_artifact_log (Track 1: anchor_tx_hash stays NULL)
    preimage_json = json.dumps({
        "zkba_class": int(ZKBAClass.CONSENT),
        "proof_weight": int(ProofWeightClass.CHAIN_ONLY),
        "component_hashes_hex": [component.hex()],
        "ts_ns": int(ts_ns),
        "consent_hash_hex": consent_norm,
        "category_bitmask": int(category_bitmask),
        "categories_active": categories_active,
        "revoked_at": int(revoked_at),
        "gamer_address_hash_hex": gamer_norm,
        "receipt_id": int(receipt_id),
    }, sort_keys=True, separators=(",", ":"))

    store.insert_zkba_artifact(
        zkba_class=int(ZKBAClass.CONSENT),
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
        description="Build a Consent Receipt Card ZKBA artifact (Phase O3-ZKBA-TRACK1 Track 2 sixth-artifact)."
    )
    parser.add_argument(
        "--db",
        default=os.path.normpath(os.path.join(_HERE, "..", "bridge", "vapi_store.db")),
        help="Path to bridge SQLite DB.",
    )
    parser.add_argument(
        "--consent-hash",
        required=True,
        help="32-byte CONSENT v1 commitment as hex (with or without 0x prefix).",
    )
    parser.add_argument(
        "--category-bitmask",
        type=int,
        required=True,
        help="uint32 bitmask of granted categories "
             "(bit 0 = TOURNAMENT_GATE, bit 1 = ANONYMIZED_RESEARCH, "
             "bit 2 = MANUFACTURER_CERT, bit 3 = MARKETPLACE).",
    )
    parser.add_argument(
        "--revoked-at",
        type=int,
        default=0,
        help="0 if consent is active; else unix ts of revocation (GDPR Art. 17 erasure).",
    )
    parser.add_argument(
        "--gamer-address-hash",
        required=True,
        help="32-byte SHA-256 of gamer's address as hex (pseudonymous).",
    )
    parser.add_argument(
        "--receipt-id",
        type=int,
        required=True,
        help="Receipt identifier (uint64).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.path.normpath(os.path.join(
            _HERE, "..", "frontend", "src", "artifacts", "consent_receipt_card",
        )),
        help="Output directory (default: frontend/src/artifacts/consent_receipt_card/).",
    )
    parser.add_argument(
        "--ts-ns",
        type=int,
        required=True,
        help="Caller-supplied uint64 timestamp (no wall-clock).",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    from vapi_bridge.store import Store  # noqa: E402
    store = Store(args.db)
    manifest = build_consent_receipt_artifact(
        store=store,
        consent_hash_hex=args.consent_hash,
        category_bitmask=args.category_bitmask,
        revoked_at=args.revoked_at,
        gamer_address_hash_hex=args.gamer_address_hash,
        receipt_id=args.receipt_id,
        output_dir=Path(args.output_dir),
        ts_ns=args.ts_ns,
    )
    print(f"Consent Receipt Card compiled:")
    print(f"  output_path:           {manifest.output_path}")
    print(f"  output_hash_hex:       {manifest.output_hash_hex}")
    print(f"  input_commitment_hex:  {manifest.input_commitment_hex}")
    print(f"  zkba_class:            CONSENT (= {int(ZKBAClass.CONSENT)})")
    print(f"  proof_weight:          CHAIN_ONLY")
    print(f"  compiler_version:      {manifest.compiler_version}")
    print(f"  manifest path:         {manifest.output_path.rsplit('.', 1)[0]}.manifest.json")
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
