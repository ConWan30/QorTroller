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

from vapi_bridge.controller_ioid_registration import register_controller_ioid
from web3 import Web3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device-id", required=True, help="Canon 32B device_id hex (must match pubkey)")
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
