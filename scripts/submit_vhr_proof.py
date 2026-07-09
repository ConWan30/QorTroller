#!/usr/bin/env python3
"""Submit the M17 VHR Groth16 replay proof on-chain (VAPIReplayProofVerifier.verify).

Turns "we verified the replay proof locally (snarkjs OK)" into "the chain witnessed it": calls
`verify(a,b,c,publicInputs[6])` on the deployed v1 wrapper, which re-runs the pairing check on-chain
and emits `ReplayProofVerified` on acceptance. The proof stays zero-knowledge (only the 6 public
inputs cross the wire — the sanitized matrix never leaves the rig).

SAFETY (anchor_posp_commitment.py / guardian_sig_anchor_tier2.py precedent):
  - snarkjs proof -> Solidity calldata done in PURE PYTHON (no snarkjs dep): a=[pi_a0,pi_a1];
    b=[[pi_b01,pi_b00],[pi_b11,pi_b10]] (the G2 pair-swap the EVM bn256 precompile needs);
    c=[pi_c0,pi_c1]; publicInputs = the 6 signals.
  - PRE-SEND verifyView eth_call (0 IOTX): confirms the inner Groth16 verifier ACCEPTS this exact
    calldata on-chain BEFORE spending a single gas unit. If verifyView != True -> ABORT, never send.
  - estimate_gas pre-send revert guard + dynamic gas x1.25 (IoTeX OOG gotcha).
  - --estimate-only (DEFAULT): read-only (verifyView + estimate_gas), sends NOTHING, safe anytime.
  - --execute triple-gate (process-scoped; bridge/.env never touched):
      Gate 1: env CHAIN_SUBMISSION_PAUSED=false
      Gate 2: env VHR_SUBMIT_AUTHORIZED=true
      Gate 3: --confirm
      + hard cap COST_BUDGET_IOTX; key read from bridge/.env internally (never transits the shell).

Usage:
    python scripts/submit_vhr_proof.py \
        --proof audits/vhr_proof2_m17/proof_m17_real.json \
        --public audits/vhr_proof2_m17/public_m17_real.json          # estimate-only (default)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

RPC = "https://babel-api.testnet.iotex.io"
# v1 wrapper (PROOF_TYPE keccak256("VAPI-REPLAY-PROOF-v1"), 6 public inputs) — matches the M17 proof.
VERIFIER = "0x5182372d1D033db0c9230843DFDE606733D5F91B"
WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
COST_BUDGET_IOTX = 1.0                # Groth16 on-chain verify is gas-heavier than a plain anchor
_IN = [{"name": "a", "type": "uint256[2]"}, {"name": "b", "type": "uint256[2][2]"},
       {"name": "c", "type": "uint256[2]"}, {"name": "publicInputs", "type": "uint256[6]"}]
_ABI = [{"name": "verify", "type": "function", "stateMutability": "nonpayable",
         "inputs": _IN, "outputs": [{"name": "verified", "type": "bool"}]},
        {"name": "verifyView", "type": "function", "stateMutability": "view",
         "inputs": _IN, "outputs": [{"name": "", "type": "bool"}]}]


def _w3():
    from web3 import Web3
    return Web3(Web3.HTTPProvider(RPC, request_kwargs={
        "timeout": 30, "headers": {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}}))


def _calldata(proof: dict, public: list):
    """snarkjs proof + public signals -> (a, b, c, publicInputs) in Solidity/EVM order."""
    a = [int(proof["pi_a"][0]), int(proof["pi_a"][1])]
    b = [[int(proof["pi_b"][0][1]), int(proof["pi_b"][0][0])],     # swap each G2 coordinate pair
         [int(proof["pi_b"][1][1]), int(proof["pi_b"][1][0])]]
    c = [int(proof["pi_c"][0]), int(proof["pi_c"][1])]
    pub = [int(x) for x in public]
    if len(pub) != 6:
        raise ValueError(f"expected 6 public inputs, got {len(pub)}")
    return a, b, c, pub


def main() -> int:
    ap = argparse.ArgumentParser(description="Submit the M17 VHR replay proof on-chain")
    ap.add_argument("--proof", required=True)
    ap.add_argument("--public", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    proof = json.load(open(args.proof, encoding="utf-8"))
    public = json.load(open(args.public, encoding="utf-8"))
    a, b, c, pub = _calldata(proof, public)

    print(f"\n  VHR proof submit -> VAPIReplayProofVerifier {VERIFIER}")
    print(f"  proof            : {os.path.basename(args.proof)} (protocol={proof.get('protocol')}, "
          f"curve={proof.get('curve')})")
    print(f"  replayProofToken : {hex(pub[0])[:18]}...  poacChainRoot: {hex(pub[2])[:18]}...")
    print(f"  humanityThreshold: {pub[4]}  (public inputs only — the matrix never leaves the rig)")

    w3 = _w3()
    reg = w3.eth.contract(address=VERIFIER, abi=_ABI)

    # ---- PRE-SEND verifyView eth_call (0 IOTX): does the chain ACCEPT this proof? ----
    try:
        accepted = reg.functions.verifyView(a, b, c, pub).call({"from": WALLET})
    except Exception as exc:  # noqa: BLE001
        print(f"  ABORT: verifyView eth_call reverted: {exc}", file=sys.stderr)
        return 3
    print(f"  verifyView (0 IOTX): {'ACCEPTED' if accepted else 'REJECTED'}  "
          f"<- on-chain Groth16 verdict for this exact calldata")
    if not accepted:
        print("  ABORT: the chain would NOT accept this proof — nothing to submit.", file=sys.stderr)
        return 3

    bal = w3.eth.get_balance(WALLET) / 1e18
    tx = reg.functions.verify(a, b, c, pub).build_transaction(
        {"from": WALLET, "nonce": w3.eth.get_transaction_count(WALLET),
         "gasPrice": w3.eth.gas_price, "chainId": 4690})
    try:
        gas_est = w3.eth.estimate_gas(tx)
    except Exception as exc:  # noqa: BLE001
        print(f"  ABORT: estimate_gas reverted, NOT sending: {exc}", file=sys.stderr)
        return 3
    tx["gas"] = int(gas_est * 1.25)
    cost = tx["gas"] * tx["gasPrice"] / 1e18
    print(f"  wallet balance   : {bal:.6f} IOTX (live)")
    print(f"  estimate_gas     : {gas_est} -> gas {tx['gas']} | est cost ~{cost:.4f} IOTX "
          f"(cap {COST_BUDGET_IOTX})")

    if not args.execute:
        print("  MODE: estimate-only. verifyView ACCEPTED + gas estimated. Nothing sent.\n"
              "  To broadcast: --execute --confirm with CHAIN_SUBMISSION_PAUSED=false + "
              "VHR_SUBMIT_AUTHORIZED=true.\n")
        return 0

    # ---- execute path: triple gate ----
    if os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower() != "false":
        print("  Gate 1 FAILED: set CHAIN_SUBMISSION_PAUSED=false in the SHELL (process-scope).",
              file=sys.stderr)
        return 3
    if os.environ.get("VHR_SUBMIT_AUTHORIZED", "").strip().lower() != "true":
        print("  Gate 2 FAILED: set VHR_SUBMIT_AUTHORIZED=true.", file=sys.stderr)
        return 3
    if not args.confirm:
        print("  Gate 3 FAILED: pass --confirm.", file=sys.stderr)
        return 3
    if cost > COST_BUDGET_IOTX:
        print(f"  ABORT: est cost {cost:.4f} exceeds hard cap {COST_BUDGET_IOTX}.", file=sys.stderr)
        return 3

    key = os.environ.get("OPERATOR_PRIVATE_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "bridge", ".env")
        if os.path.isfile(env_path):
            for line in open(env_path, encoding="utf-8"):
                line = line.strip()
                if line.startswith("BRIDGE_PRIVATE_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        print("  ABORT: no signing key (OPERATOR_PRIVATE_KEY env or BRIDGE_PRIVATE_KEY in bridge/.env).",
              file=sys.stderr)
        return 3

    signed = w3.eth.account.sign_transaction(tx, key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  sent {txh.hex()} -- waiting for receipt ...")
    rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=120)
    ok = rcpt.get("status") == 1
    print(f"  status={rcpt.get('status')} block={rcpt.get('blockNumber')} gasUsed={rcpt.get('gasUsed')}")

    manifest = {
        "artifact": "vhr-proof-onchain-submission-v0",
        "verifier": VERIFIER, "method": "verify(a,b,c,publicInputs[6]) -> ReplayProofVerified",
        "proof_file": args.proof, "public_file": args.public,
        "replay_proof_token": hex(pub[0]), "poac_chain_root": hex(pub[2]),
        "humanity_threshold": pub[4], "verifyView_accepted": bool(accepted),
        "tx": txh.hex(), "block": rcpt.get("blockNumber"), "status": rcpt.get("status"),
        "gas_used": rcpt.get("gasUsed"), "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out = "audits/vhr_proof2_m17/vhr_onchain_submission.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print(f"  submission manifest -> {out}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
