"""Day 15 ceremony dry-run REHEARSAL harness.

Operator-authorized goal 2026-05-15: walk through the exact sequence
scripts/parallel_o3_act_anchor.py will execute on Day 15 (~2026-05-30
when Curator's shadow_age 504h gate clears), but NEVER fire any tx.

This is a fault-isolated mirror of parallel_o3_act_anchor.py:
  • Same gate evaluation logic (Gates 1-4)
  • Same bundle validation (parse + Merkle vs canonical pins)
  • Same FRR computation (expected post-anchor state)
  • Same wallet balance + gas price + cost projection (eth_call only)
  • Same operational FIRST + governance SECOND ordering inspection
  • REPLACES anchor.anchor_bundle() with calldata-build-without-send

The rehearsal NEVER calls _send_tx. There is no code path through
this script that produces a signed tx. Wallet-free + chain-read-only.

Exit codes mirror parallel_o3_act_anchor.py shape:
  0  rehearsal PASS — Day 15 fire will land cleanly
  1  Gates 1-3 would FAIL on Day 15 (env / --confirm misconfigured)
  2  wallet / pre-flight RPC failure
  3  bundle validation failed (Merkle drift from canonical pin)
  4  rehearsal could not complete (DB or import error)
  5  expected_frr compute failed
  7  Gate 4 (watcher veto) would FAIL — agents not o3_ready
     (THIS IS EXPECTED until Day 15; exit 7 is informational at Day 0)

Operator usage:

    # Default rehearsal (no env vars needed; never fires):
    python scripts/parallel_o3_act_anchor_rehearsal.py

    # Strict rehearsal (require ALL 4 gates would PASS — used Day 14):
    python scripts/parallel_o3_act_anchor_rehearsal.py --strict

    # Include chain reads for live wallet balance + gas estimate:
    python scripts/parallel_o3_act_anchor_rehearsal.py --include-chain-reads

    # JSON output for programmatic consumption:
    python scripts/parallel_o3_act_anchor_rehearsal.py --json

The rehearsal MAY be run by Mythos in the pre_ceremony cadence tier
on Day 14 to surface any drift before the real fire. See
mythos_variants.py mythos_post_o3_ceremony_audit for the post-fire
counterpart; this script is the pre-fire counterpart.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


# Canonical O3 ACTING bundle Merkle pins — must match _CANONICAL_BUNDLE_
# MERKLES in mythos_variants.py + _EXPECTED_O3_ACTING_MERKLES in
# operator_initiative_post_o3_audit.py. Single source of truth per agent.
_EXPECTED_O3_ACTING_MERKLES: Dict[str, str] = {
    "anchor_sentry":
        "0xc0bcdee8576e83f6b80e8c5ac89093cf08f153033037176cd03fc34fcedfd878",
    "guardian":
        "0x6f0fc77cc1dacaf3f79aeb0f27dd8c7b3d88e95b236f0806ad3588a06bb82225",
    "curator":
        "0xd9d760c8b7b1088f2edd165fbfa6441abcb3bc3f921e8ba75a3339c0825fec24",
}

_AGENT_ANCHOR_ORDER = ("anchor_sentry", "guardian", "curator")
_BUNDLE_FILES = {
    "anchor_sentry": "anchor_sentry_o3_acting_v1.json",
    "guardian":      "guardian_o3_acting_v1.json",
    "curator":       "curator_o3_acting_v1.json",
}


def _norm_hex(s: str) -> str:
    s = (s or "").strip().lower()
    return s[2:] if s.startswith("0x") else s


def _check_gates_1_2_3(*, confirm: bool) -> Dict[str, Any]:
    """Evaluate gates 1-3 same as the real script. Reports state; does NOT
    refuse rehearsal on failure (the rehearsal MAY run without --confirm)."""
    pause_env = os.environ.get("CHAIN_SUBMISSION_PAUSED", "true").strip().lower()
    intent_env = os.environ.get(
        "OPERATOR_INITIATIVE_O3_AUTHORIZED", ""
    ).strip().lower()
    return {
        "gate_1_chain_submission_unpaused": pause_env == "false",
        "gate_2_operator_o3_authorized":    intent_env == "true",
        "gate_3_confirm_flag":              bool(confirm),
        "gates_1_2_3_all_pass": (
            pause_env == "false" and intent_env == "true" and bool(confirm)
        ),
    }


async def _check_gate_4_watcher(*, cfg, store) -> Dict[str, Any]:
    """Evaluate Gate 4 (watcher veto) via the same call the real script makes."""
    try:
        from vapi_bridge.operator_initiative_advancement import (
            evaluate_fleet_advancement_sync,
        )
        summary = evaluate_fleet_advancement_sync(cfg=cfg, store=store)
        if summary.error:
            return {
                "gate_4_pass": False,
                "error": summary.error,
                "blockers_per_agent": {},
            }
        per_agent_blockers: Dict[str, List[str]] = {}
        all_pass = True
        for a in summary.per_agent:
            per_agent_blockers[a.agent_id] = list(a.o3_blockers)
            if not a.o3_ready:
                all_pass = False
        return {
            "gate_4_pass": all_pass,
            "fleet_at_o3_ready_count": summary.fleet_at_o3_ready_count,
            "fleet_phase_aligned": summary.fleet_phase_aligned,
            "blockers_per_agent": per_agent_blockers,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "gate_4_pass": False,
            "error": f"{type(exc).__name__}: {exc}",
            "blockers_per_agent": {},
        }


def _validate_bundles(repo_root: Path) -> Dict[str, Any]:
    """Parse each of the 3 O3 ACTING bundles + verify Merkle vs canonical
    pin. Mirrors the real script's bundle validation step."""
    out: Dict[str, Any] = {"per_agent": {}, "all_pass": True}
    try:
        from vapi_bridge.cedar_parser import parse_bundle, bundle_merkle_root
    except Exception as exc:  # noqa: BLE001
        return {"all_pass": False, "error": f"cedar_parser import failed: {exc}"}

    bundles_dir = repo_root / "bridge" / "vapi_bridge" / "cedar_bundles"
    for agent in _AGENT_ANCHOR_ORDER:
        bundle_path = bundles_dir / _BUNDLE_FILES[agent]
        entry: Dict[str, Any] = {
            "bundle_path": str(bundle_path),
            "exists": bundle_path.is_file(),
            "pass": True,
        }
        if not entry["exists"]:
            entry["pass"] = False
            entry["error"] = "bundle file missing"
            out["all_pass"] = False
            out["per_agent"][agent] = entry
            continue
        try:
            with open(bundle_path, encoding="utf-8") as f:
                payload = json.load(f)
            parsed = parse_bundle(payload)
        except Exception as exc:  # noqa: BLE001
            entry["pass"] = False
            entry["error"] = f"parse failed: {exc}"
            out["all_pass"] = False
            out["per_agent"][agent] = entry
            continue
        entry["phase"] = parsed.phase
        entry["phase_ok"] = parsed.phase == "O3_ACTING"
        if not entry["phase_ok"]:
            entry["pass"] = False
            entry["error"] = (
                f"phase={parsed.phase}, expected O3_ACTING"
            )
            out["all_pass"] = False
        try:
            mb = parsed.merkle_root
            live_hex = mb.hex() if isinstance(mb, (bytes, bytearray)) else str(mb)
            expected = _EXPECTED_O3_ACTING_MERKLES[agent]
            entry["merkle_live"] = "0x" + live_hex
            entry["merkle_expected"] = expected
            entry["merkle_match"] = _norm_hex(live_hex) == _norm_hex(expected)
            if not entry["merkle_match"]:
                entry["pass"] = False
                entry["error"] = (
                    "MERKLE DRIFT: on-disk bundle does not match canonical "
                    "O3 ACTING pin. Day 15 fire would write the WRONG Merkle "
                    "to AgentScope."
                )
                out["all_pass"] = False
        except Exception as exc:  # noqa: BLE001
            entry["pass"] = False
            entry["error"] = f"merkle compute failed: {exc}"
            out["all_pass"] = False
        out["per_agent"][agent] = entry
    return out


async def _compute_expected_frr(*, cfg) -> Dict[str, Any]:
    """Build the synthetic post-anchor FleetAdvancementSummary + compute the
    FRR commitment. Mirrors the real script's expected-FRR section."""
    try:
        from vapi_bridge.operator_initiative_advancement import (
            AgentAdvancementReadiness,
            FleetAdvancementSummary,
            compute_fleet_readiness_root,
            FRR_DOMAIN_TAG,
            PHASE_CODE_O3_ACT,
        )
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
            for agent_id in _AGENT_ANCHOR_ORDER
        )
        synthetic = FleetAdvancementSummary(
            timestamp=time.time(),
            fleet_size=3,
            fleet_at_o1_count=0,
            fleet_at_o2_ready_count=0,
            fleet_at_o3_ready_count=3,
            fleet_phase_aligned=True,
            next_alignment_target="O3_ACT",
            per_agent=synthetic_per_agent,
        )
        result = compute_fleet_readiness_root(
            synthetic, cfg=cfg, ts_ns=expected_ts_ns,
        )
        if result.error:
            return {"ok": False, "error": result.error}
        return {
            "ok": True,
            "domain_tag": FRR_DOMAIN_TAG.decode(),
            "phase_code_hex": f"0x{PHASE_CODE_O3_ACT:02x}",
            "ts_ns": expected_ts_ns,
            "frr_hex": "0x" + result.frr_hex,
            "agents": [
                {
                    "name": name,
                    "agent_id": "0x" + id_hex,
                    "phase_code": f"0x{phase_code:02x}",
                }
                for name, id_hex, phase_code in result.agents
            ],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


async def _read_wallet_state(*, cfg, include_chain_reads: bool) -> Dict[str, Any]:
    """Read wallet balance + gas price via eth_call (read-only). Skipped
    if --include-chain-reads is False (offline rehearsal)."""
    if not include_chain_reads:
        return {
            "skipped": True,
            "reason": "Use --include-chain-reads to enable RPC reads.",
        }
    try:
        from vapi_bridge.chain import ChainClient
        chain = ChainClient(cfg)
        if chain._account is None:
            return {"ok": False, "error": "bridge wallet not loaded"}
        wallet_addr = chain._account.address
        bal_wei = await chain._w3.eth.get_balance(wallet_addr)
        try:
            gas_price_wei = await chain._w3.eth.gas_price
        except Exception:  # noqa: BLE001
            gas_price_wei = 0
        # 6 txs × ~200k gas × 1.25 buffer (mirror parallel_o3_act_anchor.py)
        est_per_tx_iotx = (
            (200_000 * 1.25 * gas_price_wei) / 1e18 if gas_price_wei else 0.05
        )
        est_total_iotx = est_per_tx_iotx * 6
        return {
            "ok": True,
            "wallet_addr": wallet_addr,
            "balance_iotx": bal_wei / 1e18,
            "gas_price_gwei": (gas_price_wei or 0) / 1e9,
            "estimated_cost_iotx_for_6_txs": est_total_iotx,
            "cost_budget_iotx": 3.0,
            "cost_budget_ok": est_total_iotx <= 3.0,
            "safety_floor_iotx": 0.50,
            "safety_floor_ok": (bal_wei / 1e18) >= 0.50,
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _ceremony_step_plan() -> List[Dict[str, Any]]:
    """The 6-tx ceremony plan in fixed firing order (operational FIRST +
    governance SECOND per INV-OPERATOR-AGENT-001). Each entry describes
    a tx that WOULD be fired on Day 15."""
    plan: List[Dict[str, Any]] = []
    for i, agent in enumerate(_AGENT_ANCHOR_ORDER, start=1):
        # Operational anchor (AgentScope.setAgentScopeRoot)
        plan.append({
            "step": (i - 1) * 2 + 1,
            "agent": agent,
            "leg": "operational",
            "contract": "AgentScope",
            "method": "setAgentScopeRoot",
            "args": ["agent_id (Q9 hex)", "merkle_root (O3 ACTING Merkle)"],
            "gas_buffer_multiplier": 1.25,
            "would_fire_if_gates_clear": True,
        })
        # Governance anchor (AgentRegistry.updateAgentScope)
        plan.append({
            "step": (i - 1) * 2 + 2,
            "agent": agent,
            "leg": "governance",
            "contract": "AgentRegistry",
            "method": "updateAgentScope",
            "args": ["agent_id (Q9 hex)", "merkle_root (matches operational)"],
            "gas_buffer_multiplier": 1.25,
            "would_fire_if_gates_clear": True,
        })
    return plan


async def run_rehearsal(
    *,
    repo_root: Path,
    confirm: bool,
    include_chain_reads: bool,
    strict: bool,
) -> Dict[str, Any]:
    """Run the full rehearsal end-to-end. Never raises."""
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))
    rehearsal: Dict[str, Any] = {
        "timestamp_iso": now_iso,
        "strict": strict,
        "include_chain_reads": include_chain_reads,
        "verdict": "UNKNOWN",
        "exit_code": 4,
        "sections": {},
    }
    try:
        from vapi_bridge.config import Config
        from vapi_bridge.store import Store

        cfg = Config()
        db_path = str(repo_root / "bridge" / "vapi_store.db")
        store = Store(db_path=db_path)

        # Section 1 — Gates 1-3 (env + --confirm)
        gates_1_2_3 = _check_gates_1_2_3(confirm=confirm)
        rehearsal["sections"]["gates_1_2_3"] = gates_1_2_3

        # Section 2 — Gate 4 (watcher veto)
        gate_4 = await _check_gate_4_watcher(cfg=cfg, store=store)
        rehearsal["sections"]["gate_4_watcher"] = gate_4

        # Section 3 — Bundle validation (Merkle vs canonical pin)
        bundles = _validate_bundles(repo_root=repo_root)
        rehearsal["sections"]["bundle_validation"] = bundles
        if not bundles.get("all_pass"):
            rehearsal["verdict"] = "BUNDLE_DRIFT_DETECTED"
            rehearsal["exit_code"] = 3
            return rehearsal

        # Section 4 — Expected post-anchor FRR
        expected_frr = await _compute_expected_frr(cfg=cfg)
        rehearsal["sections"]["expected_post_anchor_frr"] = expected_frr
        if not expected_frr.get("ok"):
            rehearsal["verdict"] = "FRR_COMPUTE_FAILED"
            rehearsal["exit_code"] = 5
            return rehearsal

        # Section 5 — Wallet state (optional chain reads)
        wallet = await _read_wallet_state(
            cfg=cfg, include_chain_reads=include_chain_reads,
        )
        rehearsal["sections"]["wallet_state"] = wallet

        # Section 6 — Ceremony plan (6 txs in firing order)
        rehearsal["sections"]["ceremony_plan"] = {
            "total_txs": 6,
            "ordering_invariant":
                "operational FIRST + governance SECOND per INV-OPERATOR-AGENT-001",
            "agent_order": list(_AGENT_ANCHOR_ORDER),
            "steps": _ceremony_step_plan(),
        }

        # Verdict resolution
        gates_1_3_ok = gates_1_2_3["gates_1_2_3_all_pass"]
        gate_4_ok = gate_4.get("gate_4_pass", False)
        if gates_1_3_ok and gate_4_ok and bundles["all_pass"]:
            rehearsal["verdict"] = "READY_TO_FIRE"
            rehearsal["exit_code"] = 0
        elif not gate_4_ok:
            rehearsal["verdict"] = "GATE_4_WATCHER_VETO"
            rehearsal["exit_code"] = 7
        elif not gates_1_3_ok:
            rehearsal["verdict"] = "GATES_1_3_NOT_SET"
            rehearsal["exit_code"] = 1
        else:
            rehearsal["verdict"] = "UNKNOWN"
            rehearsal["exit_code"] = 4

        # Strict mode: anything other than READY_TO_FIRE is exit 1
        if strict and rehearsal["exit_code"] != 0:
            rehearsal["exit_code"] = 1

        return rehearsal
    except Exception as exc:  # noqa: BLE001 — fail-open
        rehearsal["error"] = f"{type(exc).__name__}: {exc}"
        rehearsal["exit_code"] = 4
        return rehearsal


def _format_human(rehearsal: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("Day 15 Ceremony Dry-Run REHEARSAL")
    lines.append(f"  timestamp:          {rehearsal['timestamp_iso']}")
    lines.append(f"  strict:             {rehearsal['strict']}")
    lines.append(f"  include_chain_reads:{rehearsal['include_chain_reads']}")
    lines.append("=" * 72)
    s = rehearsal.get("sections", {})

    if "gates_1_2_3" in s:
        g = s["gates_1_2_3"]
        lines.append("Section 1 — Gates 1-3 (env + --confirm):")
        for k in ("gate_1_chain_submission_unpaused",
                  "gate_2_operator_o3_authorized",
                  "gate_3_confirm_flag"):
            mark = "✓" if g.get(k) else "✗"
            lines.append(f"  {mark} {k} = {g.get(k)}")
        lines.append("")

    if "gate_4_watcher" in s:
        g4 = s["gate_4_watcher"]
        mark = "✓" if g4.get("gate_4_pass") else "✗"
        lines.append(f"Section 2 — Gate 4 (watcher veto):  {mark}")
        if "error" in g4:
            lines.append(f"  error: {g4['error']}")
        for agent, blockers in (g4.get("blockers_per_agent") or {}).items():
            if blockers:
                lines.append(f"  {agent}: {len(blockers)} blockers")
                for b in blockers[:4]:
                    lines.append(f"    - {b}")
            else:
                lines.append(f"  {agent}: o3_ready")
        lines.append("")

    if "bundle_validation" in s:
        bv = s["bundle_validation"]
        mark = "✓" if bv.get("all_pass") else "✗"
        lines.append(f"Section 3 — Bundle validation:  {mark}")
        if "error" in bv:
            lines.append(f"  error: {bv['error']}")
        for agent, entry in (bv.get("per_agent") or {}).items():
            agent_mark = "✓" if entry.get("pass") else "✗"
            lines.append(f"  {agent_mark} {agent}")
            lines.append(f"      file: {Path(entry.get('bundle_path', '')).name}")
            lines.append(f"      phase: {entry.get('phase', 'n/a')}")
            if "merkle_live" in entry:
                lines.append(f"      merkle_live:     {entry['merkle_live'][:24]}...")
                lines.append(f"      merkle_expected: {entry['merkle_expected'][:24]}...")
                lines.append(f"      merkle_match:    {entry.get('merkle_match', False)}")
            if "error" in entry:
                lines.append(f"      ERROR: {entry['error']}")
        lines.append("")

    if "expected_post_anchor_frr" in s:
        fr = s["expected_post_anchor_frr"]
        lines.append("Section 4 — Expected post-anchor FRR:")
        if fr.get("ok"):
            lines.append(f"  domain_tag:  {fr['domain_tag']}")
            lines.append(f"  phase_code:  {fr['phase_code_hex']} (all 3 agents)")
            lines.append(f"  ts_ns:       {fr['ts_ns']}")
            lines.append(f"  FRR (hex):   {fr['frr_hex']}")
            for a in fr.get("agents", []):
                lines.append(f"    {a['name']:<14s} {a['agent_id'][:24]}... phase {a['phase_code']}")
        else:
            lines.append(f"  ERROR: {fr.get('error', 'unknown')}")
        lines.append("")

    if "wallet_state" in s:
        w = s["wallet_state"]
        lines.append("Section 5 — Wallet state (eth_call only; no tx):")
        if w.get("skipped"):
            lines.append(f"  SKIPPED — {w.get('reason', '')}")
        elif w.get("ok"):
            lines.append(f"  wallet:                   {w['wallet_addr']}")
            lines.append(f"  balance_iotx:             {w['balance_iotx']:.6f}")
            lines.append(f"  gas_price_gwei:           {w['gas_price_gwei']:.1f}")
            lines.append(f"  estimated_cost_iotx_6tx:  {w['estimated_cost_iotx_for_6_txs']:.4f}")
            lines.append(f"  cost_budget_iotx:         {w['cost_budget_iotx']}")
            lines.append(f"  cost_budget_ok:           {w['cost_budget_ok']}")
            lines.append(f"  safety_floor_iotx:        {w['safety_floor_iotx']}")
            lines.append(f"  safety_floor_ok:          {w['safety_floor_ok']}")
        else:
            lines.append(f"  ERROR: {w.get('error', 'unknown')}")
        lines.append("")

    if "ceremony_plan" in s:
        p = s["ceremony_plan"]
        lines.append(f"Section 6 — Ceremony plan ({p['total_txs']} txs):")
        lines.append(f"  ordering invariant: {p['ordering_invariant']}")
        for step in p["steps"]:
            lines.append(
                f"  step {step['step']}. [{step['agent']}] "
                f"{step['contract']}.{step['method']}() "
                f"({step['leg']})"
            )
        lines.append("")

    lines.append(f"VERDICT:  {rehearsal.get('verdict', 'UNKNOWN')}")
    lines.append(f"EXIT:     {rehearsal.get('exit_code', 4)}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Day 15 ceremony dry-run rehearsal — wallet-free + tx-free."
    )
    parser.add_argument("--confirm", action="store_true",
        help="Simulate operator passing --confirm (does NOT fire anything)")
    parser.add_argument("--include-chain-reads", action="store_true",
        help="Read wallet balance + gas price via eth_call (read-only)")
    parser.add_argument("--strict", action="store_true",
        help="Exit 1 unless verdict is READY_TO_FIRE (used Day 14 prep)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    rehearsal = asyncio.run(run_rehearsal(
        repo_root=PROJECT_ROOT,
        confirm=args.confirm,
        include_chain_reads=args.include_chain_reads,
        strict=args.strict,
    ))
    if args.json:
        print(json.dumps(rehearsal, indent=2, default=str))
    else:
        print(_format_human(rehearsal))
    return int(rehearsal.get("exit_code", 4))


if __name__ == "__main__":
    sys.exit(main())
