"""Phase O0 Block-B-prime — operator_session_register_agents wrapper tests.

20 tests covering:
  Session state utilities (4 tests): load empty / roundtrip / merge / atomic
  Step 1-2 verification helpers (4 tests): file reads + format validation + raise paths
  Step 3-8 transaction submission (10 tests): per-step args + receipt parsing
                                              + event extraction + session-state writes
  Post-session aggregation (1 test): cross-step summary
  + 1 bonus test for _load_bridge_account env-var validation

All tests use:
  Cryptographically valid MockKMSClient (real ECDSA signatures)
  MockPinataClient (deterministic CIDs)
  Mocked AsyncWeb3 with canned receipts + events
  monkeypatch on _session_state_path() to isolate per-test state files
  Mock Account (Account.from_key("0x" + "11" * 32)) for deterministic signing

No real network calls. No real on-chain transactions.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from eth_account import Account
from eth_hash.auto import keccak

from bridge.scripts import operator_session_register_agents as mod
from bridge.scripts.operator_session_register_agents import (
    OperatorSessionStateError,
    OperatorSessionStepError,
    OperatorSessionVerificationError,
    _load_session_state,
    _parse_event_from_receipt,
    _save_session_state,
    _session_state_path,
    post_session_verification,
    step_1_deploy_device_nft,
    step_2_update_constant_commit,
    step_3_register_project,
    step_4_setup_device_contract,
    step_5_apply_ioids,
    step_6_mint_device_nft,
    step_7_register_full_flow,
    step_8_register_agent,
)
from bridge.vapi_bridge.agent_registration import (
    AGENT_REGISTRY_ADDR,
    IOID_REGISTRY_ADDR,
    IOID_STORE_ADDR,
    PROJECT_REGISTRY_ADDR,
    compute_agent_id,
)
from bridge.vapi_bridge.mock_kms_client import MockKMSClient
from bridge.vapi_bridge.mock_pinata_client import MockPinataClient


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------

_MOCK_BRIDGE_PK = "0x" + "11" * 32
_MOCK_DEVICE_NFT = "0x000000000000000000000000000000000000aFFa"
_MOCK_IPROJECT = "0xf07336e1c77319b4e740b666eb0c2b19d11fc14f"
_MOCK_PRICE_WEI = 100_000_000_000_000_000  # 0.1 IOTX


@pytest.fixture(autouse=True)
def _isolate_session_state(monkeypatch, tmp_path):
    """Redirect SESSION_STATE_PATH to per-test tmp_path so tests don't collide."""
    p = tmp_path / ".operator_session_state.json"
    monkeypatch.setattr(mod, "SESSION_STATE_PATH", p)
    return p


def _mock_account() -> Account:
    """Deterministic mock bridge wallet."""
    return Account.from_key(_MOCK_BRIDGE_PK)


def _make_mock_receipt(
    block_number: int = 12345,
    gas_used: int = 100_000,
    status: int = 1,
) -> dict:
    """Standard successful receipt dict shape."""
    return {
        "blockNumber": block_number,
        "gasUsed": gas_used,
        "status": status,
        "transactionHash": b"\xaa" * 32,
    }


def _make_mock_w3_for_submit(
    canned_tx_hash: bytes = b"\xde\xad\xbe\xef" * 8,
    canned_receipt: dict = None,
    estimate_gas_returns: int = 100_000,
    nonce: int = 0,
) -> MagicMock:
    """Build an AsyncWeb3 mock supporting full _submit_transaction flow."""
    if canned_receipt is None:
        canned_receipt = _make_mock_receipt()

    w3 = MagicMock()
    w3.eth = MagicMock()
    w3.eth.get_transaction_count = AsyncMock(return_value=nonce)
    w3.eth.send_raw_transaction = AsyncMock(return_value=canned_tx_hash)
    w3.eth.wait_for_transaction_receipt = AsyncMock(return_value=canned_receipt)
    w3.eth.get_balance = AsyncMock(return_value=16_973_199_000_000_000_000)

    return w3


def _wire_contract(w3: MagicMock, contract: MagicMock):
    """Make w3.eth.contract(any_address, any_abi) return the supplied contract."""
    w3.eth.contract = MagicMock(return_value=contract)


def _make_function_mock(
    return_value: any = None,
    estimate_gas_returns: int = 100_000,
    build_transaction_returns: dict = None,
) -> MagicMock:
    """Shared helper: build a contract-function-call mock supporting .call(),
    .estimate_gas(), and .build_transaction() on the same chain."""
    if build_transaction_returns is None:
        build_transaction_returns = {
            "from": _mock_account().address,
            "nonce": 0,
            "value": 0,
            "gas": int(estimate_gas_returns * 1.5),
            "gasPrice": mod.IOTEX_TESTNET_GAS_PRICE_WEI,
            "chainId": mod.IOTEX_TESTNET_CHAIN_ID,
            "data": "0x00",
            "to": "0x" + "00" * 20,
        }
    fn = MagicMock()
    fn.call = AsyncMock(return_value=return_value)
    fn.estimate_gas = AsyncMock(return_value=estimate_gas_returns)
    fn.build_transaction = AsyncMock(return_value=build_transaction_returns)
    return fn


# ===========================================================================
# Test 1-4: Session state utilities
# ===========================================================================

def test_session_state_load_returns_empty_dict_when_no_file():
    """First invocation: no state file → empty dict."""
    state = _load_session_state()
    assert state == {}


def test_session_state_save_and_load_roundtrip():
    """Save updates → load returns merged state including timestamp."""
    _save_session_state({"foo": "bar", "count": 42})
    state = _load_session_state()
    assert state["foo"] == "bar"
    assert state["count"] == 42
    assert "_last_updated" in state  # auto-stamped


def test_session_state_save_merges_existing_state():
    """Second save merges into existing state without erasing prior keys."""
    _save_session_state({"first": "one"})
    _save_session_state({"second": "two"})
    state = _load_session_state()
    assert state["first"] == "one"
    assert state["second"] == "two"


def test_session_state_atomic_write_via_temp_file():
    """Atomic write produces no leftover .tmp file after successful save."""
    _save_session_state({"key": "value"})
    path = _session_state_path()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    assert path.exists()
    assert not tmp_path.exists()  # tmp file replaced; no leftover


# ===========================================================================
# Test 5-6: Step 1 verification
# ===========================================================================

@pytest.mark.asyncio
async def test_step_1_reads_deployed_addresses_correctly(monkeypatch, tmp_path):
    """step_1 reads VAPIOperatorAgentNFT entry from deployed-addresses.json."""
    fake_addr = "0x1234567890123456789012345678901234567890"
    fake_addresses = {"VAPIOperatorAgentNFT": fake_addr}
    fake_path = tmp_path / "deployed-addresses.json"
    fake_path.write_text(json.dumps(fake_addresses))
    monkeypatch.setattr(mod, "DEPLOYED_ADDRESSES_PATH", fake_path)

    result = await step_1_deploy_device_nft()
    assert result["device_nft_address"].lower() == fake_addr.lower()
    assert result["source"] == "deployed-addresses.json"

    state = _load_session_state()
    assert state["device_nft_address"].lower() == fake_addr.lower()
    assert "step_1_completed_at" in state


@pytest.mark.asyncio
async def test_step_1_raises_when_device_nft_not_deployed(monkeypatch, tmp_path):
    """step_1 raises OperatorSessionStepError when entry is placeholder zero."""
    fake_addresses = {"VAPIOperatorAgentNFT": "0x0000000000000000000000000000000000000000"}
    fake_path = tmp_path / "deployed-addresses.json"
    fake_path.write_text(json.dumps(fake_addresses))
    monkeypatch.setattr(mod, "DEPLOYED_ADDRESSES_PATH", fake_path)

    with pytest.raises(OperatorSessionStepError) as exc_info:
        await step_1_deploy_device_nft()
    assert "placeholder zero" in str(exc_info.value)


# ===========================================================================
# Test 7-8: Step 2 verification
# ===========================================================================

@pytest.mark.asyncio
async def test_step_2_verifies_constant_matches_session_state(monkeypatch, tmp_path):
    """step_2 confirms constant matches session-state device_nft_address."""
    fake_addr = "0x1234567890123456789012345678901234567890"
    _save_session_state({"device_nft_address": fake_addr})

    fake_module = tmp_path / "agent_registration.py"
    fake_module.write_text(
        f'# stuff\nVAPI_OPERATOR_AGENT_NFT_ADDR = "{fake_addr}"\n# more stuff\n'
    )
    monkeypatch.setattr(mod, "AGENT_REGISTRATION_PATH", fake_module)

    result = await step_2_update_constant_commit()
    assert result["match"] is True
    assert result["constant_value"].lower() == fake_addr.lower()


@pytest.mark.asyncio
async def test_step_2_raises_on_constant_mismatch(monkeypatch, tmp_path):
    """step_2 raises when constant differs from session-state address."""
    session_addr = "0x1111111111111111111111111111111111111111"
    constant_addr = "0x2222222222222222222222222222222222222222"
    _save_session_state({"device_nft_address": session_addr})

    fake_module = tmp_path / "agent_registration.py"
    fake_module.write_text(f'VAPI_OPERATOR_AGENT_NFT_ADDR = "{constant_addr}"\n')
    monkeypatch.setattr(mod, "AGENT_REGISTRATION_PATH", fake_module)

    with pytest.raises(OperatorSessionStepError) as exc_info:
        await step_2_update_constant_commit()
    assert "mismatch" in str(exc_info.value).lower()


# ===========================================================================
# Test 9: Step 3 register_project event parsing
# ===========================================================================

@pytest.mark.asyncio
async def test_step_3_register_project_extracts_token_id_from_event():
    """step_3 submits ProjectRegistry.register + parses Transfer event for tokenId."""
    expected_token_id = 7

    pr_contract = MagicMock()
    pr_contract.functions.register = MagicMock(return_value=_make_function_mock())
    project_func = MagicMock()
    project_func.call = AsyncMock(return_value=_MOCK_IPROJECT)
    pr_contract.functions.project = MagicMock(return_value=project_func)

    iproject_contract = MagicMock()
    transfer_event_obj = MagicMock()
    transfer_event_obj.process_receipt = MagicMock(return_value=[
        {"args": {"from": "0x" + "00" * 20, "to": _mock_account().address, "tokenId": expected_token_id}}
    ])
    iproject_contract.events.Transfer = MagicMock(return_value=transfer_event_obj)

    w3 = _make_mock_w3_for_submit()

    def contract_factory(address=None, abi=None, **kw):
        addr = str(address).lower()
        if addr == PROJECT_REGISTRY_ADDR.lower():
            return pr_contract
        if addr == _MOCK_IPROJECT.lower():
            return iproject_contract
        return MagicMock()

    w3.eth.contract = MagicMock(side_effect=contract_factory)

    result = await step_3_register_project(w3=w3, account=_mock_account())
    assert result["project_token_id"] == expected_token_id
    assert result["tx_hash"].startswith("0x")
    assert result["block_number"] == 12345

    state = _load_session_state()
    assert state["project_token_id"] == expected_token_id


# ===========================================================================
# Test 10-11: Step 4 setup_device_contract
# ===========================================================================

@pytest.mark.asyncio
async def test_step_4_setup_device_contract_uses_session_state():
    """step_4 reads project_token_id + device_nft_address from session state."""
    _save_session_state({
        "project_token_id": 5,
        "device_nft_address": _MOCK_DEVICE_NFT,
    })

    store_contract = MagicMock()
    store_contract.functions.setDeviceContract = MagicMock(return_value=_make_function_mock())
    dcp_func = MagicMock()
    dcp_func.call = AsyncMock(return_value=5)  # mapping verified
    store_contract.functions.deviceContractProject = MagicMock(return_value=dcp_func)

    w3 = _make_mock_w3_for_submit()
    _wire_contract(w3, store_contract)

    result = await step_4_setup_device_contract(w3=w3, account=_mock_account())
    assert result["mapping_verified"] is True
    assert result["tx_hash"].startswith("0x")

    store_contract.functions.setDeviceContract.assert_called_once_with(5, _MOCK_DEVICE_NFT)


@pytest.mark.asyncio
async def test_step_4_raises_when_session_state_missing_dependencies():
    """step_4 raises when project_token_id or device_nft_address missing."""
    # No session state
    with pytest.raises(OperatorSessionStepError) as exc_info:
        await step_4_setup_device_contract()
    assert "project_token_id" in str(exc_info.value)


# ===========================================================================
# Test 12-13: Step 5 apply_ioids
# ===========================================================================

@pytest.mark.asyncio
async def test_step_5_apply_ioids_pre_pay_path():
    """step_5 pre-pay submits ioIDStore.applyIoIDs with msg.value = amount * price."""
    _save_session_state({"project_token_id": 1})

    store_contract = MagicMock()
    price_func = MagicMock()
    price_func.call = AsyncMock(return_value=_MOCK_PRICE_WEI)
    store_contract.functions.price = MagicMock(return_value=price_func)
    store_contract.functions.applyIoIDs = MagicMock(return_value=_make_function_mock())

    w3 = _make_mock_w3_for_submit()
    _wire_contract(w3, store_contract)

    result = await step_5_apply_ioids(amount=2, pre_pay=True, w3=w3, account=_mock_account())
    assert result["value_consumed"] == 2 * _MOCK_PRICE_WEI
    assert result["price_wei"] == _MOCK_PRICE_WEI
    assert result["amount"] == 2

    state = _load_session_state()
    assert state["pay_as_you_go"] is False
    assert state["applied_ioids_count"] == 2


@pytest.mark.asyncio
async def test_step_5_apply_ioids_pay_as_you_go_path():
    """step_5 pay-as-you-go skips submission; records decision in session state."""
    _save_session_state({"project_token_id": 1})

    result = await step_5_apply_ioids(amount=2, pre_pay=False)
    assert result["pay_as_you_go"] is True

    state = _load_session_state()
    assert state["pay_as_you_go"] is True
    assert state["applied_ioids_count"] == 0


# ===========================================================================
# Test 14-15: Step 6 mint_device_nft
# ===========================================================================

@pytest.mark.asyncio
async def test_step_6_mint_device_nft_returns_token_id():
    """step_6 submits VAPIOperatorAgentNFT.mint + parses Transfer event for tokenId."""
    _save_session_state({"device_nft_address": _MOCK_DEVICE_NFT})

    nft_contract = MagicMock()
    nft_contract.functions.mint = MagicMock(return_value=_make_function_mock())
    transfer_event_obj = MagicMock()
    transfer_event_obj.process_receipt = MagicMock(return_value=[
        {"args": {"from": "0x" + "00" * 20, "to": _mock_account().address, "tokenId": 1}}
    ])
    nft_contract.events.Transfer = MagicMock(return_value=transfer_event_obj)

    w3 = _make_mock_w3_for_submit()
    _wire_contract(w3, nft_contract)

    result = await step_6_mint_device_nft("anchor-sentry", w3=w3, account=_mock_account())
    assert result["device_token_id"] == 1
    assert result["agent"] == "anchor-sentry"


@pytest.mark.asyncio
async def test_step_6_assigns_distinct_token_ids_to_agents():
    """Sequential step_6 invocations produce distinct device_token_ids per agent."""
    _save_session_state({"device_nft_address": _MOCK_DEVICE_NFT})

    # Mint 1 for sentry
    nft_contract_1 = MagicMock()
    nft_contract_1.functions.mint = MagicMock(return_value=_make_function_mock())
    transfer_1 = MagicMock()
    transfer_1.process_receipt = MagicMock(return_value=[{"args": {"from": "0x0", "to": "0x0", "tokenId": 1}}])
    nft_contract_1.events.Transfer = MagicMock(return_value=transfer_1)
    w3_1 = _make_mock_w3_for_submit()
    _wire_contract(w3_1, nft_contract_1)
    await step_6_mint_device_nft("anchor-sentry", w3=w3_1, account=_mock_account())

    # Mint 2 for guardian
    nft_contract_2 = MagicMock()
    nft_contract_2.functions.mint = MagicMock(return_value=_make_function_mock())
    transfer_2 = MagicMock()
    transfer_2.process_receipt = MagicMock(return_value=[{"args": {"from": "0x0", "to": "0x0", "tokenId": 2}}])
    nft_contract_2.events.Transfer = MagicMock(return_value=transfer_2)
    w3_2 = _make_mock_w3_for_submit()
    _wire_contract(w3_2, nft_contract_2)
    await step_6_mint_device_nft("guardian", w3=w3_2, account=_mock_account())

    state = _load_session_state()
    assert state["device_token_ids"]["anchor-sentry"] == 1
    assert state["device_token_ids"]["guardian"] == 2


# ===========================================================================
# Test 16-17: Step 7 register_full_flow
# ===========================================================================

@pytest.mark.asyncio
async def test_step_7_register_full_flow_orchestrates_correctly(monkeypatch, tmp_path):
    """step_7 composes pure AgentRegistrar methods + submits ioIDRegistry.register."""
    _save_session_state({
        "device_nft_address": _MOCK_DEVICE_NFT,
        "device_token_ids": {"anchor-sentry": 1},
        "pay_as_you_go": False,
        "applied_ioids_price_wei": _MOCK_PRICE_WEI,
    })

    # Place a minimal DID template at expected location
    did_dir = tmp_path / "agents" / "did_templates"
    did_dir.mkdir(parents=True)
    did_template = did_dir / "vapi-anchor-sentry.did.template.json"
    did_template.write_text(json.dumps({
        "id": "did:io:0x<address>",
        "verificationMethod": [{"id": "did:io:0x<address>#kms-key-1", "publicKeyHex": "<placeholder>"}],
        "metadata": {"createdAt": "<iso8601>"},
    }))

    # Monkeypatch _REPO_ROOT used by agent_registration to find DID templates
    from bridge.vapi_bridge import agent_registration as ar_mod
    monkeypatch.setattr(ar_mod, "_REPO_ROOT", tmp_path)

    # Mock web3: ioIDRegistry.register submission + nonces query
    register_func = _make_function_mock()
    nonces_func = MagicMock()
    nonces_func.call = AsyncMock(return_value=0)
    ioid_registry_contract = MagicMock()
    ioid_registry_contract.functions.register = MagicMock(return_value=register_func)
    ioid_registry_contract.functions.nonces = MagicMock(return_value=nonces_func)

    # ioID contract: ERC-721 Enumerable (balanceOf + tokenOfOwnerByIndex)
    # for tokenId readback per third-sitting empirical fix; wallet() for TBA.
    # Original ids() approach replaced because deployed ioIDRegistry lacks
    # the public ids getter. See operator_session_register_agents.py step_7
    # NatSpec for the empirical-finding-as-permanent-fix rationale.
    ioid_contract = MagicMock()
    balance_func = MagicMock()
    balance_func.call = AsyncMock(return_value=1)  # 1 ioID NFT after register
    ioid_contract.functions.balanceOf = MagicMock(return_value=balance_func)
    tofbi_func = MagicMock()
    tofbi_func.call = AsyncMock(return_value=42)  # ioID tokenId at index 0
    ioid_contract.functions.tokenOfOwnerByIndex = MagicMock(return_value=tofbi_func)
    wallet_func = MagicMock()
    wallet_func.call = AsyncMock(return_value=("0x" + "ab" * 20, "did:io:0xtest"))
    ioid_contract.functions.wallet = MagicMock(return_value=wallet_func)

    w3 = _make_mock_w3_for_submit()

    def contract_factory(address=None, abi=None, **kw):
        addr = str(address).lower()
        if addr == IOID_REGISTRY_ADDR.lower():
            return ioid_registry_contract
        if addr == "0x45ce3e6f526e597628c73b731a3e9af7fc32f5b7":
            return ioid_contract
        return MagicMock()

    w3.eth.contract = MagicMock(side_effect=contract_factory)

    result = await step_7_register_full_flow(
        "anchor-sentry", w3=w3, account=_mock_account(),
        kms_client=MockKMSClient(), pinata_client=MockPinataClient(),
    )
    assert result["agent"] == "anchor-sentry"
    assert result["ioid_token_id"] == 42
    assert result["tba_address"] == "0x" + "ab" * 20
    assert result["did_document_cid"].startswith("bafk")
    assert result["did_uri"].startswith("ipfs://")
    assert result["permit_nonce"] == 0
    assert result["register_value_wei"] == 0  # pre-paid path

    state = _load_session_state()
    assert "ioid_data" in state
    assert "anchor-sentry" in state["ioid_data"]


@pytest.mark.asyncio
async def test_step_7_raises_when_upstream_session_state_missing():
    """step_7 raises when device_nft_address or device_token_ids[agent] missing."""
    # No session state at all
    with pytest.raises(OperatorSessionStepError) as exc_info:
        await step_7_register_full_flow("anchor-sentry")
    assert "device_nft_address" in str(exc_info.value)

    # device_nft_address present but device_token_ids missing for agent
    _save_session_state({"device_nft_address": _MOCK_DEVICE_NFT})
    with pytest.raises(OperatorSessionStepError) as exc_info:
        await step_7_register_full_flow("anchor-sentry")
    assert "device_token_ids" in str(exc_info.value)


# ===========================================================================
# Test 18-19: Step 8 register_agent
# ===========================================================================

@pytest.mark.asyncio
async def test_step_8_register_agent_uses_q9_agentid_encoding(monkeypatch, tmp_path):
    """step_8 computes agentId per Q9 + submits AgentRegistry.registerAgent."""
    ioid_did = "0x" + "11" * 20
    tba = "0x" + "22" * 20
    expected_agent_id = compute_agent_id(ioid_did, tba)

    _save_session_state({
        "ioid_data": {
            "anchor-sentry": {
                "ioid_did_address": ioid_did,
                "tba_address": tba,
            },
        },
    })

    # Provide minimal AgentRegistry artifact
    artifact_dir = tmp_path / "contracts" / "artifacts" / "contracts" / "AgentRegistry.sol"
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / "AgentRegistry.json"
    artifact_path.write_text(json.dumps({
        "abi": [{
            "type": "function", "name": "registerAgent", "stateMutability": "nonpayable",
            "inputs": [
                {"name": "agentId", "type": "bytes32"},
                {"name": "publicKey", "type": "address"},
                {"name": "scopeHash", "type": "bytes32"},
                {"name": "status", "type": "uint8"},
            ], "outputs": [],
        }, {
            "type": "function", "name": "getAgent", "stateMutability": "view",
            "inputs": [{"name": "agentId", "type": "bytes32"}],
            "outputs": [
                {"name": "publicKey", "type": "address"},
                {"name": "scopeHash", "type": "bytes32"},
                {"name": "status", "type": "uint8"},
            ],
        }, {
            "type": "event", "name": "AgentRegistered",
            "inputs": [
                {"indexed": True, "name": "agentId", "type": "bytes32"},
                {"indexed": True, "name": "publicKey", "type": "address"},
                {"indexed": False, "name": "scopeHash", "type": "bytes32"},
                {"indexed": False, "name": "status", "type": "uint8"},
            ], "anonymous": False,
        }],
    }))

    # Monkeypatch the artifact path resolution within step_8
    real_path_class = Path

    class _PathPatched(type(real_path_class())):
        pass

    # Simpler: monkeypatch __file__ to point step_8 at tmp_path
    monkeypatch.setattr(mod, "__file__", str(tmp_path / "bridge" / "scripts" / "operator_session_register_agents.py"))
    (tmp_path / "bridge" / "scripts").mkdir(parents=True, exist_ok=True)

    # Mock contract: registerAgent submission + getAgent verify
    registry_contract = MagicMock()
    registry_contract.functions.registerAgent = MagicMock(return_value=_make_function_mock())
    get_agent_func = MagicMock()
    get_agent_func.call = AsyncMock(return_value=[_mock_account().address, b"\x00" * 32, 0])
    registry_contract.functions.getAgent = MagicMock(return_value=get_agent_func)
    event_obj = MagicMock()
    event_obj.process_receipt = MagicMock(return_value=[
        {"args": {"agentId": expected_agent_id, "publicKey": _mock_account().address, "scopeHash": b"\x00" * 32, "status": 0}}
    ])
    registry_contract.events.AgentRegistered = MagicMock(return_value=event_obj)

    w3 = _make_mock_w3_for_submit()
    _wire_contract(w3, registry_contract)

    result = await step_8_register_agent(
        "anchor-sentry", w3=w3, account=_mock_account(),
        kms_client=MockKMSClient(),
    )
    assert result["agent_id"] == "0x" + expected_agent_id.hex()
    assert result["status"] == 0
    assert result["scope_hash"] == "0x" + ("00" * 32)
    assert result["registration_tuple"] is not None


@pytest.mark.asyncio
async def test_step_8_verifies_registration_post_submission(monkeypatch, tmp_path):
    """step_8 calls getAgent post-submission and includes the tuple in result."""
    # Reuse the harness from test 18 — verify that registration_tuple field is populated
    ioid_did = "0x" + "33" * 20
    tba = "0x" + "44" * 20
    _save_session_state({
        "ioid_data": {
            "anchor-sentry": {"ioid_did_address": ioid_did, "tba_address": tba},
        },
    })

    artifact_dir = tmp_path / "contracts" / "artifacts" / "contracts" / "AgentRegistry.sol"
    artifact_dir.mkdir(parents=True)
    artifact_path = artifact_dir / "AgentRegistry.json"
    artifact_path.write_text(json.dumps({"abi": [
        {"type": "function", "name": "registerAgent", "stateMutability": "nonpayable",
         "inputs": [{"name": "agentId", "type": "bytes32"}, {"name": "publicKey", "type": "address"},
                    {"name": "scopeHash", "type": "bytes32"}, {"name": "status", "type": "uint8"}],
         "outputs": []},
        {"type": "function", "name": "getAgent", "stateMutability": "view",
         "inputs": [{"name": "agentId", "type": "bytes32"}],
         "outputs": [{"name": "publicKey", "type": "address"}, {"name": "scopeHash", "type": "bytes32"},
                     {"name": "status", "type": "uint8"}]},
        {"type": "event", "name": "AgentRegistered",
         "inputs": [{"indexed": True, "name": "agentId", "type": "bytes32"},
                    {"indexed": True, "name": "publicKey", "type": "address"},
                    {"indexed": False, "name": "scopeHash", "type": "bytes32"},
                    {"indexed": False, "name": "status", "type": "uint8"}],
         "anonymous": False},
    ]}))
    monkeypatch.setattr(mod, "__file__", str(tmp_path / "bridge" / "scripts" / "operator_session_register_agents.py"))
    (tmp_path / "bridge" / "scripts").mkdir(parents=True, exist_ok=True)

    registry_contract = MagicMock()
    registry_contract.functions.registerAgent = MagicMock(return_value=_make_function_mock())
    get_agent_func = MagicMock()
    expected_tuple = [_mock_account().address, b"\x00" * 32, 0]
    get_agent_func.call = AsyncMock(return_value=expected_tuple)
    registry_contract.functions.getAgent = MagicMock(return_value=get_agent_func)
    event_obj = MagicMock()
    event_obj.process_receipt = MagicMock(return_value=[])
    registry_contract.events.AgentRegistered = MagicMock(return_value=event_obj)

    w3 = _make_mock_w3_for_submit()
    _wire_contract(w3, registry_contract)

    result = await step_8_register_agent(
        "anchor-sentry", w3=w3, account=_mock_account(), kms_client=MockKMSClient(),
    )
    assert result["registration_tuple"] == expected_tuple


# ===========================================================================
# Test 20: post_session_verification aggregates session state
# ===========================================================================

@pytest.mark.asyncio
async def test_post_session_verification_aggregates_all_state(monkeypatch, tmp_path):
    """post_session_verification aggregates session state + on-chain queries."""
    _save_session_state({
        "device_nft_address": _MOCK_DEVICE_NFT,
        "project_token_id": 1,
        "device_token_ids": {"anchor-sentry": 1, "guardian": 2},
        "ioid_data": {
            "anchor-sentry": {
                "ioid_did_address": "0x" + "11" * 20,
                "ioid_token_id": 100,
                "tba_address": "0x" + "aa" * 20,
                "did_document_cid": "bafkmocktest1",
            },
            "guardian": {
                "ioid_did_address": "0x" + "22" * 20,
                "ioid_token_id": 101,
                "tba_address": "0x" + "bb" * 20,
                "did_document_cid": "bafkmocktest2",
            },
        },
        "agent_registry_data": {
            "anchor-sentry": {"agent_id": "0x" + "11" * 32, "public_key": _mock_account().address, "tx_hash": "0xtx1"},
            "guardian":      {"agent_id": "0x" + "22" * 32, "public_key": _mock_account().address, "tx_hash": "0xtx2"},
        },
    })

    # No artifact path → registry verification skipped (returns None)
    fake_root = tmp_path / "_fake_repo_root"
    fake_root.mkdir()
    monkeypatch.setattr(mod, "__file__", str(fake_root / "bridge" / "scripts" / "operator_session_register_agents.py"))
    (fake_root / "bridge" / "scripts").mkdir(parents=True, exist_ok=True)

    w3 = _make_mock_w3_for_submit()

    summary = await post_session_verification(w3=w3)
    assert "agents" in summary
    assert "anchor-sentry" in summary["agents"]
    assert "guardian" in summary["agents"]
    assert summary["agents"]["anchor-sentry"]["ioid_token_id"] == 100
    assert summary["agents"]["guardian"]["ioid_token_id"] == 101


# ===========================================================================
# Bonus: _load_bridge_account env-var validation
# ===========================================================================

def test_load_bridge_account_raises_when_env_missing(monkeypatch):
    """_load_bridge_account raises OperatorSessionStateError when env missing."""
    monkeypatch.delenv("BRIDGE_PRIVATE_KEY", raising=False)
    with pytest.raises(OperatorSessionStateError) as exc_info:
        mod._load_bridge_account()
    assert "BRIDGE_PRIVATE_KEY" in str(exc_info.value)


def test_load_bridge_account_loads_when_env_present(monkeypatch):
    """_load_bridge_account constructs Account from BRIDGE_PRIVATE_KEY env var."""
    monkeypatch.setenv("BRIDGE_PRIVATE_KEY", _MOCK_BRIDGE_PK)
    acct = mod._load_bridge_account()
    assert acct.address == _mock_account().address
