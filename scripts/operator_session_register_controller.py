"""ioID Controller Ceremony - Inc-C: prerequisite transactions (operator-fired).

Runs the on-chain prerequisites that make the deployed VAPIGamerControllerNFT
registerable as an ioID device, ONE STEP PER INVOKE so each spend is a separate,
explicit operator decision:

  register-project      ProjectRegistry.register("QorTroller Controllers", 0)
                          -> prints PROJECT_TOKEN_ID (read from the Transfer log)
  set-device-contract   ioIDStore.setDeviceContract(PROJECT_TOKEN_ID, NFT)  (M4 1:1 map)
  apply-ioids           ioIDStore.applyIoIDs(PROJECT_TOKEN_ID, N) {value: N*price}  (OPTIONAL pre-pay)
  mint                  VAPIGamerControllerNFT.mint(gamer)
                          -> prints CONTROLLER_TOKEN_ID (read from the Transfer log)

Each subcommand is ESTIMATE-FIRST + TRIPLE-GATED, mirroring scripts/provision_device_mfg.py:
  (1) caller must be the bridge wallet          (controller_ceremony.is_bridge_caller)
  (2) buffered cost must be <= the per-step cap (controller_ceremony.hard_cap_ok)
  (3) --execute AND IOID_CONTROLLER_CEREMONY_CONFIRM=1 required to broadcast

Default (no --execute): estimate-only, prints the cost, does NOT broadcast.
estimate_gas is also the pre-send revert guard (it reverts if the call would revert).
receipt.status is checked after every broadcast (a mined-but-reverted tx returns a receipt).

Sequencing (hard constraints, grok r04 F6): NFT deployed (Inc-A) + project
registered before set-device-contract; mint requires the NFT deployed but is
INDEPENDENT of the mapping; both the mapping AND the mint must precede the Inc-D
register. Deploy<->project order can swap; mint<->map order can swap.

Env: IOTEX_RPC_URL (default babel-api.testnet.iotex.io), BRIDGE_PRIVATE_KEY,
     IOID_CONTROLLER_CEREMONY_CONFIRM=1 (broadcast gate).

Honest ceiling: dev-self ceremony (the "gamer" = the operator's bridge wallet).
Real register send is Inc-D (scripts/register_controller_ioid.py). See
docs/ioid-controller-ceremony-scope-2026-07-17.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "bridge" / ".env")
load_dotenv(ROOT / "contracts" / ".env")

from vapi_bridge.controller_ceremony import (
    PROJECT_REGISTRY_ADDR, IOID_STORE_ADDR,
    PROJECT_REGISTRY_ABI, IOID_STORE_ABI, IPROJECT_ABI,
    CONTROLLER_NFT_ABI, CONTROLLER_PROJECT_NAME, CONTROLLER_PROJECT_TYPE,
    BRIDGE_WALLET,
    assert_nft_deployed, assert_project_token_id, assert_gamer_address,
    assert_mint_authorized, is_bridge_caller, hard_cap_ok,
    minted_token_id_from_logs, CeremonyError,
)

CONFIRM_ENV = "IOID_CONTROLLER_CEREMONY_CONFIRM"
GAS_BUFFER = 1.25          # IoTeX recoverable-gas convention (provision_device_mfg.py)
CHAIN_ID = 4690            # IoTeX testnet
DEPLOYED_ADDRESSES = ROOT / "contracts" / "deployed-addresses.json"

# Per-step hard caps (IOTX). These are simple calls (not upgradeable deploys), so
# the IoTeX ~3-4x under-estimate that bit the NFT deploy does not apply; caps stay
# tight. applyIoIDs adds its msg.value on top of gas.
HARD_CAP = {
    "register-project": 0.75,
    "set-device-contract": 0.50,
    "apply-ioids": 1.00,
    "mint": 0.50,
}


# --- shared chain helpers -----------------------------------------------------

def _connect():
    from web3 import Web3
    from eth_account import Account
    rpc_url = os.getenv("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
    pk = os.getenv("BRIDGE_PRIVATE_KEY", "")
    if not pk:
        print("ERROR: BRIDGE_PRIVATE_KEY not set in env (bridge/.env)", file=sys.stderr)
        sys.exit(2)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = Account.from_key(pk)
    if not is_bridge_caller(account.address):
        print(f"[GATE] caller {account.address} != bridge wallet {BRIDGE_WALLET} - ABORT.",
              file=sys.stderr)
        sys.exit(2)
    print(f"  rpc            : {rpc_url}")
    print(f"  caller         : {account.address}")
    print(f"  balance        : {w3.from_wei(w3.eth.get_balance(account.address), 'ether')} IOTX")
    return w3, account


def _load_deployed() -> dict:
    # encoding="utf-8" is REQUIRED: deployed-addresses.json holds UTF-8 (smart quotes/em-dashes
    # in wiring notes) and the default read_text() uses the OS locale (cp1252 on Windows) -> a
    # UnicodeDecodeError on byte 0x9d. read_text() must never rely on the platform default here.
    return json.loads(DEPLOYED_ADDRESSES.read_text(encoding="utf-8"))


def _submit(w3, account, fn, *, value_wei: int, cap: float, execute: bool,
            gas_limit_override, label: str):
    """Estimate-first -> hard-cap -> (estimate-only STOP | confirm-gate broadcast).
    Returns the receipt on broadcast, or None on estimate-only. Exits nonzero on
    cap breach, missing confirm, or a reverted tx."""
    # estimate_gas doubles as the pre-send revert guard.
    est_gas = fn.estimate_gas({"from": account.address, "value": value_wei})
    gas_price = w3.eth.gas_price
    buffered_gas = int(gas_limit_override) if gas_limit_override else (est_gas * int(GAS_BUFFER * 100)) // 100
    buf_cost_wei = buffered_gas * gas_price + value_wei
    buf_cost_iotx = float(w3.from_wei(buf_cost_wei, "ether"))
    print(f"\n--- {label}: GAS ESTIMATE ---")
    print(f"  estimate_gas   : {est_gas}   buffered: {buffered_gas}"
          + ("  (override)" if gas_limit_override else f"  (x{GAS_BUFFER})"))
    print(f"  gasPrice (wei) : {gas_price}")
    if value_wei:
        print(f"  value          : {w3.from_wei(value_wei, 'ether')} IOTX")
    print(f"  buffered cost  : {buf_cost_iotx} IOTX   (cap {cap})")
    if not hard_cap_ok(buf_cost_iotx, cap):
        print(f"[HARD-CAP EXCEEDED] {buf_cost_iotx} > {cap} - ABORT.", file=sys.stderr)
        sys.exit(2)
    print("  hard-cap check : PASS")

    if not execute:
        print(f"\n[ESTIMATE-ONLY] --execute not set. NOT broadcasting {label}.")
        print(f"Re-run with --execute {CONFIRM_ENV}=1 to broadcast.")
        return None
    if os.getenv(CONFIRM_ENV, "") != "1":
        print(f"\nERROR: --execute requires {CONFIRM_ENV}=1 env var.", file=sys.stderr)
        sys.exit(2)

    print(f"\n[BROADCASTING] {label} - sending tx...")
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction({
        "from": account.address, "nonce": nonce, "gas": buffered_gas,
        "gasPrice": gas_price, "chainId": CHAIN_ID, "value": value_wei,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  tx hash        : 0x{tx_hash.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    print(f"  block          : {rcpt.blockNumber}   gasUsed: {rcpt.gasUsed}   status: {rcpt.status}")
    if rcpt.status != 1:
        print(f"[FAILED] status {rcpt.status} - tx reverted. "
              f"https://testnet.iotexscan.io/tx/0x{tx_hash.hex()}", file=sys.stderr)
        sys.exit(1)
    return rcpt


def _tx_url(rcpt) -> str:
    h = rcpt.transactionHash.hex() if hasattr(rcpt.transactionHash, "hex") else str(rcpt.transactionHash)
    return "https://testnet.iotexscan.io/tx/0x" + h.removeprefix("0x")


# --- subcommands --------------------------------------------------------------

def cmd_register_project(args):
    w3, account = _connect()
    reg = w3.eth.contract(address=w3.to_checksum_address(PROJECT_REGISTRY_ADDR),
                          abi=PROJECT_REGISTRY_ABI)
    print(f"  project name   : {CONTROLLER_PROJECT_NAME!r}  type={CONTROLLER_PROJECT_TYPE}")
    fn = reg.functions.register(CONTROLLER_PROJECT_NAME, CONTROLLER_PROJECT_TYPE)
    rcpt = _submit(w3, account, fn, value_wei=0, cap=HARD_CAP["register-project"],
                   execute=args.execute, gas_limit_override=args.gas_limit,
                   label="register-project")
    if rcpt is None:
        return
    # Readback: the IProject NFT address, then the tokenId from its Transfer log
    # (robust pure parse), with the enumerable IProject as a labelled fallback.
    iproject_addr = reg.functions.project().call()
    token_id = minted_token_id_from_logs(rcpt.logs, iproject_addr, account.address)
    print(f"\n  IProject NFT   : {iproject_addr}")
    if token_id is None:
        iproj = w3.eth.contract(address=w3.to_checksum_address(iproject_addr), abi=IPROJECT_ABI)
        bal = iproj.functions.balanceOf(account.address).call()
        if bal > 0:
            token_id = iproj.functions.tokenOfOwnerByIndex(account.address, bal - 1).call()
            print("  (Transfer-log parse empty; enumeration fallback - verify on explorer if multi-project)")
    if token_id is None:
        print(f"ERROR: could not determine PROJECT_TOKEN_ID - read it from the receipt: {_tx_url(rcpt)}",
              file=sys.stderr)
        sys.exit(1)
    print(f"  PROJECT_TOKEN_ID={token_id}")
    print(f"\n  Next: set-device-contract --project-token-id {token_id}")


def cmd_set_device_contract(args):
    project_token_id = assert_project_token_id(args.project_token_id)
    deployed = _load_deployed()
    nft = assert_nft_deployed(deployed)   # fail-honest if Inc-A unfired
    w3, account = _connect()
    store = w3.eth.contract(address=w3.to_checksum_address(IOID_STORE_ADDR), abi=IOID_STORE_ABI)
    # preflight: is this NFT already mapped?
    existing = store.functions.deviceContractProject(w3.to_checksum_address(nft)).call()
    print(f"  NFT            : {nft}")
    print(f"  projectTokenId : {project_token_id}")
    print(f"  existing map   : deviceContractProject(NFT) = {existing}")
    if existing == project_token_id:
        print("  [ALREADY MAPPED] deviceContractProject already == projectTokenId - nothing to do.")
        return
    if existing != 0:
        print(f"ERROR: NFT already mapped to a DIFFERENT project ({existing}) - refusing to remap.",
              file=sys.stderr)
        sys.exit(2)
    fn = store.functions.setDeviceContract(project_token_id, w3.to_checksum_address(nft))
    rcpt = _submit(w3, account, fn, value_wei=0, cap=HARD_CAP["set-device-contract"],
                   execute=args.execute, gas_limit_override=args.gas_limit,
                   label="set-device-contract")
    if rcpt is None:
        return
    after = store.functions.deviceContractProject(w3.to_checksum_address(nft)).call()
    print(f"\n  readback       : deviceContractProject(NFT) = {after}")
    if after != project_token_id:
        print(f"ERROR: mapping readback {after} != {project_token_id} - inspect the tx.", file=sys.stderr)
        sys.exit(1)
    print("  [MAPPED] setDeviceContract confirmed. Next: mint --to <gamer>")


def cmd_apply_ioids(args):
    project_token_id = assert_project_token_id(args.project_token_id)
    amount = int(args.amount)
    if amount < 1:
        print("ERROR: --amount must be >= 1", file=sys.stderr)
        sys.exit(2)
    w3, account = _connect()
    store = w3.eth.contract(address=w3.to_checksum_address(IOID_STORE_ADDR), abi=IOID_STORE_ABI)
    price = store.functions.price().call()
    value_wei = price * amount
    print(f"  projectTokenId : {project_token_id}   amount={amount}")
    print(f"  ioIDStore.price: {w3.from_wei(price, 'ether')} IOTX/device -> value {w3.from_wei(value_wei, 'ether')} IOTX")
    print("  (OPTIONAL pre-pay; the register step can pay-as-you-go value=price instead)")
    fn = store.functions.applyIoIDs(project_token_id, amount)
    _submit(w3, account, fn, value_wei=value_wei, cap=HARD_CAP["apply-ioids"],
            execute=args.execute, gas_limit_override=args.gas_limit, label="apply-ioids")


def cmd_mint(args):
    gamer = assert_gamer_address(args.to)
    deployed = _load_deployed()
    nft = assert_nft_deployed(deployed)
    w3, account = _connect()
    gamer = w3.to_checksum_address(gamer)
    nft_c = w3.eth.contract(address=w3.to_checksum_address(nft), abi=CONTROLLER_NFT_ABI)
    # preflight: bridge must be a configured minter with allowance
    assert_mint_authorized(
        is_minter=nft_c.functions.isMinter(account.address).call(),
        minter_allowance=nft_c.functions.minterAllowance(account.address).call(),
    )
    bal_before = nft_c.functions.balanceOf(gamer).call()
    print(f"  NFT            : {nft}")
    print(f"  mint -> gamer  : {gamer}")
    print(f"  balanceOf(before): {bal_before}")
    fn = nft_c.functions.mint(gamer)
    rcpt = _submit(w3, account, fn, value_wei=0, cap=HARD_CAP["mint"],
                   execute=args.execute, gas_limit_override=args.gas_limit, label="mint")
    if rcpt is None:
        return
    token_id = minted_token_id_from_logs(rcpt.logs, nft, gamer)
    bal_after = nft_c.functions.balanceOf(gamer).call()
    total_after = nft_c.functions.total().call()
    print(f"\n  balanceOf(after) : {bal_after}  (delta {bal_after - bal_before})")
    if bal_after != bal_before + 1:
        print(f"ERROR: balance did not increment by 1 - inspect the tx: {_tx_url(rcpt)}", file=sys.stderr)
        sys.exit(1)
    # F1: never emit CONTROLLER_TOKEN_ID=None. Primary = the mint Transfer log;
    # deterministic fallback = total() (mint does `_tokenId = ++total`; balance
    # delta==1 was just asserted + bridge is the sole minter, so total() IS the
    # just-minted id and is always a positive int - no None can reach the operator).
    if token_id is None:
        token_id = total_after
        print("  (Transfer-log parse empty; using total() counter as the tokenId)")
    elif token_id != total_after:
        print(f"  WARN: parsed tokenId {token_id} != total() {total_after} - inspect {_tx_url(rcpt)}")
    print(f"  CONTROLLER_TOKEN_ID={token_id}")
    print(f"\n  Next (Inc-D): scripts/register_controller_ioid.py - real register send "
          f"consumes CONTROLLER_TOKEN_ID={token_id} + device_contract={nft}.")


def main():
    ap = argparse.ArgumentParser(description="ioID controller ceremony prereq txs (Inc-C, "
                                             "one step per invoke, estimate-first + triple-gated).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("register-project", help="ProjectRegistry.register(name, 0)")
    p.set_defaults(func=cmd_register_project)

    p = sub.add_parser("set-device-contract", help="ioIDStore.setDeviceContract(projectTokenId, NFT)")
    p.add_argument("--project-token-id", required=True, help="from register-project's PROJECT_TOKEN_ID")
    p.set_defaults(func=cmd_set_device_contract)

    p = sub.add_parser("apply-ioids", help="[optional] ioIDStore.applyIoIDs(projectTokenId, N) pre-pay")
    p.add_argument("--project-token-id", required=True)
    p.add_argument("--amount", default="1", help="number of ioIDs to pre-pay (default 1)")
    p.set_defaults(func=cmd_apply_ioids)

    p = sub.add_parser("mint", help="VAPIGamerControllerNFT.mint(gamer)")
    p.add_argument("--to", required=True, help="gamer address (dev-self = the bridge wallet)")
    p.set_defaults(func=cmd_mint)

    for sp in (sub.choices.values()):
        sp.add_argument("--execute", action="store_true",
                        help=f"broadcast (also requires {CONFIRM_ENV}=1). Default = estimate-only.")
        sp.add_argument("--gas-limit", default=None,
                        help="explicit gasLimit override (use if a step OOGs at status 0x65 on IoTeX).")

    args = ap.parse_args()
    try:
        args.func(args)
    except CeremonyError as exc:
        print(f"\nERROR (ceremony guard): {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
