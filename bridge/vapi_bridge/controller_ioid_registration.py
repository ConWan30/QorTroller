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

Binding to physical controller (mint/verify split, A2A round-26 / F-PATHA-1):
- NEW device_ids are minted as canon keccak256(65B SEC1 pubkey) per DEVICE_ID_CANON_v1
- an ALREADY-REGISTERED device is bound by its VMDR pubkeyHash — callers with
  chain access pass on_chain_pubkey_hash_hex (devices[deviceId].pubkeyHash) and
  the binding check becomes authoritative chain evidence (grandfathers the
  pre-canon 581a836c registration); without it the canon best-effort applies
- birth cert (on-chain via MFG registry) proves the P256 pubkey ownership at manufacture

Reuse of agent pattern (M1/M2/M4/M6/N2β/N4) without duplicating operator code.
Phase 2 software-only surface; on-chain registration gated on 1B (silicon).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from eth_account import Account
# Manual EIP-712 (no eth_account encode_typed_data dependency for this simple Permit)
# Mirrors the proven construction in agent_registration.py (Section 14.3 / M2)
from eth_abi import encode as abi_encode
from eth_hash.auto import keccak
from eth_keys import keys
from web3 import Web3

from vapi_bridge.device_birth_cert import verify_registered_device_binding

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

# Placeholder addresses (resolved at runtime via resolve_ioid_registry_address).
DEFAULT_IOID_REGISTRY = "0x0000000000000000000000000000000000000000"  # sentinel: unresolved
DEFAULT_IOID = "0x0000000000000000000000000000000000000000"
_ZERO_ADDR = "0x0000000000000000000000000000000000000000"

# The Phase 55 VAPIioIDRegistry (bridge-only DID book — register(bytes32,address,string),
# NO nonces / NO EIP-712 permit). It is NOT the ioID permit registry the controller flow
# needs; wiring the permit path at it makes nonces() revert. Refuse it by address equality
# (F-T3-1 / A2A round-33).
_VAPI_DID_REGISTRY_ADDR = "0xF7885B588718b891B2234477D031607da4a7ACfe"


def resolve_ioid_registry_address(*, deployed_addresses_path: Path | None = None) -> str:
    """Resolve the ioID PERMIT registry (the one with nonces() + 8-param EIP-712 register).

    Fail-loud, never the zero address, never the Phase 55 VAPIioIDRegistry DID book.
    Resolution order (A2A round-33 Q3 + F3 hardening):
      1. env IOID_PERMIT_REGISTRY_ADDRESS (DEDICATED — permit registry only)
      2. env IOID_REGISTRY_ADDRESS (SHARED — historically also holds the Phase 55 DID book
         for chain.py's DID wiring; the DID book is SKIPPED here, not fatal)
      3. contracts/deployed-addresses.json key "ioIDRegistry" (NOT "VAPIioIDRegistry")
      4. agent_registration.IOID_REGISTRY_ADDR (fleet-proven system registry; last resort)

    A candidate equal to the DID book (or zero) is SKIPPED, not fatal — the shared env
    legitimately points at the DID book for Phase 55 DID work (grok F3). Passing the DID book
    EXPLICITLY as ioid_registry_address IS fatal (a deliberate mis-wire) — that check lives in
    register_controller_ioid.

    Both agents and controllers register against this SAME system registry; the device-type
    difference is the ioIDStore deviceContract (VAPIOperatorAgentNFT vs VAPIGamerControllerNFT),
    NOT the registry — so reusing the agent-path constant here is correct, not an identity merge.
    """
    candidates: list[tuple[str, str]] = []

    permit_env = os.environ.get("IOID_PERMIT_REGISTRY_ADDRESS", "").strip()
    if permit_env:
        candidates.append(("env IOID_PERMIT_REGISTRY_ADDRESS", permit_env))

    shared_env = os.environ.get("IOID_REGISTRY_ADDRESS", "").strip()
    if shared_env:
        candidates.append(("env IOID_REGISTRY_ADDRESS", shared_env))

    path = deployed_addresses_path or (
        Path(__file__).resolve().parents[2] / "contracts" / "deployed-addresses.json"
    )
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            addr = data.get("ioIDRegistry")
            if addr:
                candidates.append(("deployed-addresses.json ioIDRegistry", str(addr)))
    except Exception:  # noqa: BLE001 — a bad addresses file just means this source is skipped
        pass

    try:
        from vapi_bridge.agent_registration import IOID_REGISTRY_ADDR as _agent_ioid
        candidates.append(("agent_registration.IOID_REGISTRY_ADDR", str(_agent_ioid)))
    except Exception:  # noqa: BLE001 — optional fallback
        pass

    for source, addr in candidates:
        a = str(addr).strip()
        if not a or a.lower() == _ZERO_ADDR.lower():
            continue  # skip zero
        if a.lower() == _VAPI_DID_REGISTRY_ADDR.lower():
            log.debug("resolve_ioid_registry: skipping DID book %s from %s (not a permit registry)",
                      a, source)
            continue  # skip the DID book — ambient, not a permit target
        return a  # first non-zero, non-DID-book candidate wins

    raise ValueError(
        "no ioID PERMIT registry resolved. Sources tried (env IOID_PERMIT_REGISTRY_ADDRESS / "
        "env IOID_REGISTRY_ADDRESS / deployed-addresses 'ioIDRegistry' / agent constant) were "
        "all absent, zero, or the Phase 55 VAPIioIDRegistry DID book (which has no permit "
        "interface; F-T3-1). Set IOID_PERMIT_REGISTRY_ADDRESS or the deployed-addresses "
        "'ioIDRegistry' key to the ioID permit registry."
    )


@dataclass(slots=True)
class ControllerRegistrationResult:
    device_id: str
    ioid_token_id: Optional[int]      # None in dry-run — NEVER a fabricated placeholder
    tba_address: Optional[str]        # None in dry-run — needs a real mint + ioID.wallet()
    did_cid: str
    tx_hash: Optional[str]
    dry_run: bool
    ioid_registry_address: Optional[str] = None  # the resolved PERMIT registry
    device_nonce: Optional[int] = None           # live nonce read (proves the registry interface)
    pending_prereqs: Optional[list[str]] = None  # what blocks a real registration (honest)


def _require_device_binding(
    device_id_hex: str,
    pubkey_hex: str,
    *,
    on_chain_pubkey_hash_hex: Optional[str] = None,
) -> None:
    """Chain-first device binding (mint/verify split, A2A round-26).

    With on_chain_pubkey_hash_hex (VMDR devices[deviceId].pubkeyHash) the check
    is the AUTHORITATIVE chain binding — a registered pre-canon device (581a836c)
    passes iff its key matches what the manufacturer attested. Without it, the
    offline canon best-effort applies (byte-identical to the pre-split behavior).
    """
    ok, reason = verify_registered_device_binding(
        device_id_hex, pubkey_hex,
        on_chain_pubkey_hash_hex=on_chain_pubkey_hash_hex,
    )
    if not ok:
        raise ValueError(f"device_id/key binding failed: {reason}")


def build_controller_did_document(
    *,
    device_id_hex: str,
    ecdsa_p256_pubkey_hex: str,
    birth_cert_cid: Optional[str] = None,
    mfg_registry_tx: Optional[str] = None,
    gamer_address: str,
    on_chain_pubkey_hash_hex: Optional[str] = None,
) -> dict:
    """Minimal DID document for a gamer controller.

    The document asserts:
      - controller's device_id (canon-minted, or chain-bound for a registered
        device when on_chain_pubkey_hash_hex is supplied)
      - the P256 public key from its birth cert
      - optional links to on-chain MFG birth cert + gamer owner
    """
    _require_device_binding(
        device_id_hex, ecdsa_p256_pubkey_hex,
        on_chain_pubkey_hash_hex=on_chain_pubkey_hash_hex,
    )

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
    device_contract: str,   # VAPIGamerControllerNFT (controller prereq — placeholder in dry-run)
    token_id: int,          # minted controller-NFT tokenId (prereq — placeholder in dry-run)
    device: str,            # device EOA (checksummed)
    did_hash: bytes,        # bytes32 DID content hash
    uri: str,
    v: int,
    r: bytes,
    s: bytes,
) -> bytes:
    """Build canonical `ioIDRegistry.register(deviceContract, tokenId, device, hash, uri, v, r, s)`
    calldata — the exact 8-param order/types of the LIVE IoTeX ioIDRegistry ABI
    (`agent_registration.IOID_REGISTRY_ABI`), corrected from the old skeleton shape
    `(projectId, deviceContract, didHash, uri, v, r, s, user)` which never matched the
    real registry (A2A round-33 F6).

    `device_contract` + `token_id` are CONTROLLER PREREQUISITES (VAPIGamerControllerNFT
    deployed + a minted tokenId); until those exist they are placeholders, so this is
    dry-run-shape only — never a broadcastable registration.
    """
    from eth_abi import encode  # type: ignore

    return encode(
        ["address", "uint256", "address", "bytes32", "string", "uint8", "bytes32", "bytes32"],
        [device_contract, token_id, device, did_hash, uri, v, r, s],
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
    on_chain_pubkey_hash_hex: Optional[str] = None,
) -> ControllerRegistrationResult:
    """End-to-end (or dry-run) registration for a gamer controller.

    ioid_registry_address: the ioID PERMIT registry. Default (the zero sentinel) triggers
    resolve_ioid_registry_address() — env → deployed-addresses 'ioIDRegistry' → agent constant,
    fail-loud, refusing the zero address AND the Phase 55 VAPIioIDRegistry DID book (F-T3-1).

    HONEST SCOPE: dry-run assembles the permit + canonical calldata against the LIVE registry
    (proving the interface) but returns ioid_token_id=None / tba_address=None — a controller
    registration is BLOCKED until the prerequisites exist (VAPIGamerControllerNFT deployed +
    ioIDStore.setDeviceContract for a "QorTroller Controllers" project + a minted tokenId +
    a real gamer permit signature). A non-dry-run call raises rather than fabricate a tx.

    Steps:
      1. Resolve + validate the ioID permit registry (never zero, never the DID book).
      2. Validate the device_id/key binding (chain-first when the caller supplies the
         VMDR pubkeyHash; canon best-effort otherwise).
      3. Build + pin DID doc; compute did content hash.
      4. Read the live device nonce (proves the resolved registry's permit interface).
      5. Build permit; (gamer signs if key supplied).
      6. Assemble canonical register calldata (placeholder deviceContract/tokenId in dry-run).
    """
    if not ioid_registry_address or ioid_registry_address == DEFAULT_IOID_REGISTRY:
        ioid_registry_address = resolve_ioid_registry_address()
    elif ioid_registry_address.lower() == _VAPI_DID_REGISTRY_ADDR.lower():
        raise ValueError(
            f"ioid_registry_address is VAPIioIDRegistry {ioid_registry_address} (the Phase 55 "
            f"DID book — no permit/nonces; F-T3-1). Pass the ioID PERMIT registry."
        )

    _require_device_binding(
        device_id_hex, p256_pubkey_hex,
        on_chain_pubkey_hash_hex=on_chain_pubkey_hash_hex,
    )

    did_doc = build_controller_did_document(
        device_id_hex=device_id_hex,
        ecdsa_p256_pubkey_hex=p256_pubkey_hex,
        birth_cert_cid=birth_cert_cid,
        mfg_registry_tx=mfg_registry_tx,
        gamer_address=gamer_address,
        on_chain_pubkey_hash_hex=on_chain_pubkey_hash_hex,
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

    # Canonical register calldata. deviceContract/tokenId/device are controller
    # prerequisites (VAPIGamerControllerNFT + a minted tokenId) — placeholders here, so
    # this is dry-run-shape only, never a broadcastable registration.
    _device_addr = Web3.to_checksum_address("0x" + device_id_hex.lower().removeprefix("0x")[-40:])
    calldata = assemble_register_calldata(
        device_contract=_ZERO_ADDR,   # VAPIGamerControllerNFT — PREREQ, not deployed
        token_id=0,                   # minted controller tokenId — PREREQ, not minted
        device=_device_addr,
        did_hash=bytes.fromhex(did_hash[2:]),
        uri=f"ipfs://{cid}",
        v=v,
        r=r,
        s=s,
    )

    # The controller registration prerequisites (D-CONTROLLER-IOID-1 Option A + Phase 1B).
    prereqs = [
        "ProjectRegistry: a 'QorTroller Controllers' project registered",
        "VAPIGamerControllerNFT deployed (the controller deviceContract)",
        "ioIDStore.setDeviceContract(projectId, VAPIGamerControllerNFT)",
        "a minted controller-NFT tokenId for this device",
        "a real gamer EIP-712 permit signature (gamer-sovereign, Option A)",
    ]

    if not dry_run:
        # HONEST: the real broadcast path is NOT wired and the prerequisites above are unmet.
        # Refuse to fabricate a tx / tokenId / TBA (the old skeleton returned fake success).
        raise NotImplementedError(
            "controller ioID registration broadcast is not wired — dry-run only. "
            "Blocked on: " + "; ".join(prereqs) + ". "
            "The registry + permit interface are proven live (see the dry-run result); "
            "registration is a separate operator-GO ceremony once the prereqs exist."
        )

    # Dry-run: honest result — no fabricated tokenId / TBA. The registry resolved, the
    # nonce read live, the permit + canonical calldata assembled; a real registration is
    # blocked on `pending_prereqs`.
    return ControllerRegistrationResult(
        device_id=device_id_hex,
        ioid_token_id=None,
        tba_address=None,
        did_cid=cid,
        tx_hash=None,
        dry_run=True,
        ioid_registry_address=ioid_registry_address,
        device_nonce=nonce,
        pending_prereqs=prereqs,
    )
