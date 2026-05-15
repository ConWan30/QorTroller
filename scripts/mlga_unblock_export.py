"""Phase O5-MLGA Stage 4 — Unblock-harness export script.

Maps MLGA-captured gameplay sessions to the 3 currently-blocked
hardware-capture phases per the MLGA architectural proposal §3:

  1. Phase 243-SS2 Stage-A (adaptive trigger force-curve)
     Target: N=10 players × 100 trigger pulls × 3 game contexts.
     Export: trigger-pull aggregate per session.

  2. Phase 242-BT Stage 2 (σ_RSSI held-vs-placed)
     Target: ≥5 sessions × ≥30s per condition per player; controlled
     RF environment REQUIRED — MLGA augments breadth-of-condition
     coverage but does NOT replace the lab-controlled baseline.
     Export: BT observability flag + session duration summary.

  3. Phase 229 AIT corpus growth
     Target: ≥10 sessions per player AIT-quality holds.
     Export: still-hold window count + accel tremor sample counts.

Exit codes:
  0  Export complete + all 3 targets queried
  1  No MLGA sessions in store (operator hasn't run any captures yet)
  2  Export incomplete (DB or write error)
  3  Script error

Operator usage:

    # Default: summary report against bridge/vapi_store.db
    python scripts/mlga_unblock_export.py

    # JSON output for downstream tooling
    python scripts/mlga_unblock_export.py --json

    # Filter to recent sessions only (last N days)
    python scripts/mlga_unblock_export.py --since-days 7

    # Override DB path
    python scripts/mlga_unblock_export.py --db PATH

The 3 export targets are LOGICAL views over the same mlga_session_log
table. The script does not move data between tables — it surfaces what's
available for each blocked-phase consumer.

WALLET-FREE; READ-ONLY against the DB.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


# Per-phase target thresholds (the unblock-target each phase needs)
_PHASE_243_TARGET_TRIGGER_PULLS = 100 * 3 * 10   # 3000 R2+L2 pulls fleet-wide
_PHASE_242_TARGET_SESSIONS_WITH_BT = 15           # ≥5 per player × 3 players
_PHASE_242_TARGET_BT_HELD_PLACED = 5              # held-vs-placed transitions
_PHASE_229_TARGET_AIT_SESSIONS = 30               # 10 per player × 3 players


def _query_mlga_sessions(db_path: str, since_seconds: int) -> List[Dict[str, Any]]:
    """Read mlga_session_log rows in the time window. Fail-open empty list."""
    try:
        import sqlite3
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        cutoff_ts_ns = (time.time() - since_seconds) * 1_000_000_000
        rows = con.execute(
            "SELECT * FROM mlga_session_log "
            "WHERE session_end_ts_ns >= ? "
            "ORDER BY session_end_ts_ns DESC",
            (int(cutoff_ts_ns),),
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:  # noqa: BLE001
        return []


def _build_phase_243_export(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Phase 243-SS2 Stage-A: trigger force-curve corpus growth."""
    total_r2 = sum(int(s.get("n_trigger_pulls_r2") or 0) for s in sessions)
    total_l2 = sum(int(s.get("n_trigger_pulls_l2") or 0) for s in sessions)
    total_pulls = total_r2 + total_l2
    progress_pct = (
        min(100.0, (total_pulls / _PHASE_243_TARGET_TRIGGER_PULLS) * 100.0)
        if _PHASE_243_TARGET_TRIGGER_PULLS > 0 else 0.0
    )
    return {
        "phase": "243-SS2-Stage-A",
        "consumer": "scripts/analyze_interperson_separation.py "
                    "--session-type trigger_force_curve",
        "target_trigger_pulls": _PHASE_243_TARGET_TRIGGER_PULLS,
        "mlga_total_r2_pulls": total_r2,
        "mlga_total_l2_pulls": total_l2,
        "mlga_total_pulls": total_pulls,
        "progress_pct": round(progress_pct, 1),
        "unblock_status": (
            "READY_FOR_STREAM_2"
            if total_pulls >= _PHASE_243_TARGET_TRIGGER_PULLS
            else "IN_PROGRESS"
        ),
        "note": (
            "Adaptive trigger force-curves derive from L2/R2 onset velocity. "
            "Each MLGA-captured trigger pull contributes 1 sample to the "
            "Phase 243-SS2 Stage-A corpus. Once total >= target, the "
            "operator can ship Phase 243-SS2 Stream 2 (feature schema + "
            "extractor + endpoint + SDK + PV-CI invariants) with empirical "
            "data behind it."
        ),
    }


def _build_phase_242_export(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Phase 242-BT Stage 2: σ_RSSI held-vs-placed corpus growth."""
    n_with_bt = sum(
        1 for s in sessions if int(s.get("bt_observability") or 0) >= 1
    )
    n_held_placed = sum(
        1 for s in sessions if int(s.get("bt_observability") or 0) == 2
    )
    progress_pct = (
        min(100.0, (n_with_bt / _PHASE_242_TARGET_SESSIONS_WITH_BT) * 100.0)
        if _PHASE_242_TARGET_SESSIONS_WITH_BT > 0 else 0.0
    )
    return {
        "phase": "242-BT-Stage-2",
        "consumer": "wiki/methodology/bt_calibration_v1_1_architectural_revision.md §5",
        "target_sessions_with_bt": _PHASE_242_TARGET_SESSIONS_WITH_BT,
        "target_held_placed_transitions": _PHASE_242_TARGET_BT_HELD_PLACED,
        "mlga_sessions_with_bt_observed": n_with_bt,
        "mlga_sessions_with_held_placed": n_held_placed,
        "progress_pct": round(progress_pct, 1),
        "unblock_status": (
            "PARTIAL_SUPPLEMENT_READY"
            if n_with_bt >= _PHASE_242_TARGET_SESSIONS_WITH_BT
            else "IN_PROGRESS"
        ),
        "note": (
            "MLGA Channel B (BT BR/EDR via USB BT dongle) augments but does "
            "NOT replace the lab-controlled σ_RSSI measurement. The v1.1 BT "
            "calibration anchor §5 Empirical Unknown #1 requires "
            "low-WiFi-interference controlled RF environment for the held-"
            "vs-placed baseline. MLGA captures real-world deployment "
            "breadth-of-condition coverage as a supplement."
        ),
    }


def _build_phase_229_export(sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Phase 229 AIT corpus growth."""
    # AIT-quality sessions: GIC chain advanced (proxy for ACTIVE_GAMEPLAY +
    # NOMINAL capture + non-divergent rulings). Each GIC advance is a clean
    # session unit.
    total_gic_advances = sum(
        int(s.get("gic_advances_in_session") or 0) for s in sessions
    )
    progress_pct = (
        min(100.0, (total_gic_advances / _PHASE_229_TARGET_AIT_SESSIONS) * 100.0)
        if _PHASE_229_TARGET_AIT_SESSIONS > 0 else 0.0
    )
    return {
        "phase": "229-AIT-Corpus-Growth",
        "consumer": "scripts/analyze_interperson_separation.py "
                    "--session-type ait --write-snapshot",
        "target_ait_sessions": _PHASE_229_TARGET_AIT_SESSIONS,
        "mlga_gic_advances_total": total_gic_advances,
        "progress_pct": round(progress_pct, 1),
        "unblock_status": (
            "READY_FOR_CORPUS_GROWTH"
            if total_gic_advances >= _PHASE_229_TARGET_AIT_SESSIONS
            else "IN_PROGRESS"
        ),
        "note": (
            "MLGA-captured sessions that advance the GIC chain are AIT-"
            "corpus-eligible per Phase 229 (PCC=NOMINAL + EXCLUSIVE_USB + "
            "gameplay_context=ACTIVE_GAMEPLAY + non-divergent ruling). "
            "Each GIC advance = 1 clean session unit toward N=37+ corpus."
        ),
    }


def run_export(*, db_path: str, since_days: int) -> Dict[str, Any]:
    """Run the unblock export across all 3 phases. Never raises."""
    since_seconds = max(1, since_days) * 86400
    out: Dict[str, Any] = {
        "timestamp_iso": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time())
        ),
        "db_path": db_path,
        "since_days": since_days,
        "sessions_in_window": 0,
        "exports": {},
        "verdict": "NO_SESSIONS",
        "exit_code": 1,
        "error": None,
    }
    try:
        sessions = _query_mlga_sessions(db_path, since_seconds)
        out["sessions_in_window"] = len(sessions)
        if not sessions:
            return out
        out["exports"] = {
            "phase_243_ss2_stage_a": _build_phase_243_export(sessions),
            "phase_242_bt_stage_2":  _build_phase_242_export(sessions),
            "phase_229_ait_corpus":  _build_phase_229_export(sessions),
        }
        # Verdict resolution
        statuses = [e["unblock_status"] for e in out["exports"].values()]
        if all(s.startswith("READY") or s.startswith("PARTIAL") for s in statuses):
            out["verdict"] = "ALL_TARGETS_REACHED"
            out["exit_code"] = 0
        else:
            out["verdict"] = "TARGETS_IN_PROGRESS"
            out["exit_code"] = 0
        return out
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["exit_code"] = 2
        return out


def _format_human(o: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("MLGA Unblock Export — 3 blocked-phase corpus progress")
    lines.append(f"  timestamp:  {o['timestamp_iso']}")
    lines.append(f"  db_path:    {o['db_path']}")
    lines.append(f"  since_days: {o['since_days']}")
    lines.append(f"  sessions:   {o['sessions_in_window']}")
    lines.append("=" * 72)
    if o.get("error"):
        lines.append(f"ERROR: {o['error']}")
        return "\n".join(lines)
    if not o["exports"]:
        lines.append("No MLGA sessions in window. Run operator gameplay with")
        lines.append("MLGA enabled (Phase O5-MLGA Stage 3 smoke session)")
        lines.append("before re-running this export.")
        return "\n".join(lines)
    for key, exp in o["exports"].items():
        lines.append(f"  Phase: {exp['phase']}")
        lines.append(f"    consumer:   {exp['consumer']}")
        lines.append(f"    progress:   {exp['progress_pct']}%")
        lines.append(f"    status:     {exp['unblock_status']}")
        for k, v in exp.items():
            if k.startswith("mlga_") or k.startswith("target_"):
                lines.append(f"    {k}: {v}")
        lines.append("")
    lines.append(f"VERDICT:  {o['verdict']}")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MLGA unblock-harness — map ambient captures to 3 phases."
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "bridge" / "vapi_store.db"),
    )
    parser.add_argument("--since-days", type=int, default=30,
        help="Only consider MLGA sessions ending within N days (default 30)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    out = run_export(db_path=args.db, since_days=args.since_days)
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(_format_human(out))
    return int(out.get("exit_code", 3))


if __name__ == "__main__":
    sys.exit(main())
