"""Path A Arc 1 Commit 3 — DeviceBirthCertificate audit tool.

Read-only verifier. The tool a tournament operator runs to confirm a device
the gamer is using actually matches an on-chain manufacturer attestation.

  $ python scripts/verify_device_cert.py
  $ python scripts/verify_device_cert.py --cert-path /custom/path.json

Three checks (all must pass for VALID):

  1. cert ECDSA-P256 sig verifies against its claimed issuer_pubkey_hex
  2. SHA-256(canonical_bytes_full) matches the on-chain birthCertHash
     (chain-anchored cert integrity)
  3. VAPIManufacturerDeviceRegistry.isActive(deviceId) is TRUE on-chain
     (device has not been revoked)

Exit codes:
  0 = VALID            (all 3 checks pass)
  1 = INVALID          (sig fails, hash mismatch, or revoked)
  2 = NOT_REGISTERED   (cert exists but no on-chain record)
  3 = ERROR            (env / file / RPC failure — operator action required)

Pure-local mode (no chain calls):
  --offline            Skip the on-chain checks. Only cert sig + format checks.
                       Returns VALID-OFFLINE / INVALID-OFFLINE.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from vapi_bridge.device_birth_cert import (
    cert_from_json, compute_cert_hash, verify_cert,
)

DEFAULT_CERT_PATH = str(Path.home() / ".vapi" / "device_birth_cert.json")


def main():
    ap = argparse.ArgumentParser(description="Audit a DeviceBirthCertificate "
                                             "against VAPIManufacturerDeviceRegistry.")
    ap.add_argument("--cert-path", default=DEFAULT_CERT_PATH,
                    help="Path to the signed cert JSON.")
    ap.add_argument("--offline", action="store_true",
                    help="Skip on-chain checks. Cert-format + sig only.")
    args = ap.parse_args()

    cert_path = Path(args.cert_path)
    if not cert_path.exists():
        print(f"ERROR: cert file not found: {cert_path}", file=sys.stderr)
        sys.exit(3)

    print(f"[AUDIT] {cert_path}")
    try:
        cert = cert_from_json(cert_path.read_text())
    except (KeyError, ValueError) as exc:
        print(f"ERROR: cert deserialize failed: {exc}", file=sys.stderr)
        sys.exit(3)

    # ── Check 1: cert sig ────────────────────────────────────────────────────
    sig_ok, sig_reason = verify_cert(cert)
    print(f"  cert sig         : {'OK' if sig_ok else 'FAIL — ' + sig_reason}")
    if not sig_ok:
        print(f"\nVERDICT: INVALID  ({sig_reason})")
        sys.exit(1)

    # Cert details for the operator
    print(f"  device_id        : 0x{cert.device_id_hex}")
    print(f"  controller_model : {cert.controller_model}")
    print(f"  signing_path     : {cert.signing_path}")
    print(f"  proof_tier       : {cert.proof_tier}")
    print(f"  manufacturer     : {cert.manufacturer_id}")
    print(f"  manufactured     : {cert.manufacturing_date}")
    print(f"  issuer_backend   : {cert.issuer_backend or 'unset'}")
    if cert.atecc_chip_id:
        print(f"  atecc_chip_id    : {cert.atecc_chip_id}")

    expected_hash = compute_cert_hash(cert)
    print(f"  expected on-chain birthCertHash: 0x{expected_hash.hex()}")

    if args.offline:
        print("\nVERDICT: VALID-OFFLINE  (cert sig OK; on-chain checks skipped)")
        sys.exit(0)

    # ── Checks 2 + 3: on-chain ───────────────────────────────────────────────
    rpc_url = os.getenv("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
    registry_addr = os.getenv("MANUFACTURER_DEVICE_REGISTRY_ADDRESS", "")
    if not registry_addr:
        print("ERROR: MANUFACTURER_DEVICE_REGISTRY_ADDRESS not set in env "
              "(use --offline to skip).", file=sys.stderr)
        sys.exit(3)

    from web3 import Web3
    # We want the FULL ABI (including the auto-mapping getter for the public
    # `devices` mapping which gives us birthCertHash). The bridge's read-only
    # ABI doesn't include `devices(bytes32)`, so we declare a minimal local ABI
    # for the audit.
    AUDIT_ABI = [
        {"name": "isActive", "type": "function", "stateMutability": "view",
         "inputs": [{"name": "deviceId", "type": "bytes32"}],
         "outputs": [{"type": "bool"}]},
        {"name": "registered", "type": "function", "stateMutability": "view",
         "inputs": [{"name": "deviceId", "type": "bytes32"}],
         "outputs": [{"type": "bool"}]},
        # Public mapping getter: returns the DeviceRegistration tuple in
        # declaration order (pubkeyHash, controllerModel, signingPath,
        # proofTier, registeredAt, birthCertHash, manufacturerWallet, active).
        {"name": "devices", "type": "function", "stateMutability": "view",
         "inputs": [{"name": "", "type": "bytes32"}],
         "outputs": [
             {"type": "bytes32"}, {"type": "bytes32"}, {"type": "uint8"},
             {"type": "uint8"}, {"type": "uint64"}, {"type": "bytes32"},
             {"type": "address"}, {"type": "bool"},
         ]},
    ]

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        contract = w3.eth.contract(
            address=w3.to_checksum_address(registry_addr), abi=AUDIT_ABI,
        )
        device_id_bytes = bytes.fromhex(cert.device_id_hex)
        registered_flag = contract.functions.registered(device_id_bytes).call()
        if not registered_flag:
            print("  on-chain         : NOT REGISTERED")
            print("\nVERDICT: NOT_REGISTERED  (cert sig OK, but no on-chain attestation)")
            sys.exit(2)
        active = contract.functions.isActive(device_id_bytes).call()
        record = contract.functions.devices(device_id_bytes).call()
        on_chain_birth_cert_hash = bytes(record[5])
    except Exception as exc:  # noqa: BLE001 — surface for operator
        print(f"ERROR: on-chain read failed: {exc}", file=sys.stderr)
        sys.exit(3)

    print(f"  on-chain         : registered={registered_flag} active={active}")
    print(f"  on-chain hash    : 0x{on_chain_birth_cert_hash.hex()}")

    if on_chain_birth_cert_hash != expected_hash:
        print(f"\nVERDICT: INVALID  (birthCertHash mismatch — cert content "
              f"differs from what was attested on-chain)")
        sys.exit(1)

    if not active:
        print(f"\nVERDICT: INVALID  (device revoked on-chain — registered but isActive=False)")
        sys.exit(1)

    print("\nVERDICT: VALID  (cert sig OK + on-chain hash match + active)")
    sys.exit(0)


if __name__ == "__main__":
    main()
