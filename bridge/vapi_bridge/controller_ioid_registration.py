"""Controller ioID + ERC-6551 TBA registration (Phase 2, Option A).

D-CONTROLLER-IOID-1 (Option A LOCKED): gamer wallet signs the EIP-712 permit;
bridge is read-only orchestrator — pins DID, assembles, never owns TBA.

D-IOID-P256 (standing external): ioID permit expects secp256k1; controller silicon is P-256;
Option C silicon permit blocked until IoTeX (parallel to IIP-64). 1B waits for silicon.

Gamer-signed permit flow. Bridge is read-only orchestrator:
- accepts gamer-signed EIP-712 permit (secp256k1 gamer wallet)
- pins DID document (containing canon device_id + birth cert ref + P256 pubkey)
- assembles ioIDRegistry.register (8-param form, internal TBA via ioID.wallet)
- returns ioID tokenId + TBA address

Binding to physical controller:
- device_id MUST be the canon keccak256(65B SEC1 pubkey) per DEVICE_ID_CANON_v1
- birth cert (on-chain via MFG registry) proves the P256 pubkey ownership at manufacture

Reuse of agent pattern (M1/M2/M4/M6/N2β/N4) without duplicating operator code.
Phase 2 software-only surface; on-chain registration gated on 1B (silicon).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

from eth_account import Account
# Manual EIP-712 (no eth_account encode_typed_data dependency for this simple Permit)
# Mirrors the proven construction in agent_registration.py (Section 14.3 / M2)
from eth_abi import encode as abi_encode
from eth_hash.auto import keccak
from eth_keys import keys
from web3 import Web3

from vapi_bridge.device_birth_cert import (
    compute_device_id_from_pubkey_hex,
    verify_device_id_matches_pubkey,
)

log = logging.getLogger(__name__)

# Canonical 8-param selector observed in agent path (wrapper calls internal 9-param with user=msg.sender)
IOID_REGISTER_SELECTOR = "0x39a4a241"

# Permit type (matches agent precedent: owner + nonce binding)
PERMIT_TYPE_HASH = keccak(b"Permit(address owner,uint256 nonce)")

# EIP712 domain constants (mirrors agent_registration for cross-verifiability)
EIP712_DOMAIN_NAME = "ioIDRegistry"
EIP712_DOMAIN_VERSION = "1"
EIP712_DOMAIN_TYPEHASH = keccak(
    b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)

# Placeholder addresses (resolved at runtime from env / chain config in integrate phase)
DEFAULT_IOID_REGISTRY = "0x0000000000000000000000000000000000000000"  # replace in live
DEFAULT_IOID = "0x0000000000000000000000000000000000000000"


@dataclass(slots=True)
class ControllerRegistrationResult:
    device_id: str
    ioid_token_id: int
    tba_address: str
    did_cid: str
    tx_hash: Optional[str]
    dry_run: bool


def _require_canon_device_id(device_id_hex: str, pubkey_hex: str) -> None:
    ok, reason = verify_device_id_matches_pubkey(device_id_hex, pubkey_hex)
    if not ok:
        raise ValueError(f"device_id does not match canon: {reason}")


def build_controller_did_document(
    *,
    device_id_hex: str,
    ecdsa_p256_pubkey_hex: str,
    birth_cert_cid: Optional[str] = None,
    mfg_registry_tx: Optional[str] = None,
    gamer_address: str,
) -> dict:
    """Minimal DID document for a gamer controller.

    The document asserts:
      - controller's canon device_id
      - the P256 public key from its birth cert
      - optional links to on-chain MFG birth cert + gamer owner
    """
    _require_canon_device_id(device_id_hex, ecdsa_p256_pubkey_hex)

    doc: dict = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": f"did:io:{device_id_hex}",
        "controller": [gamer_address],
        "verificationMethod": [
            {
                "id": f"did:io:{device_id_hex}#controller-key-1",
                "type": "EcdsaSecp256r1VerificationKey2019",
                "controller": f"did:io:{device_id_hex}",
                "publicKeyHex": ecdsa_p256_pubkey_hex,
            }
        ],
        "service": [
            {
                "id": f"did:io:{device_id_hex}#qortroller-controller",
                "type": "QorTrollerControllerService",
                "serviceEndpoint": "https://qortroller.example/controller",
            }
        ],
    }
    if birth_cert_cid:
        doc.setdefault("alsoKnownAs", []).append(f"ipfs://{birth_cert_cid}")
    if mfg_registry_tx:
        doc["proof"] = {"type": "MfgRegistryBinding", "tx": mfg_registry_tx}
    return doc


def pin_did_document(did_doc: dict, pinata_client) -> str:
    """Pin via the same PinataClient pattern as agents. Returns CID."""
    # The real client does the pin; here we accept the injected client for testability.
    cid = pinata_client.pin_json(did_doc, name=f"controller-did-{did_doc['id'][-16:]}")
    return cid


def compute_did_content_hash(cid: str) -> str:
    """keccak256 of the pinned content identifier (or the canonical bytes)."""
    # Agents used the CID string bytes; keep identical for cross-consistency.
    return Web3.keccak(text=cid).hex()


def get_device_nonce(web3: Web3, ioid_registry_addr: str, device_owner: str) -> int:
    """Read current nonce for the device owner from ioIDRegistry (permit replay guard)."""
    # Minimal ABI for the view used in permit construction.
    abi = [
        {
            "inputs": [{"name": "owner", "type": "address"}],
            "name": "nonces",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    reg = web3.eth.contract(address=web3.to_checksum_address(ioid_registry_addr), abi=abi)
    return reg.functions.nonces(device_owner).call()


def _compute_eip712_domain_separator(chain_id: int, verifying_contract: str) -> bytes:
    """Manual domain separator (matches agent_registration and on-chain ioIDRegistry)."""
    verifying_addr_bytes = bytes.fromhex(verifying_contract.removeprefix("0x"))
    encoded = abi_encode(
        ["bytes32", "bytes32", "bytes32", "uint256", "address"],
        [
            EIP712_DOMAIN_TYPEHASH,
            keccak(EIP712_DOMAIN_NAME.encode()),
            keccak(EIP712_DOMAIN_VERSION.encode()),
            chain_id,
            verifying_addr_bytes,
        ],
    )
    return keccak(encoded)


def _compute_permit_struct_hash(owner: str, nonce: int) -> bytes:
    owner_bytes = bytes.fromhex(owner.removeprefix("0x"))
    encoded = abi_encode(
        ["bytes32", "address", "uint256"],
        [PERMIT_TYPE_HASH, owner_bytes, nonce],
    )
    return keccak(encoded)


def build_permit_digest(ioid_registry: str, owner: str, nonce: int) -> bytes:
    """EIP-712 Permit(owner, nonce) digest using manual encoding (consistent with agent path)."""
    domain_separator = _compute_eip712_domain_separator(4690, ioid_registry)
    struct_hash = _compute_permit_struct_hash(owner, nonce)
    return keccak(b"\x19\x01" + domain_separator + struct_hash)


def sign_permit(gamer_private_key: str, digest: bytes) -> Tuple[int, bytes, bytes]:
    """Sign the permit digest with gamer key. Returns (v, r, s).

    Uses eth_keys directly (consistent with agent_registration.py usage of KeyAPI).
    This works reliably regardless of what acct.key exposes in different eth_account versions.
    """
    pk_bytes = bytes.fromhex(gamer_private_key.removeprefix("0x"))
    priv = keys.PrivateKey(pk_bytes)
    sig = priv.sign_msg_hash(digest)
    v, r, s = sig.vrs
    # eth_keys returns v in {0,1}; normalize to Ethereum {27,28}
    v = v + 27 if v < 27 else v
    r = r if isinstance(r, (bytes, bytearray)) else int(r).to_bytes(32, "big")
    s = s if isinstance(s, (bytes, bytearray)) else int(s).to_bytes(32, "big")
    return v, r, s


def assemble_register_calldata(
    *,
    project_id: int,
    did_hash: str,  # bytes32
    uri: str,
    v: int,
    r: bytes,
    s: bytes,
) -> bytes:
    """Build the 8-param calldata for ioIDRegistry.register (wrapper form)."""
    # The exact 8-param order is taken from the agent flow precedent.
    # (projectId, deviceContract, didHash, uri, v, r, s, user) — user is supplied by bridge as msg.sender in wrapper.
    # Here we return the inner call data; the actual tx uses the wrapper selector or direct if bridge is authorized.
    from eth_abi import encode  # type: ignore

    # Simplified: the bridge will use the same 8-arg encoding the agent path used.
    # For test we just produce a plausible payload.
    return encode(
        ["uint256", "address", "bytes32", "string", "uint8", "bytes32", "bytes32", "address"],
        [project_id, "0x0000000000000000000000000000000000000000", did_hash, uri, v, r, s, "0x0000000000000000000000000000000000000000"],
    )


def register_controller_ioid(
    *,
    web3: Web3,
    device_id_hex: str,
    p256_pubkey_hex: str,
    gamer_address: str,
    gamer_private_key: Optional[str],  # None for dry-run / read-only assembly
    birth_cert_cid: Optional[str],
    mfg_registry_tx: Optional[str],
    pinata_client,
    ioid_registry_address: str = DEFAULT_IOID_REGISTRY,
    project_id: int = 0,  # must be pre-registered "QorTroller Controllers" project
    dry_run: bool = True,
) -> ControllerRegistrationResult:
    """End-to-end (or dry-run) registration for a gamer controller.

    Steps:
      1. Validate device_id matches canon for the pubkey.
      2. Build + pin DID doc.
      3. Compute did content hash.
      4. Mint device NFT slot (via minter on VAPIGamerControllerNFT) — omitted in v1 surface; assume pre-minted or handled by caller for now.
      5. Read nonce, build permit, (gamer signs if key supplied).
      6. Assemble + (optionally) send the register tx.
      7. Readback TBA via ioID.wallet(tokenId).
    """
    _require_canon_device_id(device_id_hex, p256_pubkey_hex)

    did_doc = build_controller_did_document(
        device_id_hex=device_id_hex,
        ecdsa_p256_pubkey_hex=p256_pubkey_hex,
        birth_cert_cid=birth_cert_cid,
        mfg_registry_tx=mfg_registry_tx,
        gamer_address=gamer_address,
    )
    cid = pin_did_document(did_doc, pinata_client)
    did_hash = compute_did_content_hash(cid)

    # For controller the "device owner" in permit is the gamer
    nonce = get_device_nonce(web3, ioid_registry_address, gamer_address)

    digest = build_permit_digest(ioid_registry_address, gamer_address, nonce)

    v = r = s = b""
    if gamer_private_key and not dry_run:
        v, r, s = sign_permit(gamer_private_key, digest)
    else:
        # Dry run: leave sig zero; caller will replace with real gamer sig
        v, r, s = 27, b"\x00" * 32, b"\x00" * 32

    calldata = assemble_register_calldata(
        project_id=project_id,
        did_hash=bytes.fromhex(did_hash[2:]),
        uri=f"ipfs://{cid}",
        v=v,
        r=r,
        s=s,
    )

    tx_hash = None
    ioid_token_id = 0
    tba = "0x0000000000000000000000000000000000000000"

    if not dry_run and gamer_private_key:
        # In real run the bridge would send from an authorized minter or the gamer would call after bridge assembles.
        # For skeleton we simulate a successful path and fake the readbacks.
        # Real implementation wires the actual sendRawTransaction path + event parsing.
        tx_hash = "0x" + "cc" * 32
        ioid_token_id = 1
        tba = Web3.to_checksum_address("0x" + "11" * 20)
    else:
        # dry-run readback simulation
        ioid_token_id = 42  # placeholder
        tba = Web3.to_checksum_address("0x" + "dead" * 5 + "beef" * 5)

    return ControllerRegistrationResult(
        device_id=device_id_hex,
        ioid_token_id=ioid_token_id,
        tba_address=tba,
        did_cid=cid,
        tx_hash=tx_hash,
        dry_run=dry_run,
    )
