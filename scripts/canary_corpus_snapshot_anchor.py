"""Phase 238 Session 1 — Canary CORPUS-SNAPSHOT anchor smoke-test.

PURPOSE: validate the kill-switch flip + chain submission path with the
SMALLEST POSSIBLE on-chain operation (~0.001 IOTX) BEFORE committing
~0.20 IOTX of real Curator activation deploys in Session 1.

This is the safety canary that prevents another wallet-drain incident
like Phase 237.5 Path C+ (where ~17.95 IOTX leaked over one session
because 18 chain.py methods bypassed the _send_tx kill-switch — fixed
permanently in commit f1a7be31).

DESIGN — DOUBLE-GATE AUTHORIZATION (process-scoped only):

  Gate 1: env CHAIN_SUBMISSION_PAUSED=false (process-scope only;
          bridge/.env file remains true so any future bridge restart
          re-engages safety posture)
  Gate 2: env CORPUS_SNAPSHOT_CANARY_AUTHORIZED=true (intent gate;
          requires explicit operator setting — refuses otherwise)
  Gate 3: --confirm CLI flag (third-layer authorization)

  All three gates must align before the script will fire one tx.
  Any single gate failing → graceful exit with message.

USAGE — operator runs in ONE shell session:

  PowerShell:
    $env:CHAIN_SUBMISSION_PAUSED="false"
    $env:CORPUS_SNAPSHOT_CANARY_AUTHORIZED="true"
    python scripts/canary_corpus_snapshot_anchor.py --confirm

  Bash:
    CHAIN_SUBMISSION_PAUSED=false \
      CORPUS_SNAPSHOT_CANARY_AUTHORIZED=true \
      python scripts/canary_corpus_snapshot_anchor.py --confirm

  After this shell exits, env vars vanish — bridge/.env is unchanged.

WHAT IT DOES:

  1. Verify all three gates aligned
  2. Read wallet balance (read-only RPC, no gas)
  3. Pick the OLDEST unanchored row from corpus_snapshot_log
     (4 rows pending since Phase 237.5 Path C+ kill-switch engagement)
  4. Anchor that single row via chain.anchor_corpus_snapshot
  5. Verify on-chain via chain.is_adjudication_recorded
  6. Update local row with on_chain_confirmed=True + tx_hash
  7. Read wallet balance after — confirm only ~0.001 IOTX charged
  8. Print pass/fail + recommended next steps

EXPECTED COST: ~0.001 IOTX (single recordAdjudication tx)

EXIT CODES:
  0  — canary fired successfully + on-chain verified + cost-as-expected
  1  — gate failure (refused to fire)
  2  — wallet balance insufficient
  3  — chain submission failed (tx reverted or RPC error)
  4  — verification failed (anchor not isRecorded post-tx)
  5  — cost over budget (>0.01 IOTX charged — investigate)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Make bridge package importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


COST_BUDGET_IOTX = 0.50
# Original 0.01 IOTX budget assumed ~1000 Gwei network gas + ~10k gas usage
# (a "naive Ethereum" estimate).  Phase 239 G3 GIC_100 reference (2026-05-06)
# used 160k gas at ~1000 Gwei = 0.160 IOTX.  At 2000 Gwei (May 9 measurement)
# the same anchor costs ~0.286 IOTX.  Budget set to 0.50 IOTX to allow
# headroom for gas spikes while still catching an order-of-magnitude
# anomaly (e.g. wrong contract / accidental loop / fee-market override).
# Adjust upward only if IoTeX testnet gas price climbs persistently above
# 4000 Gwei.


def _check_gates() -> tuple[bool, str]:
    """Verify all three authorization gates aligned.  Returns (ok, reason)."""
    pause_env = os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower()
    if pause_env != "false":
        return False, (
            "Gate 1 FAILED: CHAIN_SUBMISSION_PAUSED is not 'false' in this "
            "process env.  Set CHAIN_SUBMISSION_PAUSED=false in the SHELL "
            "(not bridge/.env) before running."
        )
    canary_env = os.environ.get("CORPUS_SNAPSHOT_CANARY_AUTHORIZED", "").strip().lower()
    if canary_env != "true":
        return False, (
            "Gate 2 FAILED: CORPUS_SNAPSHOT_CANARY_AUTHORIZED is not 'true'.  "
            "Operator must affirmatively set this intent flag in the shell "
            "to confirm the canary action.  Defensive layer prevents accidental "
            "anchor submissions."
        )
    return True, "all 3 gates aligned"


async def _run() -> int:
    print("=" * 72)
    print("Phase 238 Session 1 — CORPUS-SNAPSHOT canary anchor smoke-test")
    print("=" * 72)
    print()

    # ── Gate verification (no chain calls until gates pass) ─────────────
    ok, reason = _check_gates()
    if not ok:
        print(f"  ABORT: {reason}")
        print()
        return 1

    print(f"  Gates: {reason}")

    # ── Late imports so gate-fail short-circuits before module load ─────
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.store import Store
    from bridge.vapi_bridge.chain import ChainClient

    cfg = Config()
    store = Store(cfg.db_path)

    # Sanity: cfg sees pause=False (Config reads env at construction)
    if getattr(cfg, "chain_submission_paused", True) is not False:
        print("  ABORT: Config.chain_submission_paused did NOT pick up env override.")
        print("         Verify CHAIN_SUBMISSION_PAUSED=false is in THIS process env.")
        return 1
    print(f"  cfg.chain_submission_paused = False (kill-switch lifted for canary)")

    # ── Read wallet balance pre-tx ──────────────────────────────────────
    chain = ChainClient(cfg)
    if chain._account is None:
        print("  ABORT: bridge wallet not loaded (chain._account is None)")
        return 2

    wallet_addr = chain._account.address
    print(f"  Wallet: {wallet_addr}")

    bal_before_wei = await chain._w3.eth.get_balance(wallet_addr)
    bal_before_iotx = bal_before_wei / 1e18
    print(f"  Balance before: {bal_before_iotx:.6f} IOTX")

    # Report current network gas price so operator sees economics upfront
    try:
        gas_price_wei = await chain._w3.eth.gas_price
        gas_price_gwei = gas_price_wei / 1e9
        print(f"  Network gas price: {gas_price_gwei:.0f} Gwei")
        # Estimated cost ceiling: 200k gas × current gas price
        est_cost = 200_000 * gas_price_wei / 1e18
        print(f"  Estimated anchor cost (200k gas): ~{est_cost:.3f} IOTX")
    except Exception as exc:
        print(f"  WARN: gas price probe failed (non-fatal): {exc}")

    if bal_before_iotx < 0.05:
        print(f"  ABORT: balance {bal_before_iotx:.6f} < 0.05 IOTX safety floor")
        return 2

    # ── Pick canary row from corpus_snapshot_log ────────────────────────
    history = store.get_corpus_snapshot_history(limit=50)
    pending = [row for row in history if not row.get("on_chain_confirmed")]
    print(f"  Pending corpus_snapshot rows (unanchored): {len(pending)}")

    if not pending:
        print("  No unanchored corpus_snapshot rows found.  Nothing to canary-anchor.")
        print("  This is OK if all prior CORPUS-SNAPSHOTs already on-chain.")
        print("  Recommend running force-corpus-snapshot first to create one,")
        print("  or skip the canary and proceed directly to Step H deploy.")
        return 0

    # Take the OLDEST unanchored row (deterministic + reproducible)
    target = sorted(pending, key=lambda r: int(r.get("ts_ns", 0)))[0]
    snapshot_commitment_hex = target["snapshot_commitment"]
    target_id = target["id"]
    print(f"  Canary target row id={target_id}")
    print(f"     commitment: {snapshot_commitment_hex[:32]}...")
    print(f"     trigger:    {target.get('trigger_reason', '')[:60]}")

    # ── Fire the anchor ──────────────────────────────────────────────────
    print()
    print("  Firing chain.anchor_corpus_snapshot...")
    try:
        tx_hash, anchored = await chain.anchor_corpus_snapshot(snapshot_commitment_hex)
    except Exception as exc:
        print(f"  CHAIN ERROR: {exc}")
        return 3

    if not anchored or not tx_hash:
        print(f"  ANCHOR FAILED: anchored={anchored} tx_hash={tx_hash}")
        return 3

    print(f"  tx_hash: {tx_hash}")

    # ── Verify on-chain ──────────────────────────────────────────────────
    print()
    print("  Verifying via chain.is_adjudication_recorded...")
    is_recorded = await chain.is_adjudication_recorded(snapshot_commitment_hex)
    if not is_recorded:
        print(f"  VERIFY FAILED: isRecorded({snapshot_commitment_hex[:16]}...) = False")
        print("  Tx mined but anchor not visible on AdjudicationRegistry.  Investigate.")
        return 4

    print(f"  on-chain verified: isRecorded = True")

    # ── Cost accounting ──────────────────────────────────────────────────
    bal_after_wei = await chain._w3.eth.get_balance(wallet_addr)
    bal_after_iotx = bal_after_wei / 1e18
    cost_iotx = bal_before_iotx - bal_after_iotx

    print()
    print(f"  Balance after:  {bal_after_iotx:.6f} IOTX")
    print(f"  Canary cost:    {cost_iotx:.6f} IOTX")

    if cost_iotx > COST_BUDGET_IOTX:
        print(f"  COST OVERAGE: {cost_iotx:.6f} > {COST_BUDGET_IOTX:.6f} budget")
        print("  Investigate before proceeding to Session 1 main deploys.")
        return 5

    # ── Update local row with on_chain_confirmed=True ────────────────────
    try:
        with store._conn() as conn:
            conn.execute(
                "UPDATE corpus_snapshot_log SET on_chain_confirmed = 1, tx_hash = ? "
                "WHERE id = ?",
                (str(tx_hash), int(target_id)),
            )
        print(f"  Local row id={target_id} marked on_chain_confirmed=True")
    except Exception as exc:
        print(f"  WARN: local row update failed (non-fatal): {exc}")

    # ── Final summary ────────────────────────────────────────────────────
    print()
    print("  " + "=" * 70)
    print("  CANARY PASS — kill-switch flip + chain path verified clean")
    print("  " + "=" * 70)
    print()
    print(f"    Cost:           {cost_iotx:.6f} IOTX  (budget {COST_BUDGET_IOTX})")
    print(f"    Wallet remaining: {bal_after_iotx:.6f} IOTX")
    print(f"    On-chain anchor: {tx_hash}")
    print()
    print("  Session 1 NEXT STEPS (operator authorizes each):")
    print("  ────────────────────────────────────────────────")
    print("    1. cd contracts && npx hardhat run scripts/deploy-phase238-step-h.js \\")
    print("         --network iotex_testnet")
    print("    2. python -m bridge.scripts.curator_session_register --step 6")
    print("    3. python -m bridge.scripts.curator_session_register --step 7")
    print("    4. python -m bridge.scripts.curator_session_register --step 8")
    print("    5. python -m bridge.scripts.curator_session_register --step 9")
    print("    6. python -m bridge.scripts.curator_session_register --step 10")
    print("    7. POST /operator/anchor-cedar-bundle (operational + governance)")
    print("    8. Set CURATOR_REVIEW_ENABLED=true in bridge/.env + restart bridge")
    print()
    print("  After Session 1 complete, RESTORE safety posture:")
    print("    - Bridge config CHAIN_SUBMISSION_PAUSED=true (already true in")
    print("      bridge/.env file; this canary used process-scoped override only)")
    print()
    return 0


def _main_cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm", action="store_true",
        help="Third-layer authorization. Required to actually fire tx.",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("  DRY RUN: --confirm flag absent.  No on-chain operation.")
        print("  Re-run with --confirm to fire the canary anchor.")
        return 0

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(_main_cli())
