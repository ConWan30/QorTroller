"""Anchor the VAPI-RETINA-STATE-v3 FROZEN-v1 freeze governance event ON-CHAIN (IoTeX testnet).

One-shot, bounded, triple-gated, ESTIMATE-FIRST. Records a reproducible 32-byte commitment to the
freeze - the sealed 183-invariant allowlist root + the INV-RETINA-STATE-V3 formula digest - on
AdjudicationRegistry so a third party can confirm, months later, that the freeze was anchored
on-chain at block N. Uses AdjudicationRegistry (a general commitment anchor) deliberately, to
avoid entangling with the ProtocolCoherenceRegistry governance-provenance FSCA cross-check.

  freeze_commitment = SHA-256( b"VAPI-RETINA-STATE-v3-FREEZE-v1"
                               || compute_allowlist_hash()(32)      # sealed 183-invariant root
                               || INV-RETINA-STATE-V3 digest(32) )  # frozen v3 formula pin
Reproducible by anyone from the committed .github/INVARIANTS_ALLOWLIST.json.

MODES:
  --estimate   read-only: connect + compute + estimate_gas + print cost. 0 IOTX, NO gates, NO broadcast.
  --confirm    broadcast, TRIPLE-GATED (process-scoped; bridge/.env never changed):
                 Gate 1: env CHAIN_SUBMISSION_PAUSED=false            (kill-switch, process-scope)
                 Gate 2: env RETINA_V3_FREEZE_ANCHOR_AUTHORIZED=true  (intent)
                 Gate 3: --confirm CLI flag
               estimate_gas*1.25 + pre-send revert guard + hard cap COST_BUDGET_IOTX + balance floor.
               The env vars vanish on shell exit; bridge/.env stays paused.

  # estimate (safe, run anytime):
  python scripts/anchor_governance_freeze.py --estimate
  # broadcast (one shell):
  CHAIN_SUBMISSION_PAUSED=false RETINA_V3_FREEZE_ANCHOR_AUTHORIZED=true \\
    python scripts/anchor_governance_freeze.py --confirm

EXIT: 0 ok/estimate  1 gate  2 balance  3 chain  5 cost-over-budget
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(PROJECT_ROOT), str(PROJECT_ROOT / "bridge"), str(PROJECT_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

COST_BUDGET_IOTX = 0.30       # hard cap; abort if a single anchor would exceed
BALANCE_FLOOR_IOTX = 0.05     # refuse if wallet below this
DOMAIN = b"VAPI-RETINA-STATE-v3-FREEZE-v1"
DEVICE_TAG = "VAPI_RETINA_STATE_V3_FREEZE_ANCHOR_v1"
ALLOWLIST = PROJECT_ROOT / ".github" / "INVARIANTS_ALLOWLIST.json"


def _freeze_commitment() -> tuple[str, str, str]:
    """(freeze_commitment_hex, allowlist_hash_hex, inv_v3_digest_hex) - all reproducible from the
    committed allowlist. Raises if the freeze isn't sealed (INV-RETINA-STATE-V3 absent)."""
    from vapi_invariant_gate import compute_allowlist_hash
    allowlist_hash = compute_allowlist_hash()
    d = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    inv = d if "INV-001" in d else d.get("invariants", d)
    entry = inv.get("INV-RETINA-STATE-V3")
    inv_v3 = (entry.get("digest") if isinstance(entry, dict) else entry) or ""
    if len(allowlist_hash) != 64 or len(inv_v3) != 64:
        raise SystemExit("ABORT: INV-RETINA-STATE-V3 not in the sealed allowlist (is the freeze sealed?)")
    preimage = DOMAIN + bytes.fromhex(allowlist_hash) + bytes.fromhex(inv_v3)
    return hashlib.sha256(preimage).hexdigest(), allowlist_hash, inv_v3


def _check_gates() -> tuple[bool, str]:
    if os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower() != "false":
        return False, "Gate 1 FAILED: set CHAIN_SUBMISSION_PAUSED=false in the SHELL (process-scope, not bridge/.env)."
    if os.environ.get("RETINA_V3_FREEZE_ANCHOR_AUTHORIZED", "").strip().lower() != "true":
        return False, "Gate 2 FAILED: set RETINA_V3_FREEZE_ANCHOR_AUTHORIZED=true (intent)."
    return True, "all 3 gates aligned"


async def _run(broadcast: bool) -> int:
    mode = "[BROADCAST]" if broadcast else "[ESTIMATE-ONLY, read-only, 0 IOTX]"
    print("=" * 76)
    print(f"Anchor VAPI-RETINA-STATE-v3 FROZEN-v1 freeze on IoTeX testnet  {mode}")
    print("=" * 76)

    commit_hex, allowlist_hash, inv_v3 = _freeze_commitment()
    print(f"  allowlist_hash (183 invariants) : {allowlist_hash}")
    print(f"  INV-RETINA-STATE-V3 digest      : {inv_v3}")
    print(f"  freeze_commitment (to anchor)   : {commit_hex}")

    if broadcast:
        ok, reason = _check_gates()
        if not ok:
            print(f"  ABORT: {reason}")
            return 1
        print(f"  Gates: {reason}")

    from vapi_bridge.config import Config
    from vapi_bridge.chain import ChainClient
    cfg = Config()
    chain = ChainClient(cfg)
    if chain._account is None:
        print("  ABORT: bridge wallet not loaded")
        return 2
    addr = chain._account.address
    addr_reg = getattr(cfg, "adjudication_registry_address", "")
    if not addr_reg:
        print("  ABORT: adjudication_registry_address not configured")
        return 3
    bal = (await chain._w3.eth.get_balance(addr)) / 1e18
    gas_price = await chain._w3.eth.gas_price
    print(f"  Wallet: {addr} | balance {bal:.6f} IOTX | gas_price {gas_price/1e9:.2f} Gwei")
    print(f"  AdjudicationRegistry: {addr_reg}")

    _ABI = [{"name": "recordAdjudication", "type": "function", "stateMutability": "nonpayable",
             "inputs": [{"name": "deviceIdHash", "type": "bytes32"},
                        {"name": "poadHash", "type": "bytes32"},
                        {"name": "dualVeto", "type": "bool"}], "outputs": []}]
    reg = chain._w3.eth.contract(address=chain._w3.to_checksum_address(addr_reg), abi=_ABI)
    device_id_hash = hashlib.sha256(DEVICE_TAG.encode()).digest()
    poad = bytes.fromhex(commit_hex)
    nonce = await chain._w3.eth.get_transaction_count(addr)
    tx = await reg.functions.recordAdjudication(device_id_hash, poad, False).build_transaction(
        {"from": addr, "nonce": nonce})
    # PRE-SEND revert guard: estimate_gas reverts iff the call itself would revert
    # (e.g. this commitment is already anchored -> anti-replay).
    try:
        gas_est = await chain._w3.eth.estimate_gas(tx)
    except Exception as exc:
        print(f"  estimate_gas REVERTED - the call would revert (already anchored, or not authorized): {exc}")
        return 3
    gas = int(gas_est * 1.25)
    est_cost = gas * gas_price / 1e18
    print(f"  estimate_gas={gas_est} -> gas(x1.25)={gas} | EST COST ~{est_cost:.6f} IOTX (hard cap {COST_BUDGET_IOTX})")

    if not broadcast:
        print("\n  ESTIMATE-ONLY complete: nothing broadcast, 0 IOTX spent.")
        print("  To fire (one shell):")
        print("    CHAIN_SUBMISSION_PAUSED=false RETINA_V3_FREEZE_ANCHOR_AUTHORIZED=true \\")
        print("      python scripts/anchor_governance_freeze.py --confirm")
        return 0

    if bal < BALANCE_FLOOR_IOTX:
        print(f"  ABORT: balance {bal:.6f} < floor {BALANCE_FLOOR_IOTX}")
        return 2
    if est_cost > COST_BUDGET_IOTX:
        print(f"  ABORT (pre-send cap): est cost {est_cost:.6f} > budget {COST_BUDGET_IOTX}")
        return 5
    tx["gas"] = gas
    print("\n  Firing recordAdjudication (1 tx, AdjudicationRegistry)...")
    try:
        signed = chain._account.sign_transaction(tx)
        txh = await chain._w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash = txh.hex()
    except Exception as exc:
        print(f"  CHAIN ERROR: {exc}")
        return 3
    receipt = await chain._w3.eth.wait_for_transaction_receipt(txh, timeout=120)
    block, status = receipt.get("blockNumber"), receipt.get("status")
    try:
        recorded = await chain.is_adjudication_recorded(commit_hex)
    except Exception as exc:
        print(f"  WARN: isRecorded verify failed: {exc}")
        recorded = None
    bal_after = (await chain._w3.eth.get_balance(addr)) / 1e18
    cost = bal - bal_after
    print(f"  tx={tx_hash} block={block} status={status} isRecorded={recorded} cost={cost:.6f} IOTX")

    proven = (status == 1) and (recorded is True) and (cost <= COST_BUDGET_IOTX)
    ts_iso = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = f"""# QorTroller - On-Chain Anchor: VAPI-RETINA-STATE-v3 FROZEN-v1 Freeze

**Claim proven:** the VAPI-RETINA-STATE-v3 governance freeze (TRA-1 T3; PV-CI 182->183) is
recorded **on-chain on IoTeX testnet** - third-party verifiable, reproducible from the committed
allowlist, no bridge or private access required.

**Result: {"PROVEN" if proven else "SEE FIELDS"}**  .  {ts_iso}

| Field | Value |
|---|---|
| network | IoTeX testnet (chain ID 4690) |
| contract | AdjudicationRegistry `{addr_reg}` |
| deviceIdHash attribution | SHA-256(`{DEVICE_TAG}`) |
| tx_hash | `{tx_hash}` |
| block | {block} . status {status} |
| freeze_commitment (isRecorded={recorded}) | `{commit_hex}` |
| allowlist_hash (183 invariants) | `{allowlist_hash}` |
| INV-RETINA-STATE-V3 digest | `{inv_v3}` |
| cost | **{cost:.6f} IOTX** (testnet; hard cap {COST_BUDGET_IOTX}) |
| wallet | `{addr}` |

## How a third party verifies (no bridge, no private access)
1. `compute_allowlist_hash()` over the committed `.github/INVARIANTS_ALLOWLIST.json` (183 entries) == allowlist_hash above.
2. `freeze_commitment = SHA-256(b"VAPI-RETINA-STATE-v3-FREEZE-v1" || allowlist_hash(32) || INV-RETINA-STATE-V3 digest(32))` == the value above.
3. `AdjudicationRegistry.isRecorded(freeze_commitment) == true` at the tx/block above (IoTeX testnet explorer / eth_call).

## Scope / honesty
Testnet (no real economic value); ONE bounded tx (~{cost:.4f} IOTX, hard-capped {COST_BUDGET_IOTX}); the kill-switch was lifted process-scoped only (bridge/.env stays paused; restart re-engages it). The CI-authoritative allowlist seal is independent of this anchor; this records tamper-evident on-chain provenance of the freeze via a general commitment registry (AdjudicationRegistry), not the coherence/governance-provenance path.
"""
    out = PROJECT_ROOT / "docs" / "qortroller-retina-v3-freeze-onchain-anchor-proof.md"
    out.write_text(doc, encoding="utf-8")
    print(f"  artifact: {out}")
    print("  " + ("PROVEN - freeze anchored on-chain" if proven else "INCOMPLETE - see fields"))
    return 0 if proven else 5


def _main() -> int:
    ap = argparse.ArgumentParser(description="Anchor the VAPI-RETINA-STATE-v3 freeze on IoTeX (estimate-first, triple-gated).")
    ap.add_argument("--estimate", action="store_true", help="read-only: print gas + cost, 0 IOTX, no gates, no broadcast")
    ap.add_argument("--confirm", action="store_true", help="broadcast the anchor tx (requires the two env gates)")
    a = ap.parse_args()
    if not (a.estimate or a.confirm):
        print("  Specify --estimate (read-only cost) or --confirm (broadcast, triple-gated).")
        return 0
    return asyncio.run(_run(broadcast=a.confirm))


if __name__ == "__main__":
    sys.exit(_main())
