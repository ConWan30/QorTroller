"""VBDIP-0002 Appendix B §B.8 G7 — Curator Review Readiness observability harness.

Wallet-free read-only audit that surfaces the Curator's progression through
the G7 acceptance gate ("≥9 of last 10 reviewed Curator drafts accepted by
operator over a 7-day trailing window"). The agent cannot literally
"complete" G7 — that requires Curator to be live in the bridge process
producing drafts AND the operator to be reviewing them over real time.
This harness measures gate state at any point and reports PASS / BLOCKED /
FAIL so the operator knows exactly when G7 has closed.

Per Phase O4-VPM-INTEGRATION close (commit e81e04aa) + Whitepaper v4 §15
forward roadmap, G7 is the only OPEN sub-gate in the VBDIP-0002 §B.8 gate
sweep. Closing G7 is the last development-side prerequisite for the
Curator O1_SHADOW → O2_SUGGEST graduation ceremony (~0.16 IOTX wallet
spend, separate workstream).

WALLET-FREE CONTRACT:

  - No transaction submission paths invoked
  - No bridge HTTP calls required (direct sqlite3 read against
    bridge/vapi_store.db; resilient when bridge is offline)
  - No env-var changes
  - No file mutation outside the audit report output
  - CHAIN_SUBMISSION_PAUSED state untouched

Five sections (mirroring the zkba_post_ceremony_audit.py pattern):

  Section 1 — Curator agent_id resolution
              Resolves the canonical "curator" name to its Q9-frozen
              agent_id via the same _AGENT_NAME_TO_ID_ATTR mapping that
              operator_initiative_advancement.py uses, then checks that
              the curator row exists in store.

  Section 2 — 7-day trailing window draft count
              Counts Curator drafts created in the last 7 days. Surfaces
              total drafts vs. reviewed drafts. The acceptance gate
              denominator is the reviewed count, not the total.

  Section 3 — Last-10 acceptance rate
              Of the last 10 REVIEWED Curator drafts (ordered by
              operator_decision_at DESC), how many have
              operator_decision='accept'? Reports the exact 10-row
              breakdown so the operator can audit individual decisions.

  Section 4 — Acceptance rate gate evaluation
              PASS if (n_reviewed >= 10) AND (n_accept >= 9).
              BLOCKED if n_reviewed < 10 (insufficient signal).
              FAIL if n_reviewed >= 10 AND n_accept < 9.

  Section 5 — Curator-specific operational invariants
              Cross-checks that Phase O3-ACT-WATCHER's ZERO TOLERANCE
              false_positive_rate gate (PHASE_O3_FALSE_POSITIVE_RATE_MAX
              = 0.0) is empirically clean: any 'overturn_curator' decision
              on a Curator draft blocks O3 graduation independent of
              the 9-of-10 acceptance rate.

Run:

    # Local-only audit (default):
    python scripts/g7_curator_review_readiness_audit.py

    # Emit machine-readable JSON:
    python scripts/g7_curator_review_readiness_audit.py --json

    # Custom DB path (testing / multi-bridge deployments):
    python scripts/g7_curator_review_readiness_audit.py --db /path/to/vapi_store.db

Exit codes:
  0  G7 PASS — Curator ready for O2_SUGGEST graduation ceremony
  1  G7 BLOCKED — insufficient reviewed drafts (n_reviewed < 10)
  2  G7 FAIL — acceptance rate below 9/10
  3  Curator agent not present in store (Curator has not produced drafts)
  4  Configuration / DB access error

Author: VAPI Architect (G7 observability harness ships after Whitepaper v4
revamp per operator directive 2026-05-13; closes the last agent-actionable
piece of VBDIP-0002 §B.8 G7 verification).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "bridge" / "vapi_store.db"

# FROZEN: G7 gate constants per VBDIP-0002 §B.8 + Phase O3-ACT-WATCHER
# constants in bridge/vapi_bridge/operator_initiative_advancement.py.
# Reordering or relaxing these requires a governance ceremony.
G7_WINDOW_DAYS = 7
G7_LAST_N = 10
G7_MIN_ACCEPT = 9
G7_FALSE_POSITIVE_RATE_MAX = 0.0  # ZERO TOLERANCE (Curator-specific)

# Curator-specific decision values. 'accept' / 'reject' are the standard
# operator decisions; 'overturn_curator' is the Curator-exclusive false-
# positive signal that fires the ZERO TOLERANCE gate independent of
# acceptance rate. Mirrors operator_initiative_advancement.py contract.
_VALID_DECISIONS = ("accept", "reject", "overturn_curator")


def _resolve_curator_agent_id(conn: sqlite3.Connection) -> str:
    """Find the Curator's agent_id as stored in operator_agent_drafts.

    In production, Curator's agent_id is the Q9-frozen hex
    `0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8`
    (per Sessions 1+2+3 on-chain activation 2026-05-09). In test stubs
    or pre-activation states it may be the canonical name 'curator'.
    Both are valid; we pick whichever has rows.
    """
    cur = conn.cursor()
    # Try Q9 hex first (production).
    q9_hex = (
        "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"
    )
    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts WHERE agent_id=?",
        (q9_hex,),
    )
    if cur.fetchone()[0] > 0:
        return q9_hex
    # Fall back to canonical name.
    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts WHERE agent_id=?",
        ("curator",),
    )
    if cur.fetchone()[0] > 0:
        return "curator"
    # No Curator drafts at all — surface the production-form key so
    # downstream sections fail cleanly with "0 drafts" rather than a
    # different agent's data.
    return q9_hex


def section_1_curator_presence(conn: sqlite3.Connection) -> dict:
    """Verify Curator agent has at least one row in operator_agent_drafts."""
    agent_id = _resolve_curator_agent_id(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts WHERE agent_id=?",
        (agent_id,),
    )
    total = cur.fetchone()[0]
    return {
        "section": "1_curator_presence",
        "curator_agent_id": agent_id,
        "is_q9_hex": agent_id.startswith("0x") and len(agent_id) == 66,
        "total_drafts_ever": int(total),
        "curator_present": total > 0,
    }


def section_2_window_counts(
    conn: sqlite3.Connection, agent_id: str
) -> dict:
    """Count Curator drafts in the trailing 7-day window."""
    cur = conn.cursor()
    window_seconds = G7_WINDOW_DAYS * 86400
    since = time.time() - window_seconds

    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts "
        "WHERE agent_id=? AND created_at >= ?",
        (agent_id, since),
    )
    total_in_window = int(cur.fetchone()[0])

    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts "
        "WHERE agent_id=? AND created_at >= ? "
        "AND operator_decision IS NOT NULL",
        (agent_id, since),
    )
    reviewed_in_window = int(cur.fetchone()[0])

    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts "
        "WHERE agent_id=? AND created_at >= ? "
        "AND operator_decision IS NULL",
        (agent_id, since),
    )
    unreviewed_in_window = int(cur.fetchone()[0])

    return {
        "section": "2_window_counts",
        "window_days": G7_WINDOW_DAYS,
        "since_unix_seconds": since,
        "total_in_window": total_in_window,
        "reviewed_in_window": reviewed_in_window,
        "unreviewed_in_window": unreviewed_in_window,
    }


def section_3_last_n_breakdown(
    conn: sqlite3.Connection, agent_id: str
) -> dict:
    """Inspect the last 10 REVIEWED Curator drafts ordered by decision time."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, action_name, draft_uri, payload_hash, "
        "       operator_decision, operator_decision_at, created_at "
        "FROM operator_agent_drafts "
        "WHERE agent_id=? AND operator_decision IS NOT NULL "
        "ORDER BY operator_decision_at DESC LIMIT ?",
        (agent_id, G7_LAST_N),
    )
    rows = []
    n_accept = 0
    n_reject = 0
    n_overturn_curator = 0
    n_other = 0
    for row in cur.fetchall():
        d = row[4]
        rows.append({
            "id": row[0],
            "action_name": row[1],
            "draft_uri": row[2],
            "payload_hash": row[3],
            "operator_decision": d,
            "operator_decision_at": row[5],
            "created_at": row[6],
        })
        if d == "accept":
            n_accept += 1
        elif d == "reject":
            n_reject += 1
        elif d == "overturn_curator":
            n_overturn_curator += 1
        else:
            # Anomalous decision — should not occur per
            # operator_initiative_advancement.py allowlist.
            n_other += 1

    n_reviewed = len(rows)
    return {
        "section": "3_last_n_breakdown",
        "last_n": G7_LAST_N,
        "n_reviewed_returned": n_reviewed,
        "n_accept": n_accept,
        "n_reject": n_reject,
        "n_overturn_curator": n_overturn_curator,
        "n_other_anomalous": n_other,
        "rows": rows,
    }


def section_4_gate_evaluation(
    section_2: dict, section_3: dict
) -> dict:
    """Evaluate G7 PASS / BLOCKED / FAIL state.

    PASS:    n_reviewed_in_window >= G7_LAST_N (10)
             AND n_accept (in last 10) >= G7_MIN_ACCEPT (9)
    BLOCKED: n_reviewed_in_window < G7_LAST_N (insufficient signal;
             not a fail, just not-yet-decidable)
    FAIL:    n_reviewed_in_window >= G7_LAST_N AND n_accept < G7_MIN_ACCEPT
    """
    n_reviewed = section_2["reviewed_in_window"]
    n_accept = section_3["n_accept"]
    n_reject = section_3["n_reject"]
    n_overturn = section_3["n_overturn_curator"]

    if n_reviewed < G7_LAST_N:
        verdict = "BLOCKED"
        reason = (
            f"insufficient_signal: n_reviewed_in_window={n_reviewed} "
            f"< G7_LAST_N={G7_LAST_N}; Curator needs more operator "
            f"review decisions before the gate can evaluate"
        )
        exit_code = 1
    elif n_accept >= G7_MIN_ACCEPT:
        verdict = "PASS"
        reason = (
            f"acceptance_rate_met: n_accept={n_accept}/"
            f"{G7_LAST_N} (of last 10 reviewed) >= "
            f"G7_MIN_ACCEPT={G7_MIN_ACCEPT}"
        )
        exit_code = 0
    else:
        verdict = "FAIL"
        reason = (
            f"acceptance_rate_below_threshold: n_accept={n_accept}/"
            f"{G7_LAST_N} < G7_MIN_ACCEPT={G7_MIN_ACCEPT}; "
            f"Curator drafts are not being accepted at the required "
            f"rate — investigate disagreement reasons before proceeding "
            f"to O2_SUGGEST graduation"
        )
        exit_code = 2

    return {
        "section": "4_gate_evaluation",
        "verdict": verdict,
        "exit_code_for_this_section": exit_code,
        "reason": reason,
        "n_reviewed_in_window": n_reviewed,
        "n_accept_in_last_n": n_accept,
        "n_reject_in_last_n": n_reject,
        "n_overturn_curator_in_last_n": n_overturn,
        "gate_constants": {
            "G7_WINDOW_DAYS": G7_WINDOW_DAYS,
            "G7_LAST_N": G7_LAST_N,
            "G7_MIN_ACCEPT": G7_MIN_ACCEPT,
        },
    }


def section_5_zero_tolerance_invariant(
    conn: sqlite3.Connection, agent_id: str
) -> dict:
    """Curator-specific PHASE_O3_FALSE_POSITIVE_RATE_MAX=0.0 invariant.

    Independent of the 9-of-10 acceptance gate, ANY 'overturn_curator'
    decision in the trailing window fires the ZERO TOLERANCE blocker
    against O3_ACT graduation. This section surfaces that signal so the
    operator knows whether G7 + the broader O3 graduation gate are
    BOTH closeable.
    """
    cur = conn.cursor()
    window_seconds = G7_WINDOW_DAYS * 86400
    since = time.time() - window_seconds

    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts "
        "WHERE agent_id=? AND created_at >= ? "
        "AND operator_decision='overturn_curator'",
        (agent_id, since),
    )
    n_overturn_in_window = int(cur.fetchone()[0])

    cur.execute(
        "SELECT COUNT(*) FROM operator_agent_drafts "
        "WHERE agent_id=? AND created_at >= ? "
        "AND operator_decision IS NOT NULL",
        (agent_id, since),
    )
    n_reviewed_in_window = int(cur.fetchone()[0])

    if n_reviewed_in_window > 0:
        false_positive_rate = n_overturn_in_window / n_reviewed_in_window
    else:
        false_positive_rate = 0.0

    zero_tolerance_ok = false_positive_rate <= G7_FALSE_POSITIVE_RATE_MAX

    return {
        "section": "5_zero_tolerance_invariant",
        "n_overturn_curator_in_window": n_overturn_in_window,
        "n_reviewed_in_window": n_reviewed_in_window,
        "false_positive_rate": false_positive_rate,
        "G7_FALSE_POSITIVE_RATE_MAX": G7_FALSE_POSITIVE_RATE_MAX,
        "zero_tolerance_ok": zero_tolerance_ok,
        "note": (
            "ZERO TOLERANCE: any positive false_positive_rate blocks "
            "Curator O3_ACT graduation independent of acceptance rate"
        ),
    }


def run_audit(db_path: Path) -> tuple[dict, int]:
    """Execute all 5 sections and produce the consolidated report + exit code."""
    if not db_path.exists():
        return (
            {
                "error": f"DB path does not exist: {db_path}",
                "exit_code": 4,
            },
            4,
        )

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return (
            {
                "error": f"sqlite3 connection failed: {exc}",
                "exit_code": 4,
            },
            4,
        )

    try:
        s1 = section_1_curator_presence(conn)
        if not s1["curator_present"]:
            return (
                {
                    "section_1_curator_presence": s1,
                    "verdict": "NO_CURATOR_DRAFTS",
                    "reason": (
                        "Curator agent has produced 0 drafts. Verify that "
                        "(a) Curator is registered in AgentRegistry at "
                        "agent_id 0xed6a2df5..., (b) Curator's polling "
                        "loop is enabled (OPERATOR_AGENT_CURATOR_*_TRIGGER_"
                        "ENABLED env vars true), and (c) trigger sources "
                        "have fired marketplace_listing / "
                        "anchor_freshness_alert / periodic_compliance "
                        "events at least once."
                    ),
                    "exit_code": 3,
                },
                3,
            )

        agent_id = s1["curator_agent_id"]
        s2 = section_2_window_counts(conn, agent_id)
        s3 = section_3_last_n_breakdown(conn, agent_id)
        s4 = section_4_gate_evaluation(s2, s3)
        s5 = section_5_zero_tolerance_invariant(conn, agent_id)

        # Final exit code: section 4 verdict drives gate state, but a
        # ZERO TOLERANCE violation in section 5 forces FAIL even if
        # section 4 reports PASS.
        if not s5["zero_tolerance_ok"]:
            final_exit = 2
            final_verdict = "FAIL_ZERO_TOLERANCE_VIOLATION"
        else:
            final_exit = s4["exit_code_for_this_section"]
            final_verdict = s4["verdict"]

        return (
            {
                "audit": "g7_curator_review_readiness",
                "timestamp_unix": time.time(),
                "section_1_curator_presence": s1,
                "section_2_window_counts": s2,
                "section_3_last_n_breakdown": s3,
                "section_4_gate_evaluation": s4,
                "section_5_zero_tolerance_invariant": s5,
                "final_verdict": final_verdict,
                "final_exit_code": final_exit,
            },
            final_exit,
        )
    finally:
        conn.close()


def render_human(report: dict) -> str:
    """Render the report as a human-readable text block."""
    if "error" in report:
        return (
            f"ERROR: {report['error']}\n"
            f"Exit code: {report.get('exit_code', 4)}\n"
        )

    # NO_CURATOR_DRAFTS early-return: section 1 ran but the gate cannot
    # evaluate. Render the minimum surface.
    if report.get("verdict") == "NO_CURATOR_DRAFTS":
        lines = [
            "=" * 70,
            "VBDIP-0002 §B.8 G7 — Curator Review Readiness Audit",
            "=" * 70,
            "",
            "Section 1 — Curator agent_id resolution",
        ]
        s1 = report["section_1_curator_presence"]
        lines.append(f"  curator_agent_id: {s1['curator_agent_id']}")
        lines.append(f"  is_q9_hex:        {s1['is_q9_hex']}")
        lines.append(f"  total_drafts_ever: {s1['total_drafts_ever']}")
        lines.append("")
        lines.append("=" * 70)
        lines.append("FINAL VERDICT: NO_CURATOR_DRAFTS")
        lines.append(f"Reason: {report.get('reason', '')}")
        lines.append(f"Exit code: {report.get('exit_code', 3)}")
        lines.append("=" * 70)
        return "\n".join(lines)

    lines = []
    lines.append("=" * 70)
    lines.append("VBDIP-0002 §B.8 G7 — Curator Review Readiness Audit")
    lines.append("=" * 70)
    lines.append(f"Audit time (unix): {report['timestamp_unix']:.0f}")
    lines.append("")

    s1 = report["section_1_curator_presence"]
    lines.append("Section 1 — Curator agent_id resolution")
    lines.append(f"  curator_agent_id: {s1['curator_agent_id']}")
    lines.append(f"  is_q9_hex:        {s1['is_q9_hex']}")
    lines.append(f"  total_drafts_ever: {s1['total_drafts_ever']}")
    lines.append("")

    s2 = report["section_2_window_counts"]
    lines.append(f"Section 2 — 7-day trailing window counts")
    lines.append(f"  window_days:           {s2['window_days']}")
    lines.append(f"  total_in_window:       {s2['total_in_window']}")
    lines.append(f"  reviewed_in_window:    {s2['reviewed_in_window']}")
    lines.append(f"  unreviewed_in_window:  {s2['unreviewed_in_window']}")
    lines.append("")

    s3 = report["section_3_last_n_breakdown"]
    lines.append(f"Section 3 — Last {s3['last_n']} reviewed Curator drafts")
    lines.append(f"  n_reviewed_returned:    {s3['n_reviewed_returned']}")
    lines.append(f"  n_accept:               {s3['n_accept']}")
    lines.append(f"  n_reject:               {s3['n_reject']}")
    lines.append(f"  n_overturn_curator:     {s3['n_overturn_curator']}")
    lines.append(f"  n_other_anomalous:      {s3['n_other_anomalous']}")
    lines.append("")

    s4 = report["section_4_gate_evaluation"]
    lines.append("Section 4 — Gate evaluation")
    lines.append(f"  verdict:                  {s4['verdict']}")
    lines.append(f"  reason:                   {s4['reason']}")
    lines.append(f"  n_accept / G7_MIN_ACCEPT: "
                 f"{s4['n_accept_in_last_n']} / {G7_MIN_ACCEPT}")
    lines.append("")

    s5 = report["section_5_zero_tolerance_invariant"]
    lines.append("Section 5 — ZERO TOLERANCE invariant")
    lines.append(f"  n_overturn_in_window:  {s5['n_overturn_curator_in_window']}")
    lines.append(f"  false_positive_rate:   {s5['false_positive_rate']:.4f}")
    lines.append(f"  zero_tolerance_ok:     {s5['zero_tolerance_ok']}")
    lines.append("")

    lines.append("=" * 70)
    lines.append(f"FINAL VERDICT: {report['final_verdict']}")
    lines.append(f"Exit code: {report['final_exit_code']}")
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="VBDIP-0002 §B.8 G7 Curator Review Readiness audit",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to vapi_store.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human report",
    )
    args = parser.parse_args(argv)

    # Reconfigure stdout to utf-8 on Windows so the unicode section markers
    # render cleanly. Matches the pattern in
    # scripts/zkba_post_ceremony_audit.py.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    report, exit_code = run_audit(args.db)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
