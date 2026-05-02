"""Phase O0 Section 6.4 Block B — MockAgentRegistrar for higher-level testing.

Composes a fully-mocked AgentRegistrar instance for code that wants to
exercise the registration interface without setting up per-contract web3
mocks. The mock uses MockKMSClient (cryptographically valid secp256k1
signatures per L3a) + MockPinataClient (deterministic CIDs) + a built-in
deterministic web3 mock that returns canned per-contract values matching
the Section 14 orchestration flow.

Per V8.6: per-contract mock factories live in bridge/tests/test_agent_registration.py
for tests that exercise the orchestration logic directly. MockAgentRegistrar
is for higher-level callers who want a single-import-mock; for orchestration
testing, prefer the test-local factories.

Mock behavior (deterministic values, suitable for tests of code that
composes AgentRegistrar without wanting to verify orchestration internals):

  Project token ID: 1 (constant; check_project_nft returns 1)
  IProject NFT contract: 0xf07336e1c77319b4e740b666eb0c2b19d11fc14f (canonical)
  Device token IDs: anchor-sentry → 1, guardian → 2 (per AGENT_TO_DEVICE_TOKEN_ID)
  Device nonces: 0 (assumes first registration; each agent has nonce 0)
  TBA addresses: deterministic from device_token_id
                 (sentry: 0x...0001, guardian: 0x...0002)
  ioID DID address: agent's KMS-derived ETH address (canonical pattern;
                    device_address IS the did:io:<address>)
  Tx hashes: deterministic per-agent (sentry: 0x...sentry; guardian: 0x...guardian)
  ioIDStore.price: 100_000_000_000_000_000 wei (0.1 IOTX, matches on-chain value)

Cross-references:
  bridge/vapi_bridge/agent_registration.py — real AgentRegistrar
  bridge/vapi_bridge/mock_kms_client.py — KMS mock (commit d3b30d58)
  bridge/vapi_bridge/mock_pinata_client.py — Pinata mock (commit dcaf5015)
  bridge/tests/test_agent_registration.py — per-contract mock factories
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

from .agent_registration import (
    AgentRegistrar,
    IPROJECT_ABI,
    PROJECT_REGISTRY_ABI,
    IOID_REGISTRY_ABI,
    IOID_STORE_ABI,
    IOID_ABI,
    VAPI_OPERATOR_AGENT_NFT_ABI,
    AGENT_TO_DEVICE_TOKEN_ID,
)
from .mock_kms_client import MockKMSClient
from .mock_pinata_client import MockPinataClient

log = logging.getLogger(__name__)

# Mock canonical addresses (used by the built-in deterministic web3 mock)
_MOCK_BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
_MOCK_DEVICE_NFT_ADDR = "0x000000000000000000000000000000000000aFFa"  # non-zero placeholder
_MOCK_IPROJECT_ADDR = "0xf07336e1c77319b4e740b666eb0c2b19d11fc14f"  # canonical IProject
_MOCK_PROJECT_TOKEN_ID = 1
_MOCK_PRICE_WEI = 100_000_000_000_000_000  # 0.1 IOTX
_MOCK_DOMAIN_SEPARATOR = bytes.fromhex(
    "4e31e01d4e41f6c9dc9d68103971ef473adf267bd74326f72170daac66329bcc"
)


def _mock_tba_for_token_id(token_id: int) -> str:
    """Deterministic TBA address from device tokenId (sentry → 0x...01, guardian → 0x...02)."""
    return "0x" + "0" * 38 + f"{token_id:02x}"


def _mock_tx_hash_for_agent(agent: str) -> str:
    """Deterministic tx hash per agent (sentry → ...sentry; guardian → ...guardian)."""
    return "0x" + "0" * 56 + agent.replace("-", "").rjust(8, "0")[-8:].encode().hex()


def make_mock_web3() -> MagicMock:
    """Construct a deterministic MagicMock web3 connection covering all Section 14 contract calls.

    Returns a MagicMock whose `.eth.contract(address, abi)` produces a
    contract mock whose `.functions.<name>(...).call()` returns the canned
    value appropriate for the (address, function_name) pair.

    Determinism: the mock dispatches on the contract address to return
    the right canned value per contract type (ProjectRegistry, ioIDRegistry,
    ioIDStore, ioID, IProject, VAPIOperatorAgentNFT).
    """
    web3 = MagicMock()

    def make_contract(address=None, abi=None, **kwargs):
        contract = MagicMock()
        addr_str = str(address).lower() if address else ""

        # ProjectRegistry contract
        if addr_str == "0x060581aa1a4e0cc92fbd74d251913238de2f13cd":
            project_func = MagicMock()
            project_func.call = AsyncMock(return_value=_MOCK_IPROJECT_ADDR)
            contract.functions.project = MagicMock(return_value=project_func)

            register_func = MagicMock()
            register_func.call = AsyncMock(return_value=_MOCK_PROJECT_TOKEN_ID)
            contract.functions.register = MagicMock(return_value=register_func)

        # IProject NFT contract
        elif addr_str == _MOCK_IPROJECT_ADDR.lower():
            balance_func = MagicMock()
            balance_func.call = AsyncMock(return_value=1)  # bridge owns 1 project NFT
            contract.functions.balanceOf = MagicMock(return_value=balance_func)

            token_func = MagicMock()
            token_func.call = AsyncMock(return_value=_MOCK_PROJECT_TOKEN_ID)
            contract.functions.tokenOfOwnerByIndex = MagicMock(return_value=token_func)

        # ioIDRegistry contract
        elif addr_str == "0x0a7e595c7889df3652a19af52c18377bf17e027d":
            register_func = MagicMock()
            register_func.call = AsyncMock(return_value=None)  # void return
            contract.functions.register = MagicMock(return_value=register_func)

            nonces_func = MagicMock()
            nonces_func.call = AsyncMock(return_value=0)  # first registration
            contract.functions.nonces = MagicMock(return_value=nonces_func)

            ds_func = MagicMock()
            ds_func.call = AsyncMock(return_value=_MOCK_DOMAIN_SEPARATOR)
            contract.functions.DOMAIN_SEPARATOR = MagicMock(return_value=ds_func)

        # ioIDStore contract
        elif addr_str == "0x60cac5ce11cb2f98bf179be5fd3d801c3d5dbff2":
            price_func = MagicMock()
            price_func.call = AsyncMock(return_value=_MOCK_PRICE_WEI)
            contract.functions.price = MagicMock(return_value=price_func)

            apply_func = MagicMock()
            apply_func.call = AsyncMock(return_value=None)
            contract.functions.applyIoIDs = MagicMock(return_value=apply_func)

            setup_func = MagicMock()
            setup_func.call = AsyncMock(return_value=None)
            contract.functions.setDeviceContract = MagicMock(return_value=setup_func)

            dcp_func = MagicMock()
            dcp_func.call = AsyncMock(return_value=_MOCK_PROJECT_TOKEN_ID)
            contract.functions.deviceContractProject = MagicMock(return_value=dcp_func)

        # ioID per-DID NFT contract
        elif addr_str == "0x45ce3e6f526e597628c73b731a3e9af7fc32f5b7":
            wallet_func = MagicMock()
            # Returns (wallet_address, did_string) tuple per IioID interface
            wallet_func.call = AsyncMock(
                return_value=(_mock_tba_for_token_id(1), "did:io:0xmock")
            )
            contract.functions.wallet = MagicMock(return_value=wallet_func)

        # VAPIOperatorAgentNFT contract (or any catch-all device NFT)
        else:
            mint_func = MagicMock()
            # Counter-based: each call returns next sequential tokenId
            # For simple deterministic test, return 1 (overridable via test-local factories)
            mint_func.call = AsyncMock(return_value=1)
            contract.functions.mint = MagicMock(return_value=mint_func)

            config_func = MagicMock()
            config_func.call = AsyncMock(return_value=None)
            contract.functions.configureMinter = MagicMock(return_value=config_func)

            init_func = MagicMock()
            init_func.call = AsyncMock(return_value=None)
            contract.functions.initialize = MagicMock(return_value=init_func)

            total_func = MagicMock()
            total_func.call = AsyncMock(return_value=0)
            contract.functions.total = MagicMock(return_value=total_func)

            # AgentRegistry catch-all
            register_agent_func = MagicMock()
            register_agent_func.call = AsyncMock(return_value="0xdeadbeefcafe0001")
            contract.functions.registerAgent = MagicMock(return_value=register_agent_func)

        return contract

    web3.eth.contract = MagicMock(side_effect=make_contract)
    return web3


def make_mock_agent_registrar(
    bridge_wallet: str = _MOCK_BRIDGE_WALLET,
    device_nft_addr: str = _MOCK_DEVICE_NFT_ADDR,
    project_token_id: int = _MOCK_PROJECT_TOKEN_ID,
) -> AgentRegistrar:
    """Construct a real AgentRegistrar pre-wired with cryptographically valid mocks.

    Convenient single-import for higher-level callers who want to test
    against AgentRegistrar's interface without setting up the per-contract
    mock factories themselves.

    Returns: AgentRegistrar instance with MockKMSClient + MockPinataClient
             + deterministic web3 mock + non-zero VAPI_OPERATOR_AGENT_NFT_ADDR
             override (so register_full_flow doesn't raise the placeholder
             ConfigError).
    """
    return AgentRegistrar(
        kms_client=MockKMSClient(),
        pinata_client=MockPinataClient(),
        web3_async=make_mock_web3(),
        bridge_wallet_address=bridge_wallet,
        vapi_operator_agent_nft_addr=device_nft_addr,
        project_token_id=project_token_id,
    )


# Backward-compatible alias (per V8.6 — module exposes the factory functions
# tests directly compose; MockAgentRegistrar is just a convenience wrapper)
MockAgentRegistrar = make_mock_agent_registrar
