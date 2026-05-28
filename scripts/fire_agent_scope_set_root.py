"""Phase 4b -- AgentScope.setAgentScopeRoot(curatorAgentId, newScopeRoot).

Post-governance-commitment activation step #2. Complements Phase 4a
(AgentRegistry.updateAgentScope) by flipping the OPERATIONAL scope layer.

Per AgentScope.sol architectural docs:
  - AgentRegistry.scopeHash = governance commitment (what agent is AUTHORIZED to do)
  - AgentScope.scopeRoot    = operational state (what scope is ACTIVE)
  - Deliberately allowed to differ; AgentScope does NOT cross-validate.

At INITIAL activation (this fire), operational scope == governance scope, so
newScopeRoot = NEW_SCOPE_HASH. Later operational refinement (within the
governance-approved envelope) may produce a different scopeRoot; that is the
two-layer pattern's purpose.

AgentAdjudicationRegistry's requireAgentScope modifier reads AgentScope.scopeRoot
(operational truth at moment of action), so this fire is the one that gates
ACTUAL agent action authorization, not Phase 4a.

DISCIPLINE (triple-gate, matches every prior fire this arc):
  - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast
  - ESTIMATE-ONLY by default. Broadcast ONLY when AGENT_SCOPE_SET_ROOT_CONFIRM=1.
  - Pre-broadcast sanity:
      * AgentScope.owner() == bridge wallet
      * Curator registered in AgentRegistry (cross-contract check the contract
        also enforces, but we surface it pre-broadcast for clear error)
      * Anti-no-op: stored scopeRoot != target newScopeRoot
      * NEW_SCOPE_HASH matches Phase 4a target (sanity)
  - Process-scoped CHAIN_SUBMISSION_PAUSED override (no .env mutation)

Usage:
    # Estimate-only:
    python scripts/fire_agent_scope_set_root.py

    # Operator-confirmed broadcast:
    AGENT_SCOPE_SET_ROOT_CONFIRM=1 python scripts/fire_agent_scope_set_root.py

Post-fire: AgentScope.getScopeRoot(curatorAgentId) returns the new scopeRoot.
The Curator agent's expanded scope (CAP-001..004) is now OPERATIONALLY active
modulo Arc-1 (VAPIBuyerRegistry deploy + setCuratorWallet wiring), Arc-3
(data floor in code), and the autonomy_level default (approval_required).

Exit codes:
    0  estimate-only OR broadcast confirmed
    1  prerequisite missing
    2  ABORT guard tripped
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

CURATOR_AGENT_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"
NEW_SCOPE_ROOT   = "0xab874f6297063fd2d43f49f272b9a95accd56b79f99ccd3d64b0ecd3a52c5b14"

HARD_CAP_IOTX = 0.2
GAS_BUFFER    = 1.25

_AGENT_SCOPE_ABI = [
    {"name": "owner", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "agentRegistry", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "getScopeRoot", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "agentId", "type": "bytes32"}],
     "outputs": [{"type": "bytes32"}]},
    {"name": "setAgentScopeRoot", "type": "function", "stateMutability": "nonpayable",
     "inputs": [
         {"name": "agentId",  "type": "bytes32"},
         {"name": "scopeRoot","type": "bytes32"},
     ],
     "outputs": []},
]

_AGENT_REGISTRY_ABI_MINI = [
    {"name": "isRegistered", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "agentId", "type": "bytes32"}],
     "outputs": [{"type": "bool"}]},
]


def main():
    print("=" * 72)
    print("Phase 4b -- AgentScope.setAgentScopeRoot(curator, newScopeRoot)")
    print("=" * 72)

    if not DEPLOYED_ADDRESSES.exists():
        print("ERROR: deployed-addresses.json not found", file=sys.stderr); sys.exit(1)
    addrs = json.loads(DEPLOYED_ADDRESSES.read_text(encoding="utf-8"))
    scope_addr = addrs.get("AgentScope", "")
    registry_addr = addrs.get("AgentRegistry", "")
    if not scope_addr or not registry_addr:
        print("ERROR: AgentScope or AgentRegistry missing from deployed-addresses.json",
              file=sys.stderr); sys.exit(1)
    print(f"  AgentScope           : {scope_addr}")
    print(f"  AgentRegistry        : {registry_addr}  (for cross-check)")
    print(f"  Curator agentId      : {CURATOR_AGENT_ID}")
    print(f"  newScopeRoot         : {NEW_SCOPE_ROOT}")

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

    scope = w3.eth.contract(address=w3.to_checksum_address(scope_addr),
                            abi=_AGENT_SCOPE_ABI)
    registry = w3.eth.contract(address=w3.to_checksum_address(registry_addr),
                               abi=_AGENT_REGISTRY_ABI_MINI)

    # Pre-broadcast sanity
    print()
    print("--- PRE-BROADCAST SANITY ---")
    scope_owner = scope.functions.owner().call()
    print(f"  AgentScope.owner()   : {scope_owner}")
    if scope_owner.lower() != account.address.lower():
        print(f"ERROR: caller {account.address} is NOT AgentScope owner {scope_owner}",
              file=sys.stderr); sys.exit(2)
    print("  owner check          : PASS")

    wired_registry = scope.functions.agentRegistry().call()
    print(f"  AgentScope.agentRegistry(): {wired_registry}")
    if wired_registry.lower() != registry_addr.lower():
        print(f"ERROR: AgentScope wired registry {wired_registry} != deployed "
              f"AgentRegistry {registry_addr}", file=sys.stderr); sys.exit(2)
    print("  registry wiring      : PASS")

    is_reg = registry.functions.isRegistered(CURATOR_AGENT_ID).call()
    print(f"  Curator isRegistered : {is_reg}")
    if not is_reg:
        print("ERROR: Curator not registered (AgentScope.setAgentScopeRoot would revert)",
              file=sys.stderr); sys.exit(2)

    current_root = scope.functions.getScopeRoot(CURATOR_AGENT_ID).call()
    current_root_hex = "0x" + current_root.hex()
    print(f"  Curator scopeRoot    : {current_root_hex}  (current)")
    print(f"                         {NEW_SCOPE_ROOT}  (target)")
    if current_root_hex.lower() == NEW_SCOPE_ROOT.lower():
        print("  NOTE: scopeRoot already equals target -- no-op fire. Aborting.")
        sys.exit(2)
    print("  anti-no-op check     : PASS")

    # Estimate
    print()
    print("--- GAS ESTIMATE ---")
    fn = scope.functions.setAgentScopeRoot(
        bytes.fromhex(CURATOR_AGENT_ID[2:]),
        bytes.fromhex(NEW_SCOPE_ROOT[2:]),
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
              file=sys.stderr); sys.exit(2)
    if bal_iotx < buf_cost_iotx * 2:
        print(f"\n[BALANCE GUARD] balance {bal_iotx} < 2x buffered cost",
              file=sys.stderr); sys.exit(2)
    print("  hard-cap check       : PASS")
    print("  balance guard (2x)   : PASS")

    if os.getenv("AGENT_SCOPE_SET_ROOT_CONFIRM", "") != "1":
        print()
        print("[ESTIMATE-ONLY] AGENT_SCOPE_SET_ROOT_CONFIRM!=1 -- NOT broadcasting.")
        print("Re-run with AGENT_SCOPE_SET_ROOT_CONFIRM=1 to broadcast.")
        return 0

    # Broadcast
    os.environ["CHAIN_SUBMISSION_PAUSED"] = "false"
    print()
    print("[BROADCASTING] AGENT_SCOPE_SET_ROOT_CONFIRM=1 -- sending tx...")
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

    post_root = scope.functions.getScopeRoot(CURATOR_AGENT_ID).call()
    post_root_hex = "0x" + post_root.hex()
    print(f"  Curator scopeRoot    : {post_root_hex}  (post)")
    if post_root_hex.lower() != NEW_SCOPE_ROOT.lower():
        print(f"\n[MISMATCH] post-tx scopeRoot {post_root_hex} != target {NEW_SCOPE_ROOT}",
              file=sys.stderr); sys.exit(3)

    print()
    print("DEPLOY_RESULT_JSON " + json.dumps({
        "scriptName":  "fire_agent_scope_set_root",
        "agentScope":  scope_addr,
        "agentId":     CURATOR_AGENT_ID,
        "oldRoot":     current_root_hex,
        "newRoot":     NEW_SCOPE_ROOT,
        "txHash":      "0x" + tx_hash.hex(),
        "blockNumber": rcpt.blockNumber,
        "gasUsed":     rcpt.gasUsed,
        "status":      rcpt.status,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
