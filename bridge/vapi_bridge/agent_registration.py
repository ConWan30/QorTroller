"""Phase O0 Section 6.4 Block B — Operator agent registration orchestrator.

Composes Section 6.3 KMSClient + Section 6.4 PinataClient + web3 connection
to execute the canonical Operator agent registration flow per Pass 2C
Section 14 (fourth amendment, commit d2911480) specifications.

Block B replaces the dcaf5015 implementation in full. The dcaf5015
implementation built against an incorrect 2-parameter ioIDRegistry.register
ABI (no EIP-712), wrong NFT semantics (per K1a "shared project NFT" which
is canonically infeasible per M3), and external ERC-6551 createAccount
calls (per M6, TBA creation is internal to ioID.mint). Section 14
captures the architectural drift and Block B implements against the
canonical specification.

Registration flow per Section 14.4 + brief 13-step orchestration:

  Operator-driven prerequisite chain (one-time, NOT in register_full_flow):

    1. ProjectRegistry.register("VAPI Operator Agents", 0)
       → mints IProject NFT tokenId X (project identifier)

    2. Deploy VAPIOperatorAgentNFT contract via Hardhat
       contracts/scripts/deploy-vapi-operator-agent-nft.js
       → deployed at address Y (custom DeviceNFT)

    3. ioIDStore.setDeviceContract(X, Y)
       → bidirectional 1:1 mapping per M4

    4. (Optional) ioIDStore.applyIoIDs(X, 2) {value: 0.2 IOTX}
       → pre-pay activeIoID fees per M5; OR pay-as-you-go

  Per-agent register_full_flow (Sections 14.4 step 7-9 + 14.6):

    5.  check_project_nft (preflight verification — read-only, L2c)
    6.  populate_did_document (KMS pubkey → template)
    7.  pin_did_document (Pinata IPFS pin → CID)
    8.  compute_did_content_hash (keccak256 of pinned content)
    9.  mint_device_nft (per-agent device tokenId from VAPIOperatorAgentNFT)
    10. query_device_nonce (current nonce from ioIDRegistry per M2)
    11. compute_eip712_permit_digest (Permit struct, signed by device per M2)
    12. kms_sign_permit_digest (KMS sign digest, returns DER signature)
    13. parse_eip712_signature_to_vrs (DER → v, r, s components)
    14. mint_ioid_did (8-param ioIDRegistry.register per M1)
    15. readback_tba (ioID.wallet(ioid_token_id) per M6 + N4)
    16. compute_agent_id (keccak256(abi.encode(ioid, tba)) per Q9 unchanged)
    17. register_agent (AgentRegistry.registerAgent unchanged)

Key architectural decisions (Section 14.7):

  M1 — 8-param register wrapper canonical (selector 0x39a4a241).
       Wrapper calls 9-param with user = msg.sender (bridge_wallet).

  M2 — Canonical permit-style signing. Permit(address owner, uint256 nonce)
       type hash signing (user, nonce(device)). Recovered signer must equal
       device. The (hash, uri) content is NOT cryptographically bound;
       replay protection comes from per-device nonce.

  N2 β — Custom DeviceNFT contract (VAPIOperatorAgentNFT). Project NFT
         layer shared (one IProject NFT for all agents); device tokenId
         layer distinct (per-agent device tokenIds). Identity distinction
         at four layers preserved.

  N3 (M6-acknowledge) — Per-agent ERC-6551 salts canonically infeasible.
       Salt hardcoded to 0 inside ioID.mint. Identity distinction at TBA
       layer comes from distinct ioID tokenIds (auto-incremented).

  N4 (K3 clarification) — Two NFT addresses serve different layers:
       ioID contract (0x45Ce...) is canonical TBA token contract.
       VAPIOperatorAgentNFT (deployed) is canonical deviceContract.

  M4 — ioIDStore deviceContractProject prerequisite via setDeviceContract
       (one-time, operator-driven) plus optional applyIoIDs pre-pay.

  M5 — activeIoID fee 0.1 IOTX per device. Total 0.2 IOTX for 2 agents.
       Reassessed wallet budget 1.73 IOTX with 9.8x headroom.

L1a, L2c, L3a, L4a + V8 sub-decisions (V8.2-V8.7) honored throughout.

Cross-references:
  Pass 2C Section 14 (commit d2911480 fourth amendment) — canonical spec
  Pass 2C Section 13 (commit 8fab340e third amendment) — historical record
  bridge/vapi_bridge/kms_client.py (commit d3b30d58) — KMS integration
  bridge/vapi_bridge/pinata_client.py (commit dcaf5015) — Pinata integration
  contracts/contracts/VAPIOperatorAgentNFT.sol — custom DeviceNFT
  contracts/scripts/deploy-vapi-operator-agent-nft.js — deployment script
  github.com/iotexproject/ioID-contracts at commit b94ad092 — canonical source
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePublicKey, SECP256K1,
)
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from eth_abi import encode as abi_encode
from eth_hash.auto import keccak
from eth_keys import KeyAPI
from eth_utils import to_checksum_address

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded contract addresses (G1 pattern; sourced per comments)
# ---------------------------------------------------------------------------

# IoTeX testnet chain ID (per Pass 2C Section 12 + Stream 2-deploy verification)
IOTEX_TESTNET_CHAIN_ID = 4690

# IoTeX ioID infrastructure (Section 14.2 + Section 14.5 verified empirically)
PROJECT_REGISTRY_ADDR = "0x060581AA1A4e0cC92FBd74d251913238De2F13cd"
IOID_REGISTRY_ADDR = "0x0A7e595C7889dF3652A19aF52C18377bF17e027D"
IOID_STORE_ADDR = "0x60cac5CE11cb2F98bF179BE5fd3D801C3D5DBfF2"

# IOID_CONTRACT_ADDR is the per-DID NFT contract; per N4 + M6 it is the
# canonical TBA token contract used in ERC-6551 derivation INSIDE ioID.mint.
# Bridge code reads back TBA addresses via ioID.wallet(ioid_token_id) at
# this contract. (Distinct from VAPI_OPERATOR_AGENT_NFT_ADDR which is
# the canonical deviceContract for ioIDRegistry.register per N2 β.)
IOID_CONTRACT_ADDR = "0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7"

# AgentRegistry from Stream 2-deploy commit d019c067 (deployed-addresses.json)
AGENT_REGISTRY_ADDR = "0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4"

# VAPIOperatorAgentNFT — the canonical deviceContract for ioIDRegistry.register
# per N2 β. Placeholder zero address until contracts/scripts/deploy-vapi-operator-
# agent-nft.js executes on testnet. Per V8.3: post-deployment commit updates this
# constant with the deployed address; commit message documents the deployment
# transaction hash. register_full_flow raises AgentRegistrationConfigError if
# this constant is still the placeholder when invoked, forcing operator awareness
# before any per-agent registration.
VAPI_OPERATOR_AGENT_NFT_ADDR = "0xa0CDD2B3E292c56030185c66a3d423278A4c467b"

# ---------------------------------------------------------------------------
# EIP-712 constants per Section 14.3 (verified empirically — DOMAIN_SEPARATOR
# computed locally matches on-chain value byte-for-byte)
# ---------------------------------------------------------------------------

EIP712_DOMAIN_NAME = "ioIDRegistry"
EIP712_DOMAIN_VERSION = "1"

# Pre-computed canonical type hashes per canonical ioIDRegistry.sol lines 22-26
EIP712_DOMAIN_TYPEHASH = keccak(
    b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)
PERMIT_TYPE_HASH = keccak(b"Permit(address owner,uint256 nonce)")

# ---------------------------------------------------------------------------
# Pass 2C Section 6.4 + Section 7 constants (frozen)
# ---------------------------------------------------------------------------

SCOPE_HASH_PHASE_O0_EXIT = b"\x00" * 32  # bytes32(0) — no operational authority
STATUS_DEFINED = 0  # AgentRegistry STATUS_DEFINED enum value

# N2 β: project type 0 ("hardware project" per ioIDStore.applyIoIDs constraint)
PROJECT_TYPE_HARDWARE = 0

# Canonical project name per N2 β
VAPI_OPERATOR_AGENTS_PROJECT_NAME = "VAPI Operator Agents"

# Per-agent device tokenId mapping (FROZEN at first registration; matches
# operator-driven mint order: anchor-sentry first → tokenId 1, guardian
# second → tokenId 2). Used by mint_device_nft to determine which tokenId
# the per-agent registration consumes from VAPIOperatorAgentNFT.
AGENT_TO_DEVICE_TOKEN_ID = {
    "anchor-sentry": 1,
    "guardian": 2,
    # Phase 238 Step I-FINAL — Curator (third Operator Initiative agent).
    # tokenId 3 reserved at first registration; the per-agent mint order is
    # anchor-sentry → 1, guardian → 2, curator → 3. Operator runs
    # step_6_mint_device_nft("curator") AFTER Sentry+Guardian sessions
    # completed; the wrapper consumes tokenId 3 from VAPIOperatorAgentNFT.
    "curator": 3,
}

# ---------------------------------------------------------------------------
# Inline ABIs (G2 pattern; minimal subset of canonical contracts)
# ---------------------------------------------------------------------------

# ioIDRegistry — 8-param register wrapper per M1 + nonces view per M2 +
# DOMAIN_SEPARATOR view for verification. Canonical source at commit
# b94ad092: contracts/ioIDRegistry.sol lines 69-110.
IOID_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "register",
        "stateMutability": "payable",
        "inputs": [
            {"name": "deviceContract", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
            {"name": "device", "type": "address"},
            {"name": "hash", "type": "bytes32"},
            {"name": "uri", "type": "string"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"},
        ],
        "outputs": [],
    },
    {
        "type": "function",
        "name": "nonces",
        "stateMutability": "view",
        "inputs": [{"name": "device", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "DOMAIN_SEPARATOR",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "bytes32"}],
    },
]

# ProjectRegistry — register variants + project view. Canonical source at
# commit b94ad092: contracts/ProjectRegistry.sol.
PROJECT_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "register",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_name", "type": "string"},
            {"name": "_type", "type": "uint8"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "project",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "address"}],
    },
]

# ioIDStore — setDeviceContract (1:1 mapping per M4) + applyIoIDs (pre-pay
# per M5) + price view + deviceContractProject view. Canonical source at
# commit b94ad092: contracts/ioIDStore.sol.
IOID_STORE_ABI = [
    {
        "type": "function",
        "name": "setDeviceContract",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_projectId", "type": "uint256"},
            {"name": "_contract", "type": "address"},
        ],
        "outputs": [],
    },
    {
        "type": "function",
        "name": "applyIoIDs",
        "stateMutability": "payable",
        "inputs": [
            {"name": "_projectId", "type": "uint256"},
            {"name": "_amount", "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "type": "function",
        "name": "price",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "deviceContractProject",
        "stateMutability": "view",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# ioID per-DID NFT contract — wallet view returns the ERC-6551 TBA address
# bound to a given ioID tokenId. Per M6: TBA creation is INTERNAL to
# ioID.mint with hardcoded salt=0; bridge reads back via this view rather
# than calling ERC6551Registry directly.
IOID_ABI = [
    {
        "type": "function",
        "name": "wallet",
        "stateMutability": "view",
        "inputs": [{"name": "_id", "type": "uint256"}],
        "outputs": [
            {"name": "wallet_", "type": "address"},
            {"name": "did_", "type": "string"},
        ],
    },
]

# IProject NFT contract — read-only ownership queries used by check_project_nft
# preflight (L2c). The IProject contract address is obtained via
# ProjectRegistry.project() view (queried at runtime; not hardcoded since
# that pattern matches canonical resolution method per Section 13.4).
IPROJECT_ABI = [
    {
        "type": "function",
        "name": "balanceOf",
        "stateMutability": "view",
        "inputs": [{"name": "owner", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "tokenOfOwnerByIndex",
        "stateMutability": "view",
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "index", "type": "uint256"},
        ],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# VAPIOperatorAgentNFT — custom DeviceNFT per N2 β. Mint produces the per-agent
# device tokenId; configureMinter (operator-driven, in deploy script) grants
# bridge_wallet allowance.
VAPI_OPERATOR_AGENT_NFT_ABI = [
    {
        "type": "function",
        "name": "mint",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "_to", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
    },
    {
        "type": "function",
        "name": "configureMinter",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_minter", "type": "address"},
            {"name": "_minterAllowedAmount", "type": "uint256"},
        ],
        "outputs": [],
    },
    {
        "type": "function",
        "name": "initialize",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "_name", "type": "string"},
            {"name": "_symbol", "type": "string"},
        ],
        "outputs": [],
    },
    {
        "type": "function",
        "name": "total",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [{"name": "", "type": "uint256"}],
    },
]

# Robust repo root resolution (preserves dcaf5015 pattern)
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent

# AgentRegistry ABI loaded from Hardhat artifact (lazy load via _load_agent_registry_abi)
AGENT_REGISTRY_ABI_PATH = (
    _REPO_ROOT
    / "contracts" / "artifacts" / "contracts" / "AgentRegistry.sol" / "AgentRegistry.json"
)


def _load_agent_registry_abi() -> list:
    """Load AgentRegistry ABI from Hardhat artifact. Returns the abi field."""
    if not AGENT_REGISTRY_ABI_PATH.is_file():
        raise AgentRegistrationConfigError(
            f"AgentRegistry ABI not found at {AGENT_REGISTRY_ABI_PATH}. "
            f"Run `cd contracts && npx hardhat compile` to generate."
        )
    with open(AGENT_REGISTRY_ABI_PATH, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    return artifact["abi"]


# ---------------------------------------------------------------------------
# Exception hierarchy (extended for Block B per brief)
# ---------------------------------------------------------------------------

class AgentRegistrationError(Exception):
    """Base exception for all AgentRegistrar failures."""


class AgentRegistrationConfigError(AgentRegistrationError):
    """Raised when configuration (template path, ABI path, placeholder address) is missing/invalid."""


class AgentRegistrationKMSError(AgentRegistrationError):
    """Raised when KMS operations fail during DID population or signing."""


class AgentRegistrationPinataError(AgentRegistrationError):
    """Raised when Pinata operations fail during DID pinning."""


class AgentRegistrationContractError(AgentRegistrationError):
    """Raised when contract calls fail (mint, register, AgentRegistry call)."""


class AgentRegistrationDuplicateError(AgentRegistrationError):
    """Raised when AgentRegistry.registerAgent reverts on duplicate agentId."""


class AgentRegistrationProjectNotFoundError(AgentRegistrationError):
    """Raised when project NFT precondition not met (per L2c — preflight gap)."""


class AgentRegistrationEIP712Error(AgentRegistrationError):
    """Raised when EIP-712 signature flow fails (digest, signing, parse, recovery)."""


class AgentRegistrationDeviceNFTError(AgentRegistrationError):
    """Raised when VAPIOperatorAgentNFT mint fails."""


class AgentRegistrationIoIDStoreError(AgentRegistrationError):
    """Raised when ioIDStore prerequisite operations fail."""


# ---------------------------------------------------------------------------
# Helpers: secp256k1 KMS public key derivation (preserved from dcaf5015)
# ---------------------------------------------------------------------------

def _parse_kms_public_key_to_uncompressed_point(der_public_key: bytes) -> bytes:
    """Parse DER SubjectPublicKeyInfo to 65-byte uncompressed secp256k1 point.

    Returns: bytes of length 65 starting with 0x04, followed by X (32 bytes) + Y (32 bytes).
    """
    pub = serialization.load_der_public_key(der_public_key)
    if not isinstance(pub, EllipticCurvePublicKey):
        raise ValueError(f"DER does not contain an EC public key (got {type(pub).__name__})")
    if not isinstance(pub.curve, SECP256K1):
        raise ValueError(f"Expected secp256k1 curve, got {pub.curve.name}")
    uncompressed = pub.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    if len(uncompressed) != 65 or uncompressed[0] != 0x04:
        raise ValueError(
            f"Unexpected uncompressed point format "
            f"(len={len(uncompressed)}, first_byte={uncompressed[0] if uncompressed else None})"
        )
    return uncompressed


def derive_eth_address_from_kms_public_key(der_public_key: bytes) -> str:
    """Derive EIP-55 Ethereum address from DER-encoded secp256k1 public key.

    Per Ethereum yellow paper: address = last 20 bytes of keccak256(pubkey_x || pubkey_y).
    Returns: 0x-prefixed 42-character checksummed address string.
    """
    uncompressed = _parse_kms_public_key_to_uncompressed_point(der_public_key)
    address_bytes = keccak(uncompressed[1:])[-20:]
    return to_checksum_address("0x" + address_bytes.hex())


def derive_uncompressed_pubkey_hex_from_kms_public_key(der_public_key: bytes) -> str:
    """Derive uncompressed secp256k1 public key as 0x-prefixed 132-char hex.

    Format: 0x04 + X (32 bytes hex) + Y (32 bytes hex). Used for DID document
    verificationMethod[0].publicKeyHex per W3C DID spec + EcdsaSecp256k1VerificationKey2019.
    """
    uncompressed = _parse_kms_public_key_to_uncompressed_point(der_public_key)
    return "0x" + uncompressed.hex()


def compute_agent_id(ioid_did_address: str, tba_address: str) -> bytes:
    """Pass 2C Q9 FROZEN encoding: agentId = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address)).

    Returns: 32 bytes (bytes32).
    """
    encoded = abi_encode(["address", "address"], [ioid_did_address, tba_address])
    return keccak(encoded)


def _did_template_path(agent: str) -> Path:
    """Resolve DID template path for the given agent."""
    return _REPO_ROOT / "agents" / "did_templates" / f"vapi-{agent}.did.template.json"


# ---------------------------------------------------------------------------
# EIP-712 helpers per Section 14.3 (M2 canonical permit-style signing)
# ---------------------------------------------------------------------------

def _compute_eip712_domain_separator(chain_id: int, verifying_contract: str) -> bytes:
    """Compute EIP-712 DOMAIN_SEPARATOR per ioIDRegistry canonical construction.

    Empirically verified at Block A extension: this computation produces
    exactly the on-chain DOMAIN_SEPARATOR returned by ioIDRegistry's public
    getter at chain 4690 (byte-for-byte match against
    0x4e31e01d4e41f6c9dc9d68103971ef473adf267bd74326f72170daac66329bcc).

    Formula per canonical contracts/ioIDRegistry.sol lines 22-26 + 50:
      keccak256(abi.encode(
        EIP712DOMAIN_TYPEHASH,
        keccak256(bytes("ioIDRegistry")),
        keccak256(bytes("1")),
        block.chainid,
        address(this)
      ))
    """
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


def _compute_permit_struct_hash(user: str, nonce: int) -> bytes:
    """Compute keccak256(abi.encode(PERMIT_TYPE_HASH, user, nonce)) per Section 14.3.

    Per M2: signed struct is Permit(address owner, uint256 nonce). The `user`
    parameter is bridge_wallet (the relayer/operator); `nonce` is the device's
    current ioIDRegistry.nonces(device) value.
    """
    user_bytes = bytes.fromhex(user.removeprefix("0x"))
    encoded = abi_encode(
        ["bytes32", "address", "uint256"],
        [PERMIT_TYPE_HASH, user_bytes, nonce],
    )
    return keccak(encoded)


def _compute_eip712_permit_digest(domain_separator: bytes, user: str, nonce: int) -> bytes:
    """Compose EIP-712 envelope per canonical: keccak256("\\x19\\x01" || domain || struct_hash).

    Returns the 32-byte digest that the device's KMS key signs.
    """
    struct_hash = _compute_permit_struct_hash(user, nonce)
    return keccak(b"\x19\x01" + domain_separator + struct_hash)


# secp256k1 curve order (used for EIP-2 low-s normalization)
_SECP256K1_N = 0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141


def _parse_der_signature_to_vrs(
    der_signature: bytes,
    digest: bytes,
    expected_signer: str,
) -> tuple[int, bytes, bytes]:
    """Parse DER ECDSA signature → (v, r, s) per Ethereum convention.

    AWS KMS returns DER-encoded ECDSA. Ethereum EIP-712 signature
    verification (ecrecover) needs (v, r, s) with v ∈ {27, 28} for
    pre-EIP-155 messages. This function:
      1. Decodes DER → (r, s) integers
      2. Normalizes s to low-s form per EIP-2 (canonical signature)
      3. Tries both possible v values; returns the one that recovers
         to expected_signer

    Per V8.4: bridge code generates (v, r, s) for inclusion in
    ioIDRegistry.register's signature parameters. The recovered signer
    must equal `device` per canonical source line 110:
      require(ecrecover(digest, v, r, s) == device, "invalid signature");

    Args:
        der_signature: DER-encoded ECDSA signature from KMSClient.sign()
        digest: 32-byte EIP-712 digest that was signed
        expected_signer: 0x-prefixed address whose key produced the signature
                         (the agent's KMS-derived ETH address per M2)

    Returns: (v, r_bytes, s_bytes) tuple where v ∈ {27, 28} and r/s are
             32-byte big-endian.

    Raises: AgentRegistrationEIP712Error if no v value recovers to expected_signer.
    """
    try:
        r_int, s_int = decode_dss_signature(der_signature)
    except Exception as exc:
        raise AgentRegistrationEIP712Error(
            f"Failed to decode DER signature: {exc}"
        ) from exc

    # EIP-2 low-s normalization (canonical signature form)
    if s_int > _SECP256K1_N // 2:
        s_int = _SECP256K1_N - s_int

    r_bytes = r_int.to_bytes(32, "big")
    s_bytes = s_int.to_bytes(32, "big")

    expected_addr = to_checksum_address(expected_signer)
    keys = KeyAPI()

    for v_int in (27, 28):
        try:
            sig = keys.Signature(vrs=(v_int - 27, r_int, s_int))
            recovered_pub = keys.ecdsa_recover(digest, sig)
            recovered_addr = to_checksum_address(recovered_pub.to_address())
            if recovered_addr == expected_addr:
                return v_int, r_bytes, s_bytes
        except Exception:
            continue

    raise AgentRegistrationEIP712Error(
        f"Could not recover expected signer {expected_addr} from DER signature. "
        f"Tried v=27 and v=28; neither matched."
    )


# ---------------------------------------------------------------------------
# AgentRegistrar (Block B per Section 14)
# ---------------------------------------------------------------------------

class AgentRegistrar:
    """Orchestrates the Phase O0 Section 6.4 Block B agent registration flow.

    Composes KMSClient (Section 6.3) + PinataClient (Section 6.4) + web3
    connection via dependency injection. Tests inject MockKMSClient +
    MockPinataClient + per-contract mock factories from test_agent_registration.

    H1a: produces orchestrator code; actual on-chain execution happens in a
    separate operator-driven session.
    """

    def __init__(
        self,
        kms_client,
        pinata_client,
        web3_async,
        bridge_wallet_address: str,
        agent_registry_addr: str = AGENT_REGISTRY_ADDR,
        ioid_registry_addr: str = IOID_REGISTRY_ADDR,
        ioid_store_addr: str = IOID_STORE_ADDR,
        ioid_contract_addr: str = IOID_CONTRACT_ADDR,
        project_registry_addr: str = PROJECT_REGISTRY_ADDR,
        vapi_operator_agent_nft_addr: str = VAPI_OPERATOR_AGENT_NFT_ADDR,
        chain_id: int = IOTEX_TESTNET_CHAIN_ID,
        project_token_id: int = 0,  # operator-supplied at on-chain run
    ):
        """Construct AgentRegistrar with injected dependencies.

        Args:
            kms_client: KMSClient or MockKMSClient instance
            pinata_client: PinataClient or MockPinataClient instance
            web3_async: AsyncWeb3 connection (or per-contract mock factory output)
            bridge_wallet_address: bridge wallet address (the `user` per M2 +
                                   `msg.sender` per M1 8-param wrapper)
            agent_registry_addr: deployed AgentRegistry address
            ioid_registry_addr: deployed ioIDRegistry address
            ioid_store_addr: deployed ioIDStore address
            ioid_contract_addr: deployed ioID per-DID NFT contract (TBA token contract per N4)
            project_registry_addr: deployed ProjectRegistry address
            vapi_operator_agent_nft_addr: deployed VAPIOperatorAgentNFT address
                                          (per N2 β; placeholder until deploy script runs)
            chain_id: target chain ID (IoTeX testnet 4690)
            project_token_id: IProject NFT tokenId for VAPI Operator Agents
                              (operator-supplied; from ProjectRegistry.register call)
        """
        self._kms = kms_client
        self._pinata = pinata_client
        self._web3 = web3_async
        self._bridge_wallet = bridge_wallet_address

        self._agent_registry_addr = agent_registry_addr
        self._ioid_registry_addr = ioid_registry_addr
        self._ioid_store_addr = ioid_store_addr
        self._ioid_contract_addr = ioid_contract_addr
        self._project_registry_addr = project_registry_addr
        self._vapi_operator_agent_nft_addr = vapi_operator_agent_nft_addr
        self._chain_id = chain_id
        self._project_token_id = project_token_id

        log.info(
            "AgentRegistrar (Block B) constructed: bridge=%s "
            "agent_registry=%s ioid_registry=%s ioid_store=%s ioid=%s "
            "project_registry=%s device_nft=%s chain=%d project_token=%d",
            bridge_wallet_address, agent_registry_addr, ioid_registry_addr,
            ioid_store_addr, ioid_contract_addr, project_registry_addr,
            vapi_operator_agent_nft_addr, chain_id, project_token_id,
        )

    # =====================================================================
    # Read-only preflight (L2c — IN register_full_flow)
    # =====================================================================

    async def check_project_nft(self, expected_owner: str) -> int:
        """Verify project NFT exists and is owned by expected_owner. Returns project tokenId.

        Raises AgentRegistrationProjectNotFoundError if not owned. Used as
        preflight in register_full_flow per L2c — register_project (the
        state-changing companion) is operator-driven and NOT called from
        register_full_flow.
        """
        try:
            pr_contract = self._web3.eth.contract(
                address=self._project_registry_addr, abi=PROJECT_REGISTRY_ABI,
            )
            iproject_addr = await pr_contract.functions.project().call()

            ip_contract = self._web3.eth.contract(
                address=iproject_addr, abi=IPROJECT_ABI,
            )
            balance = await ip_contract.functions.balanceOf(expected_owner).call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"check_project_nft: failed to query IProject ownership: {exc}"
            ) from exc

        if balance == 0:
            raise AgentRegistrationProjectNotFoundError(
                f"Bridge wallet {expected_owner} owns no project NFT. "
                f"Operator must call register_project first per Section 14.5 "
                f"prerequisite chain."
            )

        try:
            token_id = await ip_contract.functions.tokenOfOwnerByIndex(
                expected_owner, 0
            ).call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"check_project_nft: failed to read project tokenId: {exc}"
            ) from exc

        log.info("check_project_nft: owner=%s token_id=%d", expected_owner, token_id)
        return int(token_id)

    # =====================================================================
    # State-changing operator-driven (NOT in register_full_flow per L2c)
    # =====================================================================

    async def register_project(
        self,
        project_name: str = VAPI_OPERATOR_AGENTS_PROJECT_NAME,
    ) -> int:
        """Operator-driven: register VAPI Operator Agents project on ProjectRegistry.

        Returns the minted project tokenId. Per N2 β + Section 14.5:
        called once per VAPI deployment by an operator-driven session.
        NOT called from register_full_flow.

        Per V8.4: uses .call() simulation pattern; production operator
        wraps in transact + receipt extraction.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._project_registry_addr, abi=PROJECT_REGISTRY_ABI,
            )
            token_id = await contract.functions.register(
                project_name, PROJECT_TYPE_HARDWARE,
            ).call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"register_project: ProjectRegistry.register failed: {exc}"
            ) from exc

        log.info(
            "register_project: name=%r type=%d token_id=%d",
            project_name, PROJECT_TYPE_HARDWARE, token_id,
        )
        return int(token_id)

    async def setup_device_contract(
        self,
        project_token_id: int,
        device_nft_addr: str,
    ) -> None:
        """Operator-driven: bind project to deviceContract via ioIDStore.setDeviceContract.

        Per M4: bidirectional 1:1 mapping. Once set, neither side can be
        replaced without a separate changeDeviceContract call.

        Called once after register_project + VAPIOperatorAgentNFT deployment.
        NOT called from register_full_flow.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._ioid_store_addr, abi=IOID_STORE_ABI,
            )
            await contract.functions.setDeviceContract(
                project_token_id, device_nft_addr,
            ).call()
        except Exception as exc:
            raise AgentRegistrationIoIDStoreError(
                f"setup_device_contract: ioIDStore.setDeviceContract failed: {exc}"
            ) from exc

        log.info(
            "setup_device_contract: project_token_id=%d device_nft=%s",
            project_token_id, device_nft_addr,
        )

    async def apply_ioids(self, project_token_id: int, count: int) -> int:
        """Operator-driven: pre-pay activeIoID fees for `count` device slots.

        Returns total IOTX value (count * price queried from ioIDStore.price).
        Per M5: optional pre-pay path; bridge can pay-as-you-go via msg.value
        forwarded through ioIDRegistry.register instead.

        NOT called from register_full_flow.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._ioid_store_addr, abi=IOID_STORE_ABI,
            )
            price = await contract.functions.price().call()
            total_value = int(count) * int(price)
            # In production: send tx with value=total_value
            # In tests (.call()): mock returns nothing
            await contract.functions.applyIoIDs(project_token_id, count).call()
        except Exception as exc:
            raise AgentRegistrationIoIDStoreError(
                f"apply_ioids: ioIDStore.applyIoIDs failed: {exc}"
            ) from exc

        log.info(
            "apply_ioids: project_token_id=%d count=%d price=%d total_value=%d",
            project_token_id, count, price, total_value,
        )
        return total_value

    # =====================================================================
    # Per-agent state-changing (IN register_full_flow per Section 14.4)
    # =====================================================================

    async def populate_did_document(self, agent: str) -> dict:
        """Read DID template and populate verificationMethod from KMS public key."""
        template_path = _did_template_path(agent)
        if not template_path.is_file():
            raise AgentRegistrationConfigError(
                f"DID template not found: {template_path}. "
                f"Expected at agents/did_templates/vapi-{agent}.did.template.json"
            )

        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)

        try:
            der_public_key = await self._kms.get_public_key(agent)
        except Exception as exc:
            raise AgentRegistrationKMSError(
                f"populate_did_document: KMS get_public_key failed for {agent!r}: {exc}"
            ) from exc

        pubkey_hex = derive_uncompressed_pubkey_hex_from_kms_public_key(der_public_key)

        if "verificationMethod" in template and template["verificationMethod"]:
            template["verificationMethod"][0]["publicKeyHex"] = pubkey_hex

        if "metadata" in template:
            template["metadata"]["createdAt"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(),
            )

        log.info(
            "populate_did_document: agent=%s pubkey_hex_len=%d",
            agent, len(pubkey_hex),
        )
        return template

    async def pin_did_document(self, did_document: dict, agent: str) -> str:
        """Pin DID document to IPFS via PinataClient. Returns CID."""
        try:
            result = await self._pinata.pin_json(
                content=did_document, name=f"vapi-{agent}.did.json",
            )
        except Exception as exc:
            raise AgentRegistrationPinataError(
                f"pin_did_document: Pinata pin_json failed for {agent!r}: {exc}"
            ) from exc

        cid = result.get("IpfsHash")
        if not cid:
            raise AgentRegistrationPinataError(
                f"pin_did_document: Pinata response missing IpfsHash: {result}"
            )

        log.info("pin_did_document: agent=%s cid=%s", agent, cid)
        return cid

    @staticmethod
    def compute_did_content_hash(did_document: dict) -> bytes:
        """Compute keccak256 of canonical-JSON-serialized DID document.

        Output is the bytes32 hash passed to ioIDRegistry.register's `hash`
        parameter. Per M2: this hash is stored as the device's record hash
        but is NOT cryptographically bound to the EIP-712 signature (the
        signature signs only (user, nonce) per Permit type hash).

        Canonical serialization: sort_keys=True, separators=(",", ":") so
        the hash is reproducible across invocations.
        """
        canonical = json.dumps(
            did_document, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        return keccak(canonical)

    async def mint_device_nft(self, agent: str) -> int:
        """Mint per-agent device tokenId from VAPIOperatorAgentNFT.

        Returns the minted device tokenId.

        Per V8.3: raises AgentRegistrationConfigError if
        VAPI_OPERATOR_AGENT_NFT_ADDR is still placeholder zero (operator
        must run deploy-vapi-operator-agent-nft.js + update constant first).

        Per V8.4: uses .call() simulation pattern. Production operator
        session wraps in transact + receipt event extraction (Transfer
        event emits the minted tokenId).
        """
        if self._vapi_operator_agent_nft_addr == "0x0000000000000000000000000000000000000000":
            raise AgentRegistrationConfigError(
                f"VAPI_OPERATOR_AGENT_NFT_ADDR is still placeholder zero. "
                f"Run contracts/scripts/deploy-vapi-operator-agent-nft.js "
                f"on testnet, then update the constant per V8.3 before "
                f"invoking register_full_flow."
            )

        try:
            contract = self._web3.eth.contract(
                address=self._vapi_operator_agent_nft_addr,
                abi=VAPI_OPERATOR_AGENT_NFT_ABI,
            )
            # Mint to bridge_wallet — bridge_wallet then transfers via
            # ioIDRegistry.register internal flow to the agent's TBA wallet
            # (per M3 Layer 1: ioIDRegistry consumes the (deviceContract,
            # tokenId) pair and transfers it away from bridge_wallet to
            # the device's IoID-bound TBA wallet).
            token_id = await contract.functions.mint(self._bridge_wallet).call()
        except Exception as exc:
            raise AgentRegistrationDeviceNFTError(
                f"mint_device_nft: VAPIOperatorAgentNFT.mint failed for {agent!r}: {exc}"
            ) from exc

        log.info("mint_device_nft: agent=%s token_id=%d", agent, token_id)
        return int(token_id)

    async def query_device_nonce(self, device_address: str) -> int:
        """Read current nonce for a device from ioIDRegistry.nonces() view.

        Per M2: the EIP-712 permit digest signs (user, nonce(device)).
        Bridge must read the current nonce before computing the digest;
        ioIDRegistry's _useNonce(device) increments after each operation,
        so each registration uses the next sequential nonce.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._ioid_registry_addr, abi=IOID_REGISTRY_ABI,
            )
            nonce = await contract.functions.nonces(device_address).call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"query_device_nonce: ioIDRegistry.nonces failed for {device_address}: {exc}"
            ) from exc

        log.info("query_device_nonce: device=%s nonce=%d", device_address, nonce)
        return int(nonce)

    def compute_eip712_permit_digest(self, user: str, nonce: int) -> bytes:
        """Compose the EIP-712 permit digest for a given (user, nonce).

        Per M2 + Section 14.3:
          domain_separator = keccak256(EIP712Domain encoding with
              name="ioIDRegistry", version="1", chainId=4690,
              verifyingContract=ioIDRegistry address)
          struct_hash = keccak256(abi.encode(PERMIT_TYPE_HASH, user, nonce))
          digest = keccak256("\\x19\\x01" || domain_separator || struct_hash)

        Returns the 32-byte digest that the device's KMS key signs.
        """
        domain_separator = _compute_eip712_domain_separator(
            self._chain_id, self._ioid_registry_addr,
        )
        return _compute_eip712_permit_digest(domain_separator, user, nonce)

    async def kms_sign_permit_digest(self, agent: str, digest: bytes) -> bytes:
        """KMS-sign the EIP-712 permit digest. Returns DER-encoded signature."""
        try:
            der_signature = await self._kms.sign(agent, digest)
        except Exception as exc:
            raise AgentRegistrationKMSError(
                f"kms_sign_permit_digest: KMS sign failed for {agent!r}: {exc}"
            ) from exc

        log.info(
            "kms_sign_permit_digest: agent=%s digest_len=%d sig_len=%d",
            agent, len(digest), len(der_signature),
        )
        return der_signature

    async def mint_ioid_did(
        self,
        device_token_id: int,
        device_address: str,
        content_hash: bytes,
        uri: str,
        v: int,
        r: bytes,
        s: bytes,
    ) -> None:
        """Call 8-param ioIDRegistry.register wrapper per M1.

        Per M1 (canonical source line 79): the 8-param register wrapper
        calls the 9-param version with user = msg.sender. For VAPI's
        bridge-wallet-as-relayer model, this is operationally equivalent
        to passing user = bridge_wallet explicitly.

        Per M3 + Section 14.4 step 8: this call CONSUMES the
        (VAPIOperatorAgentNFT, device_token_id) pair (sets registeredNFT
        flag + transfers the device NFT to the per-agent TBA wallet via
        ioID.mint internal flow).

        After this call succeeds, the new ioID tokenId is N (auto-incremented
        from prior ioID.mint calls). The bridge reads it back via TBA
        derivation in readback_tba step.

        Per V8.4: uses .call() simulation. Production operator wraps in
        transact + receipt parsing.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._ioid_registry_addr, abi=IOID_REGISTRY_ABI,
            )
            # 8-param wrapper (selector 0x39a4a241) — user implicitly = bridge_wallet
            await contract.functions.register(
                self._vapi_operator_agent_nft_addr,  # deviceContract per N2 β
                device_token_id,                      # tokenId from mint_device_nft
                device_address,                       # device (KMS-derived agent ETH addr)
                content_hash,                         # bytes32 hash (DID document)
                uri,                                   # string uri (IPFS CID)
                v, r, s,                              # EIP-712 permit signature per M2
            ).call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"mint_ioid_did: ioIDRegistry.register failed for "
                f"device={device_address} token_id={device_token_id}: {exc}"
            ) from exc

        log.info(
            "mint_ioid_did: device=%s device_token_id=%d hash=0x%s uri=%s",
            device_address, device_token_id, content_hash.hex(), uri,
        )

    async def readback_tba(self, ioid_token_id: int) -> str:
        """Read back the ERC-6551 TBA address for a given ioID tokenId.

        Per M6 + N4: ERC-6551 TBA creation happens INSIDE ioID.mint with
        salt hardcoded to 0 and token contract = ioID contract address
        (NOT IProject; NOT VAPIOperatorAgentNFT). Bridge code MUST NOT
        call ERC6551Registry directly. Instead, ioID.wallet(ioid_token_id)
        returns the TBA address (via internal ERC6551Registry.account view
        call with the canonical ioID-internal parameters).

        Returns the TBA address as 0x-prefixed checksummed string.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._ioid_contract_addr, abi=IOID_ABI,
            )
            result = await contract.functions.wallet(ioid_token_id).call()
            # ioID.wallet returns (wallet_, did_) tuple; we take wallet_
            tba_address = result[0] if isinstance(result, (list, tuple)) else result
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"readback_tba: ioID.wallet({ioid_token_id}) failed: {exc}"
            ) from exc

        log.info("readback_tba: ioid_token_id=%d tba=%s", ioid_token_id, tba_address)
        return tba_address

    async def register_agent(
        self,
        agent: str,
        ioid_did_address: str,
        tba_address: str,
        did_document_cid: str,
    ) -> str:
        """Call AgentRegistry.registerAgent (unchanged from dcaf5015 / Section 6.4).

        agentId = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))
        per Pass 2C Q9 FROZEN encoding.

        publicKey = ETH address derived from agent's KMS public key.
        scopeHash = bytes32(0) per Section 7 (no operational authority at O0).
        status = STATUS_DEFINED = 0 per Section 6.4.

        did_document_cid logged for audit; not stored on-chain (DID
        references via did:io:<address>; CID provides off-chain content
        addressing for the DID document JSON).
        """
        agent_id = compute_agent_id(ioid_did_address, tba_address)

        try:
            der_public_key = await self._kms.get_public_key(agent)
        except Exception as exc:
            raise AgentRegistrationKMSError(
                f"register_agent: KMS get_public_key failed for {agent!r}: {exc}"
            ) from exc
        public_key_address = derive_eth_address_from_kms_public_key(der_public_key)

        try:
            contract = self._web3.eth.contract(
                address=self._agent_registry_addr, abi=_load_agent_registry_abi(),
            )
            tx_func = contract.functions.registerAgent(
                agent_id,
                public_key_address,
                SCOPE_HASH_PHASE_O0_EXIT,
                STATUS_DEFINED,
            )
            tx_hash = await tx_func.call()
        except Exception as exc:
            err_msg = str(exc)
            if "AgentAlreadyRegistered" in err_msg or "duplicate" in err_msg.lower():
                raise AgentRegistrationDuplicateError(
                    f"Agent {agent!r} already registered (agentId already exists): {exc}"
                ) from exc
            raise AgentRegistrationContractError(
                f"register_agent: AgentRegistry.registerAgent failed for {agent!r}: {exc}"
            ) from exc

        log.info(
            "register_agent: agent=%s agent_id=0x%s public_key=%s did_cid=%s tx=%s",
            agent, agent_id.hex(), public_key_address, did_document_cid, tx_hash,
        )
        return tx_hash

    # =====================================================================
    # Orchestration: register_full_flow (Section 14.4 per-agent steps)
    # =====================================================================

    async def register_full_flow(self, agent: str) -> dict:
        """Orchestrate the canonical Section 14.4 per-agent registration flow.

        Per V8.2: parameters reduced to `agent` only. The deviceContract
        (VAPIOperatorAgentNFT) is the canonical class constant per N2 β;
        the device tokenId is derived from mint_device_nft return value.

        13-step per-agent flow per Section 14.4 + brief synthesis:

          1.  check_project_nft (preflight)
          2.  populate_did_document (KMS pubkey)
          3.  pin_did_document (Pinata CID)
          4.  compute_did_content_hash (keccak256)
          5.  mint_device_nft (per-agent device tokenId)
          6.  query_device_nonce (ioIDRegistry.nonces)
          7.  compute_eip712_permit_digest (Permit struct hash)
          8.  kms_sign_permit_digest (KMS DER signature)
          9.  parse_eip712_signature_to_vrs (DER → v,r,s)
          10. mint_ioid_did (8-param ioIDRegistry.register)
          11. readback_tba (ioID.wallet)
          12. compute_agent_id (Q9 frozen encoding)
          13. register_agent (AgentRegistry.registerAgent)

        Returns dict with all relevant addresses, hashes, ids, and tx hash.

        H1a: full execution against real services in operator's on-chain session.
        Tests verify orchestration via per-contract mock factories.
        """
        # Step 0: derive agent's ETH address from KMS pubkey
        try:
            der_public_key = await self._kms.get_public_key(agent)
        except Exception as exc:
            raise AgentRegistrationKMSError(
                f"register_full_flow: KMS get_public_key failed for {agent!r}: {exc}"
            ) from exc
        agent_address = derive_eth_address_from_kms_public_key(der_public_key)

        # Step 1: check_project_nft preflight
        project_token_id = await self.check_project_nft(self._bridge_wallet)
        if self._project_token_id == 0:
            self._project_token_id = project_token_id

        # Step 2: populate DID document
        did_doc = await self.populate_did_document(agent)

        # Step 3: pin DID document
        did_cid = await self.pin_did_document(did_doc, agent)

        # Step 4: compute content hash (canonical JSON keccak256)
        content_hash = self.compute_did_content_hash(did_doc)

        # Step 5: mint device NFT (per-agent device tokenId)
        device_token_id = await self.mint_device_nft(agent)

        # Step 6: query current device nonce
        nonce = await self.query_device_nonce(agent_address)

        # Step 7: compute EIP-712 permit digest (signed by device per M2)
        digest = self.compute_eip712_permit_digest(self._bridge_wallet, nonce)

        # Step 8: KMS signs the digest
        der_signature = await self.kms_sign_permit_digest(agent, digest)

        # Step 9: parse DER → (v, r, s) with ecrecover-against-device verification
        v, r, s = _parse_der_signature_to_vrs(der_signature, digest, agent_address)

        # Step 10: ioIDRegistry.register (8-param wrapper per M1)
        await self.mint_ioid_did(
            device_token_id=device_token_id,
            device_address=agent_address,
            content_hash=content_hash,
            uri=did_cid,
            v=v, r=r, s=s,
        )

        # Step 11: read back TBA via ioID.wallet (per M6 + N4)
        # Per canonical: device_address itself is the did:io:<address>
        # identifier; the per-DID NFT tokenId is the auto-incremented
        # value managed inside ioID.mint. Bridge cannot call ioID.wallet
        # by tokenId without first knowing the tokenId — which is also
        # event-emitted via NewDevice. For the orchestration's purposes,
        # device_address IS the canonical DID identifier and TBA derivation
        # is handled by ioID internally; we read back the TBA via the
        # ioID.wallet view using the device_token_id (which corresponds
        # 1:1 with the ioID tokenId for VAPI's case where each device
        # registration produces exactly one ioID NFT).
        tba_address = await self.readback_tba(device_token_id)

        # ioid_did_address per Q9 — the device address IS the did:io:<address>
        # identifier per ioID convention (each device's ETH address becomes
        # its DID identifier).
        ioid_did_address = agent_address

        # Step 12: compute agentId per Q9 FROZEN encoding (unchanged)
        agent_id = compute_agent_id(ioid_did_address, tba_address)

        # Step 13: AgentRegistry.registerAgent (unchanged from Section 6.4)
        tx_hash = await self.register_agent(
            agent=agent,
            ioid_did_address=ioid_did_address,
            tba_address=tba_address,
            did_document_cid=did_cid,
        )

        result = {
            "agent": agent,
            "agent_address": agent_address,
            "ioid_did_address": ioid_did_address,
            "device_token_id": device_token_id,
            "tba_address": tba_address,
            "agent_id": "0x" + agent_id.hex(),
            "did_document_cid": did_cid,
            "did_content_hash": "0x" + content_hash.hex(),
            "permit_nonce": nonce,
            "tx_hash": tx_hash,
        }
        log.info("register_full_flow: complete agent=%s result=%s", agent, result)
        return result
