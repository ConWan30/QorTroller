#!/usr/bin/env python3
"""P1 anomaly diagnostic runner (F-P0A-V2-1). Design: docs/p1-anomaly-diagnostic-design-2026-07-10.md.

Loads sessions_l9/*.npz, scores via the P0-A path, classifies why P1 stays below TAU_HUMAN on aim-active
sessions into a closed enum (MARGINAL_AIM / HIGH_RESIDUAL / LAG_REGIME / PROTOCOL_MIX /
GENUINE_LOW_COUPLING / INCONCLUSIVE). Offline · advisory · does NOT touch P0-A v2 SEPARATED.

Usage: python scripts/run_p1_anomaly_diagnostic.py [--glob sessions_l9/*.npz]
    -> audits/p1-anomaly-diagnostic-<date>.{json,md}
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.p1_anomaly_diagnostic import classify_p1_anomaly, session_metrics
from l9_presence.session_recorder import load_session


def main() -> int:
    ap = argparse.ArgumentParser(description="P1 anomaly diagnostic (F-P0A-V2-1)")
    ap.add_argument("--glob", default="sessions_l9/*.npz")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    metrics = []
    for p in sorted(glob.glob(a.glob)):
        try:
            m = session_metrics(load_session(p))
        except Exception:  # noqa: BLE001 — a torn .npz never blocks the diagnostic
            continue
        if m is not None:
            m["_path"] = os.path.basename(p)
            metrics.append(m)

    if not metrics:
        print("UNVERIFIABLE: no scorable sessions", file=sys.stderr)
        return 1

    report = classify_p1_anomaly(metrics)
    d = report.to_dict()
    d["positive_glob"] = a.glob

    date = time.strftime("%Y-%m-%d")
    out_json = a.out or f"audits/p1-anomaly-diagnostic-{date}.json"
    out_md = out_json.replace(".json", ".md")
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2, sort_keys=True)
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(report.to_markdown())
    print(report.to_markdown())
    print(f"\nwrote {out_json} + {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
