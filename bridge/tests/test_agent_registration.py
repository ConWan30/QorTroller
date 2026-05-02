"""Phase O0 Section 6.4 — AgentRegistrar tests with mocked dependencies.

Eight tests covering the orchestration logic of agent_registration.py.
All tests use MockKMSClient + MockPinataClient + MagicMock web3 — no real
network calls, no on-chain interactions per H1a / H3a.

Cross-references:
  bridge/vapi_bridge/agent_registration.py — orchestrator under test
  bridge/vapi_bridge/mock_kms_client.py — KMS mock (commit d3b30d58)
  bridge/vapi_bridge/mock_pinata_client.py — Pinata mock (this commit)
  Pass 2C Q9 (commits 3cb80ac5, fc61d93d) — agentId encoding spec
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.agent_registration import (
    AGENT_REGISTRY_ADDR,
    AgentRegistrar,
    AgentRegistrationKMSError,
    AgentRegistrationPinataError,
    ERC6551_REGISTRY_ADDR,
    IOID_REGISTRY_ADDR,
    SCOPE_HASH_PHASE_O0_EXIT,
    STATUS_DEFINED,
    compute_agent_id,
    derive_eth_address_from_kms_public_key,
    derive_uncompressed_pubkey_hex_from_kms_public_key,
)
from vapi_bridge.mock_kms_client import MockKMSClient
from vapi_bridge.mock_pinata_client import MockPinataClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_web3(
    mint_returns: str = "0x1111111111111111111111111111111111111111",
    tba_returns: str = "0x2222222222222222222222222222222222222222",
    register_returns: str = "0xdeadbeefcafe0001",
):
    """Create a MagicMock web3 connection that returns canned values for contract calls.

    Contract.functions.<name>(...).call() returns the canned value per call type.
    """
    web3 = MagicMock()

    def make_contract(address, abi):
        contract = MagicMock()

        # ioIDRegistry.register → DID address
        # ERC-6551 Registry .account → TBA address
        # AgentRegistry.registerAgent → tx hash

        register_func = MagicMock()
        register_func.call = AsyncMock(return_value=mint_returns)
        contract.functions.register = MagicMock(return_value=register_func)

        account_func = MagicMock()
        account_func.call = AsyncMock(return_value=tba_returns)
        contract.functions.account = MagicMock(return_value=account_func)

        register_agent_func = MagicMock()
        register_agent_func.call = AsyncMock(return_value=register_returns)
        contract.functions.registerAgent = MagicMock(return_value=register_agent_func)

        return contract

    web3.eth.contract = MagicMock(side_effect=make_contract)
    return web3


def _make_registrar(**overrides):
    """Construct AgentRegistrar with mocks; allow overrides for specific tests."""
    kms = overrides.pop("kms", MockKMSClient())
    pinata = overrides.pop("pinata", MockPinataClient())
    web3 = overrides.pop("web3", _make_mock_web3())
    return AgentRegistrar(
        kms_client=kms,
        pinata_client=pinata,
        web3_async=web3,
        **overrides,
    )


# ---------------------------------------------------------------------------
# Test 1: populate_did_document uses KMS public key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_populate_did_document_uses_kms_public_key():
    """populate_did_document fills verificationMethod.publicKeyHex from KMS."""
    registrar = _make_registrar()

    did_doc = await registrar.populate_did_document("anchor-sentry")

    assert "verificationMethod" in did_doc
    assert len(did_doc["verificationMethod"]) >= 1
    pubkey_hex = did_doc["verificationMethod"][0]["publicKeyHex"]
    assert pubkey_hex.startswith("0x04")  # uncompressed secp256k1 point prefix
    assert len(pubkey_hex) == 132  # 0x + 130 hex chars (1 byte prefix + 64 bytes X+Y)

    # createdAt was populated
    assert "metadata" in did_doc
    assert did_doc["metadata"]["createdAt"] != "<iso8601>"
    assert "T" in did_doc["metadata"]["createdAt"]  # ISO 8601 format


# ---------------------------------------------------------------------------
# Test 2: pin_did_document returns CID
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pin_did_document_returns_cid():
    """pin_did_document pins via PinataClient and returns the CID."""
    registrar = _make_registrar()
    did_doc = {"id": "did:io:0xtest", "controller": "did:io:0xtest"}

    cid = await registrar.pin_did_document(did_doc, "anchor-sentry")
    assert cid.startswith("bafk")  # IPFS CIDv1 mock prefix


# ---------------------------------------------------------------------------
# Test 3: mint_ioid_did calls correct contract
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mint_ioid_did_calls_correct_contract():
    """mint_ioid_did calls ioIDRegistry.register with the agent address."""
    expected_did = "0x3333333333333333333333333333333333333333"
    web3 = _make_mock_web3(mint_returns=expected_did)
    registrar = _make_registrar(web3=web3)

    agent_address = "0x4444444444444444444444444444444444444444"
    did_address = await registrar.mint_ioid_did(agent_address)

    assert did_address == expected_did
    # Verify the contract was constructed with ioIDRegistry address
    call_args_list = web3.eth.contract.call_args_list
    contract_addresses = [call[1].get("address") or call[0][0] for call in call_args_list]
    assert IOID_REGISTRY_ADDR in [str(a) for a in contract_addresses]


# ---------------------------------------------------------------------------
# Test 4: bind_erc6551_tba uses canonical registry address
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bind_erc6551_tba_uses_canonical_registry_address():
    """bind_erc6551_tba calls ERC-6551 Registry at the canonical singleton address."""
    expected_tba = "0x5555555555555555555555555555555555555555"
    web3 = _make_mock_web3(tba_returns=expected_tba)
    registrar = _make_registrar(web3=web3)

    tba_address = await registrar.bind_erc6551_tba(
        ioid_did_address="0x6666666666666666666666666666666666666666",
        agent_nft_address="0x7777777777777777777777777777777777777777",
        token_id=42,
    )

    assert tba_address == expected_tba
    # Verify ERC-6551 Registry singleton address was used
    call_args_list = web3.eth.contract.call_args_list
    contract_addresses = [call[1].get("address") or call[0][0] for call in call_args_list]
    assert ERC6551_REGISTRY_ADDR in [str(a) for a in contract_addresses]


# ---------------------------------------------------------------------------
# Test 5: register_agent uses Q9 agentId encoding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_agent_uses_q9_agentid_encoding():
    """register_agent computes agentId per Pass 2C Q9 FROZEN encoding."""
    registrar = _make_registrar()

    ioid_did = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    tba = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    # Compute expected agentId
    expected_agent_id = compute_agent_id(ioid_did, tba)
    assert len(expected_agent_id) == 32  # bytes32

    # Same inputs always produce same agentId (FROZEN encoding determinism)
    repeat = compute_agent_id(ioid_did, tba)
    assert expected_agent_id == repeat

    # Different inputs produce different agentIds
    different = compute_agent_id(ioid_did, "0xcccccccccccccccccccccccccccccccccccccccc")
    assert different != expected_agent_id

    tx_hash = await registrar.register_agent(
        agent="anchor-sentry",
        ioid_did_address=ioid_did,
        tba_address=tba,
        did_document_cid="bafkmocktest",
    )
    assert tx_hash == "0xdeadbeefcafe0001"

    # Verify AgentRegistry was called
    call_args_list = registrar._web3.eth.contract.call_args_list
    contract_addresses = [call[1].get("address") or call[0][0] for call in call_args_list]
    assert AGENT_REGISTRY_ADDR in [str(a) for a in contract_addresses]


# ---------------------------------------------------------------------------
# Test 6: register_full_flow orchestrates all steps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_full_flow_orchestrates_all_steps():
    """register_full_flow chains all 6 steps and returns the final result dict."""
    registrar = _make_registrar()

    result = await registrar.register_full_flow(
        agent="anchor-sentry",
        agent_nft_address="0xdddddddddddddddddddddddddddddddddddddddd",
        token_id=1,
    )

    # All keys present
    assert set(result.keys()) >= {
        "agent", "agent_address", "ioid_did_address", "tba_address",
        "agent_id", "did_document_cid", "tx_hash",
    }

    # Values consistent with mock returns
    assert result["agent"] == "anchor-sentry"
    assert result["ioid_did_address"] == "0x1111111111111111111111111111111111111111"
    assert result["tba_address"] == "0x2222222222222222222222222222222222222222"
    assert result["tx_hash"] == "0xdeadbeefcafe0001"
    assert result["did_document_cid"].startswith("bafk")
    assert result["agent_id"].startswith("0x") and len(result["agent_id"]) == 66  # 0x + 64 hex


# ---------------------------------------------------------------------------
# Test 7: register_agent handles KMS error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_agent_handles_kms_error():
    """register_agent raises AgentRegistrationKMSError when KMS get_public_key fails."""
    failing_kms = MockKMSClient()

    # Override get_public_key to raise
    async def failing_get_public_key(agent):
        raise RuntimeError("KMS network error")

    failing_kms.get_public_key = failing_get_public_key
    registrar = _make_registrar(kms=failing_kms)

    with pytest.raises(AgentRegistrationKMSError) as exc_info:
        await registrar.register_agent(
            agent="anchor-sentry",
            ioid_did_address="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            tba_address="0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            did_document_cid="bafkmocktest",
        )
    assert "KMS network error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 8: register_agent handles Pinata error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_agent_handles_pinata_error():
    """pin_did_document raises AgentRegistrationPinataError when Pinata fails."""
    failing_pinata = MockPinataClient()

    async def failing_pin_json(content, name, cid_version=1):
        raise RuntimeError("Pinata API error")

    failing_pinata.pin_json = failing_pin_json
    registrar = _make_registrar(pinata=failing_pinata)

    with pytest.raises(AgentRegistrationPinataError) as exc_info:
        await registrar.pin_did_document({"id": "test"}, "anchor-sentry")
    assert "Pinata API error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Bonus: Pass 2C Section 12 spec invariants encoded as test assertions
# ---------------------------------------------------------------------------

def test_section_6_4_constants_match_pass_2c_specs():
    """Pass 2C Section 6.4 + Section 7 constants match expected values."""
    # scopeHash = bytes32(0) per Section 7
    assert SCOPE_HASH_PHASE_O0_EXIT == b"\x00" * 32
    # status = STATUS_DEFINED = 0 per Section 6.4
    assert STATUS_DEFINED == 0
    # Stream 2-deploy AgentRegistry address per commit d019c067
    assert AGENT_REGISTRY_ADDR == "0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4"
    # ERC-6551 Registry canonical singleton per EIP-6551
    assert ERC6551_REGISTRY_ADDR == "0x000000006551c19487814612e58FE06813775758"
    # IoTeX ioID infrastructure address per operator brief
    assert IOID_REGISTRY_ADDR == "0x0A7e595C7889dF3652A19aF52C18377bF17e027D"
