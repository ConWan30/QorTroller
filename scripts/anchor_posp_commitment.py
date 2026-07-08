#!/usr/bin/env python3
"""ACT-1 A3 -- anchor a PoSP record's file digest on IoTeX (AdjudicationRegistry reuse).

KC-A3-1 (the design decision, documented where it executes): PoSP has NO commitment
method BY DESIGN (REFERENCE-AND-BIND -- its integrity is the commitments it references).
So the anchorable 32 bytes are an EXTERNAL file digest: SHA-256 over the exact canonical
record bytes as published (audits/posp_record_*.json). Anyone holding the published file
recomputes the digest and checks the chain. No PoSP schema change, no new commitment
method, no new domain tag -- the anchor manifest artifact written next to the record
documents the preimage (file path + digest + tx) for reproduction.

Pattern: guardian_sig_anchor_tier2.py precedent (double-gate + confirm, 0.50 IOTX hard
cap, estimate_gas pre-send revert guard, dynamic gas x1.25 per the IoTeX OOG gotcha).

MODES:
  --estimate-only (DEFAULT): read-only RPC -- builds the tx, estimates gas + cost,
      sends NOTHING. No gates needed; safe anytime.
  --execute: requires ALL of (process-scoped, bridge/.env never touched):
      Gate 1: env CHAIN_SUBMISSION_PAUSED=false
      Gate 2: env POSP_ANCHOR_AUTHORIZED=true
      Gate 3: --confirm flag
      plus OPERATOR_PRIVATE_KEY in env (never logged).

Usage:
    python scripts/anchor_posp_commitment.py --posp audits/posp_record_match14_rp_option_b_2026-07-07.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

RPC = "https://babel-api.testnet.iotex.io"
ADJUDICATION_REGISTRY = "0x44CF981f46a52ADE56476Ce894255954a7776fb4"
WALLET = "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692"
COST_BUDGET_IOTX = 0.50
_ABI = [{"name": "recordAdjudication", "type": "function", "stateMutability": "nonpayable",
         "inputs": [{"name": "deviceIdHash", "type": "bytes32"},
                    {"name": "payload", "type": "bytes32"},
                    {"name": "flagged", "type": "bool"}],
         "outputs": []}]


def _w3():
    from web3 import Web3
    return Web3(Web3.HTTPProvider(RPC, request_kwargs={
        "timeout": 30, "headers": {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}}))


def main() -> int:
    ap = argparse.ArgumentParser(description="Anchor a PoSP record digest (A3)")
    ap.add_argument("--posp", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()

    raw = open(args.posp, "rb").read()
    digest = hashlib.sha256(raw).digest()
    rec = json.loads(raw)
    device_id = (rec.get("device_id") or "").strip()
    if len(device_id) != 64:
        print(f"ABORT: record device_id is not 32 bytes hex: {device_id!r}", file=sys.stderr)
        return 2

    print(f"\n  PoSP anchor -- {os.path.basename(args.posp)}")
    print(f"  record verdict : {rec.get('verdict')} (session {str(rec.get('session_id'))[:16]}...)")
    print(f"  file digest    : {digest.hex()}   <- the bytes32 payload (SHA-256 of the file)")
    print(f"  device id hash : {device_id}")

    w3 = _w3()
    bal = w3.eth.get_balance(WALLET) / 1e18
    reg = w3.eth.contract(address=ADJUDICATION_REGISTRY, abi=_ABI)
    tx = reg.functions.recordAdjudication(
        bytes.fromhex(device_id), digest, False
    ).build_transaction({"from": WALLET, "nonce": w3.eth.get_transaction_count(WALLET),
                         "gasPrice": w3.eth.gas_price, "chainId": 4690})
    try:
        gas_est = w3.eth.estimate_gas(tx)          # pre-send revert guard: reverts iff call would
    except Exception as exc:  # noqa: BLE001
        print(f"  ABORT: estimate_gas reverted -- the call would revert, NOT sending: {exc}",
              file=sys.stderr)
        return 3
    tx["gas"] = int(gas_est * 1.25)                # the IoTeX OOG gotcha: dynamic, never static
    cost = tx["gas"] * tx["gasPrice"] / 1e18
    print(f"  wallet balance : {bal:.6f} IOTX (live)")
    print(f"  estimate_gas   : {gas_est} -> gas {tx['gas']} | est cost ~{cost:.4f} IOTX "
          f"(cap {COST_BUDGET_IOTX})")

    if not args.execute:
        print("  MODE: estimate-only. Nothing sent. Re-run with --execute --confirm + gates to fire.\n")
        return 0

    # ---- execute path: triple gate ----
    if os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower() != "false":
        print("  Gate 1 FAILED: set CHAIN_SUBMISSION_PAUSED=false in the SHELL "
              "(process-scope; bridge/.env never changes).", file=sys.stderr)
        return 3
    if os.environ.get("POSP_ANCHOR_AUTHORIZED", "").strip().lower() != "true":
        print("  Gate 2 FAILED: set POSP_ANCHOR_AUTHORIZED=true.", file=sys.stderr)
        return 3
    if not args.confirm:
        print("  Gate 3 FAILED: pass --confirm.", file=sys.stderr)
        return 3
    if cost > COST_BUDGET_IOTX:
        print(f"  ABORT: est cost {cost:.4f} exceeds hard cap {COST_BUDGET_IOTX}.", file=sys.stderr)
        return 3
    key = os.environ.get("OPERATOR_PRIVATE_KEY", "")
    if not key:
        print("  ABORT: OPERATOR_PRIVATE_KEY not in env.", file=sys.stderr)
        return 3

    signed = w3.eth.account.sign_transaction(tx, key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  sent {txh.hex()} -- waiting for receipt ...")
    rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=120)
    ok = rcpt.get("status") == 1
    print(f"  status={rcpt.get('status')} block={rcpt.get('blockNumber')} "
          f"gasUsed={rcpt.get('gasUsed')}")

    manifest = {
        "artifact": "posp-anchor-manifest-v0",
        "posp_file": args.posp,
        "file_sha256": digest.hex(),
        "preimage": "SHA-256 over the exact published record file bytes (KC-A3-1: PoSP has "
                    "no commitment method BY DESIGN; this is an external file digest)",
        "contract": ADJUDICATION_REGISTRY,
        "method": "recordAdjudication(deviceIdHash, payload=file_sha256, flagged=false)",
        "device_id_hash": device_id,
        "tx": txh.hex(), "block": rcpt.get("blockNumber"), "status": rcpt.get("status"),
        "gas_used": rcpt.get("gasUsed"), "anchored_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "session_id": rec.get("session_id"), "verdict": rec.get("verdict"),
    }
    out = args.posp.replace("posp_record", "posp_anchor").replace(".json", "") + "_anchor.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print(f"  anchor manifest -> {out}\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
