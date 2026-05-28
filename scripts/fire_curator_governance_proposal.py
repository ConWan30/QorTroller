"""One-shot operator-fired Curator scope-expansion governance proposal.

Submits the on-chain commitment via VAPIBiometricGovernance.proposeWithVHP()
per the deployed Phase 222 ABI (V-check 2026-05-28, Option A reconciliation).

DISCIPLINE (triple-gate, matches the Guardian Tier-2 anchor + VMDR deploy +
LensV2 deploy + provision_device_mfg.py --execute precedents):
  - Computes governance hashes from docs/governance/ via the canonical
    compute_governance_hashes.py logic (proposalHash = SHA-256 over a
    126-byte preimage: 30B domain tag + 32B agentId + 32B scopeHash +
    32B justificationHash).
  - estimate_gas + 1.25x buffer + hard-cap check BEFORE broadcast.
  - ESTIMATE-ONLY by default. Broadcast ONLY when
    CURATOR_GOVERNANCE_CONFIRM=1 env var is set.
  - Process-scoped CHAIN_SUBMISSION_PAUSED override (does NOT modify the
    .env file's kill-switch posture — matches the Guardian Tier-2
    process-scoped pattern that re-engages on bridge restart).
  - Pre-broadcast sanity checks:
      * Bridge wallet's Phase 99 VHP tokenId=2 isValid (anti-stale)
      * VAPIBiometricGovernance is not already at proposalHash (anti-replay)
      * Wallet balance + 2x safety margin against estimated cost

Usage:
    # Estimate-only (no spend, no broadcast):
    python scripts/fire_curator_governance_proposal.py

    # Operator-confirmed broadcast:
    CURATOR_GOVERNANCE_CONFIRM=1 python scripts/fire_curator_governance_proposal.py

Exit codes:
    0  success (estimate-only OR broadcast confirmed)
    1  prerequisite missing (governance hashes, env, VHP, etc.)
    2  ABORT guard tripped (insufficient balance, hard-cap exceeded,
       proposalHash already submitted, VHP invalid, etc.)
    3  RPC / broadcast / receipt error
"""
from __future__ import annotations

import hashlib
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

# ─── Constants (mirror compute_governance_hashes.py — single source of truth)─

MANIFEST_PATH      = REPO_ROOT / "docs" / "governance" / "curator-scope-manifest.json"
JUSTIFICATION_PATH = REPO_ROOT / "docs" / "governance" / "curator-governance-justification.md"

CURATOR_AGENT_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"
VHP_TOKEN_ID     = 2
_PROPOSAL_DOMAIN_TAG = b"VAPI-CURATOR-SCOPE-PROPOSAL-v1"

VAPI_BIOMETRIC_GOVERNANCE_ADDR = "0x06782293F1CFC1AA30C0Baee0437c2B336796A00"
# VHP_TOKEN_ADDR is now resolved DYNAMICALLY from BBG.vhpContract() so this
# script auto-adapts to whichever VHP-or-adapter contract BBG is currently
# pointed at. The 2026-05-28 governance-unblock arc pointed BBG at
# VHPExpiresAtAdapter (0x086a660fe457633063299F3BE9661B86c43aF053); reading
# vhpContract() at runtime means a future setVHPContract() flip needs no
# script edit. Sanity reads (ownerOf/isValid/expiresAt) hit the actual
# contract BBG will hit during proposeWithVHP -> same revert classes catch.

HARD_CAP_IOTX = 0.5   # governance proposal is a small state-write call
GAS_BUFFER    = 1.25  # estimate_gas x 1.25 (IoTeX gotcha discipline)

# Minimal ABIs (read-only surface for sanity checks + the one writer)
_BBG_ABI = [
    {"name": "proposeWithVHP", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "proposalHash", "type": "bytes32"},
                {"name": "vhpTokenId", "type": "uint256"}],
     "outputs": []},
    {"name": "isProposed", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "proposalHash", "type": "bytes32"}],
     "outputs": [{"type": "bool"}]},
    {"name": "totalProposals", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "bbgMaxAgeSec", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
]

_VHP_ABI = [
    {"name": "isValid", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}],
     "outputs": [{"type": "bool"}]},
    {"name": "expiresAt", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}],
     "outputs": [{"type": "uint256"}]},
    {"name": "ownerOf", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "tokenId", "type": "uint256"}],
     "outputs": [{"type": "address"}]},
]


def _canonical_json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _compute_hashes() -> dict:
    """Recompute governance hashes from disk. Single source of truth lives in
    compute_governance_hashes.py; this script replicates the algorithm so the
    fire is self-contained (operator can re-derive without trusting an import)."""
    if not MANIFEST_PATH.exists():
        print(f"ERROR: manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)
    if not JUSTIFICATION_PATH.exists():
        print(f"ERROR: justification not found: {JUSTIFICATION_PATH}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_canonical = _canonical_json_bytes(manifest)
    try:
        from eth_utils import keccak
    except ImportError:
        print("ERROR: eth_utils not installed", file=sys.stderr)
        sys.exit(1)
    scope_hash = keccak(manifest_canonical)

    justification_bytes = JUSTIFICATION_PATH.read_bytes()
    justification_hash  = _sha256(justification_bytes)

    agent_id_bytes = bytes.fromhex(CURATOR_AGENT_ID[2:])
    proposal_preimage = _PROPOSAL_DOMAIN_TAG + agent_id_bytes + scope_hash + justification_hash
    assert len(proposal_preimage) == 126, "preimage width drift"
    proposal_hash = _sha256(proposal_preimage)

    return {
        "scopeHash":         scope_hash,
        "justificationHash": justification_hash,
        "proposalHash":      proposal_hash,
        "manifestBytes":     len(manifest_canonical),
        "justBytes":         len(justification_bytes),
    }


def main():
    print("=" * 72)
    print("Curator Scope Expansion -- VAPIBiometricGovernance.proposeWithVHP()")
    print("Phase 222 ABI verified V-check 2026-05-28 (Option A reconciliation)")
    print("=" * 72)

    hashes = _compute_hashes()
    print()
    print(f"  manifest canon bytes : {hashes['manifestBytes']}")
    print(f"  newScopeHash         : 0x{hashes['scopeHash'].hex()}")
    print(f"  justification bytes  : {hashes['justBytes']}")
    print(f"  justificationHash    : 0x{hashes['justificationHash'].hex()}")
    print(f"  agentId              : {CURATOR_AGENT_ID}")
    print(f"  vhpTokenId           : {VHP_TOKEN_ID}")
    print(f"  domain tag           : {_PROPOSAL_DOMAIN_TAG.decode('ascii')}")
    print(f"  proposalHash         : 0x{hashes['proposalHash'].hex()}")
    print()

    # ─── Web3 + wallet setup ───────────────────────────────────────────────
    from web3 import Web3
    from eth_account import Account

    rpc_url = os.getenv("IOTEX_RPC_URL", "https://babel-api.testnet.iotex.io")
    private_key = os.getenv("BRIDGE_PRIVATE_KEY", "")
    if not private_key:
        print("ERROR: BRIDGE_PRIVATE_KEY not set in env", file=sys.stderr)
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    account = Account.from_key(private_key)
    print(f"  rpc                  : {rpc_url}")
    print(f"  caller               : {account.address}")
    bal_wei = w3.eth.get_balance(account.address)
    bal_iotx = float(w3.from_wei(bal_wei, "ether"))
    print(f"  balance              : {bal_iotx} IOTX")

    if account.address.lower() != "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692".lower():
        print(f"\nERROR: caller {account.address} is NOT the canonical bridge wallet",
              file=sys.stderr)
        sys.exit(2)

    # ─── Pre-broadcast sanity checks ──────────────────────────────────────
    print()
    print("--- PRE-BROADCAST SANITY ---")

    # Resolve BBG.vhpContract() dynamically so we hit the same contract BBG
    # will hit when proposeWithVHP() runs. As of 2026-05-28 this is the
    # VHPExpiresAtAdapter (governance-unblock arc Phase 2b).
    bbg_for_resolve = w3.eth.contract(
        address=w3.to_checksum_address(VAPI_BIOMETRIC_GOVERNANCE_ADDR),
        abi=[{"name": "vhpContract", "type": "function", "stateMutability": "view",
              "inputs": [], "outputs": [{"type": "address"}]}],
    )
    try:
        vhp_addr = bbg_for_resolve.functions.vhpContract().call()
    except Exception as exc:
        print(f"ERROR: could not resolve BBG.vhpContract(): {exc}", file=sys.stderr)
        sys.exit(3)
    print(f"  BBG.vhpContract()    : {vhp_addr}")

    vhp = w3.eth.contract(address=w3.to_checksum_address(vhp_addr), abi=_VHP_ABI)
    try:
        vhp_owner = vhp.functions.ownerOf(VHP_TOKEN_ID).call()
        vhp_valid = vhp.functions.isValid(VHP_TOKEN_ID).call()
        vhp_expires = vhp.functions.expiresAt(VHP_TOKEN_ID).call()
        print(f"  VHP tokenId {VHP_TOKEN_ID} owner   : {vhp_owner}")
        print(f"  VHP tokenId {VHP_TOKEN_ID} isValid : {vhp_valid}")
        print(f"  VHP tokenId {VHP_TOKEN_ID} expires : {vhp_expires} (epoch)")
    except Exception as exc:
        print(f"ERROR: VHP sanity read failed against {vhp_addr}: {exc}",
              file=sys.stderr)
        print(f"       (If this is the adapter, ensure Phase 2b has fired and "
              f"BBG.vhpContract() returns the adapter address — see "
              f"deployed-addresses.json:_phase222_note)", file=sys.stderr)
        sys.exit(3)

    if vhp_owner.lower() != account.address.lower():
        print(f"ERROR: VHP {VHP_TOKEN_ID} owner ({vhp_owner}) != caller ({account.address})",
              file=sys.stderr)
        sys.exit(2)
    if not vhp_valid:
        print(f"ERROR: VHP {VHP_TOKEN_ID} isValid=False -- cannot proposeWithVHP",
              file=sys.stderr)
        sys.exit(2)

    bbg = w3.eth.contract(
        address=w3.to_checksum_address(VAPI_BIOMETRIC_GOVERNANCE_ADDR), abi=_BBG_ABI,
    )
    bbg_max_age = bbg.functions.bbgMaxAgeSec().call()
    print(f"  bbgMaxAgeSec         : {bbg_max_age} ({bbg_max_age/3600:.1f}h freshness window)")
    if vhp_expires < (int(__import__("time").time()) + bbg_max_age):
        hrs_remaining = (vhp_expires - int(__import__("time").time())) / 3600
        print(f"ERROR: VHP {VHP_TOKEN_ID} expires in {hrs_remaining:.1f}h, less than "
              f"BBG max-age window {bbg_max_age/3600:.1f}h", file=sys.stderr)
        sys.exit(2)

    proposal_hash = hashes["proposalHash"]
    already_proposed = bbg.functions.isProposed(proposal_hash).call()
    if already_proposed:
        print(f"ERROR: proposalHash 0x{proposal_hash.hex()} ALREADY submitted "
              f"(anti-replay -- BBG._proposed mapping says True)", file=sys.stderr)
        sys.exit(2)

    total_proposals = bbg.functions.totalProposals().call()
    print(f"  totalProposals (pre) : {total_proposals}")
    print("  pre-broadcast sanity : PASS")

    # ─── Estimate ─────────────────────────────────────────────────────────
    print()
    print("--- GAS ESTIMATE ---")
    fn = bbg.functions.proposeWithVHP(proposal_hash, VHP_TOKEN_ID)
    try:
        est_gas = fn.estimate_gas({"from": account.address})
    except Exception as exc:
        print(f"ERROR: estimate_gas reverted: {exc}", file=sys.stderr)
        sys.exit(3)
    gas_price = w3.eth.gas_price
    buffered_gas = (est_gas * int(GAS_BUFFER * 100)) // 100
    est_cost_wei = est_gas * gas_price
    buf_cost_wei = buffered_gas * gas_price
    print(f"  estimate_gas         : {est_gas}")
    print(f"  buffered (x{GAS_BUFFER:.2f})     : {buffered_gas}")
    print(f"  gasPrice (wei)       : {gas_price}")
    print(f"  est cost             : {w3.from_wei(est_cost_wei, 'ether')} IOTX")
    print(f"  buffered cost        : {w3.from_wei(buf_cost_wei, 'ether')} IOTX")
    print(f"  hard-cap             : {HARD_CAP_IOTX} IOTX")
    buf_cost_iotx = float(w3.from_wei(buf_cost_wei, "ether"))
    if buf_cost_iotx > HARD_CAP_IOTX:
        print(f"\n[HARD-CAP EXCEEDED] {buf_cost_iotx} > {HARD_CAP_IOTX} -- ABORT.",
              file=sys.stderr)
        sys.exit(2)
    if bal_iotx < buf_cost_iotx * 2:
        print(f"\n[BALANCE GUARD] balance {bal_iotx} < 2x buffered cost "
              f"{buf_cost_iotx*2} -- ABORT.", file=sys.stderr)
        sys.exit(2)
    print("  hard-cap check       : PASS")
    print("  balance guard (2x)   : PASS")

    if os.getenv("CURATOR_GOVERNANCE_CONFIRM", "") != "1":
        print()
        print("[ESTIMATE-ONLY] CURATOR_GOVERNANCE_CONFIRM!=1 -- NOT broadcasting.")
        print("Re-run with CURATOR_GOVERNANCE_CONFIRM=1 to broadcast.")
        return 0

    # ─── Process-scoped kill-switch lift + broadcast ──────────────────────
    # Matches the Guardian Tier-2 + VMDR + LensV2 precedent: lift the kill-
    # switch IN THIS PROCESS ONLY (does not modify .env). The bridge's
    # CHAIN_SUBMISSION_PAUSED posture re-engages on next bridge start.
    os.environ["CHAIN_SUBMISSION_PAUSED"] = "false"

    print()
    print("[BROADCASTING] CURATOR_GOVERNANCE_CONFIRM=1 -- sending tx...")
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction({
        "from":      account.address,
        "nonce":     nonce,
        "gas":       buffered_gas,
        "gasPrice":  gas_price,
        "chainId":   4690,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  tx hash              : 0x{tx_hash.hex()}")
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"  block                : {rcpt.blockNumber}")
    print(f"  gas used             : {rcpt.gasUsed}")
    print(f"  status               : {rcpt.status} "
          f"({'success' if rcpt.status == 1 else 'FAILED'})")

    # Verify the commitment landed
    post_count = bbg.functions.totalProposals().call()
    post_proposed = bbg.functions.isProposed(proposal_hash).call()
    print(f"  totalProposals (post): {post_count} (was {total_proposals})")
    print(f"  isProposed(hash)     : {post_proposed} (expected True)")

    print()
    print("DEPLOY_RESULT_JSON " + json.dumps({
        "scriptName":         "fire_curator_governance_proposal",
        "agentId":            CURATOR_AGENT_ID,
        "vhpTokenId":         VHP_TOKEN_ID,
        "proposalHash":       "0x" + proposal_hash.hex(),
        "newScopeHash":       "0x" + hashes["scopeHash"].hex(),
        "justificationHash":  "0x" + hashes["justificationHash"].hex(),
        "txHash":             "0x" + tx_hash.hex(),
        "blockNumber":        rcpt.blockNumber,
        "gasUsed":            rcpt.gasUsed,
        "status":             rcpt.status,
        "totalProposalsPre":  total_proposals,
        "totalProposalsPost": post_count,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
