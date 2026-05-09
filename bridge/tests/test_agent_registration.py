"""Phase O0 Section 6.4 Block B — AgentRegistrar tests per Section 14 canonical flow.

18 tests covering the corrected orchestration per Pass 2C Section 14
(fourth amendment, commit d2911480). All tests use cryptographically
valid mocks per L3a:

  MockKMSClient — real secp256k1 ECDSA signatures via local keys
  MockPinataClient — deterministic mock CIDs (sha256-derived)
  Per-contract web3 mock factories (V8.6) — per-(address, function) canned values

Cross-references:
  bridge/vapi_bridge/agent_registration.py — orchestrator under test (Block B rewrite)
  bridge/vapi_bridge/mock_agent_registration.py — high-level mock + make_mock_web3
  Pass 2C Section 14 (commit d2911480) — canonical specification
  github.com/iotexproject/ioID-contracts at commit b94ad092 — canonical source
"""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.agent_registration import (
    AGENT_REGISTRY_ADDR,
    AGENT_TO_DEVICE_TOKEN_ID,
    EIP712_DOMAIN_NAME,
    EIP712_DOMAIN_TYPEHASH,
    EIP712_DOMAIN_VERSION,
    IOID_CONTRACT_ADDR,
    IOID_REGISTRY_ADDR,
    IOID_STORE_ADDR,
    IOTEX_TESTNET_CHAIN_ID,
    PERMIT_TYPE_HASH,
    PROJECT_REGISTRY_ADDR,
    PROJECT_TYPE_HARDWARE,
    SCOPE_HASH_PHASE_O0_EXIT,
    STATUS_DEFINED,
    VAPI_OPERATOR_AGENTS_PROJECT_NAME,
    AgentRegistrar,
    AgentRegistrationConfigError,
    AgentRegistrationContractError,
    AgentRegistrationEIP712Error,
    AgentRegistrationKMSError,
    AgentRegistrationPinataError,
    AgentRegistrationProjectNotFoundError,
    _compute_eip712_domain_separator,
    _compute_eip712_permit_digest,
    _compute_permit_struct_hash,
    _parse_der_signature_to_vrs,
    compute_agent_id,
    derive_eth_address_from_kms_public_key,
)
from vapi_bridge.mock_agent_registration import (
    _MOCK_BRIDGE_WALLET,
    _MOCK_DEVICE_NFT_ADDR,
    _MOCK_DOMAIN_SEPARATOR,
    _MOCK_IPROJECT_ADDR,
    _MOCK_PRICE_WEI,
    _MOCK_PROJECT_TOKEN_ID,
    _mock_tba_for_token_id,
    make_mock_agent_registrar,
    make_mock_web3,
)
from vapi_bridge.mock_kms_client import MockKMSClient
from vapi_bridge.mock_pinata_client import MockPinataClient


# ---------------------------------------------------------------------------
# Per-contract mock factories (V8.6) — fine-grained for test isolation
# ---------------------------------------------------------------------------

def _make_mock_iproject(balance: int = 1, token_id: int = 1) -> MagicMock:
    """Mock IProject NFT contract with configurable balance + tokenOfOwnerByIndex."""
    mock = MagicMock()
    bal_func = MagicMock()
    bal_func.call = AsyncMock(return_value=balance)
    mock.functions.balanceOf = MagicMock(return_value=bal_func)

    tok_func = MagicMock()
    tok_func.call = AsyncMock(return_value=token_id)
    mock.functions.tokenOfOwnerByIndex = MagicMock(return_value=tok_func)
    return mock


def _make_mock_project_registry(iproject_addr: str = _MOCK_IPROJECT_ADDR, register_returns: int = 1) -> MagicMock:
    """Mock ProjectRegistry with project() + register() returning canned values."""
    mock = MagicMock()
    proj_func = MagicMock()
    proj_func.call = AsyncMock(return_value=iproject_addr)
    mock.functions.project = MagicMock(return_value=proj_func)

    reg_func = MagicMock()
    reg_func.call = AsyncMock(return_value=register_returns)
    mock.functions.register = MagicMock(return_value=reg_func)
    return mock


def _make_mock_ioid_registry(nonce_returns: int = 0) -> MagicMock:
    """Mock ioIDRegistry with register (void) + nonces + DOMAIN_SEPARATOR."""
    mock = MagicMock()
    reg_func = MagicMock()
    reg_func.call = AsyncMock(return_value=None)
    mock.functions.register = MagicMock(return_value=reg_func)

    nonce_func = MagicMock()
    nonce_func.call = AsyncMock(return_value=nonce_returns)
    mock.functions.nonces = MagicMock(return_value=nonce_func)

    ds_func = MagicMock()
    ds_func.call = AsyncMock(return_value=_MOCK_DOMAIN_SEPARATOR)
    mock.functions.DOMAIN_SEPARATOR = MagicMock(return_value=ds_func)
    return mock


def _make_mock_ioid_store(price_returns: int = _MOCK_PRICE_WEI, dcp_returns: int = 1) -> MagicMock:
    """Mock ioIDStore with price + setDeviceContract + applyIoIDs + deviceContractProject."""
    mock = MagicMock()
    price_func = MagicMock()
    price_func.call = AsyncMock(return_value=price_returns)
    mock.functions.price = MagicMock(return_value=price_func)

    setup_func = MagicMock()
    setup_func.call = AsyncMock(return_value=None)
    mock.functions.setDeviceContract = MagicMock(return_value=setup_func)

    apply_func = MagicMock()
    apply_func.call = AsyncMock(return_value=None)
    mock.functions.applyIoIDs = MagicMock(return_value=apply_func)

    dcp_func = MagicMock()
    dcp_func.call = AsyncMock(return_value=dcp_returns)
    mock.functions.deviceContractProject = MagicMock(return_value=dcp_func)
    return mock


def _make_mock_ioid(tba_returns: str = "0x" + "0" * 38 + "01") -> MagicMock:
    """Mock ioID per-DID NFT contract with wallet() returning (tba, did) tuple."""
    mock = MagicMock()
    wallet_func = MagicMock()
    wallet_func.call = AsyncMock(return_value=(tba_returns, "did:io:0xmock"))
    mock.functions.wallet = MagicMock(return_value=wallet_func)
    return mock


def _make_mock_device_nft(mint_returns: int = 1) -> MagicMock:
    """Mock VAPIOperatorAgentNFT with mint + configureMinter + total."""
    mock = MagicMock()
    mint_func = MagicMock()
    mint_func.call = AsyncMock(return_value=mint_returns)
    mock.functions.mint = MagicMock(return_value=mint_func)

    config_func = MagicMock()
    config_func.call = AsyncMock(return_value=None)
    mock.functions.configureMinter = MagicMock(return_value=config_func)

    total_func = MagicMock()
    total_func.call = AsyncMock(return_value=0)
    mock.functions.total = MagicMock(return_value=total_func)
    return mock


def _make_mock_agent_registry(register_returns: str = "0xdeadbeefcafe0001") -> MagicMock:
    """Mock AgentRegistry with registerAgent."""
    mock = MagicMock()
    reg_func = MagicMock()
    reg_func.call = AsyncMock(return_value=register_returns)
    mock.functions.registerAgent = MagicMock(return_value=reg_func)
    return mock


def _make_test_registrar(
    vapi_device_nft_addr: str = _MOCK_DEVICE_NFT_ADDR,
    bridge_wallet: str = _MOCK_BRIDGE_WALLET,
    **overrides,
) -> AgentRegistrar:
    """Construct AgentRegistrar with full deterministic web3 mock (per V8.6)."""
    kms = overrides.pop("kms", MockKMSClient())
    pinata = overrides.pop("pinata", MockPinataClient())
    web3 = overrides.pop("web3", make_mock_web3())
    return AgentRegistrar(
        kms_client=kms,
        pinata_client=pinata,
        web3_async=web3,
        bridge_wallet_address=bridge_wallet,
        vapi_operator_agent_nft_addr=vapi_device_nft_addr,
        **overrides,
    )


# ===========================================================================
# Test 1: test_check_project_nft_succeeds_when_owned
# ===========================================================================

@pytest.mark.asyncio
async def test_check_project_nft_succeeds_when_owned():
    """check_project_nft returns project tokenId when bridge_wallet owns IProject NFT."""
    registrar = _make_test_registrar()
    token_id = await registrar.check_project_nft(_MOCK_BRIDGE_WALLET)
    assert token_id == _MOCK_PROJECT_TOKEN_ID
    assert isinstance(token_id, int)


# ===========================================================================
# Test 2: test_check_project_nft_raises_when_not_owned
# ===========================================================================

@pytest.mark.asyncio
async def test_check_project_nft_raises_when_not_owned():
    """check_project_nft raises AgentRegistrationProjectNotFoundError when balance=0."""
    web3 = MagicMock()
    pr_mock = _make_mock_project_registry()
    ip_mock = _make_mock_iproject(balance=0)  # bridge owns no project NFTs

    def make_contract(address=None, abi=None, **kw):
        addr = str(address).lower()
        if addr == PROJECT_REGISTRY_ADDR.lower():
            return pr_mock
        if addr == _MOCK_IPROJECT_ADDR.lower():
            return ip_mock
        return MagicMock()

    web3.eth.contract = MagicMock(side_effect=make_contract)
    registrar = _make_test_registrar(web3=web3)

    with pytest.raises(AgentRegistrationProjectNotFoundError) as exc_info:
        await registrar.check_project_nft(_MOCK_BRIDGE_WALLET)
    assert "owns no project NFT" in str(exc_info.value)


# ===========================================================================
# Test 3: test_register_project_calls_correct_contract
# ===========================================================================

@pytest.mark.asyncio
async def test_register_project_calls_correct_contract():
    """register_project calls ProjectRegistry.register with project name + type=0."""
    web3 = MagicMock()
    pr_mock = _make_mock_project_registry(register_returns=42)
    web3.eth.contract = MagicMock(return_value=pr_mock)
    registrar = _make_test_registrar(web3=web3)

    token_id = await registrar.register_project()
    assert token_id == 42

    pr_mock.functions.register.assert_called_once_with(
        VAPI_OPERATOR_AGENTS_PROJECT_NAME,
        PROJECT_TYPE_HARDWARE,
    )

    # Verify ProjectRegistry address used
    call_args = web3.eth.contract.call_args
    addr = call_args[1].get("address") or call_args[0][0]
    assert str(addr) == PROJECT_REGISTRY_ADDR


# ===========================================================================
# Test 4: test_setup_device_contract_calls_correct_function
# ===========================================================================

@pytest.mark.asyncio
async def test_setup_device_contract_calls_correct_function():
    """setup_device_contract calls ioIDStore.setDeviceContract(projectId, deviceNft)."""
    web3 = MagicMock()
    store_mock = _make_mock_ioid_store()
    web3.eth.contract = MagicMock(return_value=store_mock)
    registrar = _make_test_registrar(web3=web3)

    await registrar.setup_device_contract(7, _MOCK_DEVICE_NFT_ADDR)
    store_mock.functions.setDeviceContract.assert_called_once_with(
        7, _MOCK_DEVICE_NFT_ADDR,
    )


# ===========================================================================
# Test 5: test_apply_ioids_calculates_correct_value
# ===========================================================================

@pytest.mark.asyncio
async def test_apply_ioids_calculates_correct_value():
    """apply_ioids returns count * price (queried from ioIDStore.price)."""
    web3 = MagicMock()
    store_mock = _make_mock_ioid_store(price_returns=_MOCK_PRICE_WEI)
    web3.eth.contract = MagicMock(return_value=store_mock)
    registrar = _make_test_registrar(web3=web3)

    total = await registrar.apply_ioids(project_token_id=1, count=2)
    assert total == 2 * _MOCK_PRICE_WEI  # 0.2 IOTX in wei

    store_mock.functions.applyIoIDs.assert_called_once_with(1, 2)


# ===========================================================================
# Test 6: test_mint_device_nft_returns_token_id
# ===========================================================================

@pytest.mark.asyncio
async def test_mint_device_nft_returns_token_id():
    """mint_device_nft returns the minted device tokenId from VAPIOperatorAgentNFT.mint."""
    web3 = MagicMock()
    nft_mock = _make_mock_device_nft(mint_returns=1)
    web3.eth.contract = MagicMock(return_value=nft_mock)
    registrar = _make_test_registrar(web3=web3)

    token_id = await registrar.mint_device_nft("anchor-sentry")
    assert token_id == 1

    nft_mock.functions.mint.assert_called_once_with(_MOCK_BRIDGE_WALLET)


# ===========================================================================
# Test 7: test_compute_eip712_permit_digest_matches_canonical_domain
# ===========================================================================

def test_compute_eip712_permit_digest_matches_canonical_domain():
    """Bridge-computed EIP-712 domain separator matches on-chain value byte-for-byte.

    Per Section 14.3: empirical verification confirmed bridge computation
    produces the exact on-chain DOMAIN_SEPARATOR returned by ioIDRegistry's
    public getter at chain 4690.
    """
    computed = _compute_eip712_domain_separator(
        IOTEX_TESTNET_CHAIN_ID, IOID_REGISTRY_ADDR,
    )
    assert computed == _MOCK_DOMAIN_SEPARATOR
    assert computed.hex() == "4e31e01d4e41f6c9dc9d68103971ef473adf267bd74326f72170daac66329bcc"

    # Permit struct hash for known (user, nonce) pair
    user = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
    struct_hash = _compute_permit_struct_hash(user, 0)
    assert len(struct_hash) == 32

    # Full permit digest composes correctly
    digest = _compute_eip712_permit_digest(computed, user, 0)
    assert len(digest) == 32
    # Deterministic: same inputs → same digest
    digest2 = _compute_eip712_permit_digest(computed, user, 0)
    assert digest == digest2

    # Different nonce → different digest
    digest_other = _compute_eip712_permit_digest(computed, user, 1)
    assert digest_other != digest


# ===========================================================================
# Test 8: test_query_device_nonce_returns_current_value
# ===========================================================================

@pytest.mark.asyncio
async def test_query_device_nonce_returns_current_value():
    """query_device_nonce reads ioIDRegistry.nonces(device) view."""
    web3 = MagicMock()
    reg_mock = _make_mock_ioid_registry(nonce_returns=5)
    web3.eth.contract = MagicMock(return_value=reg_mock)
    registrar = _make_test_registrar(web3=web3)

    device_addr = "0x1111111111111111111111111111111111111111"
    nonce = await registrar.query_device_nonce(device_addr)
    assert nonce == 5
    assert isinstance(nonce, int)

    reg_mock.functions.nonces.assert_called_once_with(device_addr)


# ===========================================================================
# Test 9: test_parse_der_signature_to_vrs_correct_components
# ===========================================================================

@pytest.mark.asyncio
async def test_parse_der_signature_to_vrs_correct_components():
    """_parse_der_signature_to_vrs recovers correct (v, r, s) from DER signature.

    Cryptographically valid end-to-end test: MockKMSClient produces a real
    ECDSA signature; parser recovers (v, r, s) such that ecrecover(digest,
    v, r, s) returns the agent's KMS-derived address.
    """
    kms = MockKMSClient(agents=("anchor-sentry",))
    der_pubkey = await kms.get_public_key("anchor-sentry")
    expected_addr = derive_eth_address_from_kms_public_key(der_pubkey)

    # Construct a 32-byte digest; sign it; parse the signature
    digest = bytes.fromhex("a" * 64)
    der_signature = await kms.sign("anchor-sentry", digest)

    v, r, s = _parse_der_signature_to_vrs(der_signature, digest, expected_addr)

    assert v in (27, 28)
    assert len(r) == 32
    assert len(s) == 32

    # Recovery: use the (v, r, s) to recover the signer; must equal expected_addr
    from eth_keys import KeyAPI
    from eth_utils import to_checksum_address

    keys = KeyAPI()
    r_int = int.from_bytes(r, "big")
    s_int = int.from_bytes(s, "big")
    sig = keys.Signature(vrs=(v - 27, r_int, s_int))
    recovered_pub = keys.ecdsa_recover(digest, sig)
    recovered_addr = to_checksum_address(recovered_pub.to_address())
    assert recovered_addr == expected_addr


# ===========================================================================
# Test 10: test_mint_ioid_did_uses_eight_parameter_signature
# ===========================================================================

@pytest.mark.asyncio
async def test_mint_ioid_did_uses_eight_parameter_signature():
    """mint_ioid_did calls ioIDRegistry.register with all 8 parameters per M1."""
    web3 = MagicMock()
    reg_mock = _make_mock_ioid_registry()
    web3.eth.contract = MagicMock(return_value=reg_mock)
    registrar = _make_test_registrar(web3=web3)

    await registrar.mint_ioid_did(
        device_token_id=1,
        device_address="0x" + "1" * 40,
        content_hash=bytes.fromhex("ab" * 32),
        uri="bafkmocktest",
        v=27,
        r=bytes.fromhex("cd" * 32),
        s=bytes.fromhex("ef" * 32),
    )

    # Verify register was called with 8 positional args
    call_args = reg_mock.functions.register.call_args
    args = call_args[0]
    assert len(args) == 8, f"register must be called with 8 args (M1 wrapper); got {len(args)}"
    assert args[0] == _MOCK_DEVICE_NFT_ADDR  # deviceContract
    assert args[1] == 1                       # tokenId
    assert args[2] == "0x" + "1" * 40        # device
    assert args[3] == bytes.fromhex("ab" * 32)  # hash
    assert args[4] == "bafkmocktest"          # uri
    assert args[5] == 27                       # v
    assert args[6] == bytes.fromhex("cd" * 32)  # r
    assert args[7] == bytes.fromhex("ef" * 32)  # s


# ===========================================================================
# Test 11: test_readback_tba_via_ioid_wallet
# ===========================================================================

@pytest.mark.asyncio
async def test_readback_tba_via_ioid_wallet():
    """readback_tba calls ioID.wallet(tokenId) and returns the TBA address.

    Per M6: bridge code does NOT call ERC6551Registry. TBA address is read
    via ioID.wallet view (which internally calls ERC6551Registry.account
    with canonical ioID-internal parameters: salt=0, token contract=ioID).
    """
    expected_tba = "0x" + "0" * 38 + "01"
    web3 = MagicMock()
    ioid_mock = _make_mock_ioid(tba_returns=expected_tba)
    web3.eth.contract = MagicMock(return_value=ioid_mock)
    registrar = _make_test_registrar(web3=web3)

    tba = await registrar.readback_tba(ioid_token_id=1)
    assert tba == expected_tba

    # Verify ioID contract address used (NOT ERC6551Registry)
    call_args = web3.eth.contract.call_args
    addr = call_args[1].get("address") or call_args[0][0]
    assert str(addr) == IOID_CONTRACT_ADDR

    ioid_mock.functions.wallet.assert_called_once_with(1)


# ===========================================================================
# Test 12: test_register_full_flow_orchestrates_section_14_order
# ===========================================================================

@pytest.mark.asyncio
async def test_register_full_flow_orchestrates_section_14_order():
    """register_full_flow chains all 13 Section 14 steps and returns expected dict."""
    registrar = _make_test_registrar()

    result = await registrar.register_full_flow("anchor-sentry")

    # All expected keys present
    expected_keys = {
        "agent", "agent_address", "ioid_did_address", "device_token_id",
        "tba_address", "agent_id", "did_document_cid", "did_content_hash",
        "permit_nonce", "tx_hash",
    }
    assert set(result.keys()) >= expected_keys

    # Values consistent with mock returns
    assert result["agent"] == "anchor-sentry"
    assert result["device_token_id"] == 1
    assert result["permit_nonce"] == 0
    assert result["tba_address"].startswith("0x")
    assert result["did_document_cid"].startswith("bafk")
    assert result["did_content_hash"].startswith("0x")
    assert len(result["did_content_hash"]) == 66  # 0x + 64 hex
    assert result["agent_id"].startswith("0x") and len(result["agent_id"]) == 66
    # ioid_did_address per canonical convention IS the device's ETH address
    assert result["ioid_did_address"] == result["agent_address"]


# ===========================================================================
# Test 13: test_register_full_flow_raises_when_project_nft_missing
# ===========================================================================

@pytest.mark.asyncio
async def test_register_full_flow_raises_when_project_nft_missing():
    """register_full_flow raises ProjectNotFoundError when bridge owns no project NFT."""
    web3 = MagicMock()
    pr_mock = _make_mock_project_registry()
    ip_mock = _make_mock_iproject(balance=0)  # no project owned

    def make_contract(address=None, abi=None, **kw):
        addr = str(address).lower()
        if addr == PROJECT_REGISTRY_ADDR.lower():
            return pr_mock
        if addr == _MOCK_IPROJECT_ADDR.lower():
            return ip_mock
        return MagicMock()

    web3.eth.contract = MagicMock(side_effect=make_contract)
    registrar = _make_test_registrar(web3=web3)

    with pytest.raises(AgentRegistrationProjectNotFoundError):
        await registrar.register_full_flow("anchor-sentry")


# ===========================================================================
# Test 14: test_register_agent_uses_q9_agentid_encoding
# ===========================================================================

@pytest.mark.asyncio
async def test_register_agent_uses_q9_agentid_encoding():
    """register_agent computes agentId per Pass 2C Q9 FROZEN encoding (unchanged from dcaf5015)."""
    ioid_did = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    tba = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"

    expected = compute_agent_id(ioid_did, tba)
    assert len(expected) == 32

    # Determinism: same inputs → same agentId
    assert compute_agent_id(ioid_did, tba) == expected

    # Different inputs → different agentId
    different = compute_agent_id(ioid_did, "0xcccccccccccccccccccccccccccccccccccccccc")
    assert different != expected

    # Wire through register_agent end-to-end
    registrar = _make_test_registrar()
    tx_hash = await registrar.register_agent(
        agent="anchor-sentry",
        ioid_did_address=ioid_did,
        tba_address=tba,
        did_document_cid="bafkmocktest",
    )
    assert tx_hash == "0xdeadbeefcafe0001"


# ===========================================================================
# Test 15: test_register_agent_handles_kms_error
# ===========================================================================

@pytest.mark.asyncio
async def test_register_agent_handles_kms_error():
    """register_agent raises AgentRegistrationKMSError when KMS get_public_key fails."""
    failing_kms = MockKMSClient()

    async def failing_get_public_key(agent):
        raise RuntimeError("KMS network error")

    failing_kms.get_public_key = failing_get_public_key
    registrar = _make_test_registrar(kms=failing_kms)

    with pytest.raises(AgentRegistrationKMSError) as exc_info:
        await registrar.register_agent(
            agent="anchor-sentry",
            ioid_did_address="0x" + "a" * 40,
            tba_address="0x" + "b" * 40,
            did_document_cid="bafkmocktest",
        )
    assert "KMS network error" in str(exc_info.value)


# ===========================================================================
# Test 16: test_register_agent_handles_pinata_error
# ===========================================================================

@pytest.mark.asyncio
async def test_register_agent_handles_pinata_error():
    """pin_did_document raises AgentRegistrationPinataError when Pinata fails."""
    failing_pinata = MockPinataClient()

    async def failing_pin_json(content, name, cid_version=1):
        raise RuntimeError("Pinata API error")

    failing_pinata.pin_json = failing_pin_json
    registrar = _make_test_registrar(pinata=failing_pinata)

    with pytest.raises(AgentRegistrationPinataError) as exc_info:
        await registrar.pin_did_document({"id": "test"}, "anchor-sentry")
    assert "Pinata API error" in str(exc_info.value)


# ===========================================================================
# Test 17: test_register_agent_handles_eip712_error
# ===========================================================================

@pytest.mark.asyncio
async def test_register_agent_handles_eip712_error():
    """_parse_der_signature_to_vrs raises EIP712Error when DER cannot recover expected signer."""
    # Construct synthetic DER + digest combo: signature won't recover to expected_signer.
    # DER format: 0x30 LEN 0x02 LEN R 0x02 LEN S
    # SEQUENCE(68) || INTEGER(32) r || INTEGER(32) s
    der_hex = "3044" + "0220" + ("01" * 32) + "0220" + ("02" * 32)
    invalid_der = bytes.fromhex(der_hex)
    digest = bytes.fromhex("c" * 64)
    expected_signer = "0x" + "9" * 40  # never recovers from synthetic signature

    with pytest.raises(AgentRegistrationEIP712Error) as exc_info:
        _parse_der_signature_to_vrs(invalid_der, digest, expected_signer)
    assert "Could not recover expected signer" in str(exc_info.value)


# ===========================================================================
# Test 18: test_section_14_constants_match_pass_2c_specs
# ===========================================================================

def test_section_14_constants_match_pass_2c_specs():
    """Pass 2C Section 14 + Section 7 constants match canonical specifications."""
    # Section 7: scopeHash = bytes32(0)
    assert SCOPE_HASH_PHASE_O0_EXIT == b"\x00" * 32
    # Section 6.4: status = STATUS_DEFINED = 0
    assert STATUS_DEFINED == 0
    # Section 14.5: project type 0 = "hardware project"
    assert PROJECT_TYPE_HARDWARE == 0
    # Stream 2-deploy AgentRegistry per commit d019c067
    assert AGENT_REGISTRY_ADDR == "0x9548E9d17c2d40350629b1b88ff1D2c01B0414a4"
    # Section 14 verified addresses (ioID infrastructure)
    assert PROJECT_REGISTRY_ADDR == "0x060581AA1A4e0cC92FBd74d251913238De2F13cd"
    assert IOID_REGISTRY_ADDR == "0x0A7e595C7889dF3652A19aF52C18377bF17e027D"
    assert IOID_STORE_ADDR == "0x60cac5CE11cb2F98bF179BE5fd3D801C3D5DBfF2"
    # N4 — ioID contract is canonical TBA token contract (NOT IProject)
    assert IOID_CONTRACT_ADDR == "0x45Ce3E6f526e597628c73B731a3e9Af7Fc32f5b7"
    # Section 14 chain ID (IoTeX testnet)
    assert IOTEX_TESTNET_CHAIN_ID == 4690
    # Section 14.3 EIP-712 domain
    assert EIP712_DOMAIN_NAME == "ioIDRegistry"
    assert EIP712_DOMAIN_VERSION == "1"
    # Section 14.3 type hashes (canonical per ioIDRegistry.sol lines 22-26)
    from eth_hash.auto import keccak
    assert EIP712_DOMAIN_TYPEHASH == keccak(
        b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    assert PERMIT_TYPE_HASH == keccak(b"Permit(address owner,uint256 nonce)")
    # N2 β agent → device tokenId mapping (FROZEN at first registration).
    # Phase 238 Step I-FINAL added curator → 3 (third Operator Initiative agent).
    assert AGENT_TO_DEVICE_TOKEN_ID == {"anchor-sentry": 1, "guardian": 2, "curator": 3}
    # N2 β canonical project name
    assert VAPI_OPERATOR_AGENTS_PROJECT_NAME == "VAPI Operator Agents"


# ===========================================================================
# Bonus: VAPI_OPERATOR_AGENT_NFT_ADDR placeholder ConfigError on register_full_flow
# ===========================================================================

@pytest.mark.asyncio
async def test_mint_device_nft_raises_config_error_when_placeholder_address():
    """Per V8.3: mint_device_nft raises ConfigError if VAPI_OPERATOR_AGENT_NFT_ADDR is placeholder."""
    registrar = _make_test_registrar(
        vapi_device_nft_addr="0x0000000000000000000000000000000000000000",
    )
    with pytest.raises(AgentRegistrationConfigError) as exc_info:
        await registrar.mint_device_nft("anchor-sentry")
    assert "placeholder zero" in str(exc_info.value)
