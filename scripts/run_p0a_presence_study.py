#!/usr/bin/env python3
"""P0-A presence-oracle separation study runner (design docs/p0a-presence-separation-study-design.md).

Loads the developer_self human L9 corpus (sessions_l9/*.npz), derives the paired modeled-automation
negative class in-process (synth_adversary), scores both through the SAME oracle path, and writes a
pre-registered separation operating point. Offline · advisory · developer_self · zero capture-path.

Usage:
    python scripts/run_p0a_presence_study.py [--glob sessions_l9/*.npz] [--seed 0] [--subset N]
    -> audits/p0a-presence-op-<date>.json + .md
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

from l9_presence.presence_separation_study import run_separation_study
from l9_presence.session_recorder import load_session


def main() -> int:
    ap = argparse.ArgumentParser(description="P0-A presence-oracle separation study")
    ap.add_argument("--glob", default="sessions_l9/*.npz", help="positive human L9 corpus glob")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--subset", type=int, default=0, help="use first N sessions (0 = all)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    paths = sorted(glob.glob(a.glob))
    if a.subset:
        paths = paths[:a.subset]
    if not paths:
        print(f"UNVERIFIABLE: no sessions matched {a.glob!r}", file=sys.stderr)
        return 1

    # load + prefer label=="human" positives (the corpus is developer_self human; drop any non-human
    # labels like a stray "scripted" so the positive class is real captures only — design §5.1)
    sessions, excluded_labels = [], {}
    for p in paths:
        try:
            s = load_session(p)
        except Exception as e:  # noqa: BLE001 — a torn .npz never blocks the study
            excluded_labels[f"load_error:{os.path.basename(p)}"] = str(e)[:60]
            continue
        lab = (s.label or "").strip().lower()
        if lab and lab not in ("human", ""):
            excluded_labels[lab] = excluded_labels.get(lab, 0) + 1
            continue
        sessions.append(s)

    print(f"loaded {len(sessions)} positive human sessions from {len(paths)} files "
          f"(excluded labels: {excluded_labels or 'none'}); deriving {len(sessions)*3} negatives ...",
          flush=True)

    report = run_separation_study(sessions, seed=a.seed)
    d = report.to_dict()
    d["positive_glob"] = a.glob
    d["excluded_labels"] = excluded_labels

    date = time.strftime("%Y-%m-%d")
    out_json = a.out or f"audits/p0a-presence-op-{date}.json"
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
