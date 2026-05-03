"""Phase O0 Block-B-prime — operator-driven on-chain registration wrapper.

This wrapper script adds the production-submission layer that Block B
(commit db9b4b97) deferred per V8.4 explicit decision. AgentRegistrar
methods in bridge/vapi_bridge/agent_registration.py use .call() simulation
throughout (verified orchestration logic against cryptographically valid
mocks); this wrapper composes those methods with .transact() submission,
receipt parsing, and event extraction to produce real on-chain state.

Usage pattern (P1a + P3a-with-session-state):

  Operator runs each function from interactive Python with explicit
  approval between invocations. Each function reads the session-state
  file at start (preserving cross-function context like deployed
  addresses, project tokenIds, transaction hashes) and writes captured
  outputs at end (durable audit trail + mid-session crash recovery).

  Example session:
    >>> import asyncio
    >>> from bridge.scripts.operator_session_register_agents import *
    >>>
    >>> # Step 1: operator runs Hardhat deploy externally first, then:
    >>> asyncio.run(step_1_deploy_device_nft())
    >>>
    >>> # Step 2: operator updates VAPI_OPERATOR_AGENT_NFT_ADDR constant
    >>> #         + commits + pushes externally first, then:
    >>> asyncio.run(step_2_update_constant_commit())
    >>>
    >>> # Steps 3-8: each is one tx submission per call:
    >>> asyncio.run(step_3_register_project())
    >>> asyncio.run(step_4_setup_device_contract())
    >>> asyncio.run(step_5_apply_ioids(amount=2, pre_pay=True))
    >>> asyncio.run(step_6_mint_device_nft("anchor-sentry"))
    >>> asyncio.run(step_6_mint_device_nft("guardian"))
    >>> asyncio.run(step_7_register_full_flow("anchor-sentry"))
    >>> asyncio.run(step_7_register_full_flow("guardian"))
    >>> asyncio.run(step_8_register_agent("anchor-sentry"))
    >>> asyncio.run(step_8_register_agent("guardian"))
    >>>
    >>> # Post-session aggregation:
    >>> asyncio.run(post_session_verification())

Session-state file:

  Path: bridge/scripts/.operator_session_state.json
  Lifecycle: created by step_1, updated by each subsequent step,
             read by post_session_verification.
  Gitignore: covered by repo-root .gitignore pattern
             "bridge/scripts/.operator_session_state*" (per V6.1).
  Atomic write: temp file + os.replace pattern.

Operator approval discipline:

  Each function executes ONE state-changing transaction. Between
  function invocations, operator reviews the returned dict (transaction
  hash, block number, gas consumed, captured outputs) before invoking
  the next function. The "approval" mechanism is the operator's
  decision to invoke (or not invoke) the next function — no runtime
  input() prompts that would collapse approval visibility.

Cross-references:

  Pass 2C Section 14 (commit d2911480 fourth amendment) — canonical spec
  bridge/vapi_bridge/agent_registration.py (commit db9b4b97) — composed
                                                                 modules
  bridge/vapi_bridge/kms_client.py (commit d3b30d58) — KMS integration
  bridge/vapi_bridge/pinata_client.py (commit dcaf5015) — Pinata integration
  contracts/scripts/deploy-vapi-operator-agent-nft.js — Hardhat Step 1
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

from eth_account import Account
from eth_hash.auto import keccak
from eth_utils import to_checksum_address

# Block B AgentRegistrar (composed for read-only + pure-function methods)
from bridge.vapi_bridge.agent_registration import (
    AGENT_REGISTRY_ADDR,
    AGENT_TO_DEVICE_TOKEN_ID,
    IOID_CONTRACT_ADDR,
    IOID_REGISTRY_ABI,
    IOID_REGISTRY_ADDR,
    IOID_STORE_ABI,
    IOID_STORE_ADDR,
    IOTEX_TESTNET_CHAIN_ID,
    IPROJECT_ABI,
    PROJECT_REGISTRY_ABI,
    PROJECT_REGISTRY_ADDR,
    PROJECT_TYPE_HARDWARE,
    SCOPE_HASH_PHASE_O0_EXIT,
    STATUS_DEFINED,
    VAPI_OPERATOR_AGENT_NFT_ABI,
    VAPI_OPERATOR_AGENTS_PROJECT_NAME,
    AgentRegistrar,
    _compute_eip712_permit_digest,
    _compute_eip712_domain_separator,
    _parse_der_signature_to_vrs,
    compute_agent_id,
    derive_eth_address_from_kms_public_key,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_STATE_PATH = Path(__file__).parent / ".operator_session_state.json"
DEPLOYED_ADDRESSES_PATH = (
    Path(__file__).parent.parent.parent / "contracts" / "deployed-addresses.json"
)
AGENT_REGISTRATION_PATH = (
    Path(__file__).parent.parent / "vapi_bridge" / "agent_registration.py"
)

# IoTeX testnet gas price (1000 gwei = 1e12 wei per contracts/hardhat.config.js)
# Pinned at this value so wrapper transactions match the deploy script's gas
# profile and avoid runtime gas_price queries (which add async complexity).
IOTEX_TESTNET_GAS_PRICE_WEI = 1_000_000_000_000

# Default RPC URL (operator can override via IOTEX_RPC_URL env var)
_DEFAULT_RPC_URL = "https://babel-api.testnet.iotex.io"

# Bridge wallet env var (canonical key per bridge/.env)
_BRIDGE_PRIVATE_KEY_ENV = "BRIDGE_PRIVATE_KEY"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class OperatorSessionError(Exception):
    """Base exception for all operator session failures."""


class OperatorSessionStateError(OperatorSessionError):
    """Raised when session-state read/write or env-var load fails."""


class OperatorSessionStepError(OperatorSessionError):
    """Raised when step preconditions are not met (missing deps, wrong order)."""


class OperatorSessionSubmissionError(OperatorSessionError):
    """Raised when transaction submission fails (gas, nonce, network, revert)."""


class OperatorSessionVerificationError(OperatorSessionError):
    """Raised when post-step verification fails (event missing, state mismatch)."""


# ---------------------------------------------------------------------------
# Session-state utilities (P3a-with-session-state)
# ---------------------------------------------------------------------------

def _session_state_path() -> Path:
    """Return canonical SESSION_STATE_PATH (utility for tests + introspection)."""
    return SESSION_STATE_PATH


def _load_session_state() -> dict:
    """Read SESSION_STATE_PATH if exists, return dict. Empty dict on first invocation.

    Raises OperatorSessionStateError if file exists but is corrupted JSON.
    """
    path = _session_state_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except json.JSONDecodeError as exc:
        raise OperatorSessionStateError(
            f"Session state at {path} is corrupted JSON: {exc}. "
            f"Inspect manually and either repair or delete to reset."
        ) from exc
    if not isinstance(state, dict):
        raise OperatorSessionStateError(
            f"Session state at {path} is not a dict (got {type(state).__name__})"
        )
    return state


def _save_session_state(updates: dict) -> None:
    """Read existing state, merge updates, write back atomically.

    Atomic write pattern: write to .tmp file, then os.replace(tmp, target).
    Preserves existing state if updates dict modifies subset of keys.
    """
    path = _session_state_path()
    state = _load_session_state()
    state.update(updates)
    state["_last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)
    log.info("session-state saved: keys=%s", sorted(updates.keys()))


def _load_bridge_account() -> Account:
    """Load bridge wallet Account from BRIDGE_PRIVATE_KEY env var (V6.3)."""
    pk = os.environ.get(_BRIDGE_PRIVATE_KEY_ENV)
    if not pk:
        raise OperatorSessionStateError(
            f"{_BRIDGE_PRIVATE_KEY_ENV} not set in environment. "
            f"Bridge wallet credentials required for transaction submission. "
            f"See bridge/.env."
        )
    if not pk.startswith("0x"):
        pk = "0x" + pk
    return Account.from_key(pk)


# ---------------------------------------------------------------------------
# Web3 + transaction submission utilities
# ---------------------------------------------------------------------------

def _make_web3():
    """Construct AsyncWeb3 connection to IoTeX testnet (or override via env).

    Lazy import of web3 (testing override-friendly via dependency injection).
    """
    from web3 import AsyncWeb3, AsyncHTTPProvider
    rpc_url = os.environ.get("IOTEX_RPC_URL", _DEFAULT_RPC_URL)
    return AsyncWeb3(AsyncHTTPProvider(rpc_url))


async def _submit_transaction(
    w3,
    contract,
    function_name: str,
    args: tuple,
    from_account: Account,
    value: int = 0,
    gas_estimate_buffer: float = 1.5,
    gas_price_wei: int = IOTEX_TESTNET_GAS_PRICE_WEI,
    chain_id: int = IOTEX_TESTNET_CHAIN_ID,
) -> dict:
    """Build, sign, submit, and confirm a state-changing transaction.

    Returns dict: {tx_hash, block_number, gas_used, status, receipt}.

    Raises OperatorSessionSubmissionError if any step fails (build, sign,
    send, or receipt indicates revert).
    """
    func = getattr(contract.functions, function_name)(*args)

    # Build transaction params
    try:
        nonce = await w3.eth.get_transaction_count(from_account.address)
        # Estimate gas with safety buffer
        gas_estimate = await func.estimate_gas({
            "from": from_account.address,
            "value": value,
        })
        gas_with_buffer = int(gas_estimate * gas_estimate_buffer)
        tx = await func.build_transaction({
            "from": from_account.address,
            "nonce": nonce,
            "value": value,
            "gas": gas_with_buffer,
            "gasPrice": gas_price_wei,
            "chainId": chain_id,
        })
    except Exception as exc:
        raise OperatorSessionSubmissionError(
            f"_submit_transaction: build failed for {function_name}{args}: {exc}"
        ) from exc

    # Sign with bridge wallet
    try:
        signed = from_account.sign_transaction(tx)
    except Exception as exc:
        raise OperatorSessionSubmissionError(
            f"_submit_transaction: sign failed for {function_name}{args}: {exc}"
        ) from exc

    # Send + wait for receipt
    try:
        # web3.py 7.x: signed.raw_transaction (snake_case); some 6.x: rawTransaction
        raw_tx = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")
        tx_hash = await w3.eth.send_raw_transaction(raw_tx)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
    except Exception as exc:
        raise OperatorSessionSubmissionError(
            f"_submit_transaction: send/wait failed for {function_name}{args}: {exc}"
        ) from exc

    # Verify status (1 = success, 0 = revert)
    status = receipt.get("status") if isinstance(receipt, dict) else getattr(receipt, "status", None)
    if status == 0:
        raise OperatorSessionSubmissionError(
            f"_submit_transaction: {function_name}{args} reverted on-chain. "
            f"tx_hash={tx_hash.hex() if hasattr(tx_hash, 'hex') else tx_hash}"
        )

    block_number = receipt.get("blockNumber") if isinstance(receipt, dict) else getattr(receipt, "blockNumber", None)
    gas_used = receipt.get("gasUsed") if isinstance(receipt, dict) else getattr(receipt, "gasUsed", None)
    tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
    if not tx_hash_hex.startswith("0x"):
        tx_hash_hex = "0x" + tx_hash_hex

    log.info(
        "_submit_transaction: %s%s -> tx=%s block=%s gas=%s",
        function_name, args, tx_hash_hex, block_number, gas_used,
    )
    return {
        "tx_hash": tx_hash_hex,
        "block_number": block_number,
        "gas_used": gas_used,
        "status": status,
        "receipt": receipt,
    }


def _parse_event_from_receipt(receipt, contract, event_name: str) -> dict:
    """Extract first matching event from receipt via contract.events.<EventName>().process_receipt.

    Returns dict of event args. Raises OperatorSessionVerificationError if
    event not found.
    """
    try:
        event_obj = getattr(contract.events, event_name)()
        events = event_obj.process_receipt(receipt)
    except Exception as exc:
        raise OperatorSessionVerificationError(
            f"_parse_event_from_receipt: failed to process {event_name}: {exc}"
        ) from exc

    if not events:
        raise OperatorSessionVerificationError(
            f"_parse_event_from_receipt: no {event_name} event in receipt"
        )

    first_event = events[0]
    args = first_event.get("args") if isinstance(first_event, dict) else getattr(first_event, "args", None)
    if args is None:
        raise OperatorSessionVerificationError(
            f"_parse_event_from_receipt: {event_name} event has no args field"
        )
    if hasattr(args, "_asdict"):
        return dict(args._asdict())
    return dict(args)


# ---------------------------------------------------------------------------
# Step 1: VAPIOperatorAgentNFT deployment verification (Hardhat-driven)
# ---------------------------------------------------------------------------

async def step_1_deploy_device_nft() -> dict:
    """Verify VAPIOperatorAgentNFT deployed via Hardhat + capture address.

    Step 1 is Hardhat-driven (operator runs `npx hardhat run
    contracts/scripts/deploy-vapi-operator-agent-nft.js --network
    iotex_testnet` externally before invoking this function). This Python
    function reads contracts/deployed-addresses.json to confirm the
    deployment landed and captures the address into session state.

    Returns: {device_nft_address, source}.
    Raises: OperatorSessionStepError if deployed-addresses.json lacks
            VAPIOperatorAgentNFT entry or the address is the placeholder zero.
    """
    if not DEPLOYED_ADDRESSES_PATH.exists():
        raise OperatorSessionStepError(
            f"deployed-addresses.json not found at {DEPLOYED_ADDRESSES_PATH}"
        )
    with open(DEPLOYED_ADDRESSES_PATH, "r", encoding="utf-8") as f:
        addresses = json.load(f)

    addr = addresses.get("VAPIOperatorAgentNFT")
    if not addr:
        raise OperatorSessionStepError(
            "VAPIOperatorAgentNFT entry missing from deployed-addresses.json. "
            "Run `npx hardhat run scripts/deploy-vapi-operator-agent-nft.js "
            "--network iotex_testnet` from contracts/ first."
        )
    if addr == "0x0000000000000000000000000000000000000000":
        raise OperatorSessionStepError(
            "VAPIOperatorAgentNFT entry is placeholder zero address. "
            "Deployment script must run + populate the entry with the deployed address."
        )
    # Validate address shape (0x + 40 hex chars)
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", addr):
        raise OperatorSessionStepError(
            f"VAPIOperatorAgentNFT address has invalid format: {addr!r}"
        )

    checksum_addr = to_checksum_address(addr)
    _save_session_state({
        "device_nft_address": checksum_addr,
        "step_1_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    log.info("step_1: device_nft_address=%s", checksum_addr)
    return {
        "device_nft_address": checksum_addr,
        "source": "deployed-addresses.json",
    }


# ---------------------------------------------------------------------------
# Step 2: VAPI_OPERATOR_AGENT_NFT_ADDR constant verification (git-driven)
# ---------------------------------------------------------------------------

async def step_2_update_constant_commit() -> dict:
    """Verify VAPI_OPERATOR_AGENT_NFT_ADDR constant matches session-state address.

    Step 2 is git-driven (operator updates the constant in
    bridge/vapi_bridge/agent_registration.py + commits + pushes externally
    before invoking this function). This Python function verifies the
    constant matches the session-state device_nft_address from Step 1.

    Returns: {constant_value, session_state_value, match}.
    Raises: OperatorSessionStepError if constant still equals placeholder
            or doesn't match session-state address.
    """
    state = _load_session_state()
    expected = state.get("device_nft_address")
    if not expected:
        raise OperatorSessionStepError(
            "Session state missing device_nft_address. Run step_1 first."
        )

    if not AGENT_REGISTRATION_PATH.exists():
        raise OperatorSessionStepError(
            f"agent_registration.py not found at {AGENT_REGISTRATION_PATH}"
        )
    text = AGENT_REGISTRATION_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'VAPI_OPERATOR_AGENT_NFT_ADDR\s*=\s*"(0x[0-9a-fA-F]{40})"',
        text,
    )
    if not match:
        raise OperatorSessionStepError(
            "VAPI_OPERATOR_AGENT_NFT_ADDR constant not found in agent_registration.py "
            "with expected pattern."
        )
    constant_value = match.group(1)
    if constant_value == "0x0000000000000000000000000000000000000000":
        raise OperatorSessionStepError(
            "VAPI_OPERATOR_AGENT_NFT_ADDR is still placeholder zero. "
            "Update constant to match session-state device_nft_address "
            f"({expected}) and commit + push before invoking step_2."
        )
    if to_checksum_address(constant_value) != to_checksum_address(expected):
        raise OperatorSessionStepError(
            f"VAPI_OPERATOR_AGENT_NFT_ADDR mismatch: constant={constant_value} "
            f"!= session_state={expected}"
        )

    _save_session_state({
        "constant_verified": True,
        "step_2_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return {
        "constant_value": constant_value,
        "session_state_value": expected,
        "match": True,
    }


# ---------------------------------------------------------------------------
# Step 3: ProjectRegistry.register
# ---------------------------------------------------------------------------

async def step_3_register_project(
    project_name: str = VAPI_OPERATOR_AGENTS_PROJECT_NAME,
    *,
    w3=None,
    account: Optional[Account] = None,
) -> dict:
    """Submit ProjectRegistry.register transaction + parse Transfer event for project tokenId.

    Args:
        project_name: project name (default canonical "VAPI Operator Agents")
        w3: AsyncWeb3 instance (None → constructs default; tests inject mock)
        account: bridge wallet Account (None → loads from env; tests inject mock)

    Returns: {project_token_id, tx_hash, block_number, gas_used}.
    """
    if w3 is None:
        w3 = _make_web3()
    if account is None:
        account = _load_bridge_account()

    contract = w3.eth.contract(address=PROJECT_REGISTRY_ADDR, abi=PROJECT_REGISTRY_ABI)
    submit = await _submit_transaction(
        w3=w3, contract=contract, function_name="register",
        args=(project_name, PROJECT_TYPE_HARDWARE),
        from_account=account,
    )

    # IProject is ERC-721; ProjectRegistry.register triggers IProject.mint which
    # emits Transfer(from=0x0, to=msg.sender, tokenId=N). To parse the tokenId,
    # we need the IProject contract's ABI. Get IProject address via
    # ProjectRegistry.project() view, then construct ERC-721 Transfer event ABI.
    iproject_addr = await contract.functions.project().call()
    erc721_transfer_abi = [{
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }]
    iproject_contract = w3.eth.contract(address=iproject_addr, abi=erc721_transfer_abi)
    transfer_args = _parse_event_from_receipt(submit["receipt"], iproject_contract, "Transfer")
    project_token_id = int(transfer_args.get("tokenId"))

    result = {
        "project_token_id": project_token_id,
        "tx_hash": submit["tx_hash"],
        "block_number": submit["block_number"],
        "gas_used": submit["gas_used"],
        "iproject_address": to_checksum_address(iproject_addr),
    }
    _save_session_state({
        "project_token_id": project_token_id,
        "iproject_address": result["iproject_address"],
        "step_3_tx": submit["tx_hash"],
        "step_3_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return result


# ---------------------------------------------------------------------------
# Step 4: ioIDStore.setDeviceContract
# ---------------------------------------------------------------------------

async def step_4_setup_device_contract(
    *,
    w3=None,
    account: Optional[Account] = None,
) -> dict:
    """Submit ioIDStore.setDeviceContract + verify bidirectional 1:1 mapping post-tx.

    Reads project_token_id (step 3) + device_nft_address (step 1) from session state.
    Raises OperatorSessionStepError if either missing.

    Returns: {tx_hash, block_number, gas_used, mapping_verified}.
    """
    state = _load_session_state()
    project_token_id = state.get("project_token_id")
    device_nft_addr = state.get("device_nft_address")
    if project_token_id is None:
        raise OperatorSessionStepError(
            "Session state missing project_token_id. Run step_3 first."
        )
    if not device_nft_addr:
        raise OperatorSessionStepError(
            "Session state missing device_nft_address. Run step_1 first."
        )

    if w3 is None:
        w3 = _make_web3()
    if account is None:
        account = _load_bridge_account()

    contract = w3.eth.contract(address=IOID_STORE_ADDR, abi=IOID_STORE_ABI)
    submit = await _submit_transaction(
        w3=w3, contract=contract, function_name="setDeviceContract",
        args=(project_token_id, device_nft_addr),
        from_account=account,
    )

    # Verify mapping post-submission
    try:
        verified_project_id = await contract.functions.deviceContractProject(
            device_nft_addr
        ).call()
    except Exception as exc:
        raise OperatorSessionVerificationError(
            f"step_4: deviceContractProject view call failed post-tx: {exc}"
        ) from exc

    if int(verified_project_id) != int(project_token_id):
        raise OperatorSessionVerificationError(
            f"step_4: mapping verification failed. Expected projectId={project_token_id}, "
            f"got {verified_project_id}"
        )

    result = {
        "tx_hash": submit["tx_hash"],
        "block_number": submit["block_number"],
        "gas_used": submit["gas_used"],
        "mapping_verified": True,
    }
    _save_session_state({
        "step_4_tx": submit["tx_hash"],
        "device_contract_mapping_verified": True,
        "step_4_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return result


# ---------------------------------------------------------------------------
# Step 5: ioIDStore.applyIoIDs (optional pre-pay)
# ---------------------------------------------------------------------------

async def step_5_apply_ioids(
    amount: int = 2,
    pre_pay: bool = True,
    *,
    w3=None,
    account: Optional[Account] = None,
) -> dict:
    """Optional pre-pay: submit ioIDStore.applyIoIDs with msg.value = amount * price.

    If pre_pay=False: skip submission; document decision in session state
    (step 7's ioIDRegistry.register calls will pay-as-you-go via msg.value).

    Returns dict varies by path:
      pre_pay=True:  {tx_hash, block_number, gas_used, value_consumed, price_wei}
      pre_pay=False: {pay_as_you_go: True, decision_recorded_at}
    """
    state = _load_session_state()
    project_token_id = state.get("project_token_id")
    if project_token_id is None:
        raise OperatorSessionStepError(
            "Session state missing project_token_id. Run step_3 first."
        )

    if not pre_pay:
        _save_session_state({
            "applied_ioids_count": 0,
            "pay_as_you_go": True,
            "step_5_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        return {
            "pay_as_you_go": True,
            "decision_recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    if w3 is None:
        w3 = _make_web3()
    if account is None:
        account = _load_bridge_account()

    contract = w3.eth.contract(address=IOID_STORE_ADDR, abi=IOID_STORE_ABI)
    price_wei = await contract.functions.price().call()
    value = int(amount) * int(price_wei)

    submit = await _submit_transaction(
        w3=w3, contract=contract, function_name="applyIoIDs",
        args=(project_token_id, amount),
        from_account=account, value=value,
    )

    result = {
        "tx_hash": submit["tx_hash"],
        "block_number": submit["block_number"],
        "gas_used": submit["gas_used"],
        "value_consumed": value,
        "price_wei": int(price_wei),
        "amount": amount,
    }
    _save_session_state({
        "applied_ioids_count": amount,
        "applied_ioids_value": value,
        "applied_ioids_price_wei": int(price_wei),
        "pay_as_you_go": False,
        "step_5_tx": submit["tx_hash"],
        "step_5_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return result


# ---------------------------------------------------------------------------
# Step 6: VAPIOperatorAgentNFT.mint per agent
# ---------------------------------------------------------------------------

async def step_6_mint_device_nft(
    agent: str,
    *,
    w3=None,
    account: Optional[Account] = None,
) -> dict:
    """Submit VAPIOperatorAgentNFT.mint(bridge_wallet) + parse Transfer event for tokenId.

    agent must be in {"anchor-sentry", "guardian"}. Bridge wallet receives
    the device NFT (later transferred away by ioIDRegistry.register in step_7).

    Returns: {device_token_id, tx_hash, block_number, gas_used, agent}.
    """
    if agent not in AGENT_TO_DEVICE_TOKEN_ID:
        raise OperatorSessionStepError(
            f"Unknown agent {agent!r}. Expected one of {list(AGENT_TO_DEVICE_TOKEN_ID.keys())}."
        )

    state = _load_session_state()
    device_nft_addr = state.get("device_nft_address")
    if not device_nft_addr:
        raise OperatorSessionStepError(
            "Session state missing device_nft_address. Run step_1 first."
        )

    if w3 is None:
        w3 = _make_web3()
    if account is None:
        account = _load_bridge_account()

    contract = w3.eth.contract(address=device_nft_addr, abi=VAPI_OPERATOR_AGENT_NFT_ABI)
    submit = await _submit_transaction(
        w3=w3, contract=contract, function_name="mint",
        args=(account.address,),
        from_account=account,
    )

    # Parse Transfer event for tokenId. VAPIOperatorAgentNFT extends
    # ERC721Upgradeable; Transfer signature: (from, to, tokenId).
    erc721_transfer_abi = [{
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
            {"indexed": True, "internalType": "uint256", "name": "tokenId", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }]
    contract_with_event = w3.eth.contract(address=device_nft_addr, abi=erc721_transfer_abi)
    transfer_args = _parse_event_from_receipt(submit["receipt"], contract_with_event, "Transfer")
    device_token_id = int(transfer_args.get("tokenId"))

    result = {
        "device_token_id": device_token_id,
        "tx_hash": submit["tx_hash"],
        "block_number": submit["block_number"],
        "gas_used": submit["gas_used"],
        "agent": agent,
    }
    state = _load_session_state()
    device_token_ids = state.get("device_token_ids", {})
    device_token_ids[agent] = device_token_id
    _save_session_state({
        "device_token_ids": device_token_ids,
        f"step_6_{agent}_tx": submit["tx_hash"],
        f"step_6_{agent}_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return result


# ---------------------------------------------------------------------------
# Step 7: ioIDRegistry.register full flow per agent (Section 14.4 13-step)
# ---------------------------------------------------------------------------

async def step_7_register_full_flow(
    agent: str,
    *,
    w3=None,
    account: Optional[Account] = None,
    kms_client=None,
    pinata_client=None,
) -> dict:
    """Execute Section 14.4 per-agent flow with .transact() submission for the register call.

    Composes AgentRegistrar's pure/read-only methods (DID population, IPFS pin,
    content hash, nonce query, EIP-712 permit digest, KMS sign, DER parse) and
    re-implements the state-changing ioIDRegistry.register 8-param call via
    wrapper's _submit_transaction. Reads back the ioID tokenId from the
    NewDevice event in the receipt + queries TBA address via ioID.wallet view.

    Returns dict with all captured outputs (ioID DID, ioID tokenId, TBA, content
    hash, IPFS CID, tx_hash, etc.).
    """
    if agent not in AGENT_TO_DEVICE_TOKEN_ID:
        raise OperatorSessionStepError(
            f"Unknown agent {agent!r}. Expected one of {list(AGENT_TO_DEVICE_TOKEN_ID.keys())}."
        )

    state = _load_session_state()
    device_nft_addr = state.get("device_nft_address")
    device_token_ids = state.get("device_token_ids", {})
    device_token_id = device_token_ids.get(agent)
    if not device_nft_addr:
        raise OperatorSessionStepError(
            "Session state missing device_nft_address. Run step_1 first."
        )
    if device_token_id is None:
        raise OperatorSessionStepError(
            f"Session state missing device_token_ids[{agent!r}]. Run step_6 first."
        )

    if w3 is None:
        w3 = _make_web3()
    if account is None:
        account = _load_bridge_account()
    if kms_client is None:
        from bridge.vapi_bridge.kms_client import KMSClient
        kms_client = KMSClient()
    if pinata_client is None:
        from bridge.vapi_bridge.pinata_client import PinataClient
        pinata_client = PinataClient()

    # Construct an AgentRegistrar to compose its read-only/pure methods.
    # Its state-changing methods (.call() pattern) are NOT used here — the
    # wrapper's _submit_transaction handles the ioIDRegistry.register
    # transaction directly per V6.2.
    registrar = AgentRegistrar(
        kms_client=kms_client, pinata_client=pinata_client, web3_async=w3,
        bridge_wallet_address=account.address,
        vapi_operator_agent_nft_addr=device_nft_addr,
    )

    # 1. populate_did_document (KMS pubkey → template)
    did_doc = await registrar.populate_did_document(agent)

    # 2. pin_did_document (Pinata IPFS pin → CID)
    cid = await registrar.pin_did_document(did_doc, agent)
    uri = f"ipfs://{cid}"

    # 3. compute_did_content_hash (keccak256 of canonical JSON)
    content_hash = registrar.compute_did_content_hash(did_doc)

    # 4. derive agent's ETH address (the device per M2)
    der_pubkey = await kms_client.get_public_key(agent)
    device_address = derive_eth_address_from_kms_public_key(der_pubkey)

    # 5. query device nonce from ioIDRegistry
    nonce = await registrar.query_device_nonce(device_address)

    # 6. compute EIP-712 permit digest (signed by device per M2)
    digest = registrar.compute_eip712_permit_digest(account.address, nonce)

    # 7. KMS sign the digest
    der_signature = await registrar.kms_sign_permit_digest(agent, digest)

    # 8. parse DER → (v, r, s) with ecrecover-against-device verification
    v, r, s = _parse_der_signature_to_vrs(der_signature, digest, device_address)

    # 9. submit ioIDRegistry.register (8-param wrapper per M1)
    # Pay-as-you-go path: forward msg.value = price unless pre-paid in step_5
    if state.get("pay_as_you_go", True):
        price_wei = state.get("applied_ioids_price_wei")
        if price_wei is None:
            ioid_store = w3.eth.contract(address=IOID_STORE_ADDR, abi=IOID_STORE_ABI)
            price_wei = int(await ioid_store.functions.price().call())
        register_value = int(price_wei)
    else:
        register_value = 0  # pre-paid in step_5

    ioid_registry_contract = w3.eth.contract(address=IOID_REGISTRY_ADDR, abi=IOID_REGISTRY_ABI)
    submit = await _submit_transaction(
        w3=w3, contract=ioid_registry_contract, function_name="register",
        args=(device_nft_addr, device_token_id, device_address, content_hash, uri, v, r, s),
        from_account=account, value=register_value,
    )

    # 10. Read back ioID tokenId via ERC-721 Enumerable on ioID contract.
    #
    # Original approach was ioID.ids(device) per canonical b94ad092 source.
    # Empirical finding from third sitting (2026-05-03): the deployed
    # ioIDRegistry contract does NOT expose `ids` as a public getter (revert
    # with 0x = function selector not in dispatch table). The deployed
    # contract differs from canonical b94ad092 source on this view-method
    # exposure.
    #
    # Fix: use ERC-721 Enumerable's tokenOfOwnerByIndex on the ioID per-DID
    # NFT contract. The ioID NFT is minted to bridge wallet (per ioIDRegistry
    # source line 114: `_id = _ioID.mint(_projectId, device, user)` where
    # user = msg.sender = bridge wallet). bridge_wallet balance increments
    # by 1 each successful register. Most recently minted ioID for bridge
    # is at index (balance - 1) per ERC-721 Enumerable mint-order semantics.
    # This is robust as long as bridge never transfers an ioID NFT away
    # (which Block B does NOT do — only device NFTs transfer to TBA wallets
    # during register; ioID NFTs stay with bridge).
    ioid_abi_enum = [
        {"type": "function", "name": "balanceOf", "stateMutability": "view",
         "inputs": [{"name": "owner", "type": "address"}],
         "outputs": [{"name": "", "type": "uint256"}]},
        {"type": "function", "name": "tokenOfOwnerByIndex", "stateMutability": "view",
         "inputs": [{"name": "owner", "type": "address"},
                    {"name": "index", "type": "uint256"}],
         "outputs": [{"name": "", "type": "uint256"}]},
    ]
    ioid_contract = w3.eth.contract(address=IOID_CONTRACT_ADDR, abi=ioid_abi_enum)
    try:
        bridge_ioid_balance = int(
            await ioid_contract.functions.balanceOf(account.address).call()
        )
        if bridge_ioid_balance == 0:
            raise OperatorSessionVerificationError(
                f"step_7: bridge owns 0 ioID NFTs after register; expected >= 1"
            )
        ioid_token_id = int(
            await ioid_contract.functions.tokenOfOwnerByIndex(
                account.address, bridge_ioid_balance - 1
            ).call()
        )
    except OperatorSessionVerificationError:
        raise
    except Exception as exc:
        raise OperatorSessionVerificationError(
            f"step_7: ioID tokenId readback via tokenOfOwnerByIndex failed: {exc}"
        ) from exc

    # 11. read back TBA via ioID.wallet (per M6 + N4)
    tba_address = await registrar.readback_tba(ioid_token_id)

    # 12. ioid_did_address = device_address (per Section 14 N4)
    ioid_did_address = device_address

    # Compose result + persist to session state
    result = {
        "agent": agent,
        "device_address": device_address,
        "ioid_did_address": ioid_did_address,
        "ioid_token_id": ioid_token_id,
        "tba_address": tba_address,
        "did_document_cid": cid,
        "did_uri": uri,
        "did_content_hash": "0x" + content_hash.hex(),
        "permit_nonce": nonce,
        "register_value_wei": register_value,
        "tx_hash": submit["tx_hash"],
        "block_number": submit["block_number"],
        "gas_used": submit["gas_used"],
    }

    state = _load_session_state()
    ioid_data = state.get("ioid_data", {})
    ioid_data[agent] = result
    _save_session_state({
        "ioid_data": ioid_data,
        f"step_7_{agent}_tx": submit["tx_hash"],
        f"step_7_{agent}_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return result


# ---------------------------------------------------------------------------
# Step 8: AgentRegistry.registerAgent per agent
# ---------------------------------------------------------------------------

async def step_8_register_agent(
    agent: str,
    *,
    w3=None,
    account: Optional[Account] = None,
    kms_client=None,
) -> dict:
    """Submit AgentRegistry.registerAgent + verify post-submission via getAgent view.

    Reads ioID DID address + TBA address for agent from session state ioid_data.
    Computes agentId per Pass 2C Q9 (frozen encoding). Derives publicKey from
    KMS public key. Submits with scopeHash = bytes32(0) + status = STATUS_DEFINED.

    Returns dict with agentId + registration_tuple verified.
    """
    if agent not in AGENT_TO_DEVICE_TOKEN_ID:
        raise OperatorSessionStepError(
            f"Unknown agent {agent!r}. Expected one of {list(AGENT_TO_DEVICE_TOKEN_ID.keys())}."
        )

    state = _load_session_state()
    ioid_data = state.get("ioid_data", {}).get(agent)
    if not ioid_data:
        raise OperatorSessionStepError(
            f"Session state missing ioid_data[{agent!r}]. Run step_7 first."
        )
    ioid_did_address = ioid_data.get("ioid_did_address")
    tba_address = ioid_data.get("tba_address")
    if not ioid_did_address or not tba_address:
        raise OperatorSessionStepError(
            f"Session state ioid_data[{agent!r}] missing ioid_did_address or tba_address. "
            f"Re-run step_7 to repopulate."
        )

    if w3 is None:
        w3 = _make_web3()
    if account is None:
        account = _load_bridge_account()
    if kms_client is None:
        from bridge.vapi_bridge.kms_client import KMSClient
        kms_client = KMSClient()

    # Compute agentId per Q9 (FROZEN encoding)
    agent_id = compute_agent_id(ioid_did_address, tba_address)

    # Derive publicKey (ETH address) from agent's KMS pubkey
    der_pubkey = await kms_client.get_public_key(agent)
    public_key_address = derive_eth_address_from_kms_public_key(der_pubkey)

    # Load AgentRegistry ABI from Hardhat artifact
    artifact_path = (
        Path(__file__).parent.parent.parent
        / "contracts" / "artifacts" / "contracts" / "AgentRegistry.sol" / "AgentRegistry.json"
    )
    if not artifact_path.is_file():
        raise OperatorSessionStateError(
            f"AgentRegistry artifact not found at {artifact_path}. "
            f"Run `cd contracts && npx hardhat compile`."
        )
    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)
    agent_registry_abi = artifact["abi"]

    contract = w3.eth.contract(address=AGENT_REGISTRY_ADDR, abi=agent_registry_abi)
    submit = await _submit_transaction(
        w3=w3, contract=contract, function_name="registerAgent",
        args=(agent_id, public_key_address, SCOPE_HASH_PHASE_O0_EXIT, STATUS_DEFINED),
        from_account=account,
    )

    # Verify post-submission via getAgent view
    try:
        registration_tuple = await contract.functions.getAgent(agent_id).call()
    except Exception as exc:
        raise OperatorSessionVerificationError(
            f"step_8: getAgent view failed post-tx: {exc}"
        ) from exc

    # Verify AgentRegistered event in receipt
    try:
        event_args = _parse_event_from_receipt(submit["receipt"], contract, "AgentRegistered")
    except OperatorSessionVerificationError:
        log.warning("step_8: AgentRegistered event not found (logged for review)")
        event_args = {}

    result = {
        "agent": agent,
        "agent_id": "0x" + agent_id.hex(),
        "public_key": public_key_address,
        "scope_hash": "0x" + SCOPE_HASH_PHASE_O0_EXIT.hex(),
        "status": STATUS_DEFINED,
        "tx_hash": submit["tx_hash"],
        "block_number": submit["block_number"],
        "gas_used": submit["gas_used"],
        "registration_tuple": list(registration_tuple) if registration_tuple else None,
        "event_args": event_args,
    }
    state = _load_session_state()
    agent_registry_data = state.get("agent_registry_data", {})
    agent_registry_data[agent] = {
        "agent_id": result["agent_id"],
        "public_key": public_key_address,
        "tx_hash": submit["tx_hash"],
    }
    _save_session_state({
        "agent_registry_data": agent_registry_data,
        f"step_8_{agent}_tx": submit["tx_hash"],
        f"step_8_{agent}_completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    return result


# ---------------------------------------------------------------------------
# Post-session verification + audit aggregation
# ---------------------------------------------------------------------------

async def post_session_verification(*, w3=None) -> dict:
    """Aggregate session state + run cross-step verification queries.

    Returns comprehensive verification dict suitable for the post-session
    commit message. Read-only queries against on-chain state for both agents.
    """
    state = _load_session_state()
    if w3 is None:
        w3 = _make_web3()

    summary = {
        "session_state": state,
        "agents": {},
    }

    # Load AgentRegistry ABI
    artifact_path = (
        Path(__file__).parent.parent.parent
        / "contracts" / "artifacts" / "contracts" / "AgentRegistry.sol" / "AgentRegistry.json"
    )
    if artifact_path.is_file():
        with open(artifact_path, "r", encoding="utf-8") as f:
            artifact = json.load(f)
        agent_registry_abi = artifact["abi"]
        agent_registry_contract = w3.eth.contract(
            address=AGENT_REGISTRY_ADDR, abi=agent_registry_abi,
        )
    else:
        agent_registry_contract = None

    agent_registry_data = state.get("agent_registry_data", {})
    ioid_data = state.get("ioid_data", {})

    for agent in AGENT_TO_DEVICE_TOKEN_ID:
        agent_summary = {
            "ioid_did_address": ioid_data.get(agent, {}).get("ioid_did_address"),
            "ioid_token_id": ioid_data.get(agent, {}).get("ioid_token_id"),
            "tba_address": ioid_data.get(agent, {}).get("tba_address"),
            "did_document_cid": ioid_data.get(agent, {}).get("did_document_cid"),
            "agent_id": agent_registry_data.get(agent, {}).get("agent_id"),
        }
        if agent_registry_contract and agent_summary["agent_id"]:
            try:
                agent_id_bytes = bytes.fromhex(agent_summary["agent_id"][2:])
                tup = await agent_registry_contract.functions.getAgent(agent_id_bytes).call()
                agent_summary["registry_verified"] = True
                agent_summary["registry_tuple"] = list(tup)
            except Exception as exc:
                agent_summary["registry_verified"] = False
                agent_summary["registry_error"] = str(exc)
        summary["agents"][agent] = agent_summary

    # Wallet balance delta (if start balance recorded)
    start_balance = state.get("start_balance_wei")
    if start_balance is not None:
        try:
            current_balance = await w3.eth.get_balance(
                state.get("bridge_wallet_address") or "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
            )
            summary["wallet_balance_start_wei"] = start_balance
            summary["wallet_balance_current_wei"] = int(current_balance)
            summary["total_iotx_consumed"] = (start_balance - int(current_balance)) / 1e18
        except Exception as exc:
            summary["wallet_balance_error"] = str(exc)

    return summary
