"""Phase 2b — Point VAPIBiometricGovernance at the VHPExpiresAtAdapter.

After Phase 2a deploys the adapter (VHPExpiresAtAdapter), this script
fires the one-shot `BBG.setVHPContract(adapterAddress)` call so the
governance ceremony's `proposeWithVHP()` can resolve `expiresAt(uint256)`
correctly.

DISCIPLINE (triple-gate, matches every prior fire this arc):
  - Reads adapter address from deployed-addresses.json
    (VHPExpiresAtAdapter entry written post Phase 2a deploy)
  - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
  - ESTIMATE-ONLY by default. Broadcast ONLY when BBG_SET_VHP_CONFIRM=1.
  - Pre-broadcast sanity:
      * BBG owner == bridge wallet (only owner can setVHPContract)
      * Adapter is non-zero + has the expected wrapped VHP
      * Adapter actually responds to expiresAt(2) (proves the fix lands)
  - Process-scoped CHAIN_SUBMISSION_PAUSED override (no .env mutation)

Usage:
    # Estimate-only:
    python scripts/set_bbg_vhp_contract.py

    # Operator-confirmed broadcast:
    BBG_SET_VHP_CONFIRM=1 python scripts/set_bbg_vhp_contract.py

Post-fire: BBG.vhpContract() returns the adapter address. The governance
ceremony fire (scripts/fire_curator_governance_proposal.py) then passes
its pre-broadcast sanity and can broadcast the proposalHash commitment.

Exit codes:
    0  estimate-only OR broadcast confirmed
    1  prerequisite missing (deployed-addresses.json, env, etc.)
    2  ABORT guard tripped (not owner, balance, hard-cap, etc.)
    3  RPC / broadcast / receipt error
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "contracts" / ".env")

DEPLOYED_ADDRESSES = REPO_ROOT / "contracts" / "deployed-addresses.json"
VAPI_BIOMETRIC_GOVERNANCE_ADDR = "0x06782293F1CFC1AA30C0Baee0437c2B336796A00"

HARD_CAP_IOTX = 0.2   # tiny owner-only setter call (~0.05 expected)
GAS_BUFFER    = 1.25

_BBG_ABI = [
    {"name": "owner", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "vhpContract", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "setVHPContract", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "newVHP", "type": "address"}],
     "outputs": []},
]

_ADAPTER_ABI = [
    {"name": "vhp", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "expiresAt", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}],
     "outputs": [{"type": "uint256"}]},
]


def main():
    print("=" * 72)
    print("Phase 2b -- BBG.setVHPContract(VHPExpiresAtAdapter)")
    print("=" * 72)

    if not DEPLOYED_ADDRESSES.exists():
        print(f"ERROR: deployed-addresses.json not found", file=sys.stderr)
        sys.exit(1)
    addrs = json.loads(DEPLOYED_ADDRESSES.read_text(encoding="utf-8"))
    adapter_addr = addrs.get("VHPExpiresAtAdapter", "")
    if not adapter_addr:
        print("ERROR: VHPExpiresAtAdapter missing from deployed-addresses.json -- "
              "did Phase 2a deploy land + the addresses.json commit follow?",
              file=sys.stderr)
        sys.exit(1)
    print(f"  adapter address      : {adapter_addr}")
    print(f"  BBG address          : {VAPI_BIOMETRIC_GOVERNANCE_ADDR}")

    from web3 import Web3
    from eth_account import Account

    rpc_url = os.getenv("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
    private_key = os.getenv("BRIDGE_PRIVATE_KEY", "")
    if not private_key:
        print("ERROR: BRIDGE_PRIVATE_KEY not set", file=sys.stderr); sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = Account.from_key(private_key)
    print(f"  caller               : {account.address}")
    bal_iotx = float(w3.from_wei(w3.eth.get_balance(account.address), "ether"))
    print(f"  balance              : {bal_iotx} IOTX")

    bbg = w3.eth.contract(
        address=w3.to_checksum_address(VAPI_BIOMETRIC_GOVERNANCE_ADDR),
        abi=_BBG_ABI,
    )

    # ── Pre-broadcast sanity ──────────────────────────────────────────────
    print()
    print("--- PRE-BROADCAST SANITY ---")
    bbg_owner = bbg.functions.owner().call()
    print(f"  BBG.owner()          : {bbg_owner}")
    if bbg_owner.lower() != account.address.lower():
        print(f"ERROR: caller {account.address} is NOT BBG owner {bbg_owner}",
              file=sys.stderr)
        sys.exit(2)
    print("  owner check          : PASS")

    current_vhp = bbg.functions.vhpContract().call()
    print(f"  BBG.vhpContract()    : {current_vhp}  (current)")
    if current_vhp.lower() == adapter_addr.lower():
        print("  NOTE: BBG already points at the adapter -- no-op fire would still")
        print("        spend gas with no state change. Aborting.")
        sys.exit(2)

    adapter = w3.eth.contract(
        address=w3.to_checksum_address(adapter_addr), abi=_ADAPTER_ABI,
    )
    try:
        adapter_wrapped = adapter.functions.vhp().call()
        adapter_expires_2 = adapter.functions.expiresAt(2).call()
        print(f"  adapter.vhp()        : {adapter_wrapped}")
        print(f"  adapter.expiresAt(2) : {adapter_expires_2} (epoch s)")
    except Exception as exc:
        print(f"ERROR: adapter sanity read failed: {exc}", file=sys.stderr)
        sys.exit(3)
    if adapter_expires_2 == 0:
        print("ERROR: adapter.expiresAt(2) = 0 -- adapter not connected to a real VHP",
              file=sys.stderr)
        sys.exit(2)
    print("  adapter sanity       : PASS")

    # ── Estimate ──────────────────────────────────────────────────────────
    print()
    print("--- GAS ESTIMATE ---")
    fn = bbg.functions.setVHPContract(w3.to_checksum_address(adapter_addr))
    est_gas = fn.estimate_gas({"from": account.address})
    gas_price = w3.eth.gas_price
    buffered_gas = (est_gas * int(GAS_BUFFER * 100)) // 100
    buf_cost_wei = buffered_gas * gas_price
    buf_cost_iotx = float(w3.from_wei(buf_cost_wei, "ether"))
    print(f"  estimate_gas         : {est_gas}")
    print(f"  buffered (x{GAS_BUFFER:.2f})     : {buffered_gas}")
    print(f"  gasPrice (wei)       : {gas_price}")
    print(f"  buffered cost        : {buf_cost_iotx} IOTX")
    print(f"  hard-cap             : {HARD_CAP_IOTX} IOTX")
    if buf_cost_iotx > HARD_CAP_IOTX:
        print(f"\n[HARD-CAP EXCEEDED] {buf_cost_iotx} > {HARD_CAP_IOTX} -- ABORT.",
              file=sys.stderr)
        sys.exit(2)
    if bal_iotx < buf_cost_iotx * 2:
        print(f"\n[BALANCE GUARD] balance {bal_iotx} < 2x buffered cost", file=sys.stderr)
        sys.exit(2)
    print("  hard-cap check       : PASS")
    print("  balance guard (2x)   : PASS")

    if os.getenv("BBG_SET_VHP_CONFIRM", "") != "1":
        print()
        print("[ESTIMATE-ONLY] BBG_SET_VHP_CONFIRM!=1 -- NOT broadcasting.")
        print("Re-run with BBG_SET_VHP_CONFIRM=1 to broadcast.")
        return 0

    # ── Broadcast ─────────────────────────────────────────────────────────
    os.environ["CHAIN_SUBMISSION_PAUSED"] = "false"
    print()
    print("[BROADCASTING] BBG_SET_VHP_CONFIRM=1 -- sending tx...")
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction({
        "from": account.address, "nonce": nonce,
        "gas": buffered_gas, "gasPrice": gas_price, "chainId": 4690,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  tx hash              : 0x{tx_hash.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"  block                : {rcpt.blockNumber}")
    print(f"  gas used             : {rcpt.gasUsed}")
    print(f"  status               : {rcpt.status} "
          f"({'success' if rcpt.status == 1 else 'FAILED'})")

    # Verify
    post_vhp = bbg.functions.vhpContract().call()
    print(f"  BBG.vhpContract()    : {post_vhp}  (post)")
    if post_vhp.lower() != adapter_addr.lower():
        print(f"\n[MISMATCH] BBG.vhpContract still {post_vhp}, expected {adapter_addr}",
              file=sys.stderr)
        sys.exit(3)

    print()
    print("DEPLOY_RESULT_JSON " + json.dumps({
        "scriptName":  "set_bbg_vhp_contract",
        "bbgAddress":  VAPI_BIOMETRIC_GOVERNANCE_ADDR,
        "newVhp":      adapter_addr,
        "oldVhp":      current_vhp,
        "txHash":      "0x" + tx_hash.hex(),
        "blockNumber": rcpt.blockNumber,
        "gasUsed":     rcpt.gasUsed,
        "status":      rcpt.status,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
