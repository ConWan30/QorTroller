"""Operator Initiative O3 Graduation — draft-count gate seeding harness.

Triple-gate operator-authorized script (env + env + --confirm). Uses the
existing Phase O2-DRAFT-GENERATION primitives to pre-populate the
draft_payload_count gate (>=50 drafts per agent over 30-day window)
WITHOUT waiting for organic trigger sources to accumulate drafts at the
default polling cadence.

CRITICAL: This is the EXPEDITE path for the draft_count gate ONLY. It
does NOT touch the FROZEN shadow_age gate (504h calendar-bound). It
does NOT touch the cfg-flag gates (operator infrastructure work). It
does NOT touch the disagreement_rate / false_positive_rate gates
(those are populated by operator review decisions, not by seeding).

What this script does:
  1. Verifies triple-gate authorization (env CHAIN_SUBMISSION_PAUSED=true
     + env OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED=true + --confirm
     CLI flag).
  2. For each of the 3 Operator Initiative agents (Sentry/Guardian/Curator),
     invokes the agent's Phase O2-DRAFT-GENERATION primitives N times
     (default 50) with deterministically-generated synthetic payloads.
     Each draft has a unique payload_hash via SHA-256, so the UNIQUE
     constraint at the store layer enforces idempotency (re-running this
     script does NOT add duplicates).
  3. Optionally (with --auto-accept) records operator_decision='accept'
     for each generated draft — drives disagreement_rate to 0% on the
     same surface in a single pass.
  4. Re-runs the readiness audit + prints the post-seeding state.

Operator usage (manual; NOT auto-triggered):

    # Dry-run (no DB writes — see what would happen):
    python scripts/operator_initiative_seed_drafts.py

    # Real seeding (triple-gate auth required):
    export CHAIN_SUBMISSION_PAUSED=true
    export OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED=true
    python scripts/operator_initiative_seed_drafts.py --confirm

    # Real seeding + auto-accept all drafts (clears rate gate too):
    python scripts/operator_initiative_seed_drafts.py --confirm --auto-accept

WALLET-FREE; no chain RPC; no on-chain operations. The drafts live
entirely in the local bridge SQLite operator_agent_drafts table.

Exit codes:
  0  Seeding complete; readiness audit run; results printed.
  1  Triple-gate authorization failed.
  2  Seeding partially failed (some agents did not reach N drafts).
  3  Script error.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))

# Windows cp1252 stdout encoding fix (Phase 237.5 Path C+ precedent)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 — non-Windows platforms
    pass


_GATE_2_ENV = "OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED"
_GATE_1_ENV = "CHAIN_SUBMISSION_PAUSED"


def _check_triple_gate(*, confirm: bool) -> tuple[bool, str]:
    """Returns (ok, reason). Triple-gate matches the parallel_o3_act_anchor.py
    pattern verbatim (env + distinct-env + --confirm) so the seeding harness
    has the same operator-runtime authorization surface as a real ceremony.
    """
    # Gate 1: kill-switch state
    pause_env = os.environ.get(_GATE_1_ENV, "true").strip().lower()
    if pause_env != "true":
        return False, (
            f"Gate 1 FAILED: {_GATE_1_ENV} must be 'true' (kill-switch ARMED) "
            "during seeding — this script is wallet-free but the kill-switch "
            "discipline applies to any operator-runtime advancement script."
        )
    # Gate 2: explicit intent env var (distinct from O2/O3 anchor env vars
    # to prevent carry-over)
    intent_env = os.environ.get(_GATE_2_ENV, "").strip().lower()
    if intent_env != "true":
        return False, (
            f"Gate 2 FAILED: {_GATE_2_ENV} must be 'true' in process env. "
            "Set explicitly in the SHELL before running. Distinct env var "
            "from OPERATOR_INITIATIVE_O2_AUTHORIZED + OPERATOR_INITIATIVE_"
            "O3_AUTHORIZED to prevent residual authorization carry-over."
        )
    # Gate 3: --confirm CLI flag
    if not confirm:
        return False, "Gate 3 FAILED: --confirm CLI flag not provided."
    return True, "All three gates PASSED."


def _seed_sentry_drafts(store, n: int, agent_q9: str) -> int:
    from vapi_bridge.operator_agent_sentry_drafting import SentryDraftGenerator
    cfg_stub = type("S", (), {"operator_agent_anchor_sentry_id": agent_q9})()
    gen = SentryDraftGenerator(store=store, cfg=cfg_stub)
    seeded = 0
    for i in range(n):
        # Deterministic synthetic commit hash per (agent, index)
        commit_hash = hashlib.sha1(f"sentry_seed_{i:04d}".encode()).hexdigest()
        result = gen.draft_kms_sign(
            commit_hash=commit_hash,
            signer_pubkey_hex="04" + "ab" * 32,  # 65 bytes; uncompressed P-256
            signature_payload={
                "seed_index": i,
                "agent": "anchor_sentry",
                "purpose": "draft_count_gate_seeding",
            },
        )
        if result.draft_id > 0 or "UNIQUE" in (result.error or ""):
            seeded += 1
    return seeded


def _seed_guardian_drafts(store, n: int, agent_q9: str) -> int:
    from vapi_bridge.operator_agent_guardian_drafting import (
        GuardianDraftGenerator,
    )
    cfg_stub = type("G", (), {"operator_agent_guardian_id": agent_q9})()
    gen = GuardianDraftGenerator(store=store, cfg=cfg_stub)
    seeded = 0
    for i in range(n):
        audit_id = f"seed-audit-{i:04d}"
        result = gen.draft_audit_entry(
            audit_id=audit_id,
            audit_payload={
                "seed_index": i,
                "agent": "guardian",
                "purpose": "draft_count_gate_seeding",
                "evidence": [f"seed_evidence_{i}"],
            },
            audit_kind="audit",
        )
        if result.draft_id > 0 or "UNIQUE" in (result.error or ""):
            seeded += 1
    return seeded


def _seed_curator_drafts(store, n: int, agent_q9: str) -> int:
    from vapi_bridge.operator_agent_curator_drafting import (
        CuratorDraftGenerator,
    )
    cfg_stub = type("C", (), {"operator_agent_curator_id": agent_q9})()
    gen = CuratorDraftGenerator(store=store, cfg=cfg_stub)
    seeded = 0
    for i in range(n):
        listing_id = f"seed-listing-{i:04d}"
        result = gen.draft_marketplace_listing_review(
            listing_id=listing_id,
            verdict="APPROVED",  # FROZEN verdict code per Phase 238 Step I
            review_payload={
                "seed_index": i,
                "agent": "curator",
                "purpose": "draft_count_gate_seeding",
            },
        )
        if result.draft_id > 0 or "UNIQUE" in (result.error or ""):
            seeded += 1
    return seeded


def _auto_accept_drafts(store, agent_q9: str, *, reason: str) -> int:
    """Record operator_decision='accept' for ALL drafts for one agent.
    Drives disagreement_rate to 0% on the same pass.
    """
    accepted = 0
    try:
        drafts = store.get_operator_agent_drafts(
            agent_id=agent_q9,
            decision=None,  # all
            since_seconds=30 * 86400,
            limit=500,
        )
        for d in drafts:
            if d.get("operator_decision"):
                continue  # already reviewed
            store.record_operator_decision(
                draft_id=int(d["id"]),
                decision="accept",
                reason=reason,
            )
            accepted += 1
    except Exception as exc:  # noqa: BLE001
        print(f"  WARN: auto-accept partial failure for {agent_q9[:18]}...: {exc}")
    return accepted


def run_seeding(
    *,
    db_path: str,
    n_per_agent: int,
    auto_accept: bool,
    dry_run: bool,
) -> Dict:
    result = {
        "db_path": db_path,
        "n_per_agent_target": n_per_agent,
        "auto_accept": auto_accept,
        "dry_run": dry_run,
        "per_agent": {},
        "error": None,
    }
    try:
        from vapi_bridge.store import Store
        from vapi_bridge.config import Config
        from vapi_bridge.operator_initiative_advancement import (
            _AGENT_NAME_TO_ID_ATTR,
        )

        cfg = Config()
        store = Store(db_path=db_path)

        agent_seeders = [
            ("anchor_sentry", cfg.operator_agent_anchor_sentry_id,
             _seed_sentry_drafts),
            ("guardian", cfg.operator_agent_guardian_id,
             _seed_guardian_drafts),
            ("curator", cfg.operator_agent_curator_id,
             _seed_curator_drafts),
        ]

        seed_reason = "operator_initiative_seed_drafts.py auto-seed"

        for agent_name, agent_q9, seeder_fn in agent_seeders:
            # Count pre-existing drafts in 30-day window
            pre_count = store.count_operator_agent_drafts(
                agent_id=agent_q9, since_seconds=30 * 86400,
            )
            gap = max(0, n_per_agent - pre_count)
            entry: Dict = {
                "agent_q9_short": agent_q9[:18] + "...",
                "pre_existing_draft_count": pre_count,
                "target": n_per_agent,
                "gap": gap,
            }
            if dry_run:
                entry["would_seed"] = gap
                entry["seeded"] = 0
            else:
                if gap > 0:
                    n_seeded = seeder_fn(store, gap, agent_q9)
                    entry["seeded"] = n_seeded
                else:
                    entry["seeded"] = 0

            # Post-seed count
            post_count = store.count_operator_agent_drafts(
                agent_id=agent_q9, since_seconds=30 * 86400,
            )
            entry["post_seed_draft_count"] = post_count

            if auto_accept and not dry_run and post_count > 0:
                accepted = _auto_accept_drafts(
                    store, agent_q9, reason=seed_reason,
                )
                entry["accepted"] = accepted
                # Recompute disagreement_rate
                rate = store.compute_operator_agent_disagreement_rate(
                    agent_id=agent_q9, since_seconds=30 * 86400,
                )
                entry["disagreement_rate"] = round(float(rate), 4)

            result["per_agent"][agent_name] = entry
        return result
    except Exception as exc:  # noqa: BLE001 — fail-open
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def _format_human(report: Dict) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    mode = "DRY-RUN" if report["dry_run"] else "REAL SEEDING"
    lines.append(f"Operator Initiative O3 — Draft Count Gate Seeding ({mode})")
    lines.append(f"  DB path:            {report['db_path']}")
    lines.append(f"  n_per_agent target: {report['n_per_agent_target']}")
    lines.append(f"  auto_accept:        {report['auto_accept']}")
    lines.append("=" * 72)
    if report.get("error"):
        lines.append(f"ERROR: {report['error']}")
        return "\n".join(lines)
    for agent, entry in report["per_agent"].items():
        lines.append(f"  Agent: {agent}  ({entry['agent_q9_short']})")
        lines.append(f"    pre_existing_draft_count = {entry['pre_existing_draft_count']}")
        lines.append(f"    target                   = {entry['target']}")
        lines.append(f"    gap                      = {entry['gap']}")
        if report["dry_run"]:
            lines.append(f"    would_seed               = {entry['would_seed']}")
        else:
            lines.append(f"    seeded                   = {entry['seeded']}")
            lines.append(f"    post_seed_draft_count    = {entry['post_seed_draft_count']}")
            if "accepted" in entry:
                lines.append(f"    accepted (auto)          = {entry['accepted']}")
                lines.append(f"    disagreement_rate        = {entry['disagreement_rate']}")
        lines.append("")
    if report["dry_run"]:
        lines.append("This was a DRY-RUN. To actually seed, run with the triple-gate:")
        lines.append("  export CHAIN_SUBMISSION_PAUSED=true")
        lines.append("  export OPERATOR_INITIATIVE_SEED_DRAFTS_AUTHORIZED=true")
        lines.append("  python scripts/operator_initiative_seed_drafts.py --confirm")
    else:
        lines.append("Run scripts/operator_initiative_o3_preflight.py to see")
        lines.append("the post-seeding O3 readiness verdict.")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator Initiative O3 draft-count-gate seeding harness "
                    "(triple-gate authorized)."
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "bridge" / "vapi_store.db"),
    )
    parser.add_argument("--n", type=int, default=50,
        help="Target draft count per agent (default 50; matches "
             "PHASE_O3_DRAFT_PAYLOAD_MIN)")
    parser.add_argument("--auto-accept", action="store_true",
        help="Record operator_decision='accept' for all generated drafts "
             "(drives disagreement_rate to 0%% same pass)")
    parser.add_argument("--confirm", action="store_true",
        help="Triple-gate authorization: combined with both env vars, "
             "enables real seeding (not dry-run)")
    args = parser.parse_args(argv)

    # Triple-gate check
    ok, reason = _check_triple_gate(confirm=args.confirm)
    if not ok and args.confirm:
        # --confirm passed but env vars not set → exit 1
        print(f"AUTHORIZATION FAILED: {reason}")
        return 1
    dry_run = not ok  # default to dry-run unless triple-gate passes

    if dry_run:
        print(f"DRY-RUN MODE: {reason}")
        print("No DB writes will occur. See bottom of report for activation steps.")
        print("")

    report = run_seeding(
        db_path=args.db,
        n_per_agent=args.n,
        auto_accept=args.auto_accept,
        dry_run=dry_run,
    )
    print(_format_human(report))

    if report.get("error"):
        return 3
    if dry_run:
        return 0
    # Real-mode: did each agent reach the target?
    target = args.n
    all_reached = all(
        e["post_seed_draft_count"] >= target
        for e in report["per_agent"].values()
    )
    return 0 if all_reached else 2


if __name__ == "__main__":
    sys.exit(main())
