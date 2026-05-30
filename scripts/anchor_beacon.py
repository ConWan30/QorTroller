#!/usr/bin/env python3
"""Data Economy Arc 6 — VAPITemporalBeaconRegistry keeper (operator cron).

Per Decision T1 → Option B: operator-fired cron anchors block hashes at
ANCHOR_CADENCE=64 blocks. Reads the latest finalized block from IoTeX
testnet, rounds DOWN to the nearest cadence multiple within the 256-block
BLOCKHASH window, calls `anchorBeacon(blockNumber)` against the registry
from the bridge wallet (which must already be `setKeeper`-set by owner).

Honest ongoing cost (empirical IoTeX testnet 2026-05-30, 2.616 s/block):
  64-block cadence -> ~2.8 min/anchor -> ~516 anchors/day
  ~0.0005 IOTX/anchor -> ~0.258 IOTX/day (revised from spec's 0.135)
  Document in keeper runbook; refill cycle becomes operational reality.

Usage:
  # one-shot anchor (manual cron tick):
  python scripts/anchor_beacon.py

  # dry-run (estimate only):
  ANCHOR_BEACON_CONFIRM=0 python scripts/anchor_beacon.py

  # loop (background daemon — operator decides how to supervise):
  python scripts/anchor_beacon.py --loop

Required env (read from contracts/.env or operator shell):
  TEMPORAL_BEACON_REGISTRY_ADDRESS  Arc 6 Commit 1 registry address
  DEPLOYER_PRIVATE_KEY              keeper wallet key (= bridge wallet for v1)
  ANCHOR_BEACON_CONFIRM=1           required to broadcast (default: 0 = dry-run)

Honesty rails:
  - Skips if the latest cadence block within window is already anchored
  - Hard-cap: refuses to spend > 0.005 IOTX per anchor (gas-price safety)
  - Pre-send `estimate_gas` revert-guard
  - Logs every action to stderr; one machine-readable JSON line per anchor
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from web3 import Web3
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
log = logging.getLogger("anchor_beacon")

# Reads contracts/.env where DEPLOYER_PRIVATE_KEY lives. Project-root .env
# is also loaded as a fallback (path-discovery memory).
load_dotenv(Path(__file__).resolve().parent.parent / "contracts" / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

RPC_URL = "https://babel-api.testnet.iotex.io"
CHAIN_ID = 4690
ANCHOR_CADENCE = 64
BLOCKHASH_WINDOW = 256
HARD_CAP_IOTX = 0.005      # per-anchor max spend
GAS_BUFFER = 1.25

REGISTRY_ABI = [
    {"name": "ANCHOR_CADENCE", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "keeper", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"name": "", "type": "address"}]},
    {"name": "anchoredHash", "type": "function", "stateMutability": "view",
     "inputs": [{"name": "blockNumber", "type": "uint256"}],
     "outputs": [{"name": "", "type": "bytes32"}]},
    {"name": "latestAnchoredBlock", "type": "function", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "anchorBeacon", "type": "function", "stateMutability": "nonpayable",
     "inputs": [{"name": "blockNumber", "type": "uint256"}], "outputs": []},
]


def _require_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        log.error("ERROR: %s env not set", name)
        sys.exit(2)
    return v


def _candidate_cadence_block(latest_block: int) -> int:
    """Return the highest cadence-multiple block that is:
      - strictly less than `latest_block`
      - within the 256-block BLOCKHASH window
    """
    # Round down `latest_block - 1` to the nearest multiple of ANCHOR_CADENCE
    candidate = (latest_block - 1) - ((latest_block - 1) % ANCHOR_CADENCE)
    if latest_block - candidate > BLOCKHASH_WINDOW:
        # Should never happen at ANCHOR_CADENCE=64 (well within 256), but
        # guard anyway in case of clock skew / forced gap.
        return -1
    return candidate


def anchor_once(*, confirm: bool) -> dict:
    """Anchor exactly one cadence block. Returns a result dict. Idempotent:
    if the candidate cadence block is already anchored, returns
    outcome=already_anchored with no chain action."""
    registry_addr = _require_env("TEMPORAL_BEACON_REGISTRY_ADDRESS")
    deployer_key = _require_env("DEPLOYER_PRIVATE_KEY")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        log.error("RPC not reachable: %s", RPC_URL)
        return {"outcome": "rpc_down"}

    account = w3.eth.account.from_key(deployer_key)
    registry = w3.eth.contract(
        address=w3.to_checksum_address(registry_addr), abi=REGISTRY_ABI,
    )

    # Sanity: keeper must be set to our address
    onchain_keeper = registry.functions.keeper().call()
    if onchain_keeper.lower() != account.address.lower():
        log.error("registry keeper %s != our wallet %s — operator must call setKeeper",
                  onchain_keeper, account.address)
        return {"outcome": "keeper_mismatch", "registry_keeper": onchain_keeper,
                "our_wallet": account.address}

    latest_block = w3.eth.block_number
    candidate = _candidate_cadence_block(latest_block)
    if candidate < 0:
        return {"outcome": "no_candidate_in_window", "latest_block": latest_block}

    # Idempotency check
    already = registry.functions.anchoredHash(candidate).call()
    if int.from_bytes(already, "big") != 0:
        log.info("candidate %d already anchored (hash=%s) — skip", candidate, already.hex())
        return {"outcome": "already_anchored", "block": candidate, "hash": already.hex()}

    log.info("preparing to anchor block %d (latest=%d, gap=%d)",
             candidate, latest_block, latest_block - candidate)

    # Pre-send estimate_gas
    try:
        est_gas = registry.functions.anchorBeacon(candidate).estimate_gas({"from": account.address})
    except Exception as e:
        log.error("estimate_gas failed (likely the candidate block hash is now > 256 behind): %s", e)
        return {"outcome": "estimate_failed", "error": str(e)[:200]}

    gas_price = w3.eth.gas_price
    buf_gas = int(est_gas * GAS_BUFFER)
    cost_wei = buf_gas * gas_price
    cost_iotx = cost_wei / 1e18
    log.info("estimate=%d gas, buffered=%d, cost=%.6f IOTX (cap=%.4f)",
             est_gas, buf_gas, cost_iotx, HARD_CAP_IOTX)
    if cost_iotx > HARD_CAP_IOTX:
        return {"outcome": "hard_cap_exceeded", "buffered_cost_iotx": cost_iotx}

    if not confirm:
        log.info("ANCHOR_BEACON_CONFIRM!=1 — dry-run only")
        return {"outcome": "dry_run", "block": candidate, "buffered_cost_iotx": cost_iotx}

    # Build + send tx (legacy type 0 — IoTeX EIP-1559 reservation quirk per
    # Arc 5 manifest-write precedent)
    nonce = w3.eth.get_transaction_count(account.address)
    tx = registry.functions.anchorBeacon(candidate).build_transaction({
        "from": account.address, "nonce": nonce, "gas": buf_gas,
        "gasPrice": gas_price, "chainId": CHAIN_ID, "type": 0,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    log.info("broadcast tx %s for block %d", tx_hash.hex(), candidate)
    rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    result = {
        "outcome": "anchored" if rcpt.status == 1 else "failed",
        "block": candidate, "tx_hash": tx_hash.hex(),
        "tx_block": rcpt.blockNumber, "gas_used": rcpt.gasUsed,
        "status": rcpt.status,
    }
    log.info("ANCHOR_RESULT_JSON %s", json.dumps(result))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true",
                    help="anchor in a loop with sleep matching cadence (operator cron use)")
    ap.add_argument("--sleep-s", type=int, default=170,
                    help="seconds between attempts in --loop mode (default 170s ≈ 64-block cadence)")
    args = ap.parse_args()

    confirm = os.environ.get("ANCHOR_BEACON_CONFIRM") == "1"
    if not confirm:
        log.warning("ANCHOR_BEACON_CONFIRM!=1 — running in dry-run mode")

    if args.loop:
        log.info("loop mode — interval %ds (operator-supervised)", args.sleep_s)
        while True:
            try:
                anchor_once(confirm=confirm)
            except KeyboardInterrupt:
                log.info("interrupted — exit")
                return
            except Exception as e:
                log.exception("anchor cycle failed (non-fatal): %s", e)
            time.sleep(args.sleep_s)
    else:
        result = anchor_once(confirm=confirm)
        print(json.dumps(result))
        sys.exit(0 if result.get("outcome") in ("anchored", "already_anchored", "dry_run") else 1)


if __name__ == "__main__":
    main()
