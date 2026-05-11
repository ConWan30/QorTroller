"""Phase O1-VBDIP-0001-INTEGRATION Step 4 — Architect Ed25519 key attestation.

Establishes the deployer-anchored signing chain for VAD methodology
artifacts per VBD-INV-1 (continuous deployer-verified provenance):

  1. Generate an Ed25519 key pair locally (architect's signing key)
  2. Build a canonical attestation envelope (JSON; sorted-key) over the
     architect's 32-byte public key + bridge wallet address + purpose tag
     + ts_ns
  3. Sign the envelope with the BRIDGE_WALLET'S secp256k1 private key via
     EIP-191 (eth_account.Account.sign_message; off-chain, zero gas)
  4. Verify the signature recovers the bridge wallet address
  5. Write the attestation JSON to vsd-vault/eval/architect_key_attestation.json

Security model:
  - The architect Ed25519 PRIVATE key (vsd-vault/architect_key.pem) is
    gitignored via vsd-vault/.gitignore; NEVER committed
  - The architect public key is extracted to vsd-vault/architect_pubkey.pem
    and is safe to commit
  - The bridge wallet PRIVATE key (BRIDGE_PRIVATE_KEY in bridge/.env) is
    READ from environment ONCE for signing; NEVER echoed; NEVER persisted
    anywhere by this script
  - The attestation JSON contains: pubkey bytes (hex), bridge wallet
    address, purpose tag, ts_ns, signature bytes (hex), recovered address
    (for verification). NO private material.

Usage (CLI):
  python scripts/vsd_attest_architect_key.py [--ts-ns <int>] [--force]

Options:
  --ts-ns <int>: explicit uint64 timestamp; if omitted, time.time_ns() is
                 used and the resulting value is RECORDED in the
                 attestation JSON (so the attestation is reproducible
                 from its own recorded fields)
  --force:       overwrite existing attestation (DESTRUCTIVE; default
                 refuses if attestation already exists)

Author: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# eth_account / web3 for bridge wallet signing
from eth_account import Account
from eth_account.messages import encode_defunct

# Cryptography for Ed25519 key parsing (extract raw public key from PEM)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, ".."))
_VSD_VAULT = Path(_REPO) / "vsd-vault"
_ARCHITECT_KEY_PEM = _VSD_VAULT / "architect_key.pem"
_ARCHITECT_PUBKEY_PEM = _VSD_VAULT / "architect_pubkey.pem"
_ATTESTATION_PATH = _VSD_VAULT / "eval" / "architect_key_attestation.json"

# FROZEN attestation purpose tag — pinned at v1.0 for the deployer-anchored
# signing chain establishment; any change requires a new attestation epoch
# and a separate audit-trail entry
_PURPOSE_TAG = "vsd-architect-key-anchor-v1"

# Expected bridge wallet (per CLAUDE.md memory header). The attestation is
# considered valid only if the recovered signer address equals this value.
_EXPECTED_BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"


def _canonical_json_bytes(obj) -> bytes:
    """Sorted-key UTF-8 JSON encoding for deterministic byte output."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _read_bridge_private_key_from_env_file(env_path: Path) -> str:
    """Read BRIDGE_PRIVATE_KEY from a .env-style file.  Returns the raw
    value with surrounding quotes stripped.  Never echoes the value."""
    if not env_path.exists():
        raise FileNotFoundError(f"bridge/.env not found at {env_path}")
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("BRIDGE_PRIVATE_KEY="):
                value = line.split("=", 1)[1].strip()
                # Strip surrounding quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                if not value:
                    raise ValueError("BRIDGE_PRIVATE_KEY is set but empty")
                return value
    raise KeyError("BRIDGE_PRIVATE_KEY not found in bridge/.env")


def _generate_ed25519_key_pair(out_pem: Path) -> None:
    """Generate an Ed25519 key pair via openssl and write to out_pem.
    Does NOT echo any key material to stdout."""
    out_pem.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(out_pem)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"openssl genpkey failed (rc={result.returncode}); stderr: {result.stderr.strip()}"
        )
    if not out_pem.exists():
        raise RuntimeError(f"openssl produced no output at {out_pem}")


def _extract_ed25519_public_bytes(pem_path: Path) -> bytes:
    """Load Ed25519 private key from PEM, return raw 32-byte public key."""
    with open(pem_path, "rb") as f:
        pem_bytes = f.read()
    private_key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError(
            f"key at {pem_path} is not Ed25519; got {type(private_key).__name__}"
        )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    if len(public_bytes) != 32:
        raise RuntimeError(
            f"unexpected Ed25519 public key length: {len(public_bytes)} (expected 32)"
        )
    return public_bytes


def _write_architect_pubkey_pem(private_pem_path: Path, public_pem_out: Path) -> None:
    """Write the public-key-only PEM (safe to commit) extracted from
    the private key PEM."""
    with open(private_pem_path, "rb") as f:
        pem_bytes = f.read()
    private_key = serialization.load_pem_private_key(pem_bytes, password=None)
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_pem_out.parent.mkdir(parents=True, exist_ok=True)
    public_pem_out.write_bytes(public_pem)


def _build_attestation_envelope(architect_pubkey_hex: str, ts_ns: int) -> dict:
    """Build the canonical attestation envelope (without signature)."""
    return {
        "architect_pubkey_ed25519": architect_pubkey_hex,  # 64 lowercase hex
        "attested_at_ts_ns":        int(ts_ns),
        "purpose":                  _PURPOSE_TAG,
        "bridge_wallet_address":    _EXPECTED_BRIDGE_WALLET,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate architect Ed25519 key + bridge-wallet attestation "
                    "(VBDIP-0001 Step 4)."
    )
    parser.add_argument("--ts-ns", type=int, default=None, help="Explicit uint64 ts_ns")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing attestation (default refuse)")
    args = parser.parse_args()

    # 0. Pre-flight checks
    if _ATTESTATION_PATH.exists() and not args.force:
        print(f"ATTESTATION ALREADY EXISTS: {_ATTESTATION_PATH}")
        print("Refusing to overwrite. Use --force to override (DESTRUCTIVE).")
        return 2

    # 1. Generate Ed25519 key (or reuse existing)
    if _ARCHITECT_KEY_PEM.exists():
        print(f"Using existing architect key: {_ARCHITECT_KEY_PEM}")
    else:
        print(f"Generating new architect Ed25519 key: {_ARCHITECT_KEY_PEM}")
        _generate_ed25519_key_pair(_ARCHITECT_KEY_PEM)
        print("  -> generated")

    # 2. Extract Ed25519 public key (32 raw bytes)
    architect_pubkey = _extract_ed25519_public_bytes(_ARCHITECT_KEY_PEM)
    architect_pubkey_hex = architect_pubkey.hex()
    print(f"Architect Ed25519 public key (hex): {architect_pubkey_hex}")

    # 2a. Write architect_pubkey.pem (safe to commit; public material only)
    _write_architect_pubkey_pem(_ARCHITECT_KEY_PEM, _ARCHITECT_PUBKEY_PEM)
    print(f"Wrote architect public-key PEM: {_ARCHITECT_PUBKEY_PEM}")

    # 3. Resolve ts_ns
    ts_ns = args.ts_ns if args.ts_ns is not None else time.time_ns()
    print(f"Attestation ts_ns: {ts_ns}")

    # 4. Build canonical attestation envelope
    envelope = _build_attestation_envelope(architect_pubkey_hex, ts_ns)
    envelope_bytes = _canonical_json_bytes(envelope)
    envelope_hash = hashlib.sha256(envelope_bytes).hexdigest()
    print(f"Envelope canonical SHA-256: {envelope_hash}")

    # 5. Read bridge wallet private key (NEVER echoed)
    env_path = Path(_REPO) / "bridge" / ".env"
    bridge_private_key = _read_bridge_private_key_from_env_file(env_path)
    # Quick sanity check: must look like 0x-prefixed hex (66 chars) or raw 64 hex
    if not (
        (bridge_private_key.startswith("0x") and len(bridge_private_key) == 66)
        or (not bridge_private_key.startswith("0x") and len(bridge_private_key) == 64)
    ):
        raise ValueError(
            f"BRIDGE_PRIVATE_KEY does not look like a secp256k1 private key "
            f"(unexpected length {len(bridge_private_key)})"
        )

    # 6. Sign envelope via EIP-191 (encode_defunct + sign_message)
    account = Account.from_key(bridge_private_key)
    if account.address.lower() != _EXPECTED_BRIDGE_WALLET.lower():
        raise RuntimeError(
            f"BRIDGE_PRIVATE_KEY does not match expected bridge wallet. "
            f"Expected {_EXPECTED_BRIDGE_WALLET}, got {account.address}."
        )
    message = encode_defunct(primitive=envelope_bytes)
    signed = account.sign_message(message)
    signature_hex = signed.signature.hex()
    if not signature_hex.startswith("0x"):
        signature_hex = "0x" + signature_hex
    print(f"Signature: {signature_hex}")

    # 7. Verify signature recovers expected bridge wallet
    recovered = Account.recover_message(message, signature=signed.signature)
    if recovered.lower() != _EXPECTED_BRIDGE_WALLET.lower():
        raise RuntimeError(
            f"Signature verification failed; recovered {recovered}, "
            f"expected {_EXPECTED_BRIDGE_WALLET}"
        )
    print(f"Signature verified; recovered address: {recovered}")

    # 8. Compose attestation JSON (envelope + signature + verification metadata)
    attestation = {
        "schema_version":          "vsd-architect-key-anchor-v1",
        "envelope":                envelope,
        "envelope_canonical_hash": envelope_hash,
        "signature":               signature_hex,
        "signing_method":          "EIP-191 (eth_account.Account.sign_message)",
        "recovered_address":       recovered,
        "verification_status":     "PASS",
    }
    attestation_bytes = _canonical_json_bytes(attestation)
    _ATTESTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ATTESTATION_PATH.write_bytes(attestation_bytes)
    attestation_hash = hashlib.sha256(attestation_bytes).hexdigest()
    print(f"Wrote attestation: {_ATTESTATION_PATH}")
    print(f"Attestation canonical SHA-256: {attestation_hash}")
    print()
    print("=== Step 4 COMPLETE ===")
    print(f"  Architect pubkey hex:  {architect_pubkey_hex}")
    print(f"  Bridge wallet:         {recovered}")
    print(f"  Envelope hash:         {envelope_hash}")
    print(f"  Attestation hash:      {attestation_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
