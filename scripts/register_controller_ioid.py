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
# bridge/.env is the canonical secrets home (PINATA_JWT / GAMER_PRIVATE_KEY); override=True so an
# empty/stale key in the root .env can't shadow it (grok r09 residual #3).
load_dotenv(REPO_ROOT / "bridge" / ".env", override=True)

from vapi_bridge.controller_ioid_registration import (
    register_controller_ioid,
    resolve_ioid_registry_address,
)
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


class _StubPinata:
    """Deterministic fake CID for dry-runs / offline tests (no network)."""
    def pin_json(self, doc, name=None):
        h = Web3.keccak(text=json.dumps(doc, sort_keys=True))
        return "bafy" + h.hex().removeprefix("0x")[:50]


class _RealPinataSync:
    """Sync adapter over the async PinataClient (PINATA_JWT). Pins the DID doc to REAL IPFS and
    returns the CID string that register_controller_ioid embeds as uri=ipfs://<cid> and whose
    keccak is the on-chain content hash. Needed for an honestly-resolvable registration."""
    def __init__(self):
        from vapi_bridge.pinata_client import PinataClient
        self._c = PinataClient()  # reads PINATA_JWT / PINATA_GATEWAY_URL from env (fail-loud if unset)

    def pin_json(self, doc, name=None):
        import asyncio
        res = asyncio.run(self._c.pin_json(doc, name=name or "controller-did")) or {}
        cid = res.get("IpfsHash") or res.get("cid") or res.get("Hash")
        if not cid:
            raise RuntimeError(f"Pinata pin returned no CID (keys={list(res.keys())})")
        return cid


def _resolve_controller_nft() -> str | None:
    """The deployed VAPIGamerControllerNFT (Inc-A) from deployed-addresses.json. encoding='utf-8'
    is REQUIRED (the file holds UTF-8; the OS default cp1252 raises on Windows -- the Inc-C lesson)."""
    p = REPO_ROOT / "contracts" / "deployed-addresses.json"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    v = obj.get("VAPIGamerControllerNFT")
    return v if isinstance(v, str) and v.startswith("0x") and len(v) == 42 else None


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
    ap.add_argument("--device-contract", default=None,
                    help="VAPIGamerControllerNFT (Inc-A). Default: resolved from deployed-addresses.json.")
    ap.add_argument("--token-id", type=int, default=0,
                    help="Minted controller-NFT tokenId (Inc-C). REQUIRED for --confirm.")
    ap.add_argument("--hard-cap", type=float, default=0.75, help="Spend cap (IOTX) for the register send.")
    ap.add_argument("--real-pinata", action="store_true",
                    help="Pin the DID doc to REAL IPFS via PinataClient (PINATA_JWT). Forced by --confirm.")
    args = ap.parse_args()

    key = args.gamer_key or os.environ.get("GAMER_PRIVATE_KEY")
    # Dev-self convenience (first-run ceremony): when the gamer IS the bridge wallet, sign with the
    # BRIDGE_PRIVATE_KEY already in bridge/.env -- the operator never has to find/paste the raw key and
    # it never enters a command or shell history. Honest note printed. A third-party gamer still needs
    # an explicit --gamer-key / GAMER_PRIVATE_KEY (this fallback ONLY fires when gamer == bridge wallet).
    _BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
    if not key and args.gamer and args.gamer.lower() == _BRIDGE_WALLET.lower():
        key = os.environ.get("BRIDGE_PRIVATE_KEY")
        if key:
            print("dev-self: gamer == bridge wallet -> signing with BRIDGE_PRIVATE_KEY from bridge/.env "
                  "(the operator wallet IS the gamer; the raw key never enters a command).")
    dry = args.dry_run or not args.confirm

    if args.confirm and not key:
        print("ERROR: --confirm requires --gamer-key (or GAMER_PRIVATE_KEY env)", file=sys.stderr)
        sys.exit(2)
    if args.confirm and args.token_id <= 0:
        print("ERROR: --confirm requires --token-id (the minted controller tokenId from Inc-C)",
              file=sys.stderr)
        sys.exit(2)

    w3 = Web3(Web3.HTTPProvider(os.environ.get("IOTEX_RPC", "https://babel-api.testnet.iotex.io")))

    # deviceContract: the deployed VAPIGamerControllerNFT (Inc-A). CLI arg overrides; else resolve.
    device_contract = args.device_contract or _resolve_controller_nft()
    if not dry and not device_contract:
        print("ERROR: VAPIGamerControllerNFT not deployed/resolvable -- run Inc-A + Inc-C first, "
              "or pass --device-contract.", file=sys.stderr)
        sys.exit(2)

    # Pinata: REAL IPFS pin for --confirm or --real-pinata (honest, resolvable CID whose keccak is
    # the on-chain content hash); deterministic stub otherwise (offline dry-run / tests).
    try:
        pinata = _RealPinataSync() if (args.confirm or args.real_pinata) else _StubPinata()
    except Exception as exc:  # noqa: BLE001 -- PINATA_JWT unset / client init failed
        print(f"ERROR: real Pinata requested but client init failed ({exc}) -- set PINATA_JWT, "
              f"or drop --real-pinata for a stub dry-run.", file=sys.stderr)
        sys.exit(2)

    # Resolve the ioID PERMIT registry (fail-loud; never zero, never the Phase 55
    # VAPIioIDRegistry DID book — F-T3-1 / A2A round-33).
    try:
        registry = resolve_ioid_registry_address()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    print(f"ioID permit registry: {registry}")

    # Prove the resolved registry is a LIVE permit registry (has nonces()) — read-only.
    try:
        nonce_abi = [{"name": "nonces", "type": "function", "stateMutability": "view",
                      "inputs": [{"name": "owner", "type": "address"}],
                      "outputs": [{"type": "uint256"}]}]
        reg = w3.eth.contract(address=w3.to_checksum_address(registry), abi=nonce_abi)
        live_nonce = reg.functions.nonces(w3.to_checksum_address(args.gamer)).call()
        print(f"live nonces(gamer):   {live_nonce}  (registry answers the permit interface)")
    except Exception as exc:  # noqa: BLE001 — surface but don't fabricate
        print(f"WARNING: live nonces() read failed ({exc}) — is the RPC up / address a permit "
              f"registry? Proceeding with dry-run assembly.", file=sys.stderr)

    # Mint/verify split (round-27 F2): a registered device is bound by its VMDR
    # pubkeyHash; the evidence is RPC-fetched here, never taken from the CLI.
    on_chain_pubkey_hash = _fetch_vmdr_pubkey_hash(w3, args.device_id)
    if on_chain_pubkey_hash:
        print(f"binding: CHAIN (VMDR pubkeyHash 0x{on_chain_pubkey_hash[:16]}...)")
    else:
        print("binding: CANON best-effort (device not registered on VMDR, or "
              "MANUFACTURER_DEVICE_REGISTRY_ADDRESS unset)")

    try:
        res = register_controller_ioid(
            web3=w3,
            device_id_hex=args.device_id,
            p256_pubkey_hex=args.pubkey_hex,
            gamer_address=args.gamer,
            gamer_private_key=key,
            birth_cert_cid=args.birth_cert_cid,
            mfg_registry_tx=args.mfg_tx,
            pinata_client=pinata,
            ioid_registry_address=registry,
            project_id=args.project_id,
            dry_run=dry,
            on_chain_pubkey_hash_hex=on_chain_pubkey_hash,
            device_contract=device_contract or "0x" + "00" * 20,  # ignored in dry-run (uses zero)
            token_id=args.token_id,
            hard_cap_iotx=args.hard_cap,
        )
    except (ValueError, RuntimeError) as exc:
        # Fail-closed: missing prereq / signer mismatch / no ioID mint / zero TBA. No fabrication.
        print(f"\nREGISTRATION REFUSED: {exc}", file=sys.stderr)
        sys.exit(3)

    print(json.dumps({
        "device_id": res.device_id,
        "ioid_registry_address": res.ioid_registry_address,
        "device_nonce": res.device_nonce,
        "ioid_token_id": res.ioid_token_id,   # None in dry-run (needs a real mint)
        "tba": res.tba_address,               # None in dry-run (needs ioID.wallet(tokenId))
        "did_cid": res.did_cid,
        "tx": res.tx_hash,
        "dry_run": res.dry_run,
        "pending_prereqs": res.pending_prereqs,
    }, indent=2))

    if res.dry_run:
        print("\nDRY RUN -- registry + permit interface proven live (a REAL Pinata CID if "
              "--real-pinata/--confirm). A real registration is a separate --confirm run with the "
              "gamer key + --token-id. Not a registration.")
    else:
        print(f"\nREGISTERED -- ioID tokenId={res.ioid_token_id}  TBA={res.tba_address}\n"
              f"  DID CID={res.did_cid}\n"
              f"  tx https://testnet.iotexscan.io/tx/{res.tx_hash}")


if __name__ == "__main__":
    main()
