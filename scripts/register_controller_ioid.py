#!/usr/bin/env python3
"""Gamer-fired CLI for registering a QorTroller controller to canonical ioID + ERC-6551 TBA.

D-CONTROLLER-IOID-1 / D-IOID-P256 front-loaded (see controller_ioid_registration.py).
Phase 2 software surface; on-chain reg gated pending 1B silicon.

Usage examples:
  python scripts/register_controller_ioid.py --device-id 581a83... --pubkey-hex 04... --gamer 0x... --dry-run
  python scripts/register_controller_ioid.py ... --confirm   # after prerequisites

Prerequisites (one-time operator):
  1. ProjectRegistry.register("QorTroller Controllers", ...)
  2. Deploy VAPIGamerControllerNFT
  3. ioIDStore.setDeviceContract(projectId, nft)
  4. (opt) applyIoIDs

The gamer signs the permit (secp256k1). Bridge orchestrates pinning + tx assembly (read-only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure bridge importable when run from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from vapi_bridge.controller_ioid_registration import register_controller_ioid
from web3 import Web3


def _fetch_vmdr_pubkey_hash(w3: Web3, device_id_hex: str) -> str | None:
    """Fetch devices[deviceId].pubkeyHash from VMDR (mint/verify split, A2A round-27 F2).

    Returns the hex hash for a REGISTERED device, None when the device is not
    registered or MANUFACTURER_DEVICE_REGISTRY_ADDRESS is unset (canon
    best-effort applies). Registry configured but unreadable → SystemExit 3
    fail-closed (never silently downgrade to canon for a configured registry).
    The evidence is RPC-fetched HERE — never accepted from the command line
    (a self-derived hash would be circular; round-27 F1).
    """
    registry_addr = os.environ.get("MANUFACTURER_DEVICE_REGISTRY_ADDRESS", "").strip()
    if not registry_addr:
        return None
    VMDR_READ_ABI = [
        {"name": "registered", "type": "function", "stateMutability": "view",
         "inputs": [{"name": "deviceId", "type": "bytes32"}],
         "outputs": [{"type": "bool"}]},
        {"name": "devices", "type": "function", "stateMutability": "view",
         "inputs": [{"name": "", "type": "bytes32"}],
         "outputs": [
             {"type": "bytes32"}, {"type": "bytes32"}, {"type": "uint8"},
             {"type": "uint8"}, {"type": "uint64"}, {"type": "bytes32"},
             {"type": "address"}, {"type": "bool"},
         ]},
    ]
    try:
        vmdr = w3.eth.contract(
            address=w3.to_checksum_address(registry_addr), abi=VMDR_READ_ABI)
        device_id_bytes = bytes.fromhex(device_id_hex.removeprefix("0x"))
        if not vmdr.functions.registered(device_id_bytes).call():
            return None
        record = vmdr.functions.devices(device_id_bytes).call()
        return bytes(record[0]).hex()
    except Exception as exc:  # noqa: BLE001 — fail-CLOSED when the registry is configured
        print(f"ERROR: MANUFACTURER_DEVICE_REGISTRY_ADDRESS is set but the VMDR "
              f"read failed ({exc}). Refusing to fall back to canon for a "
              f"configured registry — fix RPC/address or unset the env.",
              file=sys.stderr)
        sys.exit(3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device-id", required=True,
                    help="32B device_id hex. New (unregistered) devices must match "
                         "canon keccak256(pubkey); a VMDR-REGISTERED device is bound "
                         "by its on-chain pubkeyHash instead (fetched automatically "
                         "when MANUFACTURER_DEVICE_REGISTRY_ADDRESS is set).")
    ap.add_argument("--pubkey-hex", required=True, help="65B or 33B hex of the controller P256 pubkey")
    ap.add_argument("--gamer", required=True, help="Gamer EOA that will own the TBA and sign the permit")
    ap.add_argument("--gamer-key", default=None, help="Private key for signing (ONLY for --confirm; never commit)")
    ap.add_argument("--birth-cert-cid", default=None)
    ap.add_argument("--mfg-tx", default=None)
    ap.add_argument("--project-id", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", action="store_true", help="Actually broadcast (requires env + gamer key)")
    args = ap.parse_args()

    if args.confirm and not args.gamer_key:
        print("ERROR: --confirm requires --gamer-key (or GAMER_PRIVATE_KEY env)", file=sys.stderr)
        sys.exit(2)

    w3 = Web3(Web3.HTTPProvider(os.environ.get("IOTEX_RPC", "https://babel-api.testnet.iotex.io")))

    # In a full impl pinata_client would be a real client; here we use a tiny stub for skeleton.
    class _StubPinata:
        def pin_json(self, doc, name=None):
            # Deterministic fake CID for dry runs / tests
            h = Web3.keccak(text=json.dumps(doc, sort_keys=True))
            return "bafy" + h.hex()[:50]

    pinata = _StubPinata()

    key = args.gamer_key or os.environ.get("GAMER_PRIVATE_KEY")
    dry = args.dry_run or not args.confirm

    # Mint/verify split (round-27 F2): a registered device is bound by its VMDR
    # pubkeyHash; the evidence is RPC-fetched here, never taken from the CLI.
    on_chain_pubkey_hash = _fetch_vmdr_pubkey_hash(w3, args.device_id)
    if on_chain_pubkey_hash:
        print(f"binding: CHAIN (VMDR pubkeyHash 0x{on_chain_pubkey_hash[:16]}...)")
    else:
        print("binding: CANON best-effort (device not registered on VMDR, or "
              "MANUFACTURER_DEVICE_REGISTRY_ADDRESS unset)")

    res = register_controller_ioid(
        web3=w3,
        device_id_hex=args.device_id,
        p256_pubkey_hex=args.pubkey_hex,
        gamer_address=args.gamer,
        gamer_private_key=key,
        birth_cert_cid=args.birth_cert_cid,
        mfg_registry_tx=args.mfg_tx,
        pinata_client=pinata,
        project_id=args.project_id,
        dry_run=dry,
        on_chain_pubkey_hash_hex=on_chain_pubkey_hash,
    )

    print(json.dumps({
        "device_id": res.device_id,
        "ioid_token_id": res.ioid_token_id,
        "tba": res.tba_address,
        "did_cid": res.did_cid,
        "tx": res.tx_hash,
        "dry_run": res.dry_run,
    }, indent=2))

    if res.dry_run:
        print("\nDRY RUN — re-run with --confirm (and gamer key) to broadcast.")
    else:
        print("\nSubmitted. Verify on explorer and read TBA owner == gamer.")


if __name__ == "__main__":
    main()
