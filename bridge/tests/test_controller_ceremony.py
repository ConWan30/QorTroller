"""Inc-C — unit tests for the controller-ceremony pure core (guards + constants +
least-privilege ABI). The chain submission in
scripts/operator_session_register_controller.py is operator-fired and verified at
run time; these tests pin the fail-honest guards that gate every step."""
import json
from pathlib import Path

import pytest

from vapi_bridge.controller_ceremony import (
    CONTROLLER_PROJECT_NAME, CONTROLLER_PROJECT_TYPE, CONTROLLER_NFT_ADDRESS_KEY,
    BRIDGE_WALLET, ZERO_ADDRESS, TRANSFER_TOPIC0, CONTROLLER_NFT_ABI,
    PROJECT_REGISTRY_ADDR, IOID_STORE_ADDR, PROJECT_REGISTRY_ABI, IOID_STORE_ABI,
    CeremonyPrereqError, CeremonyError, CeremonyStep,
    resolve_controller_nft_address, assert_nft_deployed, assert_project_token_id,
    assert_gamer_address, assert_mint_authorized, is_bridge_caller, hard_cap_ok,
    minted_token_id_from_logs,
)

_ADDR = "0x" + "ab" * 20


# ── T-CC-1: NFT address resolution off deployed-addresses.json ────────────────
def test_resolve_nft_address_present():
    assert resolve_controller_nft_address({CONTROLLER_NFT_ADDRESS_KEY: _ADDR}) == _ADDR


def test_resolve_nft_address_absent_returns_none():
    assert resolve_controller_nft_address({}) is None
    assert resolve_controller_nft_address({"OtherKey": _ADDR}) is None


def test_resolve_nft_address_rejects_non_address_values():
    # a description string or a truncated value is NOT a deployed address
    assert resolve_controller_nft_address({CONTROLLER_NFT_ADDRESS_KEY: "the controller DeviceNFT"}) is None
    assert resolve_controller_nft_address({CONTROLLER_NFT_ADDRESS_KEY: "0xdead"}) is None
    assert resolve_controller_nft_address({CONTROLLER_NFT_ADDRESS_KEY: None}) is None


# ── T-CC-2: fail-honest when Inc-A unfired ────────────────────────────────────
def test_assert_nft_deployed_returns_addr_when_present():
    assert assert_nft_deployed({CONTROLLER_NFT_ADDRESS_KEY: _ADDR}) == _ADDR


def test_assert_nft_deployed_raises_with_inc_a_pointer_when_absent():
    with pytest.raises(CeremonyPrereqError) as ei:
        assert_nft_deployed({})
    msg = str(ei.value)
    assert "not deployed yet" in msg
    assert "deploy-vapi-gamer-controller-nft.js" in msg  # points at Inc-A


def test_real_deployed_addresses_nft_still_unfired():
    """Documents current state: Inc-A has not been broadcast, so the ceremony
    fails honest rather than fabricating an address."""
    deployed = json.loads(
        (Path(__file__).resolve().parents[2] / "contracts" / "deployed-addresses.json").read_text())
    assert resolve_controller_nft_address(deployed) is None
    with pytest.raises(CeremonyPrereqError):
        assert_nft_deployed(deployed)


# ── T-CC-3: project token id guard ────────────────────────────────────────────
def test_assert_project_token_id_positive():
    assert assert_project_token_id(5) == 5
    assert assert_project_token_id("5") == 5


@pytest.mark.parametrize("bad", [0, -1, "0", "abc", None])
def test_assert_project_token_id_rejects_nonpositive_or_garbage(bad):
    with pytest.raises(CeremonyPrereqError):
        assert_project_token_id(bad)


# ── T-CC-4: gamer address guard ───────────────────────────────────────────────
def test_assert_gamer_address_valid():
    assert assert_gamer_address(_ADDR) == _ADDR


@pytest.mark.parametrize("bad", [ZERO_ADDRESS, "0xshort", "not-an-address", "abababab", None])
def test_assert_gamer_address_rejects_bad(bad):
    with pytest.raises(CeremonyError):
        assert_gamer_address(bad)


# ── T-CC-5: bridge-caller gate ────────────────────────────────────────────────
def test_is_bridge_caller_case_insensitive_match():
    assert is_bridge_caller(BRIDGE_WALLET.lower()) is True
    assert is_bridge_caller(BRIDGE_WALLET.upper().replace("0X", "0x")) is True


def test_is_bridge_caller_rejects_other():
    assert is_bridge_caller(_ADDR) is False
    assert is_bridge_caller(None) is False


# ── T-CC-6: hard-cap gate ─────────────────────────────────────────────────────
def test_hard_cap_ok_boundaries():
    assert hard_cap_ok(0.4, 0.5) is True
    assert hard_cap_ok(0.5, 0.5) is True     # equal is allowed
    assert hard_cap_ok(0.51, 0.5) is False


# ── T-CC-7: mint authorization preflight ──────────────────────────────────────
def test_assert_mint_authorized_ok():
    assert_mint_authorized(is_minter=True, minter_allowance=1) is None


def test_assert_mint_authorized_not_minter_raises():
    with pytest.raises(CeremonyPrereqError, match="not a configured minter"):
        assert_mint_authorized(is_minter=False, minter_allowance=5)


def test_assert_mint_authorized_no_allowance_raises():
    with pytest.raises(CeremonyPrereqError, match="allowance exhausted"):
        assert_mint_authorized(is_minter=True, minter_allowance=0)


# ── T-CC-8: constants + single-source system anchors ──────────────────────────
def test_controller_project_constants():
    assert CONTROLLER_PROJECT_NAME == "QorTroller Controllers"
    assert CONTROLLER_PROJECT_TYPE == 0
    assert CONTROLLER_NFT_ADDRESS_KEY == "VAPIGamerControllerNFT"
    assert BRIDGE_WALLET.lower().startswith("0x0cf36db5")


def test_system_anchors_imported_not_rehardcoded():
    # b94ad092 canonical addresses, sourced from agent_registration
    assert PROJECT_REGISTRY_ADDR == "0x060581AA1A4e0cC92FBd74d251913238De2F13cd"
    assert IOID_STORE_ADDR == "0x60cac5CE11cb2F98bF179BE5fd3D801C3D5DBfF2"
    assert any(f.get("name") == "register" for f in PROJECT_REGISTRY_ABI)
    assert any(f.get("name") == "setDeviceContract" for f in IOID_STORE_ABI)


# ── T-CC-9: least-privilege NFT ABI + Transfer topic ──────────────────────────
def test_controller_nft_abi_mint_is_only_writer():
    writers = [f for f in CONTROLLER_NFT_ABI
               if f.get("type") == "function" and f.get("stateMutability") == "nonpayable"]
    assert [w["name"] for w in writers] == ["mint"]   # exactly one writer
    assert any(f.get("type") == "event" and f.get("name") == "Transfer" for f in CONTROLLER_NFT_ABI)


def test_transfer_topic0_is_canonical_erc721():
    # keccak256("Transfer(address,address,uint256)")
    from web3 import Web3
    assert TRANSFER_TOPIC0 == "0x" + Web3.keccak(text="Transfer(address,address,uint256)").hex().removeprefix("0x")


def test_ceremony_step_enum_values():
    assert CeremonyStep.REGISTER_PROJECT.value == "register-project"
    assert CeremonyStep.SET_DEVICE_CONTRACT.value == "set-device-contract"
    assert CeremonyStep.MINT.value == "mint"


# ── T-CC-10: pure Transfer-log parser (grok r04 F3 — the load-bearing path) ────
from vapi_bridge.controller_ceremony import TRANSFER_TOPIC0 as _T0

_GAMER = "0x" + "bb" * 20
_NFT = "0x" + "cc" * 20
_ZERO_TOPIC = "0x" + "00" * 32


def _addr_topic(addr):           # 20-byte addr -> 32-byte indexed topic
    return "0x" + "00" * 12 + addr.replace("0x", "")


def _id_topic(tid):
    return "0x" + f"{tid:064x}"


class _Log:
    def __init__(self, address, topics):
        self.address, self.topics = address, topics


class _Bare:
    """mimics HexBytes: .hex() returns BARE hex (no 0x) — the Inc-B F1 trap."""
    def __init__(self, s):
        self._s = s.replace("0x", "")
    def hex(self):
        return self._s


def _mint_log(nft, to, tid, *, bare=False, as_dict=False):
    topics = [_T0, _ZERO_TOPIC, _addr_topic(to), _id_topic(tid)]
    if bare:
        topics = [_Bare(t) for t in topics]
    if as_dict:
        return {"address": nft, "topics": topics}
    return _Log(nft, topics)


def test_parse_mint_log_str_topics():
    assert minted_token_id_from_logs([_mint_log(_NFT, _GAMER, 7)], _NFT, _GAMER) == 7


def test_parse_mint_log_bare_hexbytes_topics():
    # bare .hex() must not drop a byte (the Inc-B F1 lesson, exercised on topics)
    assert minted_token_id_from_logs([_mint_log(_NFT, _GAMER, 42, bare=True)], _NFT, _GAMER) == 42


def test_parse_mint_log_dict_shaped():
    assert minted_token_id_from_logs([_mint_log(_NFT, _GAMER, 3, as_dict=True)], _NFT, _GAMER) == 3


def test_parse_skips_erc20_shaped_3_topic_transfer():
    # same topic0 + address but only 3 topics (ERC-20) -> skipped, never IndexError
    lg = _Log(_NFT, [_T0, _addr_topic("0x" + "11" * 20), _addr_topic(_GAMER)])
    assert minted_token_id_from_logs([lg], _NFT, _GAMER) is None


def test_parse_skips_non_mint_transfer_from_nonzero():
    lg = _Log(_NFT, [_T0, _addr_topic("0x" + "11" * 20), _addr_topic(_GAMER), _id_topic(9)])
    assert minted_token_id_from_logs([lg], _NFT, _GAMER) is None


def test_parse_skips_wrong_recipient():
    assert minted_token_id_from_logs([_mint_log(_NFT, "0x" + "dd" * 20, 5)], _NFT, _GAMER) is None


def test_parse_skips_wrong_contract():
    assert minted_token_id_from_logs([_mint_log("0x" + "ee" * 20, _GAMER, 5)], _NFT, _GAMER) is None


def test_parse_none_when_no_logs():
    assert minted_token_id_from_logs([], _NFT, _GAMER) is None


def test_parse_picks_matching_mint_among_noise():
    logs = [
        _Log("0x" + "ee" * 20, [_T0, _ZERO_TOPIC, _addr_topic(_GAMER), _id_topic(1)]),  # wrong addr
        _Log(_NFT, ["0x" + "ab" * 32]),                                                  # 1-topic noise
        _mint_log(_NFT, _GAMER, 77),                                                     # the mint
    ]
    assert minted_token_id_from_logs(logs, _NFT, _GAMER) == 77
