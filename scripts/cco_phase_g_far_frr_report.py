"""
cco_phase_g_far_frr_report.py — per-tier FAR/FRR summary from tagged L6B corpus.

FAR (false accept): non-HUMAN classification that would fail a HUMAN-only gate
  — reported as share of corpus (BOT + INCONCLUSIVE + NO_RESPONSE treated as
  would-be false accepts if an attacker spoofed human-only policy incorrectly).

FRR (false reject): HUMAN rows with reflex_verdict != REFLEX_OBSERVED, or
  reclassified away from HUMAN when true-latency replay is available.

USAGE
-----
  python scripts/cco_phase_g_far_frr_report.py
  python scripts/cco_phase_g_far_frr_report.py --profile sony_dualsense_v1
  python scripts/cco_phase_g_far_frr_report.py --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.cco_controller_class_research import (  # noqa: E402
    resolve_controller_class_tier,
)
from bridge.vapi_bridge.config import Config  # noqa: E402

_HUMAN_ONLY = frozenset({"HUMAN"})
_NON_HUMAN = frozenset({"BOT", "INCONCLUSIVE", "NO_RESPONSE"})


def _tier_for_profile(profile_id: str | None) -> str:
    if not profile_id or str(profile_id).strip() in ("", "untagged"):
        return "untagged"
    return resolve_controller_class_tier(str(profile_id))


def _summarize_rows(rows: list[sqlite3.Row]) -> dict:
    total = len(rows)
    if total == 0:
        return {
            "n": 0,
            "classification_counts": {},
            "reflex_verdict_counts": {},
            "human_n": 0,
            "human_reflex_observed_n": 0,
            "far_rate": None,
            "frr_rate": None,
            "latency_human_ms": {},
            "peak_human_lsb": {},
        }

    class_counts: dict[str, int] = {}
    verdict_counts: dict[str, int] = {}
    human_latencies: list[float] = []
    human_peaks: list[float] = []
    human_n = 0
    human_reflex = 0

    for r in rows:
        cls = r["classification"] or "?"
        class_counts[cls] = class_counts.get(cls, 0) + 1
        rv = r["reflex_verdict"] or "unset"
        verdict_counts[rv] = verdict_counts.get(rv, 0) + 1
        if cls == "HUMAN":
            human_n += 1
            if rv == "REFLEX_OBSERVED":
                human_reflex += 1
            if r["latency_ms"] is not None:
                human_latencies.append(float(r["latency_ms"]))
            if r["accel_delta_peak"] is not None:
                human_peaks.append(float(r["accel_delta_peak"]))

    non_human_n = sum(class_counts.get(c, 0) for c in _NON_HUMAN)
    # FAR proxy: non-HUMAN share (would incorrectly pass only if gate were broken)
    far_rate = round(non_human_n / total, 4) if total else None
    # FRR proxy: HUMAN rows not REFLEX_OBSERVED
    frr_rate = round((human_n - human_reflex) / human_n, 4) if human_n else None

    def _stats(vals: list[float]) -> dict:
        if not vals:
            return {}
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        return {
            "n": n,
            "mean": round(sum(vals_sorted) / n, 2),
            "min": round(vals_sorted[0], 2),
            "max": round(vals_sorted[-1], 2),
            "p05": round(vals_sorted[max(0, int(0.05 * (n - 1)))], 2),
            "p50": round(vals_sorted[n // 2], 2),
            "p95": round(vals_sorted[min(n - 1, int(0.95 * (n - 1)))], 2),
        }

    return {
        "n": total,
        "classification_counts": class_counts,
        "reflex_verdict_counts": verdict_counts,
        "human_n": human_n,
        "human_reflex_observed_n": human_reflex,
        "far_rate": far_rate,
        "frr_rate": frr_rate,
        "latency_human_ms": _stats(human_latencies),
        "peak_human_lsb": _stats(human_peaks),
    }


def _fetch_rows(conn: sqlite3.Connection, profile_id: str | None) -> list[sqlite3.Row]:
    if profile_id:
        return conn.execute(
            """
            SELECT classification, reflex_verdict, latency_ms, accel_delta_peak, cco_profile_id
            FROM l6b_probe_log
            WHERE cco_profile_id = ?
            ORDER BY id
            """,
            (profile_id,),
        ).fetchall()
    return conn.execute(
        """
        SELECT classification, reflex_verdict, latency_ms, accel_delta_peak, cco_profile_id
        FROM l6b_probe_log
        WHERE cco_profile_id IS NOT NULL AND TRIM(cco_profile_id) != ''
        ORDER BY id
        """
    ).fetchall()


def _print_human(report: dict, db_path: Path) -> None:
    print(f"DB: {db_path}")
    print("CCO Phase G — FAR/FRR proxy (HUMAN-only gate + REFLEX_OBSERVED verdict)")
    print(
        "  FAR proxy = non-HUMAN share (BOT/INCONCLUSIVE/NO_RESPONSE); "
        "FRR proxy = HUMAN without REFLEX_OBSERVED"
    )
    print()
    for tier, block in report["by_tier"].items():
        print(f"=== {tier} ===")
        for pid, summary in sorted(block.get("by_profile", {}).items()):
            print(f"  profile {pid}: N={summary['n']}")
            print(f"    classification: {summary['classification_counts']}")
            print(f"    reflex_verdict: {summary['reflex_verdict_counts']}")
            print(
                f"    FAR proxy={summary['far_rate']}  "
                f"FRR proxy={summary['frr_rate']}  "
                f"human={summary['human_n']} reflex_obs={summary['human_reflex_observed_n']}"
            )
            if summary.get("latency_human_ms"):
                print(f"    HUMAN latency_ms: {summary['latency_human_ms']}")
            if summary.get("peak_human_lsb"):
                print(f"    HUMAN peak LSB: {summary['peak_human_lsb']}")
        tier_summary = block.get("tier_summary") or {}
        if tier_summary.get("n"):
            print(
                f"  tier totals: N={tier_summary['n']} "
                f"FAR={tier_summary['far_rate']} FRR={tier_summary['frr_rate']}"
            )
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None)
    parser.add_argument("--profile", default=None, help="Filter one cco_profile_id")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db or Config().db_path)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = _fetch_rows(conn, args.profile)
    finally:
        conn.close()

    by_tier: dict[str, dict] = {}
    for row in rows:
        pid = row["cco_profile_id"]
        tier = _tier_for_profile(pid)
        tier_block = by_tier.setdefault(
            tier,
            {"by_profile": {}, "tier_summary": None},
        )
        profile_rows = tier_block["by_profile"].setdefault(pid, [])
        profile_rows.append(row)

    for tier, block in by_tier.items():
        all_tier_rows: list[sqlite3.Row] = []
        for pid, prow in block["by_profile"].items():
            summary = _summarize_rows(prow)
            block["by_profile"][pid] = summary
            all_tier_rows.extend(prow)
        block["tier_summary"] = _summarize_rows(all_tier_rows)

    report = {"db": str(db_path), "by_tier": by_tier}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report, db_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
