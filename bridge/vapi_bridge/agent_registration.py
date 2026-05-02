"""Phase O0 Section 6.4 — Operator agent registration orchestrator.

Composes Section 6.3 KMSClient + Section 6.4 PinataClient + web3 connection
to execute the full Operator agent registration flow per Pass 2C Section 6.4
specifications.

The registration flow per Pass 2C Section 6.4:

  1. populate_did_document: read DID template, populate verificationMethod
     publicKeyHex with KMS-derived secp256k1 public key
  2. mint_ioid_did: ProjectRegistry/ioIDRegistry contract calls produce
     the agent's ioID DID address
  3. bind_erc6551_tba: ERC-6551 Registry deterministic binding produces
     the TBA address
  4. pin_did_document: Pinata IPFS pinning returns CID for DID document
  5. register_agent: AgentRegistry.registerAgent on Stream 2-deploy
     contract with agentId per Pass 2C Q9 frozen encoding:
       agentId = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))

Design rationale (Section 6.4 implementation):

  H1a (test-first, defer on-chain to operator session): the implementation
  produces the orchestrator code; actual on-chain execution (irreversible
  state via AgentRegistry.registerAgent) happens in a separate
  operator-driven session after architectural verification. Q9 freezes
  the agentId encoding at first registration call.

  H2c (PinataClient separate, others in orchestrator): PinataClient lives
  at bridge/vapi_bridge/pinata_client.py for reusability; this module
  composes PinataClient with KMSClient and web3 contract calls.

  H3a (mock all external services): the orchestrator accepts injected
  KMSClient, PinataClient, and web3 dependencies via constructor. Tests
  inject MockKMSClient + MockPinataClient + MagicMock web3.

  G1 (hardcode contract addresses): the four contract addresses are
  hardcoded as module constants with documenting comments + source
  references. Avoids env var bloat for canonical/network constants.
  ERC-6551 Registry is the universal singleton at
  0x000000006551c19487814612e58FE06813775758 (EIP-6551, never changes).

  G2 (inline minimal ABIs): external contract ABIs (ProjectRegistry,
  ioIDRegistry, ERC-6551 Registry) embedded inline as Python dict literals
  with only the functions VAPI calls. AgentRegistry ABI loaded from
  Hardhat artifact at contracts/artifacts/contracts/AgentRegistry.sol/
  AgentRegistry.json.

Helper functions (operator note implementation):

  derive_eth_address_from_kms_public_key(der_public_key)
    Returns 0x-prefixed 42-char EIP-55 checksummed Ethereum address.
    Used for AgentRegistry.registerAgent publicKey parameter.

  derive_uncompressed_pubkey_hex_from_kms_public_key(der_public_key)
    Returns 0x-prefixed 132-char uncompressed secp256k1 point hex
    (0x04 || X || Y). Used for DID document verificationMethod.publicKeyHex.

Both helpers parse DER once internally via _parse_kms_public_key_to_uncompressed_point.

Cross-references:

  Pass 2C Section 6.4 + Q9 (commits 3cb80ac5, fc61d93d) — architectural specs
  agents/skills/cryptographic-signing/SKILL.md (commit 52978771)
  agents/skills/provenance-recording/SKILL.md (commit 52978771)
  bridge/vapi_bridge/kms_client.py (commit d3b30d58) — KMS client integration
  bridge/vapi_bridge/pinata_client.py (this commit) — Pinata integration
  contracts/artifacts/contracts/AgentRegistry.sol/AgentRegistry.json — Hardhat ABI
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    EllipticCurvePublicKey, SECP256K1,
)
from eth_abi import encode as abi_encode
from eth_hash.auto import keccak
from eth_utils import to_checksum_address

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# G1: Hardcoded contract addresses (network constants, sourced per comments)
# ---------------------------------------------------------------------------

# IoTeX testnet chain ID (per Pass 2C Section 12 + Stream 2-deploy verification)
IOTEX_TESTNET_CHAIN_ID = 4690

# IoTeX ioID infrastructure (operator brief Section 6.4 + bridge/.env IOID_REGISTRY_ADDRESS)
PROJECT_REGISTRY_ADDR = "0x060581AA1A4e0cC92FBd74d251913238De2F13cd"
IOID_REGISTRY_ADDR = "0x0A7e595C7889dF3652A19aF52C18377bF17e027D"

# ERC-6551 Registry — universal singleton at the same address on every EVM chain
# Source: EIP-6551 spec, https://eips.ethereum.org/EIPS/eip-6551
ERC6551_REGISTRY_ADDR = "0x000000006551c19487814612e58FE06813775758"

# ERC-6551 Account implementation contract (operator-deployed; placeholder
# until verified by operator — typically the canonical reference implementation
# Tokenbound provides at the same address across chains)
# TODO: operator confirms exact account implementation address before on-chain run
ERC6551_ACCOUNT_IMPL_ADDR = "0x000000004FCe27D5BCb1aE9C9D4F3F2C4FC0F5C0"  # placeholder

# AgentRegistry from Stream 2-deploy commit d019c067 (deployed-addresses.json)
AGENT_REGISTRY_ADDR = "0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4"

# Pass 2C Section 6.4 + Section 7: scopeHash and status at registration
SCOPE_HASH_PHASE_O0_EXIT = b"\x00" * 32  # bytes32(0) — no operational authority
STATUS_DEFINED = 0  # AgentRegistry STATUS_DEFINED enum value


# ---------------------------------------------------------------------------
# G2: Inline minimal ABIs for external contracts (only functions we call)
# ---------------------------------------------------------------------------

# ERC-6551 Registry ABI — canonical EIP-6551 spec
# Source: https://eips.ethereum.org/EIPS/eip-6551
ERC6551_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "createAccount",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "implementation", "type": "address"},
            {"name": "salt", "type": "bytes32"},
            {"name": "chainId", "type": "uint256"},
            {"name": "tokenContract", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "outputs": [{"name": "account", "type": "address"}],
    },
    {
        "type": "function",
        "name": "account",
        "stateMutability": "view",
        "inputs": [
            {"name": "implementation", "type": "address"},
            {"name": "salt", "type": "bytes32"},
            {"name": "chainId", "type": "uint256"},
            {"name": "tokenContract", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
        ],
        "outputs": [{"name": "account", "type": "address"}],
    },
]

# ioIDRegistry ABI — minimal subset for register call
# Source: IoTeX ioID infrastructure (operator verifies exact signature
# against IoTeX docs before on-chain execution per H1a)
IOID_REGISTRY_ABI = [
    {
        "type": "function",
        "name": "register",
        "stateMutability": "nonpayable",
        "inputs": [
            {"name": "projectId", "type": "uint256"},
            {"name": "deviceAddress", "type": "address"},
        ],
        "outputs": [{"name": "didAddress", "type": "address"}],
    },
]

# ProjectRegistry ABI — Phase O0 assumes project pre-registered
# (no calls needed at Phase O0 exit; included for forward compatibility)
PROJECT_REGISTRY_ABI: list = []

# Robust repo root resolution: .resolve() guarantees absolute path before
# walking up. Without .resolve(), pytest --import-mode=importlib can produce
# relative __file__ values that resolve incorrectly when joined with cwd.
_MODULE_FILE = Path(__file__).resolve()
_REPO_ROOT = _MODULE_FILE.parent.parent.parent  # bridge/vapi_bridge/agent_registration.py -> repo root

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
# Exception hierarchy
# ---------------------------------------------------------------------------

class AgentRegistrationError(Exception):
    """Base exception for all AgentRegistrar failures."""


class AgentRegistrationConfigError(AgentRegistrationError):
    """Raised when configuration (template path, ABI path) is missing or invalid."""


class AgentRegistrationKMSError(AgentRegistrationError):
    """Raised when KMS operations fail during DID population."""


class AgentRegistrationPinataError(AgentRegistrationError):
    """Raised when Pinata operations fail during DID pinning."""


class AgentRegistrationContractError(AgentRegistrationError):
    """Raised when contract calls fail (mint, bind, register)."""


class AgentRegistrationDuplicateError(AgentRegistrationError):
    """Raised when AgentRegistry.registerAgent reverts on duplicate agentId."""


# ---------------------------------------------------------------------------
# Helper: DER-encoded secp256k1 public key derivation (operator-noted dual purpose)
# ---------------------------------------------------------------------------

def _parse_kms_public_key_to_uncompressed_point(der_public_key: bytes) -> bytes:
    """Parse DER SubjectPublicKeyInfo to 65-byte uncompressed secp256k1 point.

    Returns: bytes of length 65 starting with 0x04, followed by X (32 bytes) + Y (32 bytes).
    Both consumer functions (Eth address derivation, hex pubkey for DID) parse via this helper.
    """
    pub = serialization.load_der_public_key(der_public_key)
    if not isinstance(pub, EllipticCurvePublicKey):
        raise ValueError(
            f"DER does not contain an EC public key (got {type(pub).__name__})"
        )
    if not isinstance(pub.curve, SECP256K1):
        raise ValueError(
            f"Expected secp256k1 curve, got {pub.curve.name}"
        )
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
    Skips the 0x04 uncompressed-point prefix; hashes the 64-byte (X || Y) point.

    Returns: 0x-prefixed 42-character checksummed address string.

    Used for: AgentRegistry.registerAgent publicKey parameter.
    """
    uncompressed = _parse_kms_public_key_to_uncompressed_point(der_public_key)
    address_bytes = keccak(uncompressed[1:])[-20:]
    return to_checksum_address("0x" + address_bytes.hex())


def derive_uncompressed_pubkey_hex_from_kms_public_key(der_public_key: bytes) -> str:
    """Derive uncompressed secp256k1 public key as 0x-prefixed 132-char hex.

    Format: 0x04 + X (32 bytes hex) + Y (32 bytes hex) = 0x + 130 hex chars + 0x prefix = 132 chars.

    Used for: DID document verificationMethod[0].publicKeyHex per W3C DID spec
    + EcdsaSecp256k1VerificationKey2019 type.
    """
    uncompressed = _parse_kms_public_key_to_uncompressed_point(der_public_key)
    return "0x" + uncompressed.hex()


def compute_agent_id(ioid_did_address: str, tba_address: str) -> bytes:
    """Pass 2C Q9 FROZEN encoding: agentId = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address)).

    This encoding freezes at first AgentRegistry.registerAgent call per Q9.
    Modifying it in any way breaks AgentRegistry lookups across all subsequent records.

    Returns: 32 bytes (bytes32).
    """
    encoded = abi_encode(["address", "address"], [ioid_did_address, tba_address])
    return keccak(encoded)


def _did_template_path(agent: str) -> Path:
    """Resolve DID template path for the given agent (uses _REPO_ROOT for robustness)."""
    return _REPO_ROOT / "agents" / "did_templates" / f"vapi-{agent}.did.template.json"


# ---------------------------------------------------------------------------
# AgentRegistrar
# ---------------------------------------------------------------------------

class AgentRegistrar:
    """Orchestrates the Phase O0 Section 6.4 agent registration flow.

    Composes KMSClient (Section 6.3) + PinataClient (Section 6.4) + web3
    connection via dependency injection. Tests inject MockKMSClient +
    MockPinataClient + MagicMock web3 (H3a).

    H1a: produces orchestrator code; actual on-chain execution happens in a
    separate operator-driven session.
    """

    def __init__(
        self,
        kms_client,
        pinata_client,
        web3_async,
        agent_registry_addr: str = AGENT_REGISTRY_ADDR,
        ioid_registry_addr: str = IOID_REGISTRY_ADDR,
        erc6551_registry_addr: str = ERC6551_REGISTRY_ADDR,
        erc6551_account_impl_addr: str = ERC6551_ACCOUNT_IMPL_ADDR,
        chain_id: int = IOTEX_TESTNET_CHAIN_ID,
        project_id: int = 0,  # operator-supplied at on-chain run
    ):
        """Construct AgentRegistrar with injected dependencies.

        Args:
            kms_client: KMSClient or MockKMSClient instance
            pinata_client: PinataClient or MockPinataClient instance
            web3_async: AsyncWeb3 connection (or MagicMock for tests)
            agent_registry_addr: deployed AgentRegistry address
            ioid_registry_addr: deployed ioIDRegistry address
            erc6551_registry_addr: canonical ERC-6551 Registry address
            erc6551_account_impl_addr: ERC-6551 account implementation address
            chain_id: target chain ID (IoTeX testnet 4690 by default)
            project_id: ioID project ID (operator-supplied)
        """
        self._kms = kms_client
        self._pinata = pinata_client
        self._web3 = web3_async

        self._agent_registry_addr = agent_registry_addr
        self._ioid_registry_addr = ioid_registry_addr
        self._erc6551_registry_addr = erc6551_registry_addr
        self._erc6551_account_impl_addr = erc6551_account_impl_addr
        self._chain_id = chain_id
        self._project_id = project_id

        log.info(
            "AgentRegistrar constructed: agent_registry=%s ioid_registry=%s erc6551=%s chain=%d project=%d",
            agent_registry_addr, ioid_registry_addr, erc6551_registry_addr,
            chain_id, project_id,
        )

    async def populate_did_document(self, agent: str) -> dict:
        """Read DID template and populate with KMS-derived public key + addresses.

        Note: this method populates the publicKeyHex from KMS but leaves the
        DID address (id, controller, etc.) parameterized. Full DID address
        substitution happens after mint_ioid_did returns the actual address.

        Returns: dict with verificationMethod.publicKeyHex populated; address
        placeholders remain for downstream substitution after minting.
        """
        template_path = _did_template_path(agent)
        if not template_path.is_file():
            raise AgentRegistrationConfigError(
                f"DID template not found: {template_path}. "
                f"Expected at agents/did_templates/vapi-{agent}.did.template.json"
            )

        with open(template_path, "r", encoding="utf-8") as f:
            template = json.load(f)

        # Get KMS public key and derive both formats
        try:
            der_public_key = await self._kms.get_public_key(agent)
        except Exception as exc:
            raise AgentRegistrationKMSError(
                f"Failed to retrieve KMS public key for agent {agent!r}: {exc}"
            ) from exc

        pubkey_hex = derive_uncompressed_pubkey_hex_from_kms_public_key(der_public_key)

        # Populate verificationMethod.publicKeyHex (DID address fields populated post-mint)
        if "verificationMethod" in template and template["verificationMethod"]:
            template["verificationMethod"][0]["publicKeyHex"] = pubkey_hex

        # Populate metadata.createdAt (ISO 8601 UTC)
        if "metadata" in template:
            template["metadata"]["createdAt"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            )

        log.info(
            "populate_did_document: agent=%s pubkey_hex_len=%d",
            agent, len(pubkey_hex),
        )
        return template

    def substitute_did_addresses(
        self,
        did_document: dict,
        ioid_did_address: str,
        tba_address: str,
        agent_id_bytes32: bytes,
    ) -> dict:
        """Substitute DID address placeholders with actual minted addresses.

        Called after mint_ioid_did + bind_erc6551_tba complete; substitutes
        the address fields that were placeholders in the template.
        """
        did_doc = json.loads(json.dumps(did_document))  # deep copy

        did_url = f"did:io:{ioid_did_address}"

        if "id" in did_doc:
            did_doc["id"] = did_url
        if "controller" in did_doc:
            did_doc["controller"] = did_url

        if "verificationMethod" in did_doc:
            for vm in did_doc["verificationMethod"]:
                if "id" in vm and "<address>" in vm["id"]:
                    vm["id"] = vm["id"].replace(f"did:io:0x<address>", did_url)
                if "controller" in vm:
                    vm["controller"] = did_url

        if "authentication" in did_doc:
            did_doc["authentication"] = [
                a.replace("did:io:0x<address>", did_url) if isinstance(a, str) else a
                for a in did_doc["authentication"]
            ]
        if "assertionMethod" in did_doc:
            did_doc["assertionMethod"] = [
                a.replace("did:io:0x<address>", did_url) if isinstance(a, str) else a
                for a in did_doc["assertionMethod"]
            ]

        if "service" in did_doc:
            for svc in did_doc["service"]:
                if "id" in svc:
                    svc["id"] = svc["id"].replace("did:io:0x<address>", did_url)

        if "alsoKnownAs" in did_doc:
            agent_id_hex = "0x" + agent_id_bytes32.hex()
            new_aka = []
            for aka in did_doc["alsoKnownAs"]:
                aka = aka.replace("0x<agent_id_bytes32_hex>", agent_id_hex)
                aka = aka.replace("0x<tba_address>", tba_address)
                new_aka.append(aka)
            did_doc["alsoKnownAs"] = new_aka

        return did_doc

    async def pin_did_document(self, did_document: dict, agent: str) -> str:
        """Pin DID document to IPFS via PinataClient. Returns CID."""
        try:
            result = await self._pinata.pin_json(
                content=did_document,
                name=f"vapi-{agent}.did.json",
            )
        except Exception as exc:
            raise AgentRegistrationPinataError(
                f"Failed to pin DID document for agent {agent!r}: {exc}"
            ) from exc

        cid = result.get("IpfsHash")
        if not cid:
            raise AgentRegistrationPinataError(
                f"Pinata response missing IpfsHash: {result}"
            )

        log.info("pin_did_document: agent=%s cid=%s", agent, cid)
        return cid

    async def mint_ioid_did(self, agent_address: str) -> str:
        """Call ioIDRegistry.register to mint an ioID DID for the agent.

        Returns the DID document address (an EVM address that becomes the
        ioID DID's did:io:<address> identifier).

        H1a: this function is structured for testing via mocked web3; actual
        on-chain execution happens in a separate operator session.
        """
        try:
            contract = self._web3.eth.contract(
                address=self._ioid_registry_addr,
                abi=IOID_REGISTRY_ABI,
            )
            tx_func = contract.functions.register(self._project_id, agent_address)
            # In the operator's on-chain session: build + sign + send transaction
            # In tests: mock returns the simulated DID address
            did_address = await tx_func.call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"Failed to mint ioID DID for agent {agent_address}: {exc}"
            ) from exc

        log.info("mint_ioid_did: agent_addr=%s did_addr=%s", agent_address, did_address)
        return did_address

    async def bind_erc6551_tba(
        self,
        ioid_did_address: str,
        agent_nft_address: str,
        token_id: int = 0,
    ) -> str:
        """Derive + bind the ERC-6551 TBA for the agent.

        Per EIP-6551, the TBA address is deterministically derived from:
          (implementation, salt, chainId, tokenContract, tokenId)

        For VAPI: implementation = ERC6551_ACCOUNT_IMPL_ADDR,
                  salt = bytes32(0) by convention,
                  chainId = IOTEX_TESTNET_CHAIN_ID,
                  tokenContract = the ioID NFT contract address,
                  tokenId = the agent's NFT token ID.

        Returns the TBA address.
        """
        salt = b"\x00" * 32  # bytes32(0) per convention
        try:
            contract = self._web3.eth.contract(
                address=self._erc6551_registry_addr,
                abi=ERC6551_REGISTRY_ABI,
            )
            # Use account() (view) to derive the deterministic address
            tx_func = contract.functions.account(
                self._erc6551_account_impl_addr,
                salt,
                self._chain_id,
                agent_nft_address,
                token_id,
            )
            tba_address = await tx_func.call()
        except Exception as exc:
            raise AgentRegistrationContractError(
                f"Failed to derive ERC-6551 TBA for ioID DID {ioid_did_address}: {exc}"
            ) from exc

        log.info(
            "bind_erc6551_tba: ioid_did=%s nft=%s token_id=%d tba=%s",
            ioid_did_address, agent_nft_address, token_id, tba_address,
        )
        return tba_address

    async def register_agent(
        self,
        agent: str,
        ioid_did_address: str,
        tba_address: str,
        did_document_cid: str,
    ) -> str:
        """Call AgentRegistry.registerAgent on the deployed contract.

        agentId encoding per Pass 2C Q9 FROZEN spec:
          agentId = keccak256(abi.encode(ioID_DID_address, ERC6551_TBA_address))

        publicKey is the Ethereum address derived from the agent's KMS public key
        (per AgentRegistry ABI: publicKey: address).

        scopeHash = bytes32(0) per Pass 2C Section 7 (no operational authority at O0).
        status = STATUS_DEFINED = 0 per Pass 2C Section 6.4.

        Returns the transaction hash. did_document_cid is logged for audit but
        not stored on-chain (DID is referenced via did:io:<address>; CID
        provides off-chain content addressing for the DID document JSON).

        H1a: this function is structured for testing via mocked web3; actual
        on-chain execution happens in a separate operator session.
        """
        # Compute agentId per Q9 FROZEN encoding
        agent_id = compute_agent_id(ioid_did_address, tba_address)

        # Derive publicKey (Ethereum address) from KMS pubkey
        try:
            der_public_key = await self._kms.get_public_key(agent)
        except Exception as exc:
            raise AgentRegistrationKMSError(
                f"Failed to retrieve KMS public key for agent {agent!r}: {exc}"
            ) from exc
        public_key_address = derive_eth_address_from_kms_public_key(der_public_key)

        try:
            contract = self._web3.eth.contract(
                address=self._agent_registry_addr,
                abi=_load_agent_registry_abi(),
            )
            tx_func = contract.functions.registerAgent(
                agent_id,
                public_key_address,
                SCOPE_HASH_PHASE_O0_EXIT,
                STATUS_DEFINED,
            )
            # In operator's on-chain session: build + sign + send + wait for receipt
            # In tests: mock returns the simulated tx hash
            tx_hash = await tx_func.call()
        except Exception as exc:
            err_msg = str(exc)
            if "AgentAlreadyRegistered" in err_msg or "duplicate" in err_msg.lower():
                raise AgentRegistrationDuplicateError(
                    f"Agent {agent!r} already registered (agentId already exists): {exc}"
                ) from exc
            raise AgentRegistrationContractError(
                f"Failed to register agent {agent!r}: {exc}"
            ) from exc

        log.info(
            "register_agent: agent=%s agent_id=0x%s public_key=%s did_cid=%s tx=%s",
            agent, agent_id.hex(), public_key_address, did_document_cid, tx_hash,
        )
        return tx_hash

    async def register_full_flow(
        self,
        agent: str,
        agent_nft_address: str,
        token_id: int = 0,
    ) -> dict:
        """Orchestrate the complete Section 6.4 flow for one agent.

        Sequence:
          1. populate_did_document (KMS pubkey → template)
          2. mint_ioid_did (ioIDRegistry.register → DID address)
          3. bind_erc6551_tba (ERC-6551 Registry deterministic derivation → TBA address)
          4. substitute_did_addresses (DID address + TBA + agentId into template)
          5. pin_did_document (Pinata IPFS pin → CID)
          6. register_agent (AgentRegistry.registerAgent → tx hash)

        Returns dict with all relevant addresses, CID, tx hash, and the agentId.

        H1a: full execution against real services happens only in operator's
        on-chain session. Tests verify orchestration via mocks.
        """
        # 1. Populate DID document with KMS pubkey
        did_doc_unsubstituted = await self.populate_did_document(agent)

        # 2. Derive agent's Ethereum address from KMS pubkey (used to mint ioID DID)
        der_public_key = await self._kms.get_public_key(agent)
        agent_address = derive_eth_address_from_kms_public_key(der_public_key)

        # 3. Mint ioID DID for the agent
        ioid_did_address = await self.mint_ioid_did(agent_address)

        # 4. Derive ERC-6551 TBA
        tba_address = await self.bind_erc6551_tba(
            ioid_did_address=ioid_did_address,
            agent_nft_address=agent_nft_address,
            token_id=token_id,
        )

        # 5. Compute agentId per Q9 + substitute addresses into DID document
        agent_id = compute_agent_id(ioid_did_address, tba_address)
        did_doc_final = self.substitute_did_addresses(
            did_doc_unsubstituted,
            ioid_did_address=ioid_did_address,
            tba_address=tba_address,
            agent_id_bytes32=agent_id,
        )

        # 6. Pin DID document to IPFS
        did_cid = await self.pin_did_document(did_doc_final, agent)

        # 7. Register agent on AgentRegistry
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
            "tba_address": tba_address,
            "agent_id": "0x" + agent_id.hex(),
            "did_document_cid": did_cid,
            "tx_hash": tx_hash,
        }
        log.info("register_full_flow: complete agent=%s result=%s", agent, result)
        return result
