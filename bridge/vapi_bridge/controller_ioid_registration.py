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


def compute_did_content_hash(did_doc: dict) -> str:
    """keccak256 of the canonical-JSON DID DOCUMENT — the bytes32 `hash` arg of
    ioIDRegistry.register (ioID Inc-B, A2A round-01 F2).

    Matches agent_registration.compute_did_content_hash byte-for-byte: the agents hash the DID
    DOCUMENT (sort_keys=True, separators=(",",":")), NOT the CID string. The prior controller
    version hashed the CID — inconsistent with the agent path + the on-chain record semantics.
    """
    canonical = json.dumps(did_doc, sort_keys=True, separators=(",", ":"))
    return Web3.keccak(text=canonical).hex()


def assert_option_a_register_ready(
    *,
    device_contract: str,
    token_id: int,
    device: str,
    gamer_address: str,
) -> None:
    """Guard a REAL Option-A register (ioID Inc-B / round-01 F2). Raises unless:
      - device == gamer_address: under D-CONTROLLER-IOID-1 Option A the GAMER signs the permit,
        so the register's `device` (ecrecover target) MUST be the gamer EOA — not the controller's
        truncated device_id (the physical Edge binds via the DID doc + birth cert / VMDR, not this slot).
      - device_contract is a real, non-zero address (VAPIGamerControllerNFT — the deployed deviceContract).
      - token_id > 0: a minted controller-NFT tokenId (the register consumes it).
    Dry-run assembly may use placeholders; the real send (Inc-D) MUST pass this first.
    """
    if str(device).lower() != str(gamer_address).lower():
        raise ValueError(
            f"Option-A register: device ({device}) must equal the gamer EOA ({gamer_address}) — "
            f"the gamer signs the permit; ecrecover(device) would fail otherwise."
        )
    dc = str(device_contract).strip()
    if not dc or dc.lower() == _ZERO_ADDR.lower() or len(dc) != 42:
        raise ValueError(
            f"Option-A register: device_contract ({device_contract!r}) must be the deployed "
            f"VAPIGamerControllerNFT address, not zero (deploy it via Inc-A first)."
        )
    if int(token_id) <= 0:
        raise ValueError(
            f"Option-A register: token_id ({token_id}) must be a minted controller-NFT tokenId (> 0)."
        )


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


_TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _ioid_minted_token_id(logs, ioid_contract_addr: str) -> Optional[int]:
    """The ioID DID tokenId MINTED (from==0x0) by the ioID contract in a register receipt.

    Owner-AGNOSTIC by design (Inc-D): the DID NFT's owner is set by the ioID internal
    ERC-6551 flow, so we filter only on (contract == ioID) + (from == 0x0) and take the
    minted tokenId — NEVER equate it with the DeviceNFT tokenId (an agent bug already fixed
    in step-7). Robust to bare/0x/HexBytes/dict log shapes; requires a 4-topic ERC-721
    Transfer (a 3-topic ERC-20-shaped Transfer is skipped); never IndexErrors."""
    want = str(ioid_contract_addr).lower()

    def _hx(x):
        h = x.hex() if hasattr(x, "hex") else str(x)
        h = h.lower()
        return h if h.startswith("0x") else "0x" + h

    for lg in logs:
        addr = getattr(lg, "address", None)
        if addr is None and isinstance(lg, dict):
            addr = lg.get("address")
        if str(addr).lower() != want:
            continue
        topics = getattr(lg, "topics", None)
        if topics is None and isinstance(lg, dict):
            topics = lg.get("topics")
        topics = list(topics or [])
        if len(topics) < 4:
            continue
        t = [_hx(x) for x in topics[:4]]
        if t[0] != _TRANSFER_TOPIC0:
            continue
        if int(t[1][-40:] or "0", 16) != 0:   # from == 0x0 (mint)
            continue
        return int(t[3], 16)
    return None


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
    device_contract: str = _ZERO_ADDR,   # Inc-A NFT (real for the Inc-D send; placeholder in dry-run)
    token_id: int = 0,                    # minted controller tokenId (real for Inc-D)
    ioid_store_address: Optional[str] = None,    # ioIDStore (register fee price()); default = canonical
    ioid_contract_address: Optional[str] = None, # ioID NFT (wallet() TBA readback); default = canonical
    hard_cap_iotx: float = 0.75,          # Inc-D send spend cap (fee ~0.1 + gas)
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
    did_hash = compute_did_content_hash(did_doc)  # hash the DID DOCUMENT (agent-consistent, Inc-B F2)

    # Option A (D-CONTROLLER-IOID-1): the GAMER signs the permit; the permit binds (user, nonce(gamer)).
    nonce = get_device_nonce(web3, ioid_registry_address, gamer_address)

    digest = build_permit_digest(ioid_registry_address, gamer_address, nonce)

    v = r = s = b""
    if gamer_private_key and not dry_run:
        v, r, s = sign_permit(gamer_private_key, digest)
    else:
        # Dry run: leave sig zero; caller will replace with real gamer sig
        v, r, s = 27, b"\x00" * 32, b"\x00" * 32

    device_cs = Web3.to_checksum_address(gamer_address)
    # grok r02 F1: Web3.keccak(...).hex() has NO 0x prefix here, so [2:] would drop the first BYTE
    # -> a 31-byte hash. removeprefix handles both prefixed + bare, always 32 bytes.
    did_hash_b = bytes.fromhex(did_hash.removeprefix("0x"))
    uri = f"ipfs://{cid}"

    # The controller registration prerequisites (D-CONTROLLER-IOID-1 Option A + Phase 1B).
    prereqs = [
        "ProjectRegistry: a 'QorTroller Controllers' project registered",
        "VAPIGamerControllerNFT deployed (the controller deviceContract)",
        "ioIDStore.setDeviceContract(projectId, VAPIGamerControllerNFT)",
        "a minted controller-NFT tokenId for this device",
        "a real gamer EIP-712 permit signature (gamer-sovereign, Option A)",
    ]

    if dry_run:
        # Prove the interface: assemble canonical calldata with placeholder prereqs; NO broadcast,
        # NO fabricated tokenId/TBA. `device` is the GAMER EOA (permit signer / ecrecover target),
        # NOT the controller's device_id -- the Edge binds via the DID doc + birth cert / VMDR.
        assemble_register_calldata(
            device_contract=_ZERO_ADDR, token_id=0, device=device_cs,
            did_hash=did_hash_b, uri=uri, v=v, r=r, s=s,
        )
        return ControllerRegistrationResult(
            device_id=device_id_hex, ioid_token_id=None, tba_address=None,
            did_cid=cid, tx_hash=None, dry_run=True,
            ioid_registry_address=ioid_registry_address, device_nonce=nonce,
            pending_prereqs=prereqs,
        )

    # -- Inc-D: the REAL Option-A register broadcast (operator-fired, gamer-signed) -------------
    # Gamer-sovereign: the gamer signs the permit AND sends the tx (msg.sender = user = gamer;
    # dev-self => gamer == bridge). Fail-closed on every missing prerequisite; never fabricate.
    if not gamer_private_key:
        raise ValueError("real register requires gamer_private_key (Option A: the gamer signs + sends)")
    assert_option_a_register_ready(
        device_contract=device_contract, token_id=token_id,
        device=device_cs, gamer_address=device_cs,
    )
    if not (r and s and r != b"\x00" * 32):
        raise ValueError("real register requires a real gamer permit signature -- dry-run left v,r,s zero")

    # Canonical ioID system anchors (imported lazily -- heavy deps; keeps dry-run/tests light).
    from vapi_bridge.agent_registration import (
        IOID_REGISTRY_ABI, IOID_STORE_ADDR, IOID_STORE_ABI, IOID_CONTRACT_ADDR, IOID_ABI,
    )
    store_addr = ioid_store_address or IOID_STORE_ADDR
    ioid_addr = ioid_contract_address or IOID_CONTRACT_ADDR

    acct = Account.from_key(gamer_private_key)
    if acct.address.lower() != device_cs.lower():
        raise ValueError(f"gamer_private_key address {acct.address} != gamer {device_cs} "
                         f"(Option A: the permit signer must be the tx sender)")

    # Register fee = ioIDStore.price() pay-as-you-go value (applyIoIDs pre-pay is the alternative).
    store = web3.eth.contract(address=web3.to_checksum_address(store_addr), abi=IOID_STORE_ABI)
    price_wei = int(store.functions.price().call())

    registry = web3.eth.contract(
        address=web3.to_checksum_address(ioid_registry_address), abi=IOID_REGISTRY_ABI)
    fn = registry.functions.register(
        web3.to_checksum_address(device_contract), int(token_id), device_cs,
        did_hash_b, uri, int(v), r, s,
    )

    # estimate-first (also the pre-send revert guard: a bad permit / consumed tokenId reverts here)
    # + hard-cap. IoTeX gasPrice; 1.25x buffer per the ceremony convention.
    est_gas = fn.estimate_gas({"from": device_cs, "value": price_wei})
    gas_price = web3.eth.gas_price
    buffered_gas = (est_gas * 125) // 100
    buf_cost_iotx = float(Web3.from_wei(buffered_gas * gas_price + price_wei, "ether"))
    log.info("register est_gas=%d buffered=%d fee_wei=%d buf_cost_iotx=%.6f cap=%.2f",
             est_gas, buffered_gas, price_wei, buf_cost_iotx, hard_cap_iotx)
    if buf_cost_iotx > hard_cap_iotx:
        raise ValueError(f"register buffered cost {buf_cost_iotx} IOTX exceeds hard cap {hard_cap_iotx}")

    tx = fn.build_transaction({
        "from": device_cs,
        "nonce": web3.eth.get_transaction_count(device_cs),  # TX nonce (NOT the permit nonce)
        "gas": buffered_gas, "gasPrice": gas_price, "chainId": 4690, "value": price_wei,
    })
    signed = acct.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = web3.eth.send_raw_transaction(raw)
    rcpt = web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    tx_hex = "0x" + (tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)).removeprefix("0x")
    if int(getattr(rcpt, "status", 0)) != 1:
        raise RuntimeError(f"register reverted: status={rcpt.status} tx={tx_hex} "
                           f"https://testnet.iotexscan.io/tx/{tx_hex}")

    # Readback (FAIL-CLOSED, grok r07 F1): after a status=1 register the ioID mint MUST be present --
    # never return a success-shaped None id/TBA (the mint-None bug class). Parse the minted ioID DID
    # tokenId from the ioID contract's Transfer(0x0->owner) in THIS receipt (owner-agnostic; NEVER the
    # DeviceNFT tokenId), then ioID.wallet(id) -> the ERC-6551 TBA (must be non-zero).
    ioid_token_id = _ioid_minted_token_id(rcpt.logs, ioid_addr)
    if ioid_token_id is None:
        raise RuntimeError(
            f"register mined status=1 but NO ioID mint Transfer in the receipt -- refusing to report "
            f"success without a tokenId. Inspect: https://testnet.iotexscan.io/tx/{tx_hex}")
    ioid_c = web3.eth.contract(address=web3.to_checksum_address(ioid_addr), abi=IOID_ABI)
    w = ioid_c.functions.wallet(int(ioid_token_id)).call()
    tba = (w[0] if isinstance(w, (list, tuple)) else w)
    if not tba or int(str(tba), 16) == 0:
        raise RuntimeError(
            f"ioID.wallet({ioid_token_id}) returned a zero/empty TBA after register -- refusing to "
            f"report success. tx https://testnet.iotexscan.io/tx/{tx_hex}")
    log.info("register OK tx=%s ioid_token_id=%s tba=%s", tx_hex, ioid_token_id, tba)

    return ControllerRegistrationResult(
        device_id=device_id_hex,
        ioid_token_id=ioid_token_id,
        tba_address=tba,
        did_cid=cid,
        tx_hash=tx_hex,
        dry_run=False,
        ioid_registry_address=ioid_registry_address,
        device_nonce=nonce,
        pending_prereqs=None,
    )
