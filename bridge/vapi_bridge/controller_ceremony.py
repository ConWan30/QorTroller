"""ioID Controller Ceremony (Inc-C) - pure guards + constants + least-privilege
ABIs for the prerequisite-tx ceremony that makes VAPIGamerControllerNFT registerable
as an ioID device:

    ProjectRegistry.register("QorTroller Controllers", 0)   (project token id)
      -> ioIDStore.setDeviceContract(projectTokenId, NFT)   (1:1 mapping, M4)
      -> [optional] ioIDStore.applyIoIDs(projectTokenId, N) {value: N*price}
      -> VAPIGamerControllerNFT.mint(gamer)                 (controller token id)

The chain submission lives in scripts/operator_session_register_controller.py
(operator-fired, estimate-first, triple-gated, one step per invoke). This module
is the TESTABLE CORE: deployed-address resolution + fail-honest prerequisite guards
+ the least-privilege write ABI for the controller NFT.

Single-source discipline: the ioID SYSTEM addresses + ABIs (ProjectRegistry /
ioIDStore / IProject) are imported from agent_registration (canonical b94ad092),
never re-hardcoded here - the controller path is a mirror of the agent-proven
ceremony, so it shares the exact same system anchors.
"""
from __future__ import annotations

import enum
from typing import Optional

# Canonical ioID system anchors (b94ad092) - imported, not re-hardcoded.
from vapi_bridge.agent_registration import (  # noqa: F401  (re-exported for the CLI)
    PROJECT_REGISTRY_ADDR,
    IOID_STORE_ADDR,
    PROJECT_REGISTRY_ABI,
    IOID_STORE_ABI,
    IPROJECT_ABI,
)

# The controller's OWN ioID project. Separate from the agents' "VAPI Operator
# Agents" project because ioIDStore maps deviceContract<->project 1:1 (M4) - a
# controller NFT cannot share the agents' project slot.
CONTROLLER_PROJECT_NAME = "QorTroller Controllers"
CONTROLLER_PROJECT_TYPE = 0  # hardware project (ioIDStore.applyIoIDs constraint, N2 beta)

# deployed-addresses.json key that Inc-A writes on a successful NFT deploy.
CONTROLLER_NFT_ADDRESS_KEY = "VAPIGamerControllerNFT"

# The bridge wallet is owner + configured minter of the controller NFT and owner
# of the controller project (dev-self ceremony). Every write step is gated on the
# caller being this wallet.
BRIDGE_WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
ZERO_ADDRESS = "0x" + "00" * 20

# ERC-721 Transfer topic0 = keccak("Transfer(address,address,uint256)"). Used to
# read back the minted tokenId (and the project tokenId) unambiguously from a
# receipt's logs - never inferred from enumeration ordering.
TRANSFER_TOPIC0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Least-privilege write+read ABI for the controller DeviceNFT. `mint` is the only
# writer; the rest are readback views for the ceremony's exit assertions. Declared
# LOCALLY (not the bridge's read ABI) so this surface never grants write power to a
# read-only ABI by accident - the V-N5 least-privilege discipline that
# provision_device_mfg.py established for registerDevice.
CONTROLLER_NFT_ABI = [
    {"type": "function", "name": "mint", "stateMutability": "nonpayable",
     "inputs": [{"name": "_to", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}]},
    {"type": "function", "name": "balanceOf", "stateMutability": "view",
     "inputs": [{"name": "owner", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}]},
    {"type": "function", "name": "ownerOf", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}],
     "outputs": [{"name": "", "type": "address"}]},
    {"type": "function", "name": "isMinter", "stateMutability": "view",
     "inputs": [{"name": "account", "type": "address"}],
     "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "minterAllowance", "stateMutability": "view",
     "inputs": [{"name": "minter", "type": "address"}],
     "outputs": [{"name": "", "type": "uint256"}]},
    # `total` is the contract's monotonic mint counter (mint does `_tokenId = ++total`).
    # After a single mint by the sole minter it EQUALS the minted tokenId - the
    # deterministic fallback when the Transfer-log parse comes up empty (this NFT is
    # NOT ERC721Enumerable, so tokenOfOwnerByIndex is unavailable).
    {"type": "function", "name": "total", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
    {"anonymous": False, "type": "event", "name": "Transfer", "inputs": [
        {"indexed": True, "name": "from", "type": "address"},
        {"indexed": True, "name": "to", "type": "address"},
        {"indexed": True, "name": "tokenId", "type": "uint256"}]},
]


class CeremonyError(Exception):
    """Base for controller-ceremony guard failures."""


class CeremonyPrereqError(CeremonyError):
    """A required PRIOR step has not been completed. Fail-honest - the ceremony
    never fabricates an address or a tokenId to keep moving."""


class CeremonyStep(enum.Enum):
    REGISTER_PROJECT = "register-project"
    SET_DEVICE_CONTRACT = "set-device-contract"
    APPLY_IOIDS = "apply-ioids"
    MINT = "mint"


def _is_addr(v: object) -> bool:
    return isinstance(v, str) and v.startswith("0x") and len(v) == 42


def resolve_controller_nft_address(deployed: dict) -> Optional[str]:
    """Return the deployed VAPIGamerControllerNFT address, or None if Inc-A has
    not been broadcast yet. Only a real 42-char 0x address VALUE at the top-level
    key counts - description strings elsewhere in the file that merely MENTION the
    key name are ignored (they are not the deployed address)."""
    v = deployed.get(CONTROLLER_NFT_ADDRESS_KEY)
    return v if _is_addr(v) else None


def assert_nft_deployed(deployed: dict) -> str:
    """Fail-honest: the NFT must exist on-chain (Inc-A) before setDeviceContract
    or mint can consume it."""
    addr = resolve_controller_nft_address(deployed)
    if addr is None:
        raise CeremonyPrereqError(
            f"{CONTROLLER_NFT_ADDRESS_KEY} is not deployed yet - run Inc-A first:\n"
            f"  VAPI_GCN_DEPLOY_CONFIRM=1 npx hardhat run "
            f"contracts/scripts/deploy-vapi-gamer-controller-nft.js --network iotex_testnet\n"
            f"setDeviceContract + mint consume the deployed address."
        )
    return addr


def assert_project_token_id(value: object) -> int:
    """A real project tokenId (>0) is required for setDeviceContract / applyIoIDs.
    Zero means register-project has not been run (or its output was not captured)."""
    try:
        iv = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise CeremonyPrereqError(
            f"project token id must be an integer > 0, got {value!r} - run "
            f"{CeremonyStep.REGISTER_PROJECT.value} first and pass the printed "
            f"PROJECT_TOKEN_ID"
        )
    if iv <= 0:
        raise CeremonyPrereqError(
            f"project token id must be > 0, got {iv} - run "
            f"{CeremonyStep.REGISTER_PROJECT.value} first and pass the printed "
            f"PROJECT_TOKEN_ID"
        )
    return iv


def assert_gamer_address(addr: str) -> str:
    """The mint recipient (the sovereign gamer; dev-self = the bridge wallet).
    Must be a non-zero 20-byte address."""
    if not _is_addr(addr):
        raise CeremonyError(f"gamer address must be 0x-prefixed 20-byte hex, got {addr!r}")
    if addr.lower() == ZERO_ADDRESS:
        raise CeremonyError("gamer address must not be the zero address")
    return addr


def is_bridge_caller(caller: str, bridge: str = BRIDGE_WALLET) -> bool:
    """Every write step is gated on the caller being the bridge wallet (owner +
    minter + project owner in the dev-self ceremony)."""
    return isinstance(caller, str) and caller.lower() == bridge.lower()


def hard_cap_ok(buffered_iotx: float, cap_iotx: float) -> bool:
    """Estimate-first spend gate: buffered cost must not exceed the per-step cap."""
    return buffered_iotx <= cap_iotx


def _topic_hex(x: object) -> str:
    """Normalize a log topic (HexBytes | bytes | str, bare or 0x-prefixed) to a
    lowercase 0x-hex string. HexBytes.hex()/bytes.hex() return BARE hex here (the
    Inc-B F1 lesson), so a missing 0x prefix is added rather than a byte dropped."""
    h = x.hex() if hasattr(x, "hex") else str(x)
    h = h.lower()
    return h if h.startswith("0x") else "0x" + h


def minted_token_id_from_logs(logs, contract_addr: str, expected_to: str) -> Optional[int]:
    """PURE: return the tokenId MINTED (from == 0x0) to `expected_to` by a
    Transfer(0x0, to, id) log emitted by `contract_addr` in these receipt logs.

    Robust (grok r04 F2/F3): requires a 4-topic ERC-721 Transfer (an ERC-20-shaped
    3-topic Transfer with the same topic0 is SKIPPED), requires from == 0x0 (a
    mint, not a transfer), handles bare/0x-prefixed AND HexBytes/dict log shapes,
    and never IndexErrors. Returns None if no matching mint log is present (the
    caller then falls back to the on-chain counter, never prints None)."""
    want = str(contract_addr).lower()
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
        if len(topics) < 4:                      # ERC-721 Transfer = sig+from+to+id
            continue
        t = [_topic_hex(x) for x in topics[:4]]
        if t[0] != TRANSFER_TOPIC0:
            continue
        if int(t[1][-40:] or "0", 16) != 0:      # from must be 0x0 (mint)
            continue
        if ("0x" + t[2][-40:]).lower() != str(expected_to).lower():
            continue
        return int(t[3], 16)
    return None


def assert_mint_authorized(*, is_minter: bool, minter_allowance: int) -> None:
    """Preflight for the mint step: the bridge wallet must be a configured minter
    with remaining allowance. Failure points back to Inc-A's configureMinter."""
    if not is_minter:
        raise CeremonyPrereqError(
            "bridge wallet is not a configured minter on the controller NFT - "
            "Inc-A's configureMinter(bridge, N) must have run"
        )
    if int(minter_allowance) < 1:
        raise CeremonyPrereqError(
            f"minter allowance exhausted (allowance={minter_allowance}) - "
            f"re-run configureMinter to grant more before minting"
        )
