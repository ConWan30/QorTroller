"""Phase O3-ACT-WATCHER -- Parallel Operator Initiative O3 ACTING anchor.

Sibling of `scripts/parallel_o2_anchor.py` (Phase O1-FRR Stream E). Atomically
advances all three Operator Initiative agents (Sentry + Guardian + Curator)
from O2_SUGGEST to O3_ACTING in a single ship. Honors the parallel-fleet
invariant established by Phase O1 D: the three agents MUST be at the same
phase at all times. This script either advances all three or none.

DESIGN -- QUADRUPLE-GATE AUTHORIZATION (one stricter than the O2 sibling
because O3 ACT is irreversible at the policy-active level: real on-chain
writes start firing the moment the bundles anchor):

  Gate 1: env CHAIN_SUBMISSION_PAUSED=false        (process-scope only;
          bridge/.env file remains true so the next bridge restart
          re-engages safety posture)
  Gate 2: env OPERATOR_INITIATIVE_O3_AUTHORIZED=true  (intent gate;
          operator must explicitly set in shell -- distinct env var
          from O2 to prevent residual O2 authorization carrying over)
  Gate 3: --confirm CLI flag                       (third-layer auth)
  Gate 4: ALL THREE AGENTS' o3_ready=True per      (watcher veto -- the
          evaluate_fleet_advancement_sync()         O3 readiness gates
                                                    enforce 504h shadow
                                                    age + 50 drafts +
                                                    <5% disagreement +
                                                    dual-key + KMS HSM /
                                                    GitHub-App / setCurator
                                                    role / 0% false-
                                                    positive rate per
                                                    agent's _o3_gates
                                                    field)

  All four gates must align before any tx is fired.  Any failing gate ->
  graceful exit with descriptive message.

USAGE:
  PowerShell:
    $env:CHAIN_SUBMISSION_PAUSED="false"
    $env:OPERATOR_INITIATIVE_O3_AUTHORIZED="true"
    python scripts/parallel_o3_act_anchor.py --confirm

  Bash:
    CHAIN_SUBMISSION_PAUSED=false \
      OPERATOR_INITIATIVE_O3_AUTHORIZED=true \
      python scripts/parallel_o3_act_anchor.py --confirm

  After this shell exits, env vars vanish -- bridge/.env is unchanged.

WHAT IT DOES (mirrors parallel_o2_anchor.py with O3-specific additions):
  1. Verify all four gates aligned (incl. watcher veto on per-agent o3_ready).
  2. Read wallet balance + network gas price (read-only RPC).
  3. Validate all three O3 ACTING bundles (parse + Merkle round-trip;
     bundle phase MUST equal "O3_ACTING").
  4. Compute the EXPECTED post-anchor FRR locally (every agent at
     phase_code=PHASE_CODE_O3_ACT) and print to operator for visual
     confirmation. Operator can compare against the locked Merkle roots
     from Phase O3-ACT-DRAFT (commit 3cb59f46).
  5. For each agent in [anchor_sentry, guardian, curator] (fixed order):
       a. Anchor the bundle (operational FIRST, governance SECOND
          per INV-OPERATOR-AGENT-001).
       b. STOP if either operational or governance leg reverts -- partial
          state is recoverable but parallel atomicity is broken.
  6. After all 6 txs land, recompute FRR from updated activation_log and
     verify match against pre-anchor expectation.
  7. Insert a single advancement_log row with frr_hex + fleet_phase_aligned=True.
  8. Read wallet balance after; report cost.

EXIT CODES (mirror parallel_o2_anchor.py):
  0  -- all three agents advanced; FRR verified; advancement_log written
  1  -- gate failure (refused to fire; quadruple-gate failed)
  2  -- wallet balance / pre-flight failure
  3  -- bundle validation failed
  4  -- anchor partial failure (operator MUST inspect activation_log)
  5  -- post-anchor FRR mismatch (advancement_log NOT written; investigate)
  6  -- cost overage
  7  -- watcher veto (gate 4): one or more agents NOT o3_ready

SECURITY NOTE for Curator on mainnet:
  Sessions 1+2+3 (2026-05-09) activated Curator at O1_SHADOW with
  MockKMSClient on testnet. Mainnet O3_ACTING anchor requires AWS KMS
  HSM provisioning per wiki/runbooks/curator_mainnet_migration.md.
  This script does NOT distinguish testnet vs mainnet; the operator's
  cfg.kms_hsm_production_ready flag is the single source of truth at
  invocation time. For testnet O3 anchor, that flag may be set True
  with MockKMSClient backing per Sessions 1+2+3 precedent. For mainnet,
  it MUST be backed by AWS KMS HSM.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Make bridge package importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# Cost budget = 6 txs * ~0.30 IOTX/tx (worst case at 4000 Gwei) + 50% margin.
# Same shape as O2 sibling -- gas profile is identical (storage-heavy
# AgentScope.setAgentScopeRoot + AgentRegistry.updateAgentScope writes).
COST_BUDGET_IOTX = 3.0
SAFETY_FLOOR_IOTX = 0.50  # operator wallet must have at least this much


# Fixed agent order -- matches activation_log ordering.  The order itself
# does NOT influence FRR (FRR sorts by agent_id bytes).
AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")

AGENT_BUNDLE_FILES = {
    "anchor_sentry": "anchor_sentry_o3_acting_v1.json",
    "guardian":      "guardian_o3_acting_v1.json",
    "curator":       "curator_o3_acting_v1.json",
}


def _check_gates() -> tuple[bool, str]:
    """Verify the first three authorization gates (env + CLI).

    Gate 4 (watcher veto on per-agent o3_ready) is checked separately
    inside _run() because it requires bridge module imports + store reads.
    """
    pause_env = os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower()
    if pause_env != "false":
        return False, (
            "Gate 1 FAILED: CHAIN_SUBMISSION_PAUSED is not 'false' in this "
            "process env.  Set CHAIN_SUBMISSION_PAUSED=false in the SHELL "
            "(not bridge/.env) before running."
        )
    intent_env = os.environ.get(
        "OPERATOR_INITIATIVE_O3_AUTHORIZED", ""
    ).strip().lower()
    if intent_env != "true":
        return False, (
            "Gate 2 FAILED: OPERATOR_INITIATIVE_O3_AUTHORIZED is not 'true'. "
            "Operator must affirmatively set this intent flag in the shell "
            "to confirm the parallel-fleet O3 ACTING advancement.  Distinct "
            "env var from O2's OPERATOR_INITIATIVE_O2_AUTHORIZED prevents "
            "residual O2 authorization from carrying over into O3."
        )
    return True, "gates 1+2 aligned (env-level)"


def _check_watcher_veto(actual_summary) -> tuple[bool, str, list]:
    """Gate 4 -- the per-agent watcher veto. Refuses to fire unless ALL
    THREE agents have o3_ready=True per the latest watcher evaluation.

    Returns (ok, message, blocker_dict_per_agent). blocker_dict_per_agent is
    a list of dicts so the caller can print blockers for each agent that
    failed.
    """
    blockers_per_agent: list = []
    all_ready = True
    for a in actual_summary.per_agent:
        if not a.o3_ready:
            all_ready = False
        blockers_per_agent.append({
            "agent_id": a.agent_id,
            "current_phase": a.current_phase,
            "o3_ready": a.o3_ready,
            "o3_blockers": list(a.o3_blockers),
        })
    if all_ready:
        return True, "Gate 4 PASS: all 3 agents o3_ready=True", blockers_per_agent
    return False, (
        "Gate 4 FAILED: at least one agent has o3_ready=False per the "
        "watcher.  Refusing to fire O3 ACTING anchor.  The _o3_gates "
        "criteria from the *_o3_acting_v1.json bundles must ALL pass per "
        "agent before the parallel anchor is authorized.  See per-agent "
        "blockers below."
    ), blockers_per_agent


async def _run(args: argparse.Namespace) -> int:
    print("=" * 76)
    print("Phase O3-ACT-WATCHER -- Parallel Operator Initiative O3 ACTING anchor")
    print("=" * 76)
    print()

    # -- Gates 1+2+3 (env + CLI) ----------------------------------------
    ok, reason = _check_gates()
    if not ok:
        print(f"  ABORT: {reason}")
        return 1
    print(f"  Gates 1+2+3: {reason}")
    if args.confirm:
        print(f"             gate 3 --confirm: PASS")
    else:
        print(f"             gate 3 --confirm: NOT SET (will dry-run)")

    # -- Late imports so gate-fail short-circuits before module load ----
    from bridge.vapi_bridge.config import Config
    from bridge.vapi_bridge.store import Store
    from bridge.vapi_bridge.chain import ChainClient
    from bridge.vapi_bridge.cedar_bundle_anchor import CedarBundleAnchor
    from bridge.vapi_bridge.cedar_parser import parse_bundle
    from bridge.vapi_bridge.operator_initiative_advancement import (
        compute_fleet_readiness_root,
        evaluate_fleet_advancement_sync,
        AgentAdvancementReadiness,
        FleetAdvancementSummary,
        PHASE_CODE_O3_ACT,
        FRR_DOMAIN_TAG,
    )

    cfg = Config()
    store = Store(cfg.db_path)

    # Sanity: cfg sees pause=False
    if getattr(cfg, "chain_submission_paused", True) is not False:
        print(
            "  ABORT: Config.chain_submission_paused did NOT pick up env "
            "override.  Verify CHAIN_SUBMISSION_PAUSED=false is in THIS "
            "process env."
        )
        return 1
    print(f"  cfg.chain_submission_paused = False (kill-switch lifted)")

    # -- Gate 4: watcher veto on per-agent o3_ready ---------------------
    pre_summary = evaluate_fleet_advancement_sync(cfg=cfg, store=store)
    g4_ok, g4_reason, g4_blockers = _check_watcher_veto(pre_summary)
    if not g4_ok:
        print(f"  ABORT: {g4_reason}")
        for b in g4_blockers:
            print(f"    [{b['agent_id']:<14s}] phase={b['current_phase']:<12s} "
                  f"o3_ready={b['o3_ready']}  blockers={b['o3_blockers']}")
        return 7
    print(f"  {g4_reason}")
    print()

    # -- Validate all three bundles BEFORE any chain call ---------------
    bundle_dir = Path(getattr(cfg, "cedar_bundle_dir", PROJECT_ROOT / "bridge/vapi_bridge/cedar_bundles"))
    bundle_paths: dict[str, Path] = {}
    bundle_merkles: dict[str, str] = {}
    for agent_id in AGENT_ANCHOR_ORDER:
        fname = AGENT_BUNDLE_FILES[agent_id]
        path = bundle_dir / fname
        if not path.exists():
            print(f"  ABORT: bundle missing: {path}")
            return 3
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            parsed = parse_bundle(raw)
        except Exception as exc:
            print(f"  ABORT: bundle parse failed for {fname}: {exc}")
            return 3
        if parsed.phase != "O3_ACTING":
            print(
                f"  ABORT: bundle {fname} has phase={parsed.phase}, "
                f"expected O3_ACTING"
            )
            return 3
        bundle_paths[agent_id] = path
        merkle_b = parsed.merkle_root
        merkle_hex = merkle_b.hex() if isinstance(merkle_b, (bytes, bytearray)) else str(merkle_b)
        bundle_merkles[agent_id] = merkle_hex
    print(f"  Bundles validated: {len(bundle_paths)}/3")
    for agent_id, merkle in bundle_merkles.items():
        print(f"    {agent_id:<14s}  Merkle 0x{merkle[:16]}...")

    # -- Pre-anchor FRR pre-image (expected post-anchor state) ----------
    expected_ts_ns = time.time_ns()
    synthetic_per_agent = tuple(
        AgentAdvancementReadiness(
            agent_id=agent_id,
            current_phase="O3_ACT",
            shadow_age_hours=0.0,
            cedar_eval_count=0,
            bundle_hash_drift_count_30d=0,
            scope_hash_governance_drift_count_30d=0,
            o2_ready=False,
            o2_blockers=("agent_phase_is_O3_ACT_not_O1_SHADOW",),
            o3_ready=True,
            o3_blockers=tuple(),
        )
        for agent_id in AGENT_ANCHOR_ORDER
    )
    synthetic_summary = FleetAdvancementSummary(
        timestamp=time.time(),
        fleet_size=3,
        fleet_at_o1_count=0,
        fleet_at_o2_ready_count=0,
        fleet_at_o3_ready_count=3,
        fleet_phase_aligned=True,
        next_alignment_target="O3_ACT",
        per_agent=synthetic_per_agent,
    )
    expected_frr = compute_fleet_readiness_root(
        synthetic_summary, cfg=cfg, ts_ns=expected_ts_ns,
    )
    if expected_frr.error:
        print(f"  ABORT: pre-anchor FRR compute failed: {expected_frr.error}")
        return 3
    print()
    print("  Expected post-anchor Fleet Readiness Root:")
    print(f"    domain_tag:  {FRR_DOMAIN_TAG.decode()}")
    print(f"    phase_code:  0x{PHASE_CODE_O3_ACT:02x}  (all three agents)")
    print(f"    ts_ns:       {expected_ts_ns}")
    print(f"    FRR (hex):   0x{expected_frr.frr_hex}")
    print()
    for name, id_hex, phase_code in expected_frr.agents:
        print(f"      {name:<14s}  agent_id 0x{id_hex[:16]}...  phase_code 0x{phase_code:02x}")
    print()

    # -- Read wallet balance --------------------------------------------
    chain = ChainClient(cfg)
    if chain._account is None:
        print("  ABORT: bridge wallet not loaded (chain._account is None)")
        return 2
    wallet_addr = chain._account.address
    bal_before_wei = await chain._w3.eth.get_balance(wallet_addr)
    bal_before_iotx = bal_before_wei / 1e18
    try:
        gas_price_wei = await chain._w3.eth.gas_price
        gas_price_gwei = gas_price_wei / 1e9
    except Exception:
        gas_price_wei = 0
        gas_price_gwei = 0.0
    # 6 txs * ~200k gas (storage-heavy, conservative) + 1.25 buffer
    est_per_tx_iotx = (200_000 * 1.25 * gas_price_wei) / 1e18 if gas_price_wei else 0.05
    est_total_iotx = est_per_tx_iotx * 6

    print(f"  Wallet:           {wallet_addr}")
    print(f"  Balance before:   {bal_before_iotx:.6f} IOTX")
    print(f"  Network gas:      {gas_price_gwei:.0f} Gwei")
    print(f"  Est. cost (6 tx): ~{est_total_iotx:.4f} IOTX (<={COST_BUDGET_IOTX} budget)")

    if bal_before_iotx < SAFETY_FLOOR_IOTX:
        print(
            f"  ABORT: balance {bal_before_iotx:.6f} < {SAFETY_FLOOR_IOTX} "
            f"safety floor"
        )
        return 2

    # -- Dry-run gate: --confirm absent -> exit cleanly here ------------
    if not args.confirm:
        print()
        print("  DRY RUN: --confirm flag absent.  No on-chain operation.")
        print("  Re-run with --confirm to fire the parallel anchor (6 txs).")
        return 0

    # -- Sequential dual-anchor for each agent --------------------------
    anchor = CedarBundleAnchor(chain=chain, store=store, bundle_dir=bundle_dir)
    print()
    print("  Firing parallel O3 ACTING anchor -- 6 txs in fixed order...")
    print()

    operator_authority_reason = (
        "Phase O3-ACT-WATCHER parallel-fleet O3 ACTING advancement "
        "(operator-authorized parallel anchor; "
        "all four gates passed including watcher veto on o3_ready=True; "
        "scripts/parallel_o3_act_anchor.py --confirm)"
    )

    anchor_results: list = []
    for agent_id in AGENT_ANCHOR_ORDER:
        bundle_path = bundle_paths[agent_id]
        bundle_filename = bundle_path.name
        print(f"  [{agent_id}] anchor_bundle({bundle_filename})...")
        try:
            result = await anchor.anchor_bundle(
                bundle_path=bundle_filename,
                operator_api_key=getattr(cfg, "operator_api_key", "") or "",
                reason_text=operator_authority_reason,
            )
        except Exception as exc:
            print(f"  [{agent_id}] ANCHOR FAILED (exception): {exc}")
            print(
                f"  STOP: parallel atomicity broken at agent {agent_id} -- "
                f"do NOT proceed to next agent.  Operator must inspect "
                f"operator_agent_activation_log for partial state."
            )
            return 4
        anchor_results.append((agent_id, result))
        op_tx = (result.operational_tx_hash or "")[:20]
        gov_tx = (result.governance_tx_hash or "")[:20]
        print(f"  [{agent_id}] op_tx={op_tx}...  gov_tx={gov_tx}...")
        if not result.success:
            print(
                f"  [{agent_id}] PARTIAL FAILURE: success=False  "
                f"error={result.error}"
            )
            print(
                f"  STOP: parallel atomicity broken at agent {agent_id} -- "
                f"do NOT proceed to next agent.  FSCA "
                f"SCOPE_HASH_GOVERNANCE_DRIFT_DETECTED will fire on next "
                f"15-min poll if governance leg reverted."
            )
            return 4

    # -- Post-anchor FRR verification -----------------------------------
    print()
    print("  All 6 txs landed.  Verifying post-anchor FRR...")
    actual_summary = evaluate_fleet_advancement_sync(cfg=cfg, store=store)
    actual_frr = compute_fleet_readiness_root(
        actual_summary, cfg=cfg, ts_ns=expected_ts_ns,
    )
    if actual_frr.error:
        print(f"  POST-ANCHOR FRR ERROR: {actual_frr.error}")
        return 5
    if actual_frr.frr_hex != expected_frr.frr_hex:
        print(
            f"  FRR MISMATCH:\n"
            f"    expected 0x{expected_frr.frr_hex}\n"
            f"    actual   0x{actual_frr.frr_hex}\n"
            f"  advancement_log NOT written.  Operator must investigate."
        )
        return 5
    print(f"  FRR verified: 0x{actual_frr.frr_hex}")

    if not actual_summary.fleet_phase_aligned:
        print(
            f"  WARN: actual_summary.fleet_phase_aligned={actual_summary.fleet_phase_aligned}"
        )

    # -- Persist advancement_log row ------------------------------------
    per_agent_json = json.dumps([
        {
            "agent_id": a.agent_id,
            "current_phase": a.current_phase,
            "shadow_age_hours": round(a.shadow_age_hours, 2),
            "cedar_eval_count": a.cedar_eval_count,
            "bundle_drift_30d": a.bundle_hash_drift_count_30d,
            "scope_drift_30d": a.scope_hash_governance_drift_count_30d,
            "o2_ready": a.o2_ready,
            "o2_blockers": list(a.o2_blockers),
            "o3_ready": a.o3_ready,
            "o3_blockers": list(a.o3_blockers),
            "error": a.error,
        }
        for a in actual_summary.per_agent
    ], separators=(",", ":"))

    try:
        row_id = store.insert_operator_initiative_advancement_log(
            timestamp=actual_summary.timestamp,
            fleet_phase_aligned=bool(actual_summary.fleet_phase_aligned),
            fleet_at_o1_count=actual_summary.fleet_at_o1_count,
            fleet_at_o2_ready_count=actual_summary.fleet_at_o2_ready_count,
            fleet_at_o3_ready_count=actual_summary.fleet_at_o3_ready_count,
            next_alignment_target=actual_summary.next_alignment_target,
            per_agent_json=per_agent_json,
            frr_hex=actual_frr.frr_hex,
            frr_ts_ns=actual_frr.ts_ns,
            error=actual_summary.error,
        )
        print(f"  advancement_log row id={row_id} written")
    except Exception as exc:
        print(f"  WARN: advancement_log insert failed (non-fatal): {exc}")

    # -- Cost accounting ------------------------------------------------
    bal_after_wei = await chain._w3.eth.get_balance(wallet_addr)
    bal_after_iotx = bal_after_wei / 1e18
    cost_iotx = bal_before_iotx - bal_after_iotx
    print()
    print(f"  Balance after:    {bal_after_iotx:.6f} IOTX")
    print(f"  Total cost:       {cost_iotx:.6f} IOTX  (budget {COST_BUDGET_IOTX})")

    if cost_iotx > COST_BUDGET_IOTX:
        print(f"  COST OVERAGE: {cost_iotx:.6f} > {COST_BUDGET_IOTX}")
        return 6

    # -- Final summary --------------------------------------------------
    print()
    print("  " + "=" * 74)
    print("  PARALLEL O3 ACTING ANCHOR COMPLETE -- fleet aligned at O3_ACT")
    print("  " + "=" * 74)
    print()
    print(f"    FRR:      0x{actual_frr.frr_hex}")
    print(f"    Wallet:   {bal_after_iotx:.6f} IOTX (cost {cost_iotx:.6f})")
    print()
    print("  Next steps (operator-gated):")
    print("    1. Verify on-chain: GET /operator/operator-agent-activation-log")
    print("       (latest row per agent shows phase=O3_ACTING bundle anchored)")
    print("    2. Confirm FSCA fleet_coherence quiet (no drift findings within 15 min)")
    print("    3. RESTORE safety posture: ensure bridge/.env still has")
    print("         CHAIN_SUBMISSION_PAUSED=true (script used process-scoped override)")
    print("    4. Phase O1 D advancement watcher resumes monitoring at 1h cadence;")
    print("       next_alignment_target=O3_ACT now reflects fleet at terminal phase")
    print("    5. Live O3 capabilities now active per *_o3_acting_v1.json bundles:")
    print("       Sentry  -- pda-attestation-anchor on lane://provenance/**")
    print("       Guardian -- audit-drafting on lane://audits/**")
    print("       Curator -- marketplace-listing-suspend on chain://iotex-testnet")
    print()
    return 0


def _main_cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm", action="store_true",
        help="Third-layer authorization. Required to actually fire txs.",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(_main_cli())
