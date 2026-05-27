"""Path A Arc 1 Commit 3 — provision a device birth certificate + register on
VAPIManufacturerDeviceRegistry.

Manufacturing ceremony script. Three modes:

  --dry-run         Pure-local cert creation + sign + persist. NO chain calls.
                    Use this to verify the cert format end-to-end without an
                    RPC connection.
  (no flag)         ESTIMATE-ONLY against the live RPC. Builds the cert, computes
                    the birthCertHash, calls estimate_gas against registerDevice
                    to surface the cost. NO broadcast.
  --execute         Broadcasts the registerDevice tx. Still requires
                    MFG_REGISTER_CONFIRM=1 env var as a second gate (matches the
                    scripts/provision_composite_device_key.py discipline).

Device-source flag (D-3D):
  --device-source host    (Arc 1 default) — pulls the device's EC pubkey from
                          ~/.vapi/device_composite_mldsa44.json (the composite
                          host key, EC half).
  --device-source atecc   (Arc 2) — RESERVED. Will route through the existing
                          hardware_identity.ATECC608IdentityBackend once Arc 2
                          activates. Raises NotImplementedError until then.

Honest framing:
  - The ManufacturerRootCA used here is the QorTroller Foundation SELF-SIGNED
    reference-implementation root CA at ~/.vapi/qortroller_foundation_mfg_ca.json
    (auto-generated on first run via SoftwareIdentityBackend). Production
    partner manufacturers MUST replace this with a hardware-HSM-rooted P-256 key.
  - The on-chain register call uses the BRIDGE WALLET (onlyOwner of the
    deployed VAPIManufacturerDeviceRegistry contract per Arc 1 reference deploy).
    Partner deploys redeploy the registry with their HSM wallet as initialOwner.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "contracts" / ".env")

from vapi_bridge.device_birth_cert import (
    CERT_VERSION, DeviceBirthCertificate, sign_cert, compute_cert_hash, cert_to_json,
)
from vapi_bridge.manufacturer_root_ca import (
    DEFAULT_ROOT_CA_KEY_PATH, ManufacturerRootCA, QORTROLLER_FOUNDATION_MFG_ID,
)

# ─── Constants ───────────────────────────────────────────────────────────────

HARD_CAP_IOTX = 0.5     # registerDevice is a small call (~0.05-0.1 expected)
GAS_BUFFER = 1.25       # IoTeX recoverable-gas convention
DEFAULT_CERT_PATH = str(Path.home() / ".vapi" / "device_birth_cert.json")
DEFAULT_COMPOSITE_KEY_PATH = str(Path.home() / ".vapi" / "device_composite_mldsa44.json")

# Proof tier → controller model registry. Keep in sync with the Arc 1 brief.
KNOWN_MODELS = {
    "CFI-ZCP1": "FULL",       # Sony DualSense Edge (Path A reference target)
    "CFI-ZCT1": "STANDARD",   # Sony DualSense (limited adaptive triggers)
}

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_bytes32(hexstr: str) -> bytes:
    """Accept 64-hex or 0x-prefixed 64-hex; return 32 bytes."""
    s = hexstr[2:] if hexstr.startswith("0x") else hexstr
    if len(s) != 64:
        raise ValueError(f"expected 32-byte (64-hex) string, got {len(s)} hex chars")
    return bytes.fromhex(s)


def _compress_p256_pubkey(uncompressed_65: bytes) -> bytes:
    """SEC1 0x04 || X || Y → SEC1 0x02/0x03 || X (33 bytes)."""
    if len(uncompressed_65) != 65 or uncompressed_65[0] != 0x04:
        raise ValueError(
            f"expected 65-byte uncompressed SEC1 (0x04||X||Y), "
            f"got len={len(uncompressed_65)} prefix=0x{uncompressed_65[0]:02x}"
        )
    x = uncompressed_65[1:33]
    y = uncompressed_65[33:65]
    prefix = b"\x02" if (y[-1] & 1) == 0 else b"\x03"
    return prefix + x


def _load_device_pubkey_host(composite_key_path: str) -> bytes:
    """Pull the device's ECDSA-P256 compressed pubkey from the composite host
    key file (Arc 1 Path B reference device source). Returns 33 bytes."""
    from cryptography.hazmat.primitives.serialization import (
        load_der_private_key, Encoding, PublicFormat,
    )
    p = Path(composite_key_path)
    if not p.exists():
        raise FileNotFoundError(
            f"composite host key not found: {p}\n"
            f"Run scripts/provision_composite_device_key.py first to provision it."
        )
    data = json.loads(p.read_text())
    priv_der = bytes.fromhex(data["ec_private_der_hex"])
    priv = load_der_private_key(priv_der, password=None)
    pub_uncompressed = priv.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint
    )
    return _compress_p256_pubkey(pub_uncompressed)


def _load_device_pubkey_atecc() -> bytes:
    """Arc 2 — RESERVED. Will route via hardware_identity.ATECC608IdentityBackend."""
    raise NotImplementedError(
        "--device-source atecc is reserved for Path A Arc 2 (real ATECC608A "
        "hardware via hardware_identity.ATECC608IdentityBackend). Use "
        "--device-source host for Arc 1 reference-implementation provisioning."
    )


def _controller_model_keccak(model: str) -> bytes:
    """keccak256(utf8(model)) — matches the on-chain controllerModel field type."""
    try:
        from eth_utils import keccak
        return keccak(text=model)
    except ImportError:
        from Crypto.Hash import keccak as _k
        h = _k.new(digest_bits=256)
        h.update(model.encode("utf-8"))
        return h.digest()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Provision a DeviceBirthCertificate "
                                             "and register on VAPIManufacturerDeviceRegistry.")
    ap.add_argument("--device-id", required=True,
                    help="32-byte device id (hex, optionally 0x-prefixed)")
    ap.add_argument("--controller-model", required=True, choices=list(KNOWN_MODELS) + ["BASIC"],
                    help="Controller model (e.g. CFI-ZCP1). BASIC = generic / third-party.")
    ap.add_argument("--device-source", choices=["host", "atecc"], default="host",
                    help="Where to pull the device's ECDSA-P256 pubkey from. "
                         "host = composite host key (~/.vapi/device_composite_mldsa44.json; "
                         "Arc 1). atecc = ATECC608A silicon (Arc 2 RESERVED).")
    ap.add_argument("--signing-path", choices=["A", "B"], default="B",
                    help="A = silicon-rooted (Arc 2). B = host-held JSON key (Arc 1).")
    ap.add_argument("--proof-tier", choices=["FULL", "STANDARD", "BASIC"],
                    default=None,
                    help="Defaults from --controller-model: CFI-ZCP1=FULL / "
                         "CFI-ZCT1=STANDARD / BASIC=BASIC.")
    ap.add_argument("--composite-key-path", default=DEFAULT_COMPOSITE_KEY_PATH,
                    help="Path to the device composite host key (--device-source host).")
    ap.add_argument("--root-ca-key-path", default=DEFAULT_ROOT_CA_KEY_PATH,
                    help="Path to the ManufacturerRootCA key file (auto-generated on first run).")
    ap.add_argument("--manufacturer-id", default=QORTROLLER_FOUNDATION_MFG_ID,
                    help="Issuer identifier embedded in the cert.")
    ap.add_argument("--cert-out", default=DEFAULT_CERT_PATH,
                    help="Where to persist the signed cert JSON.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Pure-local cert creation + sign + persist. NO chain calls.")
    ap.add_argument("--execute", action="store_true",
                    help="Broadcast the registerDevice tx (also requires "
                         "MFG_REGISTER_CONFIRM=1 env var).")
    args = ap.parse_args()

    if args.execute and args.dry_run:
        print("ERROR: --execute and --dry-run are mutually exclusive", file=sys.stderr)
        sys.exit(2)

    proof_tier = args.proof_tier or KNOWN_MODELS.get(args.controller_model, "BASIC")
    device_id_bytes = _to_bytes32(args.device_id)
    print(f"[CEREMONY] Path A Arc 1 — DeviceBirthCertificate provisioning")
    print(f"  device_id        : 0x{device_id_bytes.hex()}")
    print(f"  controller_model : {args.controller_model}")
    print(f"  signing_path     : {args.signing_path}")
    print(f"  proof_tier       : {proof_tier}")
    print(f"  device_source    : {args.device_source}")

    # 1. Pull device pubkey (compressed 33B)
    if args.device_source == "host":
        device_pubkey = _load_device_pubkey_host(args.composite_key_path)
    else:
        device_pubkey = _load_device_pubkey_atecc()
    pubkey_hash = hashlib.sha256(device_pubkey).digest()
    print(f"  device_pubkey    : {device_pubkey.hex()}")
    print(f"  pubkeyHash       : 0x{pubkey_hash.hex()}")

    # 2. Load / generate the ManufacturerRootCA
    root_ca = ManufacturerRootCA(key_path=args.root_ca_key_path,
                                  manufacturer_id=args.manufacturer_id)
    issuer_pubkey_hex = root_ca.issuer_pubkey_hex()
    print(f"  issuer_pubkey    : {issuer_pubkey_hex[:32]}... ({len(issuer_pubkey_hex)//2}B)")
    print(f"  issuer_backend   : {root_ca.backend_type()}")

    # 3. Build the unsigned cert
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    cert = DeviceBirthCertificate(
        version=CERT_VERSION,
        device_id_hex=device_id_bytes.hex(),
        ecdsa_p256_pubkey_hex=device_pubkey.hex(),
        controller_model=args.controller_model,
        manufacturer_id=root_ca.manufacturer_id(),
        manufacturing_date=now_iso,
        signing_path=args.signing_path,
        proof_tier=proof_tier,
        issuer_pubkey_hex=issuer_pubkey_hex,
        atecc_chip_id=None,  # Arc 1 Path B has no ATECC chip
        issuer_backend=root_ca.backend_type(),
    )

    # 4. Sign + compute birthCertHash
    sign_cert(cert, root_ca)
    cert_hash = compute_cert_hash(cert)
    print(f"  cert signed      : sig={cert.signature_hex[:32]}... ({len(cert.signature_hex)//2}B raw r||s)")
    print(f"  birthCertHash    : 0x{cert_hash.hex()}")

    # 5. Persist cert to disk
    cert_path = Path(args.cert_out)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    cert_path.write_text(cert_to_json(cert))
    print(f"  cert persisted   : {cert_path}")

    if args.dry_run:
        print("\n[DRY-RUN] No chain calls. Cert created and persisted. Done.")
        return

    # 6. Chain operations: estimate-only (default) or broadcast (--execute)
    controller_model_b32 = _controller_model_keccak(args.controller_model)
    signing_path_uint = 1 if args.signing_path == "A" else 2
    proof_tier_uint = {"FULL": 1, "STANDARD": 2, "BASIC": 3}[proof_tier]
    print(f"\n  controllerModel  : 0x{controller_model_b32.hex()}")
    print(f"  signingPath uint : {signing_path_uint}")
    print(f"  proofTier uint   : {proof_tier_uint}")

    from web3 import Web3
    from eth_account import Account
    from vapi_bridge.chain import _VAPI_MANUFACTURER_DEVICE_REGISTRY_ABI as _BRIDGE_READ_ABI
    # NOTE: bridge's ABI is read-only (no writers). For ceremony writes we need the
    # registerDevice ABI; declare it locally so we don't grant the bridge ABI write
    # power by mistake (least-privilege separation, V-N5 finding).
    REGISTER_DEVICE_ABI = [
        {"name": "registerDevice", "type": "function", "stateMutability": "nonpayable",
         "inputs": [
             {"name": "deviceId",        "type": "bytes32"},
             {"name": "pubkeyHash",      "type": "bytes32"},
             {"name": "controllerModel", "type": "bytes32"},
             {"name": "signingPath",     "type": "uint8"},
             {"name": "proofTier",       "type": "uint8"},
             {"name": "birthCertHash",   "type": "bytes32"},
         ],
         "outputs": []},
    ]

    rpc_url = os.getenv("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
    registry_addr = os.getenv("MANUFACTURER_DEVICE_REGISTRY_ADDRESS", "")
    if not registry_addr:
        print("ERROR: MANUFACTURER_DEVICE_REGISTRY_ADDRESS not set in env", file=sys.stderr)
        sys.exit(2)
    private_key = os.getenv("BRIDGE_PRIVATE_KEY", "")
    if not private_key:
        print("ERROR: BRIDGE_PRIVATE_KEY not set in env", file=sys.stderr)
        sys.exit(2)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = Account.from_key(private_key)
    print(f"  rpc              : {rpc_url}")
    print(f"  registry         : {registry_addr}")
    print(f"  caller           : {account.address}")
    bal_wei = w3.eth.get_balance(account.address)
    print(f"  balance          : {w3.from_wei(bal_wei, 'ether')} IOTX")

    contract = w3.eth.contract(
        address=w3.to_checksum_address(registry_addr),
        abi=REGISTER_DEVICE_ABI + _BRIDGE_READ_ABI,  # combined for sanity reads
    )

    # estimate gas
    fn = contract.functions.registerDevice(
        device_id_bytes, pubkey_hash, controller_model_b32,
        signing_path_uint, proof_tier_uint, cert_hash,
    )
    est_gas = fn.estimate_gas({"from": account.address})
    gas_price = w3.eth.gas_price
    buffered_gas = (est_gas * int(GAS_BUFFER * 100)) // 100
    est_cost_wei = est_gas * gas_price
    buf_cost_wei = buffered_gas * gas_price
    print("\n--- GAS ESTIMATE ---")
    print(f"  estimate_gas     : {est_gas}")
    print(f"  buffered (x{GAS_BUFFER}) : {buffered_gas}")
    print(f"  gasPrice (wei)   : {gas_price}")
    print(f"  est cost         : {w3.from_wei(est_cost_wei, 'ether')} IOTX")
    print(f"  buffered cost    : {w3.from_wei(buf_cost_wei, 'ether')} IOTX")
    print(f"  hard-cap         : {HARD_CAP_IOTX} IOTX")
    buf_cost_iotx = float(w3.from_wei(buf_cost_wei, 'ether'))
    if buf_cost_iotx > HARD_CAP_IOTX:
        print(f"\n[HARD-CAP EXCEEDED] buffered cost {buf_cost_iotx} > {HARD_CAP_IOTX} — ABORT.")
        sys.exit(2)
    print("  hard-cap check   : PASS")

    if not args.execute:
        print("\n[ESTIMATE-ONLY] --execute not set. NOT broadcasting.")
        print("Re-run with --execute MFG_REGISTER_CONFIRM=1 to broadcast.")
        return

    if os.getenv("MFG_REGISTER_CONFIRM", "") != "1":
        print("\nERROR: --execute requires MFG_REGISTER_CONFIRM=1 env var.", file=sys.stderr)
        sys.exit(2)

    # Broadcast
    print("\n[BROADCASTING] MFG_REGISTER_CONFIRM=1 + --execute — sending tx...")
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": buffered_gas,
        "gasPrice": gas_price,
        "chainId": 4690,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  tx hash          : 0x{tx_hash.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print("  block            :", rcpt.blockNumber)
    print("  gas used         :", rcpt.gasUsed)
    print("  status           :", rcpt.status, "(success)" if rcpt.status == 1 else "(FAILED)")

    # Persist tx hash into the cert metadata
    cert_meta = json.loads(cert_path.read_text())
    cert_meta["_registered_tx_hash"] = "0x" + tx_hash.hex()
    cert_meta["_registered_block"] = rcpt.blockNumber
    cert_meta["_registered_at_iso"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    cert_path.write_text(json.dumps(cert_meta, indent=2))
    print(f"  cert updated     : {cert_path} (registration metadata appended)")

    print("\n[DONE] Ceremony complete. Run scripts/verify_device_cert.py to audit.")


if __name__ == "__main__":
    main()
