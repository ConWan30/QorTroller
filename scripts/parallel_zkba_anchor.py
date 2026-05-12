"""Phase O3-ZKBA-TRACK1 Track 2 C8 — Parallel ZKBA Cedar v2 Bundle Anchor.

Mirrors scripts/parallel_o2_anchor.py (the precedent triple-gate anchor
script for Phase O1-FRR-PARALLEL parallel-fleet O2 SUGGEST graduation)
applied to the ZKBA Cedar v2 bundles shipped at C6 (commit 755fac33).

Plan §6 A4 / Operator Decision Matrix D-TRACK2-C8: re-anchor the three
Cedar v2 bundles via parallel-fleet dual-anchor pattern (each agent
gets ONE operational + ONE governance anchor via cedar_bundle_anchor).

  Sentry v2:   Merkle 0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23
  Guardian v2: Merkle 0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0
  Curator v2:  Merkle 0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d

Three-gate authorization (operator runtime; not git authorization):

  Gate 1: env CHAIN_SUBMISSION_PAUSED=false in this process shell
          (NOT bridge/.env — the file is the kill-switch; the env-var
          override above it is the operator's deliberate lift)
  Gate 2: env OPERATOR_ZKBA_ANCHOR_AUTHORIZED=true in this process shell
          (DIFFERENT env-var-name than OPERATOR_INITIATIVE_O2_AUTHORIZED;
          intentional to prevent residual O2 authorization in shell
          history from accidentally satisfying ZKBA intent gate —
          defense-in-depth against carry-over)
  Gate 3: --confirm CLI flag

Cost budget: ~0.23 IOTX (3 bundles × dual anchor at current testnet gas
~0.04 IOTX per tx; total 6 txs × 0.04 = 0.24 + 25% safety margin = 0.30).
Safety floor: SAFETY_FLOOR_IOTX = 0.50 IOTX wallet minimum.

Track 1 invariant (anchor_tx_hash IS NULL on zkba_artifact_log) is
NOT affected by this script — bundle anchoring is at the AgentScope/
AgentRegistry layer, not the artifact-anchor layer. Artifact-level
anchoring is a separate operator-authorized flow that calls
chain.anchor_zkba_artifact() per artifact.

This script is OPERATOR-RUNTIME only. The CI / test environment does
NOT have the env vars set (Gate 1 + Gate 2 will fail), so the script
short-circuits before any RPC call when run from CI.

Exit codes:
  0  Success — all three v2 bundles dual-anchored
  1  Gate failure (env vars or --confirm missing)
  2  Pre-flight validation failure (bundles missing / invalid)
  3  Wallet balance below SAFETY_FLOOR_IOTX
  4  FSCA HIGH/CRITICAL contradiction active (operator must investigate)
  5  Anchor failure (one or more txs reverted; partial state may exist)

Author: VAPI Architect (bridge wallet 0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692)
Date: 2026-05-12 (Phase O3-ZKBA-TRACK1 Track 2 C7 script; C8 fires it)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Constants — bundle anchor order + filenames + cost guards
# ---------------------------------------------------------------------------

COST_BUDGET_IOTX = 0.30      # 6 txs × 0.04 + 25% margin
SAFETY_FLOOR_IOTX = 0.50     # wallet minimum before script proceeds

# Anchor order matches parallel_o2_anchor.py for activation_log ordering
# invariant; the order does NOT influence Cedar bundle Merkle roots.
AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")

AGENT_BUNDLE_FILES = {
    "anchor_sentry": "anchor_sentry_o2_suggest_v2.json",
    "guardian":      "guardian_o2_suggest_v2.json",
    "curator":       "curator_o2_suggest_v2.json",
}

# Merkle roots locked at C6 ship (commit 755fac33). The script
# verifies these match the parsed bundle Merkle roots before firing
# any anchor tx; any drift means a bundle file changed between C6
# and ceremony time, which MUST be operator-investigated.
EXPECTED_MERKLES = {
    "anchor_sentry": "0x39e8b65f0a87671fc003c28c3f28a7afd7fae41b6c3505d1ddb3d05ff3db1f23",
    "guardian":      "0x6818a9ad49dab7898925e530526c50fcce515a889c3666f1434e6470c660a9a0",
    "curator":       "0x0ade0c92cf2aa0c5675701861ed535683f0dfd15873424a9838d402b60a80b3d",
}


def _check_gates() -> tuple[bool, str]:
    """Verify Gates 1 + 2 + 3 aligned. Returns (ok, reason)."""
    pause_env = os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower()
    if pause_env != "false":
        return False, (
            "Gate 1 FAILED: CHAIN_SUBMISSION_PAUSED is not 'false' in this "
            "process env. Set CHAIN_SUBMISSION_PAUSED=false in the SHELL "
            "(NOT bridge/.env) before running."
        )
    intent_env = os.environ.get(
        "OPERATOR_ZKBA_ANCHOR_AUTHORIZED", ""
    ).strip().lower()
    if intent_env != "true":
        return False, (
            "Gate 2 FAILED: OPERATOR_ZKBA_ANCHOR_AUTHORIZED is not 'true'. "
            "Operator must affirmatively set this intent flag in the shell "
            "to confirm the ZKBA Cedar v2 bundle re-anchoring ceremony. "
            "Defense-in-depth against accidental cross-context anchor "
            "(O2_SUGGEST anchor reuses OPERATOR_INITIATIVE_O2_AUTHORIZED; "
            "ZKBA uses its OWN env-var name to prevent residual carry-over)."
        )
    return True, "Gates 1 + 2 aligned"


def _verify_bundle_merkles(
    bundle_dir: Path,
) -> tuple[bool, str, dict[str, str]]:
    """Pre-flight: load + parse each bundle + verify Merkle matches
    EXPECTED_MERKLES locked at C6 ship.

    Returns (ok, reason, computed_merkles)."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "bridge"))
        from vapi_bridge.cedar_parser import parse_bundle  # type: ignore
    except Exception as exc:
        return False, f"cedar_parser import failed: {exc}", {}

    computed: dict[str, str] = {}
    for agent_id in AGENT_ANCHOR_ORDER:
        fname = AGENT_BUNDLE_FILES[agent_id]
        path = bundle_dir / fname
        if not path.exists():
            return False, f"Bundle missing: {path}", computed
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            parsed = parse_bundle(raw)
        except Exception as exc:
            return False, f"Bundle parse failed for {fname}: {exc}", computed
        if parsed.phase != "O2_SUGGEST":
            return False, (
                f"Bundle {fname} phase={parsed.phase} (expected O2_SUGGEST)"
            ), computed
        merkle_b = parsed.merkle_root
        merkle_hex = (
            "0x" + merkle_b.hex()
            if isinstance(merkle_b, (bytes, bytearray))
            else str(merkle_b)
        )
        computed[agent_id] = merkle_hex
        expected = EXPECTED_MERKLES[agent_id]
        if merkle_hex.lower() != expected.lower():
            return False, (
                f"Merkle DRIFT for {agent_id}: expected {expected}, "
                f"got {merkle_hex}. Bundle file modified between C6 ship "
                f"and ceremony — operator MUST investigate before "
                f"proceeding (likely: re-verify v2 bundle content was "
                f"not edited post-C6 commit 755fac33)."
            ), computed
    return True, "All three Merkle roots match EXPECTED_MERKLES", computed


async def _run(args: argparse.Namespace) -> int:
    """Main async entry — runs after gate verification + --confirm."""
    print("=" * 78)
    print("Phase O3-ZKBA-TRACK1 Track 2 — Parallel ZKBA Cedar v2 Bundle Anchor")
    print("=" * 78)
    print()

    # ── Gates 1 + 2 ----------------------------------------------------─
    ok, reason = _check_gates()
    if not ok:
        print(f"  ABORT: {reason}")
        return 1
    print(f"  Gates 1 + 2: {reason}")

    if not args.confirm:
        print(
            "  ABORT: Gate 3 FAILED — --confirm CLI flag not passed.\n"
            "         The three-factor authorization requires all three:\n"
            "           env CHAIN_SUBMISSION_PAUSED=false\n"
            "           env OPERATOR_ZKBA_ANCHOR_AUTHORIZED=true\n"
            "           --confirm CLI flag"
        )
        return 1
    print(f"  Gate 3: --confirm CLI flag present")

    # ── Pre-flight: verify Merkle roots --------------------------------─
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    ok, reason, computed = _verify_bundle_merkles(bundle_dir)
    if not ok:
        print(f"  ABORT: {reason}")
        return 2
    print(f"  Pre-flight Merkle verification: {reason}")
    for agent_id, merkle in computed.items():
        print(f"    {agent_id:<14s}  {merkle[:16]}...{merkle[-8:]}")

    # ── Late imports so gate-fail short-circuits before module load ----─
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.store import Store
    from bridge.vapi_bridge.chain import ChainClient
    from bridge.vapi_bridge.cedar_bundle_anchor import CedarBundleAnchor

    cfg = Config()
    if getattr(cfg, "chain_submission_paused", True) is not False:
        print(
            "  ABORT: Config.chain_submission_paused did NOT pick up env "
            "override. Verify CHAIN_SUBMISSION_PAUSED=false is in THIS "
            "process env."
        )
        return 1
    print(f"  cfg.chain_submission_paused = False (kill-switch lifted)")

    # ── Wallet balance check ------------------------------------------─
    store = Store(cfg.db_path)
    try:
        chain = ChainClient(cfg, store)
        balance_wei = await chain._w3.eth.get_balance(chain._account.address)
        balance_iotx = balance_wei / 10**18
        print(f"  Wallet balance: {balance_iotx:.4f} IOTX")
        if balance_iotx < SAFETY_FLOOR_IOTX:
            print(
                f"  ABORT: Wallet balance {balance_iotx:.4f} below SAFETY "
                f"FLOOR {SAFETY_FLOOR_IOTX} IOTX. Operator must refill "
                f"before re-running."
            )
            return 3
        if balance_iotx < COST_BUDGET_IOTX:
            print(
                f"  WARNING: balance {balance_iotx:.4f} below COST BUDGET "
                f"{COST_BUDGET_IOTX} — ceremony may run out of gas mid-way"
            )
    except Exception as exc:
        print(f"  ABORT: wallet balance check failed: {exc}")
        return 3

    if args.dry_run:
        print("\n  DRY-RUN MODE — would fire 6 anchor txs (3 bundles × dual)")
        for agent_id in AGENT_ANCHOR_ORDER:
            print(f"    {agent_id}: operational + governance anchor with "
                  f"Merkle {computed[agent_id][:16]}...")
        print("\n  Exit 0 (dry-run; no chain action)")
        return 0

    # ── Ceremony fires here -----------------------------------------------
    anchor = CedarBundleAnchor(cfg, store, chain)
    print()
    print("  → Firing parallel ZKBA Cedar v2 ceremony (6 dual-anchor txs)")
    print()

    successes: list[str] = []
    failures: list[tuple[str, str]] = []
    for agent_id in AGENT_ANCHOR_ORDER:
        bundle_path = bundle_dir / AGENT_BUNDLE_FILES[agent_id]
        print(f"  [{agent_id}] anchoring v2 bundle {AGENT_BUNDLE_FILES[agent_id]}")
        try:
            # CedarBundleAnchor.anchor_bundle() handles dual-anchor
            # (operational FIRST + governance SECOND) per
            # INV-OPERATOR-AGENT-001
            result = await anchor.anchor_bundle(
                str(bundle_path),
                reason=f"Track 2 C8 ZKBA Cedar v2 bundle ceremony for {agent_id}",
            )
            if result and getattr(result, "operational_tx_hash", None):
                print(
                    f"    op_tx:  {result.operational_tx_hash[:18]}...\n"
                    f"    gov_tx: {getattr(result, 'governance_tx_hash', '?')[:18]}..."
                )
                successes.append(agent_id)
            else:
                print(f"    FAIL: anchor_bundle returned no tx hashes")
                failures.append((agent_id, "no tx hashes returned"))
                # Atomic stop — do NOT proceed to next agent
                break
        except Exception as exc:
            print(f"    FAIL: {exc}")
            failures.append((agent_id, str(exc)[:100]))
            break

    print()
    print(f"  Ceremony result: {len(successes)}/3 successes, {len(failures)}/3 failures")
    if failures:
        for agent_id, msg in failures:
            print(f"    FAIL [{agent_id}]: {msg}")
        print(
            "  ABORT: Partial state may exist on chain. Operator must "
            "inspect activation_log + AgentScope/AgentRegistry views to "
            "determine which dual-anchors landed before re-running."
        )
        return 5

    print("  All three Cedar v2 bundles dual-anchored.")
    print("  ZKBA Track 2 C8 ceremony COMPLETE.")
    return 0


def _main_cli() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase O3-ZKBA-TRACK1 Track 2 C8 ceremony — parallel-fleet "
            "ZKBA Cedar v2 bundle dual-anchor. Operator three-factor "
            "authorization required: env CHAIN_SUBMISSION_PAUSED=false + "
            "env OPERATOR_ZKBA_ANCHOR_AUTHORIZED=true + --confirm flag."
        )
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Third authorization factor (Gate 3). Required to fire anchors.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Verify gates + Merkle roots + wallet balance, then exit without "
            "firing any anchor tx. Safe to run from CI."
        ),
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(_main_cli())
