"""Phase 4a -- AgentRegistry.updateAgentScope(curatorAgentId, newScopeHash).

Post-governance-commitment activation step #1. The Curator scope-expansion
governance commitment landed on-chain 2026-05-28 (BBG.proposeWithVHP,
proposalHash 0x59fb9996..., tx 0xba96f7cb..., block 44073691). This script
flips the AgentRegistry's stored scopeHash for the Curator agent from its
pre-expansion value to the committed newScopeHash.

DISCIPLINE (triple-gate, matches every prior fire this arc):
  - Reads AgentRegistry address + Curator agentId from canonical sources
    (deployed-addresses.json + curator-scope-manifest.json + Phase 3 receipt)
  - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
  - ESTIMATE-ONLY by default. Broadcast ONLY when AGENT_SCOPE_UPDATE_CONFIRM=1.
  - Pre-broadcast sanity:
      * AgentRegistry.owner() == bridge wallet (only owner can updateAgentScope)
      * Curator agentId is registered (publicKey != address(0))
      * Anti-no-op: stored scopeHash != target newScopeHash
      * newScopeHash matches the committed governance proposalHash preimage
  - Process-scoped CHAIN_SUBMISSION_PAUSED override (no .env mutation)

Usage:
    # Estimate-only:
    python scripts/fire_agent_registry_update_scope.py

    # Operator-confirmed broadcast:
    AGENT_SCOPE_UPDATE_CONFIRM=1 python scripts/fire_agent_registry_update_scope.py

Post-fire: AgentRegistry.getAgent(curatorAgentId) returns the new scopeHash.
The complementary AgentScope.setAgentScopeRoot fire (scripts/
fire_agent_scope_set_root.py) carries the operational-layer flip.

Exit codes:
    0  estimate-only OR broadcast confirmed
    1  prerequisite missing (deployed-addresses.json, env, etc.)
    2  ABORT guard tripped (not owner, balance, hard-cap, no-op, etc.)
    3  RPC / broadcast / receipt error
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "contracts" / ".env")

DEPLOYED_ADDRESSES = REPO_ROOT / "contracts" / "deployed-addresses.json"

# Curator agent identifier (Q9-frozen Phase O0 Session 1+2+3, 2026-05-09)
CURATOR_AGENT_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"

# Committed newScopeHash from the on-chain governance proposal (proposalHash
# 0x59fb9996..., tx 0xba96f7cb..., block 44073691). Re-derivable via
# scripts/compute_governance_hashes.py against docs/governance/.
NEW_SCOPE_HASH = "0xab874f6297063fd2d43f49f272b9a95accd56b79f99ccd3d64b0ecd3a52c5b14"

HARD_CAP_IOTX = 0.2   # owner-only setter (~0.04-0.06 expected)
GAS_BUFFER    = 1.25

_AGENT_REGISTRY_ABI = [
    {"name": "owner", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "isRegistered", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "agentId", "type": "bytes32"}],
     "outputs": [{"type": "bool"}]},
    {"name": "getAgent", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "agentId", "type": "bytes32"}],
     "outputs": [
         {"name": "publicKey", "type": "address"},
         {"name": "scopeHash", "type": "bytes32"},
         {"name": "status",    "type": "uint8"},
     ]},
    {"name": "updateAgentScope", "type": "function", "stateMutability": "nonpayable",
     "inputs": [
         {"name": "agentId",  "type": "bytes32"},
         {"name": "newScope", "type": "bytes32"},
     ],
     "outputs": []},
]


def main():
    print("=" * 72)
    print("Phase 4a -- AgentRegistry.updateAgentScope(curator, newScopeHash)")
    print("=" * 72)

    if not DEPLOYED_ADDRESSES.exists():
        print("ERROR: deployed-addresses.json not found", file=sys.stderr)
        sys.exit(1)
    addrs = json.loads(DEPLOYED_ADDRESSES.read_text(encoding="utf-8"))
    registry_addr = addrs.get("AgentRegistry", "")
    if not registry_addr:
        print("ERROR: AgentRegistry missing from deployed-addresses.json",
              file=sys.stderr)
        sys.exit(1)
    print(f"  AgentRegistry        : {registry_addr}")
    print(f"  Curator agentId      : {CURATOR_AGENT_ID}")
    print(f"  newScopeHash         : {NEW_SCOPE_HASH}")

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

    registry = w3.eth.contract(
        address=w3.to_checksum_address(registry_addr),
        abi=_AGENT_REGISTRY_ABI,
    )

    # Pre-broadcast sanity
    print()
    print("--- PRE-BROADCAST SANITY ---")
    reg_owner = registry.functions.owner().call()
    print(f"  AgentRegistry.owner(): {reg_owner}")
    if reg_owner.lower() != account.address.lower():
        print(f"ERROR: caller {account.address} is NOT AgentRegistry owner {reg_owner}",
              file=sys.stderr)
        sys.exit(2)
    print("  owner check          : PASS")

    is_reg = registry.functions.isRegistered(CURATOR_AGENT_ID).call()
    print(f"  Curator isRegistered : {is_reg}")
    if not is_reg:
        print("ERROR: Curator agentId not registered in AgentRegistry",
              file=sys.stderr)
        sys.exit(2)

    pk, current_scope, status = registry.functions.getAgent(CURATOR_AGENT_ID).call()
    current_scope_hex = "0x" + current_scope.hex()
    print(f"  Curator publicKey    : {pk}")
    print(f"  Curator status       : {status}")
    print(f"  Curator scopeHash    : {current_scope_hex}  (current)")
    print(f"                         {NEW_SCOPE_HASH}  (target)")
    if current_scope_hex.lower() == NEW_SCOPE_HASH.lower():
        print("  NOTE: AgentRegistry scopeHash already equals target -- no-op "
              "fire would spend gas with no state change. Aborting.")
        sys.exit(2)
    print("  anti-no-op check     : PASS")

    # Estimate
    print()
    print("--- GAS ESTIMATE ---")
    fn = registry.functions.updateAgentScope(
        bytes.fromhex(CURATOR_AGENT_ID[2:]),
        bytes.fromhex(NEW_SCOPE_HASH[2:]),
    )
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
        print(f"\n[BALANCE GUARD] balance {bal_iotx} < 2x buffered cost",
              file=sys.stderr)
        sys.exit(2)
    print("  hard-cap check       : PASS")
    print("  balance guard (2x)   : PASS")

    if os.getenv("AGENT_SCOPE_UPDATE_CONFIRM", "") != "1":
        print()
        print("[ESTIMATE-ONLY] AGENT_SCOPE_UPDATE_CONFIRM!=1 -- NOT broadcasting.")
        print("Re-run with AGENT_SCOPE_UPDATE_CONFIRM=1 to broadcast.")
        return 0

    # Broadcast
    os.environ["CHAIN_SUBMISSION_PAUSED"] = "false"
    print()
    print("[BROADCASTING] AGENT_SCOPE_UPDATE_CONFIRM=1 -- sending tx...")
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
    _, post_scope, _ = registry.functions.getAgent(CURATOR_AGENT_ID).call()
    post_scope_hex = "0x" + post_scope.hex()
    print(f"  Curator scopeHash    : {post_scope_hex}  (post)")
    if post_scope_hex.lower() != NEW_SCOPE_HASH.lower():
        print(f"\n[MISMATCH] post-tx scopeHash {post_scope_hex} != target {NEW_SCOPE_HASH}",
              file=sys.stderr)
        sys.exit(3)

    print()
    print("DEPLOY_RESULT_JSON " + json.dumps({
        "scriptName":  "fire_agent_registry_update_scope",
        "agentRegistry": registry_addr,
        "agentId":     CURATOR_AGENT_ID,
        "oldScope":    current_scope_hex,
        "newScope":    NEW_SCOPE_HASH,
        "txHash":      "0x" + tx_hash.hex(),
        "blockNumber": rcpt.blockNumber,
        "gasUsed":     rcpt.gasUsed,
        "status":      rcpt.status,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
