#!/usr/bin/env python3
"""Replay stored L6B diagnostics with true-latency classifier (desk human_max=350).

Read-only report against ~/.vapi/bridge.db — does not mutate rows.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bridge"))

from controller.l6b_reflex_analyzer import L6bReflexAnalyzer  # noqa: E402


def _classify_from_diagnostic(
    diag: dict,
    *,
    human_max_ms: float,
) -> str | None:
    true_ms = diag.get("true_latency_ms")
    legacy_ms = diag.get("legacy_index_latency_ms", -1)
    reflex_gap = diag.get("reflex_gap_ms")
    threshold = float(diag.get("response_threshold_lsb", 500))
    peak = 0.0
    for row in diag.get("samples") or []:
        peak = max(peak, float(row.get("delta", 0)))
    if peak < threshold:
        return "NO_RESPONSE"
    analyzer = L6bReflexAnalyzer(human_max_ms=human_max_ms)
    canonical = float(true_ms) if true_ms is not None else float(legacy_ms)
    if canonical < 0:
        return "NO_RESPONSE"
    return analyzer._classify(
        canonical_ms=canonical,
        true_latency_ms=float(true_ms) if true_ms is not None else -1.0,
        peak=peak,
        reflex_gap_ms=float(reflex_gap) if reflex_gap is not None else None,
    )


def main() -> int:
    db_path = Path.home() / ".vapi" / "bridge.db"
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    if not db_path.is_file():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT p.classification AS old_class, p.reflex_verdict, d.diagnostic_json,
               p.accel_delta_peak, p.device_id
        FROM l6b_probe_diagnostic d
        JOIN l6b_probe_log p ON p.id = d.probe_log_id
        ORDER BY p.id
        """
    ).fetchall()
    conn.close()

    force200 = [
        r for r in rows
        if json.loads(r["diagnostic_json"]).get("probe_r2_force") == 200
    ]

    def tally(subset: list, human_max: float) -> dict[str, int]:
        counts: dict[str, int] = {}
        reflex = 0
        for r in subset:
            diag = json.loads(r["diagnostic_json"])
            new_class = _classify_from_diagnostic(diag, human_max_ms=human_max)
            counts[new_class or "?"] = counts.get(new_class or "?", 0) + 1
            if new_class == "HUMAN":
                reflex += 1
        counts["REFLEX_OBSERVED"] = reflex
        counts["total"] = len(subset)
        return counts

    all_tally_280 = tally(rows, 280.0)
    all_tally_350 = tally(rows, 350.0)
    f200_tally_350 = tally(force200, 350.0)

    print("=== L6B corpus reclassify (true_latency + reflex_gap guard) ===")
    print(f"DB: {db_path}")
    print(f"All probes: {len(rows)}")
    print(f"force=200 subset: {len(force200)}")
    print()
    print("All probes @ human_max=280:", all_tally_280)
    print("All probes @ human_max=350:", all_tally_350)
    print("force=200 @ human_max=350:", f200_tally_350)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
